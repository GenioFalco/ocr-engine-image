from pydantic import BaseModel
from typing import Optional, Dict, Any

class DocumentTypeCreate(BaseModel):
    name: str
    description: Optional[str] = None

class ContractCreate(BaseModel):
    document_type_name: str
    json_schema: Dict[str, Any]
    is_default: bool = False

class ModelCreate(BaseModel):
    name: str # display name, e.g. "Qwen 2.5 on OpenRouter"
    provider: str # e.g. "gigachat" or "openrouter"
    model_name: str # actual LLM name string, e.g. "qwen/qwen3-235b-a22b-thinking-2507"
    api_key: str
    temperature: float = 0.1
    max_tokens: int = 8000
