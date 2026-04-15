"""Tests for MindBot Dify reply thinking strip / truncate."""

from services.mindbot.core.reply_thinking import (
    MindbotThinkingStreamFilter,
    _strip_complete_thinking_blocks,
    format_mindbot_reply_for_dingtalk,
    iter_visible_stream_chunks,
    native_reasoning_from_dify_blocking_response,
    split_tag_embedded_reasoning,
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


def test_stream_filter_tag_embedded_reasoning_text() -> None:
    """``MindbotThinkingStreamFilter`` exposes tag-derived reasoning for inspection."""
    flt = MindbotThinkingStreamFilter(show_chain_of_thought=True)
    flt.push("<redacted_thinking>inner</redacted_thinking> tail")
    assert flt.tag_embedded_reasoning_text == "inner"


def test_split_tag_matches_strip() -> None:
    """``split_tag_embedded_reasoning``.answer matches strip for hide semantics."""

    raw = "A <redacted_thinking>sec</redacted_thinking> B"
    sp = split_tag_embedded_reasoning(raw)
    assert sp.reasoning == "sec"
    assert sp.answer == _strip_complete_thinking_blocks(raw)


def test_format_native_reasoning_prepends_when_show() -> None:
    """Native Dify thought merged when not duplicated in tags."""
    out = format_mindbot_reply_for_dingtalk(
        "Hello world",
        show_chain_of_thought=True,
        chain_of_thought_max_chars=4000,
        native_reasoning="step one",
    )
    assert "<redacted_thinking>" in out
    assert "step one" in out
    assert "Hello world" in out


def test_format_native_reasoning_skips_duplicate() -> None:
    """Do not prepend native when the same text is already in tag reasoning."""
    raw = "<redacted_thinking>step one</redacted_thinking>\nHello"
    out = format_mindbot_reply_for_dingtalk(
        raw,
        show_chain_of_thought=True,
        chain_of_thought_max_chars=4000,
        native_reasoning="step one",
    )
    assert out.count("step one") == 1


def test_format_native_omitted_when_tag_reasoning_nonempty() -> None:
    """Tag-embedded reasoning wins; extra native text is not merged in."""
    raw = "<redacted_thinking>from tags</redacted_thinking>\nbody"
    out = format_mindbot_reply_for_dingtalk(
        raw,
        show_chain_of_thought=True,
        chain_of_thought_max_chars=4000,
        native_reasoning="extra native",
    )
    assert "extra native" not in out
    assert "from tags" in out


def test_native_reasoning_from_dify_blocking_response_top_level() -> None:
    assert native_reasoning_from_dify_blocking_response({"thought": "  hi  "}) == "hi"


def test_native_reasoning_from_dify_blocking_response_metadata() -> None:
    assert native_reasoning_from_dify_blocking_response(
        {"metadata": {"agent_thought": "meta"}}
    ) == "meta"


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


def test_format_hide_incomplete_block_drops_open_through_end() -> None:
    """Hide path uses stream-safe strip so an unclosed block does not leak."""
    raw = "<redacted_thinking>still thinking"
    out = format_mindbot_reply_for_dingtalk(
        raw,
        show_chain_of_thought=False,
        chain_of_thought_max_chars=4000,
    )
    assert out == ""


def test_format_hide_incomplete_block_keeps_prefix_before_open() -> None:
    """Text before an incomplete thinking open tag stays visible."""
    raw = "Hi <redacted_thinking>partial"
    out = format_mindbot_reply_for_dingtalk(
        raw,
        show_chain_of_thought=False,
        chain_of_thought_max_chars=4000,
    )
    assert out == "Hi "


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


def test_format_hide_strips_plain_think_tags() -> None:
    """Non-streaming: strip plain ``<think>...</think>`` from Dify responses."""
    raw = "<think>\ninner reasoning\n</think>visible answer"
    out = format_mindbot_reply_for_dingtalk(
        raw,
        show_chain_of_thought=False,
        chain_of_thought_max_chars=4000,
    )
    assert "inner reasoning" not in out
    assert "visible answer" in out


def test_format_hide_strips_dify_style_think_block() -> None:
    """Reproduce the exact Dify answer payload that was leaking CoT."""
    raw = (
        "<think>\n\n"
        "\u7528\u6237\u73b0\u5728\u8bf4\u4f60\u597d\uff0c\u6211\u9700\u8981\u6309\u7167"
        "\u6280\u80fd\u6765\u56de\u5e94\n"
        "</think>"
        "\u4f60\u597d\u5440\uff01\u6211\u662f\u4f60\u7684\u865a\u62df\u6559\u7814\u4f19\u4f34"
    )
    out = format_mindbot_reply_for_dingtalk(
        raw,
        show_chain_of_thought=False,
        chain_of_thought_max_chars=4000,
    )
    assert "<think>" not in out
    assert "</think>" not in out
    assert "\u4f60\u597d\u5440" in out


def test_stream_hide_plain_think_tags() -> None:
    """Streaming: ``<think>`` block content must not leak."""
    parts = [
        "<think>",
        "\nsecret reasoning\n",
        "</think>",
        "visible answer",
    ]
    visible = "".join(
        iter_visible_stream_chunks(
            parts,
            show_chain_of_thought=False,
        )
    )
    assert "secret" not in visible
    assert "visible answer" in visible


def test_split_tag_embedded_reasoning_plain_think() -> None:
    """``split_tag_embedded_reasoning`` extracts from ``<think>`` blocks."""
    raw = "<think>reasoning here</think> answer"
    sp = split_tag_embedded_reasoning(raw)
    assert "reasoning here" in sp.reasoning
    assert "answer" in sp.answer
    assert "<think>" not in sp.answer
