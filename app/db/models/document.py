from sqlalchemy import Column, Integer, String, Enum, DateTime, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.db.base import Base

class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Document(Base):
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    file_path = Column(String, nullable=False)
    file_type = Column(String) # e.g. "application/pdf"
    content_hash = Column(String, index=True) # SHA256 for deduplication
    status = Column(Enum(DocumentStatus), default=DocumentStatus.PENDING)
    error_message = Column(String, nullable=True)
    meta = Column(JSON, default={}) # page_count, file_size
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    results = relationship("OCRResult", back_populates="document", cascade="all, delete-orphan")
