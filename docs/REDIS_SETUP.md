# Redis Setup Guide for Ubuntu

## Why Upgrade to Redis 8.4? Performance Improvements

Redis 8.4 brings significant performance improvements over Redis 7.0:

### Performance Gains

| Improvement | Benefit | Impact for MindGraph |
|------------|---------|---------------------|
| **87% faster command execution** | Commands execute up to 87% faster | Rate limiting, SMS verification, captcha checks are much faster |
| **2x throughput** | Handles twice the operations per second | Can handle 2x more concurrent users |
| **18% faster replication** | Data sync across nodes is 18% faster | Better for multi-server deployments |
| **16x query processing** | Redis Query Engine is 16x more powerful | Complex queries (sorted sets for rate limiting) are much faster |
| **92% memory reduction** | Optimized storage for strings and arrays | Lower memory usage for SMS codes, captcha storage |

### Technical Improvements

1. **Multi-threaded I/O**: Better handling of concurrent connections
2. **Optimized data structures**: Unified key-value objects reduce memory overhead
3. **Enhanced replication**: Faster data synchronization
4. **Query engine improvements**: Better performance for complex operations

### Real-World Impact

For MindGraph's use cases:
- **Rate limiting**: Up to 87% faster checks (critical for high-traffic scenarios)
- **SMS verification**: Faster GET/SET/DELETE operations
- **Captcha storage**: Lower memory usage (92% reduction possible)
- **Token buffers**: Better list operations performance
- **Activity tracking**: More efficient sorted set operations

**Bottom line**: Redis 8.4 can handle **2x more concurrent users** with **87% faster response times** and **lower memory usage**.

## Upgrading from Redis 7.0 to 8.4

**Important:** You cannot run both Redis 7.0 and Redis 8.4 on the same port (6379) at the same time. You need to choose one method:

### Option A: Use Docker (Recommended - No Uninstall Needed)
- **Keep Redis 7.0 installed** (just stop it)
- Run Redis 8.4 in Docker on the same port
- No data migration needed (if using same data directory)

### Option B: Install from Source (Replace Redis 7.0)
- **Uninstall Redis 7.0** (or disable it)
- Install Redis 8.4 from source
- Migrate data from old Redis to new Redis

See detailed steps below for each option.

## Quick Start - Choose Your Method

| Method | Redis Version | Difficulty | Best For |
|--------|--------------|------------|----------|
| **Docker** | 8.4 (latest) | ⭐ Easy | Production, easy upgrades |
| **From Source** | 8.4 (latest) | ⭐⭐⭐ Medium | Production, native install |
| **apt install** | 7.0.x | ⭐ Easy | Development, quick setup |

**Recommendation:** Use **Docker** for easiest Redis 8.4 installation, or **From Source** if you prefer native Ubuntu service.

## Installation Options

### Option 1: Docker (Recommended - Gets Latest Redis 8.4)

**If you already have Redis 7.0 installed via apt:**

```bash
# Step 1: Stop the existing Redis 7.0 service
sudo systemctl stop redis-server
sudo systemctl disable redis-server  # Prevent auto-start on boot

# Step 2: Start Redis 8.4 via Docker
docker-compose -f docker/docker-compose.yml up -d redis

# Or standalone Docker command
docker run -d \
  --name mindgraph-redis \
  --restart unless-stopped \
  -p 6379:6379 \
  -v redis_data:/data \
  redis:8.4-alpine \
  redis-server --appendonly yes --maxmemory 100mb --maxmemory-policy allkeys-lru
```

**Benefits:**
- ✅ **No need to uninstall Redis 7.0** - just stop it
- ✅ Gets Redis 8.4 (latest stable release)
- ✅ Easy to upgrade/downgrade versions
- ✅ Isolated from system packages
- ✅ Production-ready configuration included
- ✅ Can easily switch back to Redis 7.0 if needed

**Optional - Remove Redis 7.0 later (if you want):**
```bash
# Only if you're sure you won't need Redis 7.0 anymore
sudo apt remove redis-server -y
sudo apt autoremove -y
```

**Note:** Redis 8.4 is the latest stable version. Redis 8.2+ provides excellent performance (35%+ faster than 7.0).

### Option 2: Ubuntu Package Manager (Redis 7.0.x)

```bash
sudo apt update
sudo apt install redis-server -y
```

**Note:** Ubuntu repositories typically provide Redis 7.0.x, not the latest 8.2. For better performance, use Docker (Option 1) or install from source (Option 3).

### Option 3: Install Redis 8.4 from Source (Native Ubuntu Installation)

**Step 1: Stop and backup existing Redis (if installed)**

```bash
# Stop current Redis service
sudo systemctl stop redis-server

# Backup existing data (if you have important data)
sudo cp -r /var/lib/redis /var/lib/redis.backup
```

**Step 2: Remove old Redis 7.0 (Required for source install)**

```bash
# Remove apt-installed Redis 7.0 (keeps data in /var/lib/redis)
sudo apt remove redis-server -y
sudo apt autoremove -y

# Verify it's stopped and removed
sudo systemctl status redis-server  # Should show "not found" or "inactive"
```

