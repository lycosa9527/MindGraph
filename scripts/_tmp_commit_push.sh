#!/usr/bin/env bash
set -euo pipefail
cd /mnt/c/MindGraph
git add -A
git commit -F - <<'EOF'
Ship 5.152.0: soft-fail showcase covers, Kitty auth reconnect, Dify host health probe.

EOF
rm -f .git/COMMIT_EDITMSG_TMP
git status
git push -u origin HEAD
git status
git log -1 --oneline
rm -f scripts/_tmp_commit_push.sh
