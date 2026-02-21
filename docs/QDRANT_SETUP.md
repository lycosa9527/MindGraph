# Qdrant Setup Guide for Ubuntu

## Quick Install (Recommended)

Run the automated install script from your MindGraph project directory:

```bash
# Python entry point (recommended - works on Windows, WSL, Linux)
# Use full path when using conda (sudo does not inherit conda PATH):
sudo $(which python) scripts/setup/install_qdrant.py

# Or use system python3:
sudo python3 scripts/setup/install_qdrant.py

# Or use the shell wrapper
sudo bash scripts/setup/install_qdrant.sh
```

**Conda users**: Run `sudo $(which python) scripts/setup/install_qdrant.py` so sudo finds your conda Python.

**WSL / Windows users**: Use the Python entry point to avoid line-ending issues when the repo is on a Windows drive.

### What the script does:

1. **Downloads** the latest Qdrant release from GitHub
2. **Installs** to `~/qdrant/`
3. **Creates** a systemd service for auto-start
4. **Starts** Qdrant on port 6333
5. **Updates** your `.env` file with `QDRANT_HOST=localhost:6333`

### Expected output:

```
========================================
  Qdrant Installation Script
  MindGraph Vector Database Setup
========================================

Step 1: Creating directories...
[OK] Created /home/user/qdrant

Step 2: Downloading latest Qdrant...
[OK] Download complete

Step 3: Extracting...
[OK] Extracted and set permissions

Step 4: Creating systemd service...
[OK] Created systemd service

Step 5: Starting Qdrant service...
[OK] Service started

Step 6: Verifying installation...
[OK] Qdrant is running on port 6333
[OK] Installed version: 1.13.0

Step 7: Updating .env file...
[OK] Added QDRANT_HOST to .env

========================================
  Installation Complete!
========================================

Qdrant is running on: http://localhost:6333
Dashboard URL: http://localhost:6333/dashboard
```

### After installation:

Restart MindGraph to enable background processing:

```bash
python main.py
```

You should see:
```
[Qdrant] Connecting to server: localhost:6333
[CELERY] Starting Celery worker for background task processing...
```

### Upgrade to latest version:

Simply run the script again - it will detect the existing installation and prompt you:

```bash
python scripts/setup/install_qdrant.py
```

---

## Why Qdrant Server? Concurrent Access for Background Processing

Qdrant Server mode is required for MindGraph's RAG feature when using Celery background workers:

### Why Server Mode vs Embedded Mode

| Mode | Pros | Cons |
|------|------|------|
| **Embedded** (default) | No setup required, works out of box | Single process only, no Celery support |
| **Server** (recommended) | Multi-process support, Celery workers, Web UI | Requires setup |

### Benefits of Qdrant Server

1. **Concurrent Access**: Both FastAPI and Celery workers can access vectors simultaneously
2. **Background Processing**: Documents process in background while users continue working
3. **Progress Bar**: Real-time progress updates (Extracting -> Chunking -> Embedding -> Indexing)
4. **Web Dashboard**: Visual UI at `http://localhost:6333/dashboard` to inspect collections
5. **Better Performance**: Optimized for production workloads

## Manual Installation (Alternative)

If you prefer to install manually instead of using the script, follow these steps.
Download and run Qdrant directly on Ubuntu. Always use the latest version.

**Step 1: Download latest Qdrant**

```bash
# Check latest version at https://github.com/qdrant/qdrant/releases
# As of Jan 2026, latest is 1.13.x - always check for newer versions

cd ~
mkdir -p qdrant && cd qdrant

# Download latest release (update version number as needed)
wget https://github.com/qdrant/qdrant/releases/latest/download/qdrant-x86_64-unknown-linux-gnu.tar.gz

# Extract
tar -xzf qdrant-x86_64-unknown-linux-gnu.tar.gz

# Make executable
chmod +x qdrant
```

**Step 2: Create data directory**

```bash
mkdir -p ~/qdrant/storage
```

**Step 3: Test run**

```bash
cd ~/qdrant
./qdrant
```

You should see:
```
[INFO] Qdrant is running on 0.0.0.0:6333
```

Press `Ctrl+C` to stop, then continue to Step 4.

**Step 4: Create systemd service**

```bash
sudo tee /etc/systemd/system/qdrant.service > /dev/null <<EOF
[Unit]
Description=Qdrant Vector Database
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$HOME/qdrant
ExecStart=$HOME/qdrant/qdrant
Restart=always
RestartSec=10
Environment="QDRANT__STORAGE__STORAGE_PATH=$HOME/qdrant/storage"

[Install]
WantedBy=multi-user.target
EOF
```

**Step 5: Enable and start service**

```bash
sudo systemctl daemon-reload
sudo systemctl enable qdrant
sudo systemctl start qdrant
```

