import re
import logging
from typing import Tuple, List
import tesserocr
import io
import os
import glob

logger = logging.getLogger(__name__)

# Dynamically locate tessdata inside the container
_TESSDATA_PREFIX = ""
_tessdata_paths = glob.glob("/usr/share/tesseract-ocr/*/tessdata")
if _tessdata_paths:
    _TESSDATA_PREFIX = _tessdata_paths[0]

# Constants
OCR_LANG = "rus+eng"
MIN_TEXT_LEN = 160
HEADER_SCAN_LINES = 18

RXF = re.IGNORECASE | re.MULTILINE

# --- Regex Patterns from Legacy Script ---
AKT_HEADER_PATTERNS = [
    r"\bАКТ\s*№\s*[\w/.\-]+",
    r"\bАКТ\s+(СДАЧИ|-?\s*ПРИ[ЕЕ]М[КК]И)",
    r"\bАКТ\s+О?\s*ВЫПОЛНЕНИИ\s+ПОРУЧЕНИЯ",
    r"\bАКТ\s+ПРИ[ЕЕ]М[АО]-СДАЧ[ИЫ]",
    r"\bАКТ\s+ОКАЗАННЫХ\s+УСЛУГ",
    r"\bАКТ\s+ПРИ[ЕЕ]МА\s+УСЛУГ",
    r"\bАКТ\s+СДАЧИ-?ПРИ[ЕЕ]МКИ",
    r"\bАКТ\s+СВЕРКИ\b",
    r"\bКС-2\b",
    r"\bОТЧЕТ\s+АГЕНТА\b",
]
AKT_HEADER_RX = re.compile("|".join(AKT_HEADER_PATTERNS), RXF)

SCHET_HEADER_PATTERNS = [
    r"\bСЧ[ЕЕ]Т\s*(НА\s*ОПЛАТУ)?\b",
    r"\bINVOICE\b",
]
SCHET_HEADER_RX = re.compile("|".join(SCHET_HEADER_PATTERNS), RXF)

SF_HEADER_PATTERNS = [
    r"\bСЧ[ЕЕ]Т\s*-\s*ФАКТУРА\b",
    r"\bСЧ[ЕЕ]ТФАКТУРА\b",
]
SF_HEADER_RX = re.compile("|".join(SF_HEADER_PATTERNS), RXF)

UPD_HEADER_PATTERNS = [
    r"\bУНИВЕРСАЛЬН(ЫЙ|ОЕ)\s+(ПЕРЕДАТОЧН(ЫЙ|ОЕ)|СЧ[ЕЕ]Т-?ФАКТУРА)\b",
    r"Приложение\s*[№N][oо]?\s*1\s*к\s*постановлению\s*Правительства\s*Российской\s*Федерации\s*от\s*26\s*(декабря|12)\s*[\.\s]*2011",
]
UPD_HEADER_RX = re.compile("|".join(UPD_HEADER_PATTERNS), RXF)

# OCR-tolerant UPD clues: partial decree text that survives bad OCR scans
# e.g. "1 кпостановлению Правительства Российской Федерации от 26 декабря 2011 « Ne 1137"
# Note: постановлению.*1137 uses re.DOTALL separately because .* must cross newlines
UPD_BODY_PATTERNS = [
    r"\bУНИВЕРСАЛЬН(ЫЙ|ОЕ)\s+(ПЕРЕДАТОЧН(ЫЙ|ОЕ)|СЧ[ЕЕ]Т-?ФАКТУРА)\b",
    r"к\s*постановлению\s*Правительства\s*Российской\s*Федерации\s*от\s*26\s*(декабря|12)[\.\s]*2011",
    # УПД-специфичное поле "Статус:" (только в форме УПД, не в обычной СФ)
    r"\bСтатус\s*:\s*[12]\b",
    # Аббревиатура УПД в тексте
    r"\bУПД\b",
    # Уникальная строка раздела передачи — есть ТОЛЬКО в УПД, не в СФ и не в счёте
    r"Основание\s+передачи\s*\(сдачи\)",
    r"получени[яе]\s*\(прие[мн]ки\)",
    # Номер функции документа (поле "Функция" в УПД)
    r"\bФункция\s*[:\-–]\s*(СЧФ|ДОП|СЧФДОП)\b",
]
UPD_BODY_RX = re.compile("|".join(UPD_BODY_PATTERNS), RXF)
# Отдельный паттерн для "постановление...1137" с DOTALL (пересекает строки)
UPD_DECREE_RX = re.compile(
    r"постановлению\s*Правительства\s*Российской\s*Федерации[\s\S]{0,80}1137",
    re.IGNORECASE
)

