"""Shared typing helpers for service-layer basedpyright compliance."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence, TypeVar, cast

from sqlalchemy.engine import CursorResult
from sqlalchemy.engine.result import Result

_K = TypeVar("_K")
_V = TypeVar("_V")


def count_pairs_by_key(rows: Sequence[Any]) -> Dict[int, int]:
    """Build ``{key: count}`` from grouped SQLAlchemy count rows."""
    out: Dict[int, int] = {}
    for row in rows:
        key = row[0]
        if key is not None:
            out[int(key)] = int(row[1])
    return out


def result_rowcount(result: Result[Any]) -> int:
    """Return DML rowcount from a SQLAlchemy 2.0 execute result."""
    return cast(CursorResult[Any], result).rowcount


def redis_decode(value: bytes | str | None) -> str | None:
    """Decode Redis bytes values to str for typed call sites."""
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode()
    return value


def redis_decode_required(value: bytes | str) -> str:
    """Decode Redis bytes values; ``None`` is not accepted."""
    decoded = redis_decode(value)
    if decoded is None:
        raise ValueError("redis value must not be None")
    return decoded


def redis_list_to_str(items: Sequence[bytes | str]) -> list[str]:
    """Decode Redis list elements to str."""
    return [redis_decode_required(item) for item in items]


def redis_hset_mapping(mapping: Dict[str, str]) -> Mapping[Any, Any]:
    """Return mapping typed for redis hset calls."""
    return cast(Mapping[Any, Any], mapping)


def redis_hash_to_str(data: dict[bytes | str, bytes | str]) -> dict[str, str]:
    """Normalize Redis hash payloads to ``dict[str, str]``."""
    return {redis_decode_required(k): redis_decode_required(v) for k, v in data.items()}


def mapping_int(mapping: Mapping[str, Any], key: str) -> int:
    """Read an int from a loosely typed settings/stats mapping."""
    return int(mapping[key])


def mapping_float(mapping: Mapping[str, Any], key: str) -> float:
    """Read a float from a loosely typed settings/stats mapping."""
    return float(mapping[key])


def object_to_int(value: object) -> int:
    """Coerce a dynamic SQL/JSON value to int."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"expected int-compatible value, got {type(value)!r}")
