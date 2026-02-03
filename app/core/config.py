from typing import List

from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DB_HOST: str
    DB_PORT: str
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str
    OPENROUTER_API_KEY: str
    allowed_extensions: List[str] = [".csv"]
    max_file_size: int = 200 * 1024 * 1024

    class Config:
        env_file = ".env"

settings = Settings()
