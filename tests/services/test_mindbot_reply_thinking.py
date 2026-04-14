"""Tests for MindBot Dify reply thinking strip / truncate."""

from services.mindbot.core.reply_thinking import (
    format_mindbot_reply_for_dingtalk,
    iter_visible_stream_chunks,
)


def _bt_think_wrapped() -> tuple[str, str]:
    bt = chr(96)
    open_b = bt + chr(60) + "think" + chr(62) + bt
    close_b = bt + chr(60) + "/" + "think" + chr(62) + bt
    return open_b, close_b


def test_format_hide_strips_backtick_think_block() -> None:
    open_b, close_b = _bt_think_wrapped()
    raw = f"Hello {open_b}inner{close_b} world"
    out = format_mindbot_reply_for_dingtalk(
        raw,
        show_chain_of_thought=False,
        chain_of_thought_max_chars=4000,
    )
    assert out == "Hello  world"


def test_format_hide_strips_redacted_pair() -> None:
    raw = "A <redacted_thinking>sec</redacted_thinking> B"
    out = format_mindbot_reply_for_dingtalk(
        raw,
        show_chain_of_thought=False,
        chain_of_thought_max_chars=4000,
    )
    assert out == "A  B"


def test_format_show_truncates_inner() -> None:
    inner = "x" * 20
    raw = f"Hi <redacted_thinking>{inner}</redacted_thinking> bye"
    out = format_mindbot_reply_for_dingtalk(
        raw,
        show_chain_of_thought=True,
        chain_of_thought_max_chars=5,
    )
    assert "xxxxx…" in out
    assert out.count("x") <= 7


def test_stream_hide_holds_until_block_closed() -> None:
    open_b, close_b = _bt_think_wrapped()
    parts = [open_b, "in", close_b, " out"]
    visible = "".join(
        iter_visible_stream_chunks(
            parts,
            show_chain_of_thought=False,
        )
    )
    assert visible == " out"


def test_stream_show_passes_through() -> None:
    parts = ["a", "b"]
    visible = "".join(
        iter_visible_stream_chunks(
            parts,
            show_chain_of_thought=True,
        )
    )
    assert visible == "ab"
