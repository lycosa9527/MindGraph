"""
Database Recovery Module for MindGraph
=======================================

Automatic database corruption detection and interactive recovery.
Runs at application startup to ensure database integrity.

Features:
- Detects database corruption on startup
- Lists available backups with metadata
- Compares backup contents (user counts, table sizes)
- Interactive restore with confirmation
- Automatic backup of corrupted database before restore

Usage:
    This module is called by main.py during startup.
    If corruption is detected, the application pauses for user decision.

Author: MindSpring Team
"""

import os
import sys
import sqlite3
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Import backup configuration
try:
    from services.backup_scheduler import (
        BACKUP_DIR, 
        get_database_path,
        list_cos_backups,
        COS_BACKUP_ENABLED,
        COS_BUCKET,
        COS_REGION,
        COS_KEY_PREFIX
    )
except ImportError:
    BACKUP_DIR = Path("backup")
    get_database_path = None
    list_cos_backups = None
    COS_BACKUP_ENABLED = False
    COS_BUCKET = ""
    COS_REGION = ""
    COS_KEY_PREFIX = ""


# Minimum percentage of records to consider a backup valid compared to previous
# If a backup has less than 50% of the previous backup's records, it's flagged as anomalous
ANOMALY_THRESHOLD_PERCENT = 50


