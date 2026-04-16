"""Tests for DingTalk AI card OpenAPI helpers (mocked HTTP)."""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models.domain.mindbot_config import OrganizationMindbotConfig
from services.mindbot.platforms.dingtalk.cards.ai_card import (
    ai_card_overflow_remainder_for_markdown,
    create_and_deliver_ai_card,
    mindbot_ai_card_param_key,
    mindbot_ai_card_streaming_max_chars,
    mindbot_ai_card_wiring_enabled,
    probe_ai_card_streaming_update_api,
    streaming_update_ai_card,
)
from services.mindbot.platforms.dingtalk.cards.ai_card_create import (
    DEFAULT_DINGTALK_AI_CARD_STREAMING_MAX_CHARS,
    _open_space_id_group,
    _open_space_id_robot,
)


def _mindbot_cfg(**kwargs: object) -> OrganizationMindbotConfig:
    return cast(OrganizationMindbotConfig, SimpleNamespace(**kwargs))


def _patch_group_stream_sdk() -> Any:
    """Avoid real Stream SDK WebSocket setup in group createAndDeliver tests."""
    mgr = MagicMock()
    mgr.ensure_client = AsyncMock()
    return patch(
        "services.mindbot.platforms.dingtalk.cards.ai_card_create.get_stream_manager",
        return_value=mgr,
    )


def test_open_space_ids() -> None:
    assert _open_space_id_group("cid-abc") == "dtv1.card//im_group.cid-abc"
    assert _open_space_id_robot("staff-1") == "dtv1.card//im_robot.staff-1"


def test_mindbot_ai_card_param_key_default() -> None:
    cfg = _mindbot_cfg(dingtalk_ai_card_param_key=None)
    assert mindbot_ai_card_param_key(cfg) == "content"


def test_mindbot_ai_card_streaming_max_chars_resolves() -> None:
    assert (
        mindbot_ai_card_streaming_max_chars(_mindbot_cfg())
        == DEFAULT_DINGTALK_AI_CARD_STREAMING_MAX_CHARS
    )
    assert mindbot_ai_card_streaming_max_chars(_mindbot_cfg(dingtalk_ai_card_streaming_max_chars=7000)) == 7000
    assert mindbot_ai_card_streaming_max_chars(_mindbot_cfg(dingtalk_ai_card_streaming_max_chars=100)) == 500


def test_ai_card_overflow_remainder_empty_when_short() -> None:
    cap = DEFAULT_DINGTALK_AI_CARD_STREAMING_MAX_CHARS
    assert ai_card_overflow_remainder_for_markdown("hello", max_chars=cap) == ""


def test_ai_card_overflow_remainder_after_cap() -> None:
    cap = 3000
    overage = 500
    long_body = "x" * (cap + overage)
    rem = ai_card_overflow_remainder_for_markdown(long_body, max_chars=cap)
    assert len(rem) == overage
    assert rem == "x" * overage


@pytest.mark.asyncio
async def test_streaming_update_retries_on_401_with_fresh_token() -> None:
    put_calls: list[int] = []

    async def fake_put(
        _path: str,
        _token: str,
        _payload: dict,
        **_kwargs,
    ):
        put_calls.append(1)
        if len(put_calls) == 1:
            return 401, None
        return 200, {"success": True, "result": True}

    cfg = _mindbot_cfg(
        organization_id=7,
        dingtalk_client_id="kid",
        dingtalk_app_secret="sec",
        dingtalk_ai_card_param_key="body",
    )
    with patch(
        "services.mindbot.platforms.dingtalk.cards.ai_card_update.put_v1_json_unverified",
        new=fake_put,
    ):
        with patch(
            "services.mindbot.platforms.dingtalk.cards.ai_card_update.invalidate_access_token_cache",
            new=AsyncMock(),
        ) as inv_mock:
            with patch(
                "services.mindbot.platforms.dingtalk.cards.ai_card_update.prefetch_ai_card_access_token",
                new=AsyncMock(return_value="tok-new"),
            ) as pre_mock:
                ok, code, detail, ref = await streaming_update_ai_card(
                    cfg,
                    access_token="tok-old",
                    out_track_id="tr",
                    markdown_full="hi",
                    is_finalize=False,
                    pipeline_ctx="ctx",
                )
    assert ok is True
    assert code is None
    assert detail == ""
    assert ref == "tok-new"
    assert len(put_calls) == 2
    inv_mock.assert_awaited_once()
    pre_mock.assert_awaited()


