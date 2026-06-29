"""Unit tests for WeChat version / crypto variant resolution."""

from __future__ import annotations

from pathlib import Path

from file_reader.wechat.version import (
    cached_weixin_version_matches,
    infer_layout_variant,
    is_weixin_v41_or_newer,
    key_extraction_plan,
    primary_key_method,
    requires_wx_key_hook,
    resolve_crypto_variant,
    supports_passive_passphrase_scan,
)


def test_resolve_crypto_variant_v3() -> None:
    assert resolve_crypto_variant("v3") == "v3"


def test_resolve_crypto_variant_v4_old_weixin() -> None:
    assert resolve_crypto_variant("v4", weixin_version=(4, 0, 5, 17)) == "v4"


def test_resolve_crypto_variant_v41_from_version() -> None:
    assert resolve_crypto_variant("v4", weixin_version=(4, 1, 10, 53)) == "v4.1"


def test_resolve_crypto_variant_v41_explicit() -> None:
    assert resolve_crypto_variant("v4.1", weixin_version=(4, 0, 99, 0)) == "v4.1"


def test_is_weixin_v41_or_newer() -> None:
    assert is_weixin_v41_or_newer((4, 1, 0, 0)) is True
    assert is_weixin_v41_or_newer((4, 0, 99, 0)) is False
    assert is_weixin_v41_or_newer(None) is False


def test_passive_scan_cutoff() -> None:
    assert supports_passive_passphrase_scan((4, 1, 10, 30)) is True
    assert supports_passive_passphrase_scan((4, 1, 10, 31)) is False
    assert requires_wx_key_hook((4, 1, 10, 31)) is True
    assert requires_wx_key_hook((4, 1, 10, 53)) is True
    assert requires_wx_key_hook((4, 1, 8, 0)) is False


def test_infer_layout_variant(tmp_path: Path) -> None:
    v4_account = tmp_path / "account"
    (v4_account / "db_storage").mkdir(parents=True)
    assert infer_layout_variant(v4_account) == "v4"
    assert infer_layout_variant(tmp_path / "wxid") == "v3"


def test_cached_weixin_version_matches() -> None:
    assert cached_weixin_version_matches("4.1.10.53", "4.1.10.53") is True
    assert cached_weixin_version_matches("4.1.10.31", "4.1.10.53") is False
    assert cached_weixin_version_matches("unknown", "4.1.10.53") is True
    assert cached_weixin_version_matches("4.1.10.53", "unknown") is True
    assert cached_weixin_version_matches("", "4.1.10.53") is True


def test_key_extraction_plan_matches_crypto() -> None:
    assert primary_key_method("v3") == "v3_wechatwin"
    assert primary_key_method("v4") == "v4_xhex"
    assert primary_key_method("v4.1", weixin_version=(4, 1, 8, 0)) == "v4.1_passphrase"
    assert primary_key_method("v4.1", weixin_version=(4, 1, 10, 53)) == "v4.1_wx_key_dll"
    assert key_extraction_plan("v4.1", weixin_version=(4, 1, 10, 53)) == ("v4.1_wx_key_dll",)
    assert key_extraction_plan("v4.1", weixin_version=(4, 1, 8, 0)) == (
        "v4.1_passphrase",
        "v4.1_wx_key_dll",
    )
