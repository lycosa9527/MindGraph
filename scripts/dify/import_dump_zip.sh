#!/usr/bin/env bash
# Import Dify raw dump zips into data/dify-dumps/{dify|neodify}/.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "$REPO_ROOT"

if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo "python3 required on MindGraph host" >&2
  exit 2
fi

exec "$PYTHON" - <<'PY'
from services.dify.export.raw_dump_config import resolve_raw_dump_dir
from services.dify.export.raw_dump_import import import_pending_zips

root = resolve_raw_dump_dir()
incoming = root / "incoming"
print(f"Importing zips from {incoming.resolve()} …")
result = import_pending_zips(root)
for path in result.imported:
    print(f"  imported -> {path}")
for skip in result.skipped:
    print(f"  skipped: {skip}")
for err in result.errors:
    print(f"  error: {err}")
if result.errors:
    raise SystemExit(1)
print(f"Done — {len(result.imported)} snapshot(s) imported.")
PY
