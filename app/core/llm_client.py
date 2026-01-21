from openai import OpenAI
import os
from dotenv import load_dotenv
import httpx

load_dotenv()

class LLMClient:
    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable not set")
        
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=self.api_key,
            http_client=httpx.Client(),
        )
        # Using a reliable model, e.g., handling generic requests
        self.model = "meta-llama/llama-3.1-8b-instruct" 

    def generate(self, prompt: str, system_message: str = "You are a helpful assistant.") -> str:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt},
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error calling LLM: {e}")
            return f"Error generation response: {str(e)}"
