import fitz  # PyMuPDF
from typing import List
import os

class PDFService:
    @staticmethod
    def pdf_to_images(pdf_path: str, output_dir: str, dpi: int = 300) -> List[str]:
        """Convert PDF pages to images.""" # Returns list of image paths
        doc = fitz.open(pdf_path)
        image_paths = []
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(dpi=dpi)
            image_filename = f"page_{page_num + 1}.jpg"
            image_path = os.path.join(output_dir, image_filename)
            pix.save(image_path)
            image_paths.append(image_path)
            
        return image_paths
