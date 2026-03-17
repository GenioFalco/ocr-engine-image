from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db.base import get_db, SessionLocal
from app.models.models import ProcessingJob, Document, ExtractedResult
from app.engine.pipeline import OCREngine
from app.config.settings import settings
import uuid
import os
import shutil
from datetime import datetime

router = APIRouter()

def save_upload_file(upload_file: UploadFile, job_id: uuid.UUID) -> str:
    upload_dir = os.path.join(settings.UPLOAD_DIR, str(job_id))
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, upload_file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    return file_path

def process_job_background(job_id: uuid.UUID, file_path: str):
    db: Session = SessionLocal()
    try:
        engine = OCREngine(job_id=job_id, db=db)
        engine.run(file_path)
    finally:
        db.close()

@router.post("/process")
async def process_sync(file: UploadFile = File(...), db: Session = Depends(get_db)):
    job_id = uuid.uuid4()
    job = ProcessingJob(id=job_id, mode="sync", status="processing")
    db.add(job)
    db.commit()

    try:
        file_path = save_upload_file(file, job_id)
        # For sync processing, we can use the request session if we are careful, 
        # but OCREngine might take a while. 
        # OCREngine uses internal commits, so it should be fine.
        engine = OCREngine(job_id=job_id, db=db)
        engine.run(file_path)
        
        # Reload job to get status
        db.refresh(job)
        
        if job.status == "failed":
            raise HTTPException(status_code=500, detail=job.error_message)

        # Fetch results
        documents = db.query(Document).filter(Document.job_id == job_id).all()
        results = []
        for doc in documents:
            extraction = db.query(ExtractedResult).filter(ExtractedResult.document_id == doc.id).first()
            results.append({
                "document_type": doc.document_type,
                "confidence": doc.confidence,
                "fields": extraction.fields_json if extraction else {},
                "stamps": extraction.stamps_json if extraction else [],
                "signatures": extraction.signatures_json if extraction else []
            })
            
        return {"status": "success", "job_id": str(job_id), "documents": results}

    except Exception as e:
        job.status = "failed"
        job.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process_async")
async def process_async(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    job_id = uuid.uuid4()
    job = ProcessingJob(id=job_id, mode="async", status="pending")
    db.add(job)
    db.commit()
    
    file_path = save_upload_file(file, job_id)
    
    # Background task
    background_tasks.add_task(process_job_background, job_id, file_path)
    
    return {"job_id": str(job_id), "status": "pending"}

@router.get("/result/{job_id}")
async def get_result(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if job.status == "done":
         # Fetch results similar to sync
        documents = db.query(Document).filter(Document.job_id == job_id).all()
        results = []
        for doc in documents:
            extraction = db.query(ExtractedResult).filter(ExtractedResult.document_id == doc.id).first()
            results.append({
                "document_type": doc.document_type,
                "confidence": doc.confidence,
                "fields": extraction.fields_json if extraction else {},
            })
        return {"status": job.status, "documents": results}
        
    return {"status": job.status, "error": job.error_message}

# --- Management API ---
from app.schemas.admin import DocumentTypeCreate, ContractCreate, ModelCreate
from app.models.models import DocumentType, Contract, Model

@router.post("/admin/models")
def add_model(model_data: ModelCreate, db: Session = Depends(get_db)):
    existing = db.query(Model).filter(Model.name == model_data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Model name already exists")
    
    provider_lower = model_data.provider.lower()
    if provider_lower not in ["gigachat", "openrouter", "qwen"]:
        raise HTTPException(status_code=400, detail="Invalid provider. Must be 'gigachat', 'openrouter', or 'qwen'.")
    
    new_model = Model(
        name=model_data.name,
        provider=provider_lower,
        model_name=model_data.model_name,
        api_key=model_data.api_key,
        temperature=model_data.temperature,
        max_tokens=model_data.max_tokens,
        is_active=False # default to inactive
    )
    db.add(new_model)
    db.commit()
    db.refresh(new_model)
    return {"status": "created", "id": new_model.id, "name": new_model.name}

@router.get("/admin/models")
def list_models(db: Session = Depends(get_db)):
    models = db.query(Model).all()
    return [{
        "id": m.id,
        "name": m.name,
        "provider": m.provider,
        "model_name": m.model_name,
        "api_key": "***" + m.api_key[-4:] if m.api_key else None,
        "is_active": m.is_active
    } for m in models]

@router.delete("/admin/models/{model_id}")
def delete_model(model_id: int, db: Session = Depends(get_db)):
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    db.delete(model)
    db.commit()
    return {"status": "deleted", "id": model_id}

@router.post("/admin/models/{model_id}/activate")
def activate_model(model_id: int, db: Session = Depends(get_db)):
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
        
    # Deactivate all others
    db.query(Model).update({Model.is_active: False})
    
    # Activate target
    model.is_active = True
    db.commit()
    return {"status": "success", "active_model": model.name}

@router.post("/admin/document_types")
def create_document_type(doc_type: DocumentTypeCreate, db: Session = Depends(get_db)):
    existing = db.query(DocumentType).filter(DocumentType.name == doc_type.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Document type already exists")
    
    new_type = DocumentType(name=doc_type.name, description=doc_type.description)
    db.add(new_type)
    db.commit()
    db.refresh(new_type)
    return new_type

@router.delete("/admin/document_types/{doc_type_id}")
def delete_document_type(doc_type_id: int, db: Session = Depends(get_db)):
    doc_type = db.query(DocumentType).filter(DocumentType.id == doc_type_id).first()
    if not doc_type:
        raise HTTPException(status_code=404, detail="Document type not found")
    
    try:
        db.delete(doc_type)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Cannot delete document type because it has associated contracts. Delete the contracts first.")
    
    return {"status": "deleted", "id": doc_type_id}

@router.get("/admin/document_types")
def list_document_types(db: Session = Depends(get_db)):
    doc_types = db.query(DocumentType).all()
    return [{"id": dt.id, "name": dt.name, "description": dt.description, "is_active": dt.is_active} for dt in doc_types]

@router.post("/admin/contracts")
def create_contract(contract: ContractCreate, db: Session = Depends(get_db)):
    doc_type = db.query(DocumentType).filter(DocumentType.name == contract.document_type_name).first()
    if not doc_type:
        raise HTTPException(status_code=404, detail="Document type not found")
        
    new_contract = Contract(
        document_type_id=doc_type.id,
        json_schema=contract.json_schema,
        is_default=contract.is_default
    )
    db.add(new_contract)
    db.commit()
    return {"status": "created", "id": new_contract.id}

@router.get("/admin/contracts")
def list_contracts(db: Session = Depends(get_db)):
    contracts = db.query(Contract).all()
    result = []
    for c in contracts:
        doc_type = db.query(DocumentType).filter(DocumentType.id == c.document_type_id).first()
        result.append({
            "id": c.id,
            "document_type": doc_type.name if doc_type else "unknown",
            "schema": c.json_schema
        })
    return result

@router.delete("/admin/contracts/{contract_id}")
def delete_contract(contract_id: int, db: Session = Depends(get_db)):
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    db.delete(contract)
    db.commit()
    return {"status": "deleted", "id": contract_id}

@router.post("/admin/init")
def init_defaults(db: Session = Depends(get_db)):
    defaults = ["Invoice", "Act", "UPD", "Contract"]
    created = []
    for name in defaults:
        existing = db.query(DocumentType).filter(DocumentType.name == name).first()
        if not existing:
            dt = DocumentType(name=name, description=f"Default type for {name}")
            db.add(dt)
            created.append(name)
    db.commit()
    return {"status": "initialized", "created": created}
