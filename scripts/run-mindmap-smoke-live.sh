#!/usr/bin/env bash
# Live mindmap one-sentence smoke (real LLM, EN + ZH).
# Usage (WSL):
#   ./scripts/run-mindmap-smoke-live.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export LIVE_LLM=1
# Do not `source .env` — comments/values can break bash. Pytest loads .env itself.
python -m pytest tests/test_mindmap_one_sentence_smoke_live.py -q -s "$@"
