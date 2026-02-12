from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.model import ModelCreate, ModelRead, ModelUpdate
from app.services.model_service import ModelService

router = APIRouter()

@router.post("/", response_model=ModelRead, status_code=status.HTTP_201_CREATED)
def create_model(
    model_in: ModelCreate,
    db: Session = Depends(get_db)
):
    model_service = ModelService(db)
    # Check if provider already exists if we want single active per provider?
    # For now allow multiple.
    return model_service.create(model_in)

@router.get("/", response_model=List[ModelRead])
def list_models(
    db: Session = Depends(get_db)
):
    model_service = ModelService(db)
    return model_service.get_all()
