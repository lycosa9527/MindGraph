#!/usr/bin/env python3
"""
Seed demo Case Square posts for local UI development.

Re-run safe: removes prior rows tagged with ``demo_seed_v1`` then inserts fresh samples.

Usage (from repo root, with DATABASE_URL configured):

    python scripts/seed_case_square_demo.py
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import delete, select
from sqlalchemy.orm import joinedload

from models.domain.auth import User
from models.domain.case_square import CaseSquarePost, CaseSquarePostFavorite, CaseSquarePostLike
from routers.features.case_square_helpers import delete_spec_json, delete_thumbnail, save_spec_json
from utils.db.rls_context import RlsContext, rls_sync_session

DEMO_TAG = "demo_seed_v1"

MINIMAL_MIND_MAP_SPEC: dict[str, Any] = {
    "diagram_type": "mind_map",
    "topic": "示例主题",
    "children": [
        {"text": "核心概念", "children": [{"text": "要点一"}, {"text": "要点二"}]},
        {"text": "应用拓展", "children": [{"text": "课堂活动"}, {"text": "评价方式"}]},
    ],
}

MINIMAL_TREE_MAP_SPEC: dict[str, Any] = {
    "diagram_type": "tree_map",
    "topic": "分类主题",
    "children": [
        {"text": "类别 A", "children": [{"text": "子项 1"}, {"text": "子项 2"}]},
        {"text": "类别 B", "children": [{"text": "子项 3"}]},
    ],
}


def _samples(now: datetime) -> list[dict[str, Any]]:
    """Nine gallery cases + one pending + one rejected (author's drafts)."""
    base = now - timedelta(days=30)
    return [
        {
            "title": "《两小儿辩日》教学设计",
            "description": "围绕《两小儿辩日》设计思辨性问题链，引导学生比较两小儿的推理路径，理解科学探究与日常经验的差异。",
            "tags": ["文言文", "思维教学", "问题链", DEMO_TAG],
            "case_type": "teaching_design",
            "subject": "语文",
            "grade": "七年级",
            "diagram_type": None,
            "spec": None,
            "status": "approved",
            "is_expert_recommended": True,
            "likes_count": 147,
            "views_count": 528,
            "created_at": base + timedelta(days=1),
        },
        {
            "title": "分数的意义 — 思维导图课例",
            "description": "用思维导图梳理“分数的意义”核心概念，帮助学生建立部分与整体、等分与大小的多重表征。",
            "tags": ["分数", "概念建构", DEMO_TAG],
            "case_type": "diagram_case",
            "subject": "数学",
            "grade": "五年级",
            "diagram_type": "mind_map",
            "spec": {**MINIMAL_MIND_MAP_SPEC, "topic": "分数的意义"},
            "status": "approved",
            "is_expert_recommended": False,
            "likes_count": 89,
            "views_count": 312,
            "created_at": base + timedelta(days=3),
        },
        {
            "title": "光合作用 — 概念图模板",
            "description": "适用于初中生物“光合作用”单元的概念图模板，可直接导入后按班级学情微调节点。",
            "tags": ["生物", "概念图", "模板", DEMO_TAG],
            "case_type": "diagram_template",
            "subject": "生物",
            "grade": "八年级",
            "diagram_type": "concept_map",
            "spec": {
                "diagram_type": "concept_map",
                "topic": "光合作用",
                "children": [{"text": "原料"}, {"text": "条件"}, {"text": "产物"}],
            },
            "status": "approved",
            "is_expert_recommended": True,
            "likes_count": 203,
            "views_count": 641,
            "created_at": base + timedelta(days=5),
        },
        {
            "title": "《春》散文阅读 — 气泡图分析",
            "description": "以气泡图呈现《春》的意象群与情感基调，支持小组合作完成文本细读。",
            "tags": ["散文", "意象", DEMO_TAG],
            "case_type": "diagram_case",
            "subject": "语文",
            "grade": "八年级",
            "diagram_type": "bubble_map",
            "spec": {
                "diagram_type": "bubble_map",
                "topic": "《春》",
                "children": [{"text": "意象"}, {"text": "情感"}, {"text": "结构"}],
            },
            "status": "approved",
            "is_expert_recommended": False,
            "likes_count": 56,
            "views_count": 198,
            "created_at": base + timedelta(days=7),
        },
        {
            "title": "牛顿第一定律 — 流程图探究",
            "description": "通过流程图梳理理想实验与推理过程，衔接生活现象与定律表述。",
            "tags": ["物理", "探究学习", DEMO_TAG],
            "case_type": "diagram_case",
            "subject": "物理",
            "grade": "九年级",
            "diagram_type": "flow_map",
            "spec": {
                "diagram_type": "flow_map",
                "topic": "牛顿第一定律",
                "children": [{"text": "观察"}, {"text": "推理"}, {"text": "结论"}],
            },
            "status": "approved",
            "is_expert_recommended": True,
            "likes_count": 112,
            "views_count": 405,
            "created_at": base + timedelta(days=9),
        },
        {
            "title": "世界地理 — 树形图区域认知",
            "description": "用大洲—国家—气候带树形图帮助学生建立空间认知框架。",
            "tags": ["地理", "区域认知", DEMO_TAG],
            "case_type": "diagram_template",
            "subject": "地理",
            "grade": "七年级",
            "diagram_type": "tree_map",
            "spec": {**MINIMAL_TREE_MAP_SPEC, "topic": "世界地理分区"},
            "status": "approved",
            "is_expert_recommended": False,
            "likes_count": 73,
            "views_count": 256,
            "created_at": base + timedelta(days=11),
        },
        {
            "title": "化学方程式配平 — 括号图课例",
            "description": "括号图分解配平步骤：观察反应物与生成物、试配系数、检验原子守恒。",
            "tags": ["化学", "方程式", DEMO_TAG],
            "case_type": "diagram_case",
            "subject": "化学",
            "grade": "九年级",
            "diagram_type": "brace_map",
            "spec": {
                "diagram_type": "brace_map",
                "topic": "方程式配平",
                "children": [{"text": "步骤一"}, {"text": "步骤二"}, {"text": "步骤三"}],
            },
            "status": "approved",
            "is_expert_recommended": False,
            "likes_count": 44,
            "views_count": 167,
            "created_at": base + timedelta(days=13),
        },
        {
            "title": "信息科技 — 算法思维导图",
            "description": "以思维导图呈现“输入—处理—输出”算法结构，配套 Scratch 小项目。",
            "tags": ["信息技术", "算法", DEMO_TAG],
            "case_type": "diagram_template",
            "subject": "信息技术",
            "grade": "六年级",
            "diagram_type": "mind_map",
            "spec": {**MINIMAL_MIND_MAP_SPEC, "topic": "算法初步"},
            "status": "approved",
            "is_expert_recommended": False,
            "likes_count": 38,
            "views_count": 142,
            "created_at": base + timedelta(days=15),
        },
        {
            "title": "跨学科项目：校园节水方案",
            "description": "综合科学、数学与道法，设计校园节水调查与改进方案，含图示与反思。",
            "tags": ["跨学科", "项目化", DEMO_TAG],
            "case_type": "teaching_design",
            "subject": "跨学科",
            "grade": "八年级",
            "diagram_type": None,
            "spec": None,
            "status": "approved",
            "is_expert_recommended": True,
            "likes_count": 95,
            "views_count": 389,
            "created_at": base + timedelta(days=17),
        },
        {
            "title": "【待审核示例】圆圈图入门课",
            "description": "演示待审核状态卡片，提交后可在此查看审核进度。",
            "tags": ["待审核", DEMO_TAG],
            "case_type": "diagram_case",
            "subject": "数学",
            "grade": "三年级",
            "diagram_type": "circle_map",
            "spec": {"diagram_type": "circle_map", "topic": "认识图形", "children": []},
            "status": "pending",
            "is_expert_recommended": False,
            "likes_count": 0,
            "views_count": 12,
            "created_at": base + timedelta(days=20),
        },
        {
            "title": "【驳回示例】不完整教学设计",
            "description": "演示驳回状态与原因展示，便于调整「我发布的」列表样式。",
            "tags": ["驳回示例", DEMO_TAG],
            "case_type": "teaching_design",
            "subject": "英语",
            "grade": "七年级",
            "diagram_type": None,
            "spec": None,
            "status": "rejected",
            "is_expert_recommended": False,
            "likes_count": 0,
            "views_count": 8,
            "rejection_reason": "请补充教学目标与评价量规后再提交。",
            "created_at": base + timedelta(days=22),
        },
    ]


def _find_author(db) -> User:
    user = db.execute(
        select(User).options(joinedload(User.organization)).where(User.phone == "13800000001")
    ).scalar_one_or_none()
    if user is not None:
        return user
    user = db.execute(select(User).where(User.role == "superadmin").limit(1)).scalar_one_or_none()
    if user is not None:
        return user
    user = db.execute(select(User).limit(1)).scalar_one_or_none()
    if user is None:
        raise SystemExit("No users in database — create a test account first.")
    return user


def _purge_demo_posts(db) -> int:
    rows = db.execute(select(CaseSquarePost)).scalars().all()
    demo_ids = [post.id for post in rows if DEMO_TAG in (post.tags or [])]
    if not demo_ids:
        return 0
    db.execute(delete(CaseSquarePostLike).where(CaseSquarePostLike.post_id.in_(demo_ids)))
    db.execute(delete(CaseSquarePostFavorite).where(CaseSquarePostFavorite.post_id.in_(demo_ids)))
    for post_id in demo_ids:
        delete_spec_json(post_id)
        delete_thumbnail(post_id)
    db.execute(delete(CaseSquarePost).where(CaseSquarePost.id.in_(demo_ids)))
    return len(demo_ids)


def seed() -> None:
    now = datetime.now(UTC)
    with rls_sync_session(RlsContext.system_bootstrap()) as db:
        author = _find_author(db)

    with rls_sync_session(RlsContext.panel_superadmin(author)) as db:
        removed = _purge_demo_posts(db)
        db.flush()

        inserted = 0
        for item in _samples(now):
            post = CaseSquarePost(
                title=item["title"],
                description=item["description"],
                tags=item["tags"],
                case_type=item["case_type"],
                subject=item["subject"],
                grade=item["grade"],
                diagram_type=item["diagram_type"],
                spec=item["spec"],
                thumbnail_path=None,
                author_id=author.id,
                submitted_by_id=author.id,
                publish_source="self",
                status=item["status"],
                is_expert_recommended=item["is_expert_recommended"],
                likes_count=item["likes_count"],
                views_count=item["views_count"],
                created_at=item["created_at"],
                updated_at=item["created_at"],
                rejection_reason=item.get("rejection_reason"),
            )
            if item["status"] == "approved":
                post.reviewed_by = author.id
                post.reviewed_at = item["created_at"] + timedelta(hours=2)
            if item["is_expert_recommended"]:
                post.expert_recommended_by = author.id
                post.expert_recommended_at = item["created_at"] + timedelta(hours=4)

            db.add(post)
            db.flush()

            if item["spec"]:
                save_spec_json(post.id, item["spec"])
            inserted += 1

        db.commit()
        print(f"Case Square demo seed: removed {removed}, inserted {inserted} (author id={author.id})")


if __name__ == "__main__":
    seed()
