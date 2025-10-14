#!/bin/bash
# Quick Fix: Delete corrupted demo users
# Run this on your Ubuntu server

echo "======================================"
echo "Demo Login Fix - Delete Corrupted Users"
echo "======================================"

# Stop the server first (if running)
echo "Stopping server..."
pkill -f "python.*run_server.py" || true
pkill -f "python.*main.py" || true

# Delete corrupted demo users from database
echo "Deleting corrupted demo users..."
sqlite3 /root/MindGraph/mindgraph.db "DELETE FROM users WHERE phone LIKE 'demo%@system.com';"

# Verify deletion
COUNT=$(sqlite3 /root/MindGraph/mindgraph.db "SELECT COUNT(*) FROM users WHERE phone LIKE 'demo%@system.com';")
echo "Demo users remaining: $COUNT (should be 0)"

echo ""
echo "✓ Demo users deleted!"
echo "✓ Now restart your server:"
echo ""
echo "  cd /root/MindGraph"
echo "  python3 run_server.py"
echo ""
echo "Then try demo login with passkey: 952701"
echo "======================================"


