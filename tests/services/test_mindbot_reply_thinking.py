"""Tests for MindBot Dify reply thinking strip / truncate."""

from services.mindbot.core.reply_thinking import (
    format_mindbot_reply_for_dingtalk,
    iter_visible_stream_chunks,
)


def _bt_think_wrapped() -> tuple[str, str]:
    """Backtick-wrapped ``think`` markers used by some models."""
    bt = chr(96)
    open_b = bt + chr(60) + "think" + chr(62) + bt
    close_b = bt + chr(60) + "/" + "think" + chr(62) + bt
    return open_b, close_b


def test_format_hide_strips_backtick_think_block() -> None:
    """Non-streaming: remove backtick-delimited think blocks when hidden."""
    open_b, close_b = _bt_think_wrapped()
    raw = f"Hello {open_b}inner{close_b} world"
    out = format_mindbot_reply_for_dingtalk(
        raw,
        show_chain_of_thought=False,
        chain_of_thought_max_chars=4000,
    )
    assert out == "Hello  world"


def test_format_hide_strips_redacted_pair() -> None:
    """Non-streaming: strip standard redacted thinking tags."""
    raw = "A <redacted_thinking>sec</redacted_thinking> B"
    out = format_mindbot_reply_for_dingtalk(
        raw,
        show_chain_of_thought=False,
        chain_of_thought_max_chars=4000,
    )
    assert out == "A  B"


def test_format_hide_strips_whitespace_redacted_tags() -> None:
    """Non-streaming: strip loose-whitespace redacted thinking tags."""
    raw = "A < redacted_thinking >sec</ redacted_thinking > B"
    out = format_mindbot_reply_for_dingtalk(
        raw,
        show_chain_of_thought=False,
        chain_of_thought_max_chars=4000,
    )
    assert out == "A  B"


def test_format_show_truncates_inner() -> None:
    """When CoT is shown, cap inner length per block."""
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
    """Streaming: hide backtick think block until close tag."""
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
    """When CoT is shown, stream passes through unchanged."""
    parts = ["a", "b"]
    visible = "".join(
        iter_visible_stream_chunks(
            parts,
            show_chain_of_thought=True,
        )
    )
    assert visible == "ab"


def test_stream_hide_emits_nothing_until_thinking_closes() -> None:
    """Thinking-first: no outbound chunks until ``</redacted_thinking>``."""
    parts = [
        "<redacted_thinking>",
        "secret",
        "</redacted_thinking>",
        " Answer",
    ]
    visible = "".join(
        iter_visible_stream_chunks(
            parts,
            show_chain_of_thought=False,
        )
    )
    assert "secret" not in visible
    assert visible.strip().startswith("Answer")


def test_stream_hide_after_first_block_second_incomplete_holds() -> None:
    """Second thinking block open without close: hold until ``</redacted_thinking>``."""
    open_rt = "<" + "redacted_thinking" + ">"
    close_rt = "</" + "redacted_thinking" + ">"
    parts = [
        open_rt + "a" + close_rt + " ok ",
        open_rt + "b",
    ]
    visible = "".join(
        iter_visible_stream_chunks(
            parts,
            show_chain_of_thought=False,
        )
    )
    assert visible == " ok "


def test_stream_hide_holds_when_open_tag_split_across_chunks() -> None:
    """Hold if the opening tag is split so the buffer has no ``>`` yet."""
    open_rt = "<" + "redacted_thinking" + ">"
    close_rt = "</" + "redacted_thinking" + ">"
    parts = [
        open_rt + "a" + close_rt + " ok ",
        open_rt[:8],
        open_rt[8:] + "b",
    ]
    visible = "".join(
        iter_visible_stream_chunks(
            parts,
            show_chain_of_thought=False,
        )
    )
    assert visible == " ok "
