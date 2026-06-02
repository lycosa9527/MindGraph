"""Load Alembic RLS helper modules (see ``alembic/migration_support.py``)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_MODULE_NAME = "mindgraph_alembic_migration_support"
_SUPPORT_PATH = Path(__file__).resolve().parent.parent.parent / "alembic" / "migration_support.py"
_cached: ModuleType | None = None


def _support_module() -> ModuleType:
    global _cached
    if _cached is not None:
        return _cached
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _SUPPORT_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load Alembic migration support: {_SUPPORT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _cached = module
    return module


def ensure_rls_migration_modules_loaded() -> None:
    """Register repo ``alembic/rls_*.py`` before revision imports."""
    _support_module().ensure_rls_migration_modules_loaded()


def load_rls_policy_builder() -> ModuleType:
    """Return the loaded ``alembic.rls_policy_builder`` module."""
    return _support_module().load_rls_policy_builder()


def load_rls_roles_sql() -> ModuleType:
    """Return the loaded ``alembic.rls_roles_sql`` module."""
    return _support_module().load_rls_roles_sql()
