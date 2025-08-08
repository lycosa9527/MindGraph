# diagram_styles.py
"""
Smart Color Theme System for Diagrams
Based on Xmind's principles of color harmony, importance-based intensity, and automatic legibility.
"""

import colorsys
from typing import Dict, List, Optional, Tuple
import re

# ============================================================================
# SMART COLOR THEMES
# ============================================================================

# Predefined color themes with 6 variations each (like Xmind's 192 color schemes)
COLOR_THEMES = {
    "classic": {
        "colorful": {
            "primary": "#4e79a7",
            "secondary": "#f28e2b", 
            "tertiary": "#e15759",
            "quaternary": "#76b7b2",
            "quinary": "#59a14f",
            "senary": "#edc949"
        },
        "monochromatic": {
            "primary": "#2c3e50",
            "secondary": "#34495e",
            "tertiary": "#5d6d7e",
            "quaternary": "#85929e",
            "quinary": "#aeb6bf",
            "senary": "#d5dbdb"
        },
        "dark": {
            "primary": "#1a1a1a",
            "secondary": "#2c2c2c",
            "tertiary": "#404040",
            "quaternary": "#5a5a5a",
            "quinary": "#737373",
            "senary": "#8c8c8c"
        },
        "light": {
            "primary": "#ffffff",
            "secondary": "#f8f9fa",
            "tertiary": "#e9ecef",
            "quaternary": "#dee2e6",
            "quinary": "#ced4da",
            "senary": "#adb5bd"
        },
        "print": {
            "primary": "#000000",
            "secondary": "#333333",
            "tertiary": "#666666",
            "quaternary": "#999999",
            "quinary": "#cccccc",
            "senary": "#ffffff"
        },
        "display": {
            "primary": "#1e3a8a",
            "secondary": "#3b82f6",
            "tertiary": "#60a5fa",
            "quaternary": "#93c5fd",
            "quinary": "#bfdbfe",
            "senary": "#dbeafe"
        }
    },
    "innovation": {
        "colorful": {
            "primary": "#ff6b6b",
            "secondary": "#4ecdc4",
            "tertiary": "#45b7d1",
            "quaternary": "#96ceb4",
            "quinary": "#feca57",
            "senary": "#ff9ff3"
        },
        "monochromatic": {
            "primary": "#e74c3c",
            "secondary": "#c0392b",
            "tertiary": "#a93226",
            "quaternary": "#922b21",
            "quinary": "#7b241c",
            "senary": "#641e16"
        },
        "dark": {
            "primary": "#2c3e50",
            "secondary": "#34495e",
            "tertiary": "#5d6d7e",
            "quaternary": "#85929e",
            "quinary": "#aeb6bf",
            "senary": "#d5dbdb"
        },
        "light": {
            "primary": "#ecf0f1",
            "secondary": "#d5dbdb",
            "tertiary": "#bdc3c7",
            "quaternary": "#a4a4a4",
            "quinary": "#8c8c8c",
            "senary": "#737373"
        },
        "print": {
            "primary": "#000000",
            "secondary": "#1a1a1a",
            "tertiary": "#333333",
            "quaternary": "#4d4d4d",
            "quinary": "#666666",
            "senary": "#808080"
        },
        "display": {
            "primary": "#3498db",
            "secondary": "#5dade2",
            "tertiary": "#85c1e9",
            "quaternary": "#aed6f1",
            "quinary": "#d6eaf8",
            "senary": "#ebf3fd"
        }
    }
}

# ============================================================================
# IMPORTANCE-BASED COLOR INTENSITY
# ============================================================================

def get_importance_color(base_color: str, importance_level: str) -> str:
    """
    Apply importance-based color intensity (Center Topic -> Main Topic -> Sub Topic).
    Higher importance = higher intensity.
    """
    # Convert color name to hex if needed
    if not base_color.startswith('#'):
        base_color = COLOR_NAMES.get(base_color.lower(), "#000000")
    
    # Convert hex to RGB
    hex_color = base_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    # Convert to HSL for easier manipulation
    h, l, s = colorsys.rgb_to_hls(r/255, g/255, b/255)
    
    # Adjust based on importance level
    importance_multipliers = {
        "center": 1.0,      # Full intensity
        "main": 0.8,        # 80% intensity
        "sub": 0.6,         # 60% intensity
        "detail": 0.4       # 40% intensity
    }
    
    multiplier = importance_multipliers.get(importance_level, 0.8)
    new_l = l * multiplier
    new_s = s * multiplier
    
    # Convert back to RGB
    new_r, new_g, new_b = colorsys.hls_to_rgb(h, new_l, new_s)
    
    # Convert to hex
    return f"#{int(new_r*255):02x}{int(new_g*255):02x}{int(new_b*255):02x}"

