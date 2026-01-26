"""
Check SQLite database bloat and fragmentation.
"""
import sqlite3
from pathlib import Path


def check_bloat(db_path: Path):
    """Check database bloat."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    try:
        cursor = conn.cursor()
        
        # Get page size
        cursor.execute("PRAGMA page_size")
        page_size = cursor.fetchone()[0]
        
        # Get page count
        cursor.execute("PRAGMA page_count")
        page_count = cursor.fetchone()[0]
        
        # Get freelist count (free pages)
        cursor.execute("PRAGMA freelist_count")
        freelist_count = cursor.fetchone()[0]
        
        # Calculate sizes
        total_size = page_count * page_size
        free_size = freelist_count * page_size
        used_size = total_size - free_size
        
        print(f"\n{'='*80}")
        print("SQLite Database Bloat Analysis")
        print(f"{'='*80}\n")
        print(f"Page Size: {page_size:,} bytes")
        print(f"Total Pages: {page_count:,}")
        print(f"Free Pages: {freelist_count:,}")
        print(f"Used Pages: {page_count - freelist_count:,}")
        print(f"\nTotal Size: {total_size / (1024*1024):.2f} MB")
        print(f"Free Space: {free_size / (1024*1024):.2f} MB ({free_size/total_size*100:.1f}%)")
        print(f"Used Space: {used_size / (1024*1024):.2f} MB ({used_size/total_size*100:.1f}%)")
        
        if free_size > 100 * 1024 * 1024:  # More than 100MB free
            print(f"\n⚠️  WARNING: Database has {free_size / (1024*1024):.2f} MB of free space!")
            print("   This is likely due to deleted data that hasn't been reclaimed.")
            print("   Run VACUUM to reclaim this space.")
        
        # Check individual table sizes
        print(f"\n{'='*80}")
        print("Table Page Counts")
        print(f"{'='*80}\n")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                row_count = cursor.fetchone()[0]
                
                # Get table info
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                
                # Estimate table size
                if row_count > 0:
                    # Sample a few rows to estimate
                    cursor.execute(f"SELECT * FROM {table} LIMIT 5")
                    sample_rows = cursor.fetchall()
                    if sample_rows:
                        # Rough estimate
                        print(f"{table:<40} {row_count:>10,} rows")
            except Exception as e:
                pass
        
    finally:
        conn.close()


if __name__ == "__main__":
    db_path = Path("data/mindgraph.db")
    if db_path.exists():
        check_bloat(db_path)
    else:
        print(f"Database not found: {db_path}")
