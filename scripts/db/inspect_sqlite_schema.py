"""
Inspect SQLite database schema to check foreign key relationships.

This script helps identify schema issues that might prevent table creation during migration.
"""

import sqlite3
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.migration.sqlite_migration_utils import get_sqlite_db_path


def inspect_sqlite_schema(db_path: Path) -> None:
    """Inspect SQLite database schema and foreign key relationships."""
    if not db_path.exists():
        print(f"[ERROR] SQLite database not found at: {db_path}")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    
    print("=" * 80)
    print("SQLite Database Schema Inspection")
    print("=" * 80)
    print(f"\nDatabase: {db_path}")
    print(f"Total tables: {len(tables)}\n")
    
    # Check each table's foreign keys
    table_fks = {}
    for table_name in tables:
        # Get CREATE TABLE statement
        cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        create_sql = cursor.fetchone()
        if create_sql and create_sql[0]:
            sql_str = create_sql[0]
            
            # Extract foreign keys from CREATE TABLE statement
            fks = []
            lines = sql_str.split('\n')
            for line in lines:
                line = line.strip()
                if 'FOREIGN KEY' in line.upper() or 'REFERENCES' in line.upper():
                    # Extract referenced table
                    if 'REFERENCES' in line.upper():
                        ref_part = line.upper().split('REFERENCES')[1].strip()
                        ref_table = ref_part.split('(')[0].strip().strip('"').strip("'")
                        fks.append(ref_table)
            
            if fks:
                table_fks[table_name] = fks
    
    # Print foreign key relationships
    print("Foreign Key Relationships:")
    print("-" * 80)
    for table_name, fks in sorted(table_fks.items()):
        print(f"\n{table_name}:")
        for fk in fks:
            print(f"  -> {fk}")
    
    # Check for the failing tables specifically
    failing_tables = [
        'child_chunks', 'chunk_attachments', 'debate_judgments', 'debate_messages',
        'document_chunks', 'document_relationships', 'document_versions',
        'evaluation_results', 'query_feedback'
    ]
    
    print("\n" + "=" * 80)
    print("Failing Tables Analysis:")
    print("=" * 80)
    
    for table_name in failing_tables:
        if table_name not in tables:
            print(f"\n{table_name}: NOT FOUND in SQLite database")
            continue
        
        print(f"\n{table_name}:")
        # Get table info
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        print(f"  Columns: {len(columns)}")
        
        # Get foreign keys
        cursor.execute(f"PRAGMA foreign_key_list({table_name})")
        fks = cursor.fetchall()
        if fks:
            print("  Foreign Keys:")
            for fk in fks:
                # fk structure: (id, seq, table, from, to, on_update, on_delete, match)
                ref_table = fk[2]
                from_col = fk[3]
                to_col = fk[4]
                print(f"    {from_col} -> {ref_table}.{to_col}")
        else:
            print("  No foreign keys found")
        
        # Check if parent tables exist
        if table_name in table_fks:
            print("  Parent tables (from CREATE TABLE):")
            for parent in table_fks[table_name]:
                exists = parent in tables
                status = "✓ EXISTS" if exists else "✗ MISSING"
                print(f"    {parent} {status}")
    
    conn.close()


def main():
    """Main entry point."""
    sqlite_path = get_sqlite_db_path()
    if not sqlite_path:
        print("[ERROR] Could not find SQLite database")
        print("  Set SQLITE_DB_PATH environment variable or place database in:")
        print("    - data/mindgraph.db")
        print("    - mindgraph.db")
        sys.exit(1)
    
    inspect_sqlite_schema(sqlite_path)


if __name__ == '__main__':
    main()
