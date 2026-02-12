from abc import ABC, abstractmethod

class BaseOCR(ABC):
    @abstractmethod
    async def get_text(self, image_path: str) -> str:
        """
        Extract raw text from an image.
        """
        pass
    
    @abstractmethod
    async def get_bboxes(self, image_path: str) -> list:
        """
        Get bounding boxes for words.
        """
        pass
