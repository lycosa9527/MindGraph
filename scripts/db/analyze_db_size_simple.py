"""
Simple SQLite database size analyzer using sqlite3 directly.
"""
import sqlite3
import os
from pathlib import Path


def find_database_file():
    """Find the SQLite database file."""
    # Check common locations
    possible_paths = [
        Path("data/mindgraph.db"),
        Path("mindgraph.db"),
        Path.cwd() / "data" / "mindgraph.db",
        Path.cwd() / "mindgraph.db",
    ]

    # Also check environment variable
    db_url = os.getenv("DATABASE_URL", "")
    if db_url and "sqlite" in db_url:
        if db_url.startswith("sqlite:////"):
            possible_paths.insert(0, Path(db_url.replace("sqlite:////", "/")))
        elif db_url.startswith("sqlite:///"):
            db_path_str = db_url.replace("sqlite:///", "")
            if db_path_str.startswith("./"):
                db_path_str = db_path_str[2:]
            if not os.path.isabs(db_path_str):
                possible_paths.insert(0, Path.cwd() / db_path_str)
            else:
                possible_paths.insert(0, Path(db_path_str))

    for path in possible_paths:
        if path.exists():
            return path

    return None


def analyze_database(database_path: Path):
    """Analyze database size."""
    if not database_path.exists():
        print(f"Database file not found: {database_path}")
        return

    db_size_mb = database_path.stat().st_size / (1024 * 1024)
    print(f"\n{'='*80}")
    print(f"Database: {database_path}")
    print(f"Total Size: {db_size_mb:.2f} MB")
    print(f"{'='*80}\n")

    conn = sqlite3.connect(str(database_path))
    conn.row_factory = sqlite3.Row

    try:
        # Get all tables
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]

        results = []

        for table in tables:
            try:
                # Get row count
                cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                row_count = cursor.fetchone()['count']

                # Get column info
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()

                text_columns = []
                blob_columns = []
                all_columns = []

                for col in columns:
                    col_name = col[1]  # Column name is at index 1
                    col_type = col[2].upper()  # Column type is at index 2
                    all_columns.append(col_name)
                    if 'TEXT' in col_type:
                        text_columns.append(col_name)
                    if 'BLOB' in col_type:
                        blob_columns.append(col_name)

                # Calculate size by summing column lengths
                estimated_size = 0
                if row_count > 0 and all_columns:
                    size_parts = []
                    for col_name in all_columns:
                        size_parts.append(f"COALESCE(LENGTH({col_name}), 0)")

                    size_query = f"SELECT SUM({' + '.join(size_parts)}) as total_size FROM {table}"
                    cursor.execute(size_query)
                    result = cursor.fetchone()
                    if result and result[0] is not None:
                        estimated_size = result[0]

                results.append({
                    'table': table,
                    'row_count': row_count,
                    'estimated_size_mb': estimated_size / (1024 * 1024),
                    'text_columns': text_columns,
                    'blob_columns': blob_columns,
                    'all_columns': all_columns
                })

            except Exception as e:
                print(f"Error analyzing table {table}: {e}")
                results.append({
                    'table': table,
                    'row_count': 0,
                    'estimated_size_mb': 0,
                    'text_columns': [],
                    'blob_columns': [],
                    'all_columns': [],
                    'error': str(e)
                })

        # Sort by size
        results.sort(key=lambda x: x['estimated_size_mb'], reverse=True)

        # Print summary
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

        # Detailed analysis for top tables
        print(f"\n{'='*80}")
        print("Detailed Analysis of Large Tables")
        print(f"{'='*80}\n")

        for r in results[:10]:  # Top 10 tables
            if r['row_count'] == 0 or 'error' in r:
                continue

            table = r['table']
            print(f"\nTable: {table}")
            print(f"  Rows: {r['row_count']:,}")
            print(f"  Estimated Size: {r['estimated_size_mb']:.2f} MB")

            # Analyze large columns
            large_cols = r['text_columns'] + r['blob_columns']
            if large_cols:
                print("  Analyzing large columns...")
                for col in large_cols:
                    try:
                        size_query = f"""
                        SELECT
                            AVG(LENGTH({col})) as avg_size,
                            MAX(LENGTH({col})) as max_size,
                            SUM(LENGTH({col})) as total_size,
                            COUNT(*) as non_null_count
                        FROM {table}
                        WHERE {col} IS NOT NULL
                        """
                        cursor.execute(size_query)
                        size_row = cursor.fetchone()
                        if size_row and size_row['total_size'] is not None:
                            total_size_mb = size_row['total_size'] / (1024 * 1024)
                            avg_size_kb = (size_row['avg_size'] or 0) / 1024
                            max_size_kb = (size_row['max_size'] or 0) / 1024
                            non_null_count = size_row['non_null_count'] or 0

                            print(f"    {col}:")
                            print(f"      Total: {total_size_mb:.2f} MB ({non_null_count:,} non-null values)")
                            if avg_size_kb > 0:
                                print(f"      Avg per row: {avg_size_kb:.2f} KB")
                            if max_size_kb > 0:
                                print(f"      Max: {max_size_kb:.2f} KB")
                    except Exception as e:
                        print(f"    {col}: Error - {e}")

        # Check WAL file size
        wal_path = Path(str(database_path) + "-wal")
        shm_path = Path(str(database_path) + "-shm")

        if wal_path.exists():
            wal_size_mb = wal_path.stat().st_size / (1024 * 1024)
            print(f"\n{'='*80}")
            print(f"WAL File: {wal_path}")
            print(f"WAL Size: {wal_size_mb:.2f} MB")
            print(f"{'='*80}")
            if wal_size_mb > 10:
                print("\n⚠️  WARNING: WAL file is large!")
                print("   Consider running: PRAGMA wal_checkpoint(TRUNCATE);")
                print("   Or restart the application to checkpoint the WAL.")

        if shm_path.exists():
            shm_size_mb = shm_path.stat().st_size / (1024 * 1024)
            print(f"\nSHM File: {shm_path}")
            print(f"SHM Size: {shm_size_mb:.2f} MB")

    finally:
        conn.close()


if __name__ == "__main__":
    db_path = find_database_file()
    if db_path:
        analyze_database(db_path)
    else:
        print("Could not find SQLite database file.")
        print("Checked locations:")
        print("  - data/mindgraph.db")
        print("  - mindgraph.db")
        print("  - DATABASE_URL environment variable")
