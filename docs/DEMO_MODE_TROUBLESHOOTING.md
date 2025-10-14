# Demo Mode Troubleshooting Guide

**Author:** lycosa9527  
**Made by:** MindSpring Team

## Issue: "Wrong Password" in Demo Mode on Ubuntu Server

### Root Cause Identified

The demo mode passkey verification was failing due to **whitespace in environment variables**. When loading from `.env` files on Ubuntu servers, trailing spaces or newlines can be accidentally included, causing the passkey comparison to fail.

### What Was Fixed

1. **Added `.strip()` to all authentication environment variables:**
   - `AUTH_MODE` - now trimmed and lowercased
   - `DEMO_PASSKEY` - now trimmed
   - `ADMIN_DEMO_PASSKEY` - now trimmed
   - `ENTERPRISE_DEFAULT_ORG_CODE` - now trimmed
   - `ENTERPRISE_DEFAULT_USER_PHONE` - now trimmed

2. **Added client-side whitespace handling:**
   - `verify_demo_passkey()` now strips whitespace from incoming passkeys
   - `is_admin_demo_passkey()` now strips whitespace from incoming passkeys

3. **Enhanced logging for debugging:**
   - Logs passkey length on startup (without revealing actual passkey)
   - Logs received vs expected passkey length during verification
   - Provides helpful error messages about whitespace issues

### Verification Steps on Ubuntu Server

#### Step 1: Check Your `.env` File

On your Ubuntu server, run this command to check for whitespace issues:

```bash
cat -A .env | grep -E "AUTH_MODE|DEMO_PASSKEY|ADMIN_DEMO_PASSKEY"
```

**What to look for:**
- `$` marks the end of each line
- Any spaces before `$` indicate trailing whitespace (BAD)
- Example of **correct** formatting:
  ```
  AUTH_MODE=demo$
  DEMO_PASSKEY=888888$
  ADMIN_DEMO_PASSKEY=999999$
  ```

- Example of **incorrect** formatting (note spaces before `$`):
  ```
  AUTH_MODE=demo   $
  DEMO_PASSKEY=888888 $
  ADMIN_DEMO_PASSKEY=999999  $
  ```

#### Step 2: Fix Whitespace Issues

If you found trailing whitespace, edit your `.env` file:

```bash
nano .env
```

Ensure these lines look exactly like this (no trailing spaces):
```env
AUTH_MODE=demo
DEMO_PASSKEY=888888
ADMIN_DEMO_PASSKEY=999999
```

Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X` in nano).

#### Step 3: Verify Environment Loading

Create a test script to verify environment variables are loaded correctly:

```bash
cat > test_env.py << 'EOF'
import os
from dotenv import load_dotenv

load_dotenv()

print("Environment Variables Test")
print("=" * 60)
print(f"AUTH_MODE: '{os.getenv('AUTH_MODE')}' (length: {len(os.getenv('AUTH_MODE', ''))})")
print(f"DEMO_PASSKEY: '{os.getenv('DEMO_PASSKEY')}' (length: {len(os.getenv('DEMO_PASSKEY', ''))})")
print(f"ADMIN_DEMO_PASSKEY: '{os.getenv('ADMIN_DEMO_PASSKEY')}' (length: {len(os.getenv('ADMIN_DEMO_PASSKEY', ''))})")
print("=" * 60)

# Check for whitespace
auth_mode = os.getenv('AUTH_MODE', '')
if auth_mode != auth_mode.strip():
    print("⚠️ WARNING: AUTH_MODE has leading/trailing whitespace!")
    
demo_passkey = os.getenv('DEMO_PASSKEY', '')
if demo_passkey != demo_passkey.strip():
    print("⚠️ WARNING: DEMO_PASSKEY has leading/trailing whitespace!")
    
admin_passkey = os.getenv('ADMIN_DEMO_PASSKEY', '')
if admin_passkey != admin_passkey.strip():
    print("⚠️ WARNING: ADMIN_DEMO_PASSKEY has leading/trailing whitespace!")

print("\nAll checks passed! Environment is correctly configured." if all([
    auth_mode == auth_mode.strip(),
    demo_passkey == demo_passkey.strip(),
    admin_passkey == admin_passkey.strip()
]) else "\n⚠️ Fix whitespace issues in .env file!")
EOF

python3 test_env.py
```

**Expected output:**
```
Environment Variables Test
============================================================
AUTH_MODE: 'demo' (length: 4)
DEMO_PASSKEY: '888888' (length: 6)
ADMIN_DEMO_PASSKEY: '999999' (length: 6)
============================================================

All checks passed! Environment is correctly configured.
```

#### Step 4: Restart the Server

After fixing the `.env` file, restart your MindGraph server:

```bash
# If using systemd
sudo systemctl restart mindgraph

