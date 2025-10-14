# Ubuntu Production Server Setup Guide

**Author:** lycosa9527  
**Made by:** MindSpring Team

## Production vs Development Mode

### ⚠️ IMPORTANT: Never Run DEBUG Mode on Production!

The "WATC | 1 change detected" log spam you're seeing is because the server is running in **DEBUG mode** with file auto-reload enabled. This creates a feedback loop:

1. Server writes to log file
2. File watcher detects the change
3. Server logs the detection
4. Server writes to log file again
5. Repeat infinitely → **LOG SPAM**

## Quick Fix for Log Spam

### Step 1: Check Your .env File on Ubuntu

```bash
cat .env | grep DEBUG
```

If you see `DEBUG=True`, that's the problem!

### Step 2: Set Production Mode

Edit your `.env` file on Ubuntu server:

```bash
nano .env
```

**Change these settings:**

```env
# Production Settings (Ubuntu Server)
DEBUG=False                    # CRITICAL: Must be False in production!
LOG_LEVEL=INFO                # Use INFO or WARNING in production
VERBOSE_LOGGING=False         # Disable verbose logging

# Keep demo mode settings
AUTH_MODE=demo
DEMO_PASSKEY=888888
ADMIN_DEMO_PASSKEY=999999
```

**Do NOT use:**
```env
DEBUG=True                    # ❌ NEVER in production!
VERBOSE_LOGGING=True          # ❌ Creates excessive logs
LOG_LEVEL=DEBUG              # ❌ Too verbose for production
```

### Step 3: Restart Server

```bash
# If using systemd
sudo systemctl restart mindgraph

# If running manually
# Ctrl+C then:
python3 run_server.py
```

### Step 4: Verify Logs Are Clean

```bash
tail -f logs/app.log
```

You should see clean logs without the WATC spam:
```
[12:05:30] INFO  | SRVR | Uvicorn running on http://0.0.0.0:9527
[12:05:31] INFO  | MAIN | Database initialized successfully
[12:05:31] INFO  | MAIN | LLM Service initialized
```

**NOT this:**
```
[12:02:34] INFO  | WATC | 1 change detected
[12:02:34] INFO  | WATC | 1 change detected
[12:02:35] INFO  | WATC | 1 change detected
[12:02:35] INFO  | WATC | 1 change detected
```

## Production .env Template for Ubuntu

Here's a complete production `.env` template:

```env
# =============================================================================
# PRODUCTION CONFIGURATION FOR UBUNTU SERVER
# =============================================================================

# Server Settings
HOST=0.0.0.0
PORT=9527
DEBUG=False                              # MUST be False in production
LOG_LEVEL=INFO                          # INFO or WARNING for production
VERBOSE_LOGGING=False                   # Disable verbose logging

# External Access
EXTERNAL_HOST=your-server-ip-here      # Set your public IP

# API Keys (Required)
QWEN_API_KEY=your-qwen-api-key-here

# Authentication Mode
AUTH_MODE=demo                          # or standard/enterprise
DEMO_PASSKEY=888888                    # Change to secure passkey
ADMIN_DEMO_PASSKEY=999999              # Change to secure passkey

# Database
DATABASE_URL=sqlite:///./mindgraph.db

# JWT Security
JWT_SECRET_KEY=your-super-secret-jwt-key-change-this-in-production-min-32-chars
JWT_EXPIRY_HOURS=24

# Admin Access
ADMIN_PHONES=demo-admin@system.com

# All other settings from env.example...
```

## Why DEBUG=False in Production?

### DEBUG=True (Development Only)
- ✅ Auto-reload on code changes
- ✅ Detailed error messages
- ✅ Hot reload for development
- ❌ Performance overhead
- ❌ Security risk (exposes internals)
- ❌ Log spam from file watcher
- ❌ Memory leaks from reload
- ❌ Not suitable for production

### DEBUG=False (Production)
- ✅ Better performance
- ✅ Secure error messages
- ✅ No file watcher overhead
- ✅ Clean, minimal logs
- ✅ Stable memory usage
- ✅ Production-ready
- ❌ No auto-reload (must restart manually)

## System Service Setup (Recommended)

For production Ubuntu servers, run MindGraph as a systemd service:

### Create Service File

```bash
sudo nano /etc/systemd/system/mindgraph.service
```

```ini
[Unit]
Description=MindGraph AI-Powered Graph Generation
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/MindGraph
Environment="PATH=/path/to/MindGraph/venv/bin"
ExecStart=/path/to/MindGraph/venv/bin/python3 run_server.py
Restart=always
RestartSec=10

# Logging
StandardOutput=append:/path/to/MindGraph/logs/systemd.log
StandardError=append:/path/to/MindGraph/logs/systemd.error.log

[Install]
WantedBy=multi-user.target
```

### Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable mindgraph

# Start the service
sudo systemctl start mindgraph

# Check status
sudo systemctl status mindgraph

# View logs
journalctl -u mindgraph -f
```

### Service Management Commands

```bash
# Start
sudo systemctl start mindgraph

# Stop
sudo systemctl stop mindgraph

# Restart (after pulling new code)
sudo systemctl restart mindgraph

# Check status
sudo systemctl status mindgraph

# View logs (last 100 lines)
journalctl -u mindgraph -n 100

# Follow logs in real-time
journalctl -u mindgraph -f
```

## Log File Management

### Automatic Log Rotation

Create `/etc/logrotate.d/mindgraph`:

```bash
sudo nano /etc/logrotate.d/mindgraph
```

```
/path/to/MindGraph/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    missingok
    create 0640 your-username your-username
}
```

This will:
- Rotate logs daily
- Keep 7 days of logs
- Compress old logs
- Create new log files automatically

## Performance Monitoring

### Check Server Resources

```bash
# CPU and Memory usage
htop

# Disk usage
df -h

# MindGraph process
ps aux | grep python

# Port usage
sudo lsof -i :9527
```

### Monitor Logs for Issues

```bash
# Watch for errors
tail -f logs/app.log | grep ERROR

# Watch for warnings
tail -f logs/app.log | grep WARN

# Monitor specific component
tail -f logs/app.log | grep AGNT  # Agents
tail -f logs/app.log | grep HTTP  # HTTP requests
tail -f logs/app.log | grep SRVR  # Server events
```

## Security Checklist

- [ ] `DEBUG=False` in production .env
- [ ] Strong `JWT_SECRET_KEY` (32+ characters)
- [ ] Changed default passkeys from 888888/999999
- [ ] Firewall configured (only port 9527 open)
- [ ] `.env` file permissions: `chmod 600 .env`
- [ ] Regular security updates: `sudo apt update && sudo apt upgrade`
- [ ] HTTPS/SSL certificate (if public-facing)
- [ ] Regular database backups

## Firewall Configuration

```bash
# Allow SSH
sudo ufw allow 22

# Allow MindGraph port
sudo ufw allow 9527

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

## Database Backup

```bash
# Create backup directory
mkdir -p backups

# Backup database
cp mindgraph.db backups/mindgraph-$(date +%Y%m%d-%H%M%S).db

# Automated daily backup (crontab)
crontab -e

# Add this line:
0 2 * * * cp /path/to/MindGraph/mindgraph.db /path/to/MindGraph/backups/mindgraph-$(date +\%Y\%m\%d).db
```

## Troubleshooting

### Server Won't Start

```bash
# Check if port is already in use
sudo lsof -i :9527

# Check logs
tail -f logs/app.log

# Check systemd status
sudo systemctl status mindgraph
```

### High Memory Usage

```bash
# Check process memory
ps aux --sort=-%mem | head

# If using DEBUG=True, switch to DEBUG=False
# This will stop the reload watcher
```

### File Watcher Spam (WATC)

**Solution:** Set `DEBUG=False` in `.env` file

The file watcher is only active in DEBUG mode and is not needed in production.

## Update Deployment Workflow

When you push new code to GitHub:

```bash
# On Ubuntu server
cd /path/to/MindGraph

# Pull latest code
git pull

# Restart service (if using systemd)
sudo systemctl restart mindgraph

# Or restart manually
# Ctrl+C (if running in terminal)
# python3 run_server.py
```

## Common Production Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| WATC log spam | DEBUG=True | Set DEBUG=False |
| Memory leak | DEBUG=True reload | Set DEBUG=False |
| Slow performance | DEBUG=True | Set DEBUG=False |
| "Wrong password" | Whitespace in .env | Use verify_demo_config.py |
| Port in use | Old process | `sudo lsof -i :9527` and kill |
| Permission denied | Wrong file perms | `chmod 600 .env` |

## Best Practices Summary

1. **Always use `DEBUG=False` in production**
2. **Use systemd service for auto-restart**
3. **Monitor logs regularly**
4. **Rotate logs to prevent disk fill**
5. **Backup database regularly**
6. **Keep secrets secure in .env (chmod 600)**
7. **Use strong passkeys and JWT secret**
8. **Configure firewall properly**
9. **Regular security updates**
10. **Test in development before deploying**

---

**Author:** lycosa9527  
**Made by:** MindSpring Team  
**Date:** 2025-10-14

