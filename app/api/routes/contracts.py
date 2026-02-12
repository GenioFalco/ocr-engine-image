from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.contract import ContractCreate, ContractRead, ContractUpdate
from app.services.contract_service import ContractService

router = APIRouter()

@router.post("/", response_model=ContractRead, status_code=status.HTTP_201_CREATED)
def create_contract(
    contract_in: ContractCreate,
    db: Session = Depends(get_db)
):
    contract_service = ContractService(db)
    try:
        # Check if duplicate name exists?
        existing = contract_service.get_by_name(contract_in.name)
        if existing:
            raise HTTPException(status_code=400, detail="Contract with this name already exists")
        
        return contract_service.create(contract_in)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@router.get("/", response_model=List[ContractRead])
def list_contracts(
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    contract_service = ContractService(db)
    if active_only:
        return contract_service.get_all_active()
    # TODO: Implement get_all with inactive
    return contract_service.get_all_active() 
