#!/usr/bin/env bash
# Same as update_swot_upstream.ps1 — refresh pyswot (git) + Kikobeats JSON.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
python -m pip install -U pip
pip install --no-cache-dir -U -r requirements.txt
python scripts/swot/sync_kikobeats_domains.py
echo "Done. Commit data/kikobeats_free_email_domains.json if updated."
