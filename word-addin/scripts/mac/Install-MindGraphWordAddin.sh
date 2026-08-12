#!/usr/bin/env bash
# Register or unregister MindGraph for Word on macOS (WEF sideload).
# Deploy zip layout: mac/*.command next to ../manifest.xml
#
# Install:   open mac/Install.command  OR  ./Install-MindGraphWordAddin.sh
# Uninstall: open mac/Uninstall.command  OR  ./Install-MindGraphWordAddin.sh --uninstall
set -euo pipefail

UNINSTALL=0
NO_LAUNCH=0
for arg in "$@"; do
  case "$arg" in
    --uninstall|-u) UNINSTALL=1 ;;
    --no-launch) NO_LAUNCH=1 ;;
    -h|--help)
      echo "Usage: $0 [--uninstall] [--no-launch]"
      exit 0
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
MANIFEST=""
for candidate in \
  "${ROOT_DIR}/manifest.xml" \
  "${SCRIPT_DIR}/manifest.xml" \
  "$(cd "${ROOT_DIR}/.." && pwd)/manifest.xml"
do
  if [[ -f "$candidate" ]]; then
    MANIFEST="$(cd "$(dirname "$candidate")" && pwd)/$(basename "$candidate")"
    break
  fi
done
if [[ -z "$MANIFEST" ]]; then
  echo "manifest.xml not found. Keep the unzip root (README.md + manifest.xml + windows/ + mac/)." >&2
  exit 1
fi

# Microsoft Word for Mac developer sideload folder (add-in only manifest).
WEF_DIR="${HOME}/Library/Containers/com.microsoft.Word/Data/Documents/wef"
# Stable filename so reinstall overwrites the same entry.
DEST="${WEF_DIR}/mindgraph-word-addin.xml"

if [[ "$UNINSTALL" -eq 1 ]]; then
  if [[ -f "$DEST" ]]; then
    rm -f "$DEST"
    echo "Uninstalled MindGraph for Word (removed ${DEST})."
  else
    echo "MindGraph for Word was not installed for this Mac user (no file in wef)."
  fi
  exit 0
fi

mkdir -p "$WEF_DIR"
cp -f "$MANIFEST" "$DEST"
echo "Installed MindGraph for Word (macOS)."
echo "Manifest copy: ${DEST}"
echo "You may delete the unzip folder; Word uses the copy in wef."
echo "Quit Word completely, reopen, then open a document → MindGraph ribbon (or Home → Add-ins)."

if [[ "$NO_LAUNCH" -eq 0 ]]; then
  if [[ -d "/Applications/Microsoft Word.app" ]]; then
    open -a "Microsoft Word" || true
  fi
fi
