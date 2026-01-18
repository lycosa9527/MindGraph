"""
Fallback characteristics data for double bubble maps.

This module contains hardcoded fallback characteristics for specific topics
when the LLM fails to generate characteristics.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, List, Optional


def get_fallback_characteristics(topic1: str, topic2: str) -> Optional[Dict[str, List[str]]]:
    """
    Get fallback characteristics for given topics.

    Args:
        topic1: First topic
        topic2: Second topic

    Returns:
        Dictionary with similarities, left_differences, right_differences,
        or None if no fallback matches
    """
    topic1_lower = topic1.lower()
    topic2_lower = topic2.lower()

    # Check for specific topic patterns
    if "photosynthesis" in topic1_lower or "cellular respiration" in topic2_lower:
        return {
            "similarities": [
                "Biological processes", "Energy involved", "Plant cells",
                "Life essential", "Chemical reactions"
            ],
            "left_differences": [
                "Food production", "Sunlight needed", "Green parts",
                "Oxygen creation", "Leaf location"
            ],
            "right_differences": [
                "Food consumption", "Dark operation", "All cells",
                "Oxygen need", "Everywhere location"
            ]
        }

    if ("d3" in topic1_lower or "bubble" in topic2_lower or
            "d3" in topic2_lower or "bubble" in topic1_lower):
        return {
            "similarities": [
                "Visual diagrams", "Text commands", "Chart creation",
                "Computer tools", "Explanation aids"
            ],
            "left_differences": [
                "Multiple types", "Wide usage", "Rich features",
                "Professional", "Flexible"
            ],
            "right_differences": [
                "Comparison focus", "Simple use", "Learning tool",
                "Clear structure", "Easy understanding"
            ]
        }

    car_brands = [
        '宝马', '奔驰', 'bmw', 'mercedes', 'audi',
        'volkswagen', 'toyota', 'honda', 'ford', 'chevrolet'
    ]
    if any(brand in topic1_lower or brand in topic2_lower for brand in car_brands):
        return {
            "similarities": [
                "Car manufacturers", "Famous brands", "Global sales",
                "Quality focus", "Large customer base"
            ],
            "left_differences": [
                "Unique designs", "Specific markets", "Different styles",
                "Special features", "Price range"
            ],
            "right_differences": [
                "Company history", "Model variety", "Different strengths",
                "Brand reputation", "Market segments"
            ]
        }

    animals = ['cat', 'dog', 'bird', 'fish', '猫', '狗', '鸟', '鱼']
    if any(animal in topic1_lower or animal in topic2_lower for animal in animals):
        return {
            "similarities": [
                "Animals", "Food water", "Home living",
                "Popular pets", "Unique behaviors"
            ],
            "left_differences": [
                "Food preferences", "Body shapes", "Movement styles",
                "Care needs", "Lifespans"
            ],
            "right_differences": [
                "Sound types", "Social needs", "Living spaces",
                "Abilities", "Personalities"
            ]
        }

    fruits = ['apple', 'orange', '苹果', '橙子']
    if any(fruit in topic1_lower or fruit in topic2_lower for fruit in fruits):
        return {
            "similarities": [
                "Fruits", "Healthy", "Tree growth",
                "Global consumption", "Vitamins"
            ],
            "left_differences": [
                "Taste profiles", "Growth requirements", "Appearances",
                "Nutrients", "Cooking uses"
            ],
            "right_differences": [
                "Seasons", "Storage needs", "Health benefits",
                "Cultural importance", "Eating methods"
            ]
        }

    tech_devices = ['computer', 'phone', 'laptop', 'tablet', '电脑', '手机']
    if any(tech in topic1_lower or tech in topic2_lower for tech in tech_devices):
        return {
            "similarities": [
                "Electronic devices", "Electricity use", "Communication tools",
                "Screens", "Charging needed"
            ],
            "left_differences": [
                "Sizes", "Uses", "Features", "Usage methods", "Prices"
            ],
            "right_differences": [
                "Portability", "Power needs", "User groups",
                "Capabilities", "Costs"
            ]
        }

    return None


def get_default_fallback() -> Dict[str, List[str]]:
    """
    Get default fallback characteristics when no specific match is found.

    Returns:
        Dictionary with generic fallback characteristics
    """
    return {
        "similarities": [
            "Comparable", "Features", "Useful", "Differences", "Interesting"
        ],
        "left_differences": [
            "Special features", "Different", "Advantages"
        ],
        "right_differences": [
            "Special features", "Different", "Advantages"
        ]
    }
