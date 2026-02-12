from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel

class LogRead(BaseModel):
    id: int
    level: str
    module: str
    message: str
    payload: Optional[Dict[str, Any]] = None
    created_at: datetime
    
    class Config:
        from_attributes = True
