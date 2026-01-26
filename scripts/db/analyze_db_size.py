"""
Analyze SQLite database size by table.

This script helps identify which tables are consuming the most space.
"""
import os
import sys
from pathlib import Path
from sqlalchemy import text, inspect

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.database import DATABASE_URL, engine


def get_table_sizes():
    """Get size information for each table."""
    if "sqlite" not in DATABASE_URL:
        print("This script only works with SQLite databases")
        return

    # Extract database file path
    db_url = DATABASE_URL
    if db_url.startswith("sqlite:////"):
        db_path = Path(db_url.replace("sqlite:////", "/"))
    elif db_url.startswith("sqlite:///"):
        db_path_str = db_url.replace("sqlite:///", "")
        if db_path_str.startswith("./"):
            db_path_str = db_path_str[2:]
        if not os.path.isabs(db_path_str):
            db_path = Path.cwd() / db_path_str
        else:
            db_path = Path(db_path_str)
    else:
        db_path = Path(db_url.replace("sqlite:///", ""))

    if not db_path.exists():
        print(f"Database file not found: {db_path}")
        return

    db_size_mb = db_path.stat().st_size / (1024 * 1024)
    print(f"\n{'='*80}")
    print(f"Database: {db_path}")
    print(f"Total Size: {db_size_mb:.2f} MB")
    print(f"{'='*80}\n")

    # Get all tables
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    results = []

    with engine.connect() as conn:
        for table in sorted(tables):
            try:
                # Get row count
                count_result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                row_count = count_result.scalar()

                # Get column info to understand data types
                columns = inspector.get_columns(table)
                text_columns = [c['name'] for c in columns if 'TEXT' in str(c['type']).upper()]
                blob_columns = [
                    c['name'] for c in columns
                    if 'BLOB' in str(c['type']).upper() or 'LARGEBINARY' in str(c['type']).upper()
                ]

                # Calculate size by summing actual column sizes
                estimated_size = 0
                if row_count > 0:
                    # Sum lengths of all columns
                    size_parts = []
                    for col in columns:
                        col_name = col['name']
                        size_parts.append(f"COALESCE(LENGTH({col_name}), 0)")
                    if size_parts:
                        size_query = f"SELECT SUM({' + '.join(size_parts)}) as total_size FROM {table}"
                        try:
                            size_result = conn.execute(text(size_query))
                            size_row = size_result.fetchone()
                            estimated_size = size_row[0] if size_row and size_row[0] is not None else 0
                        except Exception:
                            # Fallback: estimate based on row count and column types
                            estimated_size = row_count * 100  # Rough estimate

                results.append({
                    'table': table,
                    'row_count': row_count,
                    'estimated_size_mb': estimated_size / (1024 * 1024),
                    'text_columns': text_columns,
                    'blob_columns': blob_columns
                })

            except Exception as e:
                print(f"Error analyzing table {table}: {e}")
                results.append({
                    'table': table,
                    'row_count': 0,
                    'estimated_size_mb': 0,
                    'text_columns': [],
                    'blob_columns': [],
                    'error': str(e)
                })

    # Sort by estimated size
    results.sort(key=lambda x: x['estimated_size_mb'], reverse=True)

    print(f"{'Table Name':<40} {'Rows':<15} {'Est. Size (MB)':<20} {'Large Columns':<30}")
    print("-" * 105)

    total_estimated = 0
    for r in results:
        if 'error' in r:
            print(f"{r['table']:<40} {'ERROR':<15} {'-':<20} {r['error']:<30}")
        else:
            total_estimated += r['estimated_size_mb']
            large_cols = []
            if r['text_columns']:
                large_cols.extend(r['text_columns'])
            if r['blob_columns']:
                large_cols.extend(r['blob_columns'])
            large_cols_str = ', '.join(large_cols[:3]) + ('...' if len(large_cols) > 3 else '')

            print(f"{r['table']:<40} {r['row_count']:<15} {r['estimated_size_mb']:<20.2f} {large_cols_str:<30}")

    print("-" * 105)
    print(f"{'Total Estimated':<40} {'-':<15} {total_estimated:<20.2f}")
    print("\nNote: Estimated sizes are approximate. Actual sizes may vary.")
    # Now get more detailed info for large tables
    print(f"\n{'='*80}")
    print("Detailed Analysis of Large Tables")
    print(f"{'='*80}\n")

    with engine.connect() as conn:
        for r in results[:10]:  # Top 10 tables
            if r['row_count'] == 0 or 'error' in r:
                continue

            table = r['table']
            print(f"\nTable: {table}")
            print(f"  Rows: {r['row_count']:,}")
            print(f"  Estimated Size: {r['estimated_size_mb']:.2f} MB")

            # Get actual column sizes for TEXT/BLOB columns
            if r['text_columns'] or r['blob_columns']:
                print("  Analyzing large columns...")
                for col in r['text_columns'] + r['blob_columns']:
                    try:
                        # Get average and max size for this column
                        size_query = f"""
                        SELECT 
                            AVG(LENGTH({col})) as avg_size,
                            MAX(LENGTH({col})) as max_size,
                            SUM(LENGTH({col})) as total_size
                        FROM {table}
                        WHERE {col} IS NOT NULL
                        """
                        size_result = conn.execute(text(size_query))
                        size_row = size_result.fetchone()
                        if size_row and size_row[0] is not None:
                            avg_size = size_row[0] or 0
                            max_size = size_row[1] or 0
                            total_size = size_row[2] or 0
                            print(f"    {col}:")
                            print(f"      Total: {total_size / (1024*1024):.2f} MB")
                            print(f"      Avg per row: {avg_size / 1024:.2f} KB")
                            print(f"      Max: {max_size / 1024:.2f} KB")
                    except Exception as e:
                        print(f"    {col}: Error - {e}")


if __name__ == "__main__":
    get_table_sizes()
