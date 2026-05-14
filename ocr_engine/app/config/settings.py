from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str
    GIGACHAT_CREDENTIALS: Optional[str] = None
    LLM_PROVIDER: str = "gigachat"
    GIGACHAT_MODEL: str = "GigaChat-Pro"
    LOG_LEVEL: str = "INFO"
    UPLOAD_DIR: str = "uploads"

    # Auth
    SECRET_KEY: str = "secret-key-change-it-in-prod"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30        # токен AD FS / логин — 30 минут
    API_KEY_TOKEN_EXPIRE_MINUTES: int = 30       # токен по API ключу — 30 минут

    # SAML 2.0 (AD FS)
    SAML_ENABLED: bool = False
    SAML_IDP_URL: str = "https://fs.askona.ru/adfs"        # базовый URL AD FS
    SAML_IDP_CERT: str = ""                                 # x509 сертификат IdP (из их метаданных)
    SAML_SP_CERT: str = ""                                  # наш публичный сертификат SP
    SAML_SP_KEY: str = ""                                   # наш приватный ключ SP
    APP_URL: str = "https://ocr.askonalife.com"             # наш внешний URL

    # Frontend URL — куда редиректить после успешного входа через SAML
    FRONTEND_URL: str = "http://localhost:5173"


    class Config:
        env_file = ".env"

settings = Settings()
