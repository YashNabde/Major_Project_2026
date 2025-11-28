# scripts/run_anpr.py

import os
import sys
import time
from datetime import datetime
import sqlite3
import argparse

import cv2
from ultralytics import YOLO

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

from config import (
    DB_PATH,
    MODEL_PATH,
    DETECTION_CONFIDENCE,
    IOU_THRESHOLD,
    FRAME_SKIP,
    COOLDOWN_SECONDS,
    CAMERA_ID,
    CAMERA_MODE,
    SNAPSHOT_DIR,
    trigger_gate_open,
    trigger_gate_block,
)
from scripts.utils_ocr import recognize_plate
from correction import correct_plate


# ROI tuned for bottom-center plates (you can tweak based on actual video)
ROI_TOP = 0.40
ROI_BOTTOM = 0.95
ROI_LEFT = 0.25
ROI_RIGHT = 0.75

UPSCALE_FACTOR = 2.0
SHOW_WINDOW = False  # keep False if cv2.imshow causes issues


def connect_db():
    return sqlite3.connect(DB_PATH)


def get_vehicle_status(conn, plate):
    c = conn.cursor()
    c.execute("SELECT status FROM vehicles WHERE plate_number=?", (plate,))
    row = c.fetchone()
    if row:
        return row[0]
    else:
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


def seconds_to_hms(sec: float) -> str:
    """Convert seconds float to HH:MM:SS string."""
    s = int(sec)
    h = s // 3600
    m = (s % 3600) // 60
    s2 = s % 60
    return f"{h:02d}:{m:02d}:{s2:02d}"