BANK_CLUES_RX = re.compile(
    r"\bИНН\b|\bКПП\b|\bБИК\b|\bСч\.\s*№|\bПолучатель\b|\bПлательщик\b|\bБанк\s+получателя\b",
    RXF,
)

# ── Товарная накладная (ТОРГ-12) ──────────────────────────────────────────────
TORG12_HEADER_PATTERNS = [
    r"\bТОВАРНАЯ\s+НАКЛАДНАЯ\b",
    r"\bТОРГ\s*-?\s*12\b",
    r"Унифицированная\s+форма\s*[№N]?\s*ТОРГ",
    r"форма\s*[№N]?\s*ТОРГ-12",
]
TORG12_HEADER_RX = re.compile("|".join(TORG12_HEADER_PATTERNS), RXF)

TORG12_BODY_PATTERNS = [
    r"\bТОВАРНАЯ\s+НАКЛАДНАЯ\b",
    r"\bГрузоотправитель\b.*\bГрузополучатель\b",  # обе строки присутствуют
    r"\bТОРГ\s*-?\s*12\b",
]
TORG12_BODY_RX = re.compile("|".join(TORG12_BODY_PATTERNS), RXF | re.DOTALL)

# Standardized Document Types
# These should ideally match the "names" of your DocumentTypes in the database
TYPE_UPD = "UPD"
TYPE_AKT = "Act"
TYPE_SCHET = "Invoice"
TYPE_SF = "Invoice-Factura"
TYPE_TORG12 = "Torg12"
TYPE_UNKNOWN = "unknown"

def norm(s: str) -> str:
    s = s.replace("ё", "е").replace("Ё", "Е")
    s = s.replace("–", "-").replace("—", "-")
    return s

def head(text: str, n_lines: int = HEADER_SCAN_LINES) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines[:n_lines])

import threading

# Cache the Tesseract API instance per-thread to avoid the 2-second C++ model loading overhead
_tess_local = threading.local()

def get_tesserocr_api():
    if not hasattr(_tess_local, "api"):
        # PSM.AUTO_OSD enables Orientation and Script Detection, so upside-down or sideways pages are automatically rotated
        _tess_local.api = tesserocr.PyTessBaseAPI(path=_TESSDATA_PREFIX, lang=OCR_LANG, psm=tesserocr.PSM.AUTO_OSD)
    return _tess_local.api

def extract_text_from_raw_samples_with_osd(samples: bytes, width: int, height: int, bpp: int, stride: int) -> Tuple[str, int]:
    """Extract text from raw image bytes and return text along with detected orientation angle (0, 90, 180, 270)."""
    try:
        api = get_tesserocr_api()
        api.SetImageBytes(samples, width, height, bpp, stride)
        text = api.GetUTF8Text()
        
        # Determine orientation
        rotation = 0
        try:
            # PSM.AUTO_OSD is already set, so Tesseract should have calculated orientation internally
            it = api.AnalyseLayout()
            if it:
                orientation, direction, textline_order, deskew_angle = it.Orientation()
                # Orientation enum mapping in tesserocr: 0: UP, 1: RIGHT, 2: DOWN, 3: LEFT
                # Which means: UP (0 degrees), RIGHT (90 degrees CCW to fix), DOWN (180 degrees), LEFT (270 degrees CCW to fix)
                # To fix the image, we rotate it by these degrees respectively
                if orientation == 1:
                    rotation = 270 # If top is pointing right, rotate image left (270) to fix
                elif orientation == 2:
                    rotation = 180
                elif orientation == 3:
                    rotation = 90
        except Exception as osd_e:
            logger.warning(f"OSD Orientation extraction failed: {osd_e}")
            pass
            
        return text, rotation
    except Exception as e:
        logger.error(f"OCR Error extracting from raw samples: {e}")
        return "", 0

