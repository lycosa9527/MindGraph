# MindGraph - Production Deployment Guide

## Quick Start for Multi-Server Deployment

### Prerequisites
- Python 3.8+ (3.13+ recommended for best async performance)
- 2GB+ RAM per server
- Linux (Ubuntu 20.04+ recommended) or Windows Server

### Installation Steps

#### 1. Clone Repository
```bash
git clone <repository-url>
cd MindGraph
```

#### 2. Install Python Dependencies
```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Install all dependencies
pip install -r requirements.txt

# Install Playwright browser binaries
playwright install chromium
```

#### 3. Configure Environment
```bash
# Copy example environment file
cp env.example .env

# Edit .env with your configuration
nano .env  # or use your preferred editor
```

#### 4. Critical Environment Variables

**Required Settings:**
```bash
# Server Configuration
HOST=0.0.0.0
PORT=9527
DEBUG=False  # MUST be False in production

# Qwen API (Required for core functionality)
QWEN_API_KEY=your-actual-api-key-here
QWEN_API_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions

# JWT Security (CHANGE THIS!)
JWT_SECRET_KEY=your-super-secret-jwt-key-min-32-characters-here
JWT_EXPIRY_HOURS=24

# Database
DATABASE_URL=sqlite:///./mindgraph.db  # or PostgreSQL for production
```

**Feature Flags:**
```bash
# Enable/Disable Features
FEATURE_LEARNING_MODE=False
FEATURE_THINKGUIDE=True
FEATURE_MINDMATE=True
FEATURE_VOICE_AGENT=False
```

**Authentication Mode:**
```bash
# Choose one: standard, enterprise, demo
AUTH_MODE=standard

# For demo mode, set passkeys
DEMO_PASSKEY=888888
ADMIN_DEMO_PASSKEY=999999

# Admin phone numbers (comma-separated)
ADMIN_PHONES=13800000000,demo-admin@system.com
```

#### 5. Initialize Database
```bash
# Database migrations (if using Alembic)
alembic upgrade head

# Or just run the application - it will auto-create SQLite database
python run_server.py
```

#### 6. Run Server

**Development/Testing:**
```bash
python run_server.py
```

**Production (with systemd on Linux):**

Create `/etc/systemd/system/mindgraph.service`:
```ini
[Unit]
Description=MindGraph Application
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/mindgraph
Environment="PATH=/opt/mindgraph/venv/bin"
ExecStart=/opt/mindgraph/venv/bin/python run_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable mindgraph
sudo systemctl start mindgraph
sudo systemctl status mindgraph
```

### Multi-Server Deployment Architecture

#### Load Balancer Configuration (Nginx)

```nginx
upstream mindgraph_servers {
    least_conn;  # Use least connections algorithm
    server server1.example.com:9527 max_fails=3 fail_timeout=30s;
    server server2.example.com:9527 max_fails=3 fail_timeout=30s;
    server server3.example.com:9527 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name mindgraph.example.com;

    # WebSocket support
    location / {
        proxy_pass http://mindgraph_servers;
        proxy_http_version 1.1;
        
        # WebSocket headers
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Standard proxy headers
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # SSE streaming support
        proxy_buffering off;
        proxy_cache off;
        
        # Timeouts for long-running connections
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
        proxy_read_timeout 300s;
    }
}
```

### Database Considerations

#### SQLite (Development/Small Deployments)
- Default configuration
- Single server only
- Good for < 100 concurrent users

#### PostgreSQL (Production/Multi-Server)
```bash
# Install PostgreSQL client
pip install psycopg2-binary

# Update .env
DATABASE_URL=postgresql://user:password@db-server:5432/mindgraph
```

**Shared Database Schema:**
- All servers connect to same PostgreSQL instance
- Session management via database
- User authentication shared across servers

### Security Checklist

- [ ] Change `JWT_SECRET_KEY` from default
- [ ] Set `DEBUG=False` in production
- [ ] Use HTTPS (configure reverse proxy SSL)
- [ ] Set up firewall rules (allow only necessary ports)
- [ ] Use strong database passwords
- [ ] Configure `ADMIN_PHONES` for admin access
- [ ] Review `INVITATION_CODES` for controlled registration
- [ ] Enable rate limiting (`DASHSCOPE_RATE_LIMITING_ENABLED=true`)
- [ ] Set up log rotation for `logs/` directory
- [ ] Configure backup strategy for database

### Performance Tuning

#### Uvicorn Workers
```bash
# Set in environment or modify run_server.py
export UVICORN_WORKERS=4  # 1-2 workers per CPU core
```

#### Connection Limits
```python
# Already configured in run_server.py:
limit_concurrency=1000  # Max concurrent connections
timeout_keep_alive=300  # 5 minutes for SSE
```

### Monitoring & Logging

#### Log Files
```bash
# Application logs
tail -f logs/app.log

# Frontend logs
tail -f logs/frontend.log

# System monitoring
journalctl -u mindgraph -f  # systemd logs
```

#### Health Check Endpoints
```bash
# Basic health check
curl http://localhost:9527/health

# Detailed status with metrics
curl http://localhost:9527/status
```

### Troubleshooting

#### Port Already in Use
```bash
# Find process using port
lsof -i :9527  # Linux
netstat -ano | findstr :9527  # Windows

# Kill process
kill -9 <PID>  # Linux
taskkill /F /PID <PID>  # Windows
```

#### Playwright Issues
```bash
# Reinstall browsers
playwright install chromium --force

# Check Playwright status
playwright show-browsers
```

#### Database Connection Issues
```bash
# Test database connection
python -c "from config.database import init_db; init_db()"
```

#### Memory Issues
```bash
# Check memory usage
free -h  # Linux
systemctl status mindgraph  # Check process memory

# Adjust worker count if needed
export UVICORN_WORKERS=2
```

### Backup & Recovery

#### Database Backup (SQLite)
```bash
# Backup
cp mindgraph.db mindgraph.db.backup.$(date +%Y%m%d)

# Restore
cp mindgraph.db.backup.20250101 mindgraph.db
```

#### Environment Backup
```bash
# Backup .env (automatic with admin panel)
ls -la logs/env_backups/

# Manual backup
cp .env .env.backup.$(date +%Y%m%d)
```

### Updates & Maintenance

#### Update Application
```bash
# Stop service
sudo systemctl stop mindgraph

# Pull latest code
git pull origin main

# Update dependencies
pip install -r requirements.txt --upgrade

# Run migrations if needed
alembic upgrade head

# Restart service
sudo systemctl start mindgraph
```

#### Zero-Downtime Updates (Multi-Server)
```bash
# Update servers one at a time
# 1. Remove server1 from load balancer
# 2. Update server1
# 3. Add server1 back to load balancer
# 4. Repeat for other servers
```

### Support & Contact

- **Author:** lycosa9527
- **Team:** MindSpring Team (MTEL, Beijing Normal University)
- **License:** AGPLv3

### Additional Resources

- API Documentation: http://your-server:9527/docs
- Admin Panel: http://your-server:9527/admin
- Editor Interface: http://your-server:9527/editor


