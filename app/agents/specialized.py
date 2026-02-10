from typing import Any, Dict, List
from app.agents.base import Agent
from app.core.database import SessionLocal
from app.models.csv_document import CSVDocument
from app.models.csv_metadata import CSVMetadata
from datetime import datetime
import textwrap

def _filter_data_by_metadata(full_data: list, metadata: list) -> list:
    """Filter dataset to only include target/helper columns."""
    if not full_data or not metadata:
        return full_data
    relevant_columns = {m["column_name"] for m in metadata if m.get("is_target") or m.get("is_helper")}
    if not relevant_columns:
        return full_data
    filtered = []
    for row in full_data:
        filtered_row = {col: value for col, value in row.items() if col in relevant_columns}
        if filtered_row:
            filtered.append(filtered_row)
    return filtered

class Sensor(Agent):
    def __init__(self):
        super().__init__(name="Sensor", role="Data Collection")

    def process(self, input_data: Any) -> Dict[str, Any]:
        prompt = input_data.get("prompt", "")
        db = SessionLocal()
        try:
            documents = db.query(CSVDocument).order_by(CSVDocument.upload_date.desc()).all()
            if not documents:
                return {"status": "error", "message": "No uploaded files found. Please upload a file first."}

            document_ids = [doc.id for doc in documents]
            metadata_rows = db.query(CSVMetadata).filter(CSVMetadata.document_id.in_(document_ids)).all()

            metadata_by_doc = {}
            for meta in metadata_rows:
                if meta.document_id not in metadata_by_doc:
                    metadata_by_doc[meta.document_id] = []
                metadata_by_doc[meta.document_id].append(meta)

            dataset = {
                "documents": [
                    {
                        "id": doc.id,
                        "filename": doc.filename,
                        "row_count": doc.row_count,
                        "column_count": doc.column_count,
                        "upload_date": str(doc.upload_date),
                        "full_data": _filter_data_by_metadata(
                            doc.full_data or [],
                            [{"column_name": m.column_name, "data_type": m.data_type, "connection_key": m.connection_key, "alias": m.alias, "description": m.description, "is_target": m.is_target, "is_helper": m.is_helper} for m in metadata_by_doc.get(doc.id, [])]
                        ),
                        "metadata": [{"column_name": m.column_name, "data_type": m.data_type, "connection_key": m.connection_key, "alias": m.alias, "description": m.description, "is_target": m.is_target, "is_helper": m.is_helper} for m in metadata_by_doc.get(doc.id, []) if m.is_target or m.is_helper],
                    }
                    for doc in documents
                ]
            }
            return {
                "status": "success",
                "message": f"Fetched {len(documents)} uploaded file(s) with metadata.",
                "data": dataset,
                "metrics": [{"label": "Files", "value": str(len(documents))}, {"label": "Total Rows", "value": str(sum(d["row_count"] for d in dataset["documents"]))}, {"label": "Source", "value": "Uploaded Files"}]
            }
        except Exception as e:
            return {"status": "error", "message": f"Data collection failed: {str(e)}"}
        finally:
            db.close()

class Analyzer(Agent):
    def __init__(self):
        super().__init__(name="Analyzer", role="Data Analysis")

    def process(self, input_data: Any) -> Dict[str, Any]:
        dataset = input_data.get("data", {})
        user_prompt = input_data.get("prompt", "Analyze the financial data.")
        documents = dataset.get("documents", [])
        
        if not documents:
            return {"status": "error", "message": "No data available to analyze."}
        
        documents_summary = ""
        for doc in documents:
            documents_summary += f"\n\n--- FILE: {doc['filename']} ---\n"
            documents_summary += f"Rows: {doc['row_count']}, Columns: {doc['column_count']}, Upload Date: {doc['upload_date']}\n"
            if doc['metadata']:
                documents_summary += f"Column Metadata:\n"
                for meta in doc['metadata']:
                    documents_summary += f"  - {meta['alias'] or meta['column_name']} ({meta['data_type']}): {meta['description']}\n"
            documents_summary += f"Data (first 50 rows):\n"
            for idx, row in enumerate(doc['full_data'][:50]):
                documents_summary += f"  Row {idx + 1}: {row}\n"
        
        prompt = f"""
        You are a Financial Analyst.
        Answer the User's Request ONLY using the provided data. DO NOT hallucinate.
         
        User Request: "{user_prompt}"
         
        --- UPLOADED DATA ---
        Total Files: {len(documents)}
        {documents_summary}
         
        --- INSTRUCTIONS ---
        1. Analyze ONLY the provided data.
        2. Use actual numbers from the data.
        3. State what is missing if insufficient.
        4. NEVER hallucinate or invent data.
        5. Format in Markdown.
        6. Provide evidence from data.
        """
        
        analysis_text = self.llm.generate(prompt, system_message="You are a financial analyst. Only use provided data, do not hallucinate.")
        
        return {
            "status": "success",
            "message": "Financial analysis completed.",
            "analysis": analysis_text,
            "metrics": [{"label": "Files Analyzed", "value": str(len(documents))}, {"label": "Total Records", "value": str(sum(d['row_count'] for d in documents))}]
        }

class Responder(Agent):
    def __init__(self):
        super().__init__(name="Responder", role="Report Generator")

    def process(self, input_data: Any) -> Dict[str, Any]:
        # input_data is the analysis result
        analysis = input_data.get("analysis", "")
        
        # Just formatting for the final report
        # Use LLM to ensure the final report is polished (optional, but good for "Responder" role)
        # But for now, we trust the Analyzer's markdown output and just wrap it.
        
        report = textwrap.dedent(f"""
            # Financial Report

            {analysis}

            *Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
        """)
        
        return {
            "status": "success",
            "message": "Report generated and delivered.",
            "report": report,
            "metrics": [
                {"label": "Report Length", "value": f"{len(report)} chars"}
            ]
        }

class Learner(Agent):
    def __init__(self):
        super().__init__(name="Learner", role="Continuous Learning")

    def process(self, input_data: Any) -> Dict[str, Any]:
        # Stub implementation
        return {
            "status": "idle",
            "message": "Learning cycle deferred.",
            "metrics": []
        }
