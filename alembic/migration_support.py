"""Register ``alembic/rls_*.py`` on sys.modules (PyPI ``alembic`` shadows that path)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_ALEMBIC_SCRIPT_DIR = Path(__file__).resolve().parent

_HELPER_FILES = (
    ("rls_functions_sql", "rls_functions_sql.py"),
    ("rls_policy_builder", "rls_policy_builder.py"),
    ("rls_roles_sql", "rls_roles_sql.py"),
)


def ensure_rls_migration_modules_loaded() -> None:
    """Load ``alembic.rls_functions_sql`` and ``alembic.rls_policy_builder`` from this repo."""
    import alembic as alembic_pkg

    for submodule, filename in _HELPER_FILES:
        full_name = f"alembic.{submodule}"
        if full_name in sys.modules:
            continue
        path = _ALEMBIC_SCRIPT_DIR / filename
        spec = importlib.util.spec_from_file_location(full_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load migration helper module: {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[full_name] = module
        spec.loader.exec_module(module)
        setattr(alembic_pkg, submodule, module)


def load_rls_policy_builder() -> ModuleType:
    ensure_rls_migration_modules_loaded()
    module = sys.modules["alembic.rls_policy_builder"]
    if not isinstance(module, ModuleType):
        raise TypeError("alembic.rls_policy_builder failed to load")
    return module


def load_rls_roles_sql() -> ModuleType:
    ensure_rls_migration_modules_loaded()
    module = sys.modules["alembic.rls_roles_sql"]
    if not isinstance(module, ModuleType):
        raise TypeError("alembic.rls_roles_sql failed to load")
    return module
