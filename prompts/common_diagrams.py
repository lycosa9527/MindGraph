"""
Common Diagrams Prompts

This module contains prompts for common diagrams like Venn diagrams, flowcharts, etc.
"""

# ============================================================================
# VENN DIAGRAM PROMPTS
# ============================================================================

VENN_DIAGRAM_GENERATION_EN = """
Please generate a JSON specification for a Venn diagram for the following user request.

Request: {user_prompt}

Please output a JSON object containing the following fields:
sets: [
  {{
    "name": "Set1",
    "elements": ["Element1", "Element2", "Element3"]
  }},
  {{
    "name": "Set2", 
    "elements": ["Element2", "Element3", "Element4"]
  }}
]

Please ensure the JSON format is correct, do not include any code block markers.
"""

VENN_DIAGRAM_GENERATION_ZH = """
请为以下用户需求生成一个维恩图的JSON规范。

需求：{user_prompt}

请输出一个包含以下字段的JSON对象：
sets: [
  {{
    "name": "集合1",
    "elements": ["元素1", "元素2", "元素3"]
  }},
  {{
    "name": "集合2",
    "elements": ["元素2", "元素3", "元素4"]
  }}
]

请确保JSON格式正确，不要包含任何代码块标记。
"""

# ============================================================================
# FLOWCHART PROMPTS
# ============================================================================

FLOWCHART_GENERATION_EN = """
Please generate a JSON specification for a flowchart for the following user request.

Request: {user_prompt}

Please output a JSON object containing the following fields:
title: "Process title"
steps: [
  {{
    "id": "step1",
    "type": "start",
    "text": "Start"
  }},
  {{
    "id": "step2", 
    "type": "process",
    "text": "Process step"
  }}
]

Please ensure the JSON format is correct, do not include any code block markers.
"""

FLOWCHART_GENERATION_ZH = """
请为以下用户需求生成一个流程图的JSON规范。

需求：{user_prompt}

请输出一个包含以下字段的JSON对象：
title: "流程标题"
steps: [
  {{
    "id": "step1",
    "type": "start", 
    "text": "开始"
  }},
  {{
    "id": "step2",
    "type": "process",
    "text": "处理步骤"
  }}
]

请确保JSON格式正确，不要包含任何代码块标记。
"""

# ============================================================================
# FISHBONE DIAGRAM PROMPTS
# ============================================================================

FISHBONE_DIAGRAM_GENERATION_EN = """
Please generate a JSON specification for a fishbone diagram for the following user request.

Request: {user_prompt}

Please output a JSON object containing the following fields:
problem: "Main problem"
categories: [
  {{
    "name": "Category1",
    "causes": ["Cause1", "Cause2", "Cause3"]
  }}
]

Please ensure the JSON format is correct, do not include any code block markers.
"""

FISHBONE_DIAGRAM_GENERATION_ZH = """
请为以下用户需求生成一个鱼骨图的JSON规范。

需求：{user_prompt}

请输出一个包含以下字段的JSON对象：
problem: "主要问题"
categories: [
  {{
    "name": "类别1",
    "causes": ["原因1", "原因2", "原因3"]
  }}
]

请确保JSON格式正确，不要包含任何代码块标记。
"""

# ============================================================================
# ORG CHART PROMPTS
# ============================================================================

ORG_CHART_GENERATION_EN = """
Please generate a JSON specification for an organizational chart for the following user request.

Request: {user_prompt}

Please output a JSON object containing the following fields:
title: "Organization name"
structure: {{
  "name": "CEO",
  "title": "Chief Executive Officer",
  "children": [
    {{
      "name": "Manager1",
      "title": "Department Manager",
      "children": []
    }}
  ]
}}

Please ensure the JSON format is correct, do not include any code block markers.
"""

ORG_CHART_GENERATION_ZH = """
请为以下用户需求生成一个组织架构图的JSON规范。

需求：{user_prompt}

请输出一个包含以下字段的JSON对象：
title: "组织名称"
structure: {{
  "name": "CEO",
  "title": "首席执行官",
  "children": [
    {{
      "name": "Manager1",
      "title": "部门经理",
      "children": []
    }}
  ]
}}

请确保JSON格式正确，不要包含任何代码块标记。
"""

# ============================================================================
# TIMELINE PROMPTS
# ============================================================================

TIMELINE_GENERATION_EN = """
Please generate a JSON specification for a timeline for the following user request.

Request: {user_prompt}

Please output a JSON object containing the following fields:
title: "Timeline title"
events: [
  {{
    "date": "2020-01-01",
    "title": "Event title",
    "description": "Event description"
  }}
]

Please ensure the JSON format is correct, do not include any code block markers.
"""

TIMELINE_GENERATION_ZH = """
请为以下用户需求生成一个时间线的JSON规范。

需求：{user_prompt}

请输出一个包含以下字段的JSON对象：
title: "时间线标题"
events: [
  {{
    "date": "2020-01-01",
    "title": "事件标题",
    "description": "事件描述"
  }}
]

请确保JSON格式正确，不要包含任何代码块标记。
"""

# ============================================================================
# PROMPT REGISTRY
# ============================================================================

COMMON_DIAGRAM_PROMPTS = {
    "venn_diagram_generation_en": VENN_DIAGRAM_GENERATION_EN,
    "venn_diagram_generation_zh": VENN_DIAGRAM_GENERATION_ZH,
    "flowchart_generation_en": FLOWCHART_GENERATION_EN,
    "flowchart_generation_zh": FLOWCHART_GENERATION_ZH,
    "fishbone_diagram_generation_en": FISHBONE_DIAGRAM_GENERATION_EN,
    "fishbone_diagram_generation_zh": FISHBONE_DIAGRAM_GENERATION_ZH,
    "org_chart_generation_en": ORG_CHART_GENERATION_EN,
    "org_chart_generation_zh": ORG_CHART_GENERATION_ZH,
    "timeline_generation_en": TIMELINE_GENERATION_EN,
    "timeline_generation_zh": TIMELINE_GENERATION_ZH,
} 