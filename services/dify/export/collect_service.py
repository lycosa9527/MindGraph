"""
Collect MindMate (Dify) conversation history for export.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from clients.dify import AsyncDifyClient
from models.domain.auth import Organization
from services.dify.export.endpoints import ExportDifyEndpoint, endpoints_for_target
from services.dify.export.export_config import LIST_PAGE_DEFAULT, LIST_PAGE_MAX
from services.dify.export.time_range import conversation_overlaps_export_range
from services.dify.export.transcript import (
    ExportBubble,
    ExportBundle,
    ExportConversation,
    ExportConversationSummary,
    conversation_created_at,
    split_message_to_bubbles,
)
from services.dify.export.types import ControlCallback, ProgressCallback, TargetFetchResult, UserTarget
from services.dify.export.usage_supplement import supplement_mindbot_summaries_from_usage
from services.utils.error_types import DIFY_API_ERRORS
from utils.db.session_open import release_open_transaction, system_rls_session

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 100
MAX_PAGES = 200
DEFAULT_CONCURRENCY = 8
EXPORT_CLIENT_TIMEOUT_SECONDS = 120


@dataclass
class FetchPageResult:
    """Paginated Dify list fetch with completeness metadata."""

    items: List[dict] = field(default_factory=list)
    pagination_complete: bool = True
    warning: Optional[str] = None


@dataclass
class CollectResult:
    """Summaries plus structured fetch metadata from one collection pass."""

    summaries: List[ExportConversationSummary] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    target_results: List[TargetFetchResult] = field(default_factory=list)
    partial_failures: int = 0
    skipped_targets: int = 0


@dataclass
class CollectOptions:
    """Optional callbacks for job control and progress reporting."""

    control: Optional[ControlCallback] = None
    progress: Optional[ProgressCallback] = None


def _client_for(endpoint: ExportDifyEndpoint) -> AsyncDifyClient:
    return AsyncDifyClient(
        api_key=endpoint.api_key,
        api_url=endpoint.api_url,
        timeout=EXPORT_CLIENT_TIMEOUT_SECONDS,
    )


async def _fetch_all_conversations(client: AsyncDifyClient, dify_user: str) -> FetchPageResult:
    """Fully paginate a user's conversation list (newest-first ``last_id``)."""
    out: List[dict] = []
    last_id: Optional[str] = None
    pages = 0
    pagination_complete = True
    warning: Optional[str] = None
    for _ in range(MAX_PAGES):
        pages += 1
        resp = await client.get_conversations(dify_user, last_id=last_id, limit=DEFAULT_PAGE_SIZE)
        data = resp.get("data") or []
        if not data:
            break
        out.extend(item for item in data if isinstance(item, dict))
        if not resp.get("has_more"):
            break
        last_id = data[-1].get("id")
        if not last_id:
            break
    else:
        pagination_complete = False
        warning = f"dify_pagination_cap: conversations user={dify_user} pages={MAX_PAGES}"
    if pages >= MAX_PAGES and out and pagination_complete:
        pagination_complete = False
        warning = f"dify_pagination_cap: conversations user={dify_user} pages={MAX_PAGES}"
    return FetchPageResult(items=out, pagination_complete=pagination_complete, warning=warning)


def _message_sort_key(message: dict) -> int:
    raw = message.get("created_at") or 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


async def _fetch_all_messages(
    client: AsyncDifyClient,
    conversation_id: str,
    dify_user: str,
) -> FetchPageResult:
    """Fully paginate a conversation's messages (older via ``first_id``)."""
    collected: List[dict] = []
    first_id: Optional[str] = None
    pagination_complete = True
    warning: Optional[str] = None
    for _ in range(MAX_PAGES):
        resp = await client.get_messages(
            conversation_id,
            dify_user,
            first_id=first_id,
            limit=DEFAULT_PAGE_SIZE,
        )
        data = resp.get("data") or []
        if not data:
            break
        collected.extend(item for item in data if isinstance(item, dict))
        if not resp.get("has_more"):
            break
        first_id = data[-1].get("id")
        if not first_id:
            break
    else:
        pagination_complete = False
        warning = (
            f"dify_pagination_cap: messages conv={conversation_id} user={dify_user} pages={MAX_PAGES}"
        )
    collected.sort(key=_message_sort_key)
    return FetchPageResult(items=collected, pagination_complete=pagination_complete, warning=warning)


def _within_range(created_at: int, start: Optional[int], end: Optional[int]) -> bool:
    if start is not None and created_at < start:
        return False
    if end is not None and created_at > end:
        return False
    return True


