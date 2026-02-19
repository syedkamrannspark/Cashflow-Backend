import json
import requests
import re
from app.core.config import settings

def _clean_llm_json_response(content: str) -> str:
    """
    Clean LLM response by removing markdown code blocks and extra formatting.
    Handles cases where LLM returns ```json ... ``` or ``` ... ```
    """
    content = content.strip()
    
    # Remove markdown code blocks
    if content.startswith("```"):
        # Find the start and end of code block
        lines = content.split('\n')
        # Remove first line (```json or ```)
        lines = lines[1:]
        # Remove last line if it's ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = '\n'.join(lines).strip()
    
    return content

def _extract_json_from_response(content: str) -> str:
    """
    Extract JSON from various response formats.
    Handles:
    - Plain JSON
    - JSON wrapped in markdown code blocks
    - JSON embedded in prose/explanations
    """
    content = content.strip()
    
    # First try to clean markdown code blocks
    cleaned = _clean_llm_json_response(content)
    
    # If it starts with { or [, try to parse it directly
    if cleaned.startswith('{') or cleaned.startswith('['):
        return cleaned
    
    # Try to find JSON object in the content using regex
    # Look for pattern: { ... } at any nesting level
    json_match = re.search(r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}', content, re.DOTALL)
    if json_match:
        potential_json = json_match.group(0)
        try:
            # Verify it's valid JSON
            json.loads(potential_json)
            return potential_json
        except:
            pass
    
    # Last resort: try the original cleaned content
    return cleaned

def get_insights(context_data: str) -> str:
    if not settings.OPENROUTER_API_KEY:
        return "AI implementation pending (No API Key)"
        
    url = f"{settings.LLM_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": "You are a financial analyst assistant. Analyze the provided cashflow data and give 3 bullet points of insights/recommendations."},
            {"role": "user", "content": f"Here is the summary of current financial situation:\n{context_data}"}
        ]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data['choices'][0]['message']['content']
    except Exception as e:
        print(f"LLM Error: {e}")
        return "Unable to generate insights at this time."


