import cv2
import pytesseract
import sqlite3
import time
import re  # For plate format validation

# Database connection
conn = sqlite3.connect("plates.db")
cursor = conn.cursor()

# Create tables if they don’t exist
cursor.execute("CREATE TABLE IF NOT EXISTS Plates (id INTEGER PRIMARY KEY, plate_number TEXT UNIQUE, image_path TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS BlacklistedPlates (id INTEGER PRIMARY KEY, plate_number TEXT UNIQUE)")
conn.commit()

# Load number plate detector
plate_cascade = cv2.CascadeClassifier("haarcascade_russian_plate_number.xml")

# Configure Tesseract OCR
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Track detected plates to avoid duplicate detections within a short time
last_detected_plates = {}
detection_cooldown = 5  # Ignore repeated detections of the same plate for 5 seconds

# Function to check if a plate is blacklisted
def is_blacklisted(plate_text):
    cursor.execute("SELECT * FROM BlacklistedPlates WHERE plate_number=?", (plate_text,))
    return cursor.fetchone() is not None  # Returns True if plate is blacklisted

# Function to validate if the detected text is a proper number plate
def is_valid_plate(plate_text):
    plate_pattern = r'^[A-Z]{2}[0-9]{2}[A-Z]{1,2}[0-9]{4}$'  # Common Indian plate format (e.g., KA01AB1234)
    return bool(re.match(plate_pattern, plate_text))

# Function to store the clearest plate image
def save_plate(plate_text, image):
    filename = f"plate_{plate_text}.jpg"

    # Check if the plate is already in the database
    cursor.execute("SELECT * FROM Plates WHERE plate_number=?", (plate_text,))
    existing_plate = cursor.fetchone()

    if not existing_plate:
        cv2.imwrite(filename, image)  # Save the best image
        cursor.execute("INSERT INTO Plates (plate_number, image_path) VALUES (?, ?)", (plate_text, filename))
        conn.commit()
        print(f"✅ Plate {plate_text} stored in database!")
    else:
        print(f"⚠️ Plate {plate_text} is already in the database, skipping storage.")

# Start video capture
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        print("❌ Failed to capture image")
        break

    # Convert to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Detect plates in frame
    plates = plate_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(30, 30))

    for (x, y, w, h) in plates:
        plate_roi = frame[y:y + h, x:x + w]

        # Preprocess image for better OCR accuracy
        plate_roi = cv2.cvtColor(plate_roi, cv2.COLOR_BGR2GRAY)
        plate_roi = cv2.GaussianBlur(plate_roi, (3, 3), 0)
        plate_roi = cv2.adaptiveThreshold(plate_roi, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

        # Get plate text (OCR)
        plate_text = pytesseract.image_to_string(plate_roi, config='--psm 7').strip()
        plate_text = "".join(plate_text.split())  # Remove spaces

        # Validate the extracted text
        if not is_valid_plate(plate_text):
            print(f"❌ Ignored invalid plate: {plate_text}")
            continue  # Skip storing invalid text

        # Avoid duplicate detections within the cooldown period
        current_time = time.time()
        if plate_text in last_detected_plates:
            if current_time - last_detected_plates[plate_text] < detection_cooldown:
                continue  # Ignore repeated detections
        last_detected_plates[plate_text] = current_time  # Update last detection time

        print(f"🚘 Detected Plate: {plate_text}")

        # Check if the plate is blacklisted
        if is_blacklisted(plate_text):
            print(f"🚨 ALERT! Blacklisted Vehicle Detected: {plate_text}")

        # Store plate
        save_plate(plate_text, plate_roi)

    # Display frame
    cv2.imshow("License Plate Detection", frame)

    # Press 'q' to exit
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
conn.close()