# If running manually
# Ctrl+C to stop, then:
python3 run_server.py
```

#### Step 5: Check Server Logs

Look for the demo mode banner in the logs:

```bash
tail -f logs/app.log | grep -A 5 "DEMO MODE"
```

**Expected output:**
```
============================================================
DEMO MODE ACTIVE
Passkey: 888888
Passkey length: 6 characters
Access: /demo
============================================================
```

If you see the banner, demo mode is active!

#### Step 6: Test Login

1. Open your browser to `http://your-server-ip:9527/demo`
2. Enter passkey: `888888` (or your custom passkey)
3. Check the logs for verification attempt:

```bash
tail -f logs/app.log | grep "passkey verification"
```

**Expected log output on success:**
```
Demo passkey verification attempt - Received: 6 chars, Expected: 6 chars
Demo mode access granted
```

**Log output on failure:**
```
Demo passkey verification attempt - Received: 6 chars, Expected: 6 chars
Demo passkey verification failed - Check .env file for whitespace in DEMO_PASSKEY or ADMIN_DEMO_PASSKEY
```

### Common Issues and Solutions

#### Issue 1: "No such file or directory: .env"

**Solution:** Create the `.env` file from the example:
```bash
cp env.example .env
nano .env
```

Edit the relevant settings:
```env
AUTH_MODE=demo
DEMO_PASSKEY=888888
ADMIN_DEMO_PASSKEY=999999
```

#### Issue 2: Still getting "wrong password" after fixing whitespace

**Possible causes:**
1. Server wasn't restarted after editing `.env`
2. Using wrong passkey (check what you set in `.env`)
3. File encoding issues (ensure UTF-8)

**Debugging steps:**
```bash
# Check exact bytes in .env file
hexdump -C .env | grep -A 2 -B 2 "DEMO_PASSKEY"

# Recreate .env file with correct encoding
echo "AUTH_MODE=demo" > .env
echo "DEMO_PASSKEY=888888" >> .env
echo "ADMIN_DEMO_PASSKEY=999999" >> .env
```

#### Issue 3: Passkey works locally but not on server

**Check file permissions:**
```bash
ls -la .env
# Should be readable: -rw-r--r-- or -rw-------

# Fix permissions if needed:
chmod 644 .env
```

**Check if `.env` is in the correct directory:**
```bash
pwd  # Should be in your MindGraph root directory
ls -la .env  # Should exist here
```

### Issue 4: "password cannot be longer than 72 bytes" error

This error occurs when the database has corrupted demo users from previous installations.

**Error message:**
```
ValueError: password cannot be longer than 72 bytes
(trapped) error reading bcrypt version
```

**Solution - Delete corrupted demo users:**
```bash
# Stop the server
sudo systemctl stop mindgraph

# Open database
sqlite3 mindgraph.db

# Delete demo users
DELETE FROM users WHERE phone = 'demo@system.com';
DELETE FROM users WHERE phone = 'demo-admin@system.com';

# Exit
.exit

# Restart server (will recreate demo users)
sudo systemctl start mindgraph
```

**Or start completely fresh:**
```bash
# Backup old database
mv mindgraph.db mindgraph.db.backup

# Restart server - creates new database
sudo systemctl restart mindgraph
```

### Advanced Debugging

If you're still having issues, enable verbose logging:

1. Edit `.env`:
   ```env
   VERBOSE_LOGGING=True
   LOG_LEVEL=DEBUG
   ```

2. Restart server

3. Check detailed logs:
   ```bash
   tail -f logs/app.log
   ```

You'll see detailed information about:
- Environment variable loading
- Passkey comparison
- Exact string lengths and characters

### Security Notes

- **Never commit `.env` to git** - it's already in `.gitignore`
- **Change default passkeys in production** - `888888` and `999999` are examples
- **Use strong passkeys** - consider 8+ characters with letters and numbers
- **Rotate passkeys periodically** - especially for admin access

### Quick Reference

| Passkey Type | Default Value | Purpose |
|-------------|---------------|---------|
| `DEMO_PASSKEY` | `888888` | Regular demo access |
| `ADMIN_DEMO_PASSKEY` | `999999` | Admin demo access (full admin panel) |

### Need More Help?

If you're still experiencing issues after following this guide:

1. Check the logs for specific error messages
2. Verify Python version: `python3 --version` (should be 3.8+)
3. Check dotenv is installed: `pip3 show python-dotenv`
4. Ensure you're running the server from the correct directory
5. Check firewall settings aren't blocking access

### Related Documentation

- [DEMO_ADMIN_SETUP.md](DEMO_ADMIN_SETUP.md) - Full demo mode setup guide
- [env.example](../env.example) - Complete environment configuration reference
- [API_REFERENCE.md](API_REFERENCE.md) - Authentication API documentation

