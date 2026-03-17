from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class ClassificationResult(BaseModel):
    document_type: str
    confidence: float
    raw_response: str = ""

class ExtractionResult(BaseModel):
    fields: Dict[str, Any]
    stamps: List[Dict[str, Any]]
    signatures: List[Dict[str, Any]]
    raw_response: str

class BaseLLM(ABC):
    @abstractmethod
    def classify_page(self, image_path: str, document_types: Optional[List[Dict[str, str]]] = None) -> ClassificationResult:
        """Classify a single page image."""
        pass

    @abstractmethod
    def classify_document(self, image_paths: List[str], document_types: Optional[List[Dict[str, str]]] = None) -> ClassificationResult:
        """Classify a multi-page document."""
        pass

    @abstractmethod
    def extract_document(self, images_data: List[Dict[str, Any]], json_schema: Dict[str, Any]) -> ExtractionResult:
        """Extract data from a document based on a JSON schema."""
        pass

    @abstractmethod
    def validate_extraction(self, extraction_result: ExtractionResult, images_data: List[Dict[str, Any]]) -> bool:
        """Validate the extraction result."""
        pass
