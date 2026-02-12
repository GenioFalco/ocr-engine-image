from sqlalchemy import Column, Integer, String, JSON, DateTime
from sqlalchemy.sql import func

from app.db.base import Base

class Log(Base):
    id = Column(Integer, primary_key=True, index=True)
    level = Column(String, index=True) # INFO, ERROR, WARNING
    module = Column(String, index=True) # e.g., 'orchestrator', 'api'
    message = Column(String)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
