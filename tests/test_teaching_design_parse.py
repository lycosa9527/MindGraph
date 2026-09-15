"""Heading parse for 教学设计 markdown → Word spec."""

from __future__ import annotations

from services.mindmate.teaching_design_parse import parse_teaching_design_markdown


_FIXTURE = """
## 基本信息
《呼吸作用》教学设计
学段年级：初中七年级
学科：生物
教材版本：人教版
课时说明：第1课时

## 教学内容分析
本节围绕细胞呼吸展开。

## 学习者分析
学生已学过光合作用。

## 学习目标及重难点
1. 说出呼吸作用的概念（重点）
2. 比较有氧呼吸与无氧呼吸（难点）

## 学习活动设计
环节一：创设情境
教师活动：出示种子萌发视频。
学生活动：观察并提问。
环节设计意图：用生活现象引出课题。

环节二：探究本质
教师活动1：组织对比实验。
学生活动1：记录数据。
教师活动2：引导归纳。
学生活动2：汇报结论。
环节设计意图：用认知冲突推动概念建构。

## 思维训练点
认知冲突：萌发种子放热与“植物只进行光合作用”的矛盾
设计意图：暴露迷思概念
思维图示：用复流程图梳理物质变化
变式运用：改变温度条件的过程性变式

## 总结
本课用实验冲突驱动概念重建。
<!-- mg-reply-kind:teaching_instruction -->
[mg-reply-kind:teaching_instruction]
"""


def test_parse_named_headings_and_activity_rows() -> None:
    """Dify-style headings land in the matching spec fields."""
    spec = parse_teaching_design_markdown(_FIXTURE)
    assert "呼吸作用" in spec.title
    assert spec.grade == "初中七年级"
    assert spec.subject == "生物"
    assert spec.textbook == "人教版"
    assert spec.period == "第1课时"
    assert "细胞呼吸" in spec.content_analysis
    assert "光合作用" in spec.learner_analysis
    assert "有氧呼吸" in spec.objectives
    assert "实验冲突" in spec.summary
    assert spec.needs_llm_fill() is False
    assert len(spec.activities) == 2
    assert spec.activities[0].title == "创设情境"
    assert spec.activities[0].teacher_actions
    assert spec.activities[1].student_actions
    categories = {row.category for row in spec.thinking_points}
    assert "认知冲突" in categories
    assert "思维可视化" in categories
    assert "变式运用" in categories


def test_unstructured_markdown_needs_llm() -> None:
    """No headings → leftover body and LLM fill required."""
    spec = parse_teaching_design_markdown("随便一段没有标题的回复")
    assert spec.leftover.startswith("随便一段")
    assert spec.needs_llm_fill() is True
