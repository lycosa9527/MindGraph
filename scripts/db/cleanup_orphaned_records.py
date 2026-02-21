"""
Cleanup Orphaned Records from SQLite Database

Removes records that reference deleted parent records (orphaned foreign keys).
This should be run BEFORE migration to clean up the database.

Usage:
    python scripts/db/cleanup_orphaned_records.py
    
    # With options:
    python scripts/db/cleanup_orphaned_records.py --live
    python scripts/db/cleanup_orphaned_records.py --live --yes

Options:
    --live    Actually delete orphaned records (default is dry-run mode)
    --yes     Skip confirmation prompt (useful for non-interactive execution)

Examples:
    # Dry run (default - shows what would be deleted without actually deleting)
    python scripts/db/cleanup_orphaned_records.py
    
    # Actually delete orphaned records (with confirmation)
    python scripts/db/cleanup_orphaned_records.py --live
    
    # Delete without confirmation prompt
    python scripts/db/cleanup_orphaned_records.py --live --yes

Note: This script can be run from any directory. It will automatically
      find the SQLite database using DATABASE_URL environment variable
      or by checking common locations (data/mindgraph.db, /root/mindgraph/, etc.).

Author: lycosa9527
Made by: MindSpring Team
"""

import sqlite3
import os
import sys
import shutil
from pathlib import Path
from typing import Optional

# Calculate project root (parent of scripts directory)
_project_root = Path(__file__).parent.parent.parent


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
                # Use project root as base for relative paths
                db_path = _project_root / db_path_str
            else:
                db_path = Path(db_path_str)
        else:
            db_path = Path(db_url.replace("sqlite:///", ""))

        if db_path.exists():
            return db_path.resolve()

    # Check common locations relative to project root
    common_locations = [
        _project_root / "data" / "mindgraph.db",
        _project_root / "mindgraph.db",
        Path("/root/mindgraph/mindgraph.db"),  # Common server location
        Path("/root/mindgraph/data/mindgraph.db"),  # Alternative server location
    ]

    for db_path in common_locations:
        if db_path.exists():
            return db_path.resolve()

    return None


