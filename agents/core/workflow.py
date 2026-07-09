"""
Main workflow orchestration.

This module provides the main workflow functions for diagram generation,
including agent selection and specification generation.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from contextlib import nullcontext
from typing import TYPE_CHECKING

from agents.concept_maps.concept_map_agent import ConceptMapAgent
from agents.mind_maps.mind_map_agent import build_mind_map_branch_expand_user_message
from agents.core.diagram_detection import _detect_diagram_type_from_prompt
from agents.core.generate_events import (
    EventEmitter,
    GenerateGraphEvent,
    emit_progress,
    phase_emitter_from_event_emitter,
)
from agents.core.agent_result import artifact_metadata, artifact_to_spec_or_error, normalize_agent_generation_result
from agents.core.agent_routing import AgentGenerateRoute, resolve_agent_generate_route
from agents.core.prompt_requirements import (
    AgentRequirementParams,
    build_generation_user_message,
    extract_prompt_requirements,
    map_to_agent_params,
    merge_agent_params,
)
from agents.core.learning_sheet import (
    _clean_prompt_for_learning_sheet,
    _detect_learning_sheet_from_prompt,
)
from agents.core.utils import create_error_response, validate_inputs
from agents.mind_maps.mind_map_agent import MindMapAgent
from agents.thinking_maps.brace_map_agent import BraceMapAgent
from agents.thinking_maps.bridge_map_agent import BridgeMapAgent
from agents.thinking_maps.bubble_map_agent import BubbleMapAgent
from agents.thinking_maps.circle_map_agent import CircleMapAgent
from agents.thinking_maps.double_bubble_map_agent import DoubleBubbleMapAgent
from agents.thinking_maps.flow_map_agent import FlowMapAgent
from agents.thinking_maps.multi_flow_map_agent import MultiFlowMapAgent
from agents.thinking_maps.tree_map_agent import TreeMapAgent
from services.knowledge.package_rag_scope import resolve_diagram_rag_scope
from services.llm.rag_context_state import suppress_implicit_rag
from services.llm.rag_service import RAGService
from services.utils.error_types import LLM_PIPELINE_ERRORS
from utils.db.session_open import user_rls_session
from utils.prompt_locale import is_chinese_prompt_shell_language

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Max length for concept names in relationship-only requests (avoid prompt bloat)
CONCEPT_MAX_LENGTH = 100


PhaseEmitter = Callable[[str], Awaitable[None]]


def _check_cancelled(cancel_event: asyncio.Event | None) -> None:
    """Raise when the client has disconnected and generation should stop."""
    if cancel_event is not None and cancel_event.is_set():
        raise asyncio.CancelledError("Diagram generation cancelled")


async def _emit_typed(event_emit: EventEmitter | None, event: GenerateGraphEvent) -> None:
    if event_emit is not None:
        await event_emit(event)


def _instantiate_agent(diagram_type: str, model: str):
    """Create the specialized agent for a diagram type."""
    if diagram_type == "bubble_map":
        return BubbleMapAgent(model=model)
    if diagram_type == "bridge_map":
        logger.debug("Bridge map agent selection started")
        agent = BridgeMapAgent(model=model)
        logger.debug("BridgeMapAgent imported and instantiated successfully")
        return agent
    if diagram_type == "tree_map":
        return TreeMapAgent(model=model)
    if diagram_type == "circle_map":
        return CircleMapAgent(model=model)
    if diagram_type == "double_bubble_map":
        return DoubleBubbleMapAgent(model=model)
    if diagram_type == "flow_map":
        return FlowMapAgent(model=model)
    if diagram_type == "brace_map":
        return BraceMapAgent(model=model)
    if diagram_type == "multi_flow_map":
        return MultiFlowMapAgent(model=model)
    if diagram_type in ("mind_map", "mindmap"):
        return MindMapAgent(model=model)
    if diagram_type == "concept_map":
        return ConceptMapAgent(model=model)
    return BubbleMapAgent(model=model)


async def _invoke_agent_route(
    diagram_type: str,
    model: str,
    user_prompt: str,
    language: str,
    route: AgentGenerateRoute,
) -> dict:
    """Dispatch generate_graph using the resolved route."""
    kwargs = route.kwargs
    mode = route.mode

    if mode in ("bridge_pairs", "bridge_dimension_only"):
        bridge_agent = BridgeMapAgent(model=model)
        return await bridge_agent.generate_graph(user_prompt, language, **kwargs)

    if mode == "tree_brace_fixed_dimension":
        if diagram_type == "tree_map":
            tree_agent = TreeMapAgent(model=model)
            return await tree_agent.generate_graph(user_prompt, language, **kwargs)
        brace_agent = BraceMapAgent(model=model)
        return await brace_agent.generate_graph(user_prompt, language, **kwargs)

    if mode == "dimension_preference":
        if diagram_type == "brace_map":
            brace_agent = BraceMapAgent(model=model)
            return await brace_agent.generate_graph(user_prompt, language, **kwargs)
        if diagram_type == "tree_map":
            tree_agent = TreeMapAgent(model=model)
            return await tree_agent.generate_graph(user_prompt, language, **kwargs)
        bridge_agent = BridgeMapAgent(model=model)
        return await bridge_agent.generate_graph(user_prompt, language, **kwargs)

    agent = _instantiate_agent(diagram_type, model)
    return await agent.generate_graph(user_prompt, language, **kwargs)


async def _generate_spec_with_agent(
    user_prompt: str,
    diagram_type: str,
    language: str,
    dimension_preference: str | None = None,
    model: str = "qwen",
    # Token tracking parameters
    user_id=None,
    organization_id=None,
    request_type="diagram_generation",
    endpoint_path=None,
    # Bridge map specific
    existing_analogies=None,
    fixed_dimension=None,
    # Tree map and brace map: dimension-only mode (user has dimension but no topic)
    dimension_only_mode=None,
    # Prompt understanding layer (stage 2)
    structure_mode: str = "free",
    fixed_nodes: dict | None = None,
    constraints: str = "",
    mind_map_topic: str | None = None,
    expand_branch: str | None = None,
    reference_branches: list | None = None,
    existing_branch_children: list | None = None,
    parent_branch: str | None = None,
    phase_emit: PhaseEmitter | None = None,
) -> dict:
    """
    Generate specification using the appropriate specialized agent.

    Args:
        user_prompt: User's input prompt
        diagram_type: Type of diagram to generate
        language: Language for processing
        dimension_preference: Optional dimension preference for brace maps
            (decomposition), tree maps (classification), and bridge maps
            (analogy pattern)
        model: LLM model to use ('qwen', 'deepseek', 'kimi'). Passed to agent for LLM client selection.
        existing_analogies: For bridge map auto-complete - existing pairs to preserve [{left, right}, ...]
        fixed_dimension: For bridge map auto-complete - user-specified relationship pattern that should NOT be changed

    Returns:
        dict: Normalized agent artifact (spec and optional warning metadata)
    """
    try:
        logger.debug("Calling %s agent", diagram_type)
        logger.debug("User prompt: %s", user_prompt)
        logger.debug("Language: %s", language)

        route = resolve_agent_generate_route(
            diagram_type=diagram_type,
            structure_mode=structure_mode,
            fixed_nodes=fixed_nodes,
            constraints=constraints,
            fixed_dimension=fixed_dimension,
            dimension_only_mode=dimension_only_mode,
            dimension_preference=dimension_preference,
            existing_analogies=existing_analogies,
            user_id=user_id,
            organization_id=organization_id,
            request_type=request_type,
            endpoint_path=endpoint_path,
            phase_emit=phase_emit,
        )
        expand_label = (expand_branch or "").strip()
        if expand_label:
            route.kwargs["expand_branch"] = expand_label
            route.kwargs["mind_map_topic"] = (mind_map_topic or "").strip()
            route.kwargs["reference_branches"] = reference_branches or []
            route.kwargs["existing_branch_children"] = existing_branch_children or []
            route.kwargs["parent_branch"] = (parent_branch or "").strip()
        logger.debug("Agent route mode: %s", route.mode)

        result = await _invoke_agent_route(
            diagram_type,
            model,
            user_prompt,
            language,
            route,
        )
        artifact = normalize_agent_generation_result(result)
        logger.debug("Agent artifact keys: %s", list(artifact.keys()))
        return artifact

    except LLM_PIPELINE_ERRORS as e:
        logger.error("Agent instantiation/generation failed for %s: %s", diagram_type, e)
        return {"error": f"Failed to generate {diagram_type}: {str(e)}"}


async def agent_graph_workflow_with_styles(
    user_prompt,
    language="zh",
    forced_diagram_type=None,
    dimension_preference=None,
    model="qwen",
    # Token tracking parameters
    user_id=None,
    organization_id=None,
    request_type="diagram_generation",
    endpoint_path=None,
    # Bridge map specific: existing pairs for auto-complete mode
    existing_analogies=None,
    # Bridge map specific: fixed dimension/relationship that user has already specified
    fixed_dimension=None,
    # Tree map and brace map: dimension-only mode (user has dimension but no topic)
    dimension_only_mode=None,
    # Concept map: relationship-only mode (generate label for link between two concepts)
    concept_map_relationship_only=None,
    concept_a=None,
    concept_b=None,
    concept_map_topic=None,
    link_direction=None,
    # RAG integration: use knowledge space context
    use_rag=False,
    rag_top_k=5,
    # File Center: diagram-linked package scoping for RAG
    diagram_id=None,
    rag_document_ids=None,
    mind_map_topic=None,
    expand_branch=None,
    reference_branches=None,
    existing_branch_children=None,
    parent_branch=None,
    phase_emit: PhaseEmitter | None = None,
    event_emit: EventEmitter | None = None,
    cancel_event: asyncio.Event | None = None,
):
    """
    Simplified agent workflow that directly calls specialized agents.

    Args:
        user_prompt (str): User's input prompt
        language (str): Language for processing ('zh' or 'en')
        forced_diagram_type (str, optional): Force a specific diagram type instead of auto-detection.
                                            Used for auto-complete to preserve current diagram type.
        dimension_preference (str, optional): User-specified dimension for brace \
