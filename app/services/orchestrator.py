import asyncio
import os
import json
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session
from app.core.logging import logger
from app.db.models.document import DocumentStatus, Document
from app.services.document_service import DocumentService
from app.services.model_service import ModelService
from app.services.contract_service import ContractService
from app.providers.llm.gigachat_provider import GigaChatProvider
from app.utils.file_storage import convert_pdf_to_images
from app.utils.deduplicator import is_duplicate

class Orchestrator:
    def __init__(self, db: Session):
        self.db = db
        self.doc_service = DocumentService(db)
        self.model_service = ModelService(db)
        self.contract_service = ContractService(db)

    async def process_document(self, document_id: int):
        document = self.doc_service.get(document_id)
        if not document:
            logger.error(f"Document {document_id} not found")
            return

        try:
            self.doc_service.update_status(document_id, DocumentStatus.PROCESSING)
            
            # 1. Convert PDF to images
            if document.file_path.lower().endswith(".pdf"):
                image_paths = convert_pdf_to_images(document.file_path)
            else:
                image_paths = [document.file_path] # Assume image

            # 2. Get Active LLM
            model_reg = self.model_service.get_by_provider("gigachat")
            if not model_reg:
                # Fallback to check if user still has gemini configured, or raise error
                logger.warning("No active GigaChat model found, checking for generic/gemini")
                model_reg = self.model_service.get_by_provider("gemini")
            
            if not model_reg:
                 raise ValueError("No active LLM model found (GigaChat or Gemini)")
            
            # Initialize provider based on type
            if model_reg.provider == "gigachat":
                 llm_provider = GigaChatProvider(credentials=model_reg.api_key, model_name=model_reg.name)
            else:
                 from app.providers.llm.gemini_provider import GeminiProvider
                 llm_provider = GeminiProvider(api_key=model_reg.api_key, model_name=model_reg.name)

            # 3. Classify Page (Simplification: process page by page as separate docs or one doc)
            # The prompt implies splitting PDF into separate documents.
            # For MVP, we'll try to process each page and classify.
            # If multiple pages belong to same doc, we should group. This is complex.
            # Simplified approach: Treat each PDF as containing one or more documents.
            # Let's try to extract from the whole set or per page.
            
            # Strategy: Classify first page to determine document type.
            # Then extract using that contract.
            
            contracts = self.contract_service.get_all_active()
            if not contracts:
                raise ValueError("No active contracts found")
            
            contract_names = [c.name for c in contracts]
            
            # Classify first page
            doc_type = await llm_provider.classify_document(image_paths[0], contract_names)
            logger.info(f"Classified document as: {doc_type}")
            
            target_contract = next((c for c in contracts if c.name == doc_type), None)
            
            if target_contract:
                # Extract using schema
                extraction_result = await llm_provider.extract_data(image_paths, target_contract.schema)
                
                # Deduplication check
                # We need to fetch existing results for this contract to check duplicates
                # This is expensive, so maybe check only recent ones or use hash
                # implemented in deduplicator.py
                
                # Save result
                self.doc_service.create_result({
                    "document_id": document_id,
                    "model_id": model_reg.id,
                    "contract_id": target_contract.id,
                    "extracted_data": extraction_result,
                    # "stamps_signatures": ... (if returned by LLM or separate OCR)
                    "tokens_used": 0, # Metric placeholder
                })
                
                self.doc_service.update_status(document_id, DocumentStatus.COMPLETED)
            else:
                self.doc_service.update_status(document_id, DocumentStatus.FAILED, f"Unknown document type: {doc_type}")

        except Exception as e:
            logger.error(f"Processing failed for doc {document_id}: {e}")
            self.doc_service.update_status(document_id, DocumentStatus.FAILED, str(e))
