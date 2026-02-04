import json
import requests
from app.core.config import settings

def get_insights(context_data: str) -> str:
    if not settings.OPENROUTER_API_KEY:
        return "AI implementation pending (No API Key)"
        
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "openai/gpt-3.5-turbo", # or another cheap model
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

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    system_prompt = (
        "You are a financial analytics engine. Use ONLY the provided data to compute the required stats. "
        "Do not infer or fabricate missing values. If a value cannot be computed from the data, return 0. "
        "Return a single JSON object with numeric values for the keys: "
        "current, forecast30Day, atRiskInvoices, cashRunway, currentChangePercent, "
        "forecastChangePercent, overdueInvoicesCount. No extra keys, no prose."
    )

    user_prompt = (
        "Compute the stats from the following dataset. "
        "All analysis must be based strictly on this data.\n\n"
        f"DATASET_JSON:\n{json.dumps(payload_data, default=str)}"
    )

    payload = {
        "model": "openai/gpt-3.5-turbo",
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
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return parsed if isinstance(parsed, dict) else {}
    except Exception as e:
        print(f"LLM Error (stats): {e}")
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

    url = "https://openrouter.ai/api/v1/chat/completions"
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
        "model": "openai/gpt-3.5-turbo",
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
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return parsed if isinstance(parsed, list) else []
    except Exception as e:
        print(f"LLM Error (forecast): {e}")
        return []


def get_cash_flow_from_openrouter(payload_data: dict) -> list:
    if not settings.OPENROUTER_API_KEY:
        return []

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    system_prompt = (
        "You are a financial analytics engine. Use ONLY the provided data to create a weekly "
        "Cash Inflows vs Outflows series for the last 4 weeks. Do not invent or assume missing "
        "values. If data is insufficient, use 0 for numeric fields. Output must be a JSON array "
        "of exactly 4 objects with keys: week, inflows, outflows. The week values must be 'Week 1' "
        "through 'Week 4'. No extra keys, no prose."
    )

    user_prompt = (
        "Generate the Cash Inflows vs Outflows weekly comparison based strictly on the dataset. "
        "Return only the JSON array described above.\n\n"
        f"DATASET_JSON:\n{json.dumps(payload_data, default=str)}"
    )

    payload = {
        "model": "openai/gpt-3.5-turbo",
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
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return parsed if isinstance(parsed, list) else []
    except Exception as e:
        print(f"LLM Error (flow): {e}")
        return []


def answer_user_query(query: str, payload_data: dict) -> str:
    """
    Answer user queries about their uploaded data and financial information.
    Uses the provided dataset to answer questions contextually.
    """
    if not settings.OPENROUTER_API_KEY:
        return "AI assistant is not configured. Please add your OpenRouter API key."

    url = "https://openrouter.ai/api/v1/chat/completions"
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
        "model": "openai/gpt-3.5-turbo",
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
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"LLM Error (query): {e}")
        return "Sorry, I encountered an error processing your question. Please try again later."
