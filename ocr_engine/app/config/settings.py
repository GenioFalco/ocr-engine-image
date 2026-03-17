from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str
    GIGACHAT_CREDENTIALS: Optional[str] = None
    LLM_PROVIDER: str = "gigachat"
    GIGACHAT_MODEL: str = "GigaChat-Pro"
    LOG_LEVEL: str = "INFO"
    UPLOAD_DIR: str = "uploads" # Directory to store uploaded PDFs and images

    class Config:
        env_file = ".env"

settings = Settings()
