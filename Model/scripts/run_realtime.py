# scripts/run_realtime.py

import os
import sys
import time
from datetime import datetime
import sqlite3
import argparse
import re

import cv2
import numpy as np

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

from config import (
    DB_PATH,
    MODEL_PATH,                 # kept for future YOLO reuse, not used now
    FRAME_SKIP,
    COOLDOWN_SECONDS,
    CAMERA_ID,
    CAMERA_MODE,
    SNAPSHOT_DIR,
    trigger_gate_open,
    trigger_gate_block,
)
from scripts.utils_ocr import recognize_plate

# ------------------------
# ROI + UPSCALE PARAMETERS
# ------------------------
# For your new video: plate is bottom-center.
ROI_TOP = 0.50      # 50% from top (lower half)
ROI_BOTTOM = 0.95   # a bit above bottom
ROI_LEFT = 0.30     # 30% from left
ROI_RIGHT = 0.70    # 70% from left

UPSCALE_FACTOR = 3.0     # enlarge ROI before OCR
SHOW_WINDOW = False      # set True ONLY if cv2.imshow works for you
# ------------------------


def connect_db():
    return sqlite3.connect(DB_PATH)


def get_vehicle_status(conn, plate):
    c = conn.cursor()
    c.execute("SELECT status FROM vehicles WHERE plate_number=?", (plate,))
    row = c.fetchone()
    if row:
        return row[0]
    else:
        # Unknown plate -> visitor by default
        c.execute(
            "INSERT INTO vehicles (plate_number, status) VALUES (?, ?)",
            (plate, "visitor")
        )
        conn.commit()
        return "visitor"


