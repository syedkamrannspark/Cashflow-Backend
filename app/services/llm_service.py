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
