import os
import sqlite3
from datetime import datetime

# Database path
DB_PATH = "data/store.db"

def initialize_database():
    """Initialize the SQLite database with appointments table if it doesn't exist."""
    # Create data directory if it doesn't exist
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    # Remove existing database if it exists
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing database at {DB_PATH}")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create appointments table with user_id field
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS appointments (
        id TEXT PRIMARY KEY,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        doctor TEXT NOT NULL,
        available BOOLEAN NOT NULL DEFAULT 1,
        user_id TEXT DEFAULT NULL
    )
    ''')
    
    # Create personal calendar table for storing personal events
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS personal_calendar (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        all_day BOOLEAN DEFAULT 0,
        start_time TEXT,
        end_time TEXT,
        location TEXT,
        details TEXT,
        event_type TEXT NOT NULL
    )
    ''')
    
    conn.commit()
    print("Created database tables successfully")
    
    # Sample appointment data
    appointments = [
        ("slot1", "2025-10-03", "09:00 AM", "Dr. Smith", 0, None),
        ("slot2", "2025-10-03", "10:30 AM", "Dr. Smith", 0, None),
        ("slot3", "2025-10-03", "02:00 PM", "Dr. Johnson", 1, None),
        ("slot4", "2025-10-04", "11:00 AM", "Dr. Williams", 1, None),
        ("slot5", "2025-10-04", "03:30 PM", "Dr. Davis", 1, None),
        ("slot6", "2025-10-05", "01:00 PM", "Dr. Wilson", 1, None),
        ("slot7", "2025-10-03", "09:00 AM", "Dr. Johnson", 1, None),
        ("slot8", "2025-10-03", "11:30 AM", "Dr. Johnson", 1, None),
        ("slot9", "2025-10-04", "10:00 AM", "Dr. Johnson", 1, None),
        ("slot10", "2025-10-05", "02:30 PM", "Dr. Johnson", 1, None),
        ("slot11", "2025-10-03", "08:30 AM", "Dr. Williams", 1, None),
        ("slot12", "2025-10-04", "01:30 PM", "Dr. Williams", 1, None),
        ("slot13", "2025-10-05", "09:30 AM", "Dr. Williams", 1, None),
        ("slot14", "2025-10-05", "03:00 PM", "Dr. Williams", 1, None),
        ("slot15", "2025-10-03", "04:00 PM", "Dr. Davis", 1, None),
        ("slot16", "2025-10-04", "09:30 AM", "Dr. Davis", 1, None),
        ("slot17", "2025-10-04", "11:00 AM", "Dr. Davis", 1, None),
        ("slot18", "2025-10-04", "04:30 PM", "Dr. Davis", 1, None),
        ("slot19", "2025-10-05", "10:30 AM", "Dr. Davis", 1, None),
        ("slot20", "2025-10-03", "01:00 PM", "Dr. Wilson", 1, None),
        ("slot21", "2025-10-03", "02:30 PM", "Dr. Wilson", 1, None),
        ("slot22", "2025-10-04", "10:30 AM", "Dr. Wilson", 1, None),
        ("slot23", "2025-10-05", "09:00 AM", "Dr. Wilson", 1, None)
    ]
    
    cursor.executemany(
        "INSERT INTO appointments (id, date, time, doctor, available, user_id) VALUES (?, ?, ?, ?, ?, ?)",
        appointments
    )
    
    # Sample personal calendar events
    calendar_events = [
        # Italy trip for 10 days
        ("event1", "Paris Vacation", "2025-05-25", "2025-06-04", 1, None, None, 
         "Paris", "10-day vacation in Paris", "vacation"),

         # New Zealand trip for 4 days
        ("event2", "NZ Vacation", "2025-04-01", "2025-04-05", 1, None, None, 
         "New Zealand", "4-day vacation touring Queenstown", "vacation"),
        
        # Past doctor appointment
        ("event3", "Checkup with Dr. Smith", "2024-03-11", "2024-03-11", 0, "02:00 PM", "03:00 PM", 
         "Sunshine Medical Clinic", "Annual physical examination", "medical"),
        
        # Upcoming appointments
        ("event4", "Dental Cleaning", "2025-06-10", "2025-06-10", 0, "05:00 PM", "05:30 PM", 
         "Bright Smile Dental", "Regular teeth cleaning and checkup", "medical"),
        
        ("event5", "Brunch with family", "2025-06-10", "2025-06-10", 0, "10:00 AM", "11:00 AM", 
         "The Brunch Club", "Monthly brunch with family", "personal")
    ]
    
    cursor.executemany(
        "INSERT INTO personal_calendar (id, title, start_date, end_date, all_day, start_time, end_time, location, details, event_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        calendar_events
    )
    
    conn.commit()
    print("Added sample data to database")
    
    # Verify the data
    cursor.execute("SELECT COUNT(*) FROM appointments")
    appt_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM personal_calendar")
    calendar_count = cursor.fetchone()[0]
    
    print(f"Database contains {appt_count} appointment slots and {calendar_count} calendar events")
    
    conn.close()

if __name__ == "__main__":
    initialize_database()
    print("Database initialization complete") 