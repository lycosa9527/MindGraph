# Vue Frontend Setup Guide for Ubuntu

## Prerequisites

The MindGraph frontend requires Node.js 18+ and npm. This guide covers installing Node.js via NodeSource repository for the latest LTS version.

## Installation

### Step 1: Install Node.js 22 LTS

```bash
# Install required packages
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

# Add NodeSource GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg

# Add NodeSource repository (Node.js 22 LTS)
echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" | sudo tee /etc/apt/sources.list.d/nodesource.list

# Install Node.js
sudo apt-get update
sudo apt-get install -y nodejs
```

### Step 2: Verify Installation

```bash
node --version   # Should show v22.x.x
npm --version    # Should show 10.x.x
```

### Step 3: Install Frontend Dependencies

```bash
cd frontend
npm install
```

## Development Server

### Start Development Server

```bash
cd frontend
npm run dev
```

The development server runs on `http://localhost:3000` by default.

### Proxy Configuration

The development server proxies API requests to the backend. Default proxy target is configured in `vite.config.ts`:

| Path | Target |
|------|--------|
| `/api/*` | `http://172.17.230.234:9527` |
| `/ws/*` | `ws://172.17.230.234:9527` |
| `/static/*` | `http://172.17.230.234:9527` |
| `/health` | `http://172.17.230.234:9527` |

To change the backend target, edit `frontend/vite.config.ts`:

```typescript
server: {
  port: 3000,
  proxy: {
    '/api': {
      target: 'http://YOUR_BACKEND_IP:9527',
      changeOrigin: true,
    },
    // ... other proxy rules
  },
},
```

## Production Build

### Build for Production

```bash
cd frontend
npm run build
```

The build output is generated in `frontend/dist/`. These static files can be served by nginx or the FastAPI backend.

### Preview Production Build

```bash
cd frontend
npm run preview
```

This starts a local server to preview the production build before deployment.

## Common Commands

```bash
# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Run linter
npm run lint

# Fix linting issues
npm run lint:fix

# Format code
npm run format

# Check formatting
npm run format:check

# Full check (TypeScript + lint + format)
npm run check

# Fix all issues (lint + format)
npm run fix
```

## Serving with Nginx Proxy Manager (Recommended)

After running `npm run build`, the FastAPI backend automatically serves the Vue frontend from `frontend/dist/`. You only need to configure Nginx Proxy Manager to proxy to the backend.

### Step 1: Build the Frontend

```bash
cd frontend
npm run build
```

### Step 2: Start the Backend

```bash
cd /path/to/MindGraph
nohup python3 run_server.py > output.log 2>&1 &
```

The backend runs on port 9527 and serves both API and frontend.

To check if it's running:

```bash
# View logs
tail -f output.log

# Check process
ps aux | grep run_server

# Check port
ss -tlnp | grep 9527
```

To stop the server:

```bash
pkill -f run_server.py
```

### Step 3: Configure Nginx Proxy Manager

1. Open Nginx Proxy Manager web UI (usually `http://your-server:81`)

2. Go to **Hosts** > **Proxy Hosts** > **Add Proxy Host**

3. Fill in the **Details** tab:

   | Field | Value |
   |-------|-------|
   | Domain Names | `your-domain.com` |
   | Scheme | `http` |
   | Forward Hostname / IP | `127.0.0.1` (or your server IP) |
   | Forward Port | `9527` |
   | Cache Assets | Enabled |
   | Block Common Exploits | Enabled |
   | Websockets Support | **Enabled** (required for streaming) |

4. (Optional) **SSL** tab - Enable SSL with Let's Encrypt:
   - Enable **SSL**
   - Enable **Force SSL**
   - Enable **HTTP/2 Support**
   - Select **Request a new SSL Certificate**
   - Enable **I Agree to the Let's Encrypt Terms of Service**

5. Click **Save**

### Step 4: Verify Deployment

Visit `https://your-domain.com` - you should see the MindGraph interface.

### How It Works

```
Browser → Nginx Proxy Manager → FastAPI (port 9527)
                                    ├── /api/*     → API routes
                                    ├── /ws/*      → WebSocket
                                    ├── /static/*  → Static files
                                    └── /*         → Vue SPA (from dist/)
```

The FastAPI backend handles everything - no separate static file server needed.

---

## Serving with Nginx (Alternative)

For production deployments without Nginx Proxy Manager:

### Step 1: Install Nginx

```bash
sudo apt-get install nginx
```

### Step 2: Configure Nginx

Create `/etc/nginx/sites-available/mindgraph`:

```nginx
server {
    listen 80;
    server_name your-domain.com;
    root /path/to/MindGraph/frontend/dist;
    index index.html;

    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

    # Frontend static files
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Proxy API requests to backend
    location /api {
        proxy_pass http://127.0.0.1:9527;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support
    location /ws {
        proxy_pass http://127.0.0.1:9527;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    # Static files from backend
    location /static {
        proxy_pass http://127.0.0.1:9527;
        proxy_set_header Host $host;
    }
}
```

### Step 3: Enable Site

```bash
sudo ln -s /etc/nginx/sites-available/mindgraph /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## Managing Nginx Service

```bash
# Start nginx
sudo systemctl start nginx

# Stop nginx
sudo systemctl stop nginx

# Restart nginx
sudo systemctl restart nginx

# Reload config without restart
sudo systemctl reload nginx

# Enable auto-start on boot
sudo systemctl enable nginx

# Check status
sudo systemctl status nginx
```

## Troubleshooting

### Node.js Version Too Old

If `node --version` shows a version below 18:

```bash
# Remove old Node.js
sudo apt-get remove nodejs

# Follow Step 1 again to install Node.js 22 LTS
```

### Permission Errors with npm

If you encounter EACCES permission errors:

```bash
# Fix npm permissions (recommended)
mkdir -p ~/.npm-global
npm config set prefix '~/.npm-global'
echo 'export PATH=~/.npm-global/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

### Port 3000 Already in Use

If port 3000 is already in use:

```bash
# Find process using port 3000
sudo lsof -i :3000

# Kill the process
kill -9 <PID>

# Or change the dev server port in vite.config.ts
```

### Build Fails with TypeScript Errors

```bash
# Check for TypeScript errors
npm run check

# If errors exist, fix them before building
```

### Clear Node Modules and Reinstall

If you encounter dependency issues:

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

## View Frontend Logs

### Development Server Logs

The development server outputs logs directly to the terminal. For background processes:

```bash
# Run dev server in background and log to file
npm run dev > dev.log 2>&1 &

# View logs
tail -f dev.log
```

### Nginx Access Logs

```bash
# Real-time access logs
sudo tail -f /var/log/nginx/access.log

# Real-time error logs
sudo tail -f /var/log/nginx/error.log
```
