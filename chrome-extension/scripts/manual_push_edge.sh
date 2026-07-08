#!/usr/bin/env bash
# Build a store-ready zip for manual upload in Microsoft Partner Center.
# Use while the extension is In Review — do not call publish_edge_addon.py publish
# until the current submission is finished (API returns InProgressSubmission).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "${REPO_ROOT}"
export PYTHONPATH="${REPO_ROOT}"

python scripts/package_extension.py

ZIP="${REPO_ROOT}/chrome-extension/dist/mindgraph-extension.zip"
python - <<'PY'
import zipfile
from pathlib import Path

zip_path = Path("chrome-extension/dist/mindgraph-extension.zip")
with zipfile.ZipFile(zip_path) as archive:
    names = archive.namelist()
    assert "manifest.json" in names, "manifest.json must be at zip root"
    assert not any(name.startswith("chrome-extension/") for name in names), (
        "zip must not use a chrome-extension/ prefix"
    )
    manifest = archive.read("manifest.json").decode("utf-8")
    assert '"manifest_version": 3' in manifest
print("OK: store zip layout validated (manifest.json at root, MV3)")
PY

cat <<EOF

Store zip ready:
  ${ZIP}

Manual push (extension under review):
  1. Partner Center → Microsoft Edge → your extension → Packages / submission.
  2. Upload ${ZIP} (or replace package on the current draft).
  3. Complete listing fields (description, 300×300 logo) if prompted.
  4. Submit for certification from Partner Center UI.

Do NOT run full API publish while a submission is in review — Microsoft returns
errorCode InProgressSubmission on POST /v1/products/{id}/submissions.

After approval, updates can use:
  python scripts/publish_edge_addon.py --upload-only
  # then publish from Partner Center, or full publish when no submission is active

API reference:
  https://learn.microsoft.com/en-us/microsoft-edge/extensions/update/api/using-addons-api
EOF