maps (decomposition) and tree maps (classification).
        model (str): LLM model to use ('qwen', 'deepseek', 'kimi'). Passed through call chain to avoid race conditions.
        existing_analogies (list, optional): For bridge map auto-complete - \
existing pairs to preserve [{left, right}, ...]
        fixed_dimension (str, optional): For bridge map auto-complete - \
user-specified relationship pattern that should NOT be changed
        dimension_only_mode (bool, optional): For tree_map/brace_map \
auto-complete - user has dimension but no topic (generate topic and children)
        use_rag (bool): Whether to use RAG (Knowledge Space) context for enhanced diagram generation
        rag_top_k (int): Number of RAG context chunks to retrieve (default: 5)

    Returns:
        dict: JSON specification with integrated styles for D3.js rendering
    """
    logger.debug("Starting simplified graph workflow")
    workflow_start_time = time.time()
    agent_phase_emit = phase_emitter_from_event_emitter(event_emit) or phase_emit

    # Initialize timing variables
    detection_time = 0.0
    topic_time = 0.0
    generation_time = 0.0

    try:
        # Concept map relationship-only: early return (skip full workflow)
        rel_only = concept_map_relationship_only
        ca = (concept_a or "").strip()[:CONCEPT_MAX_LENGTH] if concept_a else ""
        cb = (concept_b or "").strip()[:CONCEPT_MAX_LENGTH] if concept_b else ""
        if rel_only and ca and cb:
            topic = (concept_map_topic or "").strip()[:CONCEPT_MAX_LENGTH]
            agent = ConceptMapAgent(model=model)
            result = await agent.generate_graph(
                user_prompt,
                language,
                relationship_only=True,
                concept_a=ca,
                concept_b=cb,
                concept_map_topic=topic,
                link_direction=link_direction,
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type or "autocomplete",
                endpoint_path=endpoint_path,
                phase_emit=phase_emit,
            )
            if isinstance(result, dict) and "relationship_label" in result:
                return result
            return {
                "success": False,
                "error": result.get("error", "Failed to generate relationship label"),
            }

        # Validate inputs
        validate_inputs(user_prompt, language)
        _check_cancelled(cancel_event)

        # Use forced diagram type if provided, otherwise detect from prompt
        if forced_diagram_type:
            diagram_type = forced_diagram_type
            detection_result = {
                "diagram_type": diagram_type,
                "clarity": "clear",
                "has_topic": True,
            }
            logger.debug("Using forced diagram type: %s", diagram_type)
        else:
            await _emit_typed(
                event_emit,
                GenerateGraphEvent(event="detecting", model=model),
            )
            # LLM-based diagram type detection for semantic understanding
            detection_start = time.time()
            detection_result = await _detect_diagram_type_from_prompt(
                user_prompt,
                language,
                model,
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path,
                phase_emit=agent_phase_emit,
            )
            detection_time = time.time() - detection_start
            diagram_type = detection_result["diagram_type"]
            logger.info(
                "Diagram type detection completed in %.2fs: %s (clarity: %s)",
                detection_time,
                diagram_type,
                detection_result["clarity"],
            )
            if detection_result["clarity"] == "very_unclear" and not detection_result["has_topic"]:
                logger.warning(
                    "Prompt failed validation during detection: %r — using mind_map",
                    user_prompt[:80],
                )
                diagram_type = "mind_map"
                detection_result["diagram_type"] = "mind_map"

        # Stage 2: extract type-native requirements from raw prompt (before learning sheet / RAG)
        _check_cancelled(cancel_event)
        requirements_start = time.time()
        expand_label = (expand_branch or "").strip()
        is_mind_map_branch_expand = expand_label and diagram_type in ("mind_map", "mindmap")
        if is_mind_map_branch_expand:
            agent_params = merge_agent_params(
                {
                    "fixed_dimension": fixed_dimension,
                    "existing_analogies": existing_analogies,
                    "dimension_only_mode": dimension_only_mode,
                    "dimension_preference": dimension_preference,
                },
                AgentRequirementParams(),
            )
            generation_central = expand_label
            topic_time = 0.0
            logger.info(
                "Mind map branch expand (skipped requirements extraction): topic=%r, expand=%r, refs=%d",
                (mind_map_topic or "").strip()[:80],
                expand_label[:80],
                len(reference_branches or []),
            )
        else:
            parsed = await extract_prompt_requirements(
                user_prompt,
                diagram_type,
                language,
                model,
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path,
                phase_emit=agent_phase_emit,
            )
            agent_params = merge_agent_params(
                {
                    "fixed_dimension": fixed_dimension,
                    "existing_analogies": existing_analogies,
                    "dimension_only_mode": dimension_only_mode,
                    "dimension_preference": dimension_preference,
                },
                map_to_agent_params(diagram_type, parsed),
            )
            generation_central = parsed.central_for_type(diagram_type) or user_prompt.strip()
            topic_time = time.time() - requirements_start
            logger.info(
                "Requirements extraction completed in %.2fs: structure_mode=%s, central=%r",
                topic_time,
                agent_params.structure_mode,
                generation_central[:80] if generation_central else "",
            )
        await emit_progress(
            event_emit,
            topic=generation_central[:80] if generation_central else user_prompt[:80],
            diagram_type=diagram_type,
            model=model,
        )

        effective_fixed_dimension = agent_params.fixed_dimension
        effective_existing_analogies = agent_params.existing_analogies
        effective_dimension_only_mode = agent_params.dimension_only_mode

        # Continue to full spec generation for both free-form and forced diagram type
        # Add learning sheet detection
        is_learning_sheet = _detect_learning_sheet_from_prompt(user_prompt, language)
        logger.debug("Learning sheet detected: %s", is_learning_sheet)

        # Clean the prompt for learning sheets to generate actual content, not meta-content
        generation_prompt = _clean_prompt_for_learning_sheet(user_prompt) if is_learning_sheet else user_prompt
        if is_learning_sheet:
            logger.debug("Using cleaned prompt for generation: '%s'", generation_prompt)

        # RAG Integration: Retrieve relevant context from Knowledge Space if enabled
        rag_context = None
        rag_context_block = ""

        # File Center: scope retrieval to a diagram's linked package when present.
        # Explicit rag_document_ids win; otherwise resolve from the diagram link.
        rag_metadata_filter = None
        package_rag_active = False
        resolved_document_ids = None
        if rag_document_ids:
            resolved_document_ids = [int(doc_id) for doc_id in rag_document_ids]
        elif diagram_id and user_id:
            try:
                async with user_rls_session(int(user_id)) as scope_db:
                    scope = await resolve_diagram_rag_scope(scope_db, int(user_id), str(diagram_id))
                if scope and scope.has_corpus:
                    resolved_document_ids = scope.document_ids
                    logger.info(
                        "[RAG] Package scope for diagram %s: %d completed source(s)",
                        diagram_id,
                        len(resolved_document_ids),
                    )
            except LLM_PIPELINE_ERRORS as e:
                logger.warning("[RAG] Failed to resolve package scope for diagram %s: %s", diagram_id, e)

        if resolved_document_ids:
            rag_metadata_filter = {"document_id": resolved_document_ids}
            package_rag_active = True
            use_rag = True  # auto-enable when a diagram's package has a corpus

        if use_rag and user_id:
            try:
                rag_service = RAGService()
                async with user_rls_session(int(user_id)) as db:
                    if await rag_service.has_knowledge_base(db, user_id):
                        logger.info(
                            "[RAG] Retrieving context for user %d, top_k=%d, scoped=%s",
                            user_id,
                            rag_top_k,
                            package_rag_active,
                        )

                        rag_context_chunks = await rag_service.retrieve_context(
                            db=db,
                            user_id=user_id,
                            query=generation_prompt,
                            method="hybrid",
                            top_k=rag_top_k,
                            score_threshold=0.3,
                            source="diagram_generation",
                            source_context={
                                "stage": "generation",
                                "diagram_type": diagram_type,
                            },
                            metadata_filter=rag_metadata_filter,
                        )

                        if rag_context_chunks:
                            rag_context = (
                                "\n\n".join(
                                    [f"[知识库参考 {i + 1}]: {chunk}" for i, chunk in enumerate(rag_context_chunks)]
                                )
                                if is_chinese_prompt_shell_language(language)
                                else "\n\n".join(
                                    [
                                        f"[Knowledge Base Reference {i + 1}]: {chunk}"
                                        for i, chunk in enumerate(rag_context_chunks)
                                    ]
                                )
                            )

                            logger.info(
                                "[RAG] Retrieved %d context chunks for diagram generation",
                                len(rag_context_chunks),
                            )
                        else:
                            logger.debug(
                                "[RAG] No relevant context found for query: %s...",
                                generation_prompt[:50],
                            )
                    else:
                        logger.debug("[RAG] User %d has no knowledge base, skipping RAG", user_id)
            except LLM_PIPELINE_ERRORS as e:
                logger.warning("[RAG] Failed to retrieve context: %s", e, exc_info=True)

        if rag_context:
            if is_chinese_prompt_shell_language(language):
                rag_context_block = f"""相关背景知识（来自用户的知识库）：
{rag_context}

