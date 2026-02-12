from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, HttpUrl

class ModelBase(BaseModel):
    name: str
    provider: str # gemini, qwen, tesseract
    endpoint_url: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = {}

class ModelCreate(ModelBase):
    api_key: Optional[str] = None

class ModelUpdate(BaseModel):
    name: Optional[str] = None
    endpoint_url: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None
    api_key: Optional[str] = None

class ModelRead(ModelBase):
    id: int
    is_active: bool
    created_at: datetime
    # Exclude API key from read
    
    class Config:
        from_attributes = True