def get_stats_from_openrouter(payload_data: dict) -> dict:
    if not settings.OPENROUTER_API_KEY:
        return {
            "current": 0,
            "forecast30Day": 0,
            "atRiskInvoices": 0,
            "cashRunway": 0,
            "currentChangePercent": 0,
            "forecastChangePercent": 0,
            "overdueInvoicesCount": 0,
        }

    url = f"{settings.LLM_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    # Optimize payload to avoid token limit errors
    optimized_payload = _optimize_payload_for_llm(payload_data, "payment stats financial metrics")

    system_prompt = (
        "You are a financial calculator. Your ONLY job is to return valid JSON. "
        "Do NOT explain, do NOT use markdown, do NOT include code blocks. "
        "ONLY return a JSON object and nothing else.\n\n"
        "Calculate these 7 metrics from payment data:\n"
        "1. current: Sum of Amount Paid where Status='Completed' or 'Paid'\n"
        "2. forecast30Day: Current + expected inflows for next 30 days\n"
        "3. atRiskInvoices: Sum of Invoice Amount where Days Late > 0\n"
        "4. cashRunway: Current / average daily burn (in days)\n"
        "5. currentChangePercent: (Recent week total - Previous week total) / Previous week total * 100\n"
        "6. forecastChangePercent: (Forecast - Current) / Current * 100\n"
        "7. overdueInvoicesCount: Count of invoices with Days Late > 0 or Status in ['Overdue', 'Unpaid']\n\n"
        "For each metric, also provide a breakdown object with these fields:\n"
        "  - summary: String describing what this metric means\n"
        "  - breakdown: Array of {key, value, label} objects showing the calculation components\n"
        "  - trend: 'up', 'down', or 'stable'\n"
        "  - insights: String with key insights about this metric\n\n"
        "Return ONLY valid JSON. If you cannot calculate a value, use 0."
    )

    user_prompt = (
        "Analyze this payment data and return JSON with the 7 required metrics and breakdowns:\n\n"
        f"{json.dumps(optimized_payload, default=str)}\n\n"
        "Return ONLY this JSON structure, no markdown, no code blocks, no explanation:\n"
        "{\n"
        '  "current": <number>,\n'
        '  "currentBreakdown": {"summary": "<text>", "breakdown": [{"key": "<k>", "value": <n>, "label": "<l>"}], "trend": "<dir>", "insights": "<text>"},\n'
        '  "forecast30Day": <number>,\n'
        '  "forecastBreakdown": {"summary": "<text>", "breakdown": [...], "trend": "<dir>", "insights": "<text>"},\n'
        '  "atRiskInvoices": <number>,\n'
        '  "atRiskBreakdown": {"summary": "<text>", "breakdown": [...], "trend": "<dir>", "insights": "<text>"},\n'
        '  "cashRunway": <number>,\n'
        '  "runwayBreakdown": {"summary": "<text>", "breakdown": [...], "trend": "<dir>", "insights": "<text>"},\n'
        '  "currentChangePercent": <number>,\n'
        '  "forecastChangePercent": <number>,\n'
        '  "overdueInvoicesCount": <number>\n'
        "}"
    )

    payload = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=45)
        response.raise_for_status()
        data = response.json()
        
        if "choices" not in data or not data["choices"]:
            print(f"LLM Error (stats): No choices in response: {data}")
            raise ValueError("Empty choices in LLM response")
        
        content = data["choices"][0]["message"]["content"].strip()
        
        if not content:
            print(f"LLM Error (stats): Empty content in response")
            raise ValueError("Empty message content from LLM")
        
        # Clean and extract JSON from various formats
        cleaned_content = _extract_json_from_response(content)
        parsed = json.loads(cleaned_content)
        
        # Ensure all required fields exist
        result = {
            "current": parsed.get("current", 0),
            "forecast30Day": parsed.get("forecast30Day", 0),
            "atRiskInvoices": parsed.get("atRiskInvoices", 0),
            "cashRunway": parsed.get("cashRunway", 0),
            "currentChangePercent": parsed.get("currentChangePercent", 0),
            "forecastChangePercent": parsed.get("forecastChangePercent", 0),
            "overdueInvoicesCount": parsed.get("overdueInvoicesCount", 0),
        }
        
        # Add optional breakdown objects
        if "currentBreakdown" in parsed:
            result["currentBreakdown"] = parsed["currentBreakdown"]
        if "forecastBreakdown" in parsed:
            result["forecastBreakdown"] = parsed["forecastBreakdown"]
        if "atRiskBreakdown" in parsed:
            result["atRiskBreakdown"] = parsed["atRiskBreakdown"]
        if "runwayBreakdown" in parsed:
            result["runwayBreakdown"] = parsed["runwayBreakdown"]
            
        return result if isinstance(result, dict) else {}
    except json.JSONDecodeError as e:
        print(f"LLM Error (stats): JSON parsing failed: {e}")
        print(f"Raw content: {content if 'content' in locals() else 'N/A'}")
        # Return default values
        return {
            "current": 0,
            "forecast30Day": 0,
            "atRiskInvoices": 0,
            "cashRunway": 0,
            "currentChangePercent": 0,
            "forecastChangePercent": 0,
            "overdueInvoicesCount": 0,
        }
    except Exception as e:
        print(f"LLM Error (stats): {e}")
        print(f"Response status: {response.status_code if 'response' in locals() else 'N/A'}")
        print(f"Response text: {response.text if 'response' in locals() else 'N/A'}")
        return {
            "current": 0,
            "forecast30Day": 0,
            "atRiskInvoices": 0,
            "cashRunway": 0,
            "currentChangePercent": 0,
            "forecastChangePercent": 0,
            "overdueInvoicesCount": 0,
        }

    payload = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=45)
        response.raise_for_status()
        data = response.json()
        
        if "choices" not in data or not data["choices"]:
            print(f"LLM Error (stats): No choices in response: {data}")
            raise ValueError("Empty choices in LLM response")
        
        content = data["choices"][0]["message"]["content"].strip()
        
        if not content:
            print(f"LLM Error (stats): Empty content in response")
            raise ValueError("Empty message content from LLM")
        
        # Clean markdown formatting if present
        cleaned_content = _clean_llm_json_response(content)
        parsed = json.loads(cleaned_content)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError as e:
        print(f"LLM Error (stats): JSON parsing failed: {e}. Content: {content if 'content' in locals() else 'N/A'}")
        return {
            "current": 0,
            "forecast30Day": 0,
            "atRiskInvoices": 0,
            "cashRunway": 0,
            "currentChangePercent": 0,
            "forecastChangePercent": 0,
            "overdueInvoicesCount": 0,
        }
    except Exception as e:
        print(f"LLM Error (stats): {e}")
        print(f"Response status: {response.status_code if 'response' in locals() else 'N/A'}")
        print(f"Response text: {response.text if 'response' in locals() else 'N/A'}")
        return {
            "current": 0,
            "forecast30Day": 0,
            "atRiskInvoices": 0,
            "cashRunway": 0,
            "currentChangePercent": 0,
            "forecastChangePercent": 0,
            "overdueInvoicesCount": 0,
        }


def get_cash_forecast_from_openrouter(payload_data: dict) -> list:
    if not settings.OPENROUTER_API_KEY:
        return []

    url = f"{settings.LLM_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    # Optimize payload to avoid token limit errors
    optimized_payload = _optimize_payload_for_llm(payload_data, "cash forecast position")

    system_prompt = (
        "You are a financial forecasting engine. Use ONLY the provided data to create an 8-point "
        "cash position series: 4 weeks of historical actuals followed by 4 weeks of future forecast. "
        "Do not invent or assume missing values. If data is insufficient, use 0 for numeric fields. "
        "Output must be a JSON array of exactly 8 objects with keys: date, actual, forecasted. "
        "The date values must be 'Week 1' through 'Week 8'. "
        "Weeks 1-4 represent historical actuals (forecasted should be 0). "
        "Weeks 5-8 represent future forecast (actual should be 0). "
        "No extra keys, no prose."
    )

    user_prompt = (
        "Generate a cash position chart series based strictly on the dataset. "
        "Provide 4 weeks of historical actual cash position followed by 4 weeks of future forecast. "
        "Return only the JSON array described above.\n\n"
        f"DATASET_JSON:\n{json.dumps(optimized_payload, default=str)}"
    )

    payload = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0,
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=45)
        response.raise_for_status()
        data = response.json()
        
        if "choices" not in data or not data["choices"]:
            print(f"LLM Error (forecast): No choices in response: {data}")
            return []
        
        content = data["choices"][0]["message"]["content"].strip()
        
        if not content:
            print(f"LLM Error (forecast): Empty content in response")
            return []
        
        # Clean markdown formatting if present
        cleaned_content = _clean_llm_json_response(content)
        parsed = json.loads(cleaned_content)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError as e:
        print(f"LLM Error (forecast): JSON parsing failed: {e}. Content: {content if 'content' in locals() else 'N/A'}")
        return []
    except Exception as e:
        print(f"LLM Error (forecast): {e}")
        print(f"Response status: {response.status_code if 'response' in locals() else 'N/A'}")
        print(f"Response text: {response.text if 'response' in locals() else 'N/A'}")
        return []

