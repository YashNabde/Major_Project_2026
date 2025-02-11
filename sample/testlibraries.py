'''
 import sqlite3
import datetime
import cv2
import pytesseract

# Initialize SQLite database
conn = sqlite3.connect("license_plates.db")
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS plates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plate_number TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")
conn.commit()

# Load pre-trained Haar cascades for plate detection
plate_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_russian_plate_number.xml")


# Function to recognize text from license plate
def recognize_plate(plate_img):
    gray = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    plate_text = pytesseract.image_to_string(thresh, config='--psm 8')
    return plate_text.strip()


# Function to store plate in database
def store_plate(plate_text):
    cursor.execute("INSERT INTO plates (plate_number) VALUES (?)", (plate_text,))
    conn.commit()


# Open webcam
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    plates = plate_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50))

    for (x, y, w, h) in plates:
        plate_img = frame[y:y + h, x:x + w]
        plate_text = recognize_plate(plate_img)

        if plate_text:
            store_plate(plate_text)
            cv2.putText(frame, plate_text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

    cv2.imshow("License Plate Detection", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
conn.close()
'''

import cv2
import pytesseract
import sqlite3

# Create a database and table if it doesn't exist
conn = sqlite3.connect("plates.db")
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS Plates (id INTEGER PRIMARY KEY, plate_number TEXT)")
conn.commit()



# Path to Tesseract (change this if needed)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Load pre-trained number plate detector
plate_cascade = cv2.CascadeClassifier("haarcascade_russian_plate_number.xml")

# Open webcam
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        print("Failed to capture image")
        break

    # Convert to grayscale for better detection
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Detect plates in the frame
    plates = plate_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(30, 30))

    for (x, y, w, h) in plates:
        # Draw a rectangle around the detected plate
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 3)
        plate_roi = frame[y:y + h, x:x + w]  # Extract plate region

        # Read text from the detected plate
        plate_text = pytesseract.image_to_string("detected_plate.jpg", config='--psm 7')
        print("Detected Plate Number:", plate_text)


        # Function to store plate number
        def save_plate_number(plate_text):
            cursor.execute("INSERT INTO Plates (plate_number) VALUES (?)", (plate_text,))
            conn.commit()
            print("Plate number saved to database:", plate_text)


        # Example usage
        save_plate_number(plate_text)

        # Save the detected number plate image
        cv2.imwrite("detected_plate.jpg", plate_roi)

    # Display the frame
    cv2.imshow("License Plate Detection", frame)

    # Press 'q' to exit
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
