from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.models.contract import Contract
from app.schemas.contract import ContractCreate, ContractUpdate

class ContractService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, obj_in: ContractCreate) -> Contract:
        db_obj = Contract(
            name=obj_in.name,
            description=obj_in.description,
            schema=obj_in.schema,
            is_active=True
        )
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def get_by_name(self, name: str) -> Optional[Contract]:
        return self.db.query(Contract).filter(Contract.name == name).first()
    
    def get_all_active(self) -> List[Contract]:
        return self.db.query(Contract).filter(Contract.is_active == True).all()
