# Nginx Reverse Proxy Setup for MindGraph

## Problem

When deploying MindGraph behind a reverse proxy (Nginx Proxy Manager, Caddy, etc.), the application sees all requests coming from the proxy server's IP address instead of the real client IPs. This causes:

- ❌ **Captcha rate limiting triggers immediately** (all users seen as one IP)
- ❌ **Login rate limiting affects all users** (lockouts apply to everyone)
- ❌ **Security features don't work correctly** (IP-based blocking fails)

## Solution

Configure your reverse proxy to pass real client IP addresses using HTTP headers.

---

## Nginx Proxy Manager Configuration

### Method 1: Advanced Tab (Recommended)

1. **Edit your Proxy Host** in Nginx Proxy Manager
2. Go to **Advanced** tab
3. Add to **Custom Nginx Configuration**:

```nginx
# Pass real client IP to backend
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header Host $host;

# Increase timeouts for SSE streaming
proxy_read_timeout 300s;
proxy_connect_timeout 75s;
```

4. **Save** and the changes take effect immediately

### Method 2: Custom Configuration File

If you need more control, create `/data/nginx/custom/http_top.conf`:

```nginx
# Real IP configuration for reverse proxy
set_real_ip_from 0.0.0.0/0;  # Trust all proxies (adjust for your network)
real_ip_header X-Forwarded-For;
real_ip_recursive on;
```

---

## Standard Nginx Configuration

If you're using standard nginx (not Nginx Proxy Manager), add to your server block:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:9527;
        
        # Essential headers for client IP detection
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # SSE streaming support
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
        
        # Timeouts for SSE (5 minutes)
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }
}
```

---

## Cloudflare + Nginx

If using Cloudflare in front of Nginx, add to your nginx config:

```nginx
# Trust Cloudflare IP ranges
set_real_ip_from 173.245.48.0/20;
set_real_ip_from 103.21.244.0/22;
set_real_ip_from 103.22.200.0/22;
set_real_ip_from 103.31.4.0/22;
set_real_ip_from 141.101.64.0/18;
set_real_ip_from 108.162.192.0/18;
set_real_ip_from 190.93.240.0/20;
set_real_ip_from 188.114.96.0/20;
set_real_ip_from 197.234.240.0/22;
set_real_ip_from 198.41.128.0/17;
set_real_ip_from 162.158.0.0/15;
set_real_ip_from 104.16.0.0/13;
set_real_ip_from 104.24.0.0/14;
set_real_ip_from 172.64.0.0/13;
set_real_ip_from 131.0.72.0/22;
set_real_ip_from 2400:cb00::/32;
set_real_ip_from 2606:4700::/32;
set_real_ip_from 2803:f800::/32;
set_real_ip_from 2405:b500::/32;
set_real_ip_from 2405:8100::/32;
set_real_ip_from 2a06:98c0::/29;
set_real_ip_from 2c0f:f248::/32;

# Use CF-Connecting-IP header
real_ip_header CF-Connecting-IP;
```

---

## How MindGraph Detects Client IP

The application automatically checks headers in this order:

1. **X-Forwarded-For** (most common)
   - Format: `client_ip, proxy1, proxy2`
   - Takes **leftmost IP** = original client
   
2. **X-Real-IP** (nginx-specific)
   - Single IP address
   
3. **request.client.host** (fallback)
   - Direct connection IP
   - Used when no proxy headers present

### Code Reference

See `utils/auth.py` - `get_client_ip()` function:

```python
def get_client_ip(request: Request) -> str:
    """Get real client IP, even behind reverse proxy"""
    # Check X-Forwarded-For
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    # Check X-Real-IP
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fallback to direct connection
    return request.client.host
```

---

## Verification

### 1. Check Logs

After configuration, restart your application and check logs:

```bash
tail -f logs/app.log | grep "Client IP"
```

You should see:
```
[DEBUG] Client IP from X-Forwarded-For: 203.0.113.45
```

NOT:
```
[DEBUG] Client IP from request.client.host: 82.157.13.133  # <-- Proxy IP (BAD)
```

### 2. Test Captcha

1. Open MindGraph in browser
2. Refresh captcha multiple times (< 10 times)
3. Should work fine (rate limit per real client IP)

### 3. Check Headers (Browser DevTools)

In browser console:

```javascript
fetch('/api/auth/captcha/generate')
  .then(r => console.log('Success!'))
  .catch(e => console.log('Rate limited'))
```

Check Network tab → Request Headers → should see `X-Forwarded-For`

---

## Troubleshooting

### Issue: Still seeing "Captcha rate limit exceeded"

**Check:**
1. Did you restart nginx after config changes? `systemctl reload nginx`
2. Are headers being passed? Check in logs for "Client IP from X-Forwarded-For"
3. Is there another proxy in front? (CDN, load balancer) - configure those too

### Issue: Getting proxy IP in logs

**Solution:**
- Verify nginx config has `proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;`
- Check `/etc/nginx/nginx.conf` or your proxy host configuration
- Restart nginx: `systemctl restart nginx`

### Issue: Multiple proxies (CDN → Nginx → MindGraph)

The app takes the **leftmost IP** from X-Forwarded-For automatically:

```
X-Forwarded-For: 203.0.113.45, 198.51.100.178, 82.157.13.133
                 ↑ This is used (original client)
```

No additional configuration needed!

---

## Production Checklist

- [ ] Nginx passes `X-Forwarded-For` or `X-Real-IP` headers
- [ ] SSL/TLS enabled with valid certificate
- [ ] SSE timeouts configured (300s recommended)
- [ ] Rate limiting per real client IP (not proxy IP)
- [ ] Logs show real client IPs, not proxy IP
- [ ] Tested captcha generation (no false rate limits)
- [ ] Verified with multiple clients simultaneously

---

## Related Files

- `utils/auth.py` - `get_client_ip()` function
- `routers/auth.py` - Captcha rate limiting
- `env.example` - Reverse proxy configuration notes
- `main.py` - Security headers middleware

---

## Support

If you continue to have issues:

1. Enable debug logging: `LOG_LEVEL=DEBUG` in `.env`
2. Check logs: `tail -f logs/app.log | grep -E "Client IP|rate limit"`
3. Verify nginx config: `nginx -t`
4. Check application is using the helper: Search codebase for `get_client_ip(request)`

---

**Author**: lycosa9527  
**Made by**: MindSpring Team  
**Last Updated**: 2025-10-26

