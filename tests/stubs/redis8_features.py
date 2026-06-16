"""Install stub for ``services.online_collab.redis.redis8_features`` in isolated tests."""

from __future__ import annotations

import sys
import types


class _Redis8FeaturesModule(types.ModuleType):
    """Minimal module stub matching redis8_features surface used in tests."""

    @staticmethod
    def timeseries_enabled() -> bool:
        return False

    @staticmethod
    async def ts_record_counter(_key: str, _delta: float) -> None:
        return None


def install_redis8_features_stub() -> None:
    """Register redis8_features stub modules without pulling online_collab imports."""
    online_collab_pkg = types.ModuleType("services.online_collab")
    setattr(online_collab_pkg, "__path__", [])
    online_collab_redis_pkg = types.ModuleType("services.online_collab.redis")
    setattr(online_collab_redis_pkg, "__path__", [])
    redis8_features_stub = _Redis8FeaturesModule("services.online_collab.redis.redis8_features")
    sys.modules.setdefault("services.online_collab", online_collab_pkg)
    sys.modules.setdefault("services.online_collab.redis", online_collab_redis_pkg)
    sys.modules.setdefault("services.online_collab.redis.redis8_features", redis8_features_stub)