def extract_text_from_raw_samples(samples: bytes, width: int, height: int, bpp: int, stride: int) -> str:
    """Extract text from raw image bytes. Used for fast header classification."""
    try:
        api = get_tesserocr_api()
        # Ensure API accepts raw bytes (e.g. from PyMuPDF pixmap object)
        api.SetImageBytes(samples, width, height, bpp, stride)
        text = api.GetUTF8Text()
        return text
    except Exception as e:
        logger.error(f"OCR Error extracting from raw samples: {e}")
        return ""

def detect_orientation(samples: bytes, width: int, height: int, bpp: int, stride: int) -> int:
    """Run OSD pass to determine page orientation. Returns degrees to rotate (0/90/180/270)."""
    try:
        # AUTO_OSD works correctly; OSD_ONLY returns None for AnalyseLayout on scanned pages
        if not hasattr(_tess_local, "osd_api"):
            _tess_local.osd_api = tesserocr.PyTessBaseAPI(path=_TESSDATA_PREFIX, lang="osd", psm=tesserocr.PSM.AUTO_OSD)
        osd_api = _tess_local.osd_api
        osd_api.SetImageBytes(samples, width, height, bpp, stride)
        it = osd_api.AnalyseLayout()
        if it:
            orientation, direction, textline_order, deskew_angle = it.Orientation()
            # Orientation enum: 0=UP (normal), 1=RIGHT, 2=DOWN (180°), 3=LEFT
            # AUTO_OSD returns the orientation of the text block, not angle to rotate
            # 3=LEFT means the top is on the left -> we need to rotate 90° to fix it
            if orientation == 1: return 90
            elif orientation == 2: return 180
            elif orientation == 3: return 270
    except Exception as e:
        logger.warning(f"OSD detection failed: {e}")
    return 0

    
def classify_page_text(txt: str) -> Tuple[str, bool, List[str]]:
    """
    Returns (doc_type, header_hit, reasons[])
    header_hit=True means this is the START of a new document.
    """
    reasons = []
    t = norm(txt)
    # Увеличенный скан заголовка: УПД-метка часто стоит в левом сайдбаре,
    # который в PDF-тексте может оказаться не в первых 18 строках
    h = norm(head(t, 30))

    # Priority 1: UPD (заголовок)
    if UPD_HEADER_RX.search(h):
        reasons.append("UPD:title")
        return TYPE_UPD, True, reasons

    # Priority 1.5: UPD по телу документа
    # (УПД содержит СФ-заголовок, поэтому проверяем до SF/SCHET)
    if UPD_BODY_RX.search(t):
        reasons.append("UPD:body")
        return TYPE_UPD, True, reasons

    # Priority 1.6: УПД по постановлению 1137 (через строки)
    if UPD_DECREE_RX.search(t):
        reasons.append("UPD:decree1137")
        return TYPE_UPD, True, reasons

    # Priority 2: TORG-12 (Товарная накладная) — очень однозначный заголовок
    if TORG12_HEADER_RX.search(h):
        reasons.append("TORG12:title")
        return TYPE_TORG12, True, reasons

    # Priority 3: SF
    if SF_HEADER_RX.search(h):
        reasons.append("SF:title")
        return TYPE_SF, True, reasons

    # Priority 4: AKT
    if AKT_HEADER_RX.search(h):
        reasons.append("AKT:title")
        return TYPE_AKT, True, reasons

    # Priority 5: SCHET
    if SCHET_HEADER_RX.search(h):
        reasons.append("SCH:headline")
        return TYPE_SCHET, True, reasons

    # Auxiliary SCHET clues
    if BANK_CLUES_RX.search(h) and re.search(r"\bСЧ[ЕЕ]Т\b", t, RXF):
        reasons.append("SCH:bank/org")
        return TYPE_SCHET, False, reasons

    # BODY clues (Continuation of doc)
    if TORG12_BODY_RX.search(t):
        reasons.append("TORG12:body")
        return TYPE_TORG12, False, reasons

    if re.search(r"\bАКТ\s*№\s*[\w/.\-]+", t, RXF) or re.search(r"\bСДАЧИ-?ПРИ[ЕЕ]МКИ", t, RXF):
        reasons.append("AKT:body")
        return TYPE_AKT, False, reasons

    if re.search(r"\bСЧ[ЕЕ]Т\s*-\s*ФАКТУРА\b", t, RXF):
        reasons.append("SF:body")
        return TYPE_SF, False, reasons

    return TYPE_UNKNOWN, False, ["no-hit"]
