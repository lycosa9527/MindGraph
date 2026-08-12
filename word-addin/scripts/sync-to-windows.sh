#!/usr/bin/env bash
# Mirror word-addin sources to a Windows NTFS tree for npm / Word sideload.
# Do not use \\wsl$\ paths from PowerShell for npm install (breaks .bin symlinks).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

detect_win_user() {
  if [[ -n "${WIN_USER:-}" ]]; then
    echo "${WIN_USER}"
    return
  fi
  local from_cmd
  from_cmd="$(cmd.exe /c "echo %USERNAME%" 2>/dev/null | tr -d '\r' || true)"
  if [[ -n "${from_cmd}" && -d "/mnt/c/Users/${from_cmd}" ]]; then
    echo "${from_cmd}"
    return
  fi
  # Prefer a real profile under /mnt/c/Users (skip Public/Default).
  local candidate
  for candidate in /mnt/c/Users/*; do
    case "$(basename "${candidate}")" in
      Public|Default|"Default User"|"All Users"|desktop.ini) continue ;;
    esac
    if [[ -d "${candidate}" ]]; then
      basename "${candidate}"
      return
    fi
  done
  echo "${USER}"
}

WIN_USER="$(detect_win_user)"
DEST="${WORD_ADDIN_WIN_DEST:-/mnt/c/Users/${WIN_USER}/src/MindGraph/word-addin}"

mkdir -p "${DEST}"
rsync -a --delete \
  --exclude node_modules \
  --exclude dist \
  --exclude .office-addin-dev-certs \
  --exclude '*.log' \
  "${ROOT}/" "${DEST}/"

echo "Synced → ${DEST}"
echo "On Windows PowerShell:"
echo "  cd \$env:USERPROFILE\\src\\MindGraph\\word-addin"
echo "  npm install"
echo "  npm run signin"
echo "  npm run dev    # terminal 1"
echo "  npm start      # terminal 2"