def get_data_visualization_from_openrouter(payload_data: dict) -> dict:
    """
    Analyze uploaded data and return structured visualization config with chart data.
    
    Returns:
    {
        "chartType": "line|bar|area",
        "title": "Chart title",
        "xAxisKey": "column name for X axis",
        "yAxisKeys": ["column1", "column2"],
        "data": [{xAxisKey: value, column1: value, column2: value}, ...]
    }
    """
    if not settings.OPENROUTER_API_KEY:
        return {
            "chartType": "line",
            "title": "Data Visualization",
            "xAxisKey": "date",
            "yAxisKeys": [],
            "data": []
        }

    url = f"{settings.LLM_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    # Optimize payload to avoid token limit errors
    optimized_payload = _optimize_payload_for_llm(payload_data, "visualization chart data")

    system_prompt = (
        "You are a data visualization expert. Your ONLY job is to return valid JSON. "
        "Do NOT explain, do NOT use markdown, do NOT include code blocks. "
        "ONLY return a JSON object and nothing else.\n\n"
        "Analyze the provided dataset including CSV documents and their metadata to create the best visualization:\n\n"
        "STEP 1 - Understand the Data:\n"
        "- Review metadata descriptions, aliases, and column types\n"
        "- Prioritize columns marked as 'is_target: true' for Y-axis (main metrics)\n"
        "- Use 'is_helper: true' columns for X-axis or additional context\n"
        "- Read column aliases (user-friendly names) for better labels\n"
        "- Understand data types (numeric, date, categorical)\n\n"
        "STEP 2 - Choose Chart Type Based on Data Nature:\n"
        "- 'line': For time-series data, continuous trends, temporal patterns (dates on X-axis)\n"
        "- 'bar': For categorical comparisons, discrete categories, rankings (categories on X-axis)\n"
        "- 'area': For cumulative values, volume over time, showing magnitude (dates on X-axis)\n\n"
        "STEP 3 - Generate Descriptive Title:\n"
        "- Create a meaningful title that describes what the chart shows\n"
        "- Use column aliases/descriptions from metadata for clarity\n"
        "- Format: '[Metric Name(s)] over [Time Period]' or '[Metric Name(s)] by [Category]'\n"
        "- Example: 'Revenue and Expenses Over Time' or 'Sales by Product Category'\n\n"
        "STEP 4 - Select Axes:\n"
        "- X-axis: Date/time columns (for trends) or categorical columns (for comparisons)\n"
        "- Y-axis: Numeric target columns (prioritize is_target=true)\n"
        "- Use column aliases for better readability\n\n"
        "Return ONLY valid JSON. Sample up to 50 rows for visualization. Base ALL decisions on the actual data and metadata provided."
    )

    user_prompt = (
        "Analyze this uploaded financial data with its metadata and return a chart configuration.\n\n"
        "Dataset structure:\n"
        "- documents: Array of CSV files with full_data (filtered rows)\n"
        "- metadata: Column definitions with aliases, descriptions, data_types, is_target, is_helper flags\n\n"
        f"Data:\n{json.dumps(optimized_payload, default=str)}\n\n"
        "IMPORTANT INSTRUCTIONS:\n"
        "1. Use metadata descriptions and aliases to understand what each column represents\n"
        "2. Prioritize 'is_target: true' columns for Y-axis (these are key metrics)\n"
        "3. Choose chart type based on data patterns (temporal → line, categorical → bar, cumulative → area)\n"
        "4. Generate a descriptive title using column aliases/descriptions\n"
        "5. Use actual column names in xAxisKey and yAxisKeys (not aliases)\n\n"
        "Return ONLY this JSON structure, no markdown, no code blocks, no explanation:\n"
        "{\n"
        '  "chartType": "line|bar|area",\n'
        '  "title": "Descriptive chart title based on metadata and data content",\n'
        '  "xAxisKey": "actual_column_name_for_x_axis",\n'
        '  "yAxisKeys": ["actual_numeric_column1", "actual_numeric_column2"],\n'
        '  "data": [\n'
        '    {"actual_column_name_for_x_axis": "value", "actual_numeric_column1": 123, "actual_numeric_column2": 456},\n'
        '    ...\n'
        '  ]\n'
        "}"
    )

    payload = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        if "choices" not in data or not data["choices"]:
            print(f"LLM Error (visualization): No choices in response: {data}")
            raise ValueError("Empty choices in LLM response")
        
        content = data["choices"][0]["message"]["content"].strip()
        
        if not content:
            print(f"LLM Error (visualization): Empty content in response")
            raise ValueError("Empty message content from LLM")
        
        # Clean and extract JSON
        cleaned_content = _extract_json_from_response(content)
        parsed = json.loads(cleaned_content)
        
        # Validate and return structure
        result = {
            "chartType": parsed.get("chartType", "line"),
            "title": parsed.get("title", "Data Visualization"),
            "xAxisKey": parsed.get("xAxisKey", "date"),
            "yAxisKeys": parsed.get("yAxisKeys", []),
            "data": parsed.get("data", [])
        }
        
        return result
    except json.JSONDecodeError as e:
        print(f"LLM Error (visualization): JSON parsing failed: {e}")
        print(f"Raw content: {content if 'content' in locals() else 'N/A'}")
        return {
            "chartType": "line",
            "title": "Data Visualization",
            "xAxisKey": "date",
            "yAxisKeys": [],
            "data": []
        }
    except Exception as e:
        print(f"LLM Error (visualization): {e}")
        print(f"Response status: {response.status_code if 'response' in locals() else 'N/A'}")
        print(f"Response text: {response.text if 'response' in locals() else 'N/A'}")
        return {
            "chartType": "line",
            "title": "Data Visualization",
            "xAxisKey": "date",
            "yAxisKeys": [],
            "data": []
        }