@pytest.mark.asyncio
async def test_streaming_update_propagates_token_on_failure_after_401() -> None:
    put_calls: list[int] = []

    async def fake_put(
        _path: str,
        _token: str,
        _payload: dict,
        **_kwargs,
    ):
        put_calls.append(1)
        if len(put_calls) == 1:
            return 401, None
        return 200, {"success": False, "code": "biz.err", "message": "no"}

    cfg = _mindbot_cfg(
        organization_id=7,
        dingtalk_client_id="kid",
        dingtalk_app_secret="sec",
        dingtalk_ai_card_param_key="body",
    )
    with patch(
        "services.mindbot.platforms.dingtalk.cards.ai_card_update.put_v1_json_unverified",
        new=fake_put,
    ):
        with patch(
            "services.mindbot.platforms.dingtalk.cards.ai_card_update.invalidate_access_token_cache",
            new=AsyncMock(),
        ):
            with patch(
                "services.mindbot.platforms.dingtalk.cards.ai_card_update.prefetch_ai_card_access_token",
                new=AsyncMock(return_value="tok-new"),
            ):
                ok, _, _, ref = await streaming_update_ai_card(
                    cfg,
                    access_token="tok-old",
                    out_track_id="tr",
                    markdown_full="hi",
                    is_finalize=False,
                    pipeline_ctx="ctx",
                )
    assert ok is False
    assert ref == "tok-new"
    assert len(put_calls) == 2


@pytest.mark.asyncio
async def test_streaming_update_retries_on_403_qps() -> None:
    put_calls: list[int] = []

    async def fake_put(
        _path: str,
        _token: str,
        _payload: dict,
        **_kwargs,
    ):
        put_calls.append(1)
        if len(put_calls) == 1:
            return 403, {
                "code": "Forbidden.AccessDenied.QpsLimitForAppkeyAndApi",
                "message": "throttled",
            }
        return 200, {"success": True, "result": True}

    cfg = _mindbot_cfg(
        organization_id=7,
        dingtalk_client_id="kid",
        dingtalk_app_secret="sec",
        dingtalk_ai_card_param_key="body",
    )
    with patch(
        "services.mindbot.platforms.dingtalk.cards.ai_card_update.put_v1_json_unverified",
        new=fake_put,
    ):
        with patch(
            "services.mindbot.platforms.dingtalk.cards.ai_card_update.asyncio.sleep",
            new=AsyncMock(),
        ) as sleep_mock:
            ok, code, detail, ref = await streaming_update_ai_card(
                cfg,
                access_token="tok",
                out_track_id="tr",
                markdown_full="hi",
                is_finalize=False,
                pipeline_ctx="ctx",
            )
    assert ok is True
    assert code is None
    assert detail == ""
    assert ref is None
    assert len(put_calls) == 2
    sleep_mock.assert_awaited_once_with(1.0)


def test_mindbot_ai_card_wiring_requires_template_and_client() -> None:
    cfg = _mindbot_cfg(
        dingtalk_ai_card_template_id=" ",
        dingtalk_client_id="kid",
    )
    assert not mindbot_ai_card_wiring_enabled(cfg)
    cfg2 = _mindbot_cfg(
        dingtalk_ai_card_template_id="tpl-1",
        dingtalk_client_id="",
    )
    assert not mindbot_ai_card_wiring_enabled(cfg2)
    cfg3 = _mindbot_cfg(
        dingtalk_ai_card_template_id="tpl-1",
        dingtalk_client_id="kid",
    )
    assert mindbot_ai_card_wiring_enabled(cfg3)


