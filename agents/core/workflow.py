"""
Main workflow orchestration.

This module provides the main workflow functions for diagram generation,
including agent selection and specification generation.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import logging
import time
from typing import TYPE_CHECKING, cast

from prompts import get_prompt
from services.llm import llm_service

from agents.concept_maps.concept_map_agent import ConceptMapAgent
from agents.mind_maps.mind_map_agent import MindMapAgent
from agents.thinking_maps.brace_map_agent import BraceMapAgent
from agents.thinking_maps.bridge_map_agent import BridgeMapAgent
from agents.thinking_maps.bubble_map_agent import BubbleMapAgent
from agents.thinking_maps.circle_map_agent import CircleMapAgent
from agents.thinking_maps.double_bubble_map_agent import DoubleBubbleMapAgent
from agents.thinking_maps.flow_map_agent import FlowMapAgent
from agents.thinking_maps.multi_flow_map_agent import MultiFlowMapAgent
from agents.thinking_maps.tree_map_agent import TreeMapAgent
from agents.thinking_tools.factor_analysis_agent import FactorAnalysisAgent
from agents.thinking_tools.three_position_analysis_agent import ThreePositionAnalysisAgent
from agents.thinking_tools.perspective_analysis_agent import PerspectiveAnalysisAgent
from agents.thinking_tools.goal_analysis_agent import GoalAnalysisAgent
from agents.thinking_tools.possibility_analysis_agent import PossibilityAnalysisAgent
from agents.thinking_tools.result_analysis_agent import ResultAnalysisAgent
from agents.thinking_tools.five_w_one_h_agent import FiveWOneHAgent
from agents.thinking_tools.whwm_analysis_agent import WHWMAnalysisAgent
from agents.thinking_tools.four_quadrant_agent import FourQuadrantAgent
from agents.core.diagram_detection import _detect_diagram_type_from_prompt
from agents.core.learning_sheet import _clean_prompt_for_learning_sheet, _detect_learning_sheet_from_prompt
from agents.core.utils import create_error_response, validate_inputs
from services.llm.rag_service import RAGService
from config.database import SessionLocal

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


async def _generate_spec_with_agent(
    user_prompt: str,
    diagram_type: str,
    language: str,
    dimension_preference: str | None = None,
    model: str = 'qwen',
    # Token tracking parameters
    user_id=None,
    organization_id=None,
    request_type='diagram_generation',
    endpoint_path=None,
    # Bridge map specific
    existing_analogies=None,
    fixed_dimension=None,
    # Tree map and brace map: dimension-only mode (user has dimension but no topic)
    dimension_only_mode=None
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
        dict: Generated specification
    """
    try:
        # Import and instantiate the appropriate agent with model
        if diagram_type == 'bubble_map':
            agent = BubbleMapAgent(model=model)
        elif diagram_type == 'bridge_map':
            logger.debug("Bridge map agent selection started")
            agent = BridgeMapAgent(model=model)
            logger.debug("BridgeMapAgent imported and instantiated successfully")
        elif diagram_type == 'tree_map':
            agent = TreeMapAgent(model=model)
        elif diagram_type == 'circle_map':
            agent = CircleMapAgent(model=model)
        elif diagram_type == 'double_bubble_map':
            agent = DoubleBubbleMapAgent(model=model)
        elif diagram_type == 'flow_map':
            agent = FlowMapAgent(model=model)
        elif diagram_type == 'brace_map':
            agent = BraceMapAgent(model=model)
        elif diagram_type == 'multi_flow_map':
            agent = MultiFlowMapAgent(model=model)
        elif diagram_type == 'mind_map' or diagram_type == 'mindmap':
            agent = MindMapAgent(model=model)
        elif diagram_type == 'concept_map':
            agent = ConceptMapAgent(model=model)
        # Thinking Tools
        elif diagram_type == 'factor_analysis':
            agent = FactorAnalysisAgent()
        elif diagram_type == 'three_position_analysis':
            agent = ThreePositionAnalysisAgent()
        elif diagram_type == 'perspective_analysis':
            agent = PerspectiveAnalysisAgent()
        elif diagram_type == 'goal_analysis':
            agent = GoalAnalysisAgent()
        elif diagram_type == 'possibility_analysis':
            agent = PossibilityAnalysisAgent()
        elif diagram_type == 'result_analysis':
            agent = ResultAnalysisAgent()
        elif diagram_type == 'five_w_one_h':
            agent = FiveWOneHAgent()
        elif diagram_type == 'whwm_analysis':
            agent = WHWMAnalysisAgent()
        elif diagram_type == 'four_quadrant':
            agent = FourQuadrantAgent()
        else:
            # Fallback to bubble map
            agent = BubbleMapAgent(model=model)

        # Generate using the agent
        logger.debug("Calling %s agent", diagram_type)
        logger.debug("User prompt: %s", user_prompt)
        logger.debug("Language: %s", language)

        # Bridge map special handling - Three template system:
        # Mode 1: Only pairs provided → identify relationship
        # Mode 2: Pairs + relationship provided → keep as-is
        # Mode 3: Only relationship provided → generate pairs
        if diagram_type == 'bridge_map' and existing_analogies:
            # Mode 1 or 2: Has existing pairs
            if fixed_dimension:
                logger.debug(
                    "Bridge map Mode 2: Pairs + Relationship - preserving %d pairs "
                    "with FIXED dimension '%s'", len(existing_analogies), fixed_dimension
                )
            else:
                logger.debug(
                    "Bridge map Mode 1: Only pairs - will identify relationship "
                    "from %d pairs", len(existing_analogies)
                )
            bridge_kwargs = {
                'user_id': user_id,
                'organization_id': organization_id,
                'request_type': request_type,
                'endpoint_path': endpoint_path,
                'existing_analogies': existing_analogies,
                'fixed_dimension': fixed_dimension
            }
            if dimension_preference:
                bridge_kwargs['dimension_preference'] = dimension_preference
            result = await agent.generate_graph(user_prompt, language, **bridge_kwargs)
        # Bridge map Mode 3: Relationship-only mode (no pairs, but has fixed dimension)
        elif diagram_type == 'bridge_map' and fixed_dimension and not existing_analogies:
            logger.debug(
                "Bridge map Mode 3: Relationship-only - generating pairs for '%s'",
                fixed_dimension
            )
            bridge_kwargs = {
                'user_id': user_id,
                'organization_id': organization_id,
                'request_type': request_type,
                'endpoint_path': endpoint_path,
                'existing_analogies': None,
                'fixed_dimension': fixed_dimension
            }
            if dimension_preference:
                bridge_kwargs['dimension_preference'] = dimension_preference
            result = await agent.generate_graph(user_prompt, language, **bridge_kwargs)
        # Tree map and brace map: Three-scenario system (similar to bridge_map)
        # Scenario 1: Topic only → handled by standard generation below
        # Scenario 2: Topic + dimension → fixed_dimension mode (topic exists)
        # Scenario 3: Dimension only (no topic) → dimension_only_mode
        elif (diagram_type == 'tree_map' or diagram_type == 'brace_map') and fixed_dimension:
            # At this point, agent is definitely TreeMapAgent or BraceMapAgent
            # Both accept dimension_preference and fixed_dimension parameters
            # Use explicit type annotation to help Pylint understand
            if dimension_only_mode:
                # Scenario 3: Dimension-only mode - user has dimension but no topic
                logger.debug(
                    "%s dimension-only mode: generating topic and children for "
                    "dimension '%s'", diagram_type, fixed_dimension
                )
                if diagram_type == 'tree_map':
                    typed_agent = cast(TreeMapAgent, agent)
                else:
                    typed_agent = cast(BraceMapAgent, agent)
                tree_brace_kwargs = {
                    'dimension_preference': fixed_dimension,
                    'user_id': user_id,
                    'organization_id': organization_id,
                    'request_type': request_type,
                    'endpoint_path': endpoint_path,
                    'fixed_dimension': fixed_dimension,
                    'dimension_only_mode': True
                }
                result = await typed_agent.generate_graph(
                    user_prompt, language, **tree_brace_kwargs
                )
            else:
                # Scenario 2: Topic + dimension mode
                logger.debug(
                    "%s auto-complete mode with FIXED dimension '%s' (topic exists)",
                    diagram_type, fixed_dimension
                )
                if diagram_type == 'tree_map':
                    typed_agent = cast(TreeMapAgent, agent)
                else:
                    typed_agent = cast(BraceMapAgent, agent)
                tree_brace_kwargs = {
                    'dimension_preference': fixed_dimension,
                    'user_id': user_id,
                    'organization_id': organization_id,
                    'request_type': request_type,
                    'endpoint_path': endpoint_path,
                    'fixed_dimension': fixed_dimension
                }
                result = await typed_agent.generate_graph(
                    user_prompt, language, **tree_brace_kwargs
                )
        # For brace maps, tree maps, and bridge maps (without fixed dimension), pass dimension_preference if available
        elif (diagram_type == 'brace_map' or diagram_type == 'tree_map' or
              diagram_type == 'bridge_map') and dimension_preference:
            # At this point, agent is TreeMapAgent, BraceMapAgent, or BridgeMapAgent
            # All accept dimension_preference parameter
            # Use explicit type annotation to help Pylint
            if diagram_type == 'brace_map':
                typed_agent = cast(BraceMapAgent, agent)
                logger.debug(
                    "Passing decomposition dimension preference to brace map agent: %s",
                    dimension_preference
                )
            elif diagram_type == 'tree_map':
                typed_agent = cast(TreeMapAgent, agent)
                logger.debug(
                    "Passing classification dimension preference to tree map agent: %s",
                    dimension_preference
                )
            else:  # bridge_map
                typed_agent = cast(BridgeMapAgent, agent)
                logger.debug(
                    "Passing analogy relationship pattern preference to bridge map agent: %s",
                    dimension_preference
                )
            tree_brace_kwargs = {
                'dimension_preference': dimension_preference,
                'user_id': user_id,
                'organization_id': organization_id,
                'request_type': request_type,
                'endpoint_path': endpoint_path
            }
            result = await typed_agent.generate_graph(user_prompt, language, **tree_brace_kwargs)
        else:
            # For agents that don't support dimension_preference or other special parameters
            basic_kwargs = {
                'user_id': user_id,
                'organization_id': organization_id,
                'request_type': request_type,
                'endpoint_path': endpoint_path
            }
            result = await agent.generate_graph(user_prompt, language, **basic_kwargs)

        logger.debug("Agent result type: %s", type(result))
        result_keys = list(result.keys()) if isinstance(result, dict) else 'Not a dict'
        logger.debug("Agent result keys: %s", result_keys)

        # Extract spec from agent result if wrapped
        if isinstance(result, dict):
            if 'spec' in result:
                logger.debug("Result contains 'spec' key, returning spec")
                return result['spec']
            elif 'error' not in result:
                logger.debug("Result contains no error, returning as-is")
                return result
            else:
                logger.error("Result contains error: %s", result.get('error'))

        logger.debug("Returning raw result")
        return result

    except Exception as e:  # pylint: disable=broad-except
        logger.error("Agent instantiation/generation failed for %s: %s", diagram_type, e)
        return {'error': f'Failed to generate {diagram_type}: {str(e)}'}