请基于以上背景知识生成更准确、更详细的图表。"""
            else:
                rag_context_block = f"""Relevant Context (from user's knowledge base):
{rag_context}

Please generate a more accurate and detailed diagram based on the above context."""
            logger.debug("[RAG] Prepared %d characters of context block", len(rag_context))

        if is_mind_map_branch_expand:
            agent_user_message = build_mind_map_branch_expand_user_message(
                expand_branch=expand_label,
                mind_map_topic=(mind_map_topic or "").strip(),
                reference_branches=list(reference_branches or []),
                existing_branch_children=list(existing_branch_children or []),
                parent_branch=(parent_branch or "").strip(),
                language=language,
            )
            if rag_context_block.strip():
                agent_user_message = f"{agent_user_message}\n\n{rag_context_block.strip()}"
        else:
            agent_user_message = build_generation_user_message(
                generation_central,
                agent_params,
                language,
                rag_context_block,
            )

        # Generate specification using the appropriate agent.
        # When package-scoped RAG is active, suppress implicit whole-library RAG
        # inside agent LLM calls so retrieval stays scoped to the package only.
        generation_start = time.time()
        _check_cancelled(cancel_event)
        rag_guard = suppress_implicit_rag() if package_rag_active else nullcontext()
        with rag_guard:
            agent_artifact = await _generate_spec_with_agent(
                agent_user_message,
                diagram_type,
                language,
                dimension_preference=dimension_preference if dimension_preference else None,
                model=model,
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path,
                existing_analogies=effective_existing_analogies,
                fixed_dimension=effective_fixed_dimension,
                dimension_only_mode=effective_dimension_only_mode,
                structure_mode=agent_params.structure_mode,
                fixed_nodes=agent_params.fixed_nodes,
                constraints=agent_params.constraints,
                mind_map_topic=mind_map_topic,
                expand_branch=expand_branch,
                reference_branches=reference_branches,
                existing_branch_children=existing_branch_children,
                parent_branch=parent_branch,
                phase_emit=agent_phase_emit,
            )
        generation_time = time.time() - generation_start
        logger.info(
            "Diagram generation completed in %.2fs for %s",
            generation_time,
            diagram_type,
        )

        agent_meta = artifact_metadata(agent_artifact)
        spec = artifact_to_spec_or_error(agent_artifact)

        if not spec or (isinstance(spec, dict) and spec.get("error")):
            logger.error("Failed to generate spec for %s", diagram_type)
            failure: dict = {
                "success": False,
                "spec": spec
                or create_error_response(
                    "Failed to generate specification",
                    "generation",
                    {"diagram_type": diagram_type},
                ),
                "diagram_type": diagram_type,
                "topics": [],
                "style_preferences": {},
                "language": language,
                "is_learning_sheet": is_learning_sheet,
                "hidden_node_percentage": 0,
            }
            if isinstance(spec, dict):
                if spec.get("error_type"):
                    failure["error_type"] = spec["error_type"]
                if spec.get("show_guidance") is not None:
                    failure["show_guidance"] = spec["show_guidance"]
                if spec.get("error"):
                    failure["error"] = spec["error"]
            return failure

        # Calculate hidden percentage for learning sheets (20%)
        hidden_percentage = 0.2 if is_learning_sheet else 0

        # Add learning sheet metadata to spec object so renderers can access it
        if isinstance(spec, dict):
            spec["is_learning_sheet"] = is_learning_sheet
            spec["hidden_node_percentage"] = hidden_percentage
            logger.debug(
                "Added learning sheet metadata to spec: is_learning_sheet=%s, hidden_percentage=%s",
                is_learning_sheet,
                hidden_percentage,
            )

        # Add metadata to the result
        result = {
            "success": True,
            "spec": spec,
            "diagram_type": diagram_type,
            "topics": [generation_central] if generation_central else [],
            "structure_mode": agent_params.structure_mode,
            "style_preferences": {},
            "language": language,
            "is_learning_sheet": is_learning_sheet,
            "hidden_node_percentage": hidden_percentage,
            **agent_meta,
        }

        total_time = time.time() - workflow_start_time
        logger.info(
            "Simplified workflow completed successfully in %.2fs "
            "(breakdown: detection=%.2fs, topic=%.2fs, generation=%.2fs), "
            "learning sheet: %s",
            total_time,
            detection_time,
            topic_time,
            generation_time,
            is_learning_sheet,
        )
        return result

    except ValueError as e:
        logger.error("Input validation failed: %s", e)
        return {
            "success": False,
            "spec": create_error_response(f"Invalid input: {str(e)}", "validation", {"language": language}),
            "diagram_type": "bubble_map",
            "topics": [],
            "style_preferences": {},
            "language": language,
        }
    except LLM_PIPELINE_ERRORS as e:
        logger.error("Simplified workflow failed: %s", e)
        return {
            "success": False,
            "spec": create_error_response(f"Generation failed: {str(e)}", "workflow", {"language": language}),
            "diagram_type": "bubble_map",
            "topics": [],
            "style_preferences": {},
            "language": language,
        }