@pytest.mark.asyncio
async def test_create_and_deliver_group_posts_expected_path() -> None:
    captured: dict[str, object] = {}

    async def fake_post(path: str, token: str, payload: dict, **_kwargs):
        captured["path"] = path
        captured["token"] = token
        captured["payload"] = payload
        return 200, {"success": True, "result": {"outTrackId": "x", "deliverResults": []}}

    cfg = _mindbot_cfg(
        organization_id=1,
        dingtalk_robot_code="robot-1",
        dingtalk_app_secret="sec",
        dingtalk_client_id="kid",
        dingtalk_ai_card_template_id="tpl-z",
        dingtalk_ai_card_param_key="body_md",
    )
    body = {
        "conversationType": "2",
        "conversationId": "oc-1",
        "senderStaffId": "staff-9",
    }
    with _patch_group_stream_sdk():
        with patch(
            "services.mindbot.platforms.dingtalk.cards.ai_card_create.post_v1_json_unverified",
            new=fake_post,
        ):
            with patch(
                "services.mindbot.platforms.dingtalk.cards.ai_card_create.get_access_token",
                new=AsyncMock(return_value="tok-1"),
            ):
                ok, code, detail, _ = await create_and_deliver_ai_card(
                    cfg,
                    body,
                    out_track_id="track-1",
                    initial_markdown="",
                    pipeline_ctx="tctx",
                )
    assert ok is True
    assert code is None
    assert detail == ""
    assert captured["path"] == "/v1.0/card/instances/createAndDeliver"
    pl = captured["payload"]
    assert isinstance(pl, dict)
    assert pl.get("outTrackId") == "track-1"
    assert pl.get("openSpaceId") == "dtv1.card//im_group.oc-1"
    assert pl.get("callbackType") == "STREAM"
    assert pl.get("imGroupOpenDeliverModel", {}).get("robotCode") == "robot-1"


@pytest.mark.asyncio
async def test_create_and_deliver_group_uses_appkey_when_env() -> None:
    captured: dict[str, object] = {}

    async def fake_post(_path: str, _token: str, payload: dict, **_kwargs):
        captured["payload"] = payload
        return 200, {"success": True, "result": {"outTrackId": "x", "deliverResults": []}}

    cfg = _mindbot_cfg(
        organization_id=1,
        dingtalk_robot_code="robot-1",
        dingtalk_app_secret="sec",
        dingtalk_client_id="kid",
        dingtalk_ai_card_template_id="tpl-z",
        dingtalk_ai_card_param_key="body_md",
    )
    body = {
        "conversationType": "2",
        "conversationId": "oc-1",
        "senderStaffId": "staff-9",
    }
    with patch.dict(os.environ, {"MINDBOT_AI_CARD_GROUP_USE_APPKEY": "true"}):
        with _patch_group_stream_sdk():
            with patch(
                "services.mindbot.platforms.dingtalk.cards.ai_card_create.post_v1_json_unverified",
                new=fake_post,
            ):
                with patch(
                    "services.mindbot.platforms.dingtalk.cards.ai_card_create.get_access_token",
                    new=AsyncMock(return_value="tok-1"),
                ):
                    ok, code, detail, _ = await create_and_deliver_ai_card(
                        cfg,
                        body,
                        out_track_id="track-1",
                        initial_markdown="",
                        pipeline_ctx="tctx",
                    )
    assert ok is True
    assert code is None
    assert detail == ""
    pl = captured["payload"]
    assert isinstance(pl, dict)
    assert pl.get("imGroupOpenDeliverModel", {}).get("robotCode") == "kid"


@pytest.mark.asyncio
async def test_create_and_deliver_http_400_returns_dingtalk_code() -> None:
    async def fake_post(_path: str, _token: str, _payload: dict, **_kwargs):
        return 400, {"code": "param.openDeliverModelError", "message": "param.openDeliverModelError"}

    cfg = _mindbot_cfg(
        organization_id=1,
        dingtalk_robot_code="r",
        dingtalk_app_secret="sec",
        dingtalk_client_id="kid",
        dingtalk_ai_card_template_id="tpl-z",
        dingtalk_ai_card_param_key="body_md",
    )
    body = {
        "conversationType": "2",
        "conversationId": "oc-1",
        "senderStaffId": "staff-9",
    }
    with _patch_group_stream_sdk():
        with patch(
            "services.mindbot.platforms.dingtalk.cards.ai_card_create.post_v1_json_unverified",
            new=fake_post,
        ):
            with patch(
                "services.mindbot.platforms.dingtalk.cards.ai_card_create.get_access_token",
                new=AsyncMock(return_value="tok-1"),
            ):
                ok, code, detail, _ = await create_and_deliver_ai_card(
                    cfg,
                    body,
                    out_track_id="track-1",
                    initial_markdown="",
                    pipeline_ctx="tctx",
                )
    assert ok is False
    assert code == "param.openDeliverModelError"
    assert detail == "param.openDeliverModelError"