def main():
    parser = argparse.ArgumentParser(description="Run ANPR with YOLO + OCR + correction.")
    parser.add_argument("--source", type=str, default="0",
                        help="Video file path or camera index (default 0)")
    args = parser.parse_args()

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

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    print(f"[INFO] FPS detected: {fps:.2f}")

    # Load YOLOv8n model
    model_path = MODEL_PATH if os.path.exists(MODEL_PATH) else "yolov8n.pt"
    print(f"[INFO] Loading YOLO model from: {model_path}")
    model = YOLO(model_path)

    conn = connect_db()
    print(f"[INFO] Connected to DB at {DB_PATH}")

    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    print(f"[INFO] Snapshots directory: {SNAPSHOT_DIR}")

    frame_idx = 0
    recent_events = {}  # plate -> last_detection_time

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[INFO] End of video or cannot read frame.")
            break

        frame_idx += 1

        if frame_idx == 1:
            print(f"[INFO] First frame size: {frame.shape}")

        # Timestamp of this frame
        current_time_sec = frame_idx / fps
        current_ts_str = seconds_to_hms(current_time_sec)

        # Skip frames to save compute
        if frame_idx % FRAME_SKIP != 0:
            if SHOW_WINDOW:
                cv2.imshow("ANPR", frame)
                if cv2.waitKey(1) & 0xFF == 27:
                    break
            continue

        H, W, _ = frame.shape

        # Compute ROI
        y1_roi = int(H * ROI_TOP)
        y2_roi = int(H * ROI_BOTTOM)
        x1_roi = int(W * ROI_LEFT)
        x2_roi = int(W * ROI_RIGHT)

        # Clamp
        y1_roi = max(0, min(H - 1, y1_roi))
        y2_roi = max(0, min(H, y2_roi))
        x1_roi = max(0, min(W - 1, x1_roi))
        x2_roi = max(0, min(W, x2_roi))

        roi = frame[y1_roi:y2_roi, x1_roi:x2_roi].copy()
        if roi.size == 0:
            continue

        roi_up = cv2.resize(
            roi,
            None,
            fx=UPSCALE_FACTOR,
            fy=UPSCALE_FACTOR,
            interpolation=cv2.INTER_CUBIC
        )

        # YOLO detection on upscaled ROI
        results = model.predict(
            roi_up,
            imgsz=640,
            conf=DETECTION_CONFIDENCE,
            iou=IOU_THRESHOLD,
            verbose=False
        )

        display_frame = frame.copy()
        now = time.time()
        det_count = 0
        any_detected_this_frame = False

        for r in results:
            boxes = r.boxes
            if boxes is None or len(boxes) == 0:
                continue

            for box in boxes:
                det_count += 1

                x1u, y1u, x2u, y2u = box.xyxy[0].tolist()
                det_conf = float(box.conf[0])

                # Map back to full frame
                x1 = int(x1u / UPSCALE_FACTOR + x1_roi)
                y1 = int(y1u / UPSCALE_FACTOR + y1_roi)
                x2 = int(x2u / UPSCALE_FACTOR + x1_roi)
                y2 = int(y2u / UPSCALE_FACTOR + y1_roi)

                x1 = max(0, min(W - 1, x1))
                y1 = max(0, min(H - 1, y1))
                x2 = max(0, min(W - 1, x2))
                y2 = max(0, min(H - 1, y2))

                if x2 <= x1 or y2 <= y1:
                    continue

                plate_crop = frame[y1:y2, x1:x2]

                # OCR on YOLO crop
                raw_plate_text, ocr_conf = recognize_plate(plate_crop, min_conf=0.4)
                # Use correction engine with timestamp
                final_plate = correct_plate(raw_plate_text, current_ts_str)

                if not final_plate:
                    # Draw yellow box for unreadable
                    cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 255, 255), 2)
                    cv2.putText(display_frame, f"NO READ {det_conf:.2f}",
                                (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                (0, 255, 255), 2)
                    continue

                any_detected_this_frame = True
                print(f"[DETECT] Frame {frame_idx} ({current_ts_str}) → RAW: {raw_plate_text}, FINAL: {final_plate}, det_conf={det_conf:.2f}, ocr_conf={ocr_conf:.2f}")

                # Cooldown to avoid spam
                last_t = recent_events.get(final_plate)
                if last_t and (now - last_t < COOLDOWN_SECONDS):
                    cv2.rectangle(display_frame, (x1, y1), (x2, y2), (255, 255, 0), 2)
                    cv2.putText(display_frame, f"{final_plate} (cooldown)",
                                (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                (255, 255, 0), 2)
                    continue

                recent_events[final_plate] = now

                # Decision logic
                status = get_vehicle_status(conn, final_plate)
                if status == "blacklisted":
                    decision = "blocked"
                    trigger_gate_block(final_plate)
                    color = (0, 0, 255)
                else:
                    decision = "allowed"
                    trigger_gate_open(final_plate)
                    color = (0, 255, 0)

                print(f"[DECISION] Plate {final_plate} -> {decision} (status={status})")

                # Snapshot
                ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                snapshot_name = f"{ts_str}_{final_plate}_{decision}.jpg"
                snapshot_path = os.path.join(SNAPSHOT_DIR, snapshot_name)
                cv2.imwrite(snapshot_path, plate_crop)

                # Log
                insert_log(conn, final_plate, decision, det_conf, ocr_conf, snapshot_path)

                # Draw rect
                cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(display_frame, f"{final_plate} {decision}",
                            (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                            color, 2)

        # Optional fallback: if YOLO finds nothing, try OCR on whole ROI
        if det_count == 0:
            raw_plate_text, ocr_conf = recognize_plate(roi_up, min_conf=0.5)
            final_plate = correct_plate(raw_plate_text, current_ts_str)
            if final_plate:
                any_detected_this_frame = True
                print(f"[FALLBACK] Frame {frame_idx} ({current_ts_str}) → RAW: {raw_plate_text}, FINAL: {final_plate}, ocr_conf={ocr_conf:.2f}")

                last_t = recent_events.get(final_plate)
                if not last_t or (now - last_t >= COOLDOWN_SECONDS):
                    recent_events[final_plate] = now

                    status = get_vehicle_status(conn, final_plate)
                    if status == "blacklisted":
                        decision = "blocked"
                        trigger_gate_block(final_plate)
                        color = (0, 0, 255)
                    else:
                        decision = "allowed"
                        trigger_gate_open(final_plate)
                        color = (0, 255, 0)

                    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                    snapshot_name = f"{ts_str}_{final_plate}_{decision}_fallback.jpg"
                    snapshot_path = os.path.join(SNAPSHOT_DIR, snapshot_name)
                    cv2.imwrite(snapshot_path, roi)

                    insert_log(conn, final_plate, decision, 0.0, ocr_conf, snapshot_path)

                    # Draw text near ROI
                    cx = (x1_roi + x2_roi) // 2
                    cy = (y1_roi + y2_roi) // 2
                    cv2.putText(display_frame, f"{final_plate} {decision} (FB)",
                                (max(0, cx - 100), max(0, cy - 10)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        if SHOW_WINDOW:
            cv2.imshow("ANPR", display_frame)
            if cv2.waitKey(1) & 0xFF == 27:
                break

    cap.release()
    conn.close()
    if SHOW_WINDOW:
        cv2.destroyAllWindows()
    print("[INFO] Processing finished.")


if __name__ == "__main__":
    main()
