"""
Pre-compiled SQLAlchemy statements for the online-collab hot paths.

SQLAlchemy 2.x caches compiled SQL in an LRU keyed by the statement clause
object's identity/shape.  Statements built at module import time are pinned in
the ``query_cache_size`` LRU permanently — they can never be evicted because
the clause objects live for the lifetime of the process.  Runtime-constructed
statements (e.g. inside request handlers) compete for the same cache slots.

All statements use explicit ``bindparam`` placeholders so they can be reused
across calls by passing a parameter dict to ``db.execute()``.

Usage
-----
    from services.online_collab.db.online_collab_stmt_cache import (
        STMT_DIAGRAM_BY_ID,
        STMT_DIAGRAM_SPEC_BY_ID,
    )
    row = await db.execute(STMT_DIAGRAM_BY_ID, {"p_id": diagram_id})

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from sqlalchemy import bindparam, select, update as sa_update

from models.domain.diagrams import Diagram

STMT_DIAGRAM_BY_ID = (
    select(Diagram)
    .where(
        Diagram.id == bindparam("p_id"),
        ~Diagram.is_deleted,
    )
)

STMT_DIAGRAM_SPEC_BY_ID = (
    select(Diagram.id, Diagram.spec)
    .where(
        Diagram.id == bindparam("p_id"),
        ~Diagram.is_deleted,
    )
)

STMT_DIAGRAM_UPDATE_SPEC = (
    sa_update(Diagram)
    .where(
        Diagram.id == bindparam("p_id"),
        ~Diagram.is_deleted,
    )
    .values(spec=bindparam("p_spec"))
    .returning(Diagram.id)
)
