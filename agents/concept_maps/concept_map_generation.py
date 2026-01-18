"""
Concept map generation methods.

This module provides various methods for generating concept maps using LLM,
including two-stage, unified, and enhanced 30-concept generation.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import json
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

from prompts import get_prompt

from agents.core.llm_clients import llm_generation
from agents.core.topic_extraction import extract_central_topic_llm
from agents.core.utils import _parse_strict_json

logger = logging.getLogger(__name__)


def _invoke_llm_prompt(prompt_template: str, variables: dict) -> str:
    """Invoke LLM with a specific prompt template and variables, and return raw string."""
    safe_template = prompt_template
    # Sanitize braces except for placeholders present in variables
    for k in variables.keys():
        placeholder = f"<<{k.upper()}>>"
        safe_template = safe_template.replace(f"{{{k}}}", placeholder)
    safe_template = safe_template.replace("{", "{{").replace("}", "}}")
    for k in variables.keys():
        placeholder = f"<<{k.upper()}>>"
        safe_template = safe_template.replace(placeholder, f"{{{k}}}")
    # Use generation model for concept map generation tasks (high quality)
    # Format the template with variables and call the LLM directly
    formatted_prompt = safe_template
    for key, value in variables.items():
        formatted_prompt = formatted_prompt.replace(f"{{{key}}}", str(value))

    raw = llm_generation.invoke(formatted_prompt)
    return raw if isinstance(raw, str) else str(raw)


def generate_concept_map_two_stage(user_prompt: str, language: str) -> dict:
    """Deterministic two-stage generation for concept maps (no fallback parsing errors)."""
    # Stage 1: keys
    key_prompt = get_prompt('concept_map_keys', language, 'generation')
    raw_keys = _invoke_llm_prompt(key_prompt, {'user_prompt': user_prompt})

    # Use improved parsing for better error handling
    try:
        from agents.concept_maps.concept_map_agent import ConceptMapAgent
        agent = ConceptMapAgent()
        keys_obj = agent.parse_json_response(raw_keys)
        logger.debug("Used ConceptMapAgent improved parsing for keys generation")
    except Exception as e:  # pylint: disable=broad-except
        logger.warning(
            "ConceptMapAgent parsing failed for keys, falling back to strict parsing: %s",
            e
        )
        # Fallback to strict parsing if ConceptMapAgent is not available
        keys_obj = _parse_strict_json(raw_keys)
        logger.debug("Used strict parsing fallback for keys generation")
    topic = (keys_obj.get('topic') or user_prompt).strip()
    keys_raw = keys_obj.get('keys') or []
    keys = []
    seen_keys = set()
    for k in keys_raw:
        name = k.get('name') if isinstance(k, dict) else k
        if isinstance(name, str):
            name = name.strip()
            if name and name.lower() not in seen_keys:
                keys.append(name)
                seen_keys.add(name.lower())
    # Cap keys to 4–8 for readability
    max_keys = 8
    min_keys = 4
    keys = keys[:max_keys]
    if len(keys) < min_keys and len(keys_raw) > 0:
        # Best-effort: keep as is; downstream will handle layout even with fewer keys
        pass

    # Stage 2: parts for each key
    parts_prompt = get_prompt('concept_map_parts', language, 'generation')

    # Budget total concepts <= 30
    max_concepts_total = 30
    remaining_budget = max(0, max_concepts_total - len(keys))
    per_key_cap = max(2, remaining_budget // max(1, len(keys))) if keys else 0

    def fetch_parts(k: str) -> tuple:
        try:
            raw = _invoke_llm_prompt(parts_prompt, {'topic': topic, 'key': k})

            # Use improved parsing for better error handling
            try:
                from agents.concept_maps.concept_map_agent import ConceptMapAgent
                agent = ConceptMapAgent()
                obj = agent.parse_json_response(raw)
                logger.debug("Used ConceptMapAgent improved parsing for parts of key '%s'", k)
            except Exception:  # pylint: disable=broad-except
                logger.debug(
                    "ConceptMapAgent parsing failed for parts of key '%s', "
                    "using strict parsing fallback", k
                )
                # Fallback to strict parsing if ConceptMapAgent is not available
                obj = _parse_strict_json(raw)
            plist = obj.get('parts') or []
            parts_collected = []
            seen = set()
            for p in plist:
                name = p.get('name') if isinstance(p, dict) else p
                label = p.get('label') if isinstance(p, dict) else None
                if isinstance(name, str):
                    name = name.strip()
                    if name and name.lower() not in seen:
                        parts_collected.append({'name': name, 'label': (label or '').strip()[:60]})
                        seen.add(name.lower())
                if len(parts_collected) >= per_key_cap:
                    break
            return (k, parts_collected)
        except Exception:  # pylint: disable=broad-except
            return (k, [])

    parts_results = {k: [] for k in keys}
    # Run in parallel to save time
    max_workers = min(6, len(keys)) or 1
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(fetch_parts, k) for k in keys]
        for fut in as_completed(futures):
            k, plist = fut.result()
            parts_results[k] = plist

    # Merge into standard concept map spec
    concepts = []
    seen_concepts = set()
    for name in keys + [p.get('name') for arr in parts_results.values() for p in arr]:
        low = name.lower()
        if low not in seen_concepts and len(concepts) < max_concepts_total:
            concepts.append(name)
            seen_concepts.add(low)
    relationships = []
    # topic -> key relationships (use label if present)
    for k in (keys_obj.get('keys') or []):
        name = k.get('name') if isinstance(k, dict) else None
        label = k.get('label') if isinstance(k, dict) else 'related to'
        if isinstance(name, str) and name.strip():
            if name in concepts:
                relationships.append({'from': topic, 'to': name, 'label': label or 'related to'})
    # key -> part relationships
    for key, plist in parts_results.items():
        for p in plist:
            if p.get('name') in concepts:
                relationships.append({'from': key, 'to': p.get('name'), 'label': (p.get('label') or 'includes')})

    # Final trim to satisfy validator (<= 30 concepts)
    if len(concepts) > max_concepts_total:
        concepts = concepts[:max_concepts_total]
    allowed = set(concepts)
    allowed_with_topic = allowed.union({topic})
    relationships = [
        r for r in relationships
        if r.get('from') in allowed_with_topic and r.get('to') in allowed_with_topic
    ]
    # Prune keys and parts to allowed concepts
    keys = [k for k in keys if k in allowed]
    parts_results = {
        k: [p for p in (parts_results.get(k, []) or []) if p.get('name') in allowed]
        for k in keys
    }

    # Include keys and parts for sector layout
    spec = {
        'topic': topic,
        'concepts': concepts,
        'relationships': relationships,
        'keys': [{'name': k} for k in keys],
        'key_parts': {k: parts_results.get(k, []) for k in keys}
    }
    return spec


def generate_concept_map_unified(user_prompt: str, language: str) -> dict:
    """One-shot concept map generation with keys, parts, and relationships together."""
    unified_prompt = get_prompt('concept_map_unified', language, 'generation')
    raw = _invoke_llm_prompt(unified_prompt, {'user_prompt': user_prompt})

    # Use the improved ConceptMapAgent parsing for better error handling
    try:
        from agents.concept_maps.concept_map_agent import ConceptMapAgent
        agent = ConceptMapAgent()
        obj = agent.parse_json_response(raw)
        logger.debug("Used ConceptMapAgent improved parsing for unified generation")
    except Exception as e:  # pylint: disable=broad-except
        logger.warning(
            "ConceptMapAgent parsing failed, falling back to strict parsing: %s", e
        )
        # Fallback to strict parsing if ConceptMapAgent is not available
        try:
            obj = _parse_strict_json(raw)
            logger.debug("Used strict parsing fallback for unified generation")
        except Exception as e2:  # pylint: disable=broad-except
            logger.error("All parsing methods failed for unified generation: %s", e2)
            return {'error': f'Concept map parsing failed: {e2}'}
    # Extract - prioritize concepts from ConceptMapAgent parsing
    topic = (obj.get('topic') or user_prompt).strip()
    concepts_raw = obj.get('concepts') or []
    keys_raw = obj.get('keys') or []
    key_parts_raw = obj.get('key_parts') or {}
    rels_raw = obj.get('relationships') or []

    # First, use concepts if they were successfully extracted
    if concepts_raw and isinstance(concepts_raw, list):
        concepts = []
        seen_all = set()
        for concept in concepts_raw:
            if isinstance(concept, str) and concept.strip():
                name = concept.strip()
                low = name.lower()
                if low not in seen_all and len(concepts) < 30:
                    concepts.append(name)
                    seen_all.add(low)
        allowed = set(concepts)
        logger.debug("Using concepts extracted by ConceptMapAgent: %s", concepts)
    else:
        # Fallback: build concepts from keys and parts (original logic)
        # Normalize keys
        keys = []
        seen_k = set()
        for k in keys_raw:
            name = k.get('name') if isinstance(k, dict) else k
            if isinstance(name, str):
                name = name.strip()
                if name and name.lower() not in seen_k:
                    keys.append(name)
                    seen_k.add(name.lower())
        # Normalize parts
        parts_results = {}
        seen_parts_global = set()
        for k in keys:
            plist = key_parts_raw.get(k) or []
            out = []
            seen_local = set()
            for p in plist:
                name = p.get('name') if isinstance(k, dict) else p
                if isinstance(name, str):
                    name = name.strip()
                    low = name.lower()
                    if name and low not in seen_local and low not in seen_parts_global:
                        out.append(name)
                        seen_local.add(low)
                        seen_parts_global.add(low)
            parts_results[k] = out
        # Build concepts within cap
        max_concepts_total = 30
        concepts = []
        seen_all = set()
        for name in keys + [p for arr in parts_results.values() for p in arr]:
            low = name.lower()
            if low not in seen_all and len(concepts) < max_concepts_total:
                concepts.append(name)
                seen_all.add(low)
        allowed = set(concepts)
        logger.debug("Built concepts from keys/parts: %s", concepts)
    # Relationships
    relationships = []
    pair_seen = set()

    def add_rel(frm, to, label) -> None:
        if not isinstance(frm, str) or not isinstance(to, str):
            return
        if frm == to:
            return
        if frm not in allowed and frm != topic:
            return
        if to not in allowed and to != topic:
            return
        key = tuple(sorted((frm.lower(), to.lower())))
        if key in pair_seen:
            return
        pair_seen.add(key)
        relationships.append({'from': frm, 'to': to, 'label': (label or 'related to')[:60]})
    # Add mandatory topic->key and key->part
    for k in keys_raw:
        name = k.get('name') if isinstance(k, dict) else None
        label = (k.get('label') if isinstance(k, dict) else 'related to')
        if isinstance(name, str) and name.strip() and name in allowed:
            add_rel(topic, name, label)
    for key, plist in parts_results.items():
        for p in plist:
            add_rel(key, p, 'includes')
    # Add extra from rels_raw (deduped, within allowed)
    for r in rels_raw:
        add_rel(r.get('from'), r.get('to'), r.get('label'))
    return {
        'topic': topic,
        'concepts': list(allowed),
        'relationships': relationships,
        'keys': [{'name': k} for k in keys if k in allowed],
        'key_parts': {
            k: [{'name': p} for p in parts_results.get(k, []) if p in allowed]
            for k in keys if k in allowed
        }
    }


def generate_concept_map_enhanced_30(user_prompt: str, language: str) -> dict:
    """
    Enhanced concept map generation that produces exactly 30 concepts.

    This integrates with existing topic extraction and uses optimized prompts
    to generate exactly 30 concepts + relationships, matching the desired workflow.
    """
    try:
        # Use LLM-based topic extraction instead of hardcoded string manipulation
        central_topic = extract_central_topic_llm(user_prompt, language)

        if isinstance(central_topic, list):
            central_topic = ' '.join(central_topic)

        logger.debug("Using central topic for 30-concept generation: %s", central_topic)

        # Generate exactly 30 concepts using centralized prompts
        # Get appropriate prompt for language
        concept_prompt = get_prompt("concept_30", language, "generation")
        if concept_prompt:
            concept_prompt = concept_prompt.format(central_topic=central_topic)
        else:
            # Fallback if prompt not found
            logger.warning("Concept 30 generation prompt not found in centralized system, using fallback")
            if language == 'zh':
                concept_prompt = f"为主题{central_topic}生成30个相关概念，输出JSON格式"
            else:
                concept_prompt = f"Generate 30 related concepts for topic {central_topic}, output JSON format"

        # Get concepts from LLM
        concepts_response = _invoke_llm_prompt(concept_prompt, {'central_topic': central_topic})

        if not concepts_response:
            raise ValueError("No response from LLM for concept generation")

        # Parse concepts response
        try:
            concepts_data = json.loads(concepts_response.strip())
        except json.JSONDecodeError:
            try:
                from agents.concept_maps.concept_map_agent import ConceptMapAgent
                agent = ConceptMapAgent()
                concepts_data = agent.parse_json_response(concepts_response)
                logger.debug("Used ConceptMapAgent improved parsing for concepts")
            except Exception as e:  # pylint: disable=broad-except
                logger.warning("ConceptMapAgent parsing failed for concepts: %s", e)
                concepts_data = _parse_strict_json(concepts_response)
                logger.debug("Used strict parsing for concepts")

        # Handle both dict and list formats
        if isinstance(concepts_data, dict):
            concepts = concepts_data.get('concepts', [])
        elif isinstance(concepts_data, list):
            concepts = concepts_data
        else:
            concepts = []

        # Ensure exactly 30 concepts
        original_count = len(concepts)
        if len(concepts) != 30:
            if len(concepts) > 30:
                concepts = concepts[:30]  # Take first 30
                logger.debug("Trimmed concepts from %d to 30", original_count)
            else:
                # Pad with generic concepts if less than 30
                while len(concepts) < 30:
                    concepts.append(f"Related aspect {len(concepts) + 1}")
                logger.debug("Padded concepts from %d to 30", original_count)

        if not concepts:
            raise ValueError("No concepts generated")

        # Generate relationships using systematic approach
        if language == 'zh':
            rel_prompt = f"""
