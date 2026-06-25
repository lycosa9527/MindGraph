"""
Lazy CSV indexes over one Dify raw dump snapshot.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Set

from services.dify.export.raw_dump_config import DUMP_SERVER_LABELS
from services.dify.export.raw_dump_manifest import DumpSnapshot, DumpStoreState
from services.dify.export.raw_dump_store import resolve_dump_store
from services.dify.export.raw_message_adapter import (
    api_message_files_from_rows,
    conversation_created_at,
    conversation_updated_at,
    row_to_api_message,
)

logger = logging.getLogger(__name__)


class DumpIndex:
    """In-memory indexes built from one snapshot's CSV files."""

    def __init__(self, snapshot: DumpSnapshot) -> None:
        self.snapshot = snapshot
        self.root = snapshot.path
        self.label = snapshot.label
        self.server_slot = snapshot.mindgraph_slot
        self._token_to_app_id: Optional[Dict[str, str]] = None
        self._app_ids_for_tokens: Optional[Dict[frozenset[str], Set[str]]] = None
        self._conversation_index: Optional[Dict[str, dict]] = None
        self._message_files_by_message: Optional[Dict[str, List[dict]]] = None
        self._feedback_by_message: Optional[Dict[str, str]] = None
        self.parse_errors = 0

    def _read_csv_rows(self, table: str) -> Iterator[dict]:
        path = self.root / f"{table}.csv"
        if not path.is_file():
            return
        try:
            with path.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                yield from reader
        except csv.Error as exc:
            self.parse_errors += 1
            logger.warning("[RawDump] csv parse error %s: %s", path, exc)

    def token_to_app_id(self) -> Dict[str, str]:
        """Map Service API token string to app_id (type=app only)."""
        if self._token_to_app_id is not None:
            return self._token_to_app_id
        mapping: Dict[str, str] = {}
        for row in self._read_csv_rows("api_tokens"):
            token_type = str(row.get("type") or "").strip().lower()
            if token_type and token_type != "app":
                continue
            token = str(row.get("token") or "").strip()
            app_id = str(row.get("app_id") or "").strip()
            if token and app_id:
                mapping[token] = app_id
        self._token_to_app_id = mapping
        return mapping

    def app_ids_for_api_keys(self, api_keys: Iterable[str]) -> Set[str]:
        """Resolve allowed app_ids for a set of MindGraph API keys."""
        tokens = frozenset(key.strip() for key in api_keys if key and str(key).strip())
        if self._app_ids_for_tokens is None:
            self._app_ids_for_tokens = {}
        cached = self._app_ids_for_tokens.get(tokens)
        if cached is not None:
            return set(cached)
        token_map = self.token_to_app_id()
        app_ids = {token_map[key] for key in tokens if key in token_map}
        self._app_ids_for_tokens[tokens] = set(app_ids)
        return set(app_ids)

    def _build_end_user_id_to_session(self) -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        for row in self._read_csv_rows("end_users"):
            user_id = str(row.get("id") or "").strip()
            session_id = str(row.get("session_id") or "").strip()
            if user_id and session_id:
                mapping[user_id] = session_id
        return mapping

    def _build_conversation_index(self) -> Dict[str, dict]:
        end_user_sessions = self._build_end_user_id_to_session()
        conv_index: Dict[str, dict] = {}
        for row in self._read_csv_rows("conversations"):
            conv_id = str(row.get("id") or "").strip()
            if not conv_id:
                continue
            end_user_id = str(row.get("from_end_user_id") or "").strip()
            session_id = end_user_sessions.get(end_user_id, "")
            created = conversation_created_at(row)
            updated = conversation_updated_at(row)
            conv_index[conv_id] = {
                **row,
                "session_id": session_id,
                "created_epoch": created,
                "updated_epoch": updated or created,
            }
        return conv_index

    def conversation_index(self) -> Dict[str, dict]:
        """Lazy conversation_id → row map including resolved session_id."""
        if self._conversation_index is None:
            self._conversation_index = self._build_conversation_index()
        return self._conversation_index

    def has_conversation(self, conversation_id: str) -> bool:
        """Return True when conversation_id exists in this snapshot."""
        return conversation_id in self.conversation_index()

    def list_conversations_for_user(
        self,
        dify_user: str,
        allowed_app_ids: Set[str],
    ) -> List[dict]:
        """Return API-shaped conversation dicts for one session_id."""
        if not allowed_app_ids:
            return []
        out: List[dict] = []
        for conv_id, row in self.conversation_index().items():
            session_id = str(row.get("session_id") or "")
            app_id = str(row.get("app_id") or "")
            if session_id != dify_user or app_id not in allowed_app_ids:
                continue
            created = int(row.get("created_epoch") or 0)
            updated = int(row.get("updated_epoch") or created)
            out.append(
                {
                    "id": conv_id,
                    "name": row.get("name") or "",
                    "created_at": created,
                    "updated_at": updated or created,
                    "app_id": app_id,
                }
            )
        out.sort(key=lambda item: int(item.get("updated_at") or 0), reverse=True)
        return out

    def _message_files_index(self) -> Dict[str, List[dict]]:
        if self._message_files_by_message is not None:
            return self._message_files_by_message
        grouped: Dict[str, List[dict]] = {}
        for row in self._read_csv_rows("message_files"):
            message_id = str(row.get("message_id") or "").strip()
            if not message_id:
                continue
            grouped.setdefault(message_id, []).append(row)
        self._message_files_by_message = grouped
        return grouped

    def _feedback_index(self) -> Dict[str, str]:
        if self._feedback_by_message is not None:
            return self._feedback_by_message
        grouped: Dict[str, str] = {}
        for row in self._read_csv_rows("message_feedbacks"):
            message_id = str(row.get("message_id") or "").strip()
            rating = str(row.get("rating") or "").strip()
            if message_id and rating:
                grouped[message_id] = rating
        self._feedback_by_message = grouped
        return grouped

    def fetch_messages_for_conversation(self, conversation_id: str) -> List[dict]:
        """Scan messages.csv for one conversation (streaming, no full load)."""
        files_index = self._message_files_index()
        feedback_index = self._feedback_index()
        messages: List[dict] = []
        for row in self._read_csv_rows("messages"):
            if str(row.get("conversation_id") or "").strip() != conversation_id:
                continue
            status = str(row.get("status") or "").strip().lower()
            if status == "error":
                continue
            message_id = str(row.get("id") or "").strip()
            file_rows = files_index.get(message_id, [])
            rating = feedback_index.get(message_id)
            messages.append(
                row_to_api_message(
                    row,
                    files=api_message_files_from_rows(file_rows),
                    feedback_rating=rating,
                )
            )
        messages.sort(key=lambda item: int(item.get("created_at") or 0))
        return messages


