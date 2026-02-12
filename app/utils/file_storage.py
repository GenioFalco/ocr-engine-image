import os
import secrets
from pathlib import Path
from typing import List

from pdf2image import convert_from_path

BASE_STORAGE_PATH = Path("storage")

def save_uploaded_file(file_content: bytes, filename: str) -> str:
    """
    Save uploaded file to disk and return the path.
    """
    if not BASE_STORAGE_PATH.exists():
        BASE_STORAGE_PATH.mkdir(parents=True, exist_ok=True)
    
    file_ext = Path(filename).suffix
    unique_filename = f"{secrets.token_hex(8)}{file_ext}"
    file_path = BASE_STORAGE_PATH / unique_filename
    
    with open(file_path, "wb") as buffer:
        buffer.write(file_content)
        
    return str(file_path)

def convert_pdf_to_images(pdf_path: str) -> List[str]:
    """
    Convert PDF to list of image paths (one per page).
    """
    try:
        # Check for poppler in common locations or assume in PATH
        images = convert_from_path(pdf_path)
    except Exception as e:
        if "poppler" in str(e).lower() or "not found" in str(e).lower():
            raise RuntimeError(
                "Poppler is not installed or not in PATH. "
                "Please download Poppler for Windows and add 'bin' folder to PATH."
            ) from e
        raise e

    image_paths = []
    pdf_name = Path(pdf_path).stem
    
    for i, image in enumerate(images):
        image_filename = f"{pdf_name}_page_{i+1}.jpg"
        image_path = BASE_STORAGE_PATH / image_filename
        image.save(image_path, "JPEG")
        image_paths.append(str(image_path))
        
    return image_paths
