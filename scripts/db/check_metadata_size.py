"""
Check what's in the meta_data column that's making it so large.
"""
import sqlite3
import json
from pathlib import Path


def check_metadata():
    """Check metadata content."""
    db_path = Path("data/mindgraph.db")
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Sample some rows to see what's in meta_data
    cursor.execute("""
        SELECT 
            id,
            LENGTH(meta_data) as meta_size,
            LENGTH(text) as text_size,
            meta_data
        FROM document_chunks
        WHERE meta_data IS NOT NULL
        ORDER BY LENGTH(meta_data) DESC
        LIMIT 10
    """)
    
    print("Top 10 document_chunks by meta_data size:\n")
    print(f"{'ID':<10} {'Meta Size (KB)':<20} {'Text Size (KB)':<20} {'Meta Preview':<50}")
    print("-" * 100)
    
    total_meta = 0
    total_text = 0
    
    for row in cursor.fetchall():
        chunk_id, meta_size, text_size, meta_data = row
        total_meta += meta_size
        total_text += text_size
        
        # Try to parse JSON and see what's in it
        try:
            meta_json = json.loads(meta_data)
            preview = str(meta_json)[:100] + "..." if len(str(meta_json)) > 100 else str(meta_json)
        except:
            preview = str(meta_data)[:100] + "..." if len(str(meta_data)) > 100 else str(meta_data)
        
        print(f"{chunk_id:<10} {meta_size/1024:<20.2f} {text_size/1024:<20.2f} {preview:<50}")
    
    print("-" * 100)
    print(f"\nTotal meta_data size: {total_meta / (1024*1024):.2f} MB")
    print(f"Total text size: {total_text / (1024*1024):.2f} MB")
    
    # Get statistics
    cursor.execute("""
        SELECT 
            AVG(LENGTH(meta_data)) as avg_meta_size,
            MAX(LENGTH(meta_data)) as max_meta_size,
            MIN(LENGTH(meta_data)) as min_meta_size,
            COUNT(*) as count_with_meta
        FROM document_chunks
        WHERE meta_data IS NOT NULL
    """)
    
    stats = cursor.fetchone()
    print(f"\nStatistics:")
    print(f"  Rows with meta_data: {stats[3]:,}")
    print(f"  Avg meta_data size: {stats[0] / 1024:.2f} KB")
    print(f"  Max meta_data size: {stats[1] / 1024:.2f} KB")
    print(f"  Min meta_data size: {stats[2] / 1024:.2f} KB")
    
    # Check what keys are in the metadata
    cursor.execute("SELECT meta_data FROM document_chunks WHERE meta_data IS NOT NULL LIMIT 100")
    all_keys = set()
    for row in cursor.fetchall():
        try:
            meta_json = json.loads(row[0])
            if isinstance(meta_json, dict):
                all_keys.update(meta_json.keys())
        except:
            pass
    
    print(f"\nCommon keys in meta_data: {', '.join(sorted(all_keys))}")
    
    # Check if there's a specific key that's very large
    if 'embedding' in all_keys or 'embeddings' in all_keys:
        print("\n⚠️  WARNING: Found 'embedding' or 'embeddings' key in meta_data!")
        print("   Embeddings should NOT be stored in document_chunks meta_data.")
        print("   They should be in the 'embeddings' table or Qdrant.")
    
    conn.close()


if __name__ == "__main__":
    check_metadata()
