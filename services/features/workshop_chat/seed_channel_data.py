"""
Seed Channel Data
===================

Minimal workshop fixture: one global announce channel and one teaching
group with a single lesson-study. Extra canned groups from older seeds
are archived on initialize (see ``RETIRED_SEED_*``).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Any, Dict, FrozenSet, List

KEEPER_GROUP_NAME = "语文教研组"
KEEPER_LESSON_NAME = "《背影》（朱自清）"

RETIRED_SEED_GROUP_NAMES: FrozenSet[str] = frozenset(
    {
        "STEM教研组",
        "数理化教研组",
    }
)

RETIRED_SEED_LESSON_NAMES: FrozenSet[str] = frozenset(
    {
        "《孔乙己》（鲁迅）",
        "《荷塘月色》（朱自清）",
        "《两个铁球同时着地》",
        "《蝙蝠和雷达》",
        "《赵州桥》",
        "《杠杆的科学》",
        "《水的组成》",
        "《勾股定理》",
    }
)

ANNOUNCE_CHANNEL: Dict[str, Any] = {
    "name": "系统公告",
    "description": "平台更新公告",
    "avatar": "📢",
    "channel_type": "announce",
    "topics": [
        {
            "title": "更新公告",
            "description": "平台功能更新与通知，仅管理员可发布。",
            "messages": [
                "欢迎使用研习社。此频道用于平台公告，仅管理员可发言。",
            ],
        },
    ],
}

_CHINESE_LIT_GROUP: Dict[str, Any] = {
    "name": KEEPER_GROUP_NAME,
    "description": "语文学科教学研究与集体备课",
    "avatar": "📚",
    "children": [
        {
            "name": KEEPER_LESSON_NAME,
            "description": "以质朴的语言和细腻的笔触描写父爱。",
            "color": "#6366f1",
            "status": "open",
            "topics": [
                {
                    "title": "集体备课讨论",
                    "messages": [
                        "本周集体备课讨论《背影》。请从细节描写切入，分享教学设计。",
                    ],
                },
            ],
        },
    ],
}

DEFAULT_CHANNEL_GROUPS: List[Dict[str, Any]] = [
    _CHINESE_LIT_GROUP,
]
