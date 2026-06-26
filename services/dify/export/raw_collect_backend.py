"""
Raw dump backend for MindMate export collection.

Live Dify Service API collection is disabled; exports read PostgreSQL dump
snapshots only (upload via admin **Dify raw dumps** tab).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set

from services.dify.export.endpoints import ExportDifyEndpoint
from services.dify.export.raw_dump_config import resolve_raw_dump_dir
from services.dify.export.raw_dump_import import import_pending_zips
from services.dify.export.raw_dump_index import DumpIndex, MultiServerDumpStore


@dataclass
class BackendPageResult:
    """Paginated fetch result from a raw dump snapshot."""

    items: List[dict] = field(default_factory=list)
    pagination_complete: bool = True
    warning: Optional[str] = None
    source: str = "dump"


class ExportSourceRouter:
    """Read conversations and messages from raw dump snapshots only."""

    def __init__(self, store: Optional[MultiServerDumpStore] = None) -> None:
        self.store = store
        self.warnings: List[str] = []
        self.dump_used_slots: Set[int] = set()

    @classmethod
    def bootstrap(cls, base_dir: Optional[Path] = None) -> "ExportSourceRouter":
        """Import pending zips and load dump store for one export pass."""
        root = base_dir or resolve_raw_dump_dir()
        import_result = import_pending_zips(root)
        store = MultiServerDumpStore.load(root)
        router = cls(store)
        if import_result.imported:
            router.warnings.append(f"dump_imported: count={len(import_result.imported)}")
        for err in import_result.errors:
            router.warnings.append(f"dump_import_error: {err}")
        router.warnings.extend(store.warnings)
        return router

    @classmethod
    def from_store(cls, base_dir: Optional[Path] = None) -> "ExportSourceRouter":
        """Load dump store without importing incoming zips (job resume)."""
        root = base_dir or resolve_raw_dump_dir()
        store = MultiServerDumpStore.load(root)
        router = cls(store)
        router.warnings.extend(store.warnings)
        return router

    def _dump_index_for_endpoint(self, endpoint: ExportDifyEndpoint) -> Optional[DumpIndex]:
        if self.store is None:
            return None
        snapshot = self.store.snapshot_for_slot(endpoint.server)
        if snapshot is None or not snapshot.is_usable():
            return None
        if snapshot.is_stale():
            return None
        return self.store.index_for_slot(endpoint.server)

    def _missing_dump_result(self, endpoint: ExportDifyEndpoint) -> BackendPageResult:
        snapshot = self.store.snapshot_for_slot(endpoint.server) if self.store else None
        if snapshot is None:
            self.warnings.append(f"dump_snapshot_missing: server={endpoint.server}")
            warning = f"dump_snapshot_missing: server={endpoint.server}"
        else:
            self.warnings.append(f"dump_unusable: server={endpoint.server}")
            warning = f"dump_unusable: server={endpoint.server}"
        return BackendPageResult(
            items=[],
            pagination_complete=False,
            warning=warning,
            source="dump",
        )

    async def fetch_conversations(
        self,
        _client,
        endpoint: ExportDifyEndpoint,
        dify_user: str,
        _fetch_all_conversations,
    ) -> BackendPageResult:
        """List conversations for one user from the raw dump for this server slot."""
        del _client, _fetch_all_conversations
        index = self._dump_index_for_endpoint(endpoint)
        if index is None:
            return self._missing_dump_result(endpoint)
        app_ids = index.app_ids_for_api_keys([endpoint.api_key])
        items = index.list_conversations_for_user(dify_user, app_ids)
        self.dump_used_slots.add(endpoint.server)
        return BackendPageResult(items=items, pagination_complete=True, source="dump")

    async def fetch_messages(
        self,
        _client,
        endpoint: ExportDifyEndpoint,
        conversation_id: str,
        _dify_user: str,
        _fetch_all_messages,
    ) -> BackendPageResult:
        """Fetch message bodies for one conversation from the raw dump."""
        del _client, _dify_user, _fetch_all_messages
        index = self._dump_index_for_endpoint(endpoint)
        if index is None:
            return self._missing_dump_result(endpoint)
        items = index.fetch_messages_for_conversation(conversation_id)
        if not items:
            self.warnings.append(f"dump_unusable: messages conv={conversation_id} server={endpoint.server}")
            return BackendPageResult(
                items=[],
                pagination_complete=False,
                warning=f"dump_unusable: messages conv={conversation_id}",
                source="dump",
            )
        self.dump_used_slots.add(endpoint.server)
        return BackendPageResult(items=items, pagination_complete=True, source="dump")