现在为主题"{central_topic}"和这30个概念生成关系：

概念列表：
{', '.join(concepts)}

关系生成策略：
1. 主题-概念关系：为每个概念与主题创建有意义的关系
2. 概念间关系：寻找概念之间的逻辑连接
3. 分类关系：同类概念之间的关系
4. 因果关系：存在因果链的概念
5. 依赖关系：有依赖性的概念

输出JSON格式：
{{
  "relationships": [
    {{"from": "{central_topic}", "to": "概念1", "label": "包含"}},
    {{"from": "概念A", "to": "概念B", "label": "导致"}},
    ...
  ]
}}

要求：
- 每个概念至少与主题有一个关系
- 总共生成40-60个关系
- 关系标签简洁（1-3个字）
- 关系逻辑合理
- 避免重复关系
"""
        else:
            rel_prompt = f"""
Generate relationships for topic "{central_topic}" and these 30 concepts:

Concepts:
{', '.join(concepts)}

Relationship Strategy:
1. Topic-Concept relationships: Create meaningful connections between each concept and the topic
2. Inter-concept relationships: Find logical connections between concepts
3. Category relationships: Connect concepts within same categories
4. Causal relationships: Identify cause-effect chains between concepts
5. Dependency relationships: Connect concepts with dependencies

Output JSON format:
{{
  "relationships": [
    {{"from": "{central_topic}", "to": "concept1", "label": "contains"}},
    {{"from": "conceptA", "to": "conceptB", "label": "causes"}},
    ...
  ]
}}

