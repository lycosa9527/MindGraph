#!/bin/bash
# Wrapper: invokes install_qdrant.py (avoids CRLF issues on Windows/WSL)
exec python3 "$(cd "$(dirname "$0")" && pwd)/install_qdrant.py" "$@"