def _conversation_in_export_range(
    created_at: int,
    updated_at: int,
    start: Optional[int],
    end: Optional[int],
) -> bool:
    """Include conversations with any activity overlapping the export window."""
    return conversation_overlaps_export_range(created_at, updated_at, start, end)


async def _should_continue(options: Optional[CollectOptions]) -> bool:
    if options is None or options.control is None:
        return True
    result = options.control()
    if isinstance(result, bool):
        return result
    return await result


async def _load_org(org_id: int) -> Optional[Organization]:
    async with system_rls_session() as db:
        return (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()


async def _summaries_for_target_endpoint(
    target: UserTarget,
    endpoint: ExportDifyEndpoint,
    start: Optional[int],
    end: Optional[int],
    semaphore: asyncio.Semaphore,
) -> Tuple[List[ExportConversationSummary], TargetFetchResult]:
    """Conversation summaries for one user on one endpoint (failure-tolerant)."""
    fetch_result = TargetFetchResult(
        dify_user=target.dify_user,
        endpoint_source=endpoint.source,
        server=endpoint.server,
        organization_id=target.organization_id,
        channel=target.channel,
    )
    async with semaphore:
        client = _client_for(endpoint)
        try:
            page = await _fetch_all_conversations(client, target.dify_user)
        except DIFY_API_ERRORS as exc:
            logger.warning(
                "[MindMateExport] conversations fetch failed user=%s endpoint=%s/%s: %s",
                target.dify_user,
                endpoint.source,
                endpoint.server,
                exc,
            )
            fetch_result.fetch_errors.append(str(exc))
            fetch_result.pagination_complete = False
            return [], fetch_result

    fetch_result.pagination_complete = page.pagination_complete
    if page.warning:
        fetch_result.fetch_errors.append(page.warning)

    out: List[ExportConversationSummary] = []
    for conv in page.items:
        created = conversation_created_at(conv)
        updated = int(conv.get("updated_at") or created)
        if not _conversation_in_export_range(created, updated, start, end):
            continue
        conv_id = str(conv.get("id") or "")
        out.append(
            ExportConversationSummary(
                conversation_id=conv_id,
                name=str(conv.get("name") or ""),
                server=endpoint.server,
                organization_id=target.organization_id,
                dify_user=target.dify_user,
                user_id=target.user_id,
                user_label=target.label,
                channel=target.channel,
                mindbot_config_id=endpoint.mindbot_config_id,
                endpoint_source=endpoint.source,
                created_at=created,
                updated_at=updated,
            )
        )
    fetch_result.conversations_fetched = len(out)
    return out, fetch_result


def _dedupe_summaries(
    summaries: List[ExportConversationSummary],
) -> List[ExportConversationSummary]:
    merged: Dict[str, ExportConversationSummary] = {}
    for summary in summaries:
        if not summary.conversation_id:
            continue
        key = f"{summary.dify_user}:{summary.conversation_id}"
        existing = merged.get(key)
        if existing is None or summary.updated_at >= existing.updated_at:
            merged[key] = summary
    return sorted(merged.values(), key=lambda item: item.updated_at, reverse=True)


def encode_summary_cursor(summary: ExportConversationSummary) -> str:
    """Encode pagination cursor from one conversation summary."""
    return f"{summary.updated_at}:{summary.conversation_id}"


def decode_summary_cursor(raw: Optional[str]) -> Tuple[Optional[int], Optional[str]]:
    """Decode pagination cursor into updated_at and conversation_id."""
    if not raw:
        return None, None
    if ":" not in raw:
        return None, None
    ts_raw, conv_id = raw.split(":", 1)
    try:
        return int(ts_raw), conv_id
    except ValueError:
        return None, None


def paginate_summaries(
    summaries: List[ExportConversationSummary],
    *,
    cursor: Optional[str] = None,
    limit: int = LIST_PAGE_DEFAULT,
) -> Tuple[List[ExportConversationSummary], Optional[str], bool]:
    """Slice deduped summaries (newest first) for list API pagination."""
    page_size = max(1, min(limit, LIST_PAGE_MAX))
    cursor_ts, cursor_id = decode_summary_cursor(cursor)
    start_idx = 0
    if cursor_ts is not None and cursor_id:
        for idx, item in enumerate(summaries):
            if item.updated_at < cursor_ts:
                start_idx = idx
                break
            if item.updated_at == cursor_ts and item.conversation_id == cursor_id:
                start_idx = idx + 1
                break
    page = summaries[start_idx : start_idx + page_size]
    has_more = start_idx + page_size < len(summaries)
    next_cursor = encode_summary_cursor(page[-1]) if page and has_more else None
    return page, next_cursor, has_more


async def collect_conversation_summaries(
    db: AsyncSession,
    targets: List[UserTarget],
    *,
    start: Optional[int] = None,
    end: Optional[int] = None,
    concurrency: int = DEFAULT_CONCURRENCY,
    strict_org: bool = False,
    options: Optional[CollectOptions] = None,
) -> CollectResult:
    """List conversations across orgs/endpoints for the in-scope Dify identities."""
    return await collect_conversation_summaries_batch(
        db,
        targets,
        start=start,
        end=end,
        concurrency=concurrency,
        strict_org=strict_org,
        options=options,
    )


async def collect_conversation_summaries_batch(
    db: AsyncSession,
    targets: List[UserTarget],
    *,
    start: Optional[int] = None,
    end: Optional[int] = None,
    concurrency: int = DEFAULT_CONCURRENCY,
    strict_org: bool = False,
    options: Optional[CollectOptions] = None,
) -> CollectResult:
    """List conversations for targets; commits DB reads before Dify HTTP fan-out."""
    if not targets:
        return CollectResult()

    org_by_id: Dict[int, Organization] = {}
    for org_id in {target.organization_id for target in targets}:
        org = await _load_org(org_id)
        if org is not None:
            org_by_id[org_id] = org

    endpoint_cache: Dict[tuple[int, str, str], List[ExportDifyEndpoint]] = {}
    warnings: List[str] = []
    target_results: List[TargetFetchResult] = []
    partial_failures = 0
    skipped_targets = 0
    semaphore = asyncio.Semaphore(max(1, concurrency))
    tasks = []

    for target in targets:
        if not await _should_continue(options):
            break
        org = org_by_id.get(target.organization_id)
        if org is None:
            warnings.append(f"organization {target.organization_id} not found")
            skipped_targets += 1
            continue
        cache_key = (target.organization_id, target.channel, target.dify_user)
        if cache_key not in endpoint_cache:
            endpoint_cache[cache_key] = await endpoints_for_target(
                org,
                channel=target.channel,
                dify_user=target.dify_user,
                db=db,
                strict_org=strict_org,
            )
        endpoints = endpoint_cache[cache_key]
        if not endpoints:
            warnings.append(
                f"no Dify endpoints for org={target.organization_id} channel={target.channel}"
            )
            skipped_targets += 1
            continue
        for endpoint in endpoints:
            tasks.append(
                _summaries_for_target_endpoint(target, endpoint, start, end, semaphore)
            )

    if not tasks:
        return CollectResult(
            warnings=warnings,
            partial_failures=partial_failures,
            skipped_targets=skipped_targets,
        )

    await release_open_transaction(db)
    results = await asyncio.gather(*tasks)
    flat: List[ExportConversationSummary] = []
    for chunk, fetch_meta in results:
        flat.extend(chunk)
        target_results.append(fetch_meta)
        if fetch_meta.fetch_errors:
            partial_failures += 1
            warnings.extend(fetch_meta.fetch_errors)

    deduped = _dedupe_summaries(flat)
    deduped, usage_warnings = await supplement_mindbot_summaries_from_usage(
        db,
        targets,
        deduped,
        start=start,
        end=end,
    )
    if usage_warnings:
        warnings.extend(usage_warnings)
    if options and options.progress:
        options.progress("fetching_conversations", len(deduped), len(deduped), {})
    return CollectResult(
        summaries=deduped,
        warnings=warnings,
        target_results=target_results,
        partial_failures=partial_failures,
        skipped_targets=skipped_targets,
    )


async def fetch_conversation_bubbles(
    endpoint: ExportDifyEndpoint,
    conversation_id: str,
    dify_user: str,
) -> Tuple[List[ExportBubble], bool, Optional[str]]:
    """Bubbles for one conversation; returns (bubbles, pagination_complete, warning)."""
    client = _client_for(endpoint)
    try:
        page = await _fetch_all_messages(client, conversation_id, dify_user)
    except DIFY_API_ERRORS as exc:
        logger.warning(
            "[MindMateExport] messages fetch failed conv=%s endpoint=%s/%s: %s",
            conversation_id,
            endpoint.source,
            endpoint.server,
            exc,
        )
        return [], False, str(exc)
    bubbles: List[ExportBubble] = []
    for message in page.items:
        bubbles.extend(split_message_to_bubbles(message, endpoint.server))
    return bubbles, page.pagination_complete, page.warning


async def _conversation_with_bubbles(
    summary: ExportConversationSummary,
    endpoint: ExportDifyEndpoint,
    semaphore: asyncio.Semaphore,
) -> Tuple[Optional[ExportConversation], bool, Optional[str]]:
    """Build a full conversation (with bubbles) from a summary."""
    async with semaphore:
        bubbles, complete, warning = await fetch_conversation_bubbles(
            endpoint,
            summary.conversation_id,
            summary.dify_user,
        )
    conv = ExportConversation(
        conversation_id=summary.conversation_id,
        name=summary.name,
        server=summary.server,
        organization_id=summary.organization_id,
        dify_user=summary.dify_user,
        user_id=summary.user_id,
        user_label=summary.user_label,
        channel=summary.channel,
        mindbot_config_id=summary.mindbot_config_id,
        endpoint_source=summary.endpoint_source,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
        dingtalk_chat_scope=summary.dingtalk_chat_scope,
        dingtalk_conversation_id=summary.dingtalk_conversation_id,
        bubbles=bubbles,
    )
    return conv, complete, warning


async def _endpoint_for_summary(
    db: AsyncSession,
    summary: ExportConversationSummary,
    org_by_id: Dict[int, Organization],
    endpoint_cache: Dict[tuple[int, str, str], List[ExportDifyEndpoint]],
    *,
    strict_org: bool,
) -> Optional[ExportDifyEndpoint]:
    org = org_by_id.get(summary.organization_id)
    if org is None:
        return None
    cache_key = (summary.organization_id, summary.channel, summary.dify_user)
    if cache_key not in endpoint_cache:
        endpoint_cache[cache_key] = await endpoints_for_target(
            org,
            channel=summary.channel,
            dify_user=summary.dify_user,
            db=db,
            strict_org=strict_org,
        )
    endpoints = endpoint_cache[cache_key]
    if summary.mindbot_config_id is not None:
        for endpoint in endpoints:
            if endpoint.mindbot_config_id == summary.mindbot_config_id:
                return endpoint
    for endpoint in endpoints:
        if endpoint.server == summary.server:
            return endpoint
    return endpoints[0] if endpoints else None


async def collect_messages_for_summaries(
    db: AsyncSession,
    summaries: List[ExportConversationSummary],
    *,
    concurrency: int = DEFAULT_CONCURRENCY,
    strict_org: bool = False,
    options: Optional[CollectOptions] = None,
) -> Tuple[List[ExportConversation], List[str], Dict[str, bool]]:
    """Fetch full message bodies for conversation summaries."""
    org_by_id: Dict[int, Organization] = {}
    for org_id in {summary.organization_id for summary in summaries}:
        org = await _load_org(org_id)
        if org is not None:
            org_by_id[org_id] = org

    endpoint_cache: Dict[tuple[int, str, str], List[ExportDifyEndpoint]] = {}
    semaphore = asyncio.Semaphore(max(1, concurrency))
    tasks = []
    for summary in summaries:
        if not await _should_continue(options):
            break
        endpoint = await _endpoint_for_summary(
            db,
            summary,
            org_by_id,
            endpoint_cache,
            strict_org=strict_org,
        )
        if endpoint is None:
            continue
        tasks.append(_conversation_with_bubbles(summary, endpoint, semaphore))

    warnings: List[str] = []
    messages_complete: Dict[str, bool] = {}
    if tasks:
        await release_open_transaction(db)
    built = await asyncio.gather(*tasks) if tasks else []
    conversations: List[ExportConversation] = []
    for item in built:
        if item[0] is None:
            continue
        conv, complete, warning = item
        conversations.append(conv)
        key = f"{conv.dify_user}:{conv.conversation_id}"
        messages_complete[key] = complete
        if warning:
            warnings.append(warning)
    return conversations, warnings, messages_complete


async def collect_bundle(
    db: AsyncSession,
    organization_id: Optional[int],
    organization_name: str,
    scope: str,
    targets: List[UserTarget],
    *,
    start: Optional[int] = None,
    end: Optional[int] = None,
    concurrency: int = DEFAULT_CONCURRENCY,
    strict_org: bool = False,
    options: Optional[CollectOptions] = None,
    verification_report: Optional[dict] = None,
) -> ExportBundle:
    """Full export bundle (conversations + bubbles) for download."""
    collected = await collect_conversation_summaries_batch(
        db,
        targets,
        start=start,
        end=end,
        concurrency=concurrency,
        strict_org=strict_org,
        options=options,
    )
    conversations, msg_warnings, _messages_complete = await collect_messages_for_summaries(
        db,
        collected.summaries,
        concurrency=concurrency,
        strict_org=strict_org,
        options=options,
    )
    all_warnings = list(collected.warnings) + msg_warnings
    return ExportBundle(
        organization_id=organization_id,
        organization_name=organization_name,
        scope=scope,
        conversations=conversations,
        warnings=all_warnings,
        partial_failures=collected.partial_failures,
        verification_report=verification_report,
    )
