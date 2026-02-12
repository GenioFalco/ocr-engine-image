from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class BaseLLM(ABC):
    @abstractmethod
    async def extract_data(self, image_paths: List[str], schema: Dict[str, Any], prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract structured data from images using the provided JSON schema.
        """
        pass

    @abstractmethod
    async def classify_document(self, image_path: str, categories: List[str]) -> str:
        """
        Classify the document page into one of the categories.
        """
        pass