def cleanup_orphaned_records(db_path: Path, dry_run: bool = True) -> dict:
    """
    Clean up orphaned records from SQLite database.
    
    Args:
        db_path: Path to SQLite database
        dry_run: If True, only report what would be deleted without actually deleting
        
    Returns:
        Dictionary with cleanup statistics
    """
    stats = {
        'tables_cleaned': [],
        'records_deleted': {},
        'total_deleted': 0
    }

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=" * 80)
    print("Orphaned Records Cleanup")
    print("=" * 80)
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE (will delete records)'}")
    print()

    # Clean up token_usage records with orphaned user_id
    print("Cleaning token_usage table:")
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM token_usage t
        LEFT JOIN users u ON t.user_id = u.id
        WHERE t.user_id IS NOT NULL AND u.id IS NULL
    """)
    orphaned_count = cursor.fetchone()['count']

    if orphaned_count > 0:
        print(f"  Found {orphaned_count:,} orphaned records (user_id references deleted users)")

        if not dry_run:
            cursor.execute("""
                DELETE FROM token_usage
                WHERE user_id IS NOT NULL
                  AND user_id NOT IN (SELECT id FROM users)
            """)
            deleted = cursor.rowcount
            conn.commit()
            print(f"  [DELETED] {deleted:,} orphaned token_usage records")
            stats['records_deleted']['token_usage'] = deleted
            stats['total_deleted'] += deleted
        else:
            print(f"  [WOULD DELETE] {orphaned_count:,} orphaned token_usage records")
            stats['records_deleted']['token_usage'] = orphaned_count
            stats['total_deleted'] += orphaned_count

        # Show sample orphaned user_ids
        cursor.execute("""
            SELECT DISTINCT user_id, COUNT(*) as count
            FROM token_usage t
            LEFT JOIN users u ON t.user_id = u.id
            WHERE t.user_id IS NOT NULL AND u.id IS NULL
            GROUP BY user_id
            ORDER BY count DESC
            LIMIT 5
        """)
        samples = cursor.fetchall()
        print(f"  Sample orphaned user_ids: {[r['user_id'] for r in samples]}")
    else:
        print("  [OK] No orphaned records found")

    # Check other tables for orphaned records
    print("\nChecking other tables:")

    tables_to_check = [
        ('diagrams', 'user_id', 'users', 'id'),
        ('knowledge_spaces', 'user_id', 'users', 'id'),
        ('debate_sessions', 'user_id', 'users', 'id'),
        ('debate_participants', 'user_id', 'users', 'id'),
        ('pinned_conversations', 'user_id', 'users', 'id'),
        ('api_keys', 'organization_id', 'organizations', 'id'),
    ]

    for table_name, fk_col, parent_table, parent_col in tables_to_check:
        try:
            # Check if table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
            if not cursor.fetchone():
                continue

            # Check if FK column exists
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [row[1] for row in cursor.fetchall()]
            if fk_col not in columns:
                continue

            # Count orphaned records
            cursor.execute(f"""
                SELECT COUNT(*) as count
                FROM {table_name} t
                LEFT JOIN {parent_table} p ON t.{fk_col} = p.{parent_col}
                WHERE t.{fk_col} IS NOT NULL AND p.{parent_col} IS NULL
            """)
            orphaned_count = cursor.fetchone()['count']

            if orphaned_count > 0:
                print(f"\n  {table_name}.{fk_col}:")
                print(f"    Found {orphaned_count:,} orphaned records")

                if not dry_run:
                    cursor.execute(f"""
                        DELETE FROM {table_name}
                        WHERE {fk_col} IS NOT NULL
                          AND {fk_col} NOT IN (SELECT {parent_col} FROM {parent_table})
                    """)
                    deleted = cursor.rowcount
                    conn.commit()
                    print(f"    [DELETED] {deleted:,} records")
                    stats['records_deleted'][table_name] = deleted
                    stats['total_deleted'] += deleted
                else:
                    print(f"    [WOULD DELETE] {orphaned_count:,} records")
                    stats['records_deleted'][table_name] = orphaned_count
                    stats['total_deleted'] += orphaned_count
        except Exception as e:
            print(f"    [ERROR] Could not check {table_name}: {e}")

    conn.close()

    return stats


def main():
    """Main function."""
    db_path = get_sqlite_db_path()

    if not db_path or not db_path.exists():
        print("[ERROR] SQLite database not found!")
        return

    print(f"[OK] Found SQLite database: {db_path}")
    print(f"   Size: {db_path.stat().st_size / 1024 / 1024:.2f} MB\n")

    # Check for --live flag
    dry_run = '--live' not in sys.argv

    if dry_run:
        print("[INFO] Running in DRY RUN mode. Use --live to actually delete records.\n")
    else:
        print("[WARNING] Running in LIVE mode. Records will be permanently deleted!\n")
        # Skip confirmation if --yes flag is provided or running non-interactively
        if '--yes' not in sys.argv:
            try:
                response = input("Are you sure you want to delete orphaned records? (yes/no): ")
                if response.lower() != 'yes':
                    print("Aborted.")
                    return
            except EOFError:
                # Running non-interactively, proceed with deletion
                print("[INFO] Running non-interactively, proceeding with deletion...\n")

    # Create backup before cleanup
    if not dry_run:
        backup_path = db_path.parent / f"{db_path.stem}.backup_before_cleanup{db_path.suffix}"
        print(f"\nCreating backup: {backup_path}")
        # copyfile only copies content; avoids PermissionError on WSL/Windows mounts
        # (copy2/copy fail on copystat/copymode for /mnt/c/...)
        shutil.copyfile(db_path, backup_path)
        print("[OK] Backup created\n")

    # Run cleanup
    stats = cleanup_orphaned_records(db_path, dry_run=dry_run)

    # Summary
    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)

    if stats['total_deleted'] > 0:
        print(f"\nTotal orphaned records: {stats['total_deleted']:,}")
        print("\nBreakdown by table:")
        for table, count in stats['records_deleted'].items():
            print(f"  {table}: {count:,} records")

        if dry_run:
            print("\n[INFO] This was a DRY RUN. No records were actually deleted.")
            print("Run with --live flag to actually delete these records.")
        else:
            print("\n[OK] Cleanup completed!")
    else:
        print("\n[OK] No orphaned records found. Database is clean!")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
