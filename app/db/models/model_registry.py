from sqlalchemy import Column, Integer, String, Boolean, JSON, DateTime
from sqlalchemy.sql import func

from app.db.base import Base

class ModelRegistry(Base):
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    provider = Column(String, nullable=False) # e.g., 'gemini', 'openai'
    api_key = Column(String, nullable=True) # Encrypted or obfuscated in production
    endpoint_url = Column(String, nullable=True) # For self-hosted models
    parameters = Column(JSON, default={}) # Default parameters: temp, top_k...
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
