import sqlite3

# Connect to the database
conn = sqlite3.connect("plates.db")
cursor = conn.cursor()

# Delete all records from both tables
cursor.execute("DELETE FROM Plates")
cursor.execute("DELETE FROM BlacklistedPlates")

# Reset auto-increment IDs (optional)
cursor.execute("DELETE FROM sqlite_sequence WHERE name='Plates'")
cursor.execute("DELETE FROM sqlite_sequence WHERE name='BlacklistedPlates'")

# Commit and close
conn.commit()
conn.close()

print("✅ Database cleared successfully!")
