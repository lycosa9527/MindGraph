#!/bin/bash
# Double-click in Finder to install MindGraph for Word on macOS.
cd "$(dirname "$0")" || exit 1
# Clear quarantine so first-run Gatekeeper does not block the script.
xattr -dr com.apple.quarantine . 2>/dev/null || true
chmod +x ./Install-MindGraphWordAddin.sh ./Install.command ./Uninstall.command 2>/dev/null || true
./Install-MindGraphWordAddin.sh
echo ""
read -r -p "Press Return to close…"
