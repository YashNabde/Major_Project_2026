import sqlite3

# Connect to the database (or create it if not exists)
conn = sqlite3.connect("plates.db")
cursor = conn.cursor()

# Create the BlacklistedPlates table if it doesn't exist
cursor.execute("""
CREATE TABLE IF NOT EXISTS BlacklistedPlates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plate_number TEXT UNIQUE,
    reason TEXT,
    date_added TEXT
)
""")

# Add sample blacklisted plates
blacklist_data = [
    ("MH12AB1234", "Unauthorized Entry", "2025-03-25"),
    ("DL10CD5678", "Expired Permit", "2025-03-20"),
    ("KA18EQ0001", "Security Threat", "2025-03-18"),
]

cursor.executemany("INSERT OR IGNORE INTO BlacklistedPlates (plate_number, reason, date_added) VALUES (?, ?, ?)", blacklist_data)
conn.commit()
conn.close()

print("✅ Blacklisted plates database created and populated successfully!")