class DatabaseRecovery:
    """
    Database recovery manager for handling corruption and restore operations.
    
    Features:
    - Corruption detection and recovery
    - Data anomaly detection (detects significant data loss between backups)
    - Smart merge capability (combine data from multiple backups)
    """
    
    def __init__(self):
        self.db_path = self._get_db_path()
        self.backup_dir = BACKUP_DIR
        
    def _get_db_path(self) -> Optional[Path]:
        """Get the database path from configuration."""
        if get_database_path:
            return get_database_path()
        
        # Fallback: try common locations
        for path in [Path("data/mindgraph.db"), Path("mindgraph.db")]:
            if path.exists():
                return path.resolve()
        return Path("data/mindgraph.db")
    
    def check_integrity(self) -> Tuple[bool, str]:
        """
        Check database integrity.
        
        Returns:
            tuple: (is_healthy, message)
        """
        if not self.db_path or not self.db_path.exists():
            return True, "Database does not exist yet (will be created)"
        
        conn = None
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=30.0)
            cursor = conn.cursor()
            
            # Run integrity check
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            
            if result and result[0] == "ok":
                return True, "Database integrity check passed"
            else:
                return False, f"Integrity check failed: {result[0] if result else 'unknown error'}"
                
        except sqlite3.DatabaseError as e:
            return False, f"Database error: {e}"
        except Exception as e:
            return False, f"Error checking integrity: {e}"
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
    
    def get_database_stats(self, db_path: Path) -> Dict[str, Any]:
        """
        Get statistics from a database file.
        
        Args:
            db_path: Path to database file
            
        Returns:
            dict with table counts and other stats
        """
        stats = {
            "path": str(db_path),
            "size_mb": 0,
            "modified": None,
            "tables": {},
            "total_rows": 0,
            "healthy": False
        }
        
        if not db_path.exists():
            return stats
        
        try:
            stat = db_path.stat()
            stats["size_mb"] = round(stat.st_size / (1024 * 1024), 2)
            stats["size_bytes"] = stat.st_size
            stats["modified"] = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            
            # Minimum size check: A valid SQLite database must be at least 100 bytes (header)
            # Practically, a database with tables is at least 4KB (one page)
            # We use 1KB as minimum to catch obviously invalid files
            MIN_VALID_SIZE = 1024  # 1 KB minimum
            if stat.st_size < MIN_VALID_SIZE:
                logger.warning(f"[Recovery] Backup too small ({stat.st_size} bytes): {db_path.name}")
                stats["healthy"] = False
                stats["error"] = f"File too small ({stat.st_size} bytes) - not a valid database"
                return stats
            
            # Check SQLite header magic bytes
            try:
                with open(db_path, 'rb') as f:
                    header = f.read(16)
                    if not header.startswith(b'SQLite format 3'):
                        logger.warning(f"[Recovery] Invalid SQLite header: {db_path.name}")
                        stats["healthy"] = False
                        stats["error"] = "Invalid file - not a SQLite database"
                        return stats
            except Exception as e:
                logger.warning(f"[Recovery] Cannot read file header: {e}")
                stats["healthy"] = False
                stats["error"] = f"Cannot read file: {e}"
                return stats
        except Exception:
            pass
        
        conn = None
        try:
            conn = sqlite3.connect(str(db_path), timeout=30.0)
            cursor = conn.cursor()
            
            # Check integrity first
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()
            stats["healthy"] = result and result[0] == "ok"
            
            if not stats["healthy"]:
                return stats
            
            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = cursor.fetchall()
            
            for (table_name,) in tables:
                try:
                    # Use double quotes to safely quote table name (SQLite standard)
                    # Table names from sqlite_master are trusted, but we quote for safety
                    safe_table_name = f'"{table_name}"'
                    cursor.execute(f"SELECT COUNT(*) FROM {safe_table_name}")
                    count = cursor.fetchone()[0]
                    stats["tables"][table_name] = count
                    stats["total_rows"] += count
                except Exception:
                    stats["tables"][table_name] = "error"
            
        except Exception as e:
            logger.debug(f"[Recovery] Error getting stats for {db_path}: {e}")
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
        
        return stats
    
    def download_cos_backup(self, cos_key: str, local_path: Path) -> Tuple[bool, str]:
        """
        Download a backup from COS to local temporary location for comparison.
        
        IMPORTANT: Only downloads backups with the configured COS_KEY_PREFIX to prevent
        cross-environment access (e.g., dev vs production).
        
        Args:
            cos_key: COS object key (e.g., "backups/mindgraph/mindgraph.db.20251217_081113")
            local_path: Local path to save the downloaded backup
            
        Returns:
            tuple: (success, message)
        """
        if not COS_BACKUP_ENABLED or not list_cos_backups:
            return False, "COS backup not enabled"
        
        # SECURITY: Validate that the key uses the configured prefix
        # This prevents accidentally downloading backups from other environments
        # (e.g., dev machine downloading production backups or vice versa)
        normalized_prefix = COS_KEY_PREFIX.rstrip('/')
        normalized_key = cos_key.lstrip('/')
        
        if not normalized_key.startswith(normalized_prefix):
            logger.error(
                f"[Recovery] SECURITY: COS key '{cos_key}' does not match configured prefix '{COS_KEY_PREFIX}'. "
                f"Refusing to download to prevent cross-environment access."
            )
            return False, f"Key does not match configured prefix '{COS_KEY_PREFIX}'"
        
        try:
            from qcloud_cos import CosConfig, CosS3Client
            from qcloud_cos.cos_exception import CosClientError, CosServiceError
            
            # Get credentials from backup_scheduler
            from services.backup_scheduler import COS_SECRET_ID, COS_SECRET_KEY
            
            if not COS_SECRET_ID or not COS_SECRET_KEY or not COS_BUCKET:
                return False, "COS credentials not configured"
            
            # Initialize COS client
            config = CosConfig(
                Region=COS_REGION,
                SecretId=COS_SECRET_ID,
                SecretKey=COS_SECRET_KEY,
                Scheme='https'
            )
            client = CosS3Client(config)
            
            # Ensure local directory exists
            local_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Download from COS
            logger.info(f"[Recovery] Downloading COS backup: {cos_key} (prefix: {COS_KEY_PREFIX})")
            response = client.get_object(
                Bucket=COS_BUCKET,
                Key=cos_key
            )
            
            # Save to local file
            response['Body'].get_stream_to_file(str(local_path))
            
            logger.info(f"[Recovery] Downloaded COS backup to: {local_path}")
            return True, f"Downloaded from COS: {cos_key}"
            
        except ImportError:
            return False, "COS SDK not installed"
        except CosClientError as e:
            logger.error(f"[Recovery] COS client error downloading backup: {e}")
            return False, f"COS client error: {e}"
        except CosServiceError as e:
            error_code = e.get_error_code() if hasattr(e, 'get_error_code') else 'Unknown'
            logger.error(f"[Recovery] COS service error downloading backup: {error_code}")
            return False, f"COS service error: {error_code}"
        except Exception as e:
            logger.error(f"[Recovery] Error downloading COS backup: {e}", exc_info=True)
            return False, f"Download failed: {e}"
    
    def list_backups(self, include_cos: bool = True) -> List[Dict[str, Any]]:
        """
        List all available backups with their statistics.
        Includes both local backups and COS backups (if enabled).
        
        Args:
            include_cos: Whether to include COS backups (default: True)
        
        Returns:
            List of backup info dicts, sorted by date (newest first)
            Each backup dict includes a 'source' field: 'local' or 'cos'
        """
        backups = []
        
        # List local backups
        if self.backup_dir.exists():
            for backup_file in self.backup_dir.glob("mindgraph.db.*"):
                if not backup_file.is_file():
                    continue
                
                stats = self.get_database_stats(backup_file)
                stats["filename"] = backup_file.name
                stats["source"] = "local"
                stats["path"] = str(backup_file)
                backups.append(stats)
        
        # List COS backups if enabled
        if include_cos and COS_BACKUP_ENABLED and list_cos_backups:
            try:
                cos_backups = list_cos_backups()
                for cos_backup in cos_backups:
                    # Create a temporary stats entry for COS backup
                    # We'll download it later if user wants to compare/restore
                    stats = {
                        "filename": cos_backup['key'].split('/')[-1],  # Extract filename from key
                        "source": "cos",
                        "cos_key": cos_backup['key'],
                        "size_mb": round(cos_backup['size'] / (1024 * 1024), 2) if isinstance(cos_backup['size'], (int, float)) else 0,
                        "modified": cos_backup.get('last_modified', ''),
                        "path": None,  # Will be set when downloaded
                        "tables": {},  # Will be populated after download
                        "total_rows": 0,
                        "healthy": None,  # Unknown until downloaded
                        "downloaded": False
                    }
                    backups.append(stats)
            except Exception as e:
                logger.warning(f"[Recovery] Error listing COS backups: {e}")
        
        # Sort by modification time (newest first)
        # For COS backups, parse the timestamp
        def get_sort_key(backup):
            modified = backup.get("modified", "")
            if isinstance(modified, str) and modified:
                try:
                    # Try to parse various timestamp formats
                    if 'T' in modified:
                        # ISO format
                        modified = modified.replace('Z', '')
                        if '.' in modified:
                            return datetime.strptime(modified.split('.')[0], '%Y-%m-%dT%H:%M:%S')
                        else:
                            return datetime.strptime(modified, '%Y-%m-%dT%H:%M:%S')
                    else:
                        # Format: "2025-12-17 08:11:13"
                        return datetime.strptime(modified, '%Y-%m-%d %H:%M:%S')
                except Exception:
                    pass
            return datetime.min
        
        backups.sort(key=get_sort_key, reverse=True)
        
        return backups
    
    def detect_anomalies(self, backups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect data anomalies between consecutive backups.
        
        Flags backups that have significantly fewer records than the previous backup,
        which may indicate data loss or corruption.
        
        Args:
            backups: List of backup stats (sorted newest first)
            
        Returns:
            List of anomaly reports
        """
        anomalies = []
        
        # Need at least 2 backups to compare
        if len(backups) < 2:
            return anomalies
        
        # Compare each backup with the next (older) one
        for i in range(len(backups) - 1):
            newer = backups[i]
            older = backups[i + 1]
            
            if not newer.get("healthy") or not older.get("healthy"):
                continue
            
            # Compare user counts specifically (most important table)
            newer_users = newer.get("tables", {}).get("users", 0)
            older_users = older.get("tables", {}).get("users", 0)
            
            if isinstance(newer_users, int) and isinstance(older_users, int):
                if older_users > 0 and newer_users < older_users:
                    loss_percent = ((older_users - newer_users) / older_users) * 100
                    
                    if loss_percent > (100 - ANOMALY_THRESHOLD_PERCENT):
                        anomalies.append({
                            "type": "data_loss",
                            "newer_backup": newer.get("filename"),
                            "older_backup": older.get("filename"),
                            "table": "users",
                            "newer_count": newer_users,
                            "older_count": older_users,
                            "loss_percent": round(loss_percent, 1),
                            "message": f"Possible data loss: {newer.get('filename')} has {newer_users} users, "
                                      f"but {older.get('filename')} has {older_users} users ({loss_percent:.1f}% fewer)"
                        })
            
            # Also check total rows
            newer_total = newer.get("total_rows", 0)
            older_total = older.get("total_rows", 0)
            
            if older_total > 0 and newer_total < older_total:
                loss_percent = ((older_total - newer_total) / older_total) * 100
                
                if loss_percent > (100 - ANOMALY_THRESHOLD_PERCENT):
                    anomalies.append({
                        "type": "data_loss",
                        "newer_backup": newer.get("filename"),
                        "older_backup": older.get("filename"),
                        "table": "total",
                        "newer_count": newer_total,
                        "older_count": older_total,
                        "loss_percent": round(loss_percent, 1),
                        "message": f"Possible data loss: {newer.get('filename')} has {newer_total} total rows, "
                                  f"but {older.get('filename')} has {older_total} rows ({loss_percent:.1f}% fewer)"
                    })
        
        return anomalies
    
    def merge_backups(self, base_backup: Path, newer_backup: Path, output_path: Path) -> Tuple[bool, str, Dict]:
        """
        Merge data from two backups - use base as foundation, add new records from newer.
        
        This handles the scenario where a newer backup has fewer records (data loss),
        but may have some new records that the older backup doesn't have.
        
        Strategy:
        1. Copy base backup to output
        2. For each table in newer backup, INSERT OR IGNORE new records
        3. Return merged stats
        
        Args:
            base_backup: Path to backup with more data (usually older)
            newer_backup: Path to backup with potentially new records
            output_path: Path to write merged database
            
        Returns:
            tuple: (success, message, merge_stats)
        """
        merge_stats = {
            "base_backup": base_backup.name,
            "newer_backup": newer_backup.name,
            "tables_merged": {},
            "total_new_records": 0
        }
        
        base_conn = None
        newer_conn = None
        output_conn = None
        
        try:
            # Copy base backup to output
            shutil.copy2(base_backup, output_path)
            
            # Open connections
            output_conn = sqlite3.connect(str(output_path), timeout=60.0)
            newer_conn = sqlite3.connect(str(newer_backup), timeout=60.0)
            
            output_cursor = output_conn.cursor()
            newer_cursor = newer_conn.cursor()
            
            # Get tables from newer backup
            newer_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = [row[0] for row in newer_cursor.fetchall()]
            
            for table_name in tables:
                try:
                    # Get column names
                    newer_cursor.execute(f'PRAGMA table_info("{table_name}")')
                    columns = [col[1] for col in newer_cursor.fetchall()]
                    
                    if not columns:
                        continue
                    
                    # Get all records from newer backup
                    col_list = ', '.join([f'"{c}"' for c in columns])
                    newer_cursor.execute(f'SELECT {col_list} FROM "{table_name}"')
                    records = newer_cursor.fetchall()
                    
                    if not records:
                        continue
                    
                    # Count records before
                    output_cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
                    count_before = output_cursor.fetchone()[0]
                    
                    # Insert records using INSERT OR IGNORE (skips duplicates based on primary key)
                    placeholders = ', '.join(['?' for _ in columns])
                    insert_sql = f'INSERT OR IGNORE INTO "{table_name}" ({col_list}) VALUES ({placeholders})'
                    
                    for record in records:
                        try:
                            output_cursor.execute(insert_sql, record)
                        except sqlite3.IntegrityError:
                            pass  # Duplicate, skip
                        except Exception as e:
                            logger.debug(f"[Recovery] Could not insert record into {table_name}: {e}")
                    
                    # Count records after
                    output_cursor.execute(f'SELECT COUNT(*) FROM "{table_name}"')
                    count_after = output_cursor.fetchone()[0]
                    
                    new_records = count_after - count_before
                    if new_records > 0:
                        merge_stats["tables_merged"][table_name] = new_records
                        merge_stats["total_new_records"] += new_records
                        logger.info(f"[Recovery] Merged {new_records} new records into {table_name}")
                
                except Exception as e:
                    logger.warning(f"[Recovery] Error merging table {table_name}: {e}")
            
            output_conn.commit()
            
            # Verify output integrity
            output_cursor.execute("PRAGMA integrity_check")
            result = output_cursor.fetchone()
            if not result or result[0] != "ok":
                return False, "Merged database failed integrity check", merge_stats
            
            # Get final counts (if users table exists)
            try:
                output_cursor.execute("SELECT COUNT(*) FROM users")
                merge_stats["final_user_count"] = output_cursor.fetchone()[0]
            except sqlite3.OperationalError:
                merge_stats["final_user_count"] = "N/A"
            
            return True, f"Successfully merged {merge_stats['total_new_records']} new records", merge_stats
            
        except Exception as e:
            logger.error(f"[Recovery] Merge failed: {e}", exc_info=True)
            # Clean up failed merge
            if output_path.exists():
                try:
                    output_path.unlink()
                except Exception:
                    pass
            return False, f"Merge failed: {e}", merge_stats
        finally:
            for conn in [output_conn, newer_conn, base_conn]:
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass
    
    def restore_from_backup(self, backup_path: Path) -> Tuple[bool, str]:
        """
        Restore database from a backup file.
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            tuple: (success, message)
        """
        if not backup_path.exists():
            return False, f"Backup file not found: {backup_path}"
        
        # Check minimum file size before anything else
        try:
            backup_size = backup_path.stat().st_size
            if backup_size < 1024:  # Less than 1KB
                return False, f"Backup file too small ({backup_size} bytes) - not a valid database"
        except Exception as e:
            return False, f"Cannot read backup file: {e}"
        
        # Verify backup integrity
        stats = self.get_database_stats(backup_path)
        if not stats["healthy"]:
            error_msg = stats.get("error", "Backup file is corrupted")
            return False, f"Cannot restore: {error_msg}"
        
        # Check disk space (need at least backup size + 100MB buffer)
        try:
            backup_size_mb = backup_path.stat().st_size / (1024 * 1024)
            required_mb = int(backup_size_mb) + 100
            
            if self.db_path:
                import os
                try:
                    stat = os.statvfs(self.db_path.parent)
                    free_mb = (stat.f_bavail * stat.f_frsize) / (1024 * 1024)
                    if free_mb < required_mb:
                        return False, f"Insufficient disk space: {free_mb:.1f} MB free, need {required_mb} MB"
                except AttributeError:
                    pass  # Windows - skip check
        except Exception:
            pass  # Continue anyway if check fails
        
        try:
            # Create backup of corrupted database
            if self.db_path and self.db_path.exists():
                corrupted_backup = self.db_path.parent / f"{self.db_path.name}.corrupted.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.copy2(self.db_path, corrupted_backup)
                logger.info(f"[Recovery] Saved corrupted database to: {corrupted_backup}")
                
                # Also backup WAL and SHM files if they exist
                for suffix in ["-wal", "-shm"]:
                    wal_file = Path(str(self.db_path) + suffix)
                    if wal_file.exists():
                        shutil.copy2(wal_file, Path(str(corrupted_backup) + suffix))
                
                # Remove the corrupted database and its WAL/SHM files
                self.db_path.unlink()
                for suffix in ["-wal", "-shm"]:
                    wal_file = Path(str(self.db_path) + suffix)
                    if wal_file.exists():
                        wal_file.unlink()
            
            # Ensure target directory exists
            if self.db_path:
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy backup to database location
            shutil.copy2(backup_path, self.db_path)
            
            # Verify restored database
            restored_stats = self.get_database_stats(self.db_path)
            if restored_stats["healthy"]:
                return True, f"Database restored successfully from {backup_path.name}"
            else:
                return False, "Restored database failed integrity check"
                
        except PermissionError as e:
            return False, f"Permission denied during restore: {e}"
        except OSError as e:
            return False, f"OS error during restore (disk full?): {e}"
        except Exception as e:
            logger.error(f"[Recovery] Restore error: {e}", exc_info=True)
            return False, f"Restore failed: {e}"
    
    def print_comparison(self, current_stats: Dict, backups: List[Dict], anomalies: List[Dict] = None) -> None:
        """Print a comparison table of current database and backups."""
        print("\n" + "=" * 100)
        print("DATABASE RECOVERY - Backup Comparison")
        print("=" * 100)
        
        # Separate local and COS backups
        local_backups = [b for b in backups if b.get("source") == "local"]
        cos_backups = [b for b in backups if b.get("source") == "cos"]
        
        # Limit to 2 most recent local backups
        local_backups = sorted(local_backups, key=lambda x: x.get("modified", ""), reverse=True)[:2]
        
        # Current database status
        print("\n[CURRENT DATABASE]")
        if current_stats.get("healthy"):
            print(f"  Status: HEALTHY")
        else:
            print(f"  Status: CORRUPTED")
        print(f"  Path: {current_stats.get('path', 'N/A')}")
        print(f"  Size: {current_stats.get('size_mb', 0)} MB")
        print(f"  Modified: {current_stats.get('modified', 'N/A')}")
        
        # Print comparison table
        print("\n" + "-" * 100)
        print("BACKUP COMPARISON TABLE")
        print("-" * 100)
        
        # Table header
        print(f"{'Source':<10} {'Filename':<40} {'Status':<12} {'Size (MB)':<12} {'Users':<10} {'Modified':<20}")
        print("-" * 100)
        
        # Current database row
        current_status = "HEALTHY" if current_stats.get("healthy") else "CORRUPTED"
        current_users = current_stats.get("tables", {}).get("users", "?")
        print(f"{'CURRENT':<10} {'(current database)':<40} {current_status:<12} {current_stats.get('size_mb', 0):<12.2f} {str(current_users):<10} {current_stats.get('modified', 'N/A'):<20}")
        
        # Local backups (limit to 2)
        for backup in local_backups:
            status = "HEALTHY" if backup.get("healthy") else "CORRUPTED"
            users = backup.get("tables", {}).get("users", "?")
            filename = backup.get("filename", "unknown")[:38]  # Truncate if too long
            print(f"{'LOCAL':<10} {filename:<40} {status:<12} {backup.get('size_mb', 0):<12.2f} {str(users):<10} {backup.get('modified', 'N/A'):<20}")
        
        # COS backups
        for backup in cos_backups:
            status = "COS" if backup.get("healthy") is None else ("HEALTHY" if backup.get("healthy") else "CORRUPTED")
            if backup.get("healthy") is None:
                status = "COS (not downloaded)"
            users = backup.get("tables", {}).get("users", "?")
            filename = backup.get("filename", "unknown")[:38]
            print(f"{'COS':<10} {filename:<40} {status:<12} {backup.get('size_mb', 0):<12.2f} {str(users):<10} {backup.get('modified', 'N/A'):<20}")
        
        print("-" * 100)
        
        # Detailed table information
        print("\n[DETAILED BACKUP INFORMATION]")
        
        # Local backups details
        if local_backups:
            print("\n  Local Backups:")
            for i, backup in enumerate(local_backups, 1):
                status = "HEALTHY" if backup["healthy"] else "CORRUPTED"
                print(f"\n    [{i}] {backup['filename']} ({status})")
                print(f"        Size: {backup['size_mb']} MB")
                print(f"        Modified: {backup['modified']}")
                if backup["tables"] and backup["healthy"]:
                    print(f"        Key Tables:")
                    for table in ["users", "organizations", "api_keys", "token_usage"]:
                        if table in backup["tables"]:
                            print(f"          - {table}: {backup['tables'][table]} rows")
        
        # COS backups details
        if cos_backups:
            print("\n  COS Backups:")
            for i, backup in enumerate(cos_backups, len(local_backups) + 1):
                cos_key = backup.get("cos_key", "unknown")
                downloaded = backup.get("downloaded", False)
                status_note = " (downloaded)" if downloaded else " (will download for comparison)"
                print(f"\n    [{i}] {backup['filename']} - COS{status_note}")
                print(f"        COS Key: {cos_key}")
                print(f"        Size: {backup['size_mb']} MB")
                print(f"        Modified: {backup['modified']}")
                if backup.get("tables") and backup.get("healthy"):
                    print(f"        Key Tables:")
                    for table in ["users", "organizations", "api_keys", "token_usage"]:
                        if table in backup["tables"]:
                            print(f"          - {table}: {backup['tables'][table]} rows")
                elif not downloaded:
                    print(f"        Note: Download from COS to see detailed statistics")
        
        # Show anomalies/warnings
        if anomalies:
            print("\n" + "-" * 100)
            print("[DATA ANOMALIES DETECTED]")
            for anomaly in anomalies:
                if anomaly.get("table") == "users":
                    print(f"\n  WARNING: {anomaly['message']}")
                    print(f"           Consider using MERGE to combine both backups.")
        
        print("\n" + "=" * 100)
    
    def interactive_recovery(self) -> bool:
        """
        Run interactive recovery process.
        
        Returns:
            True if recovery succeeded or not needed, False to abort startup
        """
        # Check current database
        is_healthy, message = self.check_integrity()
        
        if is_healthy:
            logger.info(f"[Recovery] {message}")
            return True
        
        # Database is corrupted - enter recovery mode
        logger.error(f"[Recovery] DATABASE CORRUPTION DETECTED: {message}")
        
        # Get stats and backups
        current_stats = self.get_database_stats(self.db_path) if self.db_path else {}
        backups = self.list_backups(include_cos=True)
        
        # Download COS backups for comparison (limit to most recent ones)
        cos_backups = [b for b in backups if b.get("source") == "cos"]
        local_backups = [b for b in backups if b.get("source") == "local"]
        
        # Limit to 2 most recent local backups
        local_backups = sorted(local_backups, key=lambda x: x.get("modified", ""), reverse=True)[:2]
        
        # Download COS backups to get their stats
        print("\n[Downloading COS backups for comparison...]")
        temp_cos_dir = self.backup_dir / ".cos_temp"
        temp_cos_dir.mkdir(exist_ok=True)
        
        for cos_backup in cos_backups[:5]:  # Limit to 5 most recent COS backups
            cos_key = cos_backup.get("cos_key")
            if not cos_key:
                continue
            
            temp_path = temp_cos_dir / cos_backup["filename"]
            if not temp_path.exists():
                success, msg = self.download_cos_backup(cos_key, temp_path)
                if success:
                    logger.info(f"[Recovery] {msg}")
                    # Get stats for downloaded backup
                    stats = self.get_database_stats(temp_path)
                    cos_backup.update(stats)
                    cos_backup["path"] = str(temp_path)
                    cos_backup["downloaded"] = True
                else:
                    logger.warning(f"[Recovery] Failed to download COS backup {cos_key}: {msg}")
            else:
                # Already downloaded, just get stats
                stats = self.get_database_stats(temp_path)
                cos_backup.update(stats)
                cos_backup["path"] = str(temp_path)
                cos_backup["downloaded"] = True
        
        # Combine all backups (local + COS)
        all_backups = local_backups + cos_backups
        healthy_backups = [b for b in all_backups if b.get("healthy") and b.get("path")]
        
        # Detect anomalies between backups
        anomalies = self.detect_anomalies(healthy_backups)
        
        # Print comparison with anomalies
        self.print_comparison(current_stats, all_backups, anomalies)
        
        if not healthy_backups:
            print("\nERROR: No healthy backups available for recovery!")
            print("Options:")
            print("  [C] Continue anyway (data may be lost)")
            print("  [D] Delete corrupted database and start fresh")
            print("  [Q] Quit application")
            
            while True:
                choice = input("\nYour choice (C/D/Q): ").strip().upper()
                
                if choice == "C":
                    print("\nWARNING: Continuing with corrupted database may cause errors!")
                    return True
                elif choice == "D":
                    if self.db_path and self.db_path.exists():
                        # Backup corrupted file first
                        corrupted_backup = self.db_path.parent / f"{self.db_path.name}.corrupted.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                        shutil.move(str(self.db_path), str(corrupted_backup))
                        print(f"\nCorrupted database moved to: {corrupted_backup}")
                        print("A fresh database will be created on startup.")
                    return True
                elif choice == "Q":
                    print("\nApplication startup aborted.")
                    return False
                else:
                    print("Invalid choice. Please enter C, D, or Q.")
        
        # Check if merge option should be offered (anomalies detected)
        can_merge = len(healthy_backups) >= 2 and any(a.get("table") == "users" for a in anomalies)
        
        # Healthy backups available
        print("\nOptions:")
        for i, backup in enumerate(healthy_backups, 1):
            source = backup.get("source", "local").upper()
            users = backup.get("tables", {}).get("users", "?")
            size_mb = backup.get("size_mb", 0)
            print(f"  [{i}] Restore from {backup['filename']} ({source}, {users} users, {size_mb} MB)")
        
        if can_merge:
            print(f"  [M] MERGE backups (combine data from multiple backups)")
        
        print(f"  [C] Continue anyway (not recommended)")
        print(f"  [Q] Quit application")
        
        while True:
            choice = input("\nYour choice: ").strip().upper()
            
            if choice == "C":
                print("\nWARNING: Continuing with corrupted database may cause errors!")
                confirm = input("Are you sure? (yes/no): ").strip().lower()
                if confirm == "yes":
                    return True
                continue
            elif choice == "Q":
                print("\nApplication startup aborted.")
                return False
            elif choice == "M" and can_merge:
                # Merge mode
                return self._interactive_merge(healthy_backups)
            else:
                try:
                    idx = int(choice)
                    if 1 <= idx <= len(healthy_backups):
                        backup = healthy_backups[idx - 1]
                        
                        # Determine backup path (local or downloaded COS)
                        if backup.get("source") == "cos":
                            backup_path = Path(backup.get("path", ""))
                            if not backup_path or not backup_path.exists():
                                # Need to download it
                                cos_key = backup.get("cos_key")
                                if cos_key:
                                    temp_cos_dir = self.backup_dir / ".cos_temp"
                                    temp_cos_dir.mkdir(exist_ok=True)
                                    backup_path = temp_cos_dir / backup["filename"]
                                    success, msg = self.download_cos_backup(cos_key, backup_path)
                                    if not success:
                                        print(f"\nFailed to download COS backup: {msg}")
                                        continue
                                else:
                                    print(f"\nCannot restore: COS backup key not found")
                                    continue
                        else:
                            backup_path = self.backup_dir / backup["filename"]
                        
                        print(f"\nRestoring from: {backup['filename']} ({backup.get('source', 'local').upper()})")
                        print(f"  Size: {backup['size_mb']} MB")
                        print(f"  Modified: {backup['modified']}")
                        print(f"  Users: {backup.get('tables', {}).get('users', '?')}")
                        
                        confirm = input("\nConfirm restore? (yes/no): ").strip().lower()
                        if confirm == "yes":
                            success, msg = self.restore_from_backup(backup_path)
                            if success:
                                print(f"\n{msg}")
                                print("Database restored successfully. Continuing startup...")
                                
                                # Clean up temporary COS downloads
                                temp_cos_dir = self.backup_dir / ".cos_temp"
                                if temp_cos_dir.exists():
                                    try:
                                        shutil.rmtree(temp_cos_dir)
                                    except Exception:
                                        pass
                                
                                return True
                            else:
                                print(f"\nRestore failed: {msg}")
                                continue
                        continue
                except ValueError:
                    pass
                
                valid_options = f"1-{len(healthy_backups)}, M, C, or Q" if can_merge else f"1-{len(healthy_backups)}, C, or Q"
                print(f"Invalid choice. Please enter {valid_options}.")
    
    def _interactive_merge(self, healthy_backups: List[Dict]) -> bool:
        """
        Interactive merge wizard - combine data from multiple backups.
        
        Args:
            healthy_backups: List of healthy backup stats
            
        Returns:
            True if merge succeeded, False to abort
        """
        print("\n" + "=" * 80)
        print("MERGE BACKUPS - Combine data from multiple backups")
        print("=" * 80)
        
        print("\nThis will:")
        print("  1. Use the backup with MORE data as the base")
        print("  2. Add any NEW records from the backup with fewer records")
        print("  3. Result: Combined data from both backups")
        
        # Find the backup with most users (likely the one before data loss)
        backups_with_users = [(b, b.get("tables", {}).get("users", 0)) for b in healthy_backups]
        backups_with_users.sort(key=lambda x: x[1] if isinstance(x[1], int) else 0, reverse=True)
        
        if len(backups_with_users) < 2:
            print("\nNeed at least 2 healthy backups to merge.")
            return False
        
        base_backup = backups_with_users[0][0]
        newer_backup = backups_with_users[1][0]
        
        # If the second one is newer in time, swap interpretation
        if newer_backup.get("modified", "") > base_backup.get("modified", ""):
            # newer_backup is actually more recent, use it for new records
            pass
        else:
            # base_backup is more recent but has more data, use newer_backup for new records
            newer_backup = backups_with_users[1][0]
        
        print(f"\nMerge plan:")
        print(f"  BASE (more data):   {base_backup['filename']} ({base_backup['tables'].get('users', '?')} users)")
        print(f"  ADD NEW FROM:       {healthy_backups[0]['filename']} ({healthy_backups[0]['tables'].get('users', '?')} users)")
        
        confirm = input("\nProceed with merge? (yes/no): ").strip().lower()
        if confirm != "yes":
            return False
        
        # Perform merge
        base_path = self.backup_dir / base_backup["filename"]
        newer_path = self.backup_dir / healthy_backups[0]["filename"]
        
        # Ensure data directory exists
        if self.db_path:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        print("\nMerging backups...")
        success, msg, stats = self.merge_backups(base_path, newer_path, self.db_path)
        
        if success:
            print(f"\n{msg}")
            print(f"  Final user count: {stats.get('final_user_count', '?')}")
            if stats.get("tables_merged"):
                print(f"  New records added:")
                for table, count in stats["tables_merged"].items():
                    print(f"    - {table}: {count} new records")
            print("\nDatabase merge completed. Continuing startup...")
            return True
        else:
            print(f"\nMerge failed: {msg}")
            return False


def check_database_on_startup() -> bool:
    """
    Check database integrity on startup.
    Called by main.py during lifespan initialization.
    
    IMPORTANT: When corruption is detected, this function ALWAYS requires
    human intervention. It will NOT automatically restore in non-interactive mode.
    This is a safety measure to prevent data loss from automated decisions.
    
    Returns:
        True if startup should continue, False to abort
    """
    recovery = DatabaseRecovery()
    
    # Quick integrity check
    is_healthy, message = recovery.check_integrity()
    
    if is_healthy:
        logger.debug(f"[Recovery] {message}")
        return True
    
    # Database is corrupted - ALWAYS require human decision
    logger.error(f"[Recovery] DATABASE CORRUPTION DETECTED: {message}")
    
    # Check if we're in interactive mode
    if sys.stdin.isatty():
        # Interactive mode - run recovery wizard
        return recovery.interactive_recovery()
    else:
        # Non-interactive mode (systemd, docker, etc.)
        # DO NOT auto-recover - require manual intervention
        logger.critical("[Recovery] " + "=" * 70)
        logger.critical("[Recovery] DATABASE CORRUPTION DETECTED - MANUAL INTERVENTION REQUIRED")
        logger.critical("[Recovery] " + "=" * 70)
        logger.critical("[Recovery] ")
        logger.critical("[Recovery] The database is corrupted and requires manual recovery.")
        logger.critical("[Recovery] Automatic recovery is DISABLED for safety - you must decide.")
        logger.critical("[Recovery] ")
        logger.critical("[Recovery] To recover, run the application interactively:")
        logger.critical("[Recovery]   1. Stop the service: sudo systemctl stop mindgraph")
        logger.critical("[Recovery]   2. Run manually: python run_server.py")
        logger.critical("[Recovery]   3. Follow the recovery wizard prompts")
        logger.critical("[Recovery]   4. After recovery, restart the service")
        logger.critical("[Recovery] ")
        
        # List available backups in logs for reference
        backups = recovery.list_backups()
        healthy_backups = [b for b in backups if b["healthy"]]
        
        if healthy_backups:
            logger.critical("[Recovery] Available healthy backups:")
            for backup in healthy_backups:
                users = backup.get("tables", {}).get("users", "?")
                logger.critical(f"[Recovery]   - {backup['filename']} ({users} users, {backup['size_mb']} MB)")
        else:
            logger.critical("[Recovery] WARNING: No healthy backups found in backup/ directory!")
        
        logger.critical("[Recovery] ")
        logger.critical("[Recovery] " + "=" * 70)
        logger.critical("[Recovery] Application startup ABORTED - manual recovery required")
        logger.critical("[Recovery] " + "=" * 70)
        
        return False


def get_recovery_status() -> Dict[str, Any]:
    """
    Get current database and backup status.
    For API/admin panel use.
    
    Returns:
        dict with database health and backup info
    """
    recovery = DatabaseRecovery()
    
    is_healthy, message = recovery.check_integrity()
    current_stats = recovery.get_database_stats(recovery.db_path) if recovery.db_path else {}
    backups = recovery.list_backups()
    
    return {
        "database_healthy": is_healthy,
        "database_message": message,
        "database_stats": current_stats,
        "backups": backups,
        "healthy_backups_count": len([b for b in backups if b["healthy"]])
    }

