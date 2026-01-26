"""
Check SQLite Database for Foreign Key Violations

Analyzes the SQLite database to find:
1. Orphaned foreign key references (FK points to non-existent parent)
2. NOT NULL FK columns that might cause migration issues
3. Data integrity issues

Author: lycosa9527
Made by: MindSpring Team
"""

import sqlite3
import os
from pathlib import Path
from typing import Dict, List, Optional


def get_sqlite_db_path() -> Optional[Path]:
    """Find SQLite database file."""
    # Check environment variable
    db_url = os.getenv('DATABASE_URL', '')
    if 'sqlite' in db_url.lower():
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

        if db_path.exists():
            return db_path.resolve()

    # Check common locations
    common_locations = [
        Path("data/mindgraph.db"),
        Path("mindgraph.db"),
        Path("./data/mindgraph.db"),
        Path("./mindgraph.db"),
    ]

    for db_path in common_locations:
        if db_path.exists():
            return db_path.resolve()

    return None


def check_foreign_key_violations(db_path: Path) -> Dict[str, List[Dict]]:
    """
    Check for foreign key violations in SQLite database.

    Returns:
        Dictionary with table names as keys and list of violations as values
    """
    violations = {}

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Enable foreign key checking in SQLite (if supported)
    try:
        cursor.execute("PRAGMA foreign_keys = ON")
    except Exception:
        pass  # Some SQLite versions don't support this

    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in cursor.fetchall()]

    # Common FK relationships based on your models
    fk_relationships = {
        'users': {
            'parent': 'organizations',
            'fk_column': 'organization_id',
            'parent_column': 'id'
        },
        'knowledge_spaces': {
            'parent': 'users',
            'fk_column': 'user_id',
            'parent_column': 'id'
        },
        'knowledge_documents': {
            'parent': 'knowledge_spaces',
            'fk_column': 'space_id',
            'parent_column': 'id'
        },
        'document_chunks': {
            'parent': 'knowledge_documents',
            'fk_column': 'document_id',
            'parent_column': 'id'
        },
        'diagrams': {
            'parent': 'users',
            'fk_column': 'user_id',
            'parent_column': 'id'
        },
        'token_usage': {
            'parent': 'users',
            'fk_column': 'user_id',
            'parent_column': 'id'
        },
        'debate_sessions': {
            'parent': 'users',
            'fk_column': 'user_id',
            'parent_column': 'id'
        },
        'debate_participants': {
            'parent': 'users',
            'fk_column': 'user_id',
            'parent_column': 'id'
        },
        'api_keys': {
            'parent': 'organizations',
            'fk_column': 'organization_id',
            'parent_column': 'id'
        },
    }

    print("=" * 80)
    print("Checking Foreign Key Violations")
    print("=" * 80)

    for table_name in tables:
        if table_name not in fk_relationships:
            continue

        fk_info = fk_relationships[table_name]
        parent_table = fk_info['parent']
        fk_column = fk_info['fk_column']
        parent_column = fk_info['parent_column']

        # Check if parent table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (parent_table,))
        if not cursor.fetchone():
            print(f"\n[WARN] Parent table '{parent_table}' doesn't exist (referenced by {table_name}.{fk_column})")
            continue

        # Check if FK column exists
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = {row[1]: row for row in cursor.fetchall()}
        if fk_column not in columns:
            continue

        # Check if column is nullable
        column_info = columns[fk_column]
        is_nullable = column_info[3] == 0  # 0 = NOT NULL, 1 = nullable

        # Find orphaned references
        query = f"""
            SELECT DISTINCT t.{fk_column}, COUNT(*) as count
            FROM {table_name} t
            LEFT JOIN {parent_table} p ON t.{fk_column} = p.{parent_column}
            WHERE t.{fk_column} IS NOT NULL
              AND p.{parent_column} IS NULL
            GROUP BY t.{fk_column}
            ORDER BY count DESC
            LIMIT 20
        """

        try:
            cursor.execute(query)
            orphaned = cursor.fetchall()

            if orphaned:
                violations[table_name] = []
                total_orphaned = 0

                for row in orphaned:
                    fk_value = row[0]
                    count = row[1]
                    total_orphaned += count

                    violations[table_name].append({
                        'fk_column': fk_column,
                        'fk_value': fk_value,
                        'count': count,
                        'parent_table': parent_table,
                        'is_nullable': is_nullable
                    })

                print(f"\n[ERROR] {table_name}.{fk_column} -> {parent_table}.{parent_column}")
                print(f"   Found {total_orphaned} orphaned records")
                print(f"   Column nullable: {is_nullable}")
                print(f"   Sample orphaned FK values: {[v['fk_value'] for v in violations[table_name][:5]]}")
        except Exception as e:
            print(f"\n[WARN] Error checking {table_name}: {e}")

    conn.close()
    return violations


