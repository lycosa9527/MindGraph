"""
Shared helpers for inline recommendation prompts.

Aligned with node_palette and concept_map prompt structure:
- Educational context (context_desc)
- Thinking approach (思维方式)
- Dimension type references (brace, tree, bridge)
- MECE where applicable

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Any, Dict, List, Optional


def get_context_desc(educational_context: Optional[Dict[str, Any]]) -> str:
    """Derive context_desc from educational_context for prompt enrichment."""
    if not educational_context:
        return "General K12 teaching"
    raw = educational_context.get('raw_message', '')
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return "General K12 teaching"


# ---------------------------------------------------------------------------
# Dimension types (from prompts/node_palette.py)
# ---------------------------------------------------------------------------

BRACE_DIMENSION_TYPES_ZH = """常见拆解维度类型（参考）：
- 物理部件（按实体组成）
- 功能模块（按功能划分）
- 时间阶段（按时间顺序）
- 空间区域（按空间位置）
- 类型分类（按种类划分）
- 属性特征（按特性划分）
- 层次结构（按层级划分）"""

BRACE_DIMENSION_TYPES_EN = """Common dimension types (reference):
- Physical Components (by physical parts)
- Functional Modules (by function)
- Time Stages (by temporal sequence)
- Spatial Regions (by location)
- Type Classification (by category)
- Attribute Features (by characteristics)
- Hierarchical Structure (by levels)"""

TREE_DIMENSION_TYPES_ZH = """常见分类维度类型（参考）：
- 物理部件、功能模块、时间阶段、空间区域
- 类型分类、属性特征、层次结构"""

TREE_DIMENSION_TYPES_EN = """Common classification dimension types (reference):
- Physical parts, Functional modules, Time stages, Spatial regions
- Type classification, Attribute features, Hierarchical structure"""

BRIDGE_DIMENSION_TYPES_ZH = """类比维度示例：关系、功能、结构、过程、属性等"""

BRIDGE_DIMENSION_TYPES_EN = """Analogy dimension examples: relationship, function, structure, process, attribute"""


# ---------------------------------------------------------------------------
# Thinking approach (思维方式)
# ---------------------------------------------------------------------------

THINKING_APPROACH: Dict[str, Dict[str, str]] = {
    'mindmap': {'zh': '联想、发散', 'en': 'Association, Divergence'},
    'flow_map': {'zh': '顺序、流程', 'en': 'Sequence, Process'},
    'tree_map': {'zh': '分类、归纳', 'en': 'Classification, Induction'},
    'brace_map': {'zh': '拆解、分解', 'en': 'Decomposition, Breakdown'},
    'circle_map': {'zh': '定义、描述', 'en': 'Definition, Description'},
    'bubble_map': {'zh': '描述、属性', 'en': 'Description, Attributes'},
    'double_bubble_map': {'zh': '比较、对比', 'en': 'Comparison, Contrast'},
    'multi_flow_map': {'zh': '因果、推理', 'en': 'Cause-effect, Reasoning'},
    'bridge_map': {'zh': '类比、对应', 'en': 'Analogy, Correspondence'},
}


def append_batch_note(
    prompt: str,
    language: str,
    batch_num: int,
    existing: Optional[List[str]] = None,
) -> str:
    """Append batch/diversity note for batch_num > 1."""
    if batch_num <= 1:
        return prompt
    if existing:
        if language == 'zh':
            prompt += f"\n\n已生成：{', '.join(existing[:20])}\n请生成不同的推荐。"
        else:
            prompt += (
                f"\n\nAlready generated: {', '.join(existing[:20])}\n"
                "Generate different recommendations."
            )
    else:
        if language == 'zh':
            prompt += f"\n\n第{batch_num}批。确保多样性。"
        else:
            prompt += f"\n\nBatch {batch_num}. Ensure diversity."
    return prompt