def get_cash_flow_from_openrouter(payload_data: dict) -> list:
    """
    Generate weekly Cash Inflows vs Outflows based on actual dates in CSV data.
    Extracts date columns from metadata and groups cash flow by weeks found in the data.
    Returns array of weekly data points with actual dates or week labels.
    """
    if not settings.OPENROUTER_API_KEY:
        return []

    url = f"{settings.LLM_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    # Optimize payload to avoid token limit errors
    optimized_payload = _optimize_payload_for_llm(payload_data, "cash flow inflows outflows weekly")

    system_prompt = (
        "You are a financial analytics engine. Analyze the provided CSV data with metadata.\n\n"
        "TASK: Create a weekly Cash Inflows vs Outflows analysis using ACTUAL DATES from the data.\n\n"
        "INSTRUCTIONS:\n"
        "1. IDENTIFY DATE COLUMNS: Look at metadata for columns with data_type='date' or containing 'date'/'time' in the name\n"
        "2. IDENTIFY INFLOW/OUTFLOW COLUMNS: Look at metadata for columns containing 'inflow', 'income', 'revenue', 'outflow', 'expense', 'cost', 'payment'\n"
        "3. GROUP BY WEEKS: Sort data by date and group transactions into weekly buckets\n"
        "4. CALCULATE TOTALS: Sum inflows and outflows for each week\n"
        "5. USE ACTUAL DATES: For each week, use the actual date range found in the data (format YYYY-MM-DD)\n\n"
        "OUTPUT FORMAT:\n"
        "Return a JSON array of objects with this structure:\n"
        "{\n"
        '  "week": "Week 1" or a week label derived from dates (e.g., "Jan 15-21"),\n'
        '  "date": "YYYY-MM-DD" (start date of the week from actual data),\n'
        '  "inflows": <total inflows for that week as number>,\n'
        '  "outflows": <total outflows for that week as number>\n'
        "}\n\n"
        "CRITICAL RULES:\n"
        "- Use ONLY data provided in the dataset\n"
        "- If no date columns exist, create logical week groupings (Week 1, Week 2, etc.)\n"
        "- If inflow/outflow columns don't exist by that name, infer from column descriptions\n"
        "- Return 4 weeks maximum\n"
        "- Do NOT invent or hallucinate data\n"
        "- Do NOT use markdown code blocks\n"
        "- Return ONLY the JSON array, no explanation"
    )

    user_prompt = (
        "Analyze this financial dataset and generate weekly Cash Inflows vs Outflows using actual dates from the data.\n\n"
        "Dataset:\n"
        f"{json.dumps(optimized_payload, default=str)}\n\n"
        "Instructions:\n"
        "1. Scan the metadata to identify date columns and inflow/outflow columns\n"
        "2. Extract actual dates from the data\n"
        "3. Group transactions by week based on these dates\n"
        "4. Sum inflows and outflows for each week\n"
        "5. Return ONLY the JSON array (4 weeks maximum) with actual dates from the data\n"
        "6. Use format: {week, date (YYYY-MM-DD), inflows, outflows}"
    )

    payload = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=45)
        response.raise_for_status()
        data = response.json()
        
        if "choices" not in data or not data["choices"]:
            print(f"LLM Error (flow): No choices in response: {data}")
            return []
        
        content = data["choices"][0]["message"]["content"].strip()
        
        if not content:
            print(f"LLM Error (flow): Empty content in response")
            return []
        
        # Clean markdown formatting if present
        cleaned_content = _extract_json_from_response(content)
        parsed = json.loads(cleaned_content)
        
        # Validate the response structure
        if isinstance(parsed, list):
            validated_points = []
            for point in parsed[:4]:  # Limit to 4 weeks
                if isinstance(point, dict):
                    validated_points.append({
                        "week": str(point.get("week", "")),
                        "date": str(point.get("date", "")),
                        "inflows": float(point.get("inflows", 0)),
                        "outflows": float(point.get("outflows", 0))
                    })
            return validated_points
        return []
    except json.JSONDecodeError as e:
        print(f"LLM Error (flow): JSON parsing failed: {e}. Content: {content if 'content' in locals() else 'N/A'}")
        return []
    except Exception as e:
        print(f"LLM Error (flow): {e}")
        print(f"Response status: {response.status_code if 'response' in locals() else 'N/A'}")
        print(f"Response text: {response.text if 'response' in locals() else 'N/A'}")
        return []