def insert_log(conn, plate, decision, detection_conf, ocr_conf, image_path):
    c = conn.cursor()
    timestamp = datetime.now().isoformat(timespec='seconds')
    c.execute("""
        INSERT INTO logs (plate_number, timestamp, direction, camera_id,
                          detection_conf, ocr_conf, image_path, decision)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (plate, timestamp, CAMERA_MODE, CAMERA_ID,
          detection_conf, ocr_conf, image_path, decision))
    conn.commit()


def clean_indian_plate(text: str):
    """
    Very strict cleaner:
    - Keeps only A–Z and 0–9.
    - Enforces common Indian pattern: AA99A9?9999
      (2 letters, 2 digits, 1–2 letters, 4 digits)
    - Fixes some OCR confusions.
    """
    if not text:
        return None

    # Uppercase and remove non-alphanumeric
    t = re.sub(r'[^A-Z0-9]', '', text.upper())

    if len(t) < 8:  # too short to be a real plate
        return None

    # Common OCR confusions
    t = t.replace('O', '0')
    t = t.replace('I', '1')
    t = t.replace('Z', '2')
    t = t.replace('S', '5')

    pattern = r'^[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{4}$'
    if re.match(pattern, t):
        return t

    return None


def main():
    parser = argparse.ArgumentParser(description="Run OCR-only ANPR on video or camera.")
    parser.add_argument("--source", type=str, default="0",
                        help="Video file path or camera index (default 0)")
    args = parser.parse_args()

    # Open source
    source = args.source
    if source.isdigit():
        source = int(source)

    print(f"[INFO] Opening source: {source}")
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print(f"[ERROR] Failed to open source: {source}")
        return
    else:
        print("[INFO] Source opened successfully.")

    conn = connect_db()
    print(f"[INFO] Connected to DB at {DB_PATH}")

    frame_idx = 0
    recent_events = {}  # plate -> last_detection_time

    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    print(f"[INFO] Snapshots will be saved to {SNAPSHOT_DIR}")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[INFO] End of video or cannot read frame.")
            break

        frame_idx += 1

        if frame_idx == 1:
            print(f"[INFO] First frame size: {frame.shape}")

        # Skip frames for speed
        if frame_idx % FRAME_SKIP != 0:
            if SHOW_WINDOW:
                cv2.imshow("ANPR", frame)
                if cv2.waitKey(1) & 0xFF == 27:
                    break
            continue

        print(f"[DEBUG] Processing frame {frame_idx}")

        H, W, _ = frame.shape
        y1_roi = int(H * ROI_TOP)
        y2_roi = int(H * ROI_BOTTOM)
        x1_roi = int(W * ROI_LEFT)
        x2_roi = int(W * ROI_RIGHT)

        # Safety clamp
        y1_roi = max(0, min(H - 1, y1_roi))
        y2_roi = max(0, min(H, y2_roi))
        x1_roi = max(0, min(W - 1, x1_roi))
        x2_roi = max(0, min(W, x2_roi))

        roi = frame[y1_roi:y2_roi, x1_roi:x2_roi].copy()
        print(f"[DEBUG] ROI shape: {roi.shape}")

        if roi.size == 0:
            print("[WARN] ROI empty, skipping frame.")
            continue

        # Upscale ROI
        roi_up = cv2.resize(
            roi,
            None,
            fx=UPSCALE_FACTOR,
            fy=UPSCALE_FACTOR,
            interpolation=cv2.INTER_CUBIC
        )
        print(f"[DEBUG] Upscaled ROI shape: {roi_up.shape}")

        # OCR on ROI
        raw_text, ocr_conf = recognize_plate(roi_up, min_conf=0.4)
        print(f"[DEBUG] Raw OCR: {raw_text}, conf: {ocr_conf:.2f}")

        plate_text = clean_indian_plate(raw_text)
        if not plate_text:
            print(f"[DEBUG] Frame {frame_idx}: no valid plate after cleaning.")
            if SHOW_WINDOW:
                cv2.imshow("ANPR", frame)
                if cv2.waitKey(1) & 0xFF == 27:
                    break
            continue

        print(f"[DETECT] Frame {frame_idx} → RAW: {raw_text}, CLEAN: {plate_text}, ocr_conf: {ocr_conf:.2f}")

        now = time.time()
        last_t = recent_events.get(plate_text)
        if last_t and (now - last_t < COOLDOWN_SECONDS):
            print(f"[INFO] Plate {plate_text} in cooldown, skipping log.")
            if SHOW_WINDOW:
                cv2.imshow("ANPR", frame)
                if cv2.waitKey(1) & 0xFF == 27:
                    break
            continue

        recent_events[plate_text] = now

        # DECISION LOGIC
        status = get_vehicle_status(conn, plate_text)
        if status == "blacklisted":
            decision = "blocked"
            trigger_gate_block(plate_text)
        else:
            decision = "allowed"
            trigger_gate_open(plate_text)

        print(f"[DECISION] Plate {plate_text} -> {decision} (status={status})")

        # Save snapshot of ROI
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_name = f"{ts_str}_{plate_text}_{decision}_ocr_only.jpg"
        snapshot_path = os.path.join(SNAPSHOT_DIR, snapshot_name)
        cv2.imwrite(snapshot_path, roi)

        # Log to DB (detection_conf = 0.0 since no YOLO)
        insert_log(conn, plate_text, decision, 0.0, ocr_conf, snapshot_path)

        # Optional: show frame
        if SHOW_WINDOW:
            # Draw a rectangle showing ROI area and plate text
            color = (0, 255, 0) if decision == "allowed" else (0, 0, 255)
            cv2.rectangle(frame, (x1_roi, y1_roi), (x2_roi, y2_roi), color, 2)
            cv2.putText(frame, f"{plate_text} {decision}",
                        (x1_roi, max(0, y1_roi - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            cv2.imshow("ANPR OCR-ONLY", frame)
            if cv2.waitKey(1) & 0xFF == 27:
                break

    cap.release()
    conn.close()
    if SHOW_WINDOW:
        cv2.destroyAllWindows()
    print("[INFO] Processing finished.")


if __name__ == "__main__":
    main()
