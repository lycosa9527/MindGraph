"""
Remove meta_data column from document_chunks table to reduce database size.

This column was storing ~2GB of data and is not needed for core functionality.
"""
import sqlite3
import sys
from pathlib import Path
from datetime import datetime


def get_sqlite_version():
    """Get SQLite version."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("SELECT sqlite_version()")
    version_str = cursor.fetchone()[0]
    conn.close()
    
    # Parse version string (e.g., "3.35.0")
    parts = version_str.split(".")
    major = int(parts[0])
    minor = int(parts[1])
    patch = int(parts[2]) if len(parts) > 2 else 0
    
    return major, minor, patch


def backup_database(db_path: Path):
    """Create a backup of the database."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"{db_path.stem}.backup.{timestamp}{db_path.suffix}"
    
    print(f"Creating backup: {backup_path}")
    
    # Copy database file
    import shutil
    shutil.copy2(db_path, backup_path)
    
    # Also copy WAL and SHM if they exist
    wal_path = Path(str(db_path) + "-wal")
    shm_path = Path(str(db_path) + "-shm")
    
    if wal_path.exists():
        shutil.copy2(wal_path, Path(str(backup_path) + "-wal"))
    if shm_path.exists():
        shutil.copy2(shm_path, Path(str(backup_path) + "-shm"))
    
    print(f"Backup created: {backup_path}")
    return backup_path


def drop_column_sqlite35(db_path: Path):
    """Drop column using SQLite 3.35+ DROP COLUMN support."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        print("Dropping meta_data column using ALTER TABLE DROP COLUMN...")
        cursor.execute("ALTER TABLE document_chunks DROP COLUMN meta_data")
        conn.commit()
        print("✓ Column dropped successfully")
        return True
    except sqlite3.OperationalError as e:
        if "DROP COLUMN" in str(e):
            print(f"SQLite version doesn't support DROP COLUMN: {e}")
            return False
        raise
    finally:
        conn.close()


def recreate_table_without_meta_data(db_path: Path):
    """Recreate table without meta_data column (for older SQLite versions)."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        print("Recreating table without meta_data column...")
        
        # Get current table structure
        cursor.execute("PRAGMA table_info(document_chunks)")
        columns = cursor.fetchall()
        
        # Filter out meta_data column
        keep_columns = [col for col in columns if col[1] != 'meta_data']
        
        if len(keep_columns) == len(columns):
            print("meta_data column not found, nothing to do")
            return True
        
        # Create new table structure
        column_defs = []
        for col in keep_columns:
            col_name = col[1]
            col_type = col[2]
            not_null = "NOT NULL" if col[3] else ""
            default = f"DEFAULT {col[4]}" if col[4] else ""
            pk = "PRIMARY KEY" if col[5] else ""
            
            col_def = f"{col_name} {col_type} {not_null} {default} {pk}".strip()
            column_defs.append(col_def)
        
        # Create temporary table
        print("Creating temporary table...")
        cursor.execute(f"""
            CREATE TABLE document_chunks_new (
                {', '.join(column_defs)}
            )
        """)
        
        # Copy data (excluding meta_data)
        keep_col_names = [col[1] for col in keep_columns]
        col_list = ', '.join(keep_col_names)
        
        print("Copying data to temporary table...")
        cursor.execute(f"""
            INSERT INTO document_chunks_new ({col_list})
            SELECT {col_list} FROM document_chunks
        """)
        
        # Drop old table
        print("Dropping old table...")
        cursor.execute("DROP TABLE document_chunks")
        
        # Rename new table
        print("Renaming temporary table...")
        cursor.execute("ALTER TABLE document_chunks_new RENAME TO document_chunks")
        
        # Recreate indexes
        print("Recreating indexes...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS ix_document_chunks_document_id_chunk_index 
            ON document_chunks (document_id, chunk_index)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS ix_document_chunks_id 
            ON document_chunks (id)
        """)
        
        conn.commit()
        print("✓ Table recreated successfully")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"✗ Error recreating table: {e}")
        raise
    finally:
        conn.close()


def main():
    """Main migration function."""
    db_path = Path("data/mindgraph.db")
    
    if not db_path.exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)
    
    # Check current size
    db_size_mb = db_path.stat().st_size / (1024 * 1024)
    print(f"\n{'='*80}")
    print(f"Current database size: {db_size_mb:.2f} MB")
    print(f"{'='*80}\n")
    
    # Check meta_data size
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(LENGTH(COALESCE(meta_data, ''))) FROM document_chunks")
    meta_size = cursor.fetchone()[0] or 0
    conn.close()
    
    print(f"meta_data column size: {meta_size / (1024*1024):.2f} MB")
    print(f"This will be freed after migration.\n")
    
    # Confirm
    response = input("Continue with migration? (yes/no): ")
    if response.lower() != 'yes':
        print("Migration cancelled")
        sys.exit(0)
    
    # Backup
    backup_path = backup_database(db_path)
    
    try:
        # Check SQLite version
        major, minor, patch = get_sqlite_version()
        print(f"\nSQLite version: {major}.{minor}.{patch}")
        
        if major > 3 or (major == 3 and minor >= 35):
            # Use DROP COLUMN (SQLite 3.35+)
            success = drop_column_sqlite35(db_path)
            if not success:
                print("Falling back to table recreation method...")
                recreate_table_without_meta_data(db_path)
        else:
            # Recreate table (older SQLite)
            print("SQLite version < 3.35, using table recreation method...")
            recreate_table_without_meta_data(db_path)
        
        # Check new size
        new_db_size_mb = db_path.stat().st_size / (1024 * 1024)
        print(f"\n{'='*80}")
        print(f"Migration completed!")
        print(f"Old size: {db_size_mb:.2f} MB")
        print(f"New size: {new_db_size_mb:.2f} MB")
        print(f"Freed: {db_size_mb - new_db_size_mb:.2f} MB")
        print(f"{'='*80}\n")
        
        print("Note: You may need to run VACUUM to fully reclaim disk space.")
        print("Run: sqlite3 data/mindgraph.db 'VACUUM;'")
        
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        print(f"Restore from backup: {backup_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