async def agent_graph_workflow_with_styles(
    user_prompt,
    language='zh',
    forced_diagram_type=None,
    dimension_preference=None,
    model='qwen',
    # Token tracking parameters
    user_id=None,
    organization_id=None,
    request_type='diagram_generation',
    endpoint_path=None,
    # Bridge map specific: existing pairs for auto-complete mode
    existing_analogies=None,
    # Bridge map specific: fixed dimension/relationship that user has already specified
    fixed_dimension=None,
    # Tree map and brace map: dimension-only mode (user has dimension but no topic)
    dimension_only_mode=None,
    # RAG integration: use knowledge space context
    use_rag=False,
    rag_top_k=5
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

    # Initialize timing variables
    detection_time = 0.0
    topic_time = 0.0
    generation_time = 0.0

    try:
        # Validate inputs
        validate_inputs(user_prompt, language)

        # Use forced diagram type if provided, otherwise detect from prompt
        if forced_diagram_type:
            diagram_type = forced_diagram_type
            detection_result = {'diagram_type': diagram_type, 'clarity': 'clear', 'has_topic': True}
            logger.debug("Using forced diagram type: %s", diagram_type)
        else:
            # LLM-based diagram type detection for semantic understanding
            detection_start = time.time()
            detection_result = await _detect_diagram_type_from_prompt(
                user_prompt,
                language,
                model,
                # Token tracking parameters
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path
            )
            detection_time = time.time() - detection_start
            diagram_type = detection_result['diagram_type']
            logger.info(
                "Diagram type detection completed in %.2fs: %s (clarity: %s)",
                detection_time, diagram_type, detection_result['clarity']
            )

            # Check if prompt is too complex/unclear and should show guidance modal
            if detection_result['clarity'] == 'very_unclear' and not detection_result['has_topic']:
                logger.warning("Prompt is too complex or unclear: '%s'", user_prompt)
                return {
                    'success': False,
                    'error_type': 'prompt_too_complex',
                    'error': 'Unable to understand the request',
                    'spec': create_error_response(
                        'Prompt is too complex or unclear',
                        'prompt_too_complex',
                        {'user_prompt': user_prompt}
                    ),
                    'diagram_type': 'mind_map',
                    'topics': [],
                    'style_preferences': {},
                    'language': language,
                    'show_guidance': True
                }

        # Extract main topic from prompt using LLM (only if not forced diagram type)
        if not forced_diagram_type:
            # Prompt-based generation: just extract topic, let frontend use default template

            # RAG Integration: Retrieve relevant context for topic extraction if enabled
            rag_context_for_topic = None
            if use_rag and user_id:
                try:
                    rag_service = RAGService()
                    db = SessionLocal()
                    try:
                        if rag_service.has_knowledge_base(db, user_id):
                            rag_context_chunks = rag_service.retrieve_context(
                                db=db,
                                user_id=user_id,
                                query=user_prompt,
                                method='hybrid',
                                top_k=rag_top_k,
                                score_threshold=0.3,
                                source='diagram_generation',
                                source_context={
                                    'stage': 'topic_extraction',
                                    'diagram_type': (
                                        diagram_type if 'diagram_type' in locals() else None
                                    )
                                }
                            )

                            if rag_context_chunks:
                                rag_context_for_topic = "\n\n".join([
                                    f"[知识库参考 {i+1}]: {chunk}"
                                    for i, chunk in enumerate(rag_context_chunks)
                                ]) if language == 'zh' else "\n\n".join([
                                    f"[Knowledge Base Reference {i+1}]: {chunk}"
                                    for i, chunk in enumerate(rag_context_chunks)
                                ])
                                logger.debug(
                                    "[RAG] Retrieved %d context chunks for topic extraction",
                                    len(rag_context_chunks)
                                )
                    finally:
                        db.close()
                except Exception as e:  # pylint: disable=broad-except
                    logger.debug(
                        "[RAG] Failed to retrieve context for topic extraction: %s", e
                    )

            # Use centralized topic extraction prompt
            topic_extraction_prompt = get_prompt("topic_extraction", language, "generation")

            # Enhance prompt with RAG context if available
            if rag_context_for_topic:
                if language == 'zh':
                    enhanced_user_prompt = f"{user_prompt}\n\n相关背景知识：\n{rag_context_for_topic}"
                else:
                    enhanced_user_prompt = f"{user_prompt}\n\nRelevant Context:\n{rag_context_for_topic}"
            else:
                enhanced_user_prompt = user_prompt

            topic_extraction_prompt = topic_extraction_prompt.format(user_prompt=enhanced_user_prompt)

            topic_start = time.time()
            main_topic = await llm_service.chat(
                prompt=topic_extraction_prompt,
                model=model,
                max_tokens=50,
                temperature=0.1,  # Lower temperature for more deterministic extraction
                # Token tracking parameters
                user_id=user_id,
                organization_id=organization_id,
                request_type=request_type,
                endpoint_path=endpoint_path
            )
            topic_time = time.time() - topic_start
            main_topic = main_topic.strip().strip('"\'')
            logger.info("Topic extraction completed in %.2fs: '%s'", topic_time, main_topic)

            # Return just the topic and diagram type - frontend will load default template
            total_time = time.time() - workflow_start_time
            logger.info(
                "Prompt-based workflow completed in %.2fs (detection=%.2fs, topic=%.2fs)",
                total_time, detection_time, topic_time
            )
            return {
                'success': True,
                'diagram_type': diagram_type,
                'extracted_topic': main_topic,  # Just the topic, no spec
                'language': language,
                'use_default_template': True  # Signal to frontend to use default template + trigger auto-complete
            }

        # For forced diagram type (manual generation), use full agent workflow
        # Add learning sheet detection
        is_learning_sheet = _detect_learning_sheet_from_prompt(user_prompt, language)
        logger.debug("Learning sheet detected: %s", is_learning_sheet)

        # Clean the prompt for learning sheets to generate actual content, not meta-content
        generation_prompt = _clean_prompt_for_learning_sheet(user_prompt) if is_learning_sheet else user_prompt
        if is_learning_sheet:
            logger.debug("Using cleaned prompt for generation: '%s'", generation_prompt)

        # RAG Integration: Retrieve relevant context from Knowledge Space if enabled
        rag_context = None
        if use_rag and user_id:
            try:
                rag_service = RAGService()
                db = SessionLocal()
                try:
                    # Check if user has knowledge base
                    if rag_service.has_knowledge_base(db, user_id):
                        logger.info(
                            "[RAG] Retrieving context for user %d, top_k=%d",
                            user_id, rag_top_k
                        )

                        # Retrieve relevant context using hybrid search
                        rag_context_chunks = rag_service.retrieve_context(
                            db=db,
                            user_id=user_id,
                            query=generation_prompt,
                            method='hybrid',  # Use hybrid search for best results
                            top_k=rag_top_k,
                            score_threshold=0.3,  # Minimum relevance threshold
                            source='diagram_generation',
                            source_context={
                                'stage': 'generation',
                                'diagram_type': diagram_type
                            }
                        )

                        if rag_context_chunks:
                            # Format context for prompt enhancement
                            rag_context = "\n\n".join([
                                f"[知识库参考 {i+1}]: {chunk}"
                                for i, chunk in enumerate(rag_context_chunks)
                            ]) if language == 'zh' else "\n\n".join([
                                f"[Knowledge Base Reference {i+1}]: {chunk}"
                                for i, chunk in enumerate(rag_context_chunks)
                            ])

                            logger.info(
                                "[RAG] Retrieved %d context chunks for diagram generation",
                                len(rag_context_chunks)
                            )
                        else:
                            logger.debug(
                                "[RAG] No relevant context found for query: %s...",
                                generation_prompt[:50]
                            )
                    else:
                        logger.debug(
                            "[RAG] User %d has no knowledge base, skipping RAG", user_id
                        )
                finally:
                    db.close()
            except Exception as e:  # pylint: disable=broad-except
                logger.warning("[RAG] Failed to retrieve context: %s", e, exc_info=True)
                # Continue without RAG context if retrieval fails

        # Enhance prompt with RAG context if available
        if rag_context:
            if language == 'zh':
                enhanced_prompt = f"""用户请求：{generation_prompt}

相关背景知识（来自用户的知识库）：
{rag_context}

请基于以上背景知识生成更准确、更详细的图表。"""
            else:
                enhanced_prompt = f"""User Request: {generation_prompt}

Relevant Context (from user's knowledge base):
{rag_context}

Please generate a more accurate and detailed diagram based on the above context."""

            logger.debug(
                "[RAG] Enhanced prompt with %d characters of context",
                len(rag_context)
            )
            generation_prompt = enhanced_prompt

        # Generate specification using the appropriate agent
        generation_start = time.time()
        spec = await _generate_spec_with_agent(
            generation_prompt,
            diagram_type,
            language,
            dimension_preference=dimension_preference if dimension_preference else None,
            model=model,
            # Token tracking parameters
            user_id=user_id,
            organization_id=organization_id,
            request_type=request_type,
            endpoint_path=endpoint_path,
            # Bridge map specific
            existing_analogies=existing_analogies,
            fixed_dimension=fixed_dimension,
            # Tree map and brace map: dimension-only mode
            dimension_only_mode=dimension_only_mode
        )
        generation_time = time.time() - generation_start
        logger.info(
            "Diagram generation completed in %.2fs for %s", generation_time, diagram_type
        )

        if not spec or (isinstance(spec, dict) and spec.get('error')):
            logger.error("Failed to generate spec for %s", diagram_type)
            return {
                'success': False,
                'spec': spec or create_error_response(
                    'Failed to generate specification',
                    'generation',
                    {'diagram_type': diagram_type}
                ),
                'diagram_type': diagram_type,
                'topics': [],
                'style_preferences': {},
                'language': language,
                'is_learning_sheet': is_learning_sheet,
                'hidden_node_percentage': 0
            }

        # Calculate hidden percentage for learning sheets (20%)
        hidden_percentage = 0.2 if is_learning_sheet else 0

        # Add learning sheet metadata to spec object so renderers can access it
        if isinstance(spec, dict):
            spec['is_learning_sheet'] = is_learning_sheet
            spec['hidden_node_percentage'] = hidden_percentage
            logger.debug(
                "Added learning sheet metadata to spec: is_learning_sheet=%s, "
                "hidden_percentage=%s", is_learning_sheet, hidden_percentage
            )

        # Add metadata to the result
        result = {
            'success': True,
            'spec': spec,
            'diagram_type': diagram_type,
            'topics': [],  # No longer extracted
            'style_preferences': {},  # No longer extracted
            'language': language,
            'is_learning_sheet': is_learning_sheet,  # NEW
            'hidden_node_percentage': hidden_percentage  # NEW
        }

        total_time = time.time() - workflow_start_time
        logger.info(
            "Simplified workflow completed successfully in %.2fs "
            "(breakdown: detection=%.2fs, topic=%.2fs, generation=%.2fs), "
            "learning sheet: %s",
            total_time, detection_time, topic_time, generation_time, is_learning_sheet
        )
        return result

    except ValueError as e:
        logger.error("Input validation failed: %s", e)
        return {
            'success': False,
            'spec': create_error_response(
                f'Invalid input: {str(e)}', 'validation', {'language': language}
            ),
            'diagram_type': 'bubble_map',
            'topics': [],
            'style_preferences': {},
            'language': language
        }
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Simplified workflow failed: %s", e)
        return {
            'success': False,
            'spec': create_error_response(
                f'Generation failed: {str(e)}', 'workflow', {'language': language}
            ),
            'diagram_type': 'bubble_map',
            'topics': [],
            'style_preferences': {},
            'language': language
        }
