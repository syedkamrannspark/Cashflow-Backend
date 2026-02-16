from typing import List

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DB_HOST: str
    DB_PORT: str
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str
    OPENROUTER_API_KEY: str
    
    # LLM Configuration
    LLM_BASE_URL: str = "https://api.groq.com/openai/v1"
    # LLM_BASE_URL: str = "https://openrouter.ai/api/v1"
    # LLM_MODEL: str = "openai/gpt-oss-20b"
    LLM_MODEL: str = "llama-3.3-70b-versatile"
    # LLM_MODEL: str = "meta-llama/llama-3.1-8b-instruct"
    
    allowed_extensions: List[str] = [".csv", ".xlsx", ".xls"]
    max_file_size: int = 200 * 1024 * 1024

    class Config:
        env_file = ".env"

settings = Settings()