@pytest.mark.asyncio
async def test_create_and_deliver_group_skips_lwcp_staff_uses_sender_id() -> None:
    captured: dict[str, object] = {}

    async def fake_post(_path: str, _token: str, payload: dict, **_kwargs):
        captured["payload"] = payload
        return 200, {"success": True, "result": {"outTrackId": "x", "deliverResults": []}}

    cfg = _mindbot_cfg(
        organization_id=1,
        dingtalk_robot_code="robot-1",
        dingtalk_app_secret="sec",
        dingtalk_client_id="kid",
        dingtalk_ai_card_template_id="tpl-z",
        dingtalk_ai_card_param_key="body_md",
    )
    body = {
        "conversationType": "2",
        "conversationId": "oc-1",
        "senderStaffId": "$:LWCP_v1:$BebpsCtoken",
        "senderId": "uid-real-openapi",
    }
    with _patch_group_stream_sdk():
        with patch(
            "services.mindbot.platforms.dingtalk.cards.ai_card_create.post_v1_json_unverified",
            new=fake_post,
        ):
            with patch(
                "services.mindbot.platforms.dingtalk.cards.ai_card_create.get_access_token",
                new=AsyncMock(return_value="tok-1"),
            ):
                ok, code, detail, _ = await create_and_deliver_ai_card(
                    cfg,
                    body,
                    out_track_id="track-1",
                    initial_markdown="",
                    pipeline_ctx="tctx",
                )
    assert ok is True
    assert code is None
    assert detail == ""
    pl = captured["payload"]
    assert isinstance(pl, dict)
    assert "userId" not in pl
    ig = pl.get("imGroupOpenDeliverModel")
    assert isinstance(ig, dict)
    assert "recipients" not in ig
    assert "atUserIds" not in ig


@pytest.mark.asyncio
async def test_create_and_deliver_group_only_lwcp_still_posts_to_group() -> None:
    """Cross-org-style LWCP-only ids: group card still createAndDeliver (whole group)."""
    post_calls: list[int] = []

    async def fake_post(_path: str, _token: str, _payload: dict, **_kwargs):
        post_calls.append(1)
        return 200, {"success": True, "result": {"outTrackId": "x", "deliverResults": []}}

    cfg = _mindbot_cfg(
        organization_id=1,
        dingtalk_robot_code="robot-1",
        dingtalk_app_secret="sec",
        dingtalk_client_id="kid",
        dingtalk_ai_card_template_id="tpl-z",
        dingtalk_ai_card_param_key="body_md",
    )
    body = {
        "conversationType": "2",
        "conversationId": "oc-1",
        "senderStaffId": "$:LWCP_v1:$a",
        "senderId": "$:LWCP_v1:$b",
    }
    with _patch_group_stream_sdk():
        with patch(
            "services.mindbot.platforms.dingtalk.cards.ai_card_create.post_v1_json_unverified",
            new=fake_post,
        ):
            with patch(
                "services.mindbot.platforms.dingtalk.cards.ai_card_create.get_access_token",
                new=AsyncMock(return_value="tok-1"),
            ):
                ok, code, detail, _ = await create_and_deliver_ai_card(
                    cfg,
                    body,
                    out_track_id="track-1",
                    initial_markdown="",
                    pipeline_ctx="tctx",
                )
    assert ok is True
    assert code is None
    assert detail == ""
    assert len(post_calls) == 1


