from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.db.base import get_db, SessionLocal
from app.models.models import ProcessingJob, Document, ExtractedResult, JobFeedback
from app.engine.pipeline import OCREngine
from app.config.settings import settings
import uuid
import os
import shutil
from datetime import datetime
from app.services.auth_service import get_current_user, get_current_admin_user
from app.models.models import User
from pydantic import BaseModel
from sqlalchemy import func

class FeedbackCreate(BaseModel):
    job_id: uuid.UUID
    rating: int

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
async def process_sync(
    file: UploadFile = File(...), 
    module: str = "standard",
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    job_id = uuid.uuid4()
    job = ProcessingJob(id=job_id, mode="sync", module=module, status="processing", user_id=current_user.id)
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
    module: str = "standard",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job_id = uuid.uuid4()
    job = ProcessingJob(id=job_id, mode="async", module=module, status="pending", user_id=current_user.id)
    db.add(job)
    db.commit()
    
    file_path = save_upload_file(file, job_id)
    
    # Background task
    background_tasks.add_task(process_job_background, job_id, file_path)
    
    return {"job_id": str(job_id), "status": "pending"}

@router.get("/result/{job_id}")
async def get_result(job_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if job.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to view this job")
        
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
        # Fetch feedback logic
        feedback = db.query(JobFeedback).filter(JobFeedback.job_id == job_id).first()
        rating = feedback.rating if feedback else None
            
        return {"status": job.status, "documents": results, "rating": rating}
        
    return {"status": job.status, "error": job.error_message}

@router.get("/debug/result/{job_id}")
async def debug_result(job_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Debug endpoint — shows raw fields_json and raw_llm_response for a job."""
    documents = db.query(Document).filter(Document.job_id == job_id).all()
    out = []
    for doc in documents:
        extraction = db.query(ExtractedResult).filter(ExtractedResult.document_id == doc.id).first()
        out.append({
            "document_type": doc.document_type,
            "fields_json": extraction.fields_json if extraction else None,
            "raw_llm_response": extraction.raw_llm_response[:2000] if extraction and extraction.raw_llm_response else None,
        })
    return out

from fastapi.responses import FileResponse
from typing import Optional
import jwt

@router.get("/preview/{job_id}")
async def get_preview(
    job_id: uuid.UUID, 
    token: Optional[str] = None,
    db: Session = Depends(get_db)
):
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    current_user = None
    if token:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            username = payload.get("sub")
            if username:
                current_user = db.query(User).filter(User.username == username).first()
        except Exception:
            pass
            
    if not current_user:
        raise HTTPException(status_code=403, detail="Not authenticated")
        
    if job.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to view this file")
        
    upload_dir = os.path.join(settings.UPLOAD_DIR, str(job_id))
    if not os.path.exists(upload_dir):
        raise HTTPException(status_code=404, detail="File directory not found")
        
    all_files = os.listdir(upload_dir)
    if not all_files:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Prefer PDF files; fall back to first file if no PDF found
    pdf_files = [f for f in all_files if f.lower().endswith('.pdf')]
    chosen_file = pdf_files[0] if pdf_files else all_files[0]
        
    file_path = os.path.join(upload_dir, chosen_file)
    return FileResponse(file_path, media_type="application/pdf")

@router.get("/jobs")
async def get_user_jobs(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Fetch all jobs for the currently authenticated user."""
    jobs = db.query(ProcessingJob).filter(ProcessingJob.user_id == current_user.id).order_by(ProcessingJob.created_at.desc()).all()
    return [{"id": j.id, "mode": j.mode, "status": j.status, "created_at": j.created_at, "error_message": j.error_message} for j in jobs]

@router.get("/admin/jobs")
async def get_all_jobs(db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    """Fetch all jobs across all users (Admin only)."""
    jobs = db.query(ProcessingJob).order_by(ProcessingJob.created_at.desc()).all()
    return [{"id": j.id, "user_id": j.user_id, "mode": j.mode, "status": j.status, "created_at": j.created_at, "error_message": j.error_message} for j in jobs]

@router.post("/feedback")
def submit_feedback(data: FeedbackCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    job = db.query(ProcessingJob).filter(ProcessingJob.id == data.job_id).first()
    if not job: raise HTTPException(404, "Job not found")
    if job.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(403, "Not authorized")
        
    feedback = db.query(JobFeedback).filter(JobFeedback.job_id == data.job_id).first()
    if feedback:
        feedback.rating = data.rating
    else:
        feedback = JobFeedback(job_id=data.job_id, user_id=current_user.id, rating=data.rating)
        db.add(feedback)
    db.commit()
    return {"status": "success"}

@router.get("/admin/analytics")
def get_analytics(db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    total_jobs = db.query(ProcessingJob).count()
    failed_jobs = db.query(ProcessingJob).filter(ProcessingJob.status == "failed").count()
    
    avg = db.query(func.avg(JobFeedback.rating)).scalar()
    overall_rating = round(avg, 1) if avg else 0.0
    
    m_stats = db.query(ProcessingJob.module, func.count(ProcessingJob.id), func.avg(JobFeedback.rating))\
        .outerjoin(JobFeedback, ProcessingJob.id == JobFeedback.job_id)\
        .group_by(ProcessingJob.module).all()
        
    module_stats = [{"name": m[0] or "unknown", "count": m[1], "avg_rating": round(m[2], 1) if m[2] else 0.0} for m in m_stats]
    
    dist = db.query(JobFeedback.rating, func.count(JobFeedback.id)).group_by(JobFeedback.rating).all()
    rating_dist = {str(r[0]): r[1] for r in dist}
    
    return {
        "total_jobs": total_jobs,
        "failed_jobs": failed_jobs,
        "overall_rating": overall_rating,
        "module_stats": module_stats,
        "rating_distribution": rating_dist
    }

# --- Management API ---
from app.schemas.admin import DocumentTypeCreate, ContractCreate, ModelCreate
from app.models.models import DocumentType, Contract, Model

@router.get("/admin/users")
def get_all_users(db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    """Fetch all registered users (Admin only)."""
    users = db.query(User).order_by(User.id.desc()).all()
    return [{"id": u.id, "username": u.username, "email": u.email, "role": u.role, "is_active": u.is_active} for u in users]

@router.post("/admin/models")
def add_model(model_data: ModelCreate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
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
def list_models(db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
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
def delete_model(model_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    model = db.query(Model).filter(Model.id == model_id).first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    db.delete(model)
    db.commit()
    return {"status": "deleted", "id": model_id}

@router.post("/admin/models/{model_id}/activate")
def activate_model(model_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
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
def create_document_type(doc_type: DocumentTypeCreate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    existing = db.query(DocumentType).filter(DocumentType.name == doc_type.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Document type already exists")
    
    new_type = DocumentType(name=doc_type.name, description=doc_type.description)
    db.add(new_type)
    db.commit()
    db.refresh(new_type)
    return new_type

@router.delete("/admin/document_types/{doc_type_id}")
def delete_document_type(doc_type_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
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
def create_contract(contract: ContractCreate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
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
def list_contracts(db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
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
def delete_contract(contract_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    db.delete(contract)
    db.commit()
    return {"status": "deleted", "id": contract_id}

@router.post("/admin/init")
def init_defaults(db: Session = Depends(get_db), admin: User = Depends(get_current_admin_user)):
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
