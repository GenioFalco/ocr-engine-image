import pytesseract
from PIL import Image

from app.providers.ocr.base_ocr import BaseOCR
from app.core.logging import logger

class TesseractFallback(BaseOCR):
    def __init__(self, lang: str = "rus+eng"):
        self.lang = lang

    async def get_text(self, image_path: str) -> str:
        try:
            image = Image.open(image_path)
            # pytesseract is synchronous, might block event loop if large.
            # In production, offload to thread/process or use async wrapper.
            # For MVP, it's acceptable.
            return pytesseract.image_to_string(image, lang=self.lang)
        except Exception as e:
            logger.error(f"Tesseract OCR failed: {e}")
            raise

    async def get_bboxes(self, image_path: str) -> list:
        # Implementation of pytesseract.image_to_data for bboxes
        try:
            image = Image.open(image_path)
            data = pytesseract.image_to_data(image, lang=self.lang, output_type=pytesseract.Output.DICT)
            bboxes = []
            n_boxes = len(data['level'])
            for i in range(n_boxes):
                if data['text'][i].strip():
                    (x, y, w, h) = (data['left'][i], data['top'][i], data['width'][i], data['height'][i])
                    bboxes.append({"text": data['text'][i], "bbox": [x, y, w, h]})
            return bboxes
        except Exception as e:
            logger.error(f"Tesseract bbox extraction failed: {e}")
            return []