**Step 3: Install build dependencies**

```bash
sudo apt update
sudo apt install -y build-essential tcl wget
```

**Step 4: Download and compile Redis 8.4**

```bash
# Download Redis 8.4 (latest stable)
cd /tmp
wget https://download.redis.io/releases/redis-8.4.0.tar.gz
tar xzf redis-8.4.0.tar.gz
cd redis-8.4.0

# Or download latest stable version (always gets the newest)
# wget https://download.redis.io/redis-stable.tar.gz
# tar xzf redis-stable.tar.gz
# cd redis-stable

# Compile Redis
make

# Install binaries to /usr/local/bin
sudo make install
```

**Step 5: Create Redis user and directories**

```bash
# Create Redis system user (if doesn't exist)
sudo adduser --system --group --no-create-home redis 2>/dev/null || true

# Create data directory
sudo mkdir -p /var/lib/redis
sudo chown redis:redis /var/lib/redis

# Create log directory
sudo mkdir -p /var/log/redis
sudo chown redis:redis /var/log/redis

# Create config directory
sudo mkdir -p /etc/redis
```

**Step 6: Create Redis configuration file**

```bash
sudo nano /etc/redis/redis.conf
```

Add this configuration (or copy from `/tmp/redis-8.4.0/redis.conf` and modify):

```conf
# Network
bind 127.0.0.1
port 6379
protected-mode yes

# General
daemonize no
supervised systemd
pidfile /var/run/redis_6379.pid
loglevel notice
logfile /var/log/redis/redis-server.log

# Persistence
dir /var/lib/redis
save 900 1
save 300 10
save 60 10000
appendonly yes
appendfsync everysec

# Memory management
maxmemory 100mb
maxmemory-policy allkeys-lru

# Security (set a password in production)
# requirepass your-strong-password-here
```

**Step 7: Create systemd service file**

```bash
sudo nano /etc/systemd/system/redis.service
```

Add this content:

```ini
[Unit]
Description=Redis In-Memory Data Store
After=network.target

[Service]
User=redis
Group=redis
ExecStart=/usr/local/bin/redis-server /etc/redis/redis.conf
ExecStop=/usr/local/bin/redis-cli shutdown
Restart=always
RestartSec=3
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
```

**Step 8: Set permissions and start Redis**

```bash
# Set ownership of config file
sudo chown redis:redis /etc/redis/redis.conf

# Create PID file directory
sudo mkdir -p /var/run
sudo chown redis:redis /var/run

# Reload systemd and start Redis
sudo systemctl daemon-reload
sudo systemctl enable redis
sudo systemctl start redis
```

**Step 9: Verify installation**

```bash
# Check Redis version
redis-cli --version

# Test connection
redis-cli ping
# Should return: PONG

# Check Redis server info
redis-cli INFO server | grep redis_version
# Should show: redis_version:8.4.0

# Check service status
sudo systemctl status redis
```

**Troubleshooting:**

```bash
# View Redis logs
sudo tail -f /var/log/redis/redis-server.log

# Check if Redis is listening
sudo netstat -tlnp | grep 6379
# Or: sudo ss -tlnp | grep 6379

# Test Redis commands
redis-cli
> SET test "Hello Redis 8.2"
> GET test
> exit
```

## Managing Redis Service

**For apt-installed Redis (service name: `redis-server`):**
```bash
sudo systemctl start redis-server
sudo systemctl enable redis-server
sudo systemctl status redis-server
```

**For source-installed Redis (service name: `redis`):**
```bash
sudo systemctl start redis
sudo systemctl enable redis
sudo systemctl status redis
```

## Verify Installation

```bash
redis-cli ping
```

Expected output: `PONG`

## Configuration

Redis runs on `localhost:6379` by default. Configure in your `.env` file:

```bash
REDIS_URL=redis://localhost:6379/0
```

## Check Status

```bash
sudo systemctl status redis-server
```

**Expected output:**
- `Active: active (running)` - Redis is running
- `enabled` - Auto-start is configured
- `Status: "Ready to accept connections"` - Ready to use
- Listening on `127.0.0.1:6379` - Default port

## View Redis Logs

### Real-time logs (follow mode)
```bash
sudo journalctl -u redis-server -f
```

### Recent logs (last 100 lines)
```bash
sudo journalctl -u redis-server -n 100
```

### Logs since today
```bash
sudo journalctl -u redis-server --since today
```

### Logs with timestamps
```bash
sudo journalctl -u redis-server --since "1 hour ago"
```

### View log file directly (if configured)
```bash
# Default log location (if logfile is set in redis.conf)
sudo tail -f /var/log/redis/redis-server.log

# Or check redis.conf for logfile location
sudo grep "^logfile" /etc/redis/redis.conf
```

## Common Commands

```bash
# Stop Redis
sudo systemctl stop redis-server

# Restart Redis
sudo systemctl restart redis-server

# View Redis logs (real-time)
sudo journalctl -u redis-server -f
```

