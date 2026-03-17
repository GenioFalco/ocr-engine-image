import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer, JSON, Float, Text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base

class DocumentType(Base):
    __tablename__ = "document_types"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Contract(Base):
    __tablename__ = "contracts"
    id = Column(Integer, primary_key=True, index=True)
    document_type_id = Column(Integer, ForeignKey("document_types.id"))
    json_schema = Column(JSON)
    version = Column(Integer, default=1)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    document_type = relationship("DocumentType")

class Model(Base):
    __tablename__ = "models"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    provider = Column(String)
    model_name = Column(String)
    api_key = Column(String) # Should be encrypted in prod
    temperature = Column(Float, default=0.0)
    max_tokens = Column(Integer, default=1000)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mode = Column(String) # sync or async
    status = Column(String, default="pending") # pending, processing, done, failed
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    total_processing_time = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("processing_jobs.id"))
    document_type = Column(String)
    confidence = Column(Float)
    hash = Column(String)
    is_duplicate = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    job = relationship("ProcessingJob")

class ExtractedResult(Base):
    __tablename__ = "extracted_results"
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    fields_json = Column(JSON)
    stamps_json = Column(JSON)
    signatures_json = Column(JSON)
    raw_llm_response = Column(Text)
    validation_status = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    document = relationship("Document")

class PageClassification(Base):
    __tablename__ = "page_classifications"
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("processing_jobs.id"))
    page_number = Column(Integer)
    predicted_type = Column(String)
    confidence = Column(Float)
    
    job = relationship("ProcessingJob")

class Log(Base):
    __tablename__ = "logs"
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(UUID(as_uuid=True), ForeignKey("processing_jobs.id"))
    stage = Column(String)
    message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    job = relationship("ProcessingJob")
