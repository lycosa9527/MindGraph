#!/usr/bin/env bash
# Fail2ban helper: report banned IP to AbuseIPDB via MindGraph module.
# Install path: symlink from /usr/local/bin/mindgraph-fail2ban-report or reference in action.d.
#
# Usage: fail2ban_report_ban.sh <ip>
# Environment:
#   MINDGRAPH_ROOT — absolute path to MindGraph repo (default: parent of this script's ..)

set -euo pipefail
ROOT="${MINDGRAPH_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT"
exec python3 -m services.infrastructure.security.fail2ban_integration.report_ban "$1"
