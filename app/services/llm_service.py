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
        f"{json.dumps(payload_data, default=str)}\n\n"
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
        f"DATASET_JSON:\n{json.dumps(payload_data, default=str)}"
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


def get_cash_flow_from_openrouter(payload_data: dict) -> list:
    if not settings.OPENROUTER_API_KEY:
        return []

    url = f"{settings.LLM_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    system_prompt = (
        "You are a financial analytics engine. Use ONLY the provided data to create a weekly "
        "Cash Inflows vs Outflows series for the last 4 weeks. Do not invent or assume missing "
        "values. If data is insufficient, use 0 for numeric fields. Output must be a JSON array "
        "of exactly 4 objects with keys: week, date, inflows, outflows. The week values must be 'Week 1' "
        "through 'Week 4'. The date field should contain the actual date from the data (format YYYY-MM-DD), "
        "No extra keys, no prose."
    )

    user_prompt = (
        "Generate the Cash Inflows vs Outflows weekly comparison based strictly on the dataset. "
        "Return only the JSON array described above.\n\n"
        f"DATASET_JSON:\n{json.dumps(payload_data, default=str)}"
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
            print(f"LLM Error (flow): No choices in response: {data}")
            return []
        
        content = data["choices"][0]["message"]["content"].strip()
        
        if not content:
            print(f"LLM Error (flow): Empty content in response")
            return []
        
        # Clean markdown formatting if present
        cleaned_content = _clean_llm_json_response(content)
        parsed = json.loads(cleaned_content)
        return parsed if isinstance(parsed, list) else []
    except json.JSONDecodeError as e:
        print(f"LLM Error (flow): JSON parsing failed: {e}. Content: {content if 'content' in locals() else 'N/A'}")
        return []
    except Exception as e:
        print(f"LLM Error (flow): {e}")
        print(f"Response status: {response.status_code if 'response' in locals() else 'N/A'}")
        print(f"Response text: {response.text if 'response' in locals() else 'N/A'}")
        return []


def answer_user_query(query: str, payload_data: dict) -> str:
    """
    Answer user queries about their uploaded data and financial information.
    Uses the provided dataset to answer questions contextually.
    """
    if not settings.OPENROUTER_API_KEY:
        return "AI assistant is not configured. Please add your OpenRouter API key."

    url = f"{settings.LLM_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    system_prompt = (
        "You are a helpful financial assistant. Answer user questions about their cash flow, "
        "invoices, payment history, and financial data. Use ONLY the provided dataset to answer questions. "
        "If the user asks about something not in the data, politely explain that you don't have that information. "
        "Be concise, clear, and provide actionable insights when possible. "
        "Always base your answer on the actual data provided, do not make assumptions or invent data."
    )

    user_prompt = (
        f"User Query: {query}\n\n"
        f"Here is the financial data available:\n"
        f"{json.dumps(payload_data, indent=2, default=str)}"
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
