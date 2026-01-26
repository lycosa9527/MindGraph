"""
Clean Old Diagram IDs Script
==============================

Removes old diagram records that have integer IDs instead of UUID strings.
This is needed after migrating from integer to UUID-based diagram IDs.

Usage:
    python scripts/clean_old_diagram_ids.py

Author: MindSpring Team
"""

import sys
import os
import io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Fix Windows console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def find_database():
    from pathlib import Path
    """Find the SQLite database file."""
    # Check data folder first (recommended location)
    data_db = Path("data/mindgraph.db")
    if data_db.exists():
        return data_db

    # Check root folder (old location)
    root_db = Path("mindgraph.db")
    if root_db.exists():
        return root_db

    # Check from environment
    db_url = os.getenv("DATABASE_URL", "")
    if "sqlite" in db_url:
        if db_url.startswith("sqlite:///./"):
            return Path(db_url.replace("sqlite:///./", ""))
        elif db_url.startswith("sqlite:///"):
            return Path(db_url.replace("sqlite:///", ""))

    return None


def clean_old_diagram_ids():
    from sqlalchemy import create_engine, text
    """Delete diagram records with non-UUID IDs."""
    db_path = find_database()

    if not db_path or not db_path.exists():
        print("Database not found. Checked: data/mindgraph.db, mindgraph.db")
        return False

    print(f"Found database: {db_path}")

    engine = create_engine(f"sqlite:///{db_path}")

    with engine.connect() as conn:
        # First, let's see what we have
        result = conn.execute(text("SELECT id, title, user_id FROM diagrams"))
        rows = result.fetchall()

        if not rows:
            print("No diagrams found in database.")
            return True

        print(f"\nFound {len(rows)} diagram(s) in database:")

        old_ids = []
        uuid_ids = []

        for row in rows:
            diagram_id = str(row[0])
            title = row[1]
            user_id = row[2]

            # Check if it's a valid UUID (36 chars with 4 dashes)
            is_uuid = len(diagram_id) == 36 and diagram_id.count('-') == 4

            if is_uuid:
                uuid_ids.append(diagram_id)
                print(f"  [OK] UUID: {diagram_id} - '{title}' (user {user_id})")
            else:
                old_ids.append(diagram_id)
                print(f"  [OLD] Integer ID: {diagram_id} - '{title}' (user {user_id})")

        if not old_ids:
            print("\nNo old integer IDs found. Database is clean.")
            return True

        print(f"\nFound {len(old_ids)} record(s) with old integer IDs to delete.")
        print(f"Keeping {len(uuid_ids)} record(s) with valid UUIDs.")

        # Delete old records
        for old_id in old_ids:
            conn.execute(text("DELETE FROM diagrams WHERE id = :id"), {"id": old_id})
            print(f"  Deleted diagram with ID: {old_id}")

        conn.commit()
        print(f"\nSuccessfully cleaned {len(old_ids)} old diagram record(s).")

    return True


if __name__ == "__main__":
    print("=" * 60)
    print("Cleaning Old Diagram IDs (Integer -> UUID Migration)")
    print("=" * 60)

    success = clean_old_diagram_ids()

    if success:
        print("\nDone. The database is now clean.")
    else:
        print("\nFailed to clean database.")
        sys.exit(1)
