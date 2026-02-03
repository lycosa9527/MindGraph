"""
Database Migration: Create devices table for ESP32 Smart Response watches
Run: python esp32/backend/migrations/create_devices_table.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from sqlalchemy import text, inspect
from config.database import get_db

def create_devices_table():
    """Create devices table if it doesn't exist"""
    with next(get_db()) as db:
        inspector = inspect(db.bind)
        tables = inspector.get_table_names()
        
        if 'devices' in tables:
            print("devices table already exists")
            return
        
        try:
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    watch_id VARCHAR(255) UNIQUE NOT NULL,
                    mac_address VARCHAR(255) UNIQUE,
                    student_id INTEGER,
                    status VARCHAR(50) DEFAULT 'unassigned',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_seen DATETIME,
                    FOREIGN KEY (student_id) REFERENCES users(id)
                )
            """))
            
            db.execute(text("CREATE INDEX IF NOT EXISTS idx_devices_watch_id ON devices(watch_id)"))
            db.execute(text("CREATE INDEX IF NOT EXISTS idx_devices_student_id ON devices(student_id)"))
            db.execute(text("CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status)"))
            
            db.commit()
            print("devices table created successfully")
            
        except Exception as e:
            db.rollback()
            print(f"Migration failed: {e}")
            raise

if __name__ == "__main__":
    create_devices_table()