@pytest.mark.asyncio
async def test_create_and_deliver_group_anonymous_omits_user_when_only_lwcp() -> None:
    captured: dict[str, object] = {}

    async def fake_post(_path: str, _token: str, payload: dict, **_kwargs):
        captured["payload"] = payload
        return 200, {"success": True, "result": {"outTrackId": "x", "deliverResults": []}}

    cfg = _mindbot_cfg(
        organization_id=1,
        dingtalk_robot_code="robot-1",
        dingtalk_app_secret="sec",
        dingtalk_client_id="kid",
        dingtalk_ai_card_template_id="tpl-z",
        dingtalk_ai_card_param_key="body_md",
    )
    body = {
        "conversationType": "2",
        "conversationId": "oc-1",
        "senderStaffId": "$:LWCP_v1:$a",
        "senderId": "$:LWCP_v1:$b",
    }
    with _patch_group_stream_sdk():
        with patch(
            "services.mindbot.platforms.dingtalk.cards.ai_card_create.post_v1_json_unverified",
            new=fake_post,
        ):
            with patch(
                "services.mindbot.platforms.dingtalk.cards.ai_card_create.get_access_token",
                new=AsyncMock(return_value="tok-1"),
            ):
                ok, code, detail, _ = await create_and_deliver_ai_card(
                    cfg,
                    body,
                    out_track_id="track-1",
                    initial_markdown="",
                    pipeline_ctx="tctx",
                )
    assert ok is True
    assert code is None
    assert detail == ""
    pl = captured["payload"]
    assert isinstance(pl, dict)
    assert "userId" not in pl
    ig = pl.get("imGroupOpenDeliverModel")
    assert isinstance(ig, dict)
    assert "recipients" not in ig
    assert ig.get("robotCode") == "robot-1"


@pytest.mark.asyncio
async def test_create_and_deliver_reads_union_id_from_extension() -> None:
    captured: dict[str, object] = {}

    async def fake_post(_path: str, _token: str, payload: dict, **_kwargs):
        captured["payload"] = payload
        return 200, {"success": True, "result": {"outTrackId": "x", "deliverResults": []}}

    cfg = _mindbot_cfg(
        organization_id=1,
        dingtalk_robot_code="robot-1",
        dingtalk_app_secret="sec",
        dingtalk_client_id="kid",
        dingtalk_ai_card_template_id="tpl-z",
        dingtalk_ai_card_param_key="body_md",
    )
    body = {
        "conversationType": "2",
        "conversationId": "oc-1",
        "senderStaffId": "$:LWCP_v1:$a",
        "extension": {"unionId": "union-real-99"},
    }
    with _patch_group_stream_sdk():
        with patch(
            "services.mindbot.platforms.dingtalk.cards.ai_card_create.post_v1_json_unverified",
            new=fake_post,
        ):
            with patch(
                "services.mindbot.platforms.dingtalk.cards.ai_card_create.get_access_token",
                new=AsyncMock(return_value="tok-1"),
            ):
                ok, _, detail, _ = await create_and_deliver_ai_card(
                    cfg,
                    body,
                    out_track_id="track-1",
                    initial_markdown="",
                    pipeline_ctx="tctx",
                )
    assert ok is True
    assert detail == ""
    pl = captured["payload"]
    assert isinstance(pl, dict)
    assert "userId" not in pl
    ig = pl.get("imGroupOpenDeliverModel")
    assert isinstance(ig, dict)
    assert "recipients" not in ig


@pytest.mark.asyncio
async def test_create_and_deliver_robot_1to1_stream_and_robot_code() -> None:
    captured: dict[str, object] = {}

    async def fake_post(path: str, _token: str, payload: dict, **_kwargs):
        captured["path"] = path
        captured["payload"] = payload
        return 200, {"success": True, "result": {"outTrackId": "x", "deliverResults": []}}

    cfg = _mindbot_cfg(
        organization_id=1,
        dingtalk_robot_code="robot-xy",
        dingtalk_app_secret="sec",
        dingtalk_client_id="kid",
        dingtalk_ai_card_template_id="tpl-z",
        dingtalk_ai_card_param_key="content",
    )
    body = {
        "conversationType": "1",
        "senderStaffId": "staff-p2p",
    }
    with patch(
        "services.mindbot.platforms.dingtalk.cards.ai_card_create.post_v1_json_unverified",
        new=fake_post,
    ):
        with patch(
            "services.mindbot.platforms.dingtalk.cards.ai_card_create.get_access_token",
            new=AsyncMock(return_value="tok-1"),
        ):
            ok, code, detail, _ = await create_and_deliver_ai_card(
                cfg,
                body,
                out_track_id="track-p2p",
                initial_markdown="",
                pipeline_ctx="tctx",
            )
    assert ok is True
    assert code is None
    assert detail == ""
    pl = captured["payload"]
    assert isinstance(pl, dict)
    assert pl.get("callbackType") == "STREAM"
    assert pl.get("openSpaceId") == "dtv1.card//im_robot.staff-p2p"
    im_robot_dm = pl.get("imRobotOpenDeliverModel")
    assert isinstance(im_robot_dm, dict)
    assert im_robot_dm.get("spaceType") == "IM_ROBOT"
    assert im_robot_dm.get("robotCode") == "robot-xy"


