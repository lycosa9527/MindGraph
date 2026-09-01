"""Unit tests for school feature-usage aggregations."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from services.admin.school_feature_usage_catalog import (
    resolve_feature_module,
    resolve_token_module,
)
from services.admin.school_feature_usage_compute import build_judgement, build_module_rows
from services.admin.school_feature_usage_stats import assemble_payload, build_school_feature_usage
from services.admin.school_feature_usage_types import TokenProcessBucket, UsageBucket
from services.admin.school_user_activity_compute import BEIJING_TIMEZONE
from services.admin.school_user_activity_types import OrgUserStamp

_TZ = BEIJING_TIMEZONE


def _bucket(
    user_id: int,
    action: str,
    *,
    title: str | None = None,
    source: str = "mindgraph",
    success: bool = True,
    month: str = "2026-01",
    count: int = 1,
) -> UsageBucket:
    return {
        "user_id": user_id,
        "action": action,
        "title": title,
        "source": source,
        "success": success,
        "month": month,
        "count": count,
    }


def test_resolve_voice_session_split():
    """Voice notes title maps to voice_notes; other voice sessions are kitty."""
    assert resolve_feature_module("voice_session", "voice_notes", "mindgraph") == "voice_notes"
    assert resolve_feature_module("voice_session", "kitty voice", "mindgraph") == "kitty"


def test_unknown_action_dropped():
    """Unknown actions are not folded into canvas."""
    assert resolve_feature_module("not_a_real_action", None, "mindgraph") is None


def test_resolve_token_module_autocomplete_and_unknown():
    """Autocomplete maps to canvas; unknown request types are dropped."""
    assert resolve_token_module("autocomplete") == "canvas"
    assert resolve_token_module("diagram_generation") == "canvas"
    assert resolve_token_module("diagram_generation", "/api/generate_dingtalk") == "dingtalk"
    assert resolve_token_module("voice_command_parsing") == "kitty"
    assert resolve_token_module("voice_omni") == "kitty"
    assert resolve_token_module("thinkguide") == "canvas"
    assert resolve_token_module("mind_classroom_canvas_tour") == "zhihui"
    assert resolve_token_module("concept_map_focus_validate") == "canvas"
    assert resolve_token_module("kitty_agent_loop_map_gen") == "kitty"
    assert resolve_token_module("mindmap_smoke_live") is None
    assert resolve_token_module("not_a_real_type") is None


def test_dingtalk_and_zhihui_attribution():
    """DingTalk source stays on 钉钉; zhihui does not steal mapped canvas actions."""
    assert resolve_feature_module("chat_turn", None, "dingtalk") == "dingtalk"
    assert resolve_feature_module("dingtalk_diagram", None, "dingtalk") == "dingtalk"
    assert resolve_feature_module("diagram_generate", None, "zhihui") == "canvas"
    assert resolve_feature_module("t2i_image", None, "zhihui") == "zhihui"
    assert resolve_feature_module("unknown_zhihui_action", None, "zhihui") == "zhihui"


def _token(
    request_type: str,
    *,
    calls: int,
    failures: int = 0,
    duration_sum: float = 0.0,
    duration_count: int = 0,
    endpoint_path: str = "",
) -> TokenProcessBucket:
    return {
        "request_type": request_type,
        "endpoint_path": endpoint_path,
        "calls": calls,
        "failures": failures,
        "duration_sum": duration_sum,
        "duration_count": duration_count,
    }


def test_token_fail_rate_stays_separate_from_usage_pass():
    """Usage pass rate stays on events; token rows supply LLM fail rate and duration."""
    rows = build_module_rows(
        [_bucket(1, "diagram_generate", count=10), _bucket(1, "chat_turn", count=4)],
        2026,
        [
            _token("autocomplete", calls=8, failures=2, duration_sum=16.0, duration_count=8),
            _token("mindmate", calls=4, failures=0, duration_sum=4.0, duration_count=4),
            _token("unknown_llm", calls=20, failures=20, duration_sum=100.0, duration_count=20),
            _token(
                "diagram_generation",
                calls=3,
                failures=0,
                duration_sum=9.0,
                duration_count=3,
                endpoint_path="/api/generate_dingtalk",
            ),
        ],
    )
    by_key = {row["key"]: row for row in rows}
    assert by_key["canvas"]["completed"] == 10
    assert by_key["canvas"]["pass_rate"] == 100.0
    assert by_key["canvas"]["fail_rate"] == 25.0
    assert by_key["canvas"]["avg_duration_seconds"] == 2.0
    assert by_key["dingtalk"]["avg_duration_seconds"] == 3.0
    assert by_key["dingtalk"]["capacity"] == "normal"
    assert by_key["mindmate"]["fail_rate"] == 0.0
    assert by_key["askonce"]["fail_rate"] is None
    judgement = build_judgement(rows, 2)
    assert judgement["bottleneck_slots"]["slow_keys"] == []
    assert judgement["bottleneck_slots"]["no_bottleneck"] is True


def test_slow_requires_median_and_eight_second_floor():
    """Relative latency is not a bottleneck unless it is also at least 8 seconds."""
    rows = build_module_rows(
        [_bucket(1, "diagram_generate", count=4), _bucket(1, "chat_turn", count=4)],
        2026,
        [
            _token("autocomplete", calls=2, duration_sum=24.0, duration_count=2),
            _token("mindmate", calls=2, duration_sum=2.0, duration_count=2),
        ],
    )
    judgement = build_judgement(rows, 1)
    assert "canvas" in judgement["bottleneck_slots"]["slow_keys"]
    assert judgement["bottleneck_slots"]["no_bottleneck"] is False


def test_mindmate_streaming_time_is_not_slow():
    """MindMate SSE turns around 40s are expected, not a handling bottleneck."""
    rows = build_module_rows(
        [_bucket(1, "diagram_generate", count=4), _bucket(1, "chat_turn", count=4)],
        2026,
        [
            _token("autocomplete", calls=2, duration_sum=16.6, duration_count=2),
            _token("mindmate", calls=2, duration_sum=84.0, duration_count=2),
        ],
    )
    judgement = build_judgement(rows, 1)
    assert "mindmate" not in judgement["bottleneck_slots"]["slow_keys"]
    assert judgement["bottleneck_slots"]["no_bottleneck"] is True


def test_top5_excludes_zero_visit_modules():
    """TOP 5 coverage list does not pad with unused modules."""
    rows = build_module_rows([_bucket(1, "chat_turn", count=3)], 2026)
    judgement = build_judgement(rows, 10)
    assert [item["key"] for item in judgement["top5"]] == ["mindmate"]
    assert judgement["top5"][0]["usage_rate"] == 10.0


def test_module_rows_uv_uses_and_sort():
    """Visits are distinct users; uses sum counts; idle modules sort last."""
    rows = build_module_rows(
        [
            _bucket(1, "diagram_generate", month="2026-01", count=2),
            _bucket(1, "diagram_save", month="2026-02", count=1),
            _bucket(2, "diagram_generate", month="2026-01", count=1),
            _bucket(1, "chat_turn", month="2026-01", count=4),
            _bucket(9, "not_a_real_action", month="2026-01", count=10),
        ],
        2026,
    )
    by_key = {row["key"]: row for row in rows}
    assert by_key["canvas"]["visits"] == 2
    assert by_key["canvas"]["uses"] == 4
    assert by_key["canvas"]["ops_per_visitor"] == 2.0
    assert by_key["canvas"]["completed"] == 4
    assert by_key["canvas"]["monthly_uses"][0]["value"] == 3
    assert by_key["canvas"]["monthly_uses"][1]["value"] == 1
    assert by_key["mindmate"]["uses"] == 4
    assert by_key["askonce"]["uses"] == 0
    assert rows[0]["key"] in {"canvas", "mindmate"}
    assert rows[-1]["uses"] == 0


def test_capacity_tense_and_idle():
    """High volume plus low pass rate is tense; zeros are idle."""
    rows = build_module_rows(
        [
            _bucket(1, "diagram_generate", success=False, count=20),
            _bucket(1, "chat_turn", success=True, count=5),
        ],
        2026,
    )
    by_key = {row["key"]: row for row in rows}
    assert by_key["canvas"]["pass_rate"] == 0.0
    assert by_key["canvas"]["capacity"] == "tense"
    assert by_key["mindmate"]["capacity"] == "ample"
    assert by_key["library"]["capacity"] == "idle"


def test_judgement_top5_enrolled_zero_and_split_skip():
    """Enrolled 0 hides usage rate; fewer than two non-zero modules skip high/low."""
    rows = build_module_rows([_bucket(1, "chat_turn", count=3)], 2026)
    judgement = build_judgement(rows, 0)
    assert judgement["top5"][0]["key"] == "mindmate"
    assert judgement["top5"][0]["usage_rate"] is None
    assert judgement["high"] == []
    assert judgement["low"] == []
    assert "canvas" in judgement["idle"]
    assert judgement["bottleneck_slots"]["uniformly_high"] is True


def test_judgement_high_low_and_concentration():
    """Above-median is high; below 25th is low; one dominant module is concentrated."""
    rows = build_module_rows(
        [
            _bucket(1, "diagram_generate", count=20),
            _bucket(2, "diagram_generate", count=20),
            _bucket(1, "chat_turn", count=10),
            _bucket(1, "askonce_turn", count=8),
            _bucket(1, "debate_turn", count=2),
        ],
        2026,
    )
    judgement = build_judgement(rows, 10)
    assert judgement["top5"][0]["key"] == "canvas"
    assert judgement["top5"][0]["usage_rate"] == 20.0
    assert "canvas" in judgement["high"]
    assert "debateverse" in judgement["low"]
    assert judgement["conclusion_slots"]["concentrated"] is True


@pytest.mark.asyncio
async def test_empty_members_skips_usage_query():
    """Empty school returns zeros and does not query usage."""
    now = datetime(2026, 9, 1, 12, tzinfo=_TZ)
    db = AsyncMock(spec=AsyncSession)
    with patch(
        "services.admin.school_feature_usage_stats.load_org_users",
        new=AsyncMock(return_value=[]),
    ):
        with patch(
            "services.admin.school_feature_usage_stats.beijing_now",
            return_value=now,
        ):
            with patch(
                "services.admin.school_feature_usage_stats.load_usage_buckets",
                new=AsyncMock(),
            ) as load_usage:
                with patch(
                    "services.admin.school_feature_usage_stats.load_token_buckets",
                    new=AsyncMock(),
                ) as load_tokens:
                    payload = await build_school_feature_usage(db, 7, 2026)
    load_usage.assert_not_called()
    load_tokens.assert_not_called()
    assert payload["enrolled"] == 0
    assert payload["year"] == 2026
    assert all(row["uses"] == 0 for row in payload["modules"])


@pytest.mark.asyncio
async def test_year_before_first_member_rejected():
    """Years before the school's first member raise year_out_of_range."""
    now = datetime(2026, 9, 1, 12, tzinfo=_TZ)
    db = AsyncMock(spec=AsyncSession)
    members: list[OrgUserStamp] = [{"user_id": 1, "created_at": datetime(2025, 3, 1, tzinfo=_TZ)}]
    with patch(
        "services.admin.school_feature_usage_stats.load_org_users",
        new=AsyncMock(return_value=members),
    ):
        with patch(
            "services.admin.school_feature_usage_stats.beijing_now",
            return_value=now,
        ):
            with pytest.raises(ValueError, match="year_out_of_range"):
                await build_school_feature_usage(db, 7, 2024)


