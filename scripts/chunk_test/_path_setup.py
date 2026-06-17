"""Add MindGraph project root to sys.path for chunk_test CLI scripts."""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
