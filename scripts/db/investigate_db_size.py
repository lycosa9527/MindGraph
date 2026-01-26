"""
Investigate why SQLite database is so large.
"""
import sqlite3
from pathlib import Path


def investigate():
    """Investigate database size."""
    db_path = Path("data/mindgraph.db")
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Get page info
    cursor.execute("PRAGMA page_count")
    pages = cursor.fetchone()[0]
    cursor.execute("PRAGMA page_size")
    page_size = cursor.fetchone()[0]
    total_size = pages * page_size
    
    print(f"Total database size: {total_size / (1024*1024):.2f} MB")
    print(f"Pages: {pages:,}, Page size: {page_size:,} bytes\n")
    
    # Check document_chunks actual data
    cursor.execute("SELECT SUM(LENGTH(text)) FROM document_chunks")
    text_size = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT SUM(LENGTH(COALESCE(meta_data, ''))) FROM document_chunks")
    meta_size = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(*) FROM document_chunks")
    row_count = cursor.fetchone()[0]
    
    data_size = text_size + meta_size
    print(f"document_chunks:")
    print(f"  Rows: {row_count:,}")
    print(f"  Text data: {text_size / (1024*1024):.2f} MB")
    print(f"  Metadata: {meta_size / (1024*1024):.2f} MB")
    print(f"  Total data: {data_size / (1024*1024):.2f} MB")
    print(f"  Efficiency: {(data_size / total_size * 100):.4f}%")
    print()
    
    # Check if there's a lot of empty space
    cursor.execute("PRAGMA freelist_count")
    freelist = cursor.fetchone()[0]
    print(f"Free pages: {freelist:,} ({freelist * page_size / (1024*1024):.2f} MB)")
    print()
    
    # Check other large tables
    print("Other tables:")
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    
    for table in ['embeddings', 'token_usage']:
        if table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            
            # Get size
            cursor.execute(f"PRAGMA table_info({table})")
            cols = cursor.fetchall()
            col_names = [col[1] for col in cols]
            
            size_parts = []
            for col_name in col_names:
                size_parts.append(f"COALESCE(LENGTH({col_name}), 0)")
            
            if size_parts:
                size_query = f"SELECT SUM({' + '.join(size_parts)}) FROM {table}"
                cursor.execute(size_query)
                size = cursor.fetchone()[0] or 0
                print(f"  {table}: {count:,} rows, {size / (1024*1024):.2f} MB")
    
    # The mystery: why is the DB so large?
    print(f"\n{'='*80}")
    print("ANALYSIS:")
    print(f"{'='*80}")
    print(f"Database file: {total_size / (1024*1024):.2f} MB")
    print(f"Actual data (document_chunks): {data_size / (1024*1024):.2f} MB")
    print(f"Difference: {(total_size - data_size) / (1024*1024):.2f} MB")
    print()
    print("Possible causes:")
    print("1. SQLite page overhead and fragmentation")
    print("2. Indexes taking up space (100+ indexes found)")
    print("3. FTS5 full-text search index")
    print("4. Database was created with large initial size or has fragmentation")
    print()
    print("SOLUTION: Run VACUUM to rebuild the database and reclaim space.")
    print("This will rebuild the database file and should reduce size significantly.")
    
    conn.close()


if __name__ == "__main__":
    investigate()
