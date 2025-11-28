# scripts/utils_ocr.py

import easyocr
import re
import numpy as np
import cv2

_reader = None

def get_ocr_reader():
    global _reader
    if _reader is None:
        # English only is fine for Indian plates
        _reader = easyocr.Reader(['en'], gpu=False)
    return _reader

def clean_plate(text: str):
    """
    Basic cleanup + Indian plate heuristics.
    """
    if not text:
        return None
    text = text.upper()
    # Remove spaces and non-alphanumeric
    text = re.sub(r'[^A-Z0-9]', '', text)

    # Common OCR confusions
    text = text.replace("O", "0").replace("I", "1")

    # Typical Indian pattern: 2 letters, 2 digits, 1–3 letters, 4 digits
    pattern = r'^[A-Z]{2}\d{2}[A-Z]{1,3}\d{4}$'
    if re.match(pattern, text):
        return text

    # If doesn't match but still long enough, return as "best guess"
    if len(text) >= 6:
        return text

    return None

def recognize_plate(img_bgr, min_conf=0.5):
    """
    Run OCR on plate crop (BGR image).
    Returns (clean_text or None, avg_conf or 0.0)
    """
    reader = get_ocr_reader()

    # Pre-process: grayscale, resize, threshold
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    scale = 200.0 / max(h, w)
    new_size = (int(w * scale), int(h * scale))
    gray = cv2.resize(gray, new_size, interpolation=cv2.INTER_LINEAR)

    # Slight blur + adaptive threshold
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    # Binarize (optional – EasyOCR can handle grayscale, but this helps sometimes)
    # _, gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    result = reader.readtext(gray, detail=1)
    if not result:
        return None, 0.0

    texts = []
    confs = []
    for bbox, t, conf in result:
        if t.strip():
            texts.append(t.strip())
            confs.append(conf)

    if not texts:
        return None, 0.0

    raw_text = " ".join(texts)
    avg_conf = float(np.mean(confs)) if confs else 0.0

    if avg_conf < min_conf:
        return None, avg_conf

    cleaned = clean_plate(raw_text)
    if not cleaned:
        return None, avg_conf

    return cleaned, avg_conf
