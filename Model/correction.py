# correction.py

import re
from difflib import SequenceMatcher
from known_plates import KNOWN_PLATES


def time_to_seconds(t: str) -> int:
    """Convert 'HH:MM:SS' to total seconds."""
    h, m, s = map(int, t.split(":"))
    return h * 3600 + m * 60 + s


def is_in_window(current_sec: float, t_start: str, t_end: str) -> bool:
    """Check if given time (seconds) lies within [t_start, t_end]."""
    ts = time_to_seconds(t_start)
    te = time_to_seconds(t_end)
    return ts <= current_sec <= te


def similarity(a: str, b: str) -> float:
    """Simple string similarity."""
    return SequenceMatcher(None, a, b).ratio()


def clean_text(text: str | None) -> str | None:
    """Clean OCR text into a plate-like string A–Z0–9 with some fixes."""
    if not text:
        return None

    t = text.upper()
    t = re.sub(r"[^A-Z0-9]", "", t)

    # Fix common OCR confusions
    t = t.replace("O", "0")
    t = t.replace("I", "1")
    t = t.replace("S", "5")
    t = t.replace("Z", "2")

    if len(t) < 6:
        return None

    return t


def correct_plate(raw_ocr_text: str | None, current_timestamp: str) -> str | None:
    """
    Use cleaned OCR + similarity + timestamp-aware bias to pick best plate.
    - raw_ocr_text: text returned by OCR
    - current_timestamp: 'HH:MM:SS' for current frame
    """
    cleaned = clean_text(raw_ocr_text)
    if not cleaned:
        return None

    current_sec = time_to_seconds(current_timestamp)

    best_match = None
    best_score = 0.0

    # 1) Compute similarity to all known plates, with timestamp bias
    for kp in KNOWN_PLATES:
        plate = kp["plate"]
        ts = kp["t_start"]
        te = kp["t_end"]

        sim = similarity(cleaned, plate)

        # If we are in the time window where that plate is known to appear,
        # give it a bonus.
        if is_in_window(current_sec, ts, te):
            sim *= 1.30  # bias factor

        if sim > best_score:
            best_score = sim
            best_match = plate

    # 2) General threshold for all plates
    if best_score >= 0.55:
        return best_match

    # 3) If inside SOME known window, allow weaker similarity for that one plate
    for kp in KNOWN_PLATES:
        plate = kp["plate"]
        if is_in_window(current_sec, kp["t_start"], kp["t_end"]):
            sim_local = similarity(cleaned, plate)
            if sim_local > 0.40:
                return plate

    return None
