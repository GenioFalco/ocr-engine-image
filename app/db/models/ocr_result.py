from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base

class OCRResult(Base):
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("document.id"), nullable=False, index=True)
    page_number = Column(Integer, nullable=True) # None for whole document
    
    model_id = Column(Integer, ForeignKey("modelregistry.id"), nullable=True)
    contract_id = Column(Integer, ForeignKey("contract.id"), nullable=True)
    
    extracted_data = Column(JSON, nullable=True) # The structured fields
    stamps_signatures = Column(JSON, nullable=True) # Coordinates: [{type: stamp, bbox: [x,y,w,h], confidence: 0.9}]
    
    tokens_used = Column(Integer, default=0)
    execution_time_ms = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    document = relationship("Document", back_populates="results")
    model = relationship("ModelRegistry")
    contract = relationship("Contract")
