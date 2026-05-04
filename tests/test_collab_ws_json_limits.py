"""Tests for workshop WebSocket JSON depth and live-spec key parsing."""

from __future__ import annotations

from services.online_collab.spec.online_collab_live_spec_shutdown import (
    workshop_code_from_live_spec_key,
)
from utils.ws_limits import (
    MAX_COLLAB_INBOUND_JSON_DEPTH,
    collab_json_exceeds_depth,
    json_value_nesting_depth,
)


def test_workshop_code_from_live_spec_key_plain() -> None:
    assert workshop_code_from_live_spec_key("workshop:live_spec:ABC12") == "ABC12"


def test_workshop_code_from_live_spec_key_hash_tag() -> None:
    assert workshop_code_from_live_spec_key("workshop:live_spec:{XYZ}") == "XYZ"


def test_workshop_code_from_live_spec_key_bytes() -> None:
    assert workshop_code_from_live_spec_key(b"workshop:live_spec:{Q}") == "Q"


def test_json_depth_nested() -> None:
    shallow = {"a": 1, "b": {"c": 2}}
    assert json_value_nesting_depth(shallow) == 2
    deep: dict = {"leaf": True}
    for _ in range(55):
        deep = {"w": deep}
    assert json_value_nesting_depth(deep) > MAX_COLLAB_INBOUND_JSON_DEPTH
    assert collab_json_exceeds_depth(deep, MAX_COLLAB_INBOUND_JSON_DEPTH)


def test_json_depth_flat_ok() -> None:
    msg = {"type": "ping", "seq": 1}
    assert not collab_json_exceeds_depth(msg, MAX_COLLAB_INBOUND_JSON_DEPTH)
