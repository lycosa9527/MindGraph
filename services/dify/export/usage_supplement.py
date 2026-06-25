"""
Supplement MindMate export with MindBot threads from usage telemetry.

DingTalk group chats share the same Dify ``user`` id as 1:1 but bind separate
``conversation_id`` rows per open group (Redis suffix includes staff). The Dify
conversation list can omit threads; usage events record every successful group
and 1:1 turn with ``dingtalk_chat_scope``.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from repositories.mindbot_usage_repo import MindbotExportThread, MindbotUsageRepository
from services.dify.export.raw_dump_index import MultiServerDumpStore
from services.dify.export.transcript import ExportConversationSummary
from services.dify.export.types import UserTarget
from utils.dify_user_key import parse_mindbot_dify_key

_USAGE_ENDPOINT_SOURCE = "mindbot_usage"


def _epoch_to_datetime(epoch: Optional[int]) -> datetime | None:
    if epoch is None:
        return None
    return datetime.fromtimestamp(int(epoch), UTC)


def _datetime_to_epoch(value: datetime) -> int:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return int(value.timestamp())


def _summary_key(dify_user: str, conversation_id: str) -> str:
    return f"{dify_user}:{conversation_id}"


def _thread_display_name(thread: MindbotExportThread) -> str:
    scope = (thread.dingtalk_chat_scope or "").strip().lower()
    nick = (thread.sender_nick or thread.dingtalk_staff_id or "").strip() or thread.dify_user_key
    if scope == "cross_org_group":
        return f"DingTalk cross-org group · {nick}"
    if scope == "group":
        return f"DingTalk group · {nick}"
    if scope in ("oto", "1:1"):
        return f"DingTalk 1:1 · {nick}"
    return f"DingTalk · {nick}"


def _staff_ids_for_org(targets: List[UserTarget], org_id: int) -> Set[str]:
    staff_ids: Set[str] = set()
    for target in targets:
        if target.channel != "mindbot" or int(target.organization_id) != int(org_id):
            continue
        _org, staff = parse_mindbot_dify_key(target.dify_user)
        if staff:
            staff_ids.add(staff)
    return staff_ids


def _summary_from_thread(
    thread: MindbotExportThread,
    target: UserTarget,
    *,
    server: int = 1,
) -> ExportConversationSummary:
    created = _datetime_to_epoch(thread.first_event_at)
    updated = _datetime_to_epoch(thread.last_event_at)
    return ExportConversationSummary(
        conversation_id=thread.dify_conversation_id,
        name=_thread_display_name(thread),
        server=server,
        organization_id=int(thread.organization_id),
        dify_user=thread.dify_user_key,
        user_id=target.user_id,
        user_label=target.label,
        channel="mindbot",
        created_at=created,
        updated_at=updated,
        mindbot_config_id=thread.mindbot_config_id,
        endpoint_source=_USAGE_ENDPOINT_SOURCE,
        dingtalk_chat_scope=thread.dingtalk_chat_scope,
        dingtalk_conversation_id=thread.dingtalk_conversation_id,
    )


def _target_for_thread(
    thread: MindbotExportThread,
    targets_by_dify: Dict[str, UserTarget],
) -> UserTarget | None:
    target = targets_by_dify.get(thread.dify_user_key)
    if target is not None:
        return target
    org_id = int(thread.organization_id)
    return UserTarget(
        organization_id=org_id,
        user_id=thread.linked_user_id,
        dify_user=thread.dify_user_key,
        label=_thread_display_name(thread),
        channel="mindbot",
    )


def _should_refresh_scope(
    prior_scope: Optional[str],
    thread_scope: Optional[str],
) -> bool:
    if not thread_scope:
        return False
    if not prior_scope:
        return True
    prior = prior_scope.strip().lower()
    incoming = thread_scope.strip().lower()
    if prior == incoming:
        return False
    if prior == "group" and incoming == "cross_org_group":
        return True
    return False


def _merge_thread_summary(
    prior: ExportConversationSummary,
    thread: MindbotExportThread,
) -> ExportConversationSummary:
    display_name = prior.name or _thread_display_name(thread)
    if _should_refresh_scope(prior.dingtalk_chat_scope, thread.dingtalk_chat_scope):
        display_name = _thread_display_name(thread)
    return ExportConversationSummary(
        conversation_id=prior.conversation_id,
        name=display_name,
        server=prior.server,
        organization_id=prior.organization_id,
        dify_user=prior.dify_user,
        user_id=prior.user_id,
        user_label=prior.user_label,
        channel=prior.channel,
        created_at=prior.created_at,
        updated_at=max(prior.updated_at, _datetime_to_epoch(thread.last_event_at)),
        mindbot_config_id=prior.mindbot_config_id or thread.mindbot_config_id,
        endpoint_source=prior.endpoint_source,
        dingtalk_chat_scope=thread.dingtalk_chat_scope or prior.dingtalk_chat_scope,
        dingtalk_conversation_id=thread.dingtalk_conversation_id or prior.dingtalk_conversation_id,
    )


async def supplement_mindbot_summaries_from_usage(
    db: AsyncSession,
    targets: List[UserTarget],
    summaries: List[ExportConversationSummary],
    *,
    start: Optional[int] = None,
    end: Optional[int] = None,
    dump_store: Optional[MultiServerDumpStore] = None,
) -> Tuple[List[ExportConversationSummary], List[str]]:
    """
    Merge usage-telemetry MindBot threads missing from Dify list collection.

    Returns updated summaries (deduped, newest ``updated_at`` first) and
    optional warning strings.
    """
    mindbot_targets = [target for target in targets if target.channel == "mindbot"]
    if not mindbot_targets:
        return summaries, []

    targets_by_dify = {target.dify_user: target for target in mindbot_targets}
    existing: Dict[str, ExportConversationSummary] = {}
    for summary in summaries:
        key = _summary_key(summary.dify_user, summary.conversation_id)
        prior = existing.get(key)
        if prior is None or summary.updated_at >= prior.updated_at:
            existing[key] = summary

    repo = MindbotUsageRepository(db)
    start_dt = _epoch_to_datetime(start)
    end_dt = _epoch_to_datetime(end)
    org_ids = {int(target.organization_id) for target in mindbot_targets}
    added = 0

    for org_id in sorted(org_ids):
        staff_ids = _staff_ids_for_org(mindbot_targets, org_id)
        thread_keys: Set[str] = set()
        org_threads: List[MindbotExportThread] = []
        thread_batches: List[List[MindbotExportThread]] = []
        if staff_ids:
            thread_batches.append(
                await repo.list_dify_threads_for_export(
                    org_id,
                    staff_ids=staff_ids,
                    start=start_dt,
                    end=end_dt,
                )
            )
        thread_batches.append(
            await repo.list_dify_threads_for_export(
                org_id,
                chat_scopes={"cross_org_group"},
                start=start_dt,
                end=end_dt,
            )
        )
        for batch in thread_batches:
            for thread in batch:
                key = _summary_key(thread.dify_user_key, thread.dify_conversation_id)
                if key in thread_keys:
                    continue
                thread_keys.add(key)
                org_threads.append(thread)

        for thread in org_threads:
            key = _summary_key(thread.dify_user_key, thread.dify_conversation_id)
            if key in existing:
                prior = existing[key]
                if _should_refresh_scope(prior.dingtalk_chat_scope, thread.dingtalk_chat_scope):
                    existing[key] = _merge_thread_summary(prior, thread)
                continue
            target = _target_for_thread(thread, targets_by_dify)
            if target is None:
                continue
            server = 1
            if dump_store is not None:
                found = dump_store.find_conversation_server(thread.dify_conversation_id)
                if found is not None:
                    server = found
            existing[key] = _summary_from_thread(thread, target, server=server)
            added += 1

    warnings: List[str] = []
    if added > 0:
        warnings.append(f"mindbot_usage_threads_merged: added={added}")

    merged = sorted(existing.values(), key=lambda item: item.updated_at, reverse=True)
    return merged, warnings
