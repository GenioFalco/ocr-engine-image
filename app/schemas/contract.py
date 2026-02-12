from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

class ContractBase(BaseModel):
    name: str
    description: Optional[str] = None
    json_schema: Dict[str, Any] = Field(alias="schema") # JSON Schema

    class Config:
        populate_by_name = True

class ContractCreate(ContractBase):
    pass

class ContractUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    json_schema: Optional[Dict[str, Any]] = Field(default=None, alias="schema")
    is_active: Optional[bool] = None

class ContractRead(ContractBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