# ============================================================================
# AUTOMATIC TEXT LEGIBILITY
# ============================================================================

def get_contrasting_text_color(background_color: str) -> str:
    """
    Automatically calculate text color for optimal legibility against background.
    Based on luminance calculation.
    """
    # Convert color name to hex if needed
    if not background_color.startswith('#'):
        background_color = COLOR_NAMES.get(background_color.lower(), "#000000")
    
    # Convert hex to RGB
    hex_color = background_color.lstrip('#')
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    # Calculate luminance
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    
    # Return black for light backgrounds, white for dark backgrounds
    return "#000000" if luminance > 0.5 else "#ffffff"

# ============================================================================
# DIAGRAM-SPECIFIC STYLE SCHEMAS
# ============================================================================

DEFAULT_STYLES = {
    "global": {
        "fontFamily": "Inter, Segoe UI, sans-serif",
        "background": "#ffffff",
        "strokeWidth": 2,
        "borderRadius": 4
    },
    
    # Thinking Maps
    "bubble_map": {
        "topicColor": "#1976d2",  # Deeper blue for topic nodes
        "topicTextColor": "#ffffff",  # White text for contrast
        "topicFontSize": 18,
        "topicFontWeight": "bold",
        "charColor": "#e3f2fd",  # Light blue for feature nodes
        "charTextColor": "#333333",
        "charFontSize": 14,
        "stroke": "#000000",  # Black border for topic nodes
        "strokeWidth": 3
    },
    
    "double_bubble_map": {
        "leftTopicColor": "#1976d2",  # Deeper blue for left topic
        "rightTopicColor": "#1976d2",  # Deeper blue for right topic
        "topicTextColor": "#ffffff",  # White text for contrast
        "topicFontSize": 18,
        "topicFontWeight": "bold",
        "similarityColor": "#e3f2fd",  # Light blue for similarities
        "similarityTextColor": "#333333",
        "similarityFontSize": 14,
        "leftDiffColor": "#e3f2fd",  # Light blue for left differences
        "rightDiffColor": "#e3f2fd",  # Light blue for right differences
        "diffTextColor": "#333333",
        "diffFontSize": 13,
        "stroke": "#000000",  # Black border for topic nodes
        "strokeWidth": 3
    },
    
    "tree_map": {
        "rootColor": "#4e79a7",
        "rootTextColor": "#ffffff",
        "rootFontSize": 18,
        "rootFontWeight": "bold",
        "branchColor": "#a7c7e7",
        "branchTextColor": "#2c3e50",
        "branchFontSize": 14,
        "leafColor": "#f4f6fb",
        "leafTextColor": "#2c3e50",
        "leafFontSize": 12,
        "stroke": "#2c3e50",
        "strokeWidth": 1
    },
    
    # Mind Maps
    "mindmap": {
        "centralTopicColor": "#4e79a7",
        "centralTopicTextColor": "#ffffff",
        "centralTopicFontSize": 20,
        "centralTopicFontWeight": "bold",
        "mainBranchColor": "#a7c7e7",
        "mainBranchTextColor": "#2c3e50",
        "mainBranchFontSize": 16,
        "subBranchColor": "#f4f6fb",
        "subBranchTextColor": "#2c3e50",
        "subBranchFontSize": 14,
        "stroke": "#2c3e50",
        "strokeWidth": 2
    },
    
    "radial_mindmap": {
        "centralTopicColor": "#4e79a7",
        "centralTopicTextColor": "#ffffff",
        "centralTopicFontSize": 22,
        "centralTopicFontWeight": "bold",
        "branchColors": ["#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#edc949", "#af7aa1", "#ff9da7", "#9c755f"],
        "branchTextColor": "#2c3e50",
        "branchFontSize": 16,
        "stroke": "#2c3e50",
        "strokeWidth": 2
    },
    
    # Concept Maps
    "concept_map": {
        "conceptColor": "#4e79a7",
        "conceptTextColor": "#ffffff",
        "conceptFontSize": 16,
        "conceptFontWeight": "bold",
        "relationshipColor": "#a7c7e7",
        "relationshipTextColor": "#2c3e50",
        "relationshipFontSize": 12,
        "stroke": "#2c3e50",
        "strokeWidth": 2
    },
    
    # Common Diagrams
    "venn_diagram": {
        "setColors": ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2"],
        "setTextColor": "#ffffff",
        "setFontSize": 16,
        "setFontWeight": "bold",
        "intersectionColor": "#a7c7e7",
        "intersectionTextColor": "#2c3e50",
        "intersectionFontSize": 14,
        "stroke": "#2c3e50",
        "strokeWidth": 2
    },
    
    "flowchart": {
        "startEndColor": "#4e79a7",
        "startEndTextColor": "#ffffff",
        "startEndFontSize": 14,
        "processColor": "#a7c7e7",
        "processTextColor": "#2c3e50",
        "processFontSize": 14,
        "decisionColor": "#f28e2b",
        "decisionTextColor": "#ffffff",
        "decisionFontSize": 14,
        "stroke": "#2c3e50",
        "strokeWidth": 2
    }
}

