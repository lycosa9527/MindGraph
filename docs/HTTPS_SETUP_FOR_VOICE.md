# HTTPS Setup Guide for Voice Input

## Why HTTPS is Required

Browsers require a **secure context (HTTPS)** for `getUserMedia()` API (microphone access) except for:
- `localhost`
- `127.0.0.1`
- `file://` URLs

**IP addresses accessed over HTTP will NOT work** for microphone access.

---

## Solutions

### Option 1: Use HTTPS with Reverse Proxy (Recommended for Production)

#### Using Nginx + Let's Encrypt (Free SSL)

1. **Install Nginx and Certbot:**
   ```bash
   sudo apt update
   sudo apt install nginx certbot python3-certbot-nginx
   ```

2. **Create Nginx Configuration** (`/etc/nginx/sites-available/mindgraph`):
   ```nginx
   server {
       listen 80;
       server_name your-domain.com;  # Or your IP if you have a domain
       
       # Redirect HTTP to HTTPS
       return 301 https://$server_name$request_uri;
   }

   server {
       listen 443 ssl http2;
       server_name your-domain.com;

       # SSL Configuration (will be auto-configured by certbot)
       ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
       
       # SSL Settings
       ssl_protocols TLSv1.2 TLSv1.3;
       ssl_ciphers HIGH:!aNULL:!MD5;
       ssl_prefer_server_ciphers on;

       # Proxy to FastAPI app
       location / {
           proxy_pass http://127.0.0.1:9527;
           proxy_http_version 1.1;
           proxy_set_header Upgrade $http_upgrade;
           proxy_set_header Connection "upgrade";
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
           
           # WebSocket support
           proxy_set_header Connection "upgrade";
           proxy_read_timeout 86400;
       }
   }
   ```

3. **Enable the site:**
   ```bash
   sudo ln -s /etc/nginx/sites-available/mindgraph /etc/nginx/sites-enabled/
   sudo nginx -t  # Test configuration
   sudo systemctl reload nginx
   ```

4. **Get SSL Certificate:**
   ```bash
   sudo certbot --nginx -d your-domain.com
   ```

5. **Auto-renewal (certbot sets this up automatically):**
   ```bash
   sudo certbot renew --dry-run  # Test renewal
   ```

---

### Option 2: Self-Signed Certificate (For Testing)

**Warning:** Browsers will show a security warning, but you can proceed.

1. **Generate self-signed certificate:**
   ```bash
   sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
       -keyout /etc/ssl/private/mindgraph.key \
       -out /etc/ssl/certs/mindgraph.crt
   ```

2. **Update Nginx config** (use the config above but point to these cert files)

3. **Access via HTTPS:** `https://82.157.39.177:9527`
   - Browser will warn about self-signed cert
   - Click "Advanced" → "Proceed anyway"

---

### Option 3: Use localhost for Testing

If testing locally, use `localhost` instead of IP:

```bash
# On server
python run_server.py

# Access via: http://localhost:9527
# This works because localhost is exempt from HTTPS requirement
```

---

### Option 4: Use ngrok (Quick Testing Solution)

1. **Install ngrok:**
   ```bash
   # Download from https://ngrok.com/download
   # Or use snap:
   sudo snap install ngrok
   ```

2. **Create HTTPS tunnel:**
   ```bash
   ngrok http 9527
   ```

3. **Use the HTTPS URL provided by ngrok** (e.g., `https://abc123.ngrok.io`)

**Note:** Free tier has limitations (session timeout, random URLs)

---

### Option 5: Update FastAPI to Support HTTPS Directly

You can configure Uvicorn to use SSL directly:

```python
# In run_server.py or uvicorn_config.py
import ssl

ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ssl_context.load_cert_chain('cert.pem', 'key.pem')

uvicorn.run(
    "main:app",
    host="0.0.0.0",
    port=9527,
    ssl_keyfile="key.pem",
    ssl_certfile="cert.pem"
)
```

---

## Quick Test

After setting up HTTPS, test microphone access:

1. Access site via HTTPS: `https://your-domain.com` or `https://82.157.39.177:9527`
2. Click voice input button
3. Browser should prompt for microphone permission
4. Allow permission
5. Voice input should work!

---

## Troubleshooting

### Browser still blocks microphone:
- Check browser console for errors
- Verify SSL certificate is valid (not expired)
- Check browser permissions: Settings → Privacy → Microphone
- Try incognito mode to rule out extension issues

### Certificate errors:
- Self-signed certs: Accept the warning in browser
- Let's Encrypt: Ensure domain points to your server IP
- Check certificate expiration: `sudo certbot certificates`

### Nginx errors:
- Test config: `sudo nginx -t`
- Check logs: `sudo tail -f /var/log/nginx/error.log`
- Verify FastAPI is running: `curl http://localhost:9527/health`

---

## Recommended Setup for Production

1. **Domain name** (even if just for SSL)
2. **Nginx reverse proxy** with Let's Encrypt SSL
3. **FastAPI on localhost:9527** (not exposed directly)
4. **Firewall** only allows ports 80/443

This provides:
- ✅ HTTPS for microphone access
- ✅ Security (SSL/TLS encryption)
- ✅ Better performance (Nginx handles static files)
- ✅ Easy SSL certificate management (auto-renewal)

---

**Last Updated:** December 2025



