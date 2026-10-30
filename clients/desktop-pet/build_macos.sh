#!/bin/sh
# Build MindGraph Pet.app on a Mac. PyInstaller cannot cross-compile this from Windows or WSL.
set -eu
cd "$(dirname "$0")"
python3 -m pip install -r requirements.txt pyinstaller
python3 -m PyInstaller --noconfirm --windowed --onedir --name "MindGraph Pet" \
  --add-data "VERSION:." \
  --add-data "assets:assets" \
  --collect-all keyring \
  mindgraph_pet/__main__.py
echo "dist/MindGraph Pet.app"