# ============================================================================
# PROMPT-TO-STYLE PARSER
# ============================================================================

# Color name mappings
COLOR_NAMES = {
    "red": "#ff0000", "blue": "#0000ff", "green": "#00ff00", "yellow": "#ffff00",
    "orange": "#ffa500", "purple": "#800080", "pink": "#ffc0cb", "brown": "#a52a2a",
    "black": "#000000", "white": "#ffffff", "gray": "#808080", "grey": "#808080",
    "cyan": "#00ffff", "magenta": "#ff00ff", "lime": "#00ff00", "navy": "#000080",
    "teal": "#008080", "olive": "#808000", "maroon": "#800000", "silver": "#c0c0c0",
    "gold": "#ffd700", "violet": "#ee82ee", "indigo": "#4b0082", "turquoise": "#40e0d0"
}

# Theme name mappings
THEME_NAMES = {
    "classic": "classic", "traditional": "classic", "professional": "classic",
    "innovation": "innovation", "modern": "innovation", "creative": "innovation",
    "colorful": "colorful", "vibrant": "colorful", "bright": "colorful",
    "monochromatic": "monochromatic", "mono": "monochromatic", "single": "monochromatic",
    "dark": "dark", "night": "dark", "black": "dark",
    "light": "light", "day": "light", "white": "light",
    "print": "print", "printer": "print", "grayscale": "print",
    "display": "display", "screen": "display", "digital": "display"
}

def parse_style_from_prompt(prompt: str) -> dict:
    """
    Parse style instructions from user prompt and return a style dictionary.
    Supports color themes, individual colors, font sizes, and importance levels.
    Now with input sanitization to prevent injection attacks.
    """
    # Input sanitization: remove dangerous patterns and control characters
    if not isinstance(prompt, str):
        return {}
    prompt = prompt.strip()
    dangerous_patterns = [
        r'<script[^>]*>.*?</script>',
        r'javascript:',
        r'data:',
        r'on\w+\s*=',
        r'<[^>]*>',
    ]
    for pattern in dangerous_patterns:
        prompt = re.sub(pattern, '', prompt, flags=re.IGNORECASE | re.DOTALL)
    prompt = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', prompt)
    prompt_lower = prompt.lower()
    style = {}
    
    # Parse color theme
    for theme_name, theme_key in THEME_NAMES.items():
        if theme_name in prompt_lower:
            style["colorTheme"] = theme_key
            break
    
    # Parse individual colors
    for color_name, hex_color in COLOR_NAMES.items():
        if color_name in prompt_lower:
            # Determine which element to color based on context
            if "topic" in prompt_lower or "central" in prompt_lower:
                style["topicColor"] = hex_color
            elif "background" in prompt_lower:
                style["background"] = hex_color
            elif "text" in prompt_lower:
                style["textColor"] = hex_color
            else:
                style["primaryColor"] = hex_color
    
    # Parse font sizes
    font_size_match = re.search(r'font\s+size\s+(\d+)', prompt_lower)
    if font_size_match:
        size = int(font_size_match.group(1))
        style["fontSize"] = size
    
    # Parse importance levels
    if "important" in prompt_lower or "emphasis" in prompt_lower:
        style["importance"] = "center"
    elif "main" in prompt_lower:
        style["importance"] = "main"
    elif "sub" in prompt_lower or "secondary" in prompt_lower:
        style["importance"] = "sub"
    
    # Parse background preferences
    if "dark background" in prompt_lower or "dark theme" in prompt_lower:
        style["backgroundTheme"] = "dark"
    elif "light background" in prompt_lower or "light theme" in prompt_lower:
        style["backgroundTheme"] = "light"
    
    # Parse stroke/border preferences
    if "bold stroke" in prompt_lower or "thick border" in prompt_lower:
        style["strokeWidth"] = 4
    elif "thin stroke" in prompt_lower or "thin border" in prompt_lower:
        style["strokeWidth"] = 1
    
    return style