def _optimize_payload_for_llm(payload_data: dict, query: str, max_tokens: int = 6000) -> dict:
    """
    Intelligently reduce payload size for LLM to avoid token limit errors.
    
    Strategy:
    1. Sample data intelligently based on query context
    2. Provide comprehensive statistics for numeric columns
    3. Include diverse representative samples
    4. Maintain data structure for proper analysis
    
    Returns optimized payload with same structure but reduced data.
    """
    if not payload_data or "documents" not in payload_data:
        return payload_data
    
    optimized = {"documents": []}
    query_lower = query.lower()
    
    for doc in payload_data.get("documents", []):
        optimized_doc = {
            "id": doc.get("id"),
            "filename": doc.get("filename"),
            "row_count": doc.get("row_count"),
            "column_count": doc.get("column_count"),
            "upload_date": doc.get("upload_date"),
        }
        
        full_data = doc.get("full_data", [])
        
        # If data is large, implement intelligent sampling
        if len(full_data) > 200:
            print(f"Optimizing payload: {len(full_data)} rows detected, sampling intelligently...")
            
            # Strategy 1: Identify relevant rows based on query keywords
            relevant_rows = []
            use_all_for_stats = True
            
            # Detect what type of data user is asking about
            if any(keyword in query_lower for keyword in ["overdue", "late", "at risk", "payment status", "pending", "unpaid"]):
                # Filter for overdue/at-risk items
                relevant_rows = [
                    row for row in full_data 
                    if isinstance(row, dict) and (
                        "overdue" in str(row).lower() or 
                        "late" in str(row).lower() or
                        "pending" in str(row).lower() or
                        "unpaid" in str(row).lower()
                    )
                ][:100]  # Limit to 100 relevant rows
            
            if any(keyword in query_lower for keyword in ["highest", "largest", "biggest", "top", "maximum", "most"]):
                # Sort and take top items
                try:
                    # Try to find numeric columns and sort by them
                    numeric_rows = []
                    for row in full_data:
                        if isinstance(row, dict):
                            for key, val in row.items():
                                try:
                                    if isinstance(val, (int, float)) and val > 0:
                                        numeric_rows.append((float(val), row))
                                        break
                                except:
                                    pass
                    if numeric_rows:
                        numeric_rows.sort(reverse=True, key=lambda x: x[0])
                        relevant_rows = [row for _, row in numeric_rows[:50]]
                except:
                    pass
            
            # If we found relevant rows, combine with samples; otherwise just sample
            if relevant_rows:
                # Use relevant rows plus some diverse samples
                sample_size = min(50, len(full_data) // 20)
                sampled_indices = set()
                
                # Add evenly spaced samples for diversity
                step = max(1, len(full_data) // sample_size)
                for i in range(0, len(full_data), step):
                    sampled_indices.add(i)
                
                diverse_samples = [full_data[i] for i in sorted(sampled_indices)]
                sampled_data = relevant_rows + diverse_samples
                print(f"Using {len(relevant_rows)} relevant rows + {len(diverse_samples)} diverse samples")
            else:
                # Strategy 2: Intelligent sampling - take larger sample for better analysis
                sample_size = min(150, max(50, len(full_data) // 10))  # Increased sample size
                
                # Always include first and last rows (shows data range)
                sampled_indices = {0, len(full_data) - 1}
                
                # Add evenly spaced samples across entire dataset
                step = max(1, len(full_data) // sample_size)
                for i in range(0, len(full_data), step):
                    sampled_indices.add(i)
                
                # Add random samples for diversity
                import random
                random.seed(42)  # Consistent sampling
                while len(sampled_indices) < sample_size:
                    sampled_indices.add(random.randint(0, len(full_data) - 1))
                
                sampled_data = [full_data[i] for i in sorted(sampled_indices)]
                print(f"Sampled {len(sampled_data)} rows from {len(full_data)} total rows")
            
            # Strategy 3: Add comprehensive summary statistics
            summary = {
                "_dataset_info": {
                    "total_rows": len(full_data),
                    "sampled_rows": len(sampled_data),
                    "sampling_note": f"Showing {len(sampled_data)} representative rows from {len(full_data)} total. Statistics calculated from all {len(full_data)} rows."
                }
            }
            
            # Calculate comprehensive statistics for all numeric columns
            if full_data and isinstance(full_data[0], dict):
                numeric_stats = {}
                for key in full_data[0].keys():
                    values = []
                    for row in full_data:
                        try:
                            val = float(row.get(key, 0))
                            if val != 0:  # Only count non-zero values for meaningful stats
                                values.append(val)
                        except:
                            pass
                    
                    if values:
                        numeric_stats[key] = {
                            "min": min(values),
                            "max": max(values),
                            "avg": round(sum(values) / len(values), 2),
                            "sum": round(sum(values), 2),
                            "count": len(values)
                        }
                
                if numeric_stats:
                    summary["_column_statistics"] = numeric_stats
                
                # Also add categorical column value distributions for better context
                categorical_stats = {}
                for key in full_data[0].keys():
                    if key not in numeric_stats:  # Only for non-numeric columns
                        value_counts = {}
                        for row in full_data:
                            val = str(row.get(key, ""))
                            if val and val != "0" and val != "nan":
                                value_counts[val] = value_counts.get(val, 0) + 1
                        
                        if value_counts:
                            # Get top 10 most common values
                            top_values = sorted(value_counts.items(), key=lambda x: x[1], reverse=True)[:10]
                            categorical_stats[key] = {
                                "unique_values": len(value_counts),
                                "top_values": [{"value": v, "count": c} for v, c in top_values]
                            }
                
                if categorical_stats:
                    summary["_categorical_distributions"] = categorical_stats
            
            optimized_doc["full_data"] = sampled_data
            optimized_doc["_data_summary"] = summary
        else:
            # Small dataset (<=200 rows), include as is
            optimized_doc["full_data"] = full_data
            print(f"Including all {len(full_data)} rows (small dataset)")
        
        optimized["documents"].append(optimized_doc)
    
    return optimized


def answer_user_query(query: str, payload_data: dict) -> str:
    """
    Answer user queries about their uploaded data and financial information.
    Uses the provided dataset to answer questions contextually.
    Automatically optimizes context if data is large to avoid token limit errors.
    """
    if not settings.OPENROUTER_API_KEY:
        return "AI assistant is not configured. Please add your OpenRouter API key."

    url = f"{settings.LLM_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    # Optimize payload to avoid token limit errors
    optimized_payload = _optimize_payload_for_llm(payload_data, query)

    system_prompt = (
        "You are a helpful financial assistant. Answer user questions about their cash flow, "
        "invoices, payment history, and financial data. Use the provided dataset to give accurate answers.\n\n"
        "IMPORTANT CONTEXT INTERPRETATION:\n"
        "1. When you see '_data_summary', it contains comprehensive statistics from the ENTIRE dataset\n"
        "2. '_column_statistics' shows min/max/avg/sum/count for ALL numeric columns across all rows\n"
        "3. '_categorical_distributions' shows value frequencies for ALL categorical columns\n"
        "4. 'full_data' contains representative sample rows for context and patterns\n"
        "5. The 'total_rows' field tells you the actual size of the complete dataset\n\n"
        "HOW TO ANSWER:\n"
        "- Use the statistics to answer aggregate questions (totals, averages, counts, etc.)\n"
        "- Use the sample data to understand patterns, structure, and specific examples\n"
        "- Combine both to provide accurate, comprehensive answers\n"
        "- Always reference the actual data - be specific with numbers from the statistics\n"
        "- If asked about totals or sums, use the '_column_statistics' sum values\n"
        "- If asked about patterns or specific records, reference the sample data\n\n"
        "Be concise, clear, and provide actionable insights. Do not make assumptions beyond the provided data."
    )

    user_prompt = (
        f"User Query: {query}\n\n"
        f"Here is the financial data available:\n"
        f"{json.dumps(optimized_payload, indent=2, default=str)}"
    )

    payload = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.7,
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=45)
        response.raise_for_status()
        data = response.json()
        
        if "choices" not in data or not data["choices"]:
            print(f"LLM Error (query): No choices in response: {data}")
            return "Sorry, I encountered an error processing your question. Please try again later."
        
        content = data["choices"][0]["message"]["content"].strip()
        
        if not content:
            print(f"LLM Error (query): Empty content in response")
            return "Sorry, I encountered an error processing your question. Please try again later."
        
        return content
    except Exception as e:
        print(f"LLM Error (query): {e}")
        print(f"Response status: {response.status_code if 'response' in locals() else 'N/A'}")
        print(f"Response text: {response.text if 'response' in locals() else 'N/A'}")
        return "Sorry, I encountered an error processing your question. Please try again later."


def get_scenario_analysis_from_openrouter(payload_data: dict) -> list:
    """
    Generate scenario analysis with optimistic, expected, and pessimistic forecasts
    based on uploaded financial data.
    
    Returns a list of data points with format:
    [
        {"week": "Week 1", "optimistic": 1150000, "expected": 1000000, "pessimistic": 850000},
        ...
    ]
    """
    if not settings.OPENROUTER_API_KEY:
        return []

    url = f"{settings.LLM_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    # Optimize payload to avoid token limit errors
    optimized_payload = _optimize_payload_for_llm(payload_data, "scenario analysis forecast optimistic pessimistic")

    system_prompt = (
        "You are a financial forecasting expert. Your ONLY job is to return valid JSON. "
        "Do NOT explain, do NOT use markdown, do NOT include code blocks. "
        "ONLY return a JSON array and nothing else.\n\n"
        "Analyze the provided financial data and generate scenario analysis with:\n"
        "- Optimistic scenario: Best case forecast (15% higher than expected)\n"
        "- Expected scenario: Most likely forecast based on historical trends\n"
        "- Pessimistic scenario: Worst case forecast (15% lower than expected)\n\n"
        "Generate 8 data points representing weekly forecasts.\n"
        "Each data point must include:\n"
        "  - week: String label (e.g., 'Week 1', 'Week 2', or actual date if determinable)\n"
        "  - optimistic: Number representing optimistic cash position\n"
        "  - expected: Number representing expected cash position\n"
        "  - pessimistic: Number representing pessimistic cash position\n\n"
        "Base your forecasts on:\n"
        "1. Historical cash flow patterns from the data\n"
        "2. Revenue trends and seasonality\n"
        "3. Expense patterns and upcoming obligations\n"
        "4. Current cash position as starting point\n\n"
        "Return ONLY a JSON array. Do NOT hallucinate data. Base calculations on actual provided data."
    )

    user_prompt = (
        "Analyze this financial data and return a JSON array with 8 scenario forecast points:\n\n"
        f"{json.dumps(optimized_payload, default=str)}\n\n"
        "Return ONLY this JSON array structure, no markdown, no code blocks, no explanation:\n"
        "[\n"
        '  {"week": "Week 1", "optimistic": <number>, "expected": <number>, "pessimistic": <number>},\n'
        '  {"week": "Week 2", "optimistic": <number>, "expected": <number>, "pessimistic": <number>},\n'
        "  ...\n"
        "]"
    )

    payload = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=45)
        response.raise_for_status()
        data = response.json()
        
        if "choices" not in data or not data["choices"]:
            print(f"LLM Error (scenario): No choices in response: {data}")
            raise ValueError("Empty choices in LLM response")
        
        content = data["choices"][0]["message"]["content"].strip()
        
        if not content:
            print(f"LLM Error (scenario): Empty content in response")
            raise ValueError("Empty message content from LLM")
        
        # Clean and extract JSON from various formats
        cleaned_content = _extract_json_from_response(content)
        parsed = json.loads(cleaned_content)
        
        # Validate structure
        if not isinstance(parsed, list):
            print(f"LLM Error (scenario): Response is not an array: {type(parsed)}")
            return []
        
        # Ensure each point has required fields
        validated_points = []
        for i, point in enumerate(parsed[:8]):  # Limit to 8 points
            if isinstance(point, dict):
                validated_points.append({
                    "week": point.get("week", f"Week {i+1}"),
                    "optimistic": float(point.get("optimistic", 0)),
                    "expected": float(point.get("expected", 0)),
                    "pessimistic": float(point.get("pessimistic", 0)),
                })
        
        return validated_points
    except json.JSONDecodeError as e:
        print(f"LLM Error (scenario): JSON parsing failed: {e}")
        print(f"Raw content: {content if 'content' in locals() else 'N/A'}")
        return []
    except Exception as e:
        print(f"LLM Error (scenario): {e}")
        print(f"Response status: {response.status_code if 'response' in locals() else 'N/A'}")
        print(f"Response text: {response.text if 'response' in locals() else 'N/A'}")
        return []


def extract_invoices_from_data(payload_data: dict) -> list:
    """
    Extract and analyze invoice data from uploaded CSV files.
    Identifies invoice records and calculates risk scores.
    
    Returns a list of invoice objects with format:
    [{
        "id": "invoice_id",
        "customer": "customer_name",
        "amount": 1000.50,
        "dueDate": "2026-02-15",
        "status": "Pending|Overdue|Paid",
        "riskScore": 0-100,
        "aiPrediction": "Risk assessment text"
    }]
    """
    if not settings.OPENROUTER_API_KEY:
        return []

    url = f"{settings.LLM_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    # Optimize payload to avoid token limit errors
    optimized_payload = _optimize_payload_for_llm(payload_data, "invoice extraction overdue at risk")

    system_prompt = (
        "You are a financial data extraction expert. Your ONLY job is to return valid JSON. "
        "Do NOT explain, do NOT use markdown, do NOT include code blocks. "
        "ONLY return a JSON array and nothing else.\n\n"
        "Analyze the provided data to extract invoice records:\n"
        "1. Identify all columns related to invoices (invoice_id, customer_name, amount, due_date, date, status, etc.)\n"
        "2. Extract all invoice rows from the data\n"
        "3. Determine invoice status based on available data:\n"
        "   - 'Paid' if status contains 'paid' or 'complete' or marked as completed\n"
        "   - 'Overdue' if current date > due_date AND status is not 'Paid'\n"
        "   - 'Pending' otherwise\n"
        "4. Calculate risk score (0-100) based on:\n"
        "   - Days past due (if overdue)\n"
        "   - Invoice amount relative to typical amounts\n"
        "   - Status and payment history patterns\n"
        "5. Generate AI prediction text describing the risk level and reason\n\n"
        "Return ONLY a JSON array. Do NOT hallucinate data. Use ONLY information present in the provided data.\n"
        "Return empty array [] if no invoice data is found."
    )

    user_prompt = (
        "Extract and analyze all invoice data from this uploaded dataset:\n\n"
        f"{json.dumps(optimized_payload, default=str)}\n\n"
        "Return ONLY a JSON array, no markdown, no code blocks, no explanation:\n"
        "[\n"
        '  {\n'
        '    "id": "invoice_id_value",\n'
        '    "customer": "customer_name",\n'
        '    "amount": 1000.50,\n'
        '    "dueDate": "2026-02-15",\n'
        '    "status": "Pending|Overdue|Paid",\n'
        '    "riskScore": 50,\n'
        '    "aiPrediction": "Risk assessment text"\n'
        '  },\n'
        "  ...\n"
        "]"
    )

    payload = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        if "choices" not in data or not data["choices"]:
            print(f"LLM Error (invoices): No choices in response: {data}")
            raise ValueError("Empty choices in LLM response")
        
        content = data["choices"][0]["message"]["content"].strip()
        
        if not content:
            print(f"LLM Error (invoices): Empty content in response")
            raise ValueError("Empty message content from LLM")
        
        # Clean and extract JSON
        cleaned_content = _extract_json_from_response(content)
        parsed = json.loads(cleaned_content)
        
        # Validate structure
        if not isinstance(parsed, list):
            print(f"LLM Error (invoices): Response is not an array: {type(parsed)}")
            return []
        
        # Validate and normalize each invoice
        validated_invoices = []
        for inv in parsed:
            if isinstance(inv, dict) and "id" in inv and "customer" in inv:
                validated_invoices.append({
                    "id": str(inv.get("id", "")),
                    "customer": str(inv.get("customer", "")),
                    "amount": float(inv.get("amount", 0)),
                    "dueDate": str(inv.get("dueDate", "")),
                    "status": str(inv.get("status", "Pending")),
                    "riskScore": int(inv.get("riskScore", 0)),
                    "aiPrediction": str(inv.get("aiPrediction", ""))
                })
        
        return validated_invoices
    except json.JSONDecodeError as e:
        print(f"LLM Error (invoices): JSON parsing failed: {e}")
        print(f"Raw content: {content if 'content' in locals() else 'N/A'}")
        return []
    except Exception as e:
        print(f"LLM Error (invoices): {e}")
        print(f"Response status: {response.status_code if 'response' in locals() else 'N/A'}")
        print(f"Response text: {response.text if 'response' in locals() else 'N/A'}")
        return []


def get_dynamic_cash_flow_from_openrouter(payload_data: dict, current_balance: float = 0) -> list:
    """
    Generate dynamic cash flow forecast data based on uploaded CSV data.
    Analyzes ONLY the provided data to project future inflows and outflows.
    Calculates running closing balance from current position.
    
    Returns a list of weekly forecast points with format:
    [{
        "week": "Week 1",
        "date": "2026-02-15",
        "projectedInflows": 50000.00,
        "projectedOutflows": 30000.00,
        "closingBalance": 20000.00
    }]
    """
    if not settings.OPENROUTER_API_KEY:
        return []

    url = f"{settings.LLM_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    # Optimize payload to avoid token limit errors
    optimized_payload = _optimize_payload_for_llm(payload_data, "dynamic cash flow forecast inflows outflows")

    system_prompt = (
        "You are a financial analyst. Your ONLY job is to return valid JSON based STRICTLY on the provided data. "
        "Do NOT explain, do NOT use markdown, do NOT include code blocks. "
        "Do NOT hallucinate, invent, or assume ANY data not explicitly provided. "
        "ONLY return a JSON array and nothing else.\n\n"
        "CRITICAL RULES:\n"
        "1. Analyze ONLY the columns and data provided in the dataset\n"
        "2. Do NOT estimate or calculate values not derivable from the data\n"
        "3. If data contains inflow/outflow columns, use their actual values or aggregated amounts\n"
        "4. If no clear inflow/outflow data exists, return empty array []\n"
        "5. Generate 4 weeks maximum\n"
        "6. Base all projections on actual data patterns observed, NOT assumptions\n\n"
        "Data Analysis Process:\n"
        "- Identify which columns represent inflows (income, revenue, deposits, etc.)\n"
        "- Identify which columns represent outflows (expenses, payments, withdrawals, etc.)\n"
        "- Calculate per-period amounts from the ACTUAL data provided\n"
        "- Detect if there are trends in the data and project based on those trends ONLY\n"
        "- Use the provided current balance to calculate closing balances"
    )

    user_prompt = (
        "Analyze ONLY this financial dataset and generate 4 weeks of cash flow projections.\n"
        "Current starting balance: ${}\n\n"
        "Dataset:\n{}\n\n"
        "INSTRUCTIONS:\n"
        "1. Examine the data for inflow and outflow amounts\n"
        "2. Base projections ONLY on patterns found in the provided data\n"
        "3. Return weekly projections with running closing balance\n"
        "4. Do NOT add, estimate, or assume any values not in the data\n"
        "5. If insufficient data to project reliably, return empty array []\n\n"
        "Return ONLY this JSON array structure, no markdown, no explanations:\n"
        "[\n"
        '  {{\n'
        '    "week": "Week 1",\n'
        '    "date": "2026-02-15",\n'
        '    "projectedInflows": <number_from_data>,\n'
        '    "projectedOutflows": <number_from_data>,\n'
        '    "closingBalance": <calculated_balance>\n'
        '  }},\n'
        "  ...\n"
        "]"
    ).format(current_balance, json.dumps(optimized_payload, default=str))

    payload = {
        "model": settings.LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        if "choices" not in data or not data["choices"]:
            print(f"LLM Error (cash_flow): No choices in response: {data}")
            raise ValueError("Empty choices in LLM response")
        
        content = data["choices"][0]["message"]["content"].strip()
        
        if not content:
            print(f"LLM Error (cash_flow): Empty content in response")
            raise ValueError("Empty message content from LLM")
        
        # Clean and extract JSON
        cleaned_content = _extract_json_from_response(content)
        parsed = json.loads(cleaned_content)
        
        # Validate structure
        if not isinstance(parsed, list):
            print(f"LLM Error (cash_flow): Response is not an array: {type(parsed)}")
            return []
        
        # Validate and normalize each forecast point
        validated_points = []
        running_balance = current_balance
        for point in parsed[:4]:  # Limit to 4 weeks
            if isinstance(point, dict):
                inflows = float(point.get("projectedInflows", 0))
                outflows = float(point.get("projectedOutflows", 0))
                running_balance += (inflows - outflows)
                
                validated_points.append({
                    "week": str(point.get("week", "")),
                    "date": str(point.get("date", "")),
                    "projectedInflows": inflows,
                    "projectedOutflows": outflows,
                    "closingBalance": running_balance
                })
        
        return validated_points
    except json.JSONDecodeError as e:
        print(f"LLM Error (cash_flow): JSON parsing failed: {e}")
        print(f"Raw content: {content if 'content' in locals() else 'N/A'}")
        return []
    except Exception as e:
        print(f"LLM Error (cash_flow): {e}")
        print(f"Response status: {response.status_code if 'response' in locals() else 'N/A'}")
        print(f"Response text: {response.text if 'response' in locals() else 'N/A'}")
        return []
