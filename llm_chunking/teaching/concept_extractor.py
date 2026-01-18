"""
Concept extraction for teaching materials.

Extracts key concepts and their relationships from educational content.
"""

import json
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

try:
    from services.llm import llm_service as default_llm_service
except ImportError:
    default_llm_service = None

logger = logging.getLogger(__name__)


@dataclass
class Concept:
    """Represents a concept with relationships."""
    name: str
    level: int  # Hierarchy level (1 = top level)
    parent: Optional[str] = None
    description: Optional[str] = None


class ConceptExtractor:
    """
    Extract key concepts from teaching materials.

    Identifies concepts and their hierarchical relationships.
    """

    def __init__(self, llm_service=None):
        """
        Initialize concept extractor.

        Args:
            llm_service: LLM service instance
        """
        self.llm_service = llm_service
        if llm_service is None:
            try:
                if default_llm_service is None:
                    raise ImportError("llm_service not available")
                self.llm_service = default_llm_service
            except Exception as e:
                logger.warning("LLM service not available: %s", e)

    async def extract_concepts(
        self,
        text: str,
        max_concepts: int = 50
    ) -> List[Concept]:
        """
        Extract key concepts and their relationships.

        Args:
            text: Text to analyze
            max_concepts: Maximum number of concepts to extract

        Returns:
            List of Concept objects
        """
        if not self.llm_service:
            return []

        prompt = f"""Extract key concepts from this teaching material and organize them hierarchically.

Text:
{text[:3000]}

Return JSON array of concepts:
[
    {{
        "name": "Machine Learning",
        "level": 1,
        "parent": null,
        "description": "A subset of AI"
    }},
    {{
        "name": "Supervised Learning",
        "level": 2,
        "parent": "Machine Learning",
        "description": "Learning from labeled data"
    }},
    ...
]

Extract up to {max_concepts} concepts.
"""

        try:
            response = await self.llm_service.chat(
                prompt=prompt,
                model='qwen',
                temperature=0.3,
                max_tokens=2000
            )

            # Parse JSON
            json_start = response.find('[')
            json_end = response.rfind(']') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                concepts_data = json.loads(json_str)

                concepts = []
                for data in concepts_data:
                    concept = Concept(
                        name=data.get("name", ""),
                        level=data.get("level", 1),
                        parent=data.get("parent"),
                        description=data.get("description")
                    )
                    concepts.append(concept)

                return concepts[:max_concepts]
        except Exception as e:
            logger.warning("Concept extraction failed: %s", e)

        return []

    def build_concept_hierarchy(self, concepts: List[Concept]) -> Dict[str, List[Concept]]:
        """
        Build concept hierarchy tree.

        Args:
            concepts: List of concepts

        Returns:
            Dict mapping parent names to child concepts
        """
        hierarchy = {}

        for concept in concepts:
            parent = concept.parent or "root"
            if parent not in hierarchy:
                hierarchy[parent] = []
            hierarchy[parent].append(concept)

        return hierarchy