Requirements:
- Each concept should have at least one relationship with the topic
- Generate 40-60 total relationships
- Relationship labels should be concise (1-3 words)
- Relationships should be logical
- Avoid duplicate relationships
"""

        # Get relationships from LLM
        relationships_response = _invoke_llm_prompt(rel_prompt, {'central_topic': central_topic, 'concepts': concepts})

        if not relationships_response:
            raise ValueError("No response from LLM for relationship generation")

        # Parse relationships response
        try:
            rel_data = json.loads(relationships_response.strip())
        except json.JSONDecodeError:
            try:
                from agents.concept_maps.concept_map_agent import ConceptMapAgent
                agent = ConceptMapAgent()
                rel_data = agent.parse_json_response(relationships_response)
                logger.debug("Used ConceptMapAgent improved parsing for relationships")
            except Exception as e:  # pylint: disable=broad-except
                logger.warning(
                    "ConceptMapAgent parsing failed for relationships: %s", e
                )
                rel_data = _parse_strict_json(relationships_response)
                logger.debug("Used strict parsing for relationships")

        relationships = rel_data.get('relationships', [])

        if not relationships:
            raise ValueError("No relationships generated")

        # Build the final specification
        spec = {
            'topic': central_topic,
            'concepts': concepts,  # Exactly 30 concepts
            'relationships': relationships,
            '_method': 'enhanced_30',  # Mark for identification
            '_concept_count': len(concepts),
            '_stage_info': {
                'original_prompt': user_prompt,
                'extracted_topic': central_topic,
                'concept_count': len(concepts),
                'relationship_count': len(relationships)
            }
        }

        logger.debug(
            "Enhanced 30-concept generation completed successfully with %d concepts "
            "and %d relationships", len(concepts), len(relationships)
        )
        return spec

    except Exception as e:  # pylint: disable=broad-except
        logger.error("Enhanced 30-concept generation failed: %s", e)
        logger.error("Stack trace: %s", traceback.format_exc())

        # Fallback to original method
        return generate_concept_map_unified(user_prompt, language)


def generate_concept_map_robust(user_prompt: str, language: str, method: str = 'auto') -> dict:
    """Robust concept map generation with multiple approaches.

    Args:
        user_prompt: User's input prompt
        language: Language for processing
        method: Generation method ('auto', 'unified', 'two_stage', 'network_first', 'three_stage')

    Returns:
        dict: Concept map specification
    """
    # NEW: Try the enhanced concept-first method (RECOMMENDED)
    if method in ['auto', 'three_stage']:
        try:
            # Use existing topic extraction + enhanced 30-concept generation
            return generate_concept_map_enhanced_30(user_prompt, language)
        except Exception as e:  # pylint: disable=broad-except
            logger.warning("Enhanced 30-concept generation failed: %s", e)
            # Try with fewer concepts as fallback
            try:
                logger.debug(
                    "Attempting fallback with simplified two-stage generation..."
                )
                from agents.concept_maps.concept_map_agent import ConceptMapAgent
                agent = ConceptMapAgent()
                result = agent.generate_simplified_two_stage(
                    user_prompt, llm_generation, language
                )
                if isinstance(result, dict) and result.get('success'):
                    return result.get('spec', {})
                logger.warning(
                    "Simplified two-stage generation failed: %s", result.get('error')
                )
                raise ValueError(
                    "All concept map generation methods failed"
                ) from e
            except Exception as fallback_error:  # pylint: disable=broad-except
                logger.warning(
                    "Simplified two-stage fallback also failed: %s", fallback_error
                )

    # If method is specified, try that first
    if method == 'network_first':
        logger.warning("Network-first method is not available, falling back to enhanced 30-concept generation")

    # With increased token limits, the enhanced method should work
    # If it fails, there's a deeper issue that needs investigation
    logger.error("Enhanced concept map generation failed despite increased token limits")
    logger.error("This indicates a configuration or API issue that needs investigation")
    raise ValueError("All concept map generation methods failed - check LLM configuration")