@pytest.mark.asyncio
async def test_streaming_update_puts_with_is_finalize() -> None:
    captured: dict[str, object] = {}

    async def fake_put(path: str, _token: str, payload: dict, **_kwargs):
        captured["path"] = path
        captured["payload"] = payload
        return 200, {"success": True, "result": True}

    cfg = _mindbot_cfg(
        organization_id=1,
        dingtalk_ai_card_param_key="k1",
    )
    with patch(
        "services.mindbot.platforms.dingtalk.cards.ai_card_update.put_v1_json_unverified",
        new=fake_put,
    ):
        ok, code, detail, ref_tok = await streaming_update_ai_card(
            cfg,
            access_token="tok",
            out_track_id="tr-2",
            markdown_full="hello",
            is_finalize=True,
            pipeline_ctx="ctx",
        )
    assert ok is True
    assert code is None
    assert detail == ""
    assert ref_tok is None
    assert captured["path"] == "/v1.0/card/streaming"
    pl = captured["payload"]
    assert isinstance(pl, dict)
    assert pl.get("isFinalize") is True
    assert pl.get("isError") is False
    assert pl.get("key") == "k1"
    assert pl.get("isFull") is True


@pytest.mark.asyncio
async def test_probe_streaming_treats_missing_card_as_ok() -> None:
    async def fake_unverified(*_a, **_k):
        return 200, {
            "success": False,
            "code": "param.stream.outTrackId",
            "message": "card is not exist",
        }

    cfg = _mindbot_cfg(
        organization_id=1,
        dingtalk_robot_code="r",
        dingtalk_app_secret="s",
        dingtalk_client_id="kid",
        dingtalk_ai_card_template_id="tpl-z",
        dingtalk_ai_card_param_key=None,
    )
    with patch(
        "services.mindbot.platforms.dingtalk.cards.ai_card_update.put_v1_json_unverified",
        new=fake_unverified,
    ):
        with patch(
            "services.mindbot.platforms.dingtalk.cards.ai_card_update.get_access_token_with_error",
            new=AsyncMock(return_value=("tok", "")),
        ):
            result = await probe_ai_card_streaming_update_api(cfg)
    assert result.ok is True
    assert result.http_status == 200
    assert result.error_token is None
    assert result.friendly_message is None


@pytest.mark.asyncio
async def test_probe_streaming_treats_missing_card_as_ok_http400() -> None:
    """DingTalk may return HTTP 400 with JSON body for unknown outTrackId."""

    async def fake_unverified(*_a, **_k):
        return 400, {
            "requestid": "73A9CE58-A5D3-7728-88A0-0273A525DA0A",
            "code": "param.stream.outTrackId",
            "message": "card is not exist",
        }

    cfg = _mindbot_cfg(
        organization_id=1,
        dingtalk_robot_code="r",
        dingtalk_app_secret="s",
        dingtalk_client_id="kid",
        dingtalk_ai_card_template_id="tpl-z",
        dingtalk_ai_card_param_key=None,
    )
    with patch(
        "services.mindbot.platforms.dingtalk.cards.ai_card_update.put_v1_json_unverified",
        new=fake_unverified,
    ):
        with patch(
            "services.mindbot.platforms.dingtalk.cards.ai_card_update.get_access_token_with_error",
            new=AsyncMock(return_value=("tok", "")),
        ):
            result = await probe_ai_card_streaming_update_api(cfg)
    assert result.ok is True
    assert result.http_status == 400
    assert result.error_token is None
    assert result.dingtalk_code == "param.stream.outTrackId"
    assert result.friendly_message is None


@pytest.mark.asyncio
async def test_probe_streaming_fails_without_template() -> None:
    cfg = _mindbot_cfg(
        organization_id=1,
        dingtalk_client_id="kid",
        dingtalk_ai_card_template_id=" ",
    )
    result = await probe_ai_card_streaming_update_api(cfg)
    assert result.ok is False
    assert result.error_token == "template_not_configured"
    assert result.http_status is None
