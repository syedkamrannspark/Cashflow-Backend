"""
Dynamic NL → SQL Agent (Schema-aware, Self-Correcting)
Generates SQL from natural language and returns ONLY raw data to orchestrator.
"""

import logging
import json
import re
from typing import Dict, Any, List
import httpx

from app.core.database import SessionLocal
from app.core.config import settings
from app.models.csv_metadata import CSVMetadata
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class NL2SQLAgent:
    """Natural language → SQL → Execute → return raw data (no insights here)."""

    def __init__(self):
        self._schema_cache = None  # cache schema to avoid repeated DB calls

    def _load_schema(self) -> Dict[str, Any]:
        """
        Dynamically fetch DB schema. 
        For this simplified agent, we focus on 'csv_documents' and use 'csv_metadata'
        to understand the structure of the JSON data in 'full_data'.
        """
        db: Session = SessionLocal()
        try:
            # 1. Base table schema
            schema = {
                "csv_documents": [
                    {"column": "id", "type": "integer"},
                    {"column": "filename", "type": "string"},
                    {"column": "upload_date", "type": "datetime"},
                    {"column": "row_count", "type": "integer"},
                    {"column": "full_data", "type": "json (list of objects)", "description": "Contains the actual CSV rows. keys defined below."}
                ]
            }

            # 2. Fetch metadata to know what keys are inside full_data
            metadata_rows = db.query(CSVMetadata).all()
            
            # Group metadata by column_name (across all files) or just list all unique columns
            # For simplicity, we'll list all unique columns found in metadata
            unique_columns = {}
            for row in metadata_rows:
                if row.column_name not in unique_columns:
                    unique_columns[row.column_name] = {
                        "type": row.data_type,
                        "description": row.description or row.alias or ""
                    }
            
            # Add these as "virtual columns" description to full_data
            keys_desc = ", ".join([f"{k} ({v['type']})" for k, v in unique_columns.items()])
            schema["csv_documents"][4]["keys_available"] = keys_desc
            
            self._schema_cache = schema
            logger.info(f"[NL2SQL] Loaded schema with {len(unique_columns)} virtual columns from metadata.")
            return schema
        except Exception as e:
            logger.error(f"Error loading schema: {e}")
            return {}
        finally:
            db.close()

    async def _call_llm_for_sql(self, natural_query: str, schema: Dict[str, Any], previous_error: str = None) -> str:
        """Generate SQL from natural language using schema-aware prompt."""
        print(schema, "schema")

        schema_json = json.dumps(schema, indent=2)

        prompt = f"""
You are a senior data engineer generating optimal PostgreSQL queries from natural language.


YOUR OBJECTIVE:
- Produce the most efficient SQL based on user intent
- Decide automatically whether to aggregate or return detailed rows
- Optimize for minimal result size without losing meaning

CONTEXT:
- You know ONLY this database schema (in JSON form below).
- You do NOT know the business domain.

DATABASE SCHEMA (JSON):
{schema_json}


PRINCIPLES:
- The data is stored in `csv_documents` table, column `full_data`.
- `full_data` is a JSON ARRAY of objects.
- To query the rows, you MUST use `json_array_elements(full_data)` (Postgres).
- Example: 
  SELECT (elem->>'Amount')::numeric, elem->>'Date' 
  FROM csv_documents, json_array_elements(full_data) AS elem 
  WHERE filename = '...'
- If querying across ALL files, omit filename check.
- Infer if user wants aggregation (summary, comparison, deviation, trend, total, avg)
- If query implies analytics → aggregate + group BY relevant fields automatically
- If query implies listing entities → return detailed rows
- Only SELECT statements. No DML (INSERT/UPDATE/DELETE).
- Output ONLY SQL. No markdown, no explanation, no comments.

BEHAVIOR RULES:
- Prefer fewer rows over many rows
- CAST json values to appropriate types (::numeric, ::date) before aggregating.
- NEVER guess column names. Use only schema-provided keys.
- If your first attempt fails, you will get the error and rewrite.

User question:
"{natural_query}"
"""

        if previous_error:
            prompt += f"\nThe earlier SQL failed with error: {previous_error}\nRewrite corrected SQL."

        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": settings.LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 500,
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                f"{settings.LLM_BASE_URL}/chat/completions",
                headers=headers,
                json=payload
            )

        if resp.status_code != 200:
            raise Exception(f"LLM API Error: {resp.status_code} - {resp.text}")

        print(resp.json(), "NL2SQL response")
        sql = resp.json()["choices"][0]["message"]["content"]
        print(sql, "NL2SQL sql response")
        return self._cleanup_sql(sql)

    @staticmethod
    def _cleanup_sql(sql: str) -> str:
        """Cleanup SQL if LLM returns it wrapped inside ```sql blocks."""
        return re.sub(r"```(sql)?|```", "", sql).strip().rstrip(";") + ";"

    @staticmethod
    def _is_safe_query(sql: str) -> bool:
        """Allow only SELECT queries. Block dangerous commands."""
        sql_lower = sql.lower()
        return sql_lower.startswith("select") and not any(
            keyword in sql_lower for keyword in
            ["delete", "update", "insert", "drop", "alter", "truncate"]
        )

    def _execute_sql(self, sql: str) -> List[Dict[str, Any]]:
        """Execute SQL safely using synchronous SQLAlchemy session."""
        if not self._is_safe_query(sql):
            raise Exception(f"Unsafe query rejected: {sql}")

        db: Session = SessionLocal()
        try:
            result = db.execute(text(sql))
            # Convert mappings to dict
            rows = [dict(row) for row in result.mappings()]
            return rows
        except Exception as e:
            logger.error(f"SQL Execution Error: {e}")
            raise e
        finally:
            db.close()

    def _reduce_for_llm(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Reduce large SQL result into statistical summary for hallucination-proof insights."""
        if not rows:
            return {}

        from statistics import mean

        sample = rows[0]
        numeric_cols = [k for k, v in sample.items() if isinstance(v, (int, float))]

        summary = {
            "total_rows": len(rows),
            "columns": list(sample.keys()),
            "numeric_summary": {
                col: {
                    "min": min(r[col] for r in rows),
                    "max": max(r[col] for r in rows),
                    "avg": mean(r[col] for r in rows)
                }
                for col in numeric_cols
            }
        }

        return summary

    async def process_natural_query(self, natural_query: str) -> Dict[str, Any]:
        """Full pipeline: NL → SQL → Execute → return result to orchestrator."""

        # Schema loading is now sync, but we can call it here
        schema = self._load_schema()

        # SQL attempt #1
        try:
            sql = await self._call_llm_for_sql(natural_query, schema)
            logger.info(f"[NL2SQL] Generated SQL: {sql}")
            # _execute_sql is sync, so we just call it (blocking the loop slightly, but acceptable)
            results = self._execute_sql(sql)

        except Exception as first_error:
            logger.warning(f"[NL2SQL] First SQL failed: {first_error}")

            # SQL attempt #2 - retry with error feedback
            sql = await self._call_llm_for_sql(
                natural_query, schema, previous_error=str(first_error)
            )
            logger.info(f"[NL2SQL] Retried SQL: {sql}")
            results = self._execute_sql(sql)

    
        if len(results) > 200:
            logger.warning(f"[NL2SQL] Returned {len(results)} asking LLM to optimize (dynamic, zero template)"
            )


            optimization_prompt =f"""
Rewrite the following SQL to return fewer rows, while maintaining the SAME filters and intent.

RULES:
- KEEP the original WHERE clause EXACTLY as-is.
- Decide aggregation based on the data:
    * If there is a numeric measure (capacity, amount, mw, deviation, etc.):
        → use SUM() and COUNT() by the most meaningful dimension (e.g., customer_name or project).
    * Use AVG() **only if the user explicitly asked for "average"**.
- DO NOT remove necessary grouping dimensions.
- Output ONLY SELECT SQL. No explanation.

ORIGINAL SQL:
{sql}
"""
            

            sql = await self._call_llm_for_sql(
                optimization_prompt,
                schema
            )
            logger.info(f"[NL2SQL] Optimized SQL: {sql}")

            results = self._execute_sql(sql)

        # ✅ return ONLY raw data. Insights agent will handle formatting.
        return {
            "success": True,
            "sql_query": sql,
            "row_count": len(results),  # give orchestrator a small preview
            "data_full": results,        # full data sent to insights agent
            "confidence": 0.95,
        }


# Required by orchestrator
nl2sql_agent = NL2SQLAgent()