class MultiServerDumpStore:
    """Latest dump index per dify/neodify label."""

    def __init__(self, state: DumpStoreState) -> None:
        self.state = state
        self.warnings = list(state.warnings)
        self._indexes: Dict[str, DumpIndex] = {}

    @classmethod
    def load(cls, base_dir: Optional[Path] = None) -> "MultiServerDumpStore":
        """Load latest dify/neodify snapshots from base_dir."""
        state = resolve_dump_store(base_dir)
        return cls(state)

    def labels(self) -> List[str]:
        """Return server labels with at least one loaded snapshot."""
        return list(self.state.snapshots.keys())

    def snapshot_for_slot(self, server: int) -> Optional[DumpSnapshot]:
        """Return snapshot for MindGraph export server slot (1 or 2)."""
        for label in DUMP_SERVER_LABELS:
            snapshot = self.state.snapshots.get(label)
            if snapshot is not None and snapshot.mindgraph_slot == int(server):
                return snapshot
        return None

    def index_for_slot(self, server: int) -> Optional[DumpIndex]:
        """Return CSV index for MindGraph export server slot."""
        snapshot = self.snapshot_for_slot(server)
        if snapshot is None:
            return None
        label = snapshot.label
        if label not in self._indexes:
            self._indexes[label] = DumpIndex(snapshot)
        return self._indexes[label]

    def find_conversation_server(self, conversation_id: str) -> Optional[int]:
        """Return MindGraph server slot if conversation exists in any loaded dump."""
        for label in DUMP_SERVER_LABELS:
            snapshot = self.state.snapshots.get(label)
            if snapshot is None:
                continue
            index = self._indexes.get(label)
            if index is None:
                index = DumpIndex(snapshot)
                self._indexes[label] = index
            if index.has_conversation(conversation_id):
                return snapshot.mindgraph_slot
        return None

    def data_source_summary(self) -> dict:
        """Summary for verification report / admin UI."""
        per_label: Dict[str, str] = {}
        for label in DUMP_SERVER_LABELS:
            snapshot = self.state.snapshots.get(label)
            if snapshot is None:
                per_label[label] = "missing"
            elif str(snapshot.manifest.get("store_kind") or "").strip().lower() == "library":
                per_label[label] = "library"
            elif snapshot.is_stale():
                per_label[label] = "stale"
            else:
                per_label[label] = "dump"
        return {"per_label": per_label}
