"""
Brace map helper classes.

Contains ContextManager, CollisionDetector, LLMHybridProcessor,
and ContextAwareAlgorithmSelector used by the brace map agent.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .brace_map_models import (
    LayoutAlgorithm,
    LayoutComplexity,
    LLMStrategy,
    NodePosition,
)


class ContextManager:
    """Manages user context and preferences"""

    def __init__(self):
        self.user_contexts: Dict = {}
        self.user_preferences: Dict = {}

    def store_user_prompt(self, user_id: str, prompt: str, diagram_type: str) -> None:
        """Store user prompt for context analysis"""
        if user_id not in self.user_contexts:
            self.user_contexts[user_id] = []

        self.user_contexts[user_id].append(
            {
                "prompt": prompt,
                "diagram_type": diagram_type,
                "timestamp": datetime.now().isoformat(),
            }
        )

        if len(self.user_contexts[user_id]) > 10:
            self.user_contexts[user_id] = self.user_contexts[user_id][-10:]

    def get_user_context(self, user_id: str) -> Dict:
        """Get user context for personalization"""
        if user_id not in self.user_contexts:
            return {"recent_prompts": [], "preferences": {}}

        recent_prompts = self.user_contexts[user_id]
        preferences = self.user_preferences.get(user_id, {})

        return {
            "recent_prompts": recent_prompts,
            "preferences": preferences,
            "session_id": self._get_current_session(user_id),
        }

    def update_preferences(self, user_id: str, preferences: Dict) -> None:
        """Update user preferences"""
        if user_id not in self.user_preferences:
            self.user_preferences[user_id] = {}
        self.user_preferences[user_id].update(preferences)

    def alter_diagram_based_on_context(self, spec: Dict, context: Dict) -> Dict:
        """Alter diagram specification based on user context"""
        altered_spec = spec.copy()
        recent_prompts = context.get("recent_prompts", [])
        if recent_prompts:
            common_themes = self._extract_common_themes(recent_prompts)
            if common_themes:
                pass
        return altered_spec

    def _get_current_session(self, user_id: str) -> str:
        """Get current session ID for user"""
        return f"session_{user_id}_{datetime.now().strftime('%Y%m%d')}"

    def _extract_common_themes(self, recent_prompts: List[Dict]) -> List[str]:
        """Extract common themes from recent prompts"""
        themes = []
        for prompt_data in recent_prompts:
            prompt = prompt_data["prompt"].lower()
            if "science" in prompt:
                themes.append("science")
            if "business" in prompt:
                themes.append("business")
            if "education" in prompt:
                themes.append("education")
        return list(set(themes))


class CollisionDetector:
    """Detects and resolves node collisions"""

    @staticmethod
    def detect_node_collisions(
        nodes: List[NodePosition], padding: float = 10.0
    ) -> List[Tuple[NodePosition, NodePosition]]:
        """Detect overlapping nodes"""
        collisions = []
        for i, node1 in enumerate(nodes):
            for node2 in nodes[i + 1 :]:
                if CollisionDetector._nodes_overlap(node1, node2, padding):
                    collisions.append((node1, node2))
        return collisions

    @staticmethod
    def resolve_collisions(nodes: List[NodePosition], padding: float = 10.0) -> List[NodePosition]:
        """Resolve node collisions by adjusting positions"""
        resolved_nodes = nodes.copy()
        max_iterations = 10
        iteration = 0

        while iteration < max_iterations:
            collisions = CollisionDetector.detect_node_collisions(resolved_nodes, padding)
            if not collisions:
                break

            for node1, node2 in collisions:
                CollisionDetector._resolve_collision(node1, node2, padding)
            iteration += 1

        return resolved_nodes

    @staticmethod
    def _nodes_overlap(node1: NodePosition, node2: NodePosition, padding: float) -> bool:
        """Check if two nodes overlap"""
        return (
            abs(node1.x - node2.x) < (node1.width + node2.width) / 2 + padding
            and abs(node1.y - node2.y) < (node1.height + node2.height) / 2 + padding
        )

    @staticmethod
    def _resolve_collision(node1: NodePosition, node2: NodePosition, padding: float) -> None:
        """Resolve collision between two nodes"""
        dx = node2.x - node1.x
        dy = node2.y - node1.y

        if node2.node_type == "subpart" or node1.node_type == "subpart":
            if dy >= 0:
                node2.y = node1.y + (node1.height + node2.height) / 2 + padding
            else:
                node2.y = node1.y - (node1.height + node2.height) / 2 - padding
        else:
            if abs(dx) > abs(dy):
                if dy >= 0:
                    node2.y = node1.y + (node1.height + node2.height) / 2 + padding
                else:
                    node2.y = node1.y - (node1.height + node2.height) / 2 - padding
            else:
                if dx >= 0:
                    node2.x = node1.x + (node1.width + node2.width) / 2 + padding
                else:
                    node2.x = node1.x - (node1.width + node2.width) / 2 - padding


class LLMHybridProcessor:
    """Processes content complexity and determines LLM strategy"""

    def analyze_complexity(self, spec: Dict) -> LayoutComplexity:
        """Analyze content complexity for layout strategy"""
        total_parts = len(spec.get("parts", []))
        total_subparts = sum(len(part.get("subparts", [])) for part in spec.get("parts", []))
        total_elements = total_parts + total_subparts

        if total_elements <= 5:
            return LayoutComplexity.SIMPLE
        if total_elements <= 15:
            return LayoutComplexity.MODERATE
        return LayoutComplexity.COMPLEX

    def determine_strategy(self, complexity: LayoutComplexity, _user_preferences: Optional[Dict] = None) -> LLMStrategy:
        """Determine LLM processing strategy"""
        if complexity == LayoutComplexity.SIMPLE:
            return LLMStrategy.PYTHON_ONLY
        if complexity == LayoutComplexity.MODERATE:
            return LLMStrategy.LLM_ENHANCEMENT
        return LLMStrategy.LLM_FIRST


class ContextAwareAlgorithmSelector:
    """Selects layout algorithm based on context"""

    def __init__(self, context_manager: ContextManager):
        self.context_manager = context_manager

    def select_algorithm(self, _spec: Dict, _user_id: Optional[str] = None) -> LayoutAlgorithm:
        """Select the appropriate layout algorithm"""
        return LayoutAlgorithm.FLEXIBLE_DYNAMIC