@pytest.mark.asyncio
async def test_future_year_rejected():
    """Years after the current Beijing year raise invalid_year."""
    now = datetime(2026, 9, 1, 12, tzinfo=_TZ)
    db = AsyncMock(spec=AsyncSession)
    with patch(
        "services.admin.school_feature_usage_stats.load_org_users",
        new=AsyncMock(return_value=[]),
    ):
        with patch(
            "services.admin.school_feature_usage_stats.beijing_now",
            return_value=now,
        ):
            with pytest.raises(ValueError, match="invalid_year"):
                await build_school_feature_usage(db, 7, 4099)


def test_assemble_payload_has_keys_not_prose():
    """Payload judgement is structured keys, not localized sentences."""
    now = datetime(2026, 9, 1, 12, tzinfo=_TZ)
    users: list[OrgUserStamp] = [{"user_id": 1, "created_at": now}]
    payload = assemble_payload(
        [row["user_id"] for row in users],
        [_bucket(1, "chat_turn", count=2)],
        2026,
        2026,
        now,
    )
    assert "bottleneck_slots" in payload["judgement"]
    assert "conclusion_slots" in payload["judgement"]
    assert isinstance(payload["judgement"]["idle"], list)
    assert "研判" not in str(payload)
    assert "bottleneck" not in payload["judgement"]["bottleneck_slots"]
