# config.py

import os

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(BASE_DIR, "db", "anpr.db")

# YOLO model weights (after training)
MODEL_PATH = os.path.join(BASE_DIR, "models", "yolov8n-plates.pt")

# Dataset config for training
DATA_YAML = os.path.join(BASE_DIR, "datasets", "plates", "data.yaml")

# Snapshots directory (vehicle snapshot at detection time)
SNAPSHOT_DIR = os.path.join(BASE_DIR, "snapshots")
os.makedirs(SNAPSHOT_DIR, exist_ok=True)

# Detection / OCR thresholds
DETECTION_CONFIDENCE = 0.25      # was 0.5
IOU_THRESHOLD = 0.4              # was 0.5
OCR_MIN_TEXT_LENGTH = 5          # was 6
OCR_CONFIDENCE_THRESHOLD = 0.4   # was 0.5
                  # was 5 (process more frames)
  # Min avg OCR confidence

# Frame handling
FRAME_SKIP = 3        # Process every Nth frame to save compute
COOLDOWN_SECONDS = 20   # Ignore re-detections of same plate within this time

# Camera info: we don't infer direction; you set it per camera
CAMERA_ID = "gate_cam_1"
CAMERA_MODE = "entry"   # or "exit"

# For demo: hardware hooks (you will replace with GPIO / relay code)
def trigger_gate_open(plate):
    print(f"[GATE] OPEN for {plate}")

def trigger_gate_block(plate):
    print(f"[GATE] BLOCK for {plate}")
