import secrets
from typing import Any, Dict, List, Optional, Union

from pydantic import AnyHttpUrl, PostgresDsn, validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Industrial OCR Engine"
    API_V1_STR: str = "/api/v1"
    
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "ocr_user"
    POSTGRES_PASSWORD: str = "ocr_password"
    POSTGRES_DB: str = "ocr_db"

    # GigaChat
    GIGACHAT_CREDENTIALS: Optional[str] = None
    
    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    # Assemble Database URL
    DATABASE_URL: Optional[Union[PostgresDsn, str]] = None

    @validator("DATABASE_URL", pre=True)
    def assemble_db_connection(cls, v: Optional[str], values: Dict[str, Any]) -> Any:
        if isinstance(v, str):
            return v
        
        # If no DATABASE_URL provided, try to build Postgres DSN
        if values.get("POSTGRES_SERVER") and values.get("POSTGRES_DB"):
            return PostgresDsn.build(
                scheme="postgresql",
                username=values.get("POSTGRES_USER"),
                password=values.get("POSTGRES_PASSWORD"),
                host=values.get("POSTGRES_SERVER"),
                path=f"{values.get('POSTGRES_DB') or ''}",
            )
        
        # Fallback to SQLite if no Postgres config
        return "sqlite:///./sql_app.db"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

settings = Settings()
