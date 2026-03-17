#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PDF → Images service (no resize, vertical stitch)
- Принимает PDF
- Рендерит страницы в 300 DPI
- Склеивает страницы вертикально (если их несколько)
- Отдаёт JPEG base64
"""

import base64
from io import BytesIO
from uuid import uuid4
from typing import List

import fitz  # PyMuPDF
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from PIL import Image

OCR_DPI = 300
JPEG_QUALITY = 70

app = FastAPI(
    title="CES PDF → Images (No Resize)",
    version="2.0.1",
)


def render_page(page: fitz.Page) -> Image.Image:
    """Рендер одной страницы PDF в PIL.Image без уменьшения размера."""
    zoom = OCR_DPI / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return img


def to_base64(img: Image.Image) -> str:
    """Конвертация PIL.Image → base64 JPEG."""
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    img_bytes = buf.getvalue()
    buf.close()
    return base64.b64encode(img_bytes).decode("ascii")


def stitch_vertical(images: List[Image.Image]) -> Image.Image:
    """Вертикальная склейка нескольких изображений в одно."""
    widths = [im.width for im in images]
    heights = [im.height for im in images]

    max_width = max(widths)
    total_height = sum(heights)

    stitched = Image.new("RGB", (max_width, total_height), color=(255, 255, 255))

    y_offset = 0
    for im in images:
        stitched.paste(im, (0, y_offset))
        y_offset += im.height

    return stitched


@app.post("/segment_pdf")
async def pdf_to_images(file: UploadFile = File(...)):
    """
    Принимает PDF (multipart/form-data, поле file)
    Возвращает JSON вида:
    {
      "source_file_name": "...",
      "session_id": "...",
      "page_count": N,
      "pages": [
        {
          "page": 1,
          "width": ...,
          "height": ...,
          "image_base64": "..."
        }
      ]
    }
    """
    pdf_bytes = await file.read()
    session_id = f"sess_{uuid4().hex[:8]}"

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        pil_pages: List[Image.Image] = []

        # рендерим все страницы
        for i in range(doc.page_count):
            page = doc.load_page(i)
            pil_pages.append(render_page(page))

        # если страниц несколько — склеиваем в одну вертикальную ленту
        if len(pil_pages) > 1:
            final_img = stitch_vertical(pil_pages)
            pages_out = [
                {
                    "page": 1,
                    "width": final_img.width,
                    "height": final_img.height,
                    "image_base64": to_base64(final_img),
                }
            ]
        else:
            img = pil_pages[0]
            pages_out = [
                {
                    "page": 1,
                    "width": img.width,
                    "height": img.height,
                    "image_base64": to_base64(img),
                }
            ]

        result = {
            "source_file_name": file.filename or "uploaded.pdf",
            "session_id": session_id,
            "page_count": len(pil_pages),
            "pages": pages_out,
        }

        return JSONResponse(result)

    finally:
        doc.close()

