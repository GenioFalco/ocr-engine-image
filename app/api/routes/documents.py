from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.document import DocumentCreate, DocumentRead, DocumentWithResults
from app.services.document_service import DocumentService
from app.services.orchestrator import Orchestrator
from app.utils.file_storage import save_uploaded_file

router = APIRouter()

@router.post("/upload", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a PDF or image for OCR processing.
    """
    # 1. Save file
    content = await file.read()
    file_path = save_uploaded_file(content, file.filename)
    
    # 2. Create DB entry
    doc_service = DocumentService(db)
    doc_in = DocumentCreate(
        filename=file.filename,
        file_path=file_path,
        file_type=file.content_type,
        meta={"size": len(content)}
    )
    document = doc_service.create(doc_in)
    
    # 3. Trigger Orchestrator in background
    # We must instantiate Orchestrator with a new session scope for background task?
    # Actually, BackgroundTasks runs after response, so the current session might be closed.
    # It's better to let Orchestrator manage its session or rely on a new dependency.
    # However, Dependency Injection usually scopes to request.
    # For simplicity, we'll pass the ID and let a worker handle it, but here we can use a wrapper.
    
    # In a real app, use Celery/arq. Here, BackgroundTasks.
    # We need to handle DB session in background task carefully.
    
    background_tasks.add_task(process_document_background, document.id)
    
    return document

async def process_document_background(document_id: int):
    # Create a new session for the background task
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        orchestrator = Orchestrator(db)
        await orchestrator.process_document(document_id)
    finally:
        db.close()

@router.get("/", response_model=List[DocumentRead])
def list_documents(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    doc_service = DocumentService(db)
    return doc_service.get_multi(skip=skip, limit=limit)

@router.get("/{document_id}", response_model=DocumentWithResults)
def get_document(
    document_id: int, 
    db: Session = Depends(get_db)
):
    doc_service = DocumentService(db)
    document = doc_service.get(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document