# ============================================================================
# STYLE MERGING AND APPLICATION
# ============================================================================

def get_style(diagram_type: str, user_style: Optional[dict] = None, 
              color_theme: Optional[str] = None, variation: str = "colorful") -> dict:
    """
    Get merged style for a diagram, combining defaults with user overrides.
    
    Args:
        diagram_type: Type of diagram (e.g., "bubble_map", "mindmap")
        user_style: User-provided style overrides
        color_theme: Color theme name (e.g., "classic", "innovation")
        variation: Theme variation (e.g., "colorful", "dark", "light")
    
    Returns:
        Merged style dictionary
    """
    # Start with global defaults
    style = DEFAULT_STYLES.get("global", {}).copy()
    
    # Add diagram-specific defaults
    diagram_style = DEFAULT_STYLES.get(diagram_type, {})
    style.update(diagram_style)
    
    # Apply color theme if specified
    if color_theme and color_theme in COLOR_THEMES:
        theme_colors = COLOR_THEMES[color_theme].get(variation, COLOR_THEMES[color_theme]["colorful"])
        
        # Map theme colors to diagram elements
        if diagram_type == "bubble_map":
            style["topicColor"] = theme_colors["primary"]
            style["charColor"] = theme_colors["secondary"]
        elif diagram_type == "mindmap":
            style["centralTopicColor"] = theme_colors["primary"]
            style["mainBranchColor"] = theme_colors["secondary"]
            style["subBranchColor"] = theme_colors["tertiary"]
        # Add more mappings as needed
    
    # Apply user overrides
    if user_style:
        # Convert color names to hex in user_style
        processed_user_style = {}
        for key, value in user_style.items():
            if isinstance(value, str) and "Color" in key and not value.startswith('#'):
                # Convert color name to hex
                processed_user_style[key] = COLOR_NAMES.get(value.lower(), value)
            else:
                processed_user_style[key] = value
        style.update(processed_user_style)
    
    # Apply importance-based intensity if specified
    if "importance" in style:
        importance_level = style["importance"]
        if "topicColor" in style:
            style["topicColor"] = get_importance_color(style["topicColor"], importance_level)
        if "centralTopicColor" in style:
            style["centralTopicColor"] = get_importance_color(style["centralTopicColor"], importance_level)
    
    # Ensure text colors are legible
    text_colors_to_add = {}
    for key, value in style.items():
        if "Color" in key and "Text" not in key and "Stroke" not in key and isinstance(value, str):
            text_key = key.replace("Color", "TextColor")
            if text_key not in style:
                text_colors_to_add[text_key] = get_contrasting_text_color(value)
    
    # Add the text colors after iteration
    style.update(text_colors_to_add)
    
    return style

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_available_themes() -> List[str]:
    """Get list of available color themes."""
    return list(COLOR_THEMES.keys())

def get_theme_variations(theme_name: str) -> List[str]:
    """Get available variations for a specific theme."""
    if theme_name in COLOR_THEMES:
        return list(COLOR_THEMES[theme_name].keys())
    return []

def validate_style(style: dict) -> Tuple[bool, str]:
    """Validate a style dictionary."""
    # Add validation logic here
    return True, ""

# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    # Example: Parse style from user prompt
    prompt = "Create a bubble map with a blue background, red topic nodes, font size 20, and use the classic dark theme"
    user_style = parse_style_from_prompt(prompt)
    print("Parsed style:", user_style)
    
    # Example: Get merged style
    final_style = get_style("bubble_map", user_style, "classic", "dark")
    print("Final style:", final_style) 