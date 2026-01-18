"""Content type detection agent for teaching materials.

Detects content types: theory, example, exercise, summary, code, formula.
"""
from typing import List, Optional, Any
import json
import logging

try:
    from services.llm import llm_service as default_llm_service
except ImportError:
    default_llm_service = None


logger = logging.getLogger(__name__)


class ContentTypeAgent:
    """
    Agent for detecting content types in teaching materials.

    Uses pattern matching + LLM for accurate classification.
    """

    CONTENT_TYPE_PATTERNS = {
        "theory": [
            "concept", "definition", "principle", "theory",
            "explanation", "introduction", "overview"
        ],
        "example": [
            "example", "for instance", "consider", "let's look at",
            "illustration", "case study"
        ],
        "exercise": [
            "exercise", "problem", "practice", "try it yourself",
            "assignment", "question", "challenge"
        ],
        "summary": [
            "summary", "key takeaways", "recap", "conclusion",
            "main points", "remember"
        ],
        "code": [
            "```", "def ", "class ", "function", "import "
        ],
        "formula": [
            "$", "$$", "equation", "formula", "="
        ]
    }

    def __init__(self, llm_service: Any = None):
        """
        Initialize content type agent.

        Args:
            llm_service: LLM service instance
        """
        self.llm_service = llm_service
        if llm_service is None:
            if default_llm_service is None:
                logger.warning("LLM service not available. Content type detection will use pattern matching fallback.")
                self.llm_service = None
            else:
                self.llm_service = default_llm_service

    async def detect_content_type(
        self,
        text: str,
        use_llm: bool = True
    ) -> str:
        """
        Detect content type.

        Args:
            text: Text to analyze
            use_llm: If True, use LLM for more accurate detection

        Returns:
            Content type: "theory", "example", "exercise", "summary", "code", "formula", or "mixed"
        """
        # Step 1: Pattern matching (fast)
        content_type = self._pattern_match(text)
        if content_type and not use_llm:
            return content_type

        # Step 2: LLM refinement (if enabled and pattern unclear)
        if use_llm and self.llm_service:
            if content_type == "mixed" or not content_type:
                return await self._llm_detect(text)

        return content_type or "theory"  # Default

    def _pattern_match(self, text: str) -> Optional[str]:
        """Pattern-based content type detection."""
        text_lower = text.lower()

        # Check for code
        if any(pattern in text for pattern in self.CONTENT_TYPE_PATTERNS["code"]):
            return "code"

        # Check for formula
        if any(pattern in text for pattern in self.CONTENT_TYPE_PATTERNS["formula"]):
            return "formula"

        # Check other types
        matches = {}
        for content_type, patterns in self.CONTENT_TYPE_PATTERNS.items():
            if content_type in ["code", "formula"]:
                continue

            count = sum(1 for pattern in patterns if pattern in text_lower)
            if count > 0:
                matches[content_type] = count

        if not matches:
            return None

        if len(matches) > 1:
            return "mixed"

        return max(matches.items(), key=lambda x: x[1])[0]

    async def _llm_detect(self, text: str) -> str:
        """LLM-based content type detection."""
        prompt = f"""Classify this teaching material content:

{text[:500]}

Return one of: theory, example, exercise, summary, code, formula, mixed

Return JSON:
{{"content_type": "theory"}}
"""

        if self.llm_service is None:
            return "theory"

        try:
            response = await self.llm_service.chat(
                prompt=prompt,
                model='qwen',
                temperature=0.3,
                max_tokens=100
            )

            # Parse JSON
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                result = json.loads(json_str)
                return result.get("content_type", "theory")
        except Exception as e:
            logger.warning("LLM content type detection failed: %s", e)

        return "theory"  # Default

    async def detect_batch(
        self,
        texts: List[str],
        use_llm: bool = True
    ) -> List[str]:
        """
        Detect content types for multiple texts in batch.

        Args:
            texts: List of texts
            use_llm: If True, use LLM

        Returns:
            List of content types
        """
        # Pattern matching first
        types = [self._pattern_match(text) or "theory" for text in texts]

        # LLM refinement for unclear cases
        if use_llm and self.llm_service:
            unclear_indices = [
                i for i, t in enumerate(types)
                if t == "mixed" or not t
            ]

            if unclear_indices:
                unclear_texts = [texts[i] for i in unclear_indices]
                unclear_types = await self._llm_detect_batch(unclear_texts)

                for idx, content_type in zip(unclear_indices, unclear_types):
                    types[idx] = content_type

        return types

    async def _llm_detect_batch(self, texts: List[str]) -> List[str]:
        """LLM batch detection."""
        texts_str = "\n\n".join([
            f"Text {i + 1}:\n{text[:300]}"
            for i, text in enumerate(texts)
        ])

        prompt = f"""Classify these teaching material contents:

{texts_str}

Return JSON array:
[
    {{"text": 1, "content_type": "theory"}},
    {{"text": 2, "content_type": "example"}},
    ...
]
"""

        if self.llm_service is None:
            return ["theory"] * len(texts)

        try:
            response = await self.llm_service.chat(
                prompt=prompt,
                model='qwen',
                temperature=0.3,
                max_tokens=500
            )

            # Parse JSON
            json_start = response.find('[')
            json_end = response.rfind(']') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                results = json.loads(json_str)

                types = []
                for result in results:
                    content_type = result.get("content_type", "theory")
                    types.append(content_type)

                return types[:len(texts)]  # Ensure correct length
        except Exception as e:
            logger.warning("LLM batch detection failed: %s", e)

        return ["theory"] * len(texts)  # Default
