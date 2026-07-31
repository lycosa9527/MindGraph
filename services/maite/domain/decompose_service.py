"""
Maite decompose template domain service.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from repositories.maite.sessions_repo import MaiteSessionsRepository
from services.maite.domain.errors import MaiteNotFoundError


class DecomposeService:
    """Provide static decompose table templates for inquiry sessions."""

    def __init__(self, session: AsyncSession) -> None:
        self._sessions = MaiteSessionsRepository(session)

    async def get_template(self, session_id: int, *, user_id: int) -> dict[str, Any]:
        """Return decompose table templates for an owned inquiry session."""
        row = await self._sessions.get_owned(session_id, user_id)
        if row is None:
            raise MaiteNotFoundError("Session not found")
        return {
            "session_id": session_id,
            "tables": [
                {
                    "table_key": "condition_table",
                    "title": "条件-考点-制约关系表",
                    "purpose": "梳理题目条件、对应考点与制约关系。",
                    "columns": [
                        {
                            "key": "condition_text",
                            "label": "条件内容",
                            "guidance": "写出已知或隐含条件。",
                            "input_type": "textarea",
                        },
                        {
                            "key": "related_knowledge",
                            "label": "对应考点",
                            "guidance": "写出可能调用的知识点。",
                            "input_type": "textarea",
                        },
                        {
                            "key": "constraint_relation",
                            "label": "制约关系",
                            "guidance": "条件如何限制解题方向。",
                            "input_type": "textarea",
                        },
                        {
                            "key": "uncertainty_marked",
                            "label": "我不确定",
                            "guidance": "不确定时勾选。",
                            "input_type": "checkbox",
                        },
                    ],
                    "guidance": "如实填写当前能想到的内容即可。",
                    "example": {
                        "condition_text": "函数在区间内连续",
                        "related_knowledge": "零点存在性定理",
                        "constraint_relation": "决定能否用端点符号判断零点",
                        "uncertainty_marked": "不确定时勾选",
                    },
                    "core_field": "condition_text",
                },
                {
                    "table_key": "step_table",
                    "title": "步骤-输出-验证三元组",
                    "purpose": "把解题过程拆成可验证的步骤。",
                    "columns": [
                        {
                            "key": "step_no",
                            "label": "步骤编号",
                            "guidance": "系统自动编号。",
                            "input_type": "auto_number",
                        },
                        {
                            "key": "task",
                            "label": "这一步要做什么",
                            "guidance": "写出小任务。",
                            "input_type": "textarea",
                        },
                        {
                            "key": "expected_output",
                            "label": "预计输出",
                            "guidance": "中间结果或结论。",
                            "input_type": "textarea",
                        },
                        {
                            "key": "verification_method",
                            "label": "如何验证",
                            "guidance": "如何确认这一步正确。",
                            "input_type": "textarea",
                        },
                    ],
                    "guidance": "步骤尽量可执行、可验证。",
                    "example": {
                        "step_no": "1",
                        "task": "整理已知条件",
                        "expected_output": "条件清单",
                        "verification_method": "与题目逐条对照",
                    },
                    "core_field": "task",
                },
                {
                    "table_key": "model_table",
                    "title": "信息-对象-模型-目标表",
                    "purpose": "从原始信息抽象到数学模型。",
                    "columns": [
                        {
                            "key": "raw_info",
                            "label": "原始信息",
                            "guidance": "题目给出的信息片段。",
                            "input_type": "textarea",
                        },
                        {
                            "key": "abstract_object",
                            "label": "抽象对象",
                            "guidance": "变量/集合/图形等。",
                            "input_type": "textarea",
                        },
                        {
                            "key": "math_model",
                            "label": "数学模型",
                            "guidance": "方程/不等式/函数等。",
                            "input_type": "textarea",
                        },
                        {
                            "key": "solving_goal",
                            "label": "求解目标",
                            "guidance": "最终要求什么。",
                            "input_type": "textarea",
                        },
                        {
                            "key": "transfer_risk",
                            "label": "迁移风险",
                            "guidance": "变式时容易出错之处。",
                            "input_type": "textarea",
                        },
                    ],
                    "guidance": "连接题目语言与数学语言。",
                    "example": {
                        "raw_info": "二次函数在区间上的最值",
                        "abstract_object": "函数 f(x)",
                        "math_model": "配方或求导",
                        "solving_goal": "最大最小值",
                        "transfer_risk": "端点与顶点位置",
                    },
                    "core_field": "math_model",
                },
            ],
        }
