"""
Check SQLite index sizes and FTS5 table sizes.
"""
import sqlite3
from pathlib import Path


def check_index_sizes(db_path: Path):
    """Check index and FTS5 sizes."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    try:
        cursor = conn.cursor()
        
        # Get all indexes
        cursor.execute("""
            SELECT name, tbl_name, sql 
            FROM sqlite_master 
            WHERE type='index' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)
        indexes = cursor.fetchall()
        
        print(f"\n{'='*80}")
        print("Index Information")
        print(f"{'='*80}\n")
        
        for idx in indexes:
            print(f"Index: {idx['name']}")
            print(f"  Table: {idx['tbl_name']}")
            if idx['sql']:
                print(f"  SQL: {idx['sql'][:100]}...")
            print()
        
        # Check FTS5 tables specifically
        print(f"\n{'='*80}")
        print("FTS5 Virtual Table Sizes")
        print(f"{'='*80}\n")
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name LIKE '%fts5%'
            ORDER BY name
        """)
        fts5_tables = cursor.fetchall()
        
        for fts5_table_row in fts5_tables:
            table_name = fts5_table_row['name']
            try:
                # Get row count
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cursor.fetchone()[0]
                
                # Get size of data
                if 'data' in table_name or 'docsize' in table_name:
                    # These tables have blob columns
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = cursor.fetchall()
                    
                    blob_cols = [col[1] for col in columns if 'BLOB' in col[2].upper()]
                    if blob_cols:
                        col_name = blob_cols[0]
                        cursor.execute(f"""
                            SELECT 
                                SUM(LENGTH({col_name})) as total_size,
                                COUNT(*) as count
                            FROM {table_name}
                        """)
                        result = cursor.fetchone()
                        if result and result[0]:
                            total_size_mb = result[0] / (1024 * 1024)
                            print(f"{table_name}:")
                            print(f"  Rows: {row_count:,}")
                            print(f"  Total Size: {total_size_mb:.2f} MB")
                            print()
                else:
                    print(f"{table_name}: {row_count:,} rows")
            except Exception as e:
                print(f"{table_name}: Error - {e}")
        
        # Check document_chunks_fts5_data specifically (this is likely the culprit)
        print(f"\n{'='*80}")
        print("Detailed FTS5 Data Analysis")
        print(f"{'='*80}\n")
        
        try:
            cursor.execute("SELECT COUNT(*) FROM document_chunks_fts5_data")
            data_rows = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT 
                    SUM(LENGTH(block)) as total_block_size,
                    AVG(LENGTH(block)) as avg_block_size,
                    MAX(LENGTH(block)) as max_block_size,
                    COUNT(*) as count
                FROM document_chunks_fts5_data
            """)
            result = cursor.fetchone()
            
            if result and result[0]:
                total_mb = result[0] / (1024 * 1024)
                avg_kb = (result[1] or 0) / 1024
                max_kb = (result[2] or 0) / 1024
                
                print(f"document_chunks_fts5_data:")
                print(f"  Rows: {data_rows:,}")
                print(f"  Total block size: {total_mb:.2f} MB")
                print(f"  Avg block size: {avg_kb:.2f} KB")
                print(f"  Max block size: {max_kb:.2f} KB")
                print()
                print(f"⚠️  This FTS5 index is taking up {total_mb:.2f} MB!")
                print(f"   FTS5 indexes can be large because they store full-text search data.")
        except Exception as e:
            print(f"Error checking FTS5 data: {e}")
        
        # Check if we can estimate the actual data vs index ratio
        print(f"\n{'='*80}")
        print("Data vs Index Size Estimate")
        print(f"{'='*80}\n")
        
        # Get actual data size from document_chunks
        cursor.execute("""
            SELECT 
                SUM(LENGTH(text)) as text_size,
                SUM(LENGTH(COALESCE(meta_data, ''))) as metadata_size,
                COUNT(*) as row_count
            FROM document_chunks
        """)
        result = cursor.fetchone()
        if result:
            text_size_mb = (result[0] or 0) / (1024 * 1024)
            metadata_size_mb = (result[1] or 0) / (1024 * 1024)
            print(f"document_chunks actual data:")
            print(f"  text column: {text_size_mb:.2f} MB")
            print(f"  metadata column: {metadata_size_mb:.2f} MB")
            print(f"  Total data: {text_size_mb + metadata_size_mb:.2f} MB")
            print(f"  Rows: {result[2]:,}")
        
        # Estimate index overhead
        db_file_size_mb = db_path.stat().st_size / (1024 * 1024)
        estimated_data_mb = text_size_mb + metadata_size_mb if result else 0
        
        print(f"\nDatabase file size: {db_file_size_mb:.2f} MB")
        print(f"Estimated data size: {estimated_data_mb:.2f} MB")
        print(f"Estimated index/overhead: {db_file_size_mb - estimated_data_mb:.2f} MB")
        print(f"  ({((db_file_size_mb - estimated_data_mb) / db_file_size_mb * 100):.1f}% of total)")
        
    finally:
        conn.close()


if __name__ == "__main__":
    db_path = Path("data/mindgraph.db")
    if db_path.exists():
        check_index_sizes(db_path)
    else:
        print(f"Database not found: {db_path}")
