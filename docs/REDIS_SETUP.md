# Redis Setup Guide for Ubuntu

## Installation

```bash
sudo apt update
sudo apt install redis-server -y
```

## Start Redis Service

```bash
sudo systemctl start redis-server
```

## Enable Auto-Start on Boot

```bash
sudo systemctl enable redis-server
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

