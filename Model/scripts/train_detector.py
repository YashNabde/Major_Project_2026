import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

from ultralytics import YOLO
from config import DATA_YAML, MODEL_PATH

def train():
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)

    # Start from YOLOv8n base model
    model = YOLO("yolov8n.pt")  # downloaded automatically by ultralytics

    model.train(
        data=DATA_YAML,
        epochs=15,
        imgsz=640,
        batch=8,
        name="anpr-plates",
        exist_ok=True
    )

    # Get best weights
    runs_dir = os.path.join(ROOT_DIR, "runs", "detect", "anpr-plates")
    best_ckpt = os.path.join(runs_dir, "weights", "best.pt")
    if os.path.exists(best_ckpt):
        import shutil
        shutil.copy(best_ckpt, MODEL_PATH)
        print(f"Copied best model to {MODEL_PATH}")
    else:
        print("Training done, but couldn't find best.pt")

if __name__ == "__main__":
    train()
