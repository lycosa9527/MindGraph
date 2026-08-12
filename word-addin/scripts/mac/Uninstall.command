#!/bin/bash
# Double-click in Finder to remove MindGraph for Word on macOS.
cd "$(dirname "$0")" || exit 1
xattr -dr com.apple.quarantine . 2>/dev/null || true
chmod +x ./Install-MindGraphWordAddin.sh ./Install.command ./Uninstall.command 2>/dev/null || true
./Install-MindGraphWordAddin.sh --uninstall
echo ""
read -r -p "Press Return to close…"
