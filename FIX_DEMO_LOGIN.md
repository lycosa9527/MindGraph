# Fix Demo Login - Simple Instructions

## Problem
Demo login not working with passkey 952701

## Cause
Corrupted demo users in database from old bcrypt code

## Fix (2 minutes)

### On Ubuntu Server:

```bash
# 1. Upload this fix to your server
# Upload fix_demo_now.sh to /root/MindGraph/

# 2. Make it executable
cd /root/MindGraph
chmod +x fix_demo_now.sh

# 3. Run it
./fix_demo_now.sh

# 4. Restart server
python3 run_server.py
```

### OR Manual Fix:

```bash
# Stop server
pkill -f run_server

# Delete demo users
sqlite3 /root/MindGraph/mindgraph.db "DELETE FROM users WHERE phone LIKE 'demo%@system.com';"

# Restart server
cd /root/MindGraph
python3 run_server.py
```

## Test

1. Go to: http://82.157.39.177:9527/demo
2. Enter passkey: **952701**
3. Should work! ✓

## What Changed

The bcrypt password hashing in `utils/auth.py` was fixed to handle edge cases better. But you had old corrupted demo users that need to be deleted. They'll be recreated automatically on next login.

## If Still Not Working

Check the logs and paste them here. The error should be different now.


