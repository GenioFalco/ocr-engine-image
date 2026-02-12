from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models.log import Log
from app.schemas.log import LogRead

router = APIRouter()

@router.get("/", response_model=List[LogRead])
def list_logs(
    level: str = None,
    limit: int = 100,
    skip: int = 0,
    db: Session = Depends(get_db)
):
    query = db.query(Log)
    if level:
        query = query.filter(Log.level == level)
    return query.order_by(Log.created_at.desc()).offset(skip).limit(limit).all()
