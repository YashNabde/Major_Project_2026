# scripts/init_db.py

import os
import sqlite3
from datetime import datetime
import sys

# Allow running from project root: python scripts/init_db.py
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

from config import DB_PATH

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Vehicles table
    c.execute("""
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_number TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'allowed',  -- allowed, blacklisted, visitor
            owner_name TEXT,
            remarks TEXT
        );
    """)

    # Logs table
    c.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_number TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            direction TEXT NOT NULL,         -- entry / exit
            camera_id TEXT,
            detection_conf REAL,
            ocr_conf REAL,
            image_path TEXT,
            decision TEXT NOT NULL           -- allowed, blocked, manual
        );
    """)

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")

if __name__ == "__main__":
    init_db()
