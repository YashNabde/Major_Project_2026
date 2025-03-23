from flask import Flask, render_template, request, redirect, url_for
import sqlite3

app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS plates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_number TEXT UNIQUE,
            entry_time TEXT,
            exit_time TEXT,
            status TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blacklisted (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plate_number TEXT UNIQUE
        )
    """)
    conn.commit()
    conn.close()

@app.route('/')
def dashboard():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM plates")
    logs = cursor.fetchall()
    cursor.execute("SELECT * FROM blacklisted")
    blacklisted = cursor.fetchall()
    conn.close()
    return render_template('dashboard.html', logs=logs, blacklisted=blacklisted)

@app.route('/blacklist', methods=['POST'])
def blacklist():
    plate_number = request.form['plate_number']
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO blacklisted (plate_number) VALUES (?)", (plate_number,))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/remove_blacklist/<plate_number>')
def remove_blacklist(plate_number):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM blacklisted WHERE plate_number = ?", (plate_number,))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    init_db()  # Ensures database tables exist
    app.run(debug=True)
