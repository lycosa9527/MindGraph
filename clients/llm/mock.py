"""
Mock LLM Client for Testing (DEPRECATED)

DEPRECATED: This file serves no purpose in production environments where LLM is always configured.
It is only kept as a fallback safety mechanism for edge cases where LLM initialization fails.

Provides a mock LLM client that returns structured responses for testing purposes.
This should not be used in production - real LLM clients should always be configured.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, List, Any


class MockLLMClient:
    """Mock LLM client that returns structured responses for testing."""

    def chat_completion(self, messages: List[Dict], temperature: float = 0.7, max_tokens: int = 1000) -> Dict[str, Any]:
        """
        Mock LLM client that returns structured responses for testing.

        Args:
            messages: List of message dictionaries
            temperature: Temperature (ignored in mock, kept for API consistency)
            max_tokens: Max tokens (ignored in mock, kept for API consistency)

        Returns:
            Dict with mock response based on prompt content
        """
        # Parameters kept for API consistency but not used in mock
        _ = temperature
        _ = max_tokens
        # Handle the message format that agents use
        if isinstance(messages, list) and len(messages) > 0:
            # Extract content from messages
            content = ""
            for msg in messages:
                if msg.get('role') == 'user':
                    content += msg.get('content', '')
                elif msg.get('role') == 'system':
                    content += msg.get('content', '')

            # Generate appropriate mock responses based on the prompt content
            content_lower = content.lower()
            if 'double bubble' in content_lower:
                return {
                    "topic1": "Topic A",
                    "topic2": "Topic B",
                    "topic1_attributes": [
                        {"id": "la1", "text": "Unique to A", "category": "A-only"},
                        {"id": "la2", "text": "Another A trait", "category": "A-only"}
                    ],
                    "topic2_attributes": [
                        {"id": "ra1", "text": "Unique to B", "category": "B-only"},
                        {"id": "ra2", "text": "Another B trait", "category": "B-only"}
                    ],
                    "shared_attributes": [
                        {"id": "shared1", "text": "Common trait", "category": "Shared"},
                        {"id": "shared2", "text": "Another common trait", "category": "Shared"}
                    ],
                    "connections": [
                        {"from": "topic1", "to": "la1", "label": "has"},
                        {"from": "topic1", "to": "la2", "label": "has"},
                        {"from": "topic2", "to": "ra1", "label": "has"},
                        {"from": "topic2", "to": "ra2", "label": "has"},
                        {"from": "topic1", "to": "shared1", "label": "shares"},
                        {"from": "topic2", "to": "shared1", "label": "shares"},
                        {"from": "topic1", "to": "shared2", "label": "shares"},
                        {"from": "topic2", "to": "shared2", "label": "shares"}
                    ]
                }
            elif 'bubble map' in content_lower:
                return {
                    "topic": "Test Topic",
                    "attributes": [
                        {"id": "attr1", "text": "Attribute 1", "category": "Category 1"},
                        {"id": "attr2", "text": "Attribute 2", "category": "Category 2"},
                        {"id": "attr3", "text": "Attribute 3", "category": "Category 3"}
                    ],
                    "connections": [
                        {"from": "topic", "to": "attr1", "label": "has"},
                        {"from": "topic", "to": "attr2", "label": "includes"},
                        {"from": "topic", "to": "attr3", "label": "contains"}
                    ]
                }
            elif 'circle map' in content_lower:
                return {
                    "central_topic": "Central Concept",
                    "inner_circle": {"title": "Definition", "content": "A clear definition of the concept"},
                    "middle_circle": {"title": "Examples", "content": "Example 1, Example 2, Example 3"},
                    "outer_circle": {"title": "Context", "content": "The broader context where this concept applies"},
                    "context_elements": [
                        {"id": "elem1", "text": "Context Element 1"},
                        {"id": "elem2", "text": "Context Element 2"}
                    ],
                    "connections": [
                        {"from": "central_topic", "to": "elem1", "label": "relates to"},
                        {"from": "central_topic", "to": "elem2", "label": "connects to"}
                    ]
                }
            elif 'bridge map' in content_lower:
                return {
                    "analogy_bridge": "Common relationship",
                    "left_side": {
                        "topic": "Source Topic",
                        "elements": [
                            {"id": "source1", "text": "Source Element 1"},
                            {"id": "source2", "text": "Source Element 2"}
                        ]
                    },
                    "right_side": {
                        "topic": "Target Topic",
                        "elements": [
                            {"id": "target1", "text": "Target Element 1"},
                            {"id": "target2", "text": "Target Element 2"}
                        ]
                    },
                    "bridge_connections": [
                        {
                            "from": "source1",
                            "to": "target1",
                            "label": "relates to",
                            "bridge_text": "Common relationship"
                        },
                        {
                            "from": "source2",
                            "to": "target2",
                            "label": "connects to",
                            "bridge_text": "Common relationship"
                        }
                    ]
                }
            elif 'concept map' in content_lower:
                return {
                    "topic": "Central Topic",
                    "concepts": ["Concept 1", "Concept 2", "Concept 3", "Concept 4"],
                    "relationships": [
                        {"from": "Concept 1", "to": "Concept 2", "label": "relates to"},
                        {"from": "Concept 2", "to": "Concept 3", "label": "includes"},
                        {"from": "Concept 3", "to": "Concept 4", "label": "part of"}
                    ]
                }
            elif 'brace map' in content_lower:
                return {
                    "topic": "Central Topic",
                    "parts": [
                        {"name": "Part 1", "subparts": [{"name": "Subpart 1"}]},
                        {"name": "Part 2", "subparts": [{"name": "Subpart 2"}]}
                    ]
                }
            elif 'multi-flow' in content_lower:
                return {
                    "event": "Multi-Flow Event",
                    "causes": ["Cause 1", "Cause 2", "Cause 3", "Cause 4"],
                    "effects": ["Effect 1", "Effect 2", "Effect 3", "Effect 4"]
                }
            elif 'flow map' in content_lower or 'flow maps' in content_lower:
                return {
                    "title": "Flow Topic",
                    "steps": ["Step 1", "Step 2", "Step 3"]
                }
            elif 'mind map' in content_lower:
                return {
                    "topic": "Central Topic",
                    "children": [
                        {"id": "branch1", "label": "Branch 1", "children": [{"id": "sub1", "label": "Sub-item 1"}]},
                        {"id": "branch2", "label": "Branch 2", "children": [{"id": "sub2", "label": "Sub-item 2"}]}
                    ]
                }
            elif 'tree map' in content_lower:
                return {
                    "topic": "Root Topic",
                    "children": [
                        {"id": "branch1", "label": "Branch 1", "children": [{"id": "sub1", "label": "Sub-item 1"}]},
                        {"id": "branch2", "label": "Branch 2", "children": [{"id": "sub2", "label": "Sub-item 2"}]}
                    ]
                }
            else:
                # Generic response for other diagram types
                return {"result": "mock response", "type": "generic"}
        else:
            # Fallback for other formats
            return {"result": "mock response", "type": "fallback"}
