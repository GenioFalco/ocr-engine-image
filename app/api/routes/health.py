from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

class HealthCheck(BaseModel):
    status: str = "ok"

@router.get("/", response_model=HealthCheck)
def health_check():
    return HealthCheck(status="ok")
