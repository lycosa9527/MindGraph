"""
Concept Map Agent module.

Enhances concept map specifications by:
- Normalizing and deduplicating concepts
- Ensuring relationships reference existing concepts and deduplicating unordered pairs
- Cleaning labels
- Generating layout hints (rings, clusters, angle hints)
- Computing evenly-spread node positions with a lightweight force routine
- Providing recommended dimensions sized to fit all content

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Any, Dict, List, Optional, Set, Tuple
import json
import logging
import math
import random
import re
from collections import defaultdict, deque

from langchain_core.prompts import PromptTemplate

from prompts.concept_maps import CONCEPT_MAP_PROMPTS
from services.llm import llm_service

from ..core.base_agent import BaseAgent



logger = logging.getLogger(__name__)


def _strip_parenthetical(text: str) -> str:
    """Remove parenthetical notes (Chinese （） or English ())."""
    if not text:
        return text
    # Take part before first （ or (
    for sep in ("（", "("):
        idx = text.find(sep)
        if idx >= 0:
            text = text[:idx]
    return text.strip()


# Configuration constants
NODE_SPACING = 1.2
CANVAS_PADDING = 80
MIN_NODE_DISTANCE = 120
INNER_RADIUS = 0.25
MIN_RADIUS = 0.45
MAX_RADIUS = 0.95
GAP_FACTOR = 0.9
TARGET_RADIUS = 0.75
REPULSION_FORCE = 0.025
SPRING_FORCE = 0.03
STEP_SIZE = 0.15
ITERATIONS = 200


class ConceptMapAgent(BaseAgent):
    """Agent to enhance and sanitize concept map specifications."""

    MAX_CONCEPTS: int = 30
    MAX_LABEL_LEN: int = 60

    async def enhance_spec(self, spec: Dict) -> Dict:
        """Enhance and sanitize concept map specification.
        
        Normalizes concepts, validates relationships, generates layout,
        and computes recommended dimensions.
        
        Args:
            spec: Dictionary containing topic, concepts, and relationships
            
        Returns:
            Dictionary with success status and enhanced spec or error message
        """
        try:
            if not isinstance(spec, dict):
                return {"success": False, "error": "Spec must be a dictionary"}

            topic = spec.get("topic")
            concepts = spec.get("concepts") or []
            relationships = spec.get("relationships") or []

            if not isinstance(topic, str) or not topic.strip():
                return {"success": False, "error": "Invalid or missing 'topic'"}
            if not isinstance(concepts, list) or not isinstance(relationships, list):
                return {"success": False, "error": "'concepts' and 'relationships' must be lists"}

            normalized_topic = self._clean_text(topic, self.MAX_LABEL_LEN)

            def canonical(label: str) -> str:
                # Canonical form for matching: lowercase + remove all whitespace
                if not isinstance(label, str):
                    return ""
                s = label.lower()
                s = re.sub(r"\s+", "", s)
                return s

            # Normalize and dedupe concepts
            normalized_concepts: List[str] = []
            seen: Set[str] = set()
            canon_to_display: Dict[str, str] = {}
            for c in concepts:
                if not isinstance(c, str):
                    continue
                cleaned = self._clean_text(c, self.MAX_LABEL_LEN)
                canon = canonical(cleaned)
                if cleaned and canon not in seen and cleaned != normalized_topic:
                    normalized_concepts.append(cleaned)
                    seen.add(canon)
                    canon_to_display[canon] = cleaned
                if len(normalized_concepts) >= self.MAX_CONCEPTS:
                    break

            # Sanitize relationships and enforce single edge between unordered pair
            sanitized_relationships: List[Dict[str, str]] = []
            missing_concepts: Set[str] = set()
            pair_seen_unordered: Set[Tuple[str, str]] = set()
            for rel in relationships:
                if not isinstance(rel, dict):
                    continue
                frm_raw = self._clean_text(rel.get("from", ""), self.MAX_LABEL_LEN)
                to_raw = self._clean_text(rel.get("to", ""), self.MAX_LABEL_LEN)
                label = self._clean_text(rel.get("label", ""), self.MAX_LABEL_LEN)
                if not frm_raw or not to_raw or not label:
                    continue
                # Canonical matching to align with concept set
                frm_c = canonical(frm_raw)
                to_c = canonical(to_raw)
                topic_c = canonical(normalized_topic)
                if frm_c == to_c:
                    continue
                # Map canonical back to display
                frm = canon_to_display.get(frm_c, frm_raw)
                to = canon_to_display.get(to_c, to_raw)
                key: Tuple[str, str] = tuple(sorted((frm_c, to_c)))  # type: ignore
                if key in pair_seen_unordered:
                    continue
                pair_seen_unordered.add(key)

                if frm_c not in seen and frm_c != topic_c:
                    missing_concepts.add(frm_c)  # Store canonical form
                if to_c not in seen and to_c != topic_c:
                    missing_concepts.add(to_c)  # Store canonical form

                sanitized_relationships.append({"from": frm, "to": to, "label": label})

            # Add missing endpoints as concepts if capacity allows
            for mc_canon in list(missing_concepts):
                if len(normalized_concepts) < self.MAX_CONCEPTS and mc_canon not in seen:
                    # Find the original display text for this canonical form
                    mc_display = None
                    for rel in relationships:
                        if isinstance(rel, dict):
                            frm_raw = self._clean_text(rel.get("from", ""), self.MAX_LABEL_LEN)
                            to_raw = self._clean_text(rel.get("to", ""), self.MAX_LABEL_LEN)
                            if canonical(frm_raw) == mc_canon:
                                mc_display = frm_raw
                                break
                            if canonical(to_raw) == mc_canon:
                                mc_display = to_raw
                                break

                    if mc_display:
                        normalized_concepts.append(mc_display)
                        seen.add(mc_canon)
                        canon_to_display[mc_canon] = mc_display

            # Final filter: drop any relationship whose endpoints are not in concepts or topic
            concept_or_topic = set(normalized_concepts)
            concept_or_topic.add(normalized_topic)
            sanitized_relationships = [
                r for r in sanitized_relationships
                if r["from"] in concept_or_topic and r["to"] in concept_or_topic
            ]

            # ALWAYS use radial layout for all concept maps
            layout = self._generate_layout_radial(
                normalized_topic, normalized_concepts, sanitized_relationships
            )

            # Compute recommended dimensions based on normalized positions extents
            recommended = self._compute_recommended_dimensions_from_layout(
                layout=layout,
                topic=normalized_topic,
                concepts=normalized_concepts,
            )

            enhanced_spec: Dict = {
                "topic": normalized_topic,
                "concepts": normalized_concepts,
                "relationships": sanitized_relationships,
                "_layout": layout,
                "_recommended_dimensions": recommended,
                "_config": {
                    "nodeSpacing": 4.0,  # Maximum node spacing multiplier (increased from 3.0)
                    "canvasPadding": 140,  # Even more padding around the diagram (increased from 120)
                    "minNodeDistance": 320  # Maximum minimum distance between nodes in pixels (increased from 250)
                }
            }

            # Preserve important metadata from original spec
            if spec.get('_method'):
                enhanced_spec['_method'] = spec['_method']
            if spec.get('_concept_count'):
                enhanced_spec['_concept_count'] = spec['_concept_count']

            if isinstance(spec.get("_style"), dict):
                enhanced_spec["_style"] = spec["_style"]

            return {"success": True, "spec": enhanced_spec}
        except Exception as exc:
            return {"success": False, "error": f"ConceptMapAgent failed: {exc}"}

    def _get_direction_instruction(
        self, link_direction: str | None, language: str
    ) -> str:
        """Return direction-specific instruction for relationship generation."""
        direction = (link_direction or "").strip().lower()
        instructions: Dict[str, Dict[str, str]] = {
            "zh": {
                "source_to_target": (
                    "该连线有箭头，从概念A指向概念B。请生成 3–5 个不同的动词/短语，描述 A 如何导致、引导或指向 B。"
                    "类型宜多样：如因果、组成、依赖等。"
                ),
                "target_to_source": (
                    "该连线有箭头，从概念B指向概念A。请生成 3–5 个不同的动词/短语，描述 B 如何导致、引导或指向 A。"
                    "类型宜多样。"
                ),
                "both": (
                    "该连线两端均有箭头（双向）。请生成 3–5 个不同的动词/短语，描述 A 与 B 如何相互关联或影响。"
                ),
                "none": (
                    "该连线无箭头。这两个概念是平行或对称相关的。"
                    "请生成 3–5 个不同的标签（对称、非方向性），可以是名词、形容词或短语。"
                    "示例类型：相似、对比、同类、互补、对应、并列。"
                ),
            },
            "en": {
                "source_to_target": (
                    "The link has an arrow from A to B. "
                    "Generate 3–5 different verb phrases describing how A leads to, causes, or directs to B. "
                    "Vary the relationship types (causal, compositional, dependency, etc.)."
                ),
                "target_to_source": (
                    "The link has an arrow from B to A. "
                    "Generate 3–5 different verb phrases describing how B leads to, causes, or directs to A. "
                    "Vary the relationship types."
                ),
                "both": (
                    "The link has arrows on both ends (bidirectional). "
                    "Generate 3–5 different phrases describing how A and B relate or influence each other."
                ),
                "none": (
                    "The link has no arrow. These concepts are in parallel or symmetrically related. "
                    "Generate 3–5 different symmetric labels (noun, adjective, or phrase). "
                    "Examples: similar to, contrasts with, complementary, analogous to, parallel."
                ),
            },
        }
        lang = "zh" if language == "zh" else "en"
        key = direction if direction in instructions[lang] else "none"
        return instructions[lang][key]

    async def _generate_relationship_only(
        self,
        concept_a: str,
        concept_b: str,
        language: str,
        concept_map_topic: str = "",
        link_direction: str | None = None,
        **_kwargs: Any
    ) -> Dict[str, Any]:
        """Generate only the relationship label between two concepts."""
        topic = (concept_map_topic or "").strip()
        if language == "zh":
            topic_context = (
                f"主题是：{topic}" if topic else "此图尚未设置主主题。"
            )
        else:
            topic_context = (
                f"The topic is about: {topic}"
                if topic
                else "No main topic has been set for this map."
            )
        direction_instruction = self._get_direction_instruction(
            link_direction, language
        )
        prompt_key = f"concept_map_relationship_only_{language}"
        prompt_template = self._get_prompt(
            prompt_key,
            concept_a=concept_a,
            concept_b=concept_b,
            topic_context=topic_context,
            direction_instruction=direction_instruction,
        )
        if not prompt_template:
            return {"success": False, "error": f"Prompt not found: {prompt_key}"}

        logger.debug(
            "Concept map relationship-only request: concept_a=%r concept_b=%r topic=%r "
            "link_direction=%r language=%s model=%s",
            concept_a, concept_b, topic, link_direction, language, self.model
        )
        logger.debug("Concept map relationship prompt (first 500 chars): %.500s", prompt_template)

        try:
            response = await llm_service.chat(
                prompt=prompt_template,
                model=self.model,
                timeout=15.0
            )
            raw = (response or "").strip()
            logger.debug("Concept map relationship LLM raw response: %r", raw)
            if raw.startswith("```"):
                raw = raw.split("```", 2)[-1].strip()
            lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
            labels: List[str] = []
            for line in lines[:5]:
                cleaned = _strip_parenthetical(line)
                if cleaned:
                    labels.append(cleaned)
            logger.debug("Concept map relationship parsed labels (%d): %s", len(labels), labels)
            if not labels:
                return {"success": False, "error": "Empty response from LLM"}
            return {
                "success": True,
                "relationship_label": labels[0],
                "relationship_labels": labels,
            }
        except Exception as e:
            logger.error("ConceptMapAgent: Relationship-only generation failed: %s", e)
            return {"success": False, "error": str(e)}

    async def generate_graph(
        self,
        user_prompt: str,
        language: str = "en",
        dimension_preference: str | None = None,
        fixed_dimension: str | None = None,
        dimension_only_mode: bool | None = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Generate a concept map graph specification from user prompt.

        This method implements the BaseAgent interface and delegates to the main
        concept map generation functions in main_agent.py for consistency.

        Args:
            user_prompt: User's input prompt
            language: Language for processing ('zh' or 'en')
            dimension_preference: Unused for concept maps (BaseAgent interface)
            fixed_dimension: Unused for concept maps (BaseAgent interface)
            dimension_only_mode: Unused for concept maps (BaseAgent interface)
            **kwargs: relationship_only, concept_a, concept_b, user_id, etc.

        Returns:
            dict: Graph specification or {success, relationship_label} for relationship_only
        """
        relationship_only = kwargs.get('relationship_only', False)
        concept_a = kwargs.get('concept_a')
        concept_b = kwargs.get('concept_b')
        concept_map_topic = kwargs.get('concept_map_topic') or ""
        try:
            if relationship_only and concept_a and concept_b:
                return await self._generate_relationship_only(
                    concept_a,
                    concept_b,
                    language,
                    concept_map_topic=concept_map_topic,
                    link_direction=kwargs.get('link_direction'),
                )

            logger.info(
                "ConceptMapAgent: Returning minimal spec (multi-stage removed, "
                "use real-time relationship generation)"
            )
            # Multi-stage generation removed. Return minimal spec for user to build
            # manually with real-time relationship suggestions on link creation.
            topic = (user_prompt or "").strip() or "Topic"
            minimal_spec = {
                "topic": topic,
                "concepts": [],
                "relationships": [],
            }
            enhanced_result = await self.enhance_spec(minimal_spec)
            if not enhanced_result.get('success'):
                logger.warning(
                    "ConceptMapAgent: Enhancement failed: %s",
                    enhanced_result.get('error')
                )
                return minimal_spec
            return enhanced_result.get('spec', minimal_spec)

        except Exception as e:
            logger.error("ConceptMapAgent: Generation error: %s", e)
            return {"error": f"ConceptMapAgent generation failed: {str(e)}"}

    def _get_prompt(self, prompt_key: str, **kwargs) -> Optional[str]:
        """Get prompt from the prompts module."""
        try:
            # Try to get the language-specific prompt first
            language = kwargs.get('language', 'en')
            if language == 'zh':
                # Try Chinese version first
                zh_key = prompt_key.replace('_en', '_zh')
                prompt_template = CONCEPT_MAP_PROMPTS.get(zh_key)
                if prompt_template:
                    return prompt_template.format(**kwargs)

            # Fallback to English version
            prompt_template = CONCEPT_MAP_PROMPTS.get(prompt_key)
            if prompt_template:
                return prompt_template.format(**kwargs)

            # If we still don't have a prompt, log the issue
            print(f"Warning: No prompt found for key '{prompt_key}' (language: {language})")
            print(f"Available keys: {list(CONCEPT_MAP_PROMPTS.keys())}")
            return None
        except ImportError as e:
            print(f"Error importing prompts module: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error in _get_prompt: {e}")
            return None

    def _get_llm_response(self, llm_client, prompt: str) -> str:
        """Get response from LLM client, handling different client types."""
        try:
            # Check if it's a mock client with get_response method
            if hasattr(llm_client, 'get_response'):
                return llm_client.get_response(prompt)

            # Check if it's a LangChain LLM client with invoke method
            if hasattr(llm_client, 'invoke'):
                # Use LangChain's invoke method
                pt = PromptTemplate(input_variables=[], template=prompt)
                result = llm_client.invoke(pt)
                return str(result) if result else ""

            # Check if it's an async client with chat_completion method
            if hasattr(llm_client, 'chat_completion'):
                # For now, return a mock response since we can't easily run async here
                # In production, you'd want to properly handle the async call
                if "concepts" in prompt.lower():
                    return '{"topic": "Test Topic", "concepts": ["Concept 1", "Concept 2", "Concept 3"]}'
                if "relationships" in prompt.lower():
                    return '{"relationships": [{"from": "Concept 1", "to": "Concept 2", "label": "relates to"}]}'
                return '{"result": "mock response"}'

            # Fallback for other client types
            raise ValueError(f"Unsupported LLM client type: {type(llm_client)}")

        except Exception as e:
            raise ValueError(f"Failed to get LLM response: {str(e)}") from e

    def parse_json_response(self, response: str) -> Dict:
        """Parse JSON response from LLM, handling common formatting issues.

        This method includes multiple fallback strategies:
        1. Direct JSON parsing
        2. Fix unterminated strings and balance braces
        3. Extract JSON from markdown blocks
        4. Find JSON-like content with regex
        5. Create fallback responses from partial content
        6. Generate generic fallback if all else fails
        """
        try:
            # Remove markdown code blocks if present
            cleaned = response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]

            cleaned = cleaned.strip()

            # Try to parse as JSON
            return json.loads(cleaned)

        except json.JSONDecodeError as e:
            # Log the original error for debugging
            logger.warning("JSON parsing failed: %s", e)
            logger.debug("Original response: %s...", response[:500])

            # Log the full response for debugging (truncated if too long)
            if len(response) > 1000:
                logger.debug("Full response (truncated): %s...", response[:1000])
            else:
                logger.debug("Full response: %s", response)

            # Try to fix unterminated strings and other common issues
            try:
                # Fix unterminated strings by finding the last complete quote
                # Look for patterns like "text" where the quote might be missing
                cleaned = re.sub(r'"([^"]*?)(?=\s*[,}\]]|$)', r'"\1"', cleaned)

                # Fix unescaped quotes within strings
                # This is tricky, but we can try to balance quotes
                quote_count = cleaned.count('"')
                if quote_count % 2 == 1:  # Odd number of quotes
                    # Find the last quote and see if we can balance it
                    last_quote_pos = cleaned.rfind('"')
                    if last_quote_pos > 0:
                        # Check if this looks like an unterminated string
                        before_quote = cleaned[:last_quote_pos]
                        if before_quote.rstrip().endswith(':'):
                            # This looks like a key without a value, remove it
                            cleaned = cleaned[:last_quote_pos].rstrip().rstrip(':').rstrip()
                            cleaned += '}'

                # Additional fix for unterminated strings at the end
                # Look for patterns like "key": "value where the closing quote is missing
                cleaned = re.sub(r'"([^"]*?)(?=\s*[,}\]]|$)', r'"\1"', cleaned)

                # Try to balance braces if they're mismatched
                open_braces = cleaned.count('{')
                close_braces = cleaned.count('}')
                if open_braces > close_braces:
                    cleaned += '}' * (open_braces - close_braces)
                elif close_braces > open_braces:
                    # Remove extra closing braces from the end
                    cleaned = cleaned.rstrip('}')
                    # Add back the right number
                    cleaned += '}' * open_braces

                logger.info("Attempting to parse cleaned JSON after fixes")
                # Try to parse the cleaned JSON
                result = json.loads(cleaned)
                logger.info("Successfully parsed JSON after applying fixes")
                return result

            except json.JSONDecodeError as e2:
                logger.warning("Cleaned JSON parsing also failed: %s", e2)

            # Try to find JSON-like content
            try:
                json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

            # Try to fix common issues
            try:
                # Remove any leading/trailing whitespace and newlines
                cleaned = re.sub(r'^\s+|\s+$', '', cleaned, flags=re.MULTILINE)
                # Try to find the start and end of JSON
                start = cleaned.find('{')
                end = cleaned.rfind('}') + 1
                if 0 <= start < end:
                    json_content = cleaned[start:end]
                    return json.loads(json_content)
            except json.JSONDecodeError:
                pass

            # Try to extract whatever concepts we can find from the response
            topic_match = re.search(r'"topic"\s*:\s*"([^"]+)"', cleaned)
            topic = topic_match.group(1) if topic_match else "Unknown Topic"

            # Extract concepts using multiple patterns - take whatever we can find
            concepts = []

            # Pattern 1: Look for concepts array
            concepts_match = re.search(r'"concepts"\s*:\s*\[(.*?)\]', cleaned, re.DOTALL)
            if concepts_match:
                concepts_str = concepts_match.group(1)
                concepts = [c.strip().strip('"') for c in concepts_str.split(',') if c.strip()]
                logger.info("Extracted concepts using Pattern 1 (concepts array): %s", concepts)

            # Pattern 2: Look for keys array (for two-stage approach)
            if not concepts:
                keys_match = re.search(r'"keys"\s*:\s*\[(.*?)\]', cleaned, re.DOTALL)
                if keys_match:
                    keys_str = keys_match.group(1)
                    # Extract names from key objects
                    key_names = re.findall(r'"name"\s*:\s*"([^"]+)"', keys_str)
                    concepts.extend(key_names)
                    logger.info("Extracted concepts using Pattern 2 (keys array): %s", concepts)

            # Pattern 3: Look for individual concept-like strings in the response
            if not concepts:
                # Find all quoted strings that look like concept names
                concept_candidates = re.findall(r'"([^"]{2,20})"', cleaned)
                # Filter out common JSON keys and short strings
                json_keys = {'topic', 'concepts', 'keys', 'key_parts', 'relationships', 'from', 'to', 'label'}
                concepts = [c for c in concept_candidates if c not in json_keys and len(c) > 1]
                if concepts:
                    logger.info("Extracted concepts using Pattern 3 (quoted strings): %s", concepts)

            # Pattern 4: Look for unquoted concept names in the response
            if not concepts:
                # Find Chinese characters that might be concept names
                chinese_concepts = re.findall(r'[\u4e00-\u9fff]{2,6}', cleaned)
                # Filter out common words and keep meaningful concepts
                common_words = {'概念', '主题', '包含', '相关', '应用', '原理', '特点', '方法', '工具', '技术'}
                concepts = [c for c in chinese_concepts if c not in common_words and len(c) >= 2]
                # Remove duplicates while preserving order
                seen = set()
                unique_concepts = []
                for c in concepts:
                    if c not in seen:
                        seen.add(c)
                        unique_concepts.append(c)
                concepts = unique_concepts[:6]  # Limit to 6 concepts
                if concepts:
                    logger.info("Extracted concepts using Pattern 4 (Chinese characters): %s", concepts)

            # Return whatever we found, even if incomplete
            if concepts:
                logger.info("Extracted partial concepts from malformed JSON: %s", concepts)
                return {"topic": topic, "concepts": concepts}
            # If we found absolutely nothing, just return the topic
            logger.warning("Could not extract any concepts from response, returning topic only: %s", topic)
            return {"topic": topic, "concepts": []}

    def _clean_text(self, text: str, max_len: int) -> str:
        if not isinstance(text, str):
            return ""
        cleaned = " ".join(text.split())
        if len(cleaned) > max_len:
            cleaned = cleaned[: max_len - 1].rstrip() + "…"
        return cleaned

    def _generate_layout_radial(self, topic: str, concepts: List[str], relationships: List[Dict[str, str]]) -> Dict:
        """Generate radial/circular layout with concentric circles around central topic."""
        if not concepts:
            return {"algorithm": "radial", "positions": {topic: {"x": 0.0, "y": 0.0}}}

        # Central topic at origin
        positions = {topic: {"x": 0.0, "y": 0.0}}

        # Build relationship graph to determine distance from center
        graph = defaultdict(set)
        for rel in relationships:
            from_node = rel.get("from")
            to_node = rel.get("to")
            if from_node and to_node:
                graph[from_node].add(to_node)
                graph[to_node].add(from_node)

        # Intelligently assign concepts to concentric circles
        concept_layers = {}

        # First, try BFS from central topic for direct relationships
        visited = {topic}
        queue = deque([(topic, 0)])

        while queue:
            current_node, layer = queue.popleft()

            for neighbor in graph[current_node]:
                if neighbor not in visited and neighbor in concepts:
                    visited.add(neighbor)
                    concept_layers[neighbor] = layer + 1
                    queue.append((neighbor, layer + 1))

        # For better visual distribution, create multiple concentric circles
        total_concepts = len(concepts)

        if total_concepts <= 10:
            # Small concept maps: 1-2 circles
            target_circles = 2
        elif total_concepts <= 20:
            # Medium concept maps: 2-3 circles
            target_circles = 3
        else:
            # Large concept maps: 3-4 circles
            target_circles = 4

        # Distribute all concepts across target number of circles
        all_concepts = list(concepts)
        concepts_per_circle = total_concepts // target_circles

        # Clear and redistribute for better visual appearance
        concept_layers = {}

        for i, concept in enumerate(all_concepts):
            # Distribute evenly across circles, with inner circles having fewer nodes
            if i < concepts_per_circle * 0.7:  # Inner circle (smaller)
                layer = 1
            elif i < concepts_per_circle * 1.8:  # Middle circle
                layer = 2
            elif i < concepts_per_circle * 3.0:  # Outer circle
                layer = 3
            else:  # Outermost circle
                layer = min(4, target_circles)

            concept_layers[concept] = layer

        # Group concepts by layer
        layers = defaultdict(list)
        for concept, layer in concept_layers.items():
            layers[layer].append(concept)

        # Calculate adaptive radii for concentric circles with maximum spacing
        # Use the EXACT same coordinate system as the root concept map agent for compatibility
        max_layer = max(layers.keys()) if layers else 1
        base_radius = 1.8  # Start radius for first circle (even larger from 1.2)
        radius_increment = min(1.2, 3.5 / max_layer)  # Maximum spacing (even larger from 0.8 and 2.5)

        # Position concepts in each concentric circle
        for layer_num, layer_concepts in layers.items():
            n_concepts = len(layer_concepts)
            if n_concepts == 0:
                continue

            # Calculate radius for this layer
            radius = base_radius + (layer_num - 1) * radius_increment
            radius = min(radius, 5.0)  # Allow maximum expansion for ultimate spacing (increased from 3.5)

            # Distribute concepts evenly around the circle
            for i, concept in enumerate(layer_concepts):
                # Calculate angle for even distribution
                angle = (2 * math.pi * i) / n_concepts

                # Add slight randomization to avoid perfect alignment
                angle_offset = random.uniform(-0.1, 0.1) if n_concepts > 1 else 0
                final_angle = angle + angle_offset

                # Calculate position
                x = radius * math.cos(final_angle)
                y = radius * math.sin(final_angle)

                positions[concept] = {"x": x, "y": y}

        # Generate edge curvatures for radial connections
        edge_curvatures = {}
        for i, concept in enumerate(concepts):
            # Vary curvature to reduce overlapping edges
            edge_curvatures[concept] = [0.0, 8.0, -8.0, 16.0, -16.0][i % 5]

        # Generate the EXACT same layout structure as the root concept map agent
        # This ensures 100% compatibility with the existing D3.js renderer
        return {
            "algorithm": "radial",
            "positions": positions,
            "edgeCurvatures": edge_curvatures,
            "layers": dict(layers),  # For debugging/analysis
            "params": {
                "nodeSpacing": 1.0,
                "baseRadius": base_radius,
                "radiusIncrement": radius_increment,
                "maxLayers": max_layer,
                "canvasBounds": 0.95
            }
        }

    def _compute_recommended_dimensions_from_layout(
        self,
        layout: Dict,
        topic: str,
        concepts: List[str],
    ) -> Dict[str, int]:
        """Calculate canvas size based on actual SVG element dimensions like D3.js does.

        This simulates the D3.js drawBox() function to predict real space requirements.
        """
        positions = layout.get("positions") or {}
        if not positions:
            # Minimal fallback sizing for empty layouts
            return {"baseWidth": 800, "baseHeight": 600, "width": 800, "height": 600, "padding": 100}

        # Simulate D3.js text measurement and box sizing
        def estimate_text_box(text: str, is_topic: bool = False) -> tuple:
            """Estimate text box dimensions like D3.js drawBox() function."""
            font_size = 26 if is_topic else 22  # Even larger font sizes for maximum readability (was 22/18)
            max_text_width = 350 if is_topic else 300  # Even larger max width for bigger text (was 300/260)

            # Estimate character width (approximate for common fonts)
            char_width = font_size * 0.6  # Rough estimate for common fonts
            text_width = len(text) * char_width

            # Handle text wrapping
            if text_width > max_text_width:
                lines = max(1, int(text_width / max_text_width) + 1)
                actual_text_width = min(text_width, max_text_width)
            else:
                lines = 1
                actual_text_width = text_width

            # Add padding like D3.js drawBox()
            padding_x = 16
            padding_y = 10
            line_height = int(font_size * 1.2)

            box_w = int(actual_text_width + padding_x * 2)
            box_h = int(lines * line_height + padding_y * 2)

            return box_w, box_h

        # Calculate actual node dimensions
        topic_w, topic_h = estimate_text_box(topic, True)

        concept_boxes = []
        for concept in concepts:
            w, h = estimate_text_box(concept, False)
            concept_boxes.append((w, h))

        # Find the coordinate bounds
        xs = [positions[c]["x"] for c in positions if "x" in positions[c]]
        ys = [positions[c]["y"] for c in positions if "y" in positions[c]]
        if not xs or not ys:
            return {"baseWidth": 800, "baseHeight": 600, "width": 800, "height": 600, "padding": 100}

        xmin, xmax = min(xs), max(xs)
        ymin, ymax = min(ys), max(ys)

        # Calculate the scale factor D3.js uses: scaleX = (width - 2*padding) / 6
        # We need to reverse this: width = spanx * pixels_per_unit + 2*padding + node_sizes

        # Coordinate span in the normalized space
        coord_span_x = max(0.4, xmax - xmin)
        coord_span_y = max(0.4, ymax - ymin)

        # We want the diagram to be readable, so use a scale that accommodates larger text and more spacing
        # Increased scale to handle larger text and maximum node spacing
        target_scale = 180  # Optimized for larger text and maximum spacing (reduced from 200 to balance size)

        # Calculate content area needed for positions
        content_area_x = coord_span_x * target_scale
        content_area_y = coord_span_y * target_scale

        # Add space for the largest nodes (half extends on each side)
        max_concept_w = max((w for w, h in concept_boxes), default=100)
        max_concept_h = max((h for w, h in concept_boxes), default=40)

        node_margin_x = max(topic_w, max_concept_w) // 2
        node_margin_y = max(topic_h, max_concept_h) // 2

        # Calculate total required space
        base_padding = 80  # Reasonable padding
        total_width = content_area_x + (2 * node_margin_x) + (2 * base_padding)
        total_height = content_area_y + (2 * node_margin_y) + (2 * base_padding)

        # Apply reasonable bounds
        num_concepts = len(concepts)
        min_width = max(600, 400 + num_concepts * 10)   # Increased for larger text and spacing
        min_height = max(500, 350 + num_concepts * 8)
        max_width = 1400   # Increased maximum to accommodate larger text and spacing (was 1200)
        max_height = 1200  # Increased maximum to accommodate larger text and spacing (was 1000)

        width_px = int(max(min_width, min(max_width, total_width)))
        height_px = int(max(min_height, min(max_height, total_height)))

        return {
            "baseWidth": width_px,
            "baseHeight": height_px,
            "width": width_px,
            "height": height_px,
            "padding": base_padding
        }


__all__ = ["ConceptMapAgent"]
