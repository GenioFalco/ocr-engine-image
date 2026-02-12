from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.models.model_registry import ModelRegistry
from app.schemas.model import ModelCreate

class ModelService:
    def __init__(self, db: Session):
        self.db = db

    def get_by_provider(self, provider: str, is_active: bool = True) -> Optional[ModelRegistry]:
        """Get the first active model for a provider."""
        return self.db.query(ModelRegistry).filter(
            ModelRegistry.provider == provider, 
            ModelRegistry.is_active == is_active
        ).first()

    def create(self, obj_in: ModelCreate) -> ModelRegistry:
        db_obj = ModelRegistry(
            name=obj_in.name,
            provider=obj_in.provider,
            api_key=obj_in.api_key,
            endpoint_url=obj_in.endpoint_url,
            parameters=obj_in.parameters or {}
        )
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def get_all(self) -> List[ModelRegistry]:
        return self.db.query(ModelRegistry).all()
