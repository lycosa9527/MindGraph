# Refresh Swot-related upstream data for MindGraph (maintainers).
# 1) Upgrade Python deps (pyswot from git @ main per requirements.txt)
# 2) Re-download Kikobeats domains.json into data/kikobeats_free_email_domains.json
#
# After running: review git diff, commit both requirements lock state and JSON if changed.
# pip may cache git checkouts; use --no-cache-dir when you need the latest rse-pyswot commit.

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

python -m pip install -U pip
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

pip install --no-cache-dir -U -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python scripts/swot/sync_kikobeats_domains.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Done. Commit data/kikobeats_free_email_domains.json if updated."