**Step 6: Verify installation**

```bash
# Check service status
sudo systemctl status qdrant

# Test API
curl http://localhost:6333/collections

# Expected output: {"result":{"collections":[]},"status":"ok","time":...}
```

**Step 7: Configure MindGraph**

Add to your `.env` file:

```bash
QDRANT_HOST=localhost:6333
```

**Step 8: Restart MindGraph**

```bash
python main.py
```

You should see:
```
[Qdrant] Connecting to server: localhost:6333
[CELERY] Starting Celery worker for background task processing...
[CELERY] Worker started (PID: xxxxx)
```

## Managing Qdrant Service

```bash
# Start Qdrant
sudo systemctl start qdrant

# Stop Qdrant
sudo systemctl stop qdrant

# Restart Qdrant
sudo systemctl restart qdrant

# Enable auto-start on boot
sudo systemctl enable qdrant

# Check status
sudo systemctl status qdrant
```

## Verify Installation

```bash
curl http://localhost:6333/collections
```

Expected output: `{"result":{"collections":[...]},"status":"ok",...}`

## View Qdrant Logs

### Real-time logs (follow mode)
```bash
sudo journalctl -u qdrant -f
```

### Recent logs (last 100 lines)
```bash
sudo journalctl -u qdrant -n 100
```

### Logs since today
```bash
sudo journalctl -u qdrant --since today
```

## Configuration

Qdrant runs on `localhost:6333` by default. Configure in your `.env` file:

```bash
# Qdrant server connection
QDRANT_HOST=localhost:6333

# Or use full URL format
# QDRANT_URL=http://localhost:6333

# Collection settings (optional)
QDRANT_COLLECTION_PREFIX=user_
QDRANT_COMPRESSION=SQ8
```

## Web Dashboard

Qdrant includes a built-in web dashboard:

**URL:** http://localhost:6333/dashboard

Features:
- View all collections
- Browse points (vectors) in each collection
- Run similarity searches
- Monitor cluster health

## Update to Latest Version

### Using the install script (easiest)

```bash
python scripts/setup/install_qdrant.py
```

The script detects existing installations and prompts to upgrade.

### Manual upgrade

```bash
# Stop service
sudo systemctl stop qdrant

# Backup current version (optional)
cd ~/qdrant
mv qdrant qdrant.bak

# Download latest
wget https://github.com/qdrant/qdrant/releases/latest/download/qdrant-x86_64-unknown-linux-gnu.tar.gz
tar -xzf qdrant-x86_64-unknown-linux-gnu.tar.gz
chmod +x qdrant

# Start service
sudo systemctl start qdrant

# Verify version
curl http://localhost:6333 | grep version
```

## Data Location

Data is stored in `~/qdrant/storage/`. To backup:

```bash
# Stop Qdrant first
sudo systemctl stop qdrant

# Backup
tar -czvf qdrant_backup_$(date +%Y%m%d).tar.gz ~/qdrant/storage/

# Restore
tar -xzvf qdrant_backup_YYYYMMDD.tar.gz -C ~/

# Start Qdrant
sudo systemctl start qdrant
```

## Troubleshooting

### Service won't start
```bash
# Check logs
sudo journalctl -u qdrant -n 50

# Check permissions
ls -la ~/qdrant/
ls -la ~/qdrant/storage/

# Fix permissions if needed
chmod +x ~/qdrant/qdrant
chmod 755 ~/qdrant/storage
```

### Port already in use
```bash
# Check what's using port 6333
sudo lsof -i :6333

# Kill the process or use a different port
# Edit the systemd service to add: Environment="QDRANT__SERVICE__HTTP_PORT=6335"
```

### MindGraph not connecting
```bash
# Verify Qdrant is running
curl http://localhost:6333/collections

# Check .env file has QDRANT_HOST
grep QDRANT .env

# Restart MindGraph after .env changes: python main.py
```

## Docker Alternative

If you prefer Docker:

```bash
docker run -d \
  --name qdrant \
  -p 6333:6333 \
  -v qdrant_storage:/qdrant/storage \
  --restart unless-stopped \
  qdrant/qdrant
```

## Comparison with Redis

| Feature | Redis | Qdrant |
|---------|-------|--------|
| Purpose | Caching, rate limiting, sessions | Vector storage for RAG |
| Default Port | 6379 | 6333 |
| Service Name | redis-server | qdrant |
| Web UI | No | Yes (dashboard) |
| MindGraph Config | `REDIS_HOST=localhost` | `QDRANT_HOST=localhost:6333` |
| Data Type | Key-value, lists, sets | Vectors with metadata |
| Logs | `journalctl -u redis-server` | `journalctl -u qdrant` |
