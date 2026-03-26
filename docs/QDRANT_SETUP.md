# Qdrant Setup Guide for Ubuntu

## Quick Install (Recommended)

Qdrant installation is built into the MindGraph setup script (Linux with systemd). From the project root:

```bash
# Use the same Python you use for the project (conda: sudo does not inherit PATH)
sudo $(which python3) scripts/setup/setup.py

# Or system Python:
sudo python3 scripts/setup/setup.py
```

**Conda users**: Use `sudo $(which python3) scripts/setup/setup.py` so sudo resolves your conda interpreter.

**Non-Linux**: Run setup for other steps; Qdrant server auto-install targets Linux. On Windows or macOS use Docker, WSL, or a manual/binary install (sections below).

When `setup.py` asks, you can skip installing the Qdrant server if you use your own instance.

### What the setup script does for Qdrant (Linux):

1. **Downloads** a pinned Qdrant release from GitHub (see `QDRANT_GITHUB_VERSION` in `scripts/setup/setup.py`)
2. **Installs** the binary to `/usr/local/bin/qdrant`
3. **Writes** `/etc/qdrant/config.yaml` with storage under `/var/lib/qdrant/`
4. **Creates** a `qdrant` systemd unit and starts the service
5. **Ensures** the `qdrant-client` Python package via pip
6. You should set **`QDRANT_HOST=localhost:6333`** in `.env` (see `env.example`)

### Expected output:

Setup runs several steps; for Qdrant you should see log lines similar to:

```
============================================================
  Qdrant vector database (GitHub release + systemd)
============================================================
...
[SUCCESS] Qdrant is running — API http://127.0.0.1:6333  gRPC 127.0.0.1:6334
```

Add `QDRANT_HOST=localhost:6333` to `.env` yourself if it is not already set (see `env.example`). Dashboard: http://localhost:6333/dashboard

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

Bump `QDRANT_GITHUB_VERSION` in `scripts/setup/setup.py` if needed, then re-run setup as root so the new binary and service are applied:

```bash
sudo python3 scripts/setup/setup.py
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

### Using setup (easiest on Linux)

```bash
sudo python3 scripts/setup/setup.py
```

Adjust `QDRANT_GITHUB_VERSION` in `scripts/setup/setup.py` when you want a newer upstream release.

### Manual upgrade (home-directory install)

If you installed under `~/qdrant` (manual section below), replace the binary there and restart the service.

### Manual upgrade (MindGraph setup paths: `/usr/local/bin`, `/var/lib/qdrant`)

```bash
# Stop service
sudo systemctl stop qdrant

# Backup current binary (optional)
sudo cp /usr/local/bin/qdrant /usr/local/bin/qdrant.bak

# Download and extract a new release (pick arch + version from GitHub)
cd /tmp
wget https://github.com/qdrant/qdrant/releases/latest/download/qdrant-x86_64-unknown-linux-gnu.tar.gz
tar -xzf qdrant-x86_64-unknown-linux-gnu.tar.gz
sudo install -m 755 qdrant /usr/local/bin/qdrant

# Start service
sudo systemctl start qdrant

# Verify
curl -s http://localhost:6333/collections
```

## Data Location

**MindGraph automated install (recommended):** vectors and snapshots live under **`/var/lib/qdrant/storage`** and **`/var/lib/qdrant/snapshots`** (see `/etc/qdrant/config.yaml`).

**Manual install (below):** data may live under **`~/qdrant/storage/`** if you configured it that way.

To back up automated-install storage:

```bash
# Stop Qdrant first
sudo systemctl stop qdrant

# Backup
sudo tar -czvf qdrant_backup_$(date +%Y%m%d).tar.gz -C /var/lib/qdrant .

# Restore (example — adjust paths)
# sudo tar -xzvf qdrant_backup_YYYYMMDD.tar.gz -C /var/lib/qdrant

# Start Qdrant
sudo systemctl start qdrant
```

## Troubleshooting

### Service won't start
```bash
# Check logs
sudo journalctl -u qdrant -n 50

# Check permissions (automated install)
ls -la /usr/local/bin/qdrant
ls -la /var/lib/qdrant/
sudo ls -la /etc/qdrant/

# Manual install under home directory
ls -la ~/qdrant/
ls -la ~/qdrant/storage/

# Fix permissions if needed (manual home install)
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
