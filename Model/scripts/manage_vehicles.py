# scripts/manage_vehicles.py

import os
import sqlite3
import argparse
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

from config import DB_PATH

def connect():
    return sqlite3.connect(DB_PATH)

def add_vehicle(plate, status="allowed", owner_name=None, remarks=None):
    conn = connect()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO vehicles (plate_number, status, owner_name, remarks)
            VALUES (?, ?, ?, ?)
        """, (plate, status, owner_name, remarks))
        conn.commit()
        print(f"Added vehicle {plate} with status={status}")
    except sqlite3.IntegrityError:
        print(f"Vehicle {plate} already exists. Use --update-status to modify.")
    finally:
        conn.close()

def update_status(plate, status):
    conn = connect()
    c = conn.cursor()
    c.execute("UPDATE vehicles SET status=? WHERE plate_number=?", (status, plate))
    if c.rowcount == 0:
        print(f"No vehicle found with plate {plate}")
    else:
        conn.commit()
        print(f"Updated {plate} to status={status}")
    conn.close()

def list_vehicles():
    conn = connect()
    c = conn.cursor()
    c.execute("SELECT plate_number, status, owner_name, remarks FROM vehicles ORDER BY plate_number;")
    rows = c.fetchall()
    conn.close()
    if not rows:
        print("No vehicles in database.")
        return
    for r in rows:
        print(f"{r[0]:<12} | {r[1]:<10} | {r[2] or ''} | {r[3] or ''}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage vehicles (whitelist/blacklist).")
    subparsers = parser.add_subparsers(dest="cmd")

    p_add = subparsers.add_parser("add", help="Add a vehicle")
    p_add.add_argument("plate")
    p_add.add_argument("--status", default="allowed", choices=["allowed", "blacklisted", "visitor"])
    p_add.add_argument("--owner_name")
    p_add.add_argument("--remarks")

    p_upd = subparsers.add_parser("update-status", help="Update vehicle status")
    p_upd.add_argument("plate")
    p_upd.add_argument("status", choices=["allowed", "blacklisted", "visitor"])

    p_list = subparsers.add_parser("list", help="List all vehicles")

    args = parser.parse_args()

    if args.cmd == "add":
        add_vehicle(args.plate.upper(), args.status, args.owner_name, args.remarks)
    elif args.cmd == "update-status":
        update_status(args.plate.upper(), args.status)
    elif args.cmd == "list":
        list_vehicles()
    else:
        parser.print_help()
