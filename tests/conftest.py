"""
Pytest Configuration
====================

Ensures project root is in Python path for imports.

@author lycosa9527
@made_by MindSpring Team
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Verify imports work
try:
    import services
    import config
    import clients
except ImportError as e:
    print(f"Warning: Could not import modules: {e}")
    print(f"Project root: {project_root}")
    print(f"sys.path: {sys.path}")

