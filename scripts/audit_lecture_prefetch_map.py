"""Fresh canvas mind map for the 思维讲堂 lookahead audit."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select

from models.domain.auth import User
from models.domain.diagrams import Diagram, generate_uuid
from repositories.diagram_repo import DiagramRepository
from utils.db.session_open import system_rls_session

PREFETCH_MAP_TITLE = "思维讲堂预取审计"
TOPIC_ID = "topic"
BRANCH_ONE_ID = "branch-1"
BRANCH_TWO_ID = "branch-2"
BRANCH_THREE_ID = "branch-3"


def _node(
    node_id: str,
    text: str,
    kind: str,
    x: float,
    y: float,
    *,
    depth: int,
    side: str,
) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": kind,
        "text": text,
        "position": {"x": x, "y": y},
        "data": {
            "mindMapUid": node_id,
            "mindMapSide": side,
            "mindMapDepth": depth,
        },
    }


def _edge(source: str, target: str) -> dict[str, Any]:
    return {
        "id": f"e-{source}-{target}",
        "source": source,
        "target": target,
    }


def build_prefetch_mindmap() -> dict[str, Any]:
    """Topic plus three first-level trunks so branch 1 has a next slide."""
    nodes = [
        _node(TOPIC_ID, "光合作用", "topic", 400.0, 300.0, depth=0, side="right"),
        _node(BRANCH_ONE_ID, "光反应", "branch", 620.0, 160.0, depth=1, side="right"),
        _node("leaf-1a", "叶绿素吸收光能", "branch", 840.0, 120.0, depth=2, side="right"),
        _node("leaf-1b", "形成 ATP 与 NADPH", "branch", 840.0, 200.0, depth=2, side="right"),
        _node(BRANCH_TWO_ID, "暗反应", "branch", 620.0, 300.0, depth=1, side="right"),
        _node("leaf-2a", "碳固定", "branch", 840.0, 260.0, depth=2, side="right"),
        _node("leaf-2b", "合成糖类", "branch", 840.0, 340.0, depth=2, side="right"),
        _node(BRANCH_THREE_ID, "影响因素", "branch", 620.0, 440.0, depth=1, side="right"),
        _node("leaf-3a", "光照强度", "branch", 840.0, 400.0, depth=2, side="right"),
        _node("leaf-3b", "二氧化碳浓度", "branch", 840.0, 480.0, depth=2, side="right"),
    ]
    connections = [
        _edge(TOPIC_ID, BRANCH_ONE_ID),
        _edge(BRANCH_ONE_ID, "leaf-1a"),
        _edge(BRANCH_ONE_ID, "leaf-1b"),
        _edge(TOPIC_ID, BRANCH_TWO_ID),
        _edge(BRANCH_TWO_ID, "leaf-2a"),
        _edge(BRANCH_TWO_ID, "leaf-2b"),
        _edge(TOPIC_ID, BRANCH_THREE_ID),
        _edge(BRANCH_THREE_ID, "leaf-3a"),
        _edge(BRANCH_THREE_ID, "leaf-3b"),
    ]
    return {
        "type": "mindmap",
        "topic": "光合作用",
        "nodes": nodes,
        "connections": connections,
    }


async def pick_map_owner() -> tuple[int, Optional[int]]:
    """Use the owner of the newest saved diagram, else the first user."""
    async with system_rls_session() as db:
        latest = await db.execute(
            select(Diagram.user_id, User.organization_id)
            .join(User, User.id == Diagram.user_id)
            .where(~Diagram.is_deleted)
            .order_by(Diagram.updated_at.desc())
            .limit(1)
        )
        row = latest.first()
        if row is not None:
            org = int(row[1]) if row[1] is not None else None
            return int(row[0]), org
        first = await db.execute(select(User.id, User.organization_id).order_by(User.id.asc()).limit(1))
        user = first.first()
        if user is None:
            raise RuntimeError("No user in Postgres to own the audit mind map")
        org = int(user[1]) if user[1] is not None else None
        return int(user[0]), org


async def persist_prefetch_mindmap(
    spec: dict[str, Any],
    *,
    user_id: int,
    title: str = PREFETCH_MAP_TITLE,
) -> str:
    """Insert the audit map so the classroom job has a real diagram_id."""
    diagram_id = generate_uuid()
    async with system_rls_session() as db:
        repo = DiagramRepository(db)
        await repo.create(
            Diagram(
                id=diagram_id,
                user_id=user_id,
                title=title,
                diagram_type="mindmap",
                language="zh",
                spec=spec,
            ),
            commit=True,
        )
    return diagram_id
