# Database Backup Guide for WAL Mode SQLite

## ⚠️ Important: Why NOT to Copy All Three Files

**DO NOT** simply copy `.db`, `.shm`, and `.wal` files together. This is **unsafe** because:

1. **WAL files contain uncommitted transactions** - copying them separately can lead to inconsistent state
2. **SHM files are shared memory** - they're temporary and shouldn't be copied
3. **File copying is not atomic** - the database state can change between copying files
4. **The backup may be corrupted** - you might get a database that won't open or has missing data

## ✅ Safe Backup Methods

### ⚡ IMPORTANT: Can Run While Application is Running!

**You do NOT need to stop the server!** SQLite's backup API safely handles active databases in WAL mode. The backup will include all committed transactions up to the moment the backup starts.

### Method 1: Using Upgraded backup_database.py Script (Recommended)

The upgraded `backup_database.py` script works in two modes:

#### Mode 1: Auto-detect (when config is available)
```bash
# Just run it - no arguments needed!
python scripts/backup_database.py
# Automatically finds database from config, saves to /backup/
```

#### Mode 2: Standalone (on old server without config)
```bash
# Copy script to server
scp scripts/backup_database.py user@server:/tmp/

# Run with --source flag (only needed if config unavailable)
python3 /tmp/backup_database.py --source /data/mindgraph.db
# Saves to /backup/mindgraph.db.TIMESTAMP automatically

# Or specify custom backup directory
python3 /tmp/backup_database.py --source /data/mindgraph.db --backup-dir /backup
```

**When do you need `--source`?**
- ✅ **NEED IT**: On old server where script can't read config
- ❌ **DON'T NEED IT**: On server with full codebase (script auto-detects)

**When do you need `--backup-dir`?**
- ✅ **NEED IT**: If you want backups in different location than `/backup`
- ❌ **DON'T NEED IT**: If `/backup` is fine (default)

### Method 2: Using SQLite Command-Line Tool

If `sqlite3` is installed on your Ubuntu server:

```bash
# Method 2a: Using .backup command (SQLite 3.8.8+)
sqlite3 /data/mindgraph.db ".backup /backup/mindgraph.db.backup"

# Method 2b: Using .dump and restore (works on older SQLite)
sqlite3 /data/mindgraph.db ".dump" | sqlite3 /backup/mindgraph.db.backup
```

**Note:** The `.backup` command automatically handles WAL checkpointing.

### Method 3: Using Python One-Liner

If you have Python 3.7+ on the server:

```bash
python3 << 'EOF'
import sqlite3
from datetime import datetime

source = "/data/mindgraph.db"
backup = f"/backup/mindgraph.db.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

src_conn = sqlite3.connect(source, timeout=30.0)
dst_conn = sqlite3.connect(backup, timeout=30.0)

backup_obj = src_conn.backup(dst_conn)
backup_obj.step(-1)
backup_obj.finish()

dst_conn.close()
src_conn.close()

print(f"Backup completed: {backup}")
EOF
```

### Method 4: Checkpoint Then Copy (NOT RECOMMENDED - Only if backup API unavailable)

**⚠️ Only use this if SQLite backup API is not available (very rare):**

```bash
# 1. Stop the MindGraph server (downtime required!)
systemctl stop mindgraph

# 2. Checkpoint WAL file (merge WAL into main database)
sqlite3 /data/mindgraph.db "PRAGMA wal_checkpoint(TRUNCATE);"

# 3. Now it's safe to copy just the .db file
cp /data/mindgraph.db /backup/mindgraph.db.backup

# 4. Restart server
systemctl start mindgraph
```

**Note:** This method requires stopping the server and causes downtime. Use Methods 1-3 instead - they work while the server is running!

## 📋 Quick Reference

### What Files Exist?

```bash
# Check what database files exist
ls -lh /data/mindgraph.db*

# You might see:
# - mindgraph.db      (main database file)
# - mindgraph.db-wal  (Write-Ahead Log - contains uncommitted changes)
# - mindgraph.db-shm  (Shared Memory - temporary file)
```

### Verify Backup

After creating a backup, verify it:

```bash
# Check backup integrity
sqlite3 /backup/mindgraph.db.backup "PRAGMA integrity_check;"

# Should output: "ok"
```

### Transfer Backup Off Server

```bash
# Copy backup to local machine
scp user@server:/backup/mindgraph.db.backup ./

# Or use rsync
rsync -avz user@server:/backup/mindgraph.db.backup ./
```

## 🔍 Troubleshooting

### Error: "database is locked"

The database is in use. Options:
1. Use the backup API (methods above) - it handles locks automatically
2. Stop the server temporarily
3. Increase timeout: `sqlite3.connect(..., timeout=60.0)`

### Error: "unable to open database file"

Check permissions:
```bash
# Check file permissions
ls -l /data/mindgraph.db

# Fix permissions if needed
sudo chown user:user /data/mindgraph.db
sudo chmod 644 /data/mindgraph.db
```

### Error: "disk I/O error"

Check disk space:
```bash
df -h /data
df -h /backup
```

## 📝 Summary

**✅ DO:**
- Use SQLite backup API (Python script or `.backup` command)
- Verify backup integrity after creation
- Keep backups in a separate location

**❌ DON'T:**
- Copy `.db`, `.wal`, and `.shm` files separately
- Copy database files while server is running (unless using backup API)
- Use `cp` or `rsync` directly on WAL-mode databases

## 🎯 Recommended Workflow

### For Server with Full Codebase:
```bash
# Just run it - no arguments needed!
python scripts/backup_database.py
# Creates: /backup/mindgraph.db.20251211_011839
```

### For Old Server (Standalone):
```bash
# Copy script to server
scp scripts/backup_database.py user@server:/tmp/

# Run with source path
python3 /tmp/backup_database.py --source /data/mindgraph.db
# Creates: /backup/mindgraph.db.20251211_011839
```

### Verify Backup:
```bash
# Using the script's verify option
python3 backup_database.py --verify /backup/mindgraph.db.20251211_011839

# Or manually
sqlite3 /backup/mindgraph.db.20251211_011839 "PRAGMA integrity_check;"
```

### Transfer to Safe Location:
```bash
scp user@server:/backup/mindgraph.db.* ./backups/
```

## ❓ FAQ

### Q: Do I need to stop the server?
**A: NO!** The backup script uses SQLite's backup API which safely handles active databases. You can run backups while the application is running.

### Q: When do I need `--source`?
**A: Only if the script can't auto-detect the database path.** This happens on old servers where the config module isn't available. On servers with the full codebase, just run `python scripts/backup_database.py` without arguments.

### Q: When do I need `--backup-dir`?
**A: Only if you want backups in a different location.** Default is `/backup/` which works for most cases.

### Q: Can I run backups while users are active?
**A: YES!** SQLite's backup API is designed for this. It creates a consistent snapshot of all committed data.

