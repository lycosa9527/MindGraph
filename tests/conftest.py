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

import importlib.util
import sys
from pathlib import Path

from pytest import fixture

# Add project root to Python path
project_root = Path(__file__).parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


def verify_imports():
    """Verify imports work after path setup."""
    try:
        importlib.util.find_spec("services")
        importlib.util.find_spec("config")
        importlib.util.find_spec("clients")
    except (ImportError, AttributeError) as e:
        print(f"Warning: Could not import modules: {e}")
        print(f"Project root: {project_root}")
        print(f"sys.path: {sys.path}")


# Verify imports work
verify_imports()


@fixture(autouse=True)
def _reset_ip_reputation_env_snapshot():
    """Tests monkeypatch env; clear snapshot so flags re-read from os.environ."""
    from services.infrastructure.security.abuseipdb_service import (
        invalidate_sismember_cache_ttl_snapshot,
    )
    from services.infrastructure.security.ip_reputation_env_snapshot import (
        invalidate_ip_reputation_env_snapshot,
    )

    invalidate_ip_reputation_env_snapshot()
    invalidate_sismember_cache_ttl_snapshot()
    yield
    invalidate_ip_reputation_env_snapshot()
    invalidate_sismember_cache_ttl_snapshot()
