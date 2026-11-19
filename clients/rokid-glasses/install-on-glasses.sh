#!/usr/bin/env bash
# Copy this tree to the Windows Gradle project, build the debug APK, install it.
# The glasses must be on the development cable with 眼镜ADB调试 on.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
WIN_ROOT="/mnt/c/Users/roywa/src/MindGraphGlasses"
ADB="/mnt/c/Users/roywa/AppData/Local/Android/Sdk/platform-tools/adb.exe"
SERIAL="${GLASSES_SERIAL:-2401092643180520}"
APK='C:\Users\roywa\src\MindGraphGlasses\app\build\outputs\apk\debug\app-debug.apk'

if [[ ! -f "$ADB" ]]; then
  echo "adb not found at $ADB" >&2
  exit 1
fi

python3 - "$ROOT" << 'PY'
import json
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
data = subprocess.check_output(
    [
        "powershell.exe",
        "-NoProfile",
        "-Command",
        "Get-NetIPAddress -AddressFamily IPv4 | ForEach-Object { "
        "$a = Get-NetAdapter -InterfaceIndex $_.InterfaceIndex -ErrorAction SilentlyContinue; "
        "[PSCustomObject]@{ IPAddress = $_.IPAddress; InterfaceAlias = $_.InterfaceAlias; "
        "InterfaceDescription = $a.InterfaceDescription } } | ConvertTo-Json -Compress",
    ],
)
try:
    raw = data.decode("utf-8")
except UnicodeDecodeError:
    raw = data.decode("gbk")
rows = json.loads(raw)
if isinstance(rows, dict):
    rows = [rows]


def skipped(row: dict) -> bool:
    address = str(row.get("IPAddress") or "")
    alias = str(row.get("InterfaceAlias") or "").lower()
    desc = str(row.get("InterfaceDescription") or "").lower()
    blob = f"{alias} {desc}"
    if address.startswith("127.") or address.startswith("169.254."):
        return True
    blocked = (
        "wsl",
        "vethernet",
        "hyper-v",
        "loopback",
        "bluetooth",
        "virtual",
        "ndis",
        "internet sharing",
    )
    return any(word in blob for word in blocked)


def rank(alias: str) -> int:
    name = alias.lower()
    if name in {"wlan", "wi-fi", "wifi"}:
        return 0
    if name.startswith("wlan") or name.startswith("wi-fi"):
        return 1
    return 2


usable = [row for row in rows if not skipped(row)]
if not usable:
    raise SystemExit("no LAN address on the Windows host")
chosen = sorted(usable, key=lambda row: rank(str(row.get("InterfaceAlias") or "")))[0]
host = str(chosen["IPAddress"])
(root / "local-endpoint.properties").write_text(
    f"LOCAL_HOST={host}\n",
    encoding="utf-8",
)
print(f"local host {host} via {chosen.get('InterfaceAlias')}")
PY

python3 - "$ROOT" "$WIN_ROOT" << 'PY'
import os
import shutil
import sys

src, dst = sys.argv[1], sys.argv[2]
skip_dirs = {".gradle", "build", "captures", ".idea"}
skip_files = {"local.properties"}
os.makedirs(dst, exist_ok=True)
for dirpath, dirnames, filenames in os.walk(src):
    dirnames[:] = [name for name in dirnames if name not in skip_dirs]
    rel = os.path.relpath(dirpath, src)
    target_dir = dst if rel == "." else os.path.join(dst, rel)
    os.makedirs(target_dir, exist_ok=True)
    for name in filenames:
        if name in skip_files or name.endswith(".apk"):
            continue
        shutil.copy2(os.path.join(dirpath, name), os.path.join(target_dir, name))
print("synced", src, "->", dst)
PY

python3 - << 'PY'
from pathlib import Path
text = r"""@echo off
set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr"
set "PATH=%JAVA_HOME%\bin;%PATH%"
cd /d C:\Users\roywa\src\MindGraphGlasses
call gradlew.bat assembleDebug
exit /b %ERRORLEVEL%
"""
Path("/mnt/c/Users/roywa/AppData/Local/Temp/mindglass-assemble.bat").write_bytes(
    text.replace("\n", "\r\n").encode("ascii")
)
PY

# cmd.exe rejects a UNC working directory, which is what a WSL path looks like.
(cd /mnt/c && cmd.exe /c 'C:\Users\roywa\AppData\Local\Temp\mindglass-assemble.bat')

"$ADB" -s "$SERIAL" install -r "$APK"
"$ADB" -s "$SERIAL" shell dumpsys package com.mindgraph.glasssheet | tr -d '\r' | grep -E 'versionName|versionCode' | head -n 4
