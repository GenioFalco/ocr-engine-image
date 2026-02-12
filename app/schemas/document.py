from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, root_validator

class DocumentBase(BaseModel):
    filename: Optional[str] = None
    file_type: Optional[str] = None

class DocumentCreate(DocumentBase):
    file_path: str
    content_hash: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

class DocumentUpdate(BaseModel):
    status: Optional[str] = None
    error_message: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

class DocumentRead(DocumentBase):
    id: int
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class OCRResultBase(BaseModel):
    page_number: Optional[int] = None
    extracted_data: Optional[Dict[str, Any]] = None
    stamps_signatures: Optional[List[Dict[str, Any]]] = None
    
class OCRResultRead(OCRResultBase):
    id: int
    execution_time_ms: Optional[int] = None
    tokens_used: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True

class DocumentWithResults(DocumentRead):
    results: List[OCRResultRead] = []
