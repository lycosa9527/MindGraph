"""
Tab Mode Color Suggestion Prompts
==================================

High-contrast color suggestions for color picker inputs.

@author MindGraph Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

TAB_MODE_COLOR_SUGGESTION_EN = """Suggest 3-5 high-contrast colors for a {diagram_type} diagram.
Current colors: fill={fill_color}, stroke={stroke_color}, text={text_color}
User typed: {partial_input}

Return only hex color codes as JSON array.
Example: ["#FF5722", "#FF9800", "#4CAF50"]"""

TAB_MODE_COLOR_SUGGESTION_ZH = """为{diagram_type}图表建议3-5个高对比度颜色。
当前颜色：填充={fill_color}，边框={stroke_color}，文字={text_color}
用户输入：{partial_input}

只返回十六进制颜色代码的JSON数组。
示例：["#FF5722", "#FF9800", "#4CAF50"]"""

# Registry
TAB_MODE_COLOR_PROMPTS = {
    "tab_mode_color_suggestion_en": TAB_MODE_COLOR_SUGGESTION_EN,
    "tab_mode_color_suggestion_zh": TAB_MODE_COLOR_SUGGESTION_ZH,
}

