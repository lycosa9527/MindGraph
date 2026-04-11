#!/usr/bin/env bash
# Deploy MindGraph Fail2ban templates to /etc/fail2ban (requires sudo).
# Run from MindGraph repo root or set MINDGRAPH_ROOT.

set -euo pipefail
ROOT="${MINDGRAPH_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$ROOT"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"
TARGET="${FAIL2BAN_ETC:-/etc/fail2ban}"

echo "MindGraph root: $ROOT"
echo "Target: $TARGET"

if [[ ! -d "$ROOT/resources/fail2ban" ]]; then
  echo "Missing $ROOT/resources/fail2ban" >&2
  exit 1
fi

python3 -c "
from pathlib import Path
from services.infrastructure.security.fail2ban_integration.deploy import deploy_fail2ban_templates
deploy_fail2ban_templates(Path(r'${TARGET}'), Path(r'${ROOT}') / 'resources' / 'fail2ban')
"

echo "Copied templates. Edit jail logpath and action.d MINDGRAPH_HOME, then:"
echo "  sudo fail2ban-client reload"
