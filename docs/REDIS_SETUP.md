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

## Installation

**This is the easiest way to get Redis 8.4 via apt!** Just add the official Redis repository and install.

**Step 1: Install required packages**

```bash
sudo apt-get install lsb-release curl gpg
```

**Step 2: Add official Redis repository**

```bash
# Add Redis GPG key
curl -fsSL https://packages.redis.io/gpg | sudo gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg
sudo chmod 644 /usr/share/keyrings/redis-archive-keyring.gpg

# Add Redis repository
echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/redis.list
```

**Step 3: Update package list and install Redis 8.4**

```bash
sudo apt-get update
sudo apt-get install redis
```

**Or install specific version:**

```bash
sudo apt-get install redis=6:8.4.0-1rl1~$(lsb_release -cs)1
```

**Step 4: Enable and start Redis**

```bash
sudo systemctl enable redis-server
sudo systemctl start redis-server
```

**Step 5: Verify installation**

```bash
redis-cli --version
redis-cli ping  # Should return: PONG
redis-cli INFO server | grep redis_version  # Should show: redis_version:8.4.0
```

**Benefits:**
- ✅ **Easy installation** - Just add repo and apt install
- ✅ Gets Redis 8.4 (latest stable release)
- ✅ Easy to upgrade via `apt upgrade`
- ✅ Native Ubuntu service integration
- ✅ Automatic updates via apt

**Note:** If you have Redis 7.0 installed from Ubuntu repos, it will be upgraded to 8.4. Your data will be preserved.

## Managing Redis Service

```bash
# Start Redis
sudo systemctl start redis-server

# Stop Redis
sudo systemctl stop redis-server

# Restart Redis
sudo systemctl restart redis-server

# Enable auto-start on boot
sudo systemctl enable redis-server

# Check status
sudo systemctl status redis-server
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