def check_table_statistics(db_path: Path) -> None:
    """Print basic statistics about tables."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    print("\n" + "=" * 80)
    print("Table Statistics")
    print("=" * 80)

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in cursor.fetchall()]

    for table_name in sorted(tables):
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  {table_name}: {count:,} rows")
        except Exception as e:
            print(f"  {table_name}: Error - {e}")

    conn.close()


def check_user_ids(db_path: Path) -> None:
    """Check for specific user_id issues mentioned in migration logs."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("\n" + "=" * 80)
    print("Checking Specific User IDs from Migration Logs")
    print("=" * 80)

    # User IDs mentioned in your migration logs
    problematic_user_ids = [671, 2157, 2172, 1428]

    # Check if these users exist
    print("\nChecking if problematic user_ids exist in users table:")
    for user_id in problematic_user_ids:
        cursor.execute("SELECT COUNT(*) FROM users WHERE id = ?", (user_id,))
        exists = cursor.fetchone()[0] > 0
        status = "[OK] EXISTS" if exists else "[ERROR] MISSING"
        print(f"  User ID {user_id}: {status}")

    # Check token_usage references
    print("\nChecking token_usage references:")
    for user_id in problematic_user_ids:
        cursor.execute("SELECT COUNT(*) FROM token_usage WHERE user_id = ?", (user_id,))
        count = cursor.fetchone()[0]
        if count > 0:
            cursor.execute("SELECT COUNT(*) FROM users WHERE id = ?", (user_id,))
            user_exists = cursor.fetchone()[0] > 0
            status = "[OK] User exists" if user_exists else "[ERROR] Orphaned!"
            print(f"  token_usage.user_id={user_id}: {count} records, {status}")

            # If orphaned, check when these records were created
            if not user_exists:
                cursor.execute(
                    "SELECT MIN(created_at) as first_usage, MAX(created_at) as last_usage "
                    "FROM token_usage WHERE user_id = ?",
                    (user_id,)
                )
                usage_info = cursor.fetchone()
                if usage_info and usage_info[0]:
                    print(f"    First usage: {usage_info[0]}")
                    print(f"    Last usage: {usage_info[1]}")

    # Check debate_sessions references
    print("\nChecking debate_sessions references:")
    for user_id in problematic_user_ids:
        cursor.execute("SELECT COUNT(*) FROM debate_sessions WHERE user_id = ?", (user_id,))
        count = cursor.fetchone()[0]
        if count > 0:
            cursor.execute("SELECT COUNT(*) FROM users WHERE id = ?", (user_id,))
            user_exists = cursor.fetchone()[0] > 0
            status = "[OK] User exists" if user_exists else "[ERROR] Orphaned!"
            print(f"  debate_sessions.user_id={user_id}: {count} records, {status}")

    # Check user ID ranges to see if there's a gap
    print("\n" + "=" * 80)
    print("Analyzing User ID Gaps")
    print("=" * 80)

    cursor.execute("SELECT MIN(id) as min_id, MAX(id) as max_id, COUNT(*) as total FROM users")
    user_stats = cursor.fetchone()
    print("\nUsers table:")
    print(f"  Min ID: {user_stats[0]}")
    print(f"  Max ID: {user_stats[1]}")
    print(f"  Total users: {user_stats[2]}")

    # Check if orphaned user IDs are in the range
    print(f"\nOrphaned user IDs: {[uid for uid in problematic_user_ids if uid not in [1428]]}")
    for user_id in [671, 2157, 2172]:
        if user_stats[0] <= user_id <= user_stats[1]:
            print(f"  User ID {user_id}: In range but missing (likely deleted)")
        else:
            print(f"  User ID {user_id}: Outside range")

    # Check SQLite FK constraints
    print("\n" + "=" * 80)
    print("Checking SQLite Foreign Key Constraints")
    print("=" * 80)

    try:
        cursor.execute("PRAGMA foreign_keys")
        fk_enabled = cursor.fetchone()[0]
        print(f"\nForeign keys enabled: {fk_enabled}")

        if not fk_enabled:
            print("\n[WARN] SQLite foreign keys are DISABLED!")
            print("  This explains why orphaned records exist.")
            print("  SQLite allows FK violations when foreign_keys=OFF")
    except Exception as e:
        print(f"\nCould not check FK status: {e}")

    # Check if there are other tables referencing these users
    print("\n" + "=" * 80)
    print("Checking Other Tables Referencing Orphaned Users")
    print("=" * 80)

    tables_to_check = [
        ('diagrams', 'user_id'),
        ('knowledge_spaces', 'user_id'),
        ('debate_sessions', 'user_id'),
        ('debate_participants', 'user_id'),
        ('pinned_conversations', 'user_id'),
    ]

    for table_name, fk_col in tables_to_check:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {fk_col} IN (671, 2157, 2172)")
            count = cursor.fetchone()[0]
            if count > 0:
                print(f"\n{table_name}.{fk_col}:")
                for user_id in [671, 2157, 2172]:
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {fk_col} = ?", (user_id,))
                    ref_count = cursor.fetchone()[0]
                    if ref_count > 0:
                        cursor.execute("SELECT COUNT(*) FROM users WHERE id = ?", (user_id,))
                        user_exists = cursor.fetchone()[0] > 0
                        status = "[OK]" if user_exists else "[ORPHANED]"
                        print(f"  User {user_id}: {ref_count} references {status}")
        except Exception:
            pass  # Table might not exist

    conn.close()


