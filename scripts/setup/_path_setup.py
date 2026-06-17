"""Add MindGraph project root to sys.path for setup CLI scripts."""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
setup_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(setup_dir))
