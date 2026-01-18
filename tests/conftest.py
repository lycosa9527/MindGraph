"""
Pytest Configuration
====================

Ensures project root is in Python path for imports.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def verify_imports():
    """Verify imports work after path setup."""
    try:
        import importlib
        importlib.util.find_spec('services')
        importlib.util.find_spec('config')
        importlib.util.find_spec('clients')
    except (ImportError, AttributeError) as e:
        print(f"Warning: Could not import modules: {e}")
        print(f"Project root: {project_root}")
        print(f"sys.path: {sys.path}")


# Verify imports work
verify_imports()

