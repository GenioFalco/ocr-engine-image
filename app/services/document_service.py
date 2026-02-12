from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.models.document import Document, DocumentStatus
from app.db.models.ocr_result import OCRResult
from app.schemas.document import DocumentCreate, DocumentUpdate

class DocumentService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, obj_in: DocumentCreate) -> Document:
        db_obj = Document(
            filename=obj_in.filename,
            file_path=obj_in.file_path,
            file_type=obj_in.file_type,
            content_hash=obj_in.content_hash,
            meta=obj_in.meta or {},
            status=DocumentStatus.PENDING
        )
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def get(self, document_id: int) -> Optional[Document]:
        return self.db.query(Document).filter(Document.id == document_id).first()

    def get_multi(self, skip: int = 0, limit: int = 100) -> List[Document]:
        return self.db.query(Document).offset(skip).limit(limit).all()

    def update_status(self, document_id: int, status: DocumentStatus, error_message: Optional[str] = None):
        db_obj = self.get(document_id)
        if db_obj:
            db_obj.status = status
            if error_message:
                db_obj.error_message = error_message
            self.db.commit()
            self.db.refresh(db_obj)

    def create_result(self, result_in: dict) -> OCRResult:
        db_obj = OCRResult(**result_in)
        self.db.add(db_obj)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj
