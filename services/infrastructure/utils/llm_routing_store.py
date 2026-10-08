"""In-process LLM routing overrides and the admin traffic diagram.

Redis refresh lives in ``llm_routing_overrides``. Config properties only peek
this process cache, so importing this module does not touch Redis or settings.
"""

from __future__ import annotations

import os
import re
import time
from typing import Dict, List, Mapping, Optional, Tuple

MODEL_FIELDS: tuple[str, ...] = (
    "DEEPSEEK_MODEL",
    "EXPRESS_MODEL",
    "QWEN_MODEL_GENERATION",
    "QWEN_MODEL_CLASSIFICATION",
)
ENDPOINT_FIELDS: tuple[str, ...] = (
    "ARK_DEEPSEEK_ENDPOINT",
    "ARK_DOUBAO_ENDPOINT",
    "ARK_KIMI_ENDPOINT",
)
ALLOWED_FIELDS: frozenset[str] = frozenset(MODEL_FIELDS + ENDPOINT_FIELDS)

ENV_DEFAULTS: Dict[str, str] = {
    "DEEPSEEK_MODEL": "deepseek-v4.1-flash",
    "EXPRESS_MODEL": "deepseek-v4.1-flash",
    "QWEN_MODEL_GENERATION": "qwen3.6-flash",
    "QWEN_MODEL_CLASSIFICATION": "qwen3.6-flash",
    "QWEN_MODEL_NODE_EXPLAIN": "qwen3.8-flash",
    "ARK_DEEPSEEK_ENDPOINT": "ep-20250101000000-dummy",
    "ARK_DOUBAO_ENDPOINT": "ep-20250101000000-dummy",
    "ARK_KIMI_ENDPOINT": "ep-20250101000000-dummy",
}

DUMMY_ENDPOINT = "ep-20250101000000-dummy"
_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_ENDPOINT_RE = re.compile(r"^ep-[A-Za-z0-9-]{8,64}$")

TokenRow = Tuple[Optional[str], Optional[str], int, int]


class _RoutingOverrideState:
    """Process-local copy of the Redis routing hash."""

    def __init__(self) -> None:
        self.values: Dict[str, str] = {}
        self.loaded_at: float = 0.0
        self.loaded: bool = False


_STATE = _RoutingOverrideState()


def peek_override(key: str) -> Optional[str]:
    """Return a non-empty override, or None when this process has none."""
    value = _STATE.values.get(key, "")
    if value:
        return value
    return None


def replace_overrides(values: Mapping[str, str]) -> None:
    """Replace the process cache after a Redis read or a local save."""
    cleaned: Dict[str, str] = {}
    for key, value in values.items():
        if key in ALLOWED_FIELDS and value:
            cleaned[key] = value
    _STATE.values = cleaned
    _STATE.loaded_at = time.monotonic()
    _STATE.loaded = True


def overrides_loaded() -> bool:
    """Whether this process has completed at least one Redis refresh."""
    return _STATE.loaded


def overrides_age_seconds() -> float:
    """Seconds since the last successful cache replacement."""
    if not _STATE.loaded:
        return 1_000_000.0
    return time.monotonic() - _STATE.loaded_at


def clear_overrides_for_tests() -> None:
    """Drop the process cache. Tests only."""
    _STATE.values = {}
    _STATE.loaded_at = 0.0
    _STATE.loaded = False


def env_value(key: str) -> str:
    """Environment value for a routing field, or the code default."""
    default = ENV_DEFAULTS[key]
    raw = os.environ.get(key)
    if raw is None:
        return default
    stripped = raw.strip()
    if not stripped:
        return default
    return stripped


def effective_value(key: str) -> str:
    """Override when present, otherwise the environment value."""
    overridden = peek_override(key)
    if overridden:
        return overridden
    return env_value(key)


def _valid_value(key: str, value: str) -> bool:
    if key in MODEL_FIELDS:
        return _MODEL_RE.fullmatch(value) is not None
    if value == DUMMY_ENDPOINT:
        return False
    return _ENDPOINT_RE.fullmatch(value) is not None


def normalize_updates(updates: Mapping[str, Optional[str]]) -> Dict[str, Optional[str]]:
    """Validate a partial update. None clears the override.

    A value equal to the current environment is stored as a clear so the
    badge returns to the env source.
    """
    if len(updates) > len(ALLOWED_FIELDS):
        raise ValueError("unknown_field")
    result: Dict[str, Optional[str]] = {}
    for key, raw in updates.items():
        if key not in ALLOWED_FIELDS:
            raise ValueError("unknown_field")
        if raw is None or not str(raw).strip():
            result[key] = None
            continue
        value = str(raw).strip()
        if not _valid_value(key, value):
            raise ValueError("invalid_value")
        if value == env_value(key):
            result[key] = None
        else:
            result[key] = value
    return result


def token_bucket(alias: Optional[str], provider: Optional[str]) -> Optional[str]:
    """Map a usage row onto a diagram leg."""
    name = (alias or "").strip().lower()
    source = (provider or "").strip().lower()
    if name == "express":
        return "express"
    if name in ("doubao", "ark-doubao", "doubao21", "ark-doubao21"):
        return "doubao"
    if name in ("kimi", "ark-kimi"):
        return "kimi"
    if name.startswith("qwen3.8"):
        return "qwen38"
    if name == "qwen" or name.startswith("qwen"):
        return "qwen"
    if name in ("deepseek", "ark-deepseek"):
        if source == "volcengine" or name == "ark-deepseek":
            return "deepseek_volcengine"
        return "deepseek_dashscope"
    return None


def accumulate_token_rows(rows: List[TokenRow]) -> Dict[str, Dict[str, int]]:
    """Sum successful usage rows into diagram buckets."""
    buckets: Dict[str, Dict[str, int]] = {}
    for alias, provider, tokens, requests in rows:
        bucket = token_bucket(alias, provider)
        if bucket is None:
            continue
        slot = buckets.setdefault(bucket, {"tokens": 0, "requests": 0})
        slot["tokens"] += int(tokens or 0)
        slot["requests"] += int(requests or 0)
    return buckets


def _field_row(key: str, kind: str) -> Dict[str, object]:
    value = effective_value(key)
    env = env_value(key)
    return {
        "key": key,
        "kind": kind,
        "value": value,
        "env_value": env,
        "overridden": peek_override(key) is not None,
    }


# Beijing DashScope published quotas, and the Volcengine console row for
# DeepSeek-V4-Flash 正式版 (500 RPM / 1,000,000 TPM). Endpoint-only routes
# stay "endpoint" because the model-square page is not that endpoint's cap.
_PROVIDER_RPM: Dict[str, Optional[int]] = {
    "deepseek_dashscope": 15000,
    "express": 15000,
    "deepseek_volcengine": 500,
    "qwen": 30000,
    "qwen38": None,
    "doubao": None,
    "kimi": None,
}
_PROVIDER_TPM: Dict[str, Optional[int]] = {
    "deepseek_dashscope": 1_200_000,
    "express": 1_200_000,
    "deepseek_volcengine": 1_000_000,
    "qwen": 10_000_000,
    "qwen38": None,
    "doubao": None,
    "kimi": None,
}
_QUOTA_KIND: Dict[str, str] = {
    "deepseek_dashscope": "fixed",
    "express": "fixed",
    "deepseek_volcengine": "fixed",
    "qwen": "fixed",
    "qwen38": "dynamic",
    "doubao": "endpoint",
    "kimi": "endpoint",
}
STRATEGIES: tuple[str, ...] = ("weighted", "round_robin", "random")


def _leg(
    leg_id: str,
    provider: str,
    target: str,
    target_kind: str,
    field: str,
    tokens: Mapping[str, Dict[str, int]],
    weight: Optional[int],
    app_rpm: Mapping[str, int],
) -> Dict[str, object]:
    stats = tokens.get(leg_id, {"tokens": 0, "requests": 0})
    return {
        "id": leg_id,
        "provider": provider,
        "target": target,
        "target_kind": target_kind,
        "field": field,
        "tokens": stats["tokens"],
        "requests": stats["requests"],
        "weight": weight,
        "app_rpm": int(app_rpm.get(leg_id, 0)),
        "provider_rpm": _PROVIDER_RPM.get(leg_id),
        "provider_tpm": _PROVIDER_TPM.get(leg_id),
        "quota_kind": _QUOTA_KIND.get(leg_id, "endpoint"),
        "shares_app_rpm": leg_id == "deepseek_dashscope",
    }


def build_llm_control_view(
    *,
    tokens: Mapping[str, Dict[str, int]],
    redis_ok: bool,
    tokens_ok: bool,
    weights: Mapping[str, int],
    balancing_enabled: bool,
    strategy: str,
    app_rpm: Mapping[str, int],
) -> Dict[str, object]:
    """JSON body for the LLM control tab."""
    dash_weight = int(weights.get("dashscope", 75))
    volc_weight = int(weights.get("volcengine", 25))
    active = strategy if strategy in STRATEGIES else "weighted"
    fields = [_field_row(key, "model") for key in MODEL_FIELDS]
    fields.extend(_field_row(key, "endpoint") for key in ENDPOINT_FIELDS)
    routes: List[Dict[str, object]] = [
        {
            "id": "deepseek",
            "split": True,
            "legs": [
                _leg(
                    "deepseek_dashscope",
                    "dashscope",
                    effective_value("DEEPSEEK_MODEL"),
                    "model",
                    "DEEPSEEK_MODEL",
                    tokens,
                    dash_weight,
                    app_rpm,
                ),
                _leg(
                    "deepseek_volcengine",
                    "volcengine",
                    effective_value("ARK_DEEPSEEK_ENDPOINT"),
                    "endpoint",
                    "ARK_DEEPSEEK_ENDPOINT",
                    tokens,
                    volc_weight,
                    app_rpm,
                ),
            ],
        },
        {
            "id": "express",
            "split": False,
            "legs": [
                _leg(
                    "express",
                    "dashscope",
                    effective_value("EXPRESS_MODEL"),
                    "model",
                    "EXPRESS_MODEL",
                    tokens,
                    None,
                    app_rpm,
                )
            ],
        },
        {
            "id": "qwen",
            "split": False,
            "legs": [
                _leg(
                    "qwen",
                    "dashscope",
                    effective_value("QWEN_MODEL_GENERATION"),
                    "model",
                    "QWEN_MODEL_GENERATION",
                    tokens,
                    None,
                    app_rpm,
                )
            ],
        },
        {
            "id": "qwen38",
            "split": False,
            "legs": [
                _leg(
                    "qwen38",
                    "dashscope",
                    "qwen3.8-flash",
                    "model",
                    "",
                    tokens,
                    None,
                    app_rpm,
                )
            ],
        },
        {
            "id": "doubao",
            "split": False,
            "legs": [
                _leg(
                    "doubao",
                    "volcengine",
                    effective_value("ARK_DOUBAO_ENDPOINT"),
                    "endpoint",
                    "ARK_DOUBAO_ENDPOINT",
                    tokens,
                    None,
                    app_rpm,
                )
            ],
        },
        {
            "id": "kimi",
            "split": False,
            "legs": [
                _leg(
                    "kimi",
                    "volcengine",
                    effective_value("ARK_KIMI_ENDPOINT"),
                    "endpoint",
                    "ARK_KIMI_ENDPOINT",
                    tokens,
                    None,
                    app_rpm,
                )
            ],
        },
    ]
    return {
        "redis_ok": redis_ok,
        "tokens_ok": tokens_ok,
        "balancing_enabled": balancing_enabled,
        "strategy": active,
        "strategies": [{"id": name, "active": name == active} for name in STRATEGIES],
        "weights": {"dashscope": dash_weight, "volcengine": volc_weight},
        "routes": routes,
        "fields": fields,
    }