def main():
    """Main function."""
    db_path = get_sqlite_db_path()

    if not db_path or not db_path.exists():
        print("[ERROR] SQLite database not found!")
        print("\nChecked locations:")
        print("  - data/mindgraph.db")
        print("  - mindgraph.db")
        print("  - DATABASE_URL environment variable")
        return

    print(f"[OK] Found SQLite database: {db_path}")
    print(f"   Size: {db_path.stat().st_size / 1024 / 1024:.2f} MB")

    # Check table statistics
    check_table_statistics(db_path)

    # Check FK violations
    violations = check_foreign_key_violations(db_path)

    # Check specific user IDs
    check_user_ids(db_path)

    # Summary
    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)

    if violations:
        total_violations = sum(sum(v['count'] for v in table_violations) for table_violations in violations.values())
        print(f"\n[WARN] Found {len(violations)} tables with FK violations")
        print(f"[WARN] Total orphaned records: {total_violations:,}")

        print("\nTables with violations:")
        for table_name, table_violations in violations.items():
            total = sum(v['count'] for v in table_violations)
            nullable_count = sum(v['count'] for v in table_violations if v['is_nullable'])
            not_null_count = total - nullable_count

            print(f"\n  {table_name}:")
            print(f"    Total orphaned: {total:,}")
            print(f"    Nullable FK (can be set to NULL): {nullable_count:,}")
            print(f"    NOT NULL FK (needs placeholder): {not_null_count:,}")
    else:
        print("\n[OK] No FK violations found!")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
