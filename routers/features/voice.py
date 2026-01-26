from datetime import datetime
from typing import Dict, List, Any, Optional
import asyncio
import base64
import json
import logging
import random
import re
import uuid

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from clients.omni_client import OmniClient
from config.settings import config
from models.domain.auth import User
from services.features.voice_agent import voice_agent_manager
from services.features.websocket_llm_middleware import omni_middleware
from services.llm import llm_service
from utils.auth import decode_access_token, get_current_user

"""
Voice Router - Real-time Voice Conversation
WebSocket endpoint for VoiceAgent

Integrates with LLM Middleware:
- Uses LLMService for intent classification (Qwen Turbo)
- Uses WebSocket OmniClient for Omni conversation
- Uses WebSocketLLMMiddleware for rate limiting, error handling, token tracking
- Follows same rate limiting, error handling, timeout patterns

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

# Standard library imports

# Third-party imports

# Local application imports

# Optional imports - voice agent prompts
try:
    from prompts.voice_agent import VOICE_AGENT_PROMPTS
except ImportError:
    VOICE_AGENT_PROMPTS = None

# Optional imports - Redis services
try:
    from services.redis.cache.redis_user_cache import user_cache as redis_user_cache
except ImportError:
    redis_user_cache = None

try:
    from services.redis.session.redis_session_manager import (
        get_session_manager as redis_get_session_manager
    )
except ImportError:
    redis_get_session_manager = None

# Configure logger with module name 'VOICE'
logger = logging.getLogger('VOICE')

router = APIRouter()

# In-memory session storage
voice_sessions: Dict[str, Dict[str, Any]] = {}

# Track active WebSocket connections by diagram_session_id
# CRITICAL: This ensures we can close WebSocket connections when diagram sessions end
active_websockets: Dict[str, List[WebSocket]] = {}


def get_diagram_prefix_map() -> Dict[str, str]:
    """
    Get the node ID prefix map for all supported diagram types.
    This ensures consistent node ID generation across the voice agent.

    Returns:
        Dictionary mapping diagram_type to node ID prefix
    """
    return {
        'circle_map': 'context',
        'bubble_map': 'attribute',
        'double_bubble_map': 'node',
        'tree_map': 'item',
        'flow_map': 'step',
        'multi_flow_map': 'step',  # Uses same prefix as flow_map
        'brace_map': 'part',
        'bridge_map': 'node',  # Bridge maps use node prefix
        'mindmap': 'branch',
        'mind_map': 'branch',  # Alias for mindmap
        'concept_map': 'concept'
    }


def is_paragraph_text(text: str) -> bool:
    """
    Detect if input text is a paragraph (long text for processing) vs a command.

    Criteria:
    - Contains 30+ words OR contains multiple sentences (2+)
    - Not a simple command structure
    - Valid content (not just whitespace)

    Args:
        text: Input text to check

    Returns:
        True if text appears to be a paragraph for processing
    """
    # Input validation
    if not text:
        return False

    text_stripped = text.strip()

    # Must have minimum meaningful content
    if len(text_stripped) < 10:
        return False

    # Must not be too long (prevent abuse)
    if len(text_stripped) > 5000:
        logger.warning(
            "Text too long (%d chars), treating as paragraph but may be truncated",
            len(text_stripped)
        )
        # Still process, but warn

    # Count words (split by whitespace, filter empty strings)
    words = [w for w in text_stripped.split() if w.strip()]
    word_count = len(words)

    # Count sentences (periods, exclamation marks, question marks)
    sentence_endings = len(re.findall(r'[.!?。！？]', text_stripped))

    # Check word count and sentence count
    # Changed from 100 chars to 30 words - more accurate for paragraph detection
    is_long = word_count >= 30
    has_multiple_sentences = sentence_endings >= 2

    # Check if it looks like a command (short, imperative structure)
    command_prefixes = (
        '请', '帮我', '请帮我', 'can you', 'please', 'change',
        'update', 'add', 'delete', 'select'
    )
    command_suffixes = ('吗', '?', '？')
    is_command_like = (
        word_count < 10 and
        sentence_endings <= 1 and
        (text_stripped.startswith(command_prefixes) or
         text_stripped.endswith(command_suffixes))
    )

    # It's a paragraph if it has 30+ words OR has multiple sentences AND doesn't look like a command
    return (is_long or has_multiple_sentences) and not is_command_like


async def process_paragraph_with_qwen_plus(
    websocket: WebSocket,
    voice_session_id: str,
    paragraph_text: str,
    session_context: Dict[str, Any]
) -> bool:
    """
    Process a paragraph using Qwen Plus to understand teacher intent and extract diagram content.

    This handles the common case where teachers paste a whole paragraph and expect the system to:
    1. Understand what the teacher wants (extract content, generate diagram, update existing)
    2. Determine the best diagram type for the content (if not already set)
    3. Extract appropriate content and update the diagram

    Args:
        websocket: WebSocket connection
        voice_session_id: Voice session ID
        paragraph_text: The paragraph text to process
        session_context: Current session context

    Returns:
        True if diagram was updated, False otherwise
    """
    try:
        current_diagram_type = voice_sessions[voice_session_id].get('diagram_type', 'circle_map')
        diagram_data = session_context.get('diagram_data', {})

        # Get current diagram state
        current_topic = (
            diagram_data.get('topic') or
            diagram_data.get('center', {}).get('text', '')
        )
        current_nodes = (
            diagram_data.get('children', []) or
            diagram_data.get('attributes', []) or []
        )
        has_existing_content = bool(current_topic or current_nodes)

        logger.info(
            "Processing paragraph with Qwen Plus (current diagram: %s)",
            current_diagram_type
        )
        logger.debug(
            "Paragraph length: %d characters, has existing content: %s",
            len(paragraph_text), has_existing_content
        )

        # CRITICAL: Send loading indicator to teacher
        await safe_websocket_send(websocket, {
            'type': 'text_chunk',
            'text': '📝 正在分析段落内容，请稍候...'
        })

        # CRITICAL: Load prompt template from centralized prompts folder
        # Determine language based on paragraph content
        # (simple heuristic: check for Chinese characters)
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', paragraph_text))
        language = 'zh' if has_chinese else 'en'

        if VOICE_AGENT_PROMPTS:
            prompt_key = f'paragraph_processing_{language}'
            fallback_key = 'paragraph_processing_en'
            prompt_template = VOICE_AGENT_PROMPTS.get(
                prompt_key, VOICE_AGENT_PROMPTS.get(fallback_key)
            )
        else:
            logger.warning(
                "Could not import voice_agent prompts, using fallback"
            )
            # Fallback to English template if import fails
            prompt_template = (
                "You are an intelligent diagram assistant. "
                "A teacher has provided a paragraph of text. "
                "Your task is to extract content and determine "
                "the best diagram type.\n\n"
                "【Paragraph Text】\n"
                "{paragraph_text}\n\n"
                "【Current Diagram State】\n"
                "- Type: {current_diagram_type}\n"
                "- Current Topic: {current_topic}\n"
                "- Current Nodes: {current_nodes_count} nodes\n"
                "- Has Existing Content: {has_existing_content}\n\n"
                "Return JSON with intent, recommended_diagram_type, "
                "topic, nodes, summary, and reasoning."
            )

        # Ensure prompt_template is not None
        if not prompt_template:
            prompt_template = (
                "You are an intelligent diagram assistant. "
                "A teacher has provided a paragraph of text. "
                "Your task is to extract content and determine "
                "the best diagram type.\n\n"
                "【Paragraph Text】\n"
                "{paragraph_text}\n\n"
                "【Current Diagram State】\n"
                "- Type: {current_diagram_type}\n"
                "- Current Topic: {current_topic}\n"
                "- Current Nodes: {current_nodes_count} nodes\n"
                "- Has Existing Content: {has_existing_content}\n\n"
                "Return JSON with intent, recommended_diagram_type, "
                "topic, nodes, summary, and reasoning."
            )

        # Format prompt template with actual values
        prompt = prompt_template.format(
            paragraph_text=paragraph_text,
            current_diagram_type=current_diagram_type,
            current_topic=current_topic if current_topic else 'Not set',
            current_nodes_count=len(current_nodes),
            has_existing_content=has_existing_content
        )

        # Use Qwen Plus (generation model) for paragraph processing
        response = await llm_service.chat(
            prompt=prompt,
            model='qwen-plus',  # Use Plus for generation/extraction tasks
            temperature=0.3,  # Lower temperature for more consistent extraction
            max_tokens=1500,  # Allow longer responses for multiple nodes
            timeout=30.0
        )

        logger.debug("Qwen Plus response: %s...", response[:200])

        # Parse JSON response
        try:
            # Extract JSON from response (handle cases where LLM adds extra text)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                extracted_data = json.loads(json_match.group())
            else:
                extracted_data = json.loads(response)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Qwen Plus JSON response: %s", e)
            logger.debug("Raw response: %s", response)
            # Fallback: send acknowledgment and return False
            await safe_websocket_send(websocket, {
                'type': 'text_chunk',
                'text': '❌ 抱歉，我无法解析这段文本。请尝试更简洁的描述，或分段输入。'
            })
            return False

        # CRITICAL: Validate extracted content
        if not extracted_data:
            logger.warning("Qwen Plus returned empty data")
            await safe_websocket_send(websocket, {
                'type': 'text_chunk',
                'text': '❌ 未能从段落中提取到有效内容。请检查文本是否包含可提取的信息。'
            })
            return False

        # Validate nodes exist and are not empty
        nodes = extracted_data.get('nodes', [])
        topic = (
            extracted_data.get('topic') or
            extracted_data.get('title') or
            extracted_data.get('event') or
            extracted_data.get('whole')
        )

        # Check if we have meaningful content
        has_nodes = bool(nodes and len(nodes) > 0)
        has_topic = bool(topic and topic.strip())

        if not has_nodes and not has_topic:
            logger.warning("No nodes or topic extracted from paragraph")
            await safe_websocket_send(websocket, {
                'type': 'text_chunk',
                'text': '❌ 未能从段落中提取到主题或节点。请确保文本包含具体的内容信息。'
            })
            return False

        # Filter out empty nodes
        if nodes:
            nodes = [node for node in nodes if node and str(node).strip()]
            extracted_data['nodes'] = nodes

        if not nodes and not has_topic:
            logger.warning("All nodes were empty after filtering")
            await safe_websocket_send(websocket, {
                'type': 'text_chunk',
                'text': '❌ 提取的节点内容为空。请检查文本格式。'
            })
            return False

        # Validate node count (reasonable range)
        if len(nodes) > 20:
            logger.warning("Too many nodes extracted (%d), limiting to 15", len(nodes))
            nodes = nodes[:15]
            extracted_data['nodes'] = nodes

        logger.info("Validated extracted content: topic=%s, nodes=%d", bool(has_topic), len(nodes))

        # Check if diagram type should be changed
        recommended_type = extracted_data.get('recommended_diagram_type', current_diagram_type)
        should_change_type = extracted_data.get('should_change_diagram_type', False)
        reasoning = extracted_data.get('reasoning', '')

        # CRITICAL: Error handling - if recommended type doesn't match current type
        if recommended_type != current_diagram_type:
            logger.warning(
                "Diagram type mismatch detected: current=%s, recommended=%s",
                current_diagram_type, recommended_type
            )

            # Map diagram type names to Chinese for user-friendly messages
            diagram_type_names = {
                'circle_map': '圆圈图',
                'bubble_map': '气泡图',
                'double_bubble_map': '双气泡图',
                'tree_map': '树形图',
                'flow_map': '流程图',
                'multi_flow_map': '复流程图',
                'brace_map': '括号图',
                'bridge_map': '桥形图',
                'mindmap': '思维导图',
                'concept_map': '概念图'
            }

            current_name = diagram_type_names.get(current_diagram_type, current_diagram_type)
            recommended_name = diagram_type_names.get(recommended_type, recommended_type)

            # Send warning message to teacher
            warning_message = "⚠️ 检测到图表类型不匹配：\n"
            warning_message += f"当前图表类型：{current_name}\n"
            warning_message += f"推荐图表类型：{recommended_name}\n"
            if reasoning:
                warning_message += f"\n原因：{reasoning}\n"
            warning_message += f"\n建议：请切换到{recommended_name}以获得更好的内容展示效果。"
            warning_message += "\n\n是否继续在当前图表中添加内容？"

            await safe_websocket_send(websocket, {
                'type': 'text_chunk',
                'text': warning_message
            })

            # Notify frontend about diagram type change recommendation
            await safe_websocket_send(websocket, {
                'type': 'action',
                'action': 'diagram_type_recommendation',
                'params': {
                    'current_type': current_diagram_type,
                    'current_type_name': current_name,
                    'recommended_type': recommended_type,
                    'recommended_type_name': recommended_name,
                    'reasoning': reasoning or '内容更适合此图表类型',
                    'warning': True,
                    'message': warning_message
                }
            })

            # CRITICAL: Don't proceed with content extraction if types don't match
            # Wait for teacher's confirmation or let them switch diagram type first
            # For now, we'll still extract but use current diagram type (with warning)
            # In future, we could add a confirmation step
            logger.info(
                "Proceeding with current diagram type %s despite recommendation for %s",
                current_diagram_type, recommended_type
            )
            diagram_type = current_diagram_type  # Use current type to avoid breaking existing diagram

            # Send additional message explaining what will happen
            await safe_websocket_send(websocket, {
                'type': 'text_chunk',
                'text': f'\n注意：内容将按照{current_name}的结构提取，可能无法完全匹配内容特点。'
            })
        elif should_change_type:
            # Types match but LLM suggested change (shouldn't happen, but handle gracefully)
            diagram_type = current_diagram_type
        else:
            # Types match, proceed normally
            diagram_type = current_diagram_type

        intent = extracted_data.get('intent', 'extract_content')
        logger.info(
            "Detected intent: %s, using diagram type: %s (recommended: %s)",
            intent, diagram_type, recommended_type
        )

        # Send progress update
        if nodes:
            await safe_websocket_send(websocket, {
                'type': 'text_chunk',
                'text': f'✓ 已提取 {len(nodes)} 个节点，正在更新图表...'
            })

        # Update diagram based on extracted data

        if diagram_type == 'double_bubble_map':
            left_topic = extracted_data.get('left_topic')
            right_topic = extracted_data.get('right_topic')
            if left_topic and right_topic:
                # Also update nodes: similarities, left_differences, right_differences
                similarities = extracted_data.get('similarities', [])
                left_differences = extracted_data.get('left_differences', [])
                right_differences = extracted_data.get('right_differences', [])
                await execute_diagram_update(websocket, voice_session_id, 'update_center', {
                    'action': 'update_center',
                    'left': left_topic,
                    'right': right_topic,
                    'target': f"{left_topic} vs {right_topic}"
                }, session_context)
                # CRITICAL: Batch add nodes instead of one-by-one for efficiency
                # Collect all nodes first, then send batch update
                nodes_to_add = []

                # Add similarities nodes
                for node_text in similarities[:5]:
                    if node_text and str(node_text).strip():
                        nodes_to_add.append({'text': str(node_text).strip(), 'category': 'similarities'})

                # Add left differences nodes
                for node_text in left_differences[:5]:
                    if node_text and str(node_text).strip():
                        nodes_to_add.append({'text': str(node_text).strip(), 'category': 'left_differences'})

                # Add right differences nodes
                for node_text in right_differences[:5]:
                    if node_text and str(node_text).strip():
                        nodes_to_add.append({'text': str(node_text).strip(), 'category': 'right_differences'})

                # Send batch update if we have nodes
                if nodes_to_add:
                    await safe_websocket_send(websocket, {
                        'type': 'diagram_update',
                        'action': 'add_nodes',
                        'updates': nodes_to_add
                    })

                    # Update session context
                    if 'diagram_data' not in session_context:
                        session_context['diagram_data'] = {}

                    # Update agent state
                    agent_session_id = get_agent_session_id(voice_session_id)
                    agent = voice_agent_manager.get_or_create(agent_session_id)
                    diagram_data = session_context.get('diagram_data', {})
                    diagram_data['diagram_type'] = voice_sessions[voice_session_id].get('diagram_type')
                    agent.update_diagram_state(diagram_data)

                    updated_context = {
                        'diagram_type': voice_sessions[voice_session_id].get('diagram_type'),
                        'active_panel': voice_sessions[voice_session_id].get('active_panel', 'none'),
                        'conversation_history': voice_sessions[voice_session_id].get('conversation_history', []),
                        'selected_nodes': session_context.get('selected_nodes', []),
                        'diagram_data': diagram_data
                    }
                    new_instructions = build_voice_instructions(updated_context)
                    omni_client = get_session_omni_client(voice_session_id)
                    if omni_client:
                        await omni_client.update_instructions(new_instructions)

                    logger.debug("Batch added %d nodes for double bubble map", len(nodes_to_add))
        elif diagram_type == 'flow_map':
            title = extracted_data.get('title') or extracted_data.get('topic')
            if title:
                await execute_diagram_update(websocket, voice_session_id, 'update_center', {
                    'action': 'update_center',
                    'title': title,
                    'target': title
                }, session_context)
            nodes = extracted_data.get('nodes', [])
            # CRITICAL: Batch add nodes instead of one-by-one
            nodes_to_add = [
                {'text': str(node_text).strip()}
                for node_text in nodes[:10]
                if node_text and str(node_text).strip()
            ]
            if nodes_to_add:
                await safe_websocket_send(websocket, {
                    'type': 'diagram_update',
                    'action': 'add_nodes',
                    'updates': nodes_to_add
                })

                # Update session context and agent state
                if 'diagram_data' not in session_context:
                    session_context['diagram_data'] = {}
                if 'children' not in session_context['diagram_data']:
                    session_context['diagram_data']['children'] = []
                session_context['diagram_data']['children'].extend([{'text': n['text']} for n in nodes_to_add])

                agent_session_id = get_agent_session_id(voice_session_id)
                agent = voice_agent_manager.get_or_create(agent_session_id)
                diagram_data = session_context.get('diagram_data', {})
                diagram_data['diagram_type'] = voice_sessions[voice_session_id].get('diagram_type')
                agent.update_diagram_state(diagram_data)

                updated_context = {
                    'diagram_type': voice_sessions[voice_session_id].get('diagram_type'),
                    'active_panel': voice_sessions[voice_session_id].get('active_panel', 'none'),
                    'conversation_history': voice_sessions[voice_session_id].get('conversation_history', []),
                    'selected_nodes': session_context.get('selected_nodes', []),
                    'diagram_data': diagram_data
                }
                new_instructions = build_voice_instructions(updated_context)
                omni_client = get_session_omni_client(voice_session_id)
                if omni_client:
                    await omni_client.update_instructions(new_instructions)

                logger.debug("Batch added %d nodes for flow map", len(nodes_to_add))
        elif diagram_type == 'multi_flow_map':
            event = extracted_data.get('event') or extracted_data.get('topic')
            if event:
                await execute_diagram_update(websocket, voice_session_id, 'update_center', {
                    'action': 'update_center',
                    'event': event,
                    'target': event
                }, session_context)
            causes = extracted_data.get('causes', [])
            effects = extracted_data.get('effects', [])
            # CRITICAL: Batch add nodes
            nodes_to_add = []
            for node_text in causes[:5]:
                if node_text and str(node_text).strip():
                    nodes_to_add.append({'text': str(node_text).strip(), 'category': 'causes'})
            for node_text in effects[:5]:
                if node_text and str(node_text).strip():
                    nodes_to_add.append({'text': str(node_text).strip(), 'category': 'effects'})

            if nodes_to_add:
                await safe_websocket_send(websocket, {
                    'type': 'diagram_update',
                    'action': 'add_nodes',
                    'updates': nodes_to_add
                })

                # Update session context and agent state
                if 'diagram_data' not in session_context:
                    session_context['diagram_data'] = {}

                agent_session_id = get_agent_session_id(voice_session_id)
                agent = voice_agent_manager.get_or_create(agent_session_id)
                diagram_data = session_context.get('diagram_data', {})
                diagram_data['diagram_type'] = voice_sessions[voice_session_id].get('diagram_type')
                agent.update_diagram_state(diagram_data)

                updated_context = {
                    'diagram_type': voice_sessions[voice_session_id].get('diagram_type'),
                    'active_panel': voice_sessions[voice_session_id].get('active_panel', 'none'),
                    'conversation_history': voice_sessions[voice_session_id].get('conversation_history', []),
                    'selected_nodes': session_context.get('selected_nodes', []),
                    'diagram_data': diagram_data
                }
                new_instructions = build_voice_instructions(updated_context)
                omni_client = get_session_omni_client(voice_session_id)
                if omni_client:
                    await omni_client.update_instructions(new_instructions)

                logger.debug("Batch added %d nodes for multi-flow map", len(nodes_to_add))
        elif diagram_type == 'brace_map':
            whole = extracted_data.get('whole') or extracted_data.get('topic')
            if whole:
                await execute_diagram_update(websocket, voice_session_id, 'update_center', {
                    'action': 'update_center',
                    'whole': whole,
                    'target': whole
                }, session_context)
            parts = extracted_data.get('parts', []) or extracted_data.get('nodes', [])
            # CRITICAL: Batch add nodes
            nodes_to_add = [
                {'text': str(node_text).strip()}
                for node_text in parts[:10]
                if node_text and str(node_text).strip()
            ]
            if nodes_to_add:
                await safe_websocket_send(websocket, {
                    'type': 'diagram_update',
                    'action': 'add_nodes',
                    'updates': nodes_to_add
                })

                # Update session context and agent state
                if 'diagram_data' not in session_context:
                    session_context['diagram_data'] = {}
                if 'children' not in session_context['diagram_data']:
                    session_context['diagram_data']['children'] = []
                session_context['diagram_data']['children'].extend([{'text': n['text']} for n in nodes_to_add])

                agent_session_id = get_agent_session_id(voice_session_id)
                agent = voice_agent_manager.get_or_create(agent_session_id)
                diagram_data = session_context.get('diagram_data', {})
                diagram_data['diagram_type'] = voice_sessions[voice_session_id].get('diagram_type')
                agent.update_diagram_state(diagram_data)

                updated_context = {
                    'diagram_type': voice_sessions[voice_session_id].get('diagram_type'),
                    'active_panel': voice_sessions[voice_session_id].get('active_panel', 'none'),
                    'conversation_history': voice_sessions[voice_session_id].get('conversation_history', []),
                    'selected_nodes': session_context.get('selected_nodes', []),
                    'diagram_data': diagram_data
                }
                new_instructions = build_voice_instructions(updated_context)
                omni_client = get_session_omni_client(voice_session_id)
                if omni_client:
                    await omni_client.update_instructions(new_instructions)

                logger.debug("Batch added %d nodes for brace map", len(nodes_to_add))
        elif diagram_type == 'bridge_map':
            dimension = extracted_data.get('dimension') or extracted_data.get('topic', '')
            if dimension:
                await execute_diagram_update(websocket, voice_session_id, 'update_center', {
                    'action': 'update_center',
                    'dimension': dimension,
                    'target': dimension
                }, session_context)
            analogies = extracted_data.get('analogies', [])
            # CRITICAL: Batch add nodes
            nodes_to_add = []
            for analogy in analogies[:5]:
                if isinstance(analogy, dict):
                    left = analogy.get('left')
                    right = analogy.get('right')
                    if left and right:
                        nodes_to_add.append({
                            'text': f"{left} : {right}",
                            'left': str(left).strip(),
                            'right': str(right).strip()
                        })

            if nodes_to_add:
                await safe_websocket_send(websocket, {
                    'type': 'diagram_update',
                    'action': 'add_nodes',
                    'updates': nodes_to_add
                })

                # Update session context and agent state
                if 'diagram_data' not in session_context:
                    session_context['diagram_data'] = {}

                agent_session_id = get_agent_session_id(voice_session_id)
                agent = voice_agent_manager.get_or_create(agent_session_id)
                diagram_data = session_context.get('diagram_data', {})
                diagram_data['diagram_type'] = voice_sessions[voice_session_id].get('diagram_type')
                agent.update_diagram_state(diagram_data)

                updated_context = {
                    'diagram_type': voice_sessions[voice_session_id].get('diagram_type'),
                    'active_panel': voice_sessions[voice_session_id].get('active_panel', 'none'),
                    'conversation_history': voice_sessions[voice_session_id].get('conversation_history', []),
                    'selected_nodes': session_context.get('selected_nodes', []),
                    'diagram_data': diagram_data
                }
                new_instructions = build_voice_instructions(updated_context)
                omni_client = get_session_omni_client(voice_session_id)
                if omni_client:
                    await omni_client.update_instructions(new_instructions)

                logger.debug("Batch added %d nodes for bridge map", len(nodes_to_add))
        else:
            # Standard diagrams (circle_map, bubble_map, tree_map, mindmap, concept_map)
            topic = extracted_data.get('topic')
            if topic:
                await execute_diagram_update(websocket, voice_session_id, 'update_center', {
                    'action': 'update_center',
                    'target': topic
                }, session_context)
            nodes = extracted_data.get('nodes', [])
            # CRITICAL: Batch add nodes instead of one-by-one
            nodes_to_add = [
                {'text': str(node_text).strip()}
                for node_text in nodes[:10]
                if node_text and str(node_text).strip()
            ]
            if nodes_to_add:
                await safe_websocket_send(websocket, {
                    'type': 'diagram_update',
                    'action': 'add_nodes',
                    'updates': nodes_to_add
                })

                # Update session context and agent state
                if 'diagram_data' not in session_context:
                    session_context['diagram_data'] = {}
                if 'children' not in session_context['diagram_data']:
                    session_context['diagram_data']['children'] = []
                session_context['diagram_data']['children'].extend([{'text': n['text']} for n in nodes_to_add])

                agent_session_id = get_agent_session_id(voice_session_id)
                agent = voice_agent_manager.get_or_create(agent_session_id)
                diagram_data = session_context.get('diagram_data', {})
                diagram_data['diagram_type'] = voice_sessions[voice_session_id].get('diagram_type')
                agent.update_diagram_state(diagram_data)

                updated_context = {
                    'diagram_type': voice_sessions[voice_session_id].get('diagram_type'),
                    'active_panel': voice_sessions[voice_session_id].get('active_panel', 'none'),
                    'conversation_history': voice_sessions[voice_session_id].get('conversation_history', []),
                    'selected_nodes': session_context.get('selected_nodes', []),
                    'diagram_data': diagram_data
                }
                new_instructions = build_voice_instructions(updated_context)
                omni_client = get_session_omni_client(voice_session_id)
                if omni_client:
                    await omni_client.update_instructions(new_instructions)

                logger.debug("Batch added %d nodes for standard diagram", len(nodes_to_add))

        # Send acknowledgment with reasoning (only if no type mismatch warning was sent)
        summary = extracted_data.get('summary', '已从段落中提取内容并更新图表')

        # Only send acknowledgment if we didn't already send a warning message
        if recommended_type == current_diagram_type:
            acknowledgment_text = f'✅ 已处理段落内容：{summary}'
            if reasoning:
                acknowledgment_text += f'\n\n说明：{reasoning}'

            await safe_websocket_send(websocket, {
                'type': 'text_chunk',
                'text': acknowledgment_text
            })
        else:
            # Type mismatch - summary already included in warning message
            # Just send a completion message
            await safe_websocket_send(websocket, {
                'type': 'text_chunk',
                'text': '\n✅ 内容已提取并添加到当前图表中。'
            })

        nodes_added = len(extracted_data.get('nodes', []))
        logger.info(
            "Successfully processed paragraph: intent=%s, diagram_type=%s, "
            "recommended=%s, nodes_added=%d",
            intent, diagram_type, recommended_type, nodes_added
        )
        return True

    except (ValueError, KeyError, json.JSONDecodeError, RuntimeError) as e:
        logger.error("Paragraph processing error: %s", e, exc_info=True)
        await safe_websocket_send(websocket, {
            'type': 'text_chunk',
            'text': '处理段落时出现错误，请稍后重试。'
        })
        return False


def get_agent_session_id(voice_session_id: str) -> str:
    """
    Get the agent session ID scoped to diagram_session_id.

    CRITICAL: Voice agent sessions must be scoped to diagram_session_id, not voice_session_id.
    This ensures:
    - One agent per diagram session (not per WebSocket connection)
    - Proper cleanup when switching diagrams
    - No cross-contamination between diagram sessions

    Args:
        voice_session_id: The voice session ID (WebSocket connection identifier)

    Returns:
        Agent session ID (scoped to diagram_session_id)
    """
    if voice_session_id in voice_sessions:
        diagram_session_id = voice_sessions[voice_session_id].get('diagram_session_id')
        if diagram_session_id:
            return f"diagram_{diagram_session_id}"

    # Fallback: use voice_session_id if diagram_session_id not available (shouldn't happen)
    logger.warning("Voice session %s has no diagram_session_id, using voice_session_id as fallback", voice_session_id)
    return voice_session_id


def create_voice_session(
    user_id: str,
    diagram_session_id: Optional[str] = None,
    diagram_type: Optional[str] = None,
    active_panel: Optional[str] = None
) -> str:
    """
    Create new voice session (session-bound to diagram session).

    CRITICAL: Creates a NEW OmniClient instance for this session to support
    multiple concurrent users. Each voice session gets its own OmniClient,
    preventing cross-contamination between users.

    VoiceAgent session lifecycle is controlled by:
    1. Black cat click (activation)
    2. Black cat click again (deactivation)
    3. Session manager cleanup (when diagram session ends)
    4. Navigation to gallery (session manager triggers cleanup)
    """
    session_id = f"voice_{uuid.uuid4().hex[:12]}"

    # CRITICAL: Create a NEW OmniClient instance for this voice session
    # This ensures each user gets their own isolated Omni conversation
    # Without this, multiple users would share the same OmniClient singleton,
    # causing cross-contamination (User A's messages going to User B's conversation)
    omni_client = OmniClient()

    voice_sessions[session_id] = {
        'session_id': session_id,
        'user_id': user_id,
        'diagram_session_id': diagram_session_id,
        'diagram_type': diagram_type,
        'active_panel': active_panel or 'mindmate',
        'created_at': datetime.now(),
        'last_activity': datetime.now(),
        'conversation_history': [],
        'omni_client': omni_client  # Per-session OmniClient instance
    }

    logger.debug("Session created: %s (linked to diagram=%s, has own OmniClient)", session_id, diagram_session_id)
    return session_id


def get_voice_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Get session"""
    return voice_sessions.get(session_id)


def get_session_omni_client(voice_session_id: str):
    """
    Get the OmniClient instance for a voice session.

    CRITICAL: Each voice session has its own OmniClient instance to support
    concurrent users. This prevents cross-contamination between users.

    Args:
        voice_session_id: Voice session ID

    Returns:
        OmniClient instance for this session, or None if session not found
    """
    session = get_voice_session(voice_session_id)
    if not session:
        logger.warning("Voice session %s not found", voice_session_id)
        return None

    omni_client = session.get('omni_client')
    if not omni_client:
        logger.warning("OmniClient not found for session %s", voice_session_id)
        return None

    return omni_client


def update_panel_context(session_id: str, active_panel: str) -> None:
    """Update active panel context"""
    if session_id in voice_sessions:
        old_panel = voice_sessions[session_id].get('active_panel', 'unknown')
        voice_sessions[session_id]['active_panel'] = active_panel
        logger.debug("Panel context updated: %s (%s -> %s)", session_id, old_panel, active_panel)


def end_voice_session(session_id: str, reason: str = 'completed') -> None:
    """
    End and cleanup session including persistent agent and OmniClient.

    CRITICAL: This closes the OmniClient WebSocket connection and removes the agent.
    Called when:
    - User navigates back to gallery
    - User switches to a different diagram
    - WebSocket connection closes
    """
    if session_id in voice_sessions:
        logger.debug("VOIC | Session ended: %s (reason=%s)", session_id, reason)
        session = voice_sessions[session_id]

        # Get diagram_session_id before deleting the session
        diagram_session_id = session.get('diagram_session_id')

        # CRITICAL: Close OmniClient WebSocket connection before deleting session
        # Each voice session has its own OmniClient instance that must be closed
        omni_client = session.get('omni_client')
        if omni_client:
            try:
                # Native WebSocket client uses async close()
                if (hasattr(omni_client, '_native_client') and
                    omni_client._native_client):  # pylint: disable=protected-access
                    # Schedule async close (can't await in sync function)
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # If loop is running, schedule close
                            asyncio.create_task(
                                omni_client._native_client.close()
                            )  # pylint: disable=protected-access
                        else:
                            loop.run_until_complete(
                                omni_client._native_client.close()
                            )  # pylint: disable=protected-access
                    except RuntimeError:
                        # No event loop, create new one
                        asyncio.run(omni_client._native_client.close())  # pylint: disable=protected-access
                    logger.debug("VOIC | Closed Omni client for session %s", session_id)
                elif hasattr(omni_client, 'close'):
                    # Handle both sync and async close methods
                    close_result = omni_client.close()
                    if asyncio.iscoroutine(close_result):
                        try:
                            loop = asyncio.get_event_loop()
                            if loop.is_running():
                                asyncio.create_task(close_result)
                            else:
                                loop.run_until_complete(close_result)
                        except RuntimeError:
                            asyncio.run(close_result)
                    logger.debug("VOIC | Closed Omni client for session %s", session_id)
            except (RuntimeError, AttributeError, asyncio.CancelledError) as e:
                logger.debug(
                    "VOIC | Error closing Omni client for session %s "
                    "(may already be closed): %s",
                    session_id, e
                )

        # Delete session from memory
        del voice_sessions[session_id]

        # Cleanup the persistent LangGraph agent using diagram_session_id
        # CRITICAL: Agent is scoped to diagram_session_id, not voice_session_id
        if diagram_session_id:
            agent_session_id = f"diagram_{diagram_session_id}"
            voice_agent_manager.remove(agent_session_id)
            logger.debug("VOIC | Removed agent for diagram session %s", diagram_session_id)


async def cleanup_voice_by_diagram_session(diagram_session_id: str) -> bool:
    """
    Cleanup voice session and WebSocket connections when diagram session ends.
    Called by session manager on session end or navigation to gallery.

    CRITICAL: This closes all WebSocket connections for the diagram session,
    ensuring fresh state when switching diagrams.
    """
    cleaned_count = 0

    # CRITICAL: Close all WebSocket connections for this diagram session
    if diagram_session_id in active_websockets:
        ws_list = active_websockets[diagram_session_id].copy()  # Copy to avoid modification during iteration
        logger.debug("Closing %d WebSocket connection(s) for diagram %s", len(ws_list), diagram_session_id)
        for ws in ws_list:
            try:
                # Check WebSocket state before attempting to close
                # This prevents errors when WebSocket is already closed by frontend
                if hasattr(ws, 'client_state'):
                    if ws.client_state.name == 'DISCONNECTED':
                        logger.debug("WebSocket already disconnected, skipping close")
                    else:
                        await ws.close(code=1001, reason="Diagram session ended")
                else:
                    # Fallback: try to close anyway (for non-FastAPI WebSocket implementations)
                    await ws.close(code=1001, reason="Diagram session ended")
            except (RuntimeError, ConnectionError, AttributeError) as e:
                logger.debug("Error closing WebSocket (may already be closed): %s", e)
            finally:
                # CRITICAL: Always remove from list, even if close failed
                # This prevents memory leaks from orphaned WebSocket references
                try:
                    if diagram_session_id in active_websockets:
                        active_websockets[diagram_session_id].remove(ws)
                except ValueError:
                    # WebSocket not in list (already removed or list was cleared)
                    pass
        # Clear the list and remove entry
        if diagram_session_id in active_websockets:
            if not active_websockets[diagram_session_id]:  # List is empty after removals
                del active_websockets[diagram_session_id]
            else:
                # Some WebSockets couldn't be removed (shouldn't happen, but defensive)
                active_websockets[diagram_session_id] = []
                del active_websockets[diagram_session_id]
        cleaned_count += len(ws_list)

    # CRITICAL: Cleanup ALL voice sessions for this diagram_session_id (not just the first one)
    # This handles cases where cleanup failed before and multiple sessions exist
    voice_session_ids_to_cleanup = []
    for sid, session in list(voice_sessions.items()):  # Use list() to avoid modification during iteration
        if session.get('diagram_session_id') == diagram_session_id:
            voice_session_ids_to_cleanup.append(sid)

    if voice_session_ids_to_cleanup:
        logger.debug(
            "Found %d voice session(s) for diagram %s, cleaning up all",
            len(voice_session_ids_to_cleanup), diagram_session_id
        )
        for voice_session_id in voice_session_ids_to_cleanup:
            logger.debug(
                "Cleaning up voice session %s (diagram session %s ended)",
                voice_session_id, diagram_session_id
            )
            end_voice_session(voice_session_id, reason='diagram_session_ended')
            cleaned_count += 1
        return True

    if cleaned_count > 0:
        return True

    return False


async def safe_websocket_send(websocket: WebSocket, message: Dict[str, Any]) -> bool:
    """
    Safely send a message via WebSocket, checking if connection is still open.

    Returns:
        True if message was sent successfully, False if WebSocket is closed
    """
    try:
        # Check WebSocket state - FastAPI WebSocket has client_state attribute
        if hasattr(websocket, 'client_state'):
            # WebSocketState enum: CONNECTING, CONNECTED, DISCONNECTED
            if websocket.client_state.name == 'DISCONNECTED':
                logger.debug("WebSocket is disconnected, skipping send")
                return False
        await websocket.send_json(message)
        return True
    except (RuntimeError, ConnectionError, AttributeError) as e:
        # Handle various WebSocket closed errors
        if "close" in str(e).lower() or "closed" in str(e).lower():
            logger.debug("WebSocket closed, cannot send message: %s", e)
            return False
        # Re-raise other exceptions
        logger.error("Error sending WebSocket message: %s", e)
        raise


def build_voice_instructions(context: Dict[str, Any]) -> str:
    """Build voice instructions from context with full diagram data"""
    diagram_type = context.get('diagram_type', 'unknown')
    active_panel = context.get('active_panel', 'mindmate')
    selected_nodes = context.get('selected_nodes', [])
    diagram_data = context.get('diagram_data', {})

    # Extract center topic based on diagram type
    center_text = ''
    if diagram_type == 'double_bubble_map':
        left = diagram_data.get('left', '')
        right = diagram_data.get('right', '')
        if left and right:
            center_text = f"{left} 和 {right}"
        elif left:
            center_text = left
        elif right:
            center_text = right
    elif diagram_type == 'flow_map':
        center_text = diagram_data.get('title', '')
    elif diagram_type == 'multi_flow_map':
        center_text = diagram_data.get('event', '')
    elif diagram_type == 'brace_map':
        center_text = diagram_data.get('whole', '')
    elif diagram_type == 'bridge_map':
        center_text = diagram_data.get('dimension', '')
    else:
        # Default: most diagrams use center.text
        center_text = diagram_data.get('center', {}).get('text', '')

    children = diagram_data.get('children', [])

    # Format nodes list for Omni to understand (with IDs for precise selection)
    nodes_list = ""
    if children:
        for i, node in enumerate(children[:15]):  # Limit to 15 nodes
            if isinstance(node, str):
                nodes_list += f"\n  {i+1}. \"{node}\""
            elif isinstance(node, dict):
                node_id = node.get('id', f'node_{i}')
                text = node.get('text') or node.get('label') or str(node)
                nodes_list += f"\n  {i+1}. \"{text}\" (id: {node_id})"
        if len(children) > 15:
            nodes_list += f"\n  ... and {len(children) - 15} more nodes"

    instructions = f"""You are a helpful K12 classroom AI assistant for MindGraph.

【Current Diagram】
- Type: {diagram_type}
- Center topic: {center_text or 'Not set'}
- Nodes ({len(children)} total):{nodes_list if nodes_list else ' None'}

【Current State】
- Active panel: {active_panel}
- Selected nodes: {len(selected_nodes)}

【Your Capabilities】
You can help with:
1. Answering questions about the diagram content
2. Explaining concepts (e.g., "explain node 1" or "explain ABC")
3. Suggesting new nodes to add
4. Understanding relationships between nodes
5. **EXECUTING CHANGES**: When users ask you to make changes (e.g., "change the first node to X",
   "update the center to Y", "add a node called Z", "delete node ABC"), you should acknowledge
   and confirm the change. The system will automatically execute these changes based on your
   conversation.

【Important: Executing Changes】
When users request changes conversationally (e.g., "can you change...", "please update...",
"I want to change..."), acknowledge the request clearly. Examples:
- "Change the first node to apples" → Acknowledge: "好的，我会把第一个节点改成'苹果'。" (The system will execute this automatically)
- "Update center to cars" → Acknowledge: "好的，我会把中心主题改成'汽车'。" (The system will execute this automatically)
- "Add a node called fruits" → Acknowledge: "好的，我会添加一个叫'水果'的节点。" (The system will execute this automatically)

When user mentions a node by name or number, you know exactly which one they mean.
For example, if user says "select ABC" and ABC is node 3, you understand they want node 3.

【Guidelines】
- Be concise and helpful
- Use simple vocabulary for K12 students
- Reference specific nodes by their content
- Encourage critical thinking
- **When users ask for changes, acknowledge clearly** - the system will execute them automatically

Respond naturally in the same language as the user."""

    return instructions


def parse_double_bubble_target(target: str) -> Optional[Dict[str, str]]:
    """
    Parse target text for double bubble map into left/right fields.

    Handles common patterns:
    - "A和B" (Chinese: A and B)
    - "A与B" (Chinese: A and B, alternative)
    - "A vs B" (English: A versus B)
    - "A and B" (English: A and B)
    - "A/B" (Slash separator)
    - "A 和 B" (with spaces)

    Args:
        target: Target text to parse

    Returns:
        Dict with 'left' and 'right' keys if parsing successful, None otherwise
    """
    if not target or not isinstance(target, str):
        return None

    target = target.strip()

    # Try different separators in order of likelihood
    separators = [
        '和',      # Chinese: and
        '与',      # Chinese: and (alternative)
        ' vs ',    # English: versus (with spaces)
        ' vs',     # English: versus (space before)
        'vs ',     # English: versus (space after)
        'vs',      # English: versus (no spaces)
        ' and ',   # English: and (with spaces)
        ' and',    # English: and (space before)
        'and ',    # English: and (space after)
        ' and',    # English: and (space before, lowercase)
        'and',     # English: and (no spaces)
        '/',       # Slash separator
        '|',       # Pipe separator
    ]

    for sep in separators:
        if sep in target:
            parts = target.split(sep, 1)  # Split only on first occurrence
            if len(parts) == 2:
                left = parts[0].strip()
                right = parts[1].strip()
                if left and right:
                    return {'left': left, 'right': right}

    # If no separator found, return None (parsing failed)
    return None


def build_greeting_message(diagram_type: str = 'unknown', language: str = 'zh') -> str:
    """
    Build personalized greeting message based on diagram type and language.

    Args:
        diagram_type: Type of diagram (circle_map, bubble_map, etc.)
        language: Language code ('zh' or 'en')

    Returns:
        Greeting message string
    """
    # Chinese greetings
    greetings_zh = {
        'circle_map': '你好！我是你的思维助手。我可以帮你完善圆圈图，探索更多观察和想法。有什么我可以帮你的吗？',
        'bubble_map': '嗨！我来帮你描述事物的特征。告诉我你想添加什么形容词或特点吧！',
        'tree_map': '你好！我可以帮你整理分类。让我们一起把想法分门别类吧！',
        'flow_map': '嗨！我来帮你梳理流程。告诉我每一步的顺序，我会协助你理清思路！',
        'brace_map': '你好！我可以帮你分析整体与部分的关系。让我们一起探索吧！',
        'bridge_map': '嗨！我来帮你找出事物之间的类比关系。准备好了吗？',
        'double_bubble_map': '你好！我可以帮你比较两个事物。告诉我它们的相同点和不同点吧！',
        'multi_flow_map': '嗨！我来帮你分析因果关系。让我们一起找出原因和结果！',
        'mind_map': '你好！我是你的思维导图助手。告诉我你的主题，我会帮你展开更多想法！',
        'concept_map': '嗨！我来帮你理清概念之间的关系。让我们一起建立知识网络吧！',
        'default': '你好！我是你的AI助手，很高兴为你服务。你可以问我任何关于思维图的问题，或者让我帮你更新图表内容。'
    }

    # English greetings
    greetings_en = {
        'circle_map': (
            'Hi! I\'m your thinking assistant. I can help you enhance your Circle Map '
            'with more observations and ideas. How can I help?'
        ),
        'bubble_map': (
            'Hello! I\'m here to help you describe things. Tell me what adjectives '
            'or characteristics you want to add!'
        ),
        'tree_map': (
            'Hi! I can help you organize by categories. Let\'s classify your ideas together!'
        ),
        'flow_map': (
            'Hello! I\'m here to help you map processes. Tell me the sequence, '
            'and I\'ll help you clarify!'
        ),
        'brace_map': (
            'Hi! I can help you analyze whole-part relationships. Let\'s explore together!'
        ),
        'bridge_map': (
            'Hello! I\'m here to help you find analogies. Ready to compare?'
        ),
        'double_bubble_map': (
            'Hi! I can help you compare two things. Tell me their similarities and differences!'
        ),
        'multi_flow_map': (
            'Hello! I\'m here to help you analyze cause and effect. '
            'Let\'s find the reasons and results!'
        ),
        'mind_map': (
            'Hi! I\'m your mind map assistant. Tell me your topic, '
            'and I\'ll help you brainstorm ideas!'
        ),
        'concept_map': (
            'Hello! I\'m here to help you connect concepts. '
            'Let\'s build a knowledge network together!'
        ),
        'default': (
            'Hello! I\'m your AI assistant, happy to help. Ask me anything about your diagram, '
            'or let me help you update it.'
        )
    }

    greetings = greetings_zh if language == 'zh' else greetings_en
    return greetings.get(diagram_type, greetings['default'])


async def _handle_update_center_action(
    websocket: WebSocket,
    voice_session_id: str,
    command: Dict[str, Any],
    session_context: Dict[str, Any],
    target: Optional[str]
) -> bool:
    """
    Handle update_center action to reduce complexity in execute_diagram_update.

    Returns:
        True if update was executed successfully, False otherwise
    """
    # CRITICAL: Get diagram_type directly from voice_sessions (source of truth)
    # This ensures we have the correct diagram type even if session wasn't updated yet
    diagram_type = None
    if voice_session_id in voice_sessions:
        diagram_type = voice_sessions[voice_session_id].get('diagram_type')
    if not diagram_type:
        # Fallback: try to get from context
        diagram_type = session_context.get('diagram_type')
    if not diagram_type:
        logger.warning("[VOIC] Could not determine diagram_type for update_center action, defaulting to circle_map")
        diagram_type = 'circle_map'

    logger.debug("[VOIC] Executing update_center for diagram_type=%s, target=%s", diagram_type, target)

    # Build updates dict based on diagram type
    # CRITICAL: Check for diagram-specific fields first, then fallback to target/new_text
    updates = {}

    if diagram_type == 'double_bubble_map':
        # Double bubble map: use left/right from command if available
        left = command.get('left')
        right = command.get('right')
        if left and right:
            updates = {'left': left, 'right': right}
            logger.info("Updating double bubble map: left=%s, right=%s", left, right)
        elif target:
            # CRITICAL: Parse target text to extract left/right for double bubble maps
            # Common patterns: "A和B", "A vs B", "A and B", "A/B", "A与B"
            parsed = parse_double_bubble_target(target)
            if parsed and parsed.get('left') and parsed.get('right'):
                updates = {'left': parsed['left'], 'right': parsed['right']}
                logger.info(
                    "Parsed double bubble map target '%s' -> left=%s, right=%s",
                    target, parsed['left'], parsed['right']
                )
            else:
                # If parsing fails, log warning and return False (don't use invalid update)
                logger.warning(
                    "Double bubble map update_center: could not parse target '%s' "
                    "into left/right fields. Expected format: 'A和B' or 'A vs B'",
                    target
                )
                await safe_websocket_send(websocket, {
                    'type': 'error',
                    'error': f"Double bubble map requires two topics separated by '和', 'vs', or 'and'. Got: {target}"
                })
                return False
        else:
            logger.warning("Double bubble map update_center: missing both left/right and target")
            return False
    elif diagram_type == 'flow_map':
        title = command.get('title') or target or command.get('new_text')
        if title:
            updates = {'title': title}
            logger.info("Updating flow map title: %s", title)
        else:
            logger.warning("Flow map update_center: missing title/target/new_text")
            return False
    elif diagram_type == 'multi_flow_map':
        event = command.get('event') or target or command.get('new_text')
        if event:
            updates = {'event': event}
            logger.info("Updating multi-flow map event: %s", event)
        else:
            logger.warning("Multi-flow map update_center: missing event/target/new_text")
            return False
    elif diagram_type == 'brace_map':
        whole = command.get('whole') or target or command.get('new_text')
        if whole:
            updates = {'whole': whole}
            logger.info("Updating brace map whole: %s", whole)
        else:
            logger.warning("Brace map update_center: missing whole/target/new_text")
            return False
    elif diagram_type == 'bridge_map':
        dimension = command.get('dimension') or target or command.get('new_text')
        if dimension:
            updates = {'dimension': dimension}
            logger.info("Updating bridge map dimension: %s", dimension)
        else:
            logger.warning("Bridge map update_center: missing dimension/target/new_text")
            return False
    else:
        # Default: most diagrams use new_text
        new_text = target or command.get('new_text')
        if new_text:
            updates = {'new_text': new_text}
            logger.info("Updating center to: %s", new_text)
        else:
            logger.warning("Default diagram update_center: missing target/new_text for %s", diagram_type)
            return False

    await safe_websocket_send(websocket, {
        'type': 'diagram_update',
        'action': 'update_center',
        'updates': updates
    })

    # CRITICAL: Update session context immediately
    if 'diagram_data' not in session_context:
        session_context['diagram_data'] = {}

    # Update diagram data based on diagram type
    if diagram_type == 'double_bubble_map':
        if 'left' in updates and 'right' in updates:
            session_context['diagram_data']['left'] = updates['left']
            session_context['diagram_data']['right'] = updates['right']
    elif diagram_type == 'flow_map':
        if 'title' in updates:
            session_context['diagram_data']['title'] = updates['title']
    elif diagram_type == 'multi_flow_map':
        if 'event' in updates:
            session_context['diagram_data']['event'] = updates['event']
    elif diagram_type == 'brace_map':
        if 'whole' in updates:
            session_context['diagram_data']['whole'] = updates['whole']
    elif diagram_type == 'bridge_map':
        if 'dimension' in updates:
            session_context['diagram_data']['dimension'] = updates['dimension']
    else:
        # Default: most diagrams use center.text
        if 'center' not in session_context['diagram_data']:
            session_context['diagram_data']['center'] = {}
        if 'new_text' in updates:
            session_context['diagram_data']['center']['text'] = updates['new_text']
        elif target:
            session_context['diagram_data']['center']['text'] = target

    # Update agent state and instructions
    # CRITICAL: Agent is scoped to diagram_session_id, not voice_session_id
    agent_session_id = get_agent_session_id(voice_session_id)
    agent = voice_agent_manager.get_or_create(agent_session_id)
    diagram_data = session_context.get('diagram_data', {})
    diagram_data['diagram_type'] = voice_sessions[voice_session_id].get('diagram_type')
    agent.update_diagram_state(diagram_data)

    updated_context = {
        'diagram_type': voice_sessions[voice_session_id].get('diagram_type'),
        'active_panel': voice_sessions[voice_session_id].get('active_panel', 'none'),
        'conversation_history': voice_sessions[voice_session_id].get('conversation_history', []),
        'selected_nodes': session_context.get('selected_nodes', []),
        'diagram_data': diagram_data
    }
    new_instructions = build_voice_instructions(updated_context)
    # Only update instructions if WebSocket is still open
    try:
        omni_client = get_session_omni_client(voice_session_id)
        if omni_client:
            await omni_client.update_instructions(new_instructions)
    except (RuntimeError, ConnectionError, AttributeError) as e:
        if "close" in str(e).lower() or "closed" in str(e).lower():
            logger.debug("WebSocket closed, skipping instruction update: %s", e)
        else:
            raise

    # Log the actual updated value based on diagram type
    if diagram_type == 'double_bubble_map':
        logger.debug("Center updated: left=%s, right=%s", updates.get('left'), updates.get('right'))
    elif diagram_type == 'flow_map':
        logger.debug("Center updated: title=%s", updates.get('title'))
    elif diagram_type == 'multi_flow_map':
        logger.debug("Center updated: event=%s", updates.get('event'))
    elif diagram_type == 'brace_map':
        logger.debug("Center updated: whole=%s", updates.get('whole'))
    elif diagram_type == 'bridge_map':
        logger.debug("Center updated: dimension=%s", updates.get('dimension'))
    else:
        logger.debug("Center updated: %s", updates.get('new_text') or target)
    return True


async def _handle_update_node_action(
    websocket: WebSocket,
    voice_session_id: str,
    command: Dict[str, Any],
    session_context: Dict[str, Any],
    target: str,
    node_index: Optional[int],
    node_identifier: Optional[str]
) -> bool:
    """
    Handle update_node action to reduce complexity in execute_diagram_update.

    Returns:
        True if update was executed successfully, False otherwise
    """
    # Resolve node by index or by target text (node_identifier)
    resolved_node_id = command.get('node_id')
    resolved_node_index = node_index

    nodes = session_context.get('diagram_data', {}).get('children', [])

    # If we have node_index, use it
    if resolved_node_index is not None:
        if 0 <= resolved_node_index < len(nodes):
            node = nodes[resolved_node_index]
            resolved_node_id = node.get('id') if isinstance(node, dict) else f"context_{resolved_node_index}"
        else:
            logger.warning("Node index %d out of bounds", resolved_node_index)
            return False
    # Otherwise, try to resolve by node_identifier (target text)
    elif node_identifier and not resolved_node_id:
        for idx, node in enumerate(nodes):
            node_text = node.get('text') if isinstance(node, dict) else str(node)
            if node_text and (node_identifier in node_text or node_text in node_identifier):
                resolved_node_index = idx
                resolved_node_id = node.get('id') if isinstance(node, dict) else f"context_{idx}"
                logger.debug("Resolved update_node by identifier '%s' to node_index=%d", node_identifier, idx)
                break

    if resolved_node_id and resolved_node_index is not None:
        logger.info("Updating node %d (%s) to: %s", resolved_node_index, resolved_node_id, target)

        # Build update payload with diagram-specific fields
        update_payload = {
            'node_id': resolved_node_id,
            'new_text': target
        }

        # Add category if specified (for double bubble map, multi-flow map)
        category = command.get('category')
        if category:
            update_payload['category'] = category

        # Add left/right if specified (for bridge map analogies)
        left = command.get('left')
        right = command.get('right')
        if left and right:
            update_payload['left'] = left
            update_payload['right'] = right

        await safe_websocket_send(websocket, {
            'type': 'diagram_update',
            'action': 'update_nodes',
            'updates': [update_payload]
        })

        # CRITICAL: Update session context immediately
        if 0 <= resolved_node_index < len(nodes):
            node = nodes[resolved_node_index]
            if isinstance(node, dict):
                node['text'] = target
                if 'label' in node:
                    node['label'] = target
            else:
                nodes[resolved_node_index] = target

        # Update agent state and instructions
        # CRITICAL: Agent is scoped to diagram_session_id, not voice_session_id
        agent_session_id = get_agent_session_id(voice_session_id)
        agent = voice_agent_manager.get_or_create(agent_session_id)
        diagram_data = session_context.get('diagram_data', {})
        diagram_data['diagram_type'] = voice_sessions[voice_session_id].get('diagram_type')
        agent.update_diagram_state(diagram_data)

        updated_context = {
            'diagram_type': voice_sessions[voice_session_id].get('diagram_type'),
            'active_panel': voice_sessions[voice_session_id].get('active_panel', 'none'),
            'conversation_history': voice_sessions[voice_session_id].get('conversation_history', []),
            'selected_nodes': session_context.get('selected_nodes', []),
            'diagram_data': diagram_data
        }
        new_instructions = build_voice_instructions(updated_context)
        # Only update instructions if WebSocket is still open
        try:
            omni_client = get_session_omni_client(voice_session_id)
            if omni_client:
                await omni_client.update_instructions(new_instructions)
        except (RuntimeError, ConnectionError, AttributeError) as e:
            if "close" in str(e).lower() or "closed" in str(e).lower():
                logger.debug("WebSocket closed, skipping instruction update: %s", e)
            else:
                raise

        logger.debug("Node updated: %d -> %s", resolved_node_index, target)
        return True
    else:
        logger.warning(
            "Could not resolve node for update: node_identifier=%s, node_index=%s",
            node_identifier, node_index
        )
        return False


async def execute_diagram_update(
    websocket: WebSocket,
    voice_session_id: str,
    action: str,
    command: Dict[str, Any],
    session_context: Dict[str, Any]
) -> bool:
    """
    Execute a diagram update action (update_center, update_node, add_node, delete_node).
    Returns True if update was executed, False otherwise.
    """
    target = command.get('target')
    node_index = command.get('node_index')
    node_identifier = command.get('node_identifier')

    try:
        if action == 'update_center':
            return await _handle_update_center_action(websocket, voice_session_id, command, session_context, target)

        elif action == 'update_node' and target:
            return await _handle_update_node_action(
                websocket, voice_session_id, command, session_context,
                target, node_index, node_identifier
            )

        elif action == 'add_node':
            if target:
                # Check if node_index is specified (for structured input like "branch 1", "branch 2")
                add_node_index = command.get('node_index')
                step_index = command.get('step_index')  # For flow_map substeps
                substep_index = command.get('substep_index')  # For flow_map substeps

                diagram_type = voice_sessions[voice_session_id].get('diagram_type', 'circle_map')

                # Extract hierarchical indices for different diagram types
                category_index = command.get('category_index')  # For tree_map items
                item_index = command.get('item_index')  # For tree_map items
                part_index = command.get('part_index')  # For brace_map subparts
                subpart_index = command.get('subpart_index')  # For brace_map subparts
                branch_index = command.get('branch_index')  # For mindmap children
                child_index = command.get('child_index')  # For mindmap children

                # Special handling for tree_map items (category_index + item_index)
                if diagram_type == 'tree_map' and category_index is not None and item_index is not None:
                    logger.info("Adding item to category %d at position %d: %s", category_index, item_index, target)

                    update_payload = {
                        'text': target,
                        'category_index': category_index,
                        'item_index': item_index
                    }

                    await safe_websocket_send(websocket, {
                        'type': 'diagram_update',
                        'action': 'add_nodes',
                        'updates': [update_payload]
                    })

                    # Update session context
                    diagram_data = session_context.get('diagram_data', {})
                    children = diagram_data.get('children', [])

                    if 0 <= category_index < len(children):
                        category = children[category_index]
                        if isinstance(category, dict):
                            if 'children' not in category or not isinstance(category['children'], list):
                                category['children'] = []

                            if item_index < len(category['children']):
                                category['children'].insert(item_index, {'text': target, 'children': []})
                            else:
                                while len(category['children']) < item_index:
                                    category['children'].append({'text': '', 'children': []})
                                category['children'].insert(item_index, {'text': target, 'children': []})

                    # Update agent state
                    agent_session_id = get_agent_session_id(voice_session_id)
                    agent = voice_agent_manager.get_or_create(agent_session_id)
                    diagram_data['diagram_type'] = diagram_type
                    agent.update_diagram_state(diagram_data)

                    updated_context = {
                        'diagram_type': diagram_type,
                        'active_panel': voice_sessions[voice_session_id].get('active_panel', 'none'),
                        'conversation_history': voice_sessions[voice_session_id].get('conversation_history', []),
                        'selected_nodes': session_context.get('selected_nodes', []),
                        'diagram_data': diagram_data
                    }
                    new_instructions = build_voice_instructions(updated_context)
                    try:
                        omni_client = get_session_omni_client(voice_session_id)
                        if omni_client:
                            await omni_client.update_instructions(new_instructions)
                    except (RuntimeError, ConnectionError, AttributeError) as e:
                        if "close" in str(e).lower() or "closed" in str(e).lower():
                            logger.debug("WebSocket closed, skipping instruction update: %s", e)
                        else:
                            raise

                    logger.debug("Item added: category %d, item %d -> %s", category_index, item_index, target)
                    return True

                # Special handling for brace_map subparts (part_index + subpart_index)
                if diagram_type == 'brace_map' and part_index is not None and subpart_index is not None:
                    logger.info("Adding subpart to part %d at position %d: %s", part_index, subpart_index, target)

                    update_payload = {
                        'text': target,
                        'part_index': part_index,
                        'subpart_index': subpart_index
                    }

                    await safe_websocket_send(websocket, {
                        'type': 'diagram_update',
                        'action': 'add_nodes',
                        'updates': [update_payload]
                    })

                    # Update session context
                    diagram_data = session_context.get('diagram_data', {})
                    parts = diagram_data.get('parts', [])

                    if 0 <= part_index < len(parts):
                        part = parts[part_index]
                        if isinstance(part, dict):
                            if 'subparts' not in part or not isinstance(part['subparts'], list):
                                part['subparts'] = []

                            if subpart_index < len(part['subparts']):
                                part['subparts'].insert(subpart_index, {'name': target})
                            else:
                                while len(part['subparts']) < subpart_index:
                                    part['subparts'].append({'name': ''})
                                part['subparts'].insert(subpart_index, {'name': target})

                    # Update agent state
                    agent_session_id = get_agent_session_id(voice_session_id)
                    agent = voice_agent_manager.get_or_create(agent_session_id)
                    diagram_data['diagram_type'] = diagram_type
                    agent.update_diagram_state(diagram_data)

                    updated_context = {
                        'diagram_type': diagram_type,
                        'active_panel': voice_sessions[voice_session_id].get('active_panel', 'none'),
                        'conversation_history': voice_sessions[voice_session_id].get('conversation_history', []),
                        'selected_nodes': session_context.get('selected_nodes', []),
                        'diagram_data': diagram_data
                    }
                    new_instructions = build_voice_instructions(updated_context)
                    try:
                        omni_client = get_session_omni_client(voice_session_id)
                        if omni_client:
                            await omni_client.update_instructions(new_instructions)
                    except (RuntimeError, ConnectionError, AttributeError) as e:
                        if "close" in str(e).lower() or "closed" in str(e).lower():
                            logger.debug("WebSocket closed, skipping instruction update: %s", e)
                        else:
                            raise

                    logger.debug("Subpart added: part %d, subpart %d -> %s", part_index, subpart_index, target)
                    return True

                # Special handling for mindmap children (branch_index + child_index)
                if diagram_type == 'mindmap' and branch_index is not None and child_index is not None:
                    logger.info("Adding child to branch %d at position %d: %s", branch_index, child_index, target)

                    update_payload = {
                        'text': target,
                        'branch_index': branch_index,
                        'child_index': child_index
                    }

                    await safe_websocket_send(websocket, {
                        'type': 'diagram_update',
                        'action': 'add_nodes',
                        'updates': [update_payload]
                    })

                    # Update session context
                    diagram_data = session_context.get('diagram_data', {})
                    children = diagram_data.get('children', [])

                    if 0 <= branch_index < len(children):
                        branch = children[branch_index]
                        if isinstance(branch, dict):
                            if 'children' not in branch or not isinstance(branch['children'], list):
                                branch['children'] = []

                            child_id = f"sub_{branch_index}_{len(branch['children'])}"
                            new_child = {'id': child_id, 'label': target, 'text': target, 'children': []}

                            if child_index < len(branch['children']):
                                branch['children'].insert(child_index, new_child)
                            else:
                                branch['children'].append(new_child)

                    # Update agent state
                    agent_session_id = get_agent_session_id(voice_session_id)
                    agent = voice_agent_manager.get_or_create(agent_session_id)
                    diagram_data['diagram_type'] = diagram_type
                    agent.update_diagram_state(diagram_data)

                    updated_context = {
                        'diagram_type': diagram_type,
                        'active_panel': voice_sessions[voice_session_id].get('active_panel', 'none'),
                        'conversation_history': voice_sessions[voice_session_id].get('conversation_history', []),
                        'selected_nodes': session_context.get('selected_nodes', []),
                        'diagram_data': diagram_data
                    }
                    new_instructions = build_voice_instructions(updated_context)
                    try:
                        omni_client = get_session_omni_client(voice_session_id)
                        if omni_client:
                            await omni_client.update_instructions(new_instructions)
                    except (RuntimeError, ConnectionError, AttributeError) as e:
                        if "close" in str(e).lower() or "closed" in str(e).lower():
                            logger.debug("WebSocket closed, skipping instruction update: %s", e)
                        else:
                            raise

                    logger.debug("Child added: branch %d, child %d -> %s", branch_index, child_index, target)
                    return True

                # Special handling for concept_map relationships (from, to, label)
                if diagram_type == 'concept_map' and command.get('from') and command.get('to') and command.get('label'):
                    from_concept = command.get('from')
                    to_concept = command.get('to')
                    rel_label = command.get('label')

                    logger.info("Adding relationship: %s --[%s]--> %s", from_concept, rel_label, to_concept)

                    update_payload = {
                        'from': from_concept,
                        'to': to_concept,
                        'label': rel_label
                    }

                    await safe_websocket_send(websocket, {
                        'type': 'diagram_update',
                        'action': 'add_nodes',
                        'updates': [update_payload]
                    })

                    # Update session context
                    diagram_data = session_context.get('diagram_data', {})
                    relationships = diagram_data.get('relationships', [])
                    relationships.append({'from': from_concept, 'to': to_concept, 'label': rel_label})
                    diagram_data['relationships'] = relationships

                    # Update agent state
                    agent_session_id = get_agent_session_id(voice_session_id)
                    agent = voice_agent_manager.get_or_create(agent_session_id)
                    diagram_data['diagram_type'] = diagram_type
                    agent.update_diagram_state(diagram_data)

                    updated_context = {
                        'diagram_type': diagram_type,
                        'active_panel': voice_sessions[voice_session_id].get('active_panel', 'none'),
                        'conversation_history': voice_sessions[voice_session_id].get('conversation_history', []),
                        'selected_nodes': session_context.get('selected_nodes', []),
                        'diagram_data': diagram_data
                    }
                    new_instructions = build_voice_instructions(updated_context)
                    try:
                        omni_client = get_session_omni_client(voice_session_id)
                        if omni_client:
                            await omni_client.update_instructions(new_instructions)
                    except (RuntimeError, ConnectionError, AttributeError) as e:
                        if "close" in str(e).lower() or "closed" in str(e).lower():
                            logger.debug("WebSocket closed, skipping instruction update: %s", e)
                        else:
                            raise

                    logger.debug("Relationship added: %s --[%s]--> %s", from_concept, rel_label, to_concept)
                    return True

                # Special handling for flow_map substeps
                if diagram_type == 'flow_map' and step_index is not None:
                    # Adding a substep to a specific step
                    logger.info("Adding substep to step %d at position %d: %s", step_index, substep_index, target)

                    # Build update payload with step_index and substep_index
                    update_payload = {
                        'text': target,
                        'step_index': step_index
                    }
                    if substep_index is not None:
                        update_payload['substep_index'] = substep_index

                    await safe_websocket_send(websocket, {
                        'type': 'diagram_update',
                        'action': 'add_nodes',
                        'updates': [update_payload]
                    })

                    # Update session context
                    diagram_data = session_context.get('diagram_data', {})
                    steps = diagram_data.get('steps', [])
                    substeps = diagram_data.get('substeps', [])

                    if 0 <= step_index < len(steps):
                        if isinstance(steps[step_index], str):
                            step_name = steps[step_index]
                        else:
                            step_name = steps[step_index].get('text', '')

                        # Find or create substeps entry for this step
                        substeps_entry = None
                        for entry in substeps:
                            if isinstance(entry, dict) and entry.get('step') == step_name:
                                substeps_entry = entry
                                break

                        if not substeps_entry:
                            if not isinstance(substeps, list):
                                diagram_data['substeps'] = []
                                substeps = diagram_data['substeps']
                            substeps_entry = {'step': step_name, 'substeps': []}
                            substeps.append(substeps_entry)

                        # Add substep at specified position
                        if not isinstance(substeps_entry.get('substeps'), list):
                            substeps_entry['substeps'] = []

                        if substep_index is not None:
                            if substep_index < len(substeps_entry['substeps']):
                                substeps_entry['substeps'].insert(substep_index, target)
                            else:
                                # Pad with empty strings if needed
                                while len(substeps_entry['substeps']) < substep_index:
                                    substeps_entry['substeps'].append('')
                                substeps_entry['substeps'].insert(substep_index, target)
                        else:
                            substeps_entry['substeps'].append(target)

                    # Update agent state
                    agent_session_id = get_agent_session_id(voice_session_id)
                    agent = voice_agent_manager.get_or_create(agent_session_id)
                    diagram_data['diagram_type'] = diagram_type
                    agent.update_diagram_state(diagram_data)

                    updated_context = {
                        'diagram_type': diagram_type,
                        'active_panel': voice_sessions[voice_session_id].get('active_panel', 'none'),
                        'conversation_history': voice_sessions[voice_session_id].get('conversation_history', []),
                        'selected_nodes': session_context.get('selected_nodes', []),
                        'diagram_data': diagram_data
                    }
                    new_instructions = build_voice_instructions(updated_context)
                    try:
                        omni_client = get_session_omni_client(voice_session_id)
                        if omni_client:
                            await omni_client.update_instructions(new_instructions)
                    except (RuntimeError, ConnectionError, AttributeError) as e:
                        if "close" in str(e).lower() or "closed" in str(e).lower():
                            logger.debug("WebSocket closed, skipping instruction update: %s", e)
                        else:
                            raise

                    logger.debug("Substep added: step %d, substep %d -> %s", step_index, substep_index, target)
                    return True

                # Get current nodes
                nodes = session_context.get('diagram_data', {}).get('children', [])
                prefix_map = get_diagram_prefix_map()
                prefix = prefix_map.get(diagram_type, 'node')

                # If node_index is specified, check if node exists at that position
                if add_node_index is not None:
                    # Check if node already exists at this position
                    if 0 <= add_node_index < len(nodes):
                        # Node exists - use update_node instead
                        logger.info(
                            "Node exists at index %d, updating instead of adding: %s",
                            add_node_index, target
                        )
                        existing_node = nodes[add_node_index]
                        if isinstance(existing_node, dict):
                            existing_node_id = existing_node.get('id')
                        else:
                            existing_node_id = f"{prefix}_{add_node_index}"

                        await safe_websocket_send(websocket, {
                            'type': 'diagram_update',
                            'action': 'update_nodes',
                            'updates': [{
                                'node_id': existing_node_id,
                                'new_text': target
                            }]
                        })

                        # Update session context
                        if isinstance(existing_node, dict):
                            existing_node['text'] = target
                        else:
                            nodes[add_node_index] = target
                    else:
                        # Node doesn't exist - insert at specified position
                        logger.info("Adding node at position %d: %s", add_node_index, target)
                        new_node = {
                            'id': f"{prefix}_{add_node_index}",
                            'index': add_node_index,
                            'text': target
                        }

                        # Insert at specified position (pad with None if needed)
                        while len(nodes) < add_node_index:
                            nodes.append(None)
                        nodes.insert(add_node_index, new_node)

                        # Build update payload with diagram-specific fields
                        update_payload = {'text': target, 'index': add_node_index}

                        # Add category if specified (for double bubble map, multi-flow map)
                        category = command.get('category')
                        if category:
                            update_payload['category'] = category

                        # Add left/right if specified (for bridge map analogies)
                        left = command.get('left')
                        right = command.get('right')
                        if left and right:
                            update_payload['left'] = left
                            update_payload['right'] = right

                        # Send update with position information and diagram-specific fields
                        await safe_websocket_send(websocket, {
                            'type': 'diagram_update',
                            'action': 'add_nodes',
                            'updates': [update_payload]
                        })
                else:
                    # No position specified - add to end (default behavior)
                    logger.info("Adding node to end: %s", target)
                    new_node = {
                        'id': f"{prefix}_{len(nodes)}",
                        'index': len(nodes),
                        'text': target
                    }
                    nodes.append(new_node)

                    # Build update payload with diagram-specific fields
                    update_payload = {'text': target}

                    # Add category if specified (for double bubble map, multi-flow map)
                    category = command.get('category')
                    if category:
                        update_payload['category'] = category

                    # Add left/right if specified (for bridge map analogies)
                    left = command.get('left')
                    right = command.get('right')
                    if left and right:
                        update_payload['left'] = left
                        update_payload['right'] = right

                    await safe_websocket_send(websocket, {
                        'type': 'diagram_update',
                        'action': 'add_nodes',
                        'updates': [update_payload]
                    })

                # Update agent state and instructions
                # CRITICAL: Agent is scoped to diagram_session_id, not voice_session_id
                agent_session_id = get_agent_session_id(voice_session_id)
                agent = voice_agent_manager.get_or_create(agent_session_id)
                diagram_data = session_context.get('diagram_data', {})
                diagram_data['diagram_type'] = voice_sessions[voice_session_id].get('diagram_type')
                agent.update_diagram_state(diagram_data)

                updated_context = {
                    'diagram_type': voice_sessions[voice_session_id].get('diagram_type'),
                    'active_panel': voice_sessions[voice_session_id].get('active_panel', 'none'),
                    'conversation_history': voice_sessions[voice_session_id].get('conversation_history', []),
                    'selected_nodes': session_context.get('selected_nodes', []),
                    'diagram_data': diagram_data
                }
                new_instructions = build_voice_instructions(updated_context)
                omni_client = get_session_omni_client(voice_session_id)
                if omni_client:
                    await omni_client.update_instructions(new_instructions)

                logger.debug("Node added: %s", target)
                return True
            else:
                count = command.get('count', 1)
                logger.debug("Opening node palette for adding %d node(s)", count)
                await safe_websocket_send(websocket, {
                    'type': 'action',
                    'action': 'open_node_palette',
                    'params': {'count': count}
                })
                return True

        elif action == 'delete_node':
            diagram_type = voice_sessions[voice_session_id].get('diagram_type')
            step_index = command.get('step_index')  # For flow_map substeps
            substep_index = command.get('substep_index')  # For flow_map substeps
            category_index = command.get('category_index')  # For tree_map items
            item_index = command.get('item_index')  # For tree_map items
            part_index = command.get('part_index')  # For brace_map subparts
            subpart_index = command.get('subpart_index')  # For brace_map subparts
            branch_index = command.get('branch_index')  # For mindmap children
            child_index = command.get('child_index')  # For mindmap children
            relationship_index = command.get('relationship_index')  # For concept_map relationships

            # Special handling for tree_map items
            if diagram_type == 'tree_map' and category_index is not None and item_index is not None:
                logger.info("Deleting item at category %d, item %d", category_index, item_index)

                delete_payload = {
                    'category_index': category_index,
                    'item_index': item_index
                }

                await safe_websocket_send(websocket, {
                    'type': 'diagram_update',
                    'action': 'remove_nodes',
                    'updates': [delete_payload]
                })

                # Update session context
                diagram_data = session_context.get('diagram_data', {})
                children = diagram_data.get('children', [])

                if 0 <= category_index < len(children):
                    category = children[category_index]
                    if isinstance(category, dict) and isinstance(category.get('children'), list):
                        if 0 <= item_index < len(category['children']):
                            category['children'].pop(item_index)

                # Update agent state
                agent_session_id = get_agent_session_id(voice_session_id)
                agent = voice_agent_manager.get_or_create(agent_session_id)
                diagram_data['diagram_type'] = diagram_type
                agent.update_diagram_state(diagram_data)

                updated_context = {
                    'diagram_type': diagram_type,
                    'active_panel': voice_sessions[voice_session_id].get('active_panel', 'none'),
                    'conversation_history': voice_sessions[voice_session_id].get('conversation_history', []),
                    'selected_nodes': session_context.get('selected_nodes', []),
                    'diagram_data': diagram_data
                }
                new_instructions = build_voice_instructions(updated_context)
                try:
                    omni_client = get_session_omni_client(voice_session_id)
                    if omni_client:
                        await omni_client.update_instructions(new_instructions)
                except (RuntimeError, ConnectionError, AttributeError) as e:
                    if "close" in str(e).lower() or "closed" in str(e).lower():
                        logger.debug("WebSocket closed, skipping instruction update: %s", e)
                    else:
                        raise

                logger.debug("Item deleted: category %d, item %d", category_index, item_index)
                return True

            # Special handling for brace_map subparts
            if diagram_type == 'brace_map' and part_index is not None and subpart_index is not None:
                logger.info("Deleting subpart at part %d, subpart %d", part_index, subpart_index)

                delete_payload = {
                    'part_index': part_index,
                    'subpart_index': subpart_index
                }

                await safe_websocket_send(websocket, {
                    'type': 'diagram_update',
                    'action': 'remove_nodes',
                    'updates': [delete_payload]
                })

                # Update session context
                diagram_data = session_context.get('diagram_data', {})
                parts = diagram_data.get('parts', [])

                if 0 <= part_index < len(parts):
                    part = parts[part_index]
                    if isinstance(part, dict) and isinstance(part.get('subparts'), list):
                        if 0 <= subpart_index < len(part['subparts']):
                            part['subparts'].pop(subpart_index)

                # Update agent state
                agent_session_id = get_agent_session_id(voice_session_id)
                agent = voice_agent_manager.get_or_create(agent_session_id)
                diagram_data['diagram_type'] = diagram_type
                agent.update_diagram_state(diagram_data)

                updated_context = {
                    'diagram_type': diagram_type,
                    'active_panel': voice_sessions[voice_session_id].get('active_panel', 'none'),
                    'conversation_history': voice_sessions[voice_session_id].get('conversation_history', []),
                    'selected_nodes': session_context.get('selected_nodes', []),
                    'diagram_data': diagram_data
                }
                new_instructions = build_voice_instructions(updated_context)
                try:
                    omni_client = get_session_omni_client(voice_session_id)
                    if omni_client:
                        await omni_client.update_instructions(new_instructions)
                except (ConnectionError, RuntimeError, AttributeError, ValueError, WebSocketDisconnect) as e:
                    if "close" in str(e).lower() or "closed" in str(e).lower():
                        logger.debug("WebSocket closed, skipping instruction update: %s", e)
                    else:
                        raise

                logger.debug("Subpart deleted: part %d, subpart %d", part_index, subpart_index)
                return True

            # Special handling for mindmap children
            if diagram_type == 'mindmap' and branch_index is not None and child_index is not None:
                logger.info("Deleting child at branch %d, child %d", branch_index, child_index)

                delete_payload = {
                    'branch_index': branch_index,
                    'child_index': child_index
                }

                await safe_websocket_send(websocket, {
                    'type': 'diagram_update',
                    'action': 'remove_nodes',
                    'updates': [delete_payload]
                })

                # Update session context
                diagram_data = session_context.get('diagram_data', {})
                children = diagram_data.get('children', [])

                if 0 <= branch_index < len(children):
                    branch = children[branch_index]
                    if isinstance(branch, dict) and isinstance(branch.get('children'), list):
                        if 0 <= child_index < len(branch['children']):
                            branch['children'].pop(child_index)

                # Update agent state
                agent_session_id = get_agent_session_id(voice_session_id)
                agent = voice_agent_manager.get_or_create(agent_session_id)
                diagram_data['diagram_type'] = diagram_type
                agent.update_diagram_state(diagram_data)

                updated_context = {
                    'diagram_type': diagram_type,
                    'active_panel': voice_sessions[voice_session_id].get('active_panel', 'none'),
                    'conversation_history': voice_sessions[voice_session_id].get('conversation_history', []),
                    'selected_nodes': session_context.get('selected_nodes', []),
                    'diagram_data': diagram_data
                }
                new_instructions = build_voice_instructions(updated_context)
                try:
                    omni_client = get_session_omni_client(voice_session_id)
                    if omni_client:
                        await omni_client.update_instructions(new_instructions)
                except (RuntimeError, ConnectionError, AttributeError) as e:
                    if "close" in str(e).lower() or "closed" in str(e).lower():
                        logger.debug("WebSocket closed, skipping instruction update: %s", e)
                    else:
                        raise

                logger.debug("Child deleted: branch %d, child %d", branch_index, child_index)
                return True

            # Special handling for concept_map relationships
            if diagram_type == 'concept_map' and relationship_index is not None:
                logger.info("Deleting relationship at index %d", relationship_index)

                delete_payload = {
                    'relationship_index': relationship_index
                }

                await safe_websocket_send(websocket, {
                    'type': 'diagram_update',
                    'action': 'remove_nodes',
                    'updates': [delete_payload]
                })

                # Update session context
                diagram_data = session_context.get('diagram_data', {})
                relationships = diagram_data.get('relationships', [])

                if 0 <= relationship_index < len(relationships):
                    relationships.pop(relationship_index)

                # Update agent state
                agent_session_id = get_agent_session_id(voice_session_id)
                agent = voice_agent_manager.get_or_create(agent_session_id)
                diagram_data['diagram_type'] = diagram_type
                agent.update_diagram_state(diagram_data)

                updated_context = {
                    'diagram_type': diagram_type,
                    'active_panel': voice_sessions[voice_session_id].get('active_panel', 'none'),
                    'conversation_history': voice_sessions[voice_session_id].get('conversation_history', []),
                    'selected_nodes': session_context.get('selected_nodes', []),
                    'diagram_data': diagram_data
                }
                new_instructions = build_voice_instructions(updated_context)
                try:
                    omni_client = get_session_omni_client(voice_session_id)
                    if omni_client:
                        await omni_client.update_instructions(new_instructions)
                except (RuntimeError, ConnectionError, AttributeError) as e:
                    if "close" in str(e).lower() or "closed" in str(e).lower():
                        logger.debug("WebSocket closed, skipping instruction update: %s", e)
                    else:
                        raise

                logger.debug("Relationship deleted: index %d", relationship_index)
                return True

            # Special handling for flow_map substeps
            if diagram_type == 'flow_map' and step_index is not None and substep_index is not None:
                logger.info("Deleting substep at step %d, substep %d", step_index, substep_index)

                # Build delete payload with step_index and substep_index
                delete_payload = {
                    'step_index': step_index,
                    'substep_index': substep_index
                }

                await safe_websocket_send(websocket, {
                    'type': 'diagram_update',
                    'action': 'remove_nodes',
                    'updates': [delete_payload]
                })

                # Update session context
                diagram_data = session_context.get('diagram_data', {})
                steps = diagram_data.get('steps', [])
                substeps = diagram_data.get('substeps', [])

                if 0 <= step_index < len(steps):
                    if isinstance(steps[step_index], str):
                        step_name = steps[step_index]
                    else:
                        step_name = steps[step_index].get('text', '')

                    # Find substeps entry for this step
                    for entry in substeps:
                        if isinstance(entry, dict) and entry.get('step') == step_name:
                            if isinstance(entry.get('substeps'), list) and 0 <= substep_index < len(entry['substeps']):
                                entry['substeps'].pop(substep_index)
                                break

                # Update agent state
                agent_session_id = get_agent_session_id(voice_session_id)
                agent = voice_agent_manager.get_or_create(agent_session_id)
                diagram_data['diagram_type'] = diagram_type
                agent.update_diagram_state(diagram_data)

                updated_context = {
                    'diagram_type': diagram_type,
                    'active_panel': voice_sessions[voice_session_id].get('active_panel', 'none'),
                    'conversation_history': voice_sessions[voice_session_id].get('conversation_history', []),
                    'selected_nodes': session_context.get('selected_nodes', []),
                    'diagram_data': diagram_data
                }
                new_instructions = build_voice_instructions(updated_context)
                try:
                    omni_client = get_session_omni_client(voice_session_id)
                    if omni_client:
                        await omni_client.update_instructions(new_instructions)
                except (RuntimeError, ConnectionError, AttributeError) as e:
                    if "close" in str(e).lower() or "closed" in str(e).lower():
                        logger.debug("WebSocket closed, skipping instruction update: %s", e)
                    else:
                        raise

                logger.debug("Substep deleted: step %d, substep %d", step_index, substep_index)
                return True

            # Resolve node by index or by target text
            resolved_node_id = command.get('node_id')
            resolved_node_index = node_index

            nodes = session_context.get('diagram_data', {}).get('children', [])

            if not resolved_node_id and resolved_node_index is not None:
                diagram_type = voice_sessions[voice_session_id].get('diagram_type', 'circle_map')
                prefix_map = get_diagram_prefix_map()
                prefix = prefix_map.get(diagram_type, 'node')
                resolved_node_id = f"{prefix}_{resolved_node_index}"

            # Also try to resolve by target text if we have it
            if not resolved_node_id and target:
                for idx, node in enumerate(nodes):
                    node_text = node.get('text') if isinstance(node, dict) else str(node)
                    if target in node_text or node_text in target:
                        diagram_type = voice_sessions[voice_session_id].get('diagram_type', 'circle_map')
                        prefix_map = get_diagram_prefix_map()
                        prefix = prefix_map.get(diagram_type, 'node')
                        resolved_node_id = f"{prefix}_{idx}"
                        resolved_node_index = idx
                        break

            if resolved_node_id:
                diagram_type = voice_sessions[voice_session_id].get('diagram_type')

                # Build delete payload with diagram-specific fields
                delete_payload = resolved_node_id

                # For diagrams with categories, include category in delete payload
                # This helps frontend identify which category array to remove from
                category = command.get('category')
                if category and diagram_type in ['double_bubble_map', 'multi_flow_map']:
                    # Send structured delete payload with category
                    delete_payload = {
                        'node_id': resolved_node_id,
                        'category': category
                    }

                if category:
                    logger.info("Deleting node: %s (category: %s)", resolved_node_id, category)
                else:
                    logger.info("Deleting node: %s", resolved_node_id)
                await safe_websocket_send(websocket, {
                    'type': 'diagram_update',
                    'action': 'remove_nodes',
                    'updates': [delete_payload]
                })

                # CRITICAL: Update session context immediately
                if resolved_node_index is not None and 0 <= resolved_node_index < len(nodes):
                    nodes.pop(resolved_node_index)
                    logger.debug("Node %d removed from session context", resolved_node_index)

                # Update agent state and instructions
                # CRITICAL: Agent is scoped to diagram_session_id, not voice_session_id
                agent_session_id = get_agent_session_id(voice_session_id)
                agent = voice_agent_manager.get_or_create(agent_session_id)
                diagram_data = session_context.get('diagram_data', {})
                diagram_data['diagram_type'] = voice_sessions[voice_session_id].get('diagram_type')
                agent.update_diagram_state(diagram_data)

                updated_context = {
                    'diagram_type': voice_sessions[voice_session_id].get('diagram_type'),
                    'active_panel': voice_sessions[voice_session_id].get('active_panel', 'none'),
                    'conversation_history': voice_sessions[voice_session_id].get('conversation_history', []),
                    'selected_nodes': session_context.get('selected_nodes', []),
                    'diagram_data': diagram_data
                }
                new_instructions = build_voice_instructions(updated_context)
                omni_client = get_session_omni_client(voice_session_id)
                if omni_client:
                    await omni_client.update_instructions(new_instructions)

                logger.debug("Node deleted: %s", resolved_node_id)
                return True
            else:
                logger.warning("Could not resolve node_id for deletion: target=%s, node_index=%s", target, node_index)
                return False

        return False

    except (ValueError, KeyError, RuntimeError, AttributeError) as e:
        logger.error("Diagram update execution error: %s", e, exc_info=True)
        return False


async def process_voice_command(
    websocket: WebSocket,
    voice_session_id: str,
    command_text: str,
    session_context: Dict[str, Any],
    is_text_message: bool = False
) -> bool:
    """
    Process a voice command (from transcription or text message).

    Handles two cases:
    1. Paragraph processing: Long text inputs are processed with Qwen Plus to extract diagram content
    2. Command processing: Short commands are parsed with Qwen Turbo for intention checking

    Returns True if command was executed, False if it should be sent to Omni for conversational response.

    Args:
        websocket: WebSocket connection
        voice_session_id: Voice session ID
        command_text: Command text from user
        session_context: Current session context
        is_text_message: True if this is from text input (lower confidence threshold)

    Note:
        - Paragraphs (long text) are processed with Qwen Plus for content extraction
        - Commands (short text) are parsed with Qwen Turbo (classification model) for intention checking
        - No keyword detection - all parsing is done by LLM
    """
    try:
        # CRITICAL: Check if input is a paragraph (long text for processing)
        # Common case: Teachers paste whole paragraphs expecting diagram generation
        if is_paragraph_text(command_text):
            logger.info("Detected paragraph input (length: %d), processing with Qwen Plus", len(command_text))
            return await process_paragraph_with_qwen_plus(
                websocket, voice_session_id, command_text, session_context
            )

        # Otherwise, process as a command
        # Get the persistent agent for this session
        # CRITICAL: Agent is scoped to diagram_session_id, not voice_session_id
        # This ensures the agent is scoped to the diagram session, not the WebSocket connection
        agent_session_id = get_agent_session_id(voice_session_id)
        agent = voice_agent_manager.get_or_create(agent_session_id)

        # Get user info from session for token tracking
        session = get_voice_session(voice_session_id)
        user_id = None
        organization_id = None
        if session:
            user_id_str = session.get('user_id')
            # Convert user_id to int if it's a string (voice_sessions stores as string)
            if user_id_str:
                try:
                    user_id = int(user_id_str) if isinstance(user_id_str, str) else user_id_str
                    # Get organization_id from user if available (use cache)
                    if redis_user_cache:
                        try:
                            user = redis_user_cache.get_by_id(user_id)
                            if user:
                                organization_id = user.organization_id
                        except (AttributeError, KeyError) as e:
                            logger.debug("Error getting organization_id for token tracking: %s", e)
                except (ValueError, TypeError) as e:
                    logger.debug("Error converting user_id for token tracking: %s", e)

        # CRITICAL: Get diagram_type directly from voice_sessions (source of truth)
        # session_context may be stale when diagram type changes
        # Always check voice_sessions first, then fallback to session_context
        diagram_type = None
        if voice_session_id in voice_sessions:
            diagram_type = voice_sessions[voice_session_id].get('diagram_type')
        if not diagram_type and session:
            diagram_type = session.get('diagram_type')
        if not diagram_type:
            diagram_type = session_context.get('diagram_type')

        if not diagram_type:
            logger.warning("VOIC | Could not determine diagram_type for voice command, defaulting to circle_map")
            diagram_type = 'circle_map'

        logger.debug("VOIC | Using diagram_type=%s for voice command processing", diagram_type)

        # Process command through LLM (Qwen Turbo) for intention checking
        # LLM parses the command and returns structured action JSON (no keyword detection)
        # Pass user tracking info for token tracking
        command = await agent.process_command(
            command_text,
            user_id=user_id,
            organization_id=organization_id,
            voice_session_id=voice_session_id,
            diagram_type=diagram_type
        )

        action = command['action']
        target = command.get('target')
        node_index = command.get('node_index')
        confidence = command.get('confidence', 0.0)

        logger.debug(
            "Command processed: action=%s, target=%s, node_index=%s, "
            "confidence=%s, is_text=%s",
            action, target, node_index, confidence, is_text_message
        )

        # Only proceed if confidence is high enough (except for UI actions)
        ui_actions = [
            'open_thinkguide', 'close_thinkguide',
            'open_node_palette', 'close_node_palette',
            'open_mindmate', 'close_mindmate', 'close_all_panels',
            'select_node', 'explain_node',
            'ask_thinkguide', 'ask_mindmate', 'auto_complete', 'help'
        ]

        # For text messages, use lower confidence threshold (0.5) since they're more explicit
        # This allows conversational requests like "can you change..." to be executed
        confidence_threshold = 0.5 if is_text_message else 0.7

        # Check if this is a diagram update action
        diagram_update_actions = ['update_center', 'update_node', 'add_node', 'delete_node']
        if action in diagram_update_actions:
            # For diagram updates, execute if confidence meets threshold
            if confidence >= confidence_threshold:
                return await execute_diagram_update(
                    websocket, voice_session_id, action, command, session_context
                )
            else:
                logger.debug(
                    "Low confidence (%s) for diagram update '%s', threshold=%s",
                    confidence, action, confidence_threshold
                )
                return False

        # For non-diagram-update actions, check confidence
        if action not in ui_actions and confidence < confidence_threshold:
            logger.debug("Low confidence (%s), should send to Omni for conversational response", confidence)
            return False

        # Handle UI actions first
        if action == 'open_thinkguide':
            # Redirect to MindMate
            logger.debug("Opening MindMate panel")
            await safe_websocket_send(websocket, {
                'type': 'action',
                'action': 'open_mindmate',
                'params': {}
            })
            return True

        elif action == 'close_thinkguide':
            # Redirect to MindMate
            logger.debug("Closing MindMate panel")
            await safe_websocket_send(websocket, {
                'type': 'action',
                'action': 'close_mindmate',
                'params': {}
            })
            return True

        elif action == 'open_node_palette':
            logger.debug("Opening Node Palette")
            await safe_websocket_send(websocket, {
                'type': 'action',
                'action': 'open_node_palette',
                'params': {}
            })
            return True

        elif action == 'close_node_palette':
            logger.debug("Closing Node Palette")
            await safe_websocket_send(websocket, {
                'type': 'action',
                'action': 'close_node_palette',
                'params': {}
            })
            return True

        elif action == 'open_mindmate':
            logger.debug("Opening MindMate AI panel")
            await safe_websocket_send(websocket, {
                'type': 'action',
                'action': 'open_mindmate',
                'params': {}
            })
            return True

        elif action == 'close_mindmate':
            logger.debug("Closing MindMate AI panel")
            await safe_websocket_send(websocket, {
                'type': 'action',
                'action': 'close_mindmate',
                'params': {}
            })
            return True

        elif action == 'close_all_panels':
            logger.debug("Closing all panels")
            await safe_websocket_send(websocket, {
                'type': 'action',
                'action': 'close_all_panels',
                'params': {}
            })
            return True

        # Interaction control
        elif action == 'auto_complete':
            logger.info("Triggering AI auto-complete from text/voice command")
            await safe_websocket_send(websocket, {
                'type': 'action',
                'action': 'auto_complete',
                'params': {}
            })
            # Send acknowledgment message to user via Omni
            try:
                # Create a response acknowledging the action
                omni_client = get_session_omni_client(voice_session_id)
                if omni_client:
                    await omni_client.create_response(instructions="好的，我正在帮你自动完成图表。")
            except (RuntimeError, ConnectionError, AttributeError) as e:
                logger.debug("Could not send acknowledgment to Omni: %s", e)
            return True

        elif action == 'ask_thinkguide' and target:
            # Redirect to MindMate
            logger.debug("Sending question to MindMate: %s", target)
            await safe_websocket_send(websocket, {
                'type': 'action',
                'action': 'ask_mindmate',
                'params': {'message': target}
            })
            return True

        elif action == 'ask_mindmate' and target:
            logger.debug("Sending question to MindMate: %s", target)
            await safe_websocket_send(websocket, {
                'type': 'action',
                'action': 'ask_mindmate',
                'params': {'message': target}
            })
            return True

        elif action == 'select_node':
            node_id = command.get('node_id')
            resolved_node_id = node_id

            # Resolve node_id from index if needed
            if node_index is not None and not resolved_node_id:
                diagram_type = voice_sessions[voice_session_id].get('diagram_type', 'circle_map')
                prefix_map = get_diagram_prefix_map()
                prefix = prefix_map.get(diagram_type, 'node')
                resolved_node_id = f"{prefix}_{node_index}"

            if resolved_node_id:
                logger.debug("Selecting node: %s", resolved_node_id)
                await safe_websocket_send(websocket, {
                    'type': 'action',
                    'action': 'select_node',
                    'params': {'node_id': resolved_node_id, 'node_index': node_index}
                })
            return True

        elif action == 'explain_node':
            node_id = command.get('node_id')
            node_label = target
            if (node_id or node_index is not None) and node_label:
                resolved_node_id = node_id
                if node_index is not None and not resolved_node_id:
                    nodes = session_context.get('diagram_data', {}).get('children', [])
                    if 0 <= node_index < len(nodes):
                        node = nodes[node_index]
                        resolved_node_id = node.get('id') if isinstance(node, dict) else f"context_{node_index}"
                        if not node_label:
                            node_label = node.get('text', node.get('label', ''))

                if resolved_node_id and node_label:
                    logger.debug("Explaining node: %s (%s)", resolved_node_id, node_label)
                    await safe_websocket_send(websocket, {
                        'type': 'action',
                        'action': 'explain_node',
                        'params': {
                            'node_id': resolved_node_id,
                            'node_label': node_label,
                            'prompt': f'请解释一下"{node_label}"这个概念，用简单的语言，适合K12学生理解。'
                        }
                    })
            return True

        elif action == 'help':
            logger.debug("User requested help - opening MindMate")
            await safe_websocket_send(websocket, {
                'type': 'action',
                'action': 'open_mindmate',
                'params': {}
            })
            return True

        elif action == 'none':
            logger.debug("No command detected - should send to Omni for conversational response")
            return False

        # Unknown action - send to Omni
        return False

    except (ValueError, KeyError, RuntimeError, AttributeError) as e:
        logger.error("Command processing error: %s", e, exc_info=True)
        return False  # Send to Omni on error


@router.websocket("/ws/voice/{diagram_session_id}")
async def voice_conversation(
    websocket: WebSocket,
    diagram_session_id: str
):
    """
    WebSocket endpoint for real-time voice conversation.

    Protocol:
    Client -> Server:
    - {"type": "start", "diagram_type": str, "active_panel": str, "context": {...}}
    - {"type": "audio", "data": str}  # base64 PCM audio
    - {"type": "context_update", "active_panel": str, "context": {...}}
    - {"type": "stop"}

    Server -> Client:
    - {"type": "connected", "session_id": str}
    - {"type": "transcription", "text": str}
    - {"type": "text_chunk", "text": str}
    - {"type": "audio_chunk", "audio": str}  # base64
    - {"type": "speech_started", "audio_start_ms": int}
    - {"type": "speech_stopped", "audio_end_ms": int}
    - {"type": "response_done"}
    - {"type": "action", "action": str, "params": {...}}
    - {"type": "error", "error": str}
    """
    # Accept connection first (required before we can close it or use it)
    await websocket.accept()

    # Check if voice agent feature is enabled
    if not config.FEATURE_VOICE_AGENT:
        await websocket.close(code=4003, reason="Voice agent feature is disabled")
        logger.warning("Voice agent WebSocket connection rejected: feature disabled")
        return

    # Authenticate AFTER accepting - use manual session management to avoid holding connection
    current_user = None
    try:
        # Get token from query params or cookies
        token = websocket.query_params.get('token')
        if not token:  # Handles both None and '' (empty string)
            token = websocket.cookies.get('access_token')

        if not token:
            await websocket.close(code=4001, reason="No authentication token")
            logger.warning("WebSocket auth failed: No token provided")
            return

        # Decode and validate token
        payload = decode_access_token(token)
        user_id_str = payload.get("sub")

        if not user_id_str:
            await websocket.close(code=4001, reason="Invalid token payload")
            logger.warning("WebSocket auth failed: Invalid token payload")
            return

        # Session validation: Check if session exists in Redis
        if redis_get_session_manager:
            session_manager = redis_get_session_manager()
            if session_manager and not session_manager.is_session_valid(int(user_id_str), token):
                await websocket.close(code=4001, reason="Session expired or invalidated")
                logger.warning("WebSocket auth failed: Session invalid for user %s", user_id_str)
                return

        # Get user from cache (with database fallback)
        current_user = None
        if redis_user_cache:
            current_user = redis_user_cache.get_by_id(int(user_id_str))

        if not current_user:
            await websocket.close(code=4001, reason="User not found")
            logger.warning("WebSocket auth failed: User %s not found", user_id_str)
            return

        logger.debug("WebSocket authenticated: user %d", current_user.id)

    except (ValueError, KeyError, AttributeError) as e:
        logger.error("WebSocket auth error: %s", e, exc_info=True)
        await websocket.close(code=4001, reason=f"Authentication failed: {str(e)}")
        return

    voice_session_id = None
    omni_generator = None
    user_id = str(current_user.id)

    try:
        # CRITICAL: Close any existing WebSocket connections for this diagram_session_id
        # This ensures fresh state when switching diagrams
        if diagram_session_id in active_websockets:
            existing_ws_list = active_websockets[diagram_session_id]
            logger.debug(
                "Closing %d existing WebSocket connection(s) for diagram %s",
                len(existing_ws_list), diagram_session_id
            )
            for existing_ws in existing_ws_list:
                try:
                    await existing_ws.close(code=1001, reason="Diagram session ended")
                except (RuntimeError, ConnectionError, AttributeError) as e:
                    logger.debug("Error closing existing WebSocket: %s", e)
            active_websockets[diagram_session_id] = []

        # Wait for start message
        start_msg = await websocket.receive_json()

        if start_msg.get('type') != 'start':
            logger.warning("Invalid start message type: %s", start_msg.get('type'))
            await safe_websocket_send(websocket, {'type': 'error', 'error': 'Expected start message'})
            await websocket.close()
            return

        logger.debug("Starting voice conversation for user %s", user_id)

        # CRITICAL: Voice agent session MUST be scoped to diagram_session_id
        # This ensures one agent per diagram session, proper cleanup, and no cross-contamination
        # Use diagram_session_id as the agent session identifier (not a random UUID)
        agent_session_id = f"diagram_{diagram_session_id}"

        # CRITICAL: Clean up any existing voice session for this diagram_session_id FIRST
        # This ensures old conversation history doesn't persist when switching diagrams
        # IMPORTANT: Do this BEFORE registering the new WebSocket to avoid closing it
        # We already closed existing WebSocket connections above, this cleans up session state
        existing_cleaned = await cleanup_voice_by_diagram_session(diagram_session_id)
        if existing_cleaned:
            logger.debug("Cleaned up existing voice session for diagram %s", diagram_session_id)

        # Also cleanup the agent if it exists (should be cleaned up already, but double-check)
        if agent_session_id in voice_agent_manager._agents:  # pylint: disable=protected-access
            logger.debug("Removing existing agent for diagram session %s", diagram_session_id)
            voice_agent_manager.remove(agent_session_id)

        # NOTE: No need to close existing Omni conversation here anymore
        # Each voice session now has its own OmniClient instance (created in create_voice_session)
        # This prevents cross-contamination between concurrent users

        # CRITICAL: Register this WebSocket connection for this diagram_session_id
        # Do this AFTER cleanup to ensure we don't close our own connection
        if diagram_session_id not in active_websockets:
            active_websockets[diagram_session_id] = []
        active_websockets[diagram_session_id].append(websocket)
        logger.debug(
            "Registered WebSocket for diagram %s (total: %d)",
            diagram_session_id, len(active_websockets[diagram_session_id])
        )

        # Create new voice session (with fresh conversation_history: [])
        voice_session_id = create_voice_session(
            user_id=user_id,
            diagram_session_id=diagram_session_id,
            diagram_type=start_msg.get('diagram_type'),
            active_panel=start_msg.get('active_panel', 'mindmate')
        )

        logger.debug(
            "Session created: %s, diagram_type=%s, panel=%s",
            voice_session_id, start_msg.get('diagram_type'),
            start_msg.get('active_panel')
        )
        logger.debug("Agent session ID: %s (scoped to diagram_session_id)", agent_session_id)

        # Store initial context
        voice_sessions[voice_session_id]['context'] = start_msg.get('context', {})

        # Initialize persistent LangGraph agent with diagram state
        # CRITICAL: Agent is scoped to diagram_session_id, not voice_session_id
        # This ensures the agent is scoped to the diagram session, not the WebSocket connection
        # If agent already exists (shouldn't happen after cleanup), clear its history
        initial_context = start_msg.get('context', {})
        agent = voice_agent_manager.get_or_create(agent_session_id)

        # CRITICAL: Clear agent's conversation history when starting a new diagram session
        # This ensures no cross-contamination between diagram sessions
        agent.clear_history()

        # Sync initial diagram state to agent
        diagram_data = initial_context.get('diagram_data', {})
        diagram_data['diagram_type'] = start_msg.get('diagram_type')
        agent.update_diagram_state(diagram_data)
        agent.update_panel_state(
            start_msg.get('active_panel', 'none'),
            initial_context.get('panels', {})
        )

        logger.debug("VoiceAgent initialized with %d nodes", len(diagram_data.get('children', [])))

        # Build instructions with FULL context including diagram_data
        context = {
            'diagram_type': start_msg.get('diagram_type'),
            'active_panel': start_msg.get('active_panel'),
            'conversation_history': [],
            'selected_nodes': initial_context.get('selected_nodes', []),
            'diagram_data': initial_context.get('diagram_data', {})  # Include node content!
        }
        instructions = build_voice_instructions(context)

        children_count = len(context.get('diagram_data', {}).get('children', []))
        logger.debug("Initial instructions built with %d nodes", children_count)

        logger.debug("Built instructions for context: %d chars", len(instructions))

        # CRITICAL: Use session-specific OmniClient (not singleton)
        # Each voice session has its own OmniClient instance to support concurrent users
        session = get_voice_session(voice_session_id)
        if not session:
            logger.error("Voice session %s not found", voice_session_id)
            await websocket.close(code=1008, reason="Session not found")
            return

        omni_client = session.get('omni_client')
        if not omni_client:
            logger.error("OmniClient not found for session %s", voice_session_id)
            await websocket.close(code=1008, reason="OmniClient not initialized")
            return

        # Start Omni conversation using session-specific client WITH middleware
        # This provides rate limiting, error handling, token tracking, and performance tracking
        omni_generator = omni_middleware.wrap_start_conversation(
            omni_client=omni_client,
            instructions=instructions,
            user_id=int(user_id) if user_id else None,
            organization_id=(
                getattr(current_user, 'organization_id', None)
                if current_user and hasattr(current_user, 'id') else None
            ),
            session_id=voice_session_id,
            request_type='voice_omni',
            endpoint_path='/ws/voice'
        )

        # Store generator in session for cleanup
        voice_sessions[voice_session_id]['omni_generator'] = omni_generator

        # Send connected confirmation
        await safe_websocket_send(websocket, {
            'type': 'connected',
            'session_id': voice_session_id
        })

        logger.debug("Voice session %s connected", voice_session_id)

        # Wait for SDK to initialize conversation (check via async iteration start)
        # The first event will confirm conversation is ready
        logger.debug("Waiting for Omni session to initialize...")

        # Handle messages concurrently
        async def handle_client_messages():
            """Handle messages from client"""
            try:
                while True:
                    message = await websocket.receive_json()
                    msg_type = message.get('type')

                    if msg_type == 'audio':
                        # Forward audio to Omni
                        audio_data = message.get('data')
                        if audio_data:
                            # Log every 20th audio packet to avoid spam
                            if random.random() < 0.05:
                                logger.debug("Forwarding audio to Omni: %d bytes (base64)", len(audio_data))
                            omni_client = get_session_omni_client(voice_session_id)
                            if omni_client:
                                await omni_client.send_audio(audio_data)
                            else:
                                logger.warning(
                                    "Cannot send audio: OmniClient not found for session %s",
                                    voice_session_id
                                )

                    elif msg_type == 'text':
                        # Handle text message from user
                        text = message.get('text', '').strip()
                        if text:
                            logger.debug("Received text message: %s", text)

                            # Store in conversation history
                            voice_sessions[voice_session_id]['conversation_history'].append({
                                'role': 'user',
                                'content': text
                            })

                            # CRITICAL: Process text message through unified command processing
                            # Uses Qwen Turbo (classification model) for intention checking via agent.process_command()
                            # Pass is_text_message=True for lower confidence threshold (0.5 vs 0.7)
                            # This allows conversational requests like "can you change..." to be executed
                            session_context = voice_sessions[voice_session_id].get('context', {})

                            # Process command through unified function (handles UI actions AND diagram updates)
                            # LLM (Qwen Turbo) parses the command and returns structured action JSON
                            command_executed = await process_voice_command(
                                websocket, voice_session_id, text, session_context, is_text_message=True
                            )

                            # If command was executed (UI actions or diagram updates), we're done
                            if command_executed:
                                continue

                            # Otherwise, send to Omni for conversational response
                            try:
                                logger.debug("Text message is conversational, sending to Omni")
                                omni_client = get_session_omni_client(voice_session_id)
                                if omni_client:
                                    await omni_client.send_text_message(text)
                                else:
                                    logger.warning(
                                        "Cannot send text: OmniClient not found for session %s",
                                        voice_session_id
                                    )
                                    await safe_websocket_send(websocket, {
                                        'type': 'error',
                                        'error': 'Voice session not initialized'
                                    })
                            except (RuntimeError, ConnectionError, AttributeError) as text_error:
                                logger.error("Text message processing error: %s", text_error, exc_info=True)
                                await safe_websocket_send(websocket, {
                                    'type': 'error',
                                    'error': str(text_error)
                                })

                    elif msg_type == 'context_update':
                        # Update context and instructions with full diagram data
                        active_panel = message.get('active_panel')
                        new_context = message.get('context', {})

                        # CRITICAL: Update diagram_type from context if provided
                        # This ensures the session knows the current diagram type when switching diagrams
                        new_diagram_type = new_context.get('diagram_type')
                        if new_diagram_type:
                            old_diagram_type = voice_sessions[voice_session_id].get('diagram_type')
                            voice_sessions[voice_session_id]['diagram_type'] = new_diagram_type
                            if old_diagram_type != new_diagram_type:
                                logger.info(
                                    "VOIC | Diagram type updated: %s -> %s for session %s",
                                    old_diagram_type, new_diagram_type, voice_session_id
                                )
                                # CRITICAL: When diagram type changes, clear old diagram data
                                # to prevent cross-contamination
                                if 'diagram_data' in voice_sessions[voice_session_id].get('context', {}):
                                    voice_sessions[voice_session_id]['context']['diagram_data'] = {}

                        update_panel_context(voice_session_id, active_panel)
                        voice_sessions[voice_session_id]['context'].update(new_context)

                        # CRITICAL: Ensure diagram_type is also in context dict for consistency
                        # This prevents issues when session_context is passed to other functions
                        if new_diagram_type:
                            voice_sessions[voice_session_id]['context']['diagram_type'] = new_diagram_type

                        # Update persistent agent's diagram state (keeps agent in sync)
                        # CRITICAL: Agent is scoped to diagram_session_id, not voice_session_id
                        agent_session_id = get_agent_session_id(voice_session_id)
                        agent = voice_agent_manager.get_or_create(agent_session_id)
                        diagram_data = new_context.get('diagram_data', {})
                        # Use updated diagram_type from session (or fallback to context)
                        session_diagram_type = voice_sessions[voice_session_id].get('diagram_type')
                        diagram_data['diagram_type'] = session_diagram_type or new_diagram_type
                        agent.update_diagram_state(diagram_data)
                        agent.update_panel_state(active_panel, new_context.get('panels', {}))

                        # Rebuild and update Omni instructions with FULL context
                        updated_context = {
                            'diagram_type': voice_sessions[voice_session_id].get('diagram_type'),
                            'active_panel': active_panel,
                            'conversation_history': voice_sessions[voice_session_id].get('conversation_history', []),
                            'selected_nodes': new_context.get('selected_nodes', []),
                            'diagram_data': diagram_data
                        }
                        new_instructions = build_voice_instructions(updated_context)
                        try:
                            omni_client = get_session_omni_client(voice_session_id)
                            if omni_client:
                                await omni_client.update_instructions(new_instructions)
                            else:
                                logger.debug(
                                    "Cannot update instructions: OmniClient not found "
                                    "for session %s",
                                    voice_session_id
                                )
                        except (RuntimeError, ConnectionError, AttributeError) as e:
                            logger.debug("Error updating Omni instructions: %s", e)

                        children_count = len(diagram_data.get('children', []))
                        logger.debug(
                            "Context updated for %s with %d nodes",
                            voice_session_id, children_count
                        )

                    elif msg_type == 'stop':
                        # User wants to stop the conversation
                        break

                    elif msg_type == 'cancel_response':
                        # Cancel ongoing Omni response
                        logger.debug("User requested to cancel response")
                        omni_client = get_session_omni_client(voice_session_id)
                        if omni_client:
                            await omni_client.cancel_response()
                            await safe_websocket_send(websocket, {
                                'type': 'response_cancelled'
                            })
                        else:
                            logger.warning(
                                "Cannot cancel response: OmniClient not found for session %s",
                                voice_session_id
                            )

                    elif msg_type == 'clear_audio_buffer':
                        # Clear audio buffer (cancel pending audio input)
                        logger.debug("User requested to clear audio buffer")
                        omni_client = get_session_omni_client(voice_session_id)
                        if omni_client:
                            await omni_client.clear_audio_buffer()
                            await safe_websocket_send(websocket, {
                                'type': 'audio_buffer_cleared'
                            })
                        else:
                            logger.warning(
                                "Cannot clear audio buffer: OmniClient not found for session %s",
                                voice_session_id
                            )

                    elif msg_type == 'commit_audio_buffer':
                        # Explicitly commit audio buffer
                        logger.debug("User requested to commit audio buffer")
                        omni_client = get_session_omni_client(voice_session_id)
                        if omni_client:
                            await omni_client.commit_audio_buffer()
                            await safe_websocket_send(websocket, {
                                'type': 'audio_buffer_committed'
                            })
                        else:
                            logger.warning(
                                "Cannot commit audio buffer: OmniClient not found for session %s",
                                voice_session_id
                            )

                    elif msg_type == 'append_image':
                        # Append image data (for multimodal support)
                        logger.debug("User requested to append image")
                        image_data = message.get('data')  # Base64 encoded image
                        image_format = message.get('format', 'jpeg')
                        if image_data:
                            omni_client = get_session_omni_client(voice_session_id)
                            if omni_client:
                                # Decode base64 to bytes (base64 imported at top of file)
                                image_bytes = base64.b64decode(image_data)
                                await omni_client.append_image(image_bytes, image_format)
                                await safe_websocket_send(websocket, {
                                    'type': 'image_appended',
                                    'format': image_format
                                })
                            else:
                                logger.warning(
                                    "Cannot append image: OmniClient not found for session %s",
                                    voice_session_id
                                )
                        else:
                            await safe_websocket_send(websocket, {
                                'type': 'error',
                                'error': 'Missing image data'
                            })

            except WebSocketDisconnect:
                logger.debug("Client disconnected: %s", voice_session_id)
            except (RuntimeError, ConnectionError, AttributeError) as e:
                logger.error("Client message error: %s", e, exc_info=True)

        async def handle_omni_events():
            """Handle events from Omni"""
            greeting_sent = False  # Track if greeting was sent
            try:
                async for event in omni_generator:
                    event_type = event.get('type')

                    # Send short greeting when session is ready
                    if not greeting_sent and event_type == 'session_ready':
                        # Build short, personalized greeting (avoid long intro that triggers Omni's self-intro)
                        diagram_type = voice_sessions[voice_session_id].get('diagram_type', 'unknown')
                        greeting = build_greeting_message(diagram_type, language='zh')

                        omni_client = get_session_omni_client(voice_session_id)
                        if omni_client:
                            await omni_client.create_greeting(greeting_text=greeting)
                        else:
                            logger.debug(
                                "Cannot create greeting: OmniClient not found for session %s",
                                voice_session_id
                            )
                        greeting_sent = True
                        logger.debug("Greeting sent: %s...", greeting[:50])

                    if event_type == 'transcription':
                        transcription_text = event.get('text', '')
                        session_context = voice_sessions[voice_session_id].get('context', {})

                        logger.debug("Omni transcription: '%s'", transcription_text)

                        # Send transcription to client
                        await safe_websocket_send(websocket, {
                            'type': 'transcription',
                            'text': transcription_text
                        })

                        # Store in conversation history
                        voice_sessions[voice_session_id]['conversation_history'].append({
                            'role': 'user',
                            'content': transcription_text
                        })

                        # Parse voice command using unified command processing
                        # Voice transcriptions use higher confidence threshold (0.7)
                        try:
                            session_context = voice_sessions[voice_session_id].get('context', {})

                            # Process command through unified function (handles UI actions AND diagram updates)
                            command_executed = await process_voice_command(
                                websocket, voice_session_id, transcription_text, session_context, is_text_message=False
                            )

                            # If command was executed (UI actions or diagram updates), we're done
                            if command_executed:
                                continue

                            # Otherwise, continue to next transcription (no action needed)
                            continue

                        except (ValueError, KeyError, RuntimeError, AttributeError) as voice_error:
                            logger.error("Voice command processing error: %s", voice_error, exc_info=True)

                    elif event_type == 'text_chunk':
                        text_chunk = event.get('text', '')
                        logger.debug("Omni text chunk: '%s'", text_chunk)
                        await safe_websocket_send(websocket, {
                            'type': 'text_chunk',
                            'text': text_chunk
                        })

                    elif event_type == 'audio_chunk':
                        # Send base64 audio to client
                        audio_bytes = event.get('audio')
                        if audio_bytes is None:
                            logger.warning("Received audio_chunk event without audio data")
                            continue
                        audio_b64 = base64.b64encode(audio_bytes).decode('ascii')

                        # Log audio chunk (every 5th to avoid spam)
                        if random.random() < 0.2:
                            logger.debug("Omni audio chunk: %d bytes -> %d base64", len(audio_bytes), len(audio_b64))

                        await safe_websocket_send(websocket, {
                            'type': 'audio_chunk',
                            'audio': audio_b64
                        })

                    elif event_type == 'speech_started':
                        logger.debug("VAD: Speech started at %sms", event.get('audio_start_ms'))
                        await safe_websocket_send(websocket, {
                            'type': 'speech_started',
                            'audio_start_ms': event.get('audio_start_ms')
                        })

                    elif event_type == 'speech_stopped':
                        logger.debug("VAD: Speech stopped at %sms", event.get('audio_end_ms'))
                        await safe_websocket_send(websocket, {
                            'type': 'speech_stopped',
                            'audio_end_ms': event.get('audio_end_ms')
                        })

                    elif event_type == 'response_done':
                        logger.debug("Omni response complete")
                        # NOTE: Token tracking is now handled automatically by WebSocket LLM middleware
                        # The middleware wraps the generator and tracks tokens on response_done events

                        await safe_websocket_send(websocket, {
                            'type': 'response_done'
                        })

                    elif event_type == 'error':
                        await safe_websocket_send(websocket, {
                            'type': 'error',
                            'error': str(event.get('error'))
                        })

                    # Additional informational events (forwarded for future use)
                    elif event_type == 'session_created':
                        await safe_websocket_send(websocket, {
                            'type': 'session_created',
                            'session': event.get('session', {})
                        })

                    elif event_type == 'session_updated':
                        await safe_websocket_send(websocket, {
                            'type': 'session_updated',
                            'session': event.get('session', {})
                        })

                    elif event_type == 'response_created':
                        await safe_websocket_send(websocket, {
                            'type': 'response_created',
                            'response': event.get('response', {})
                        })

                    elif event_type == 'audio_buffer_committed':
                        await safe_websocket_send(websocket, {
                            'type': 'audio_buffer_committed',
                            'item_id': event.get('item_id')
                        })

                    elif event_type == 'audio_buffer_cleared':
                        await safe_websocket_send(websocket, {
                            'type': 'audio_buffer_cleared'
                        })

                    elif event_type == 'item_created':
                        await safe_websocket_send(websocket, {
                            'type': 'item_created',
                            'item': event.get('item', {})
                        })

                    elif event_type == 'response_text_done':
                        await safe_websocket_send(websocket, {
                            'type': 'response_text_done',
                            'text': event.get('text', '')
                        })

                    elif event_type == 'response_audio_done':
                        await safe_websocket_send(websocket, {
                            'type': 'response_audio_done'
                        })

                    elif event_type == 'response_audio_transcript_done':
                        await safe_websocket_send(websocket, {
                            'type': 'response_audio_transcript_done',
                            'transcript': event.get('transcript', '')
                        })

                    elif event_type == 'output_item_added':
                        await safe_websocket_send(websocket, {
                            'type': 'output_item_added',
                            'item': event.get('item', {})
                        })

                    elif event_type == 'output_item_done':
                        await safe_websocket_send(websocket, {
                            'type': 'output_item_done',
                            'item': event.get('item', {})
                        })

                    elif event_type == 'content_part_added':
                        await safe_websocket_send(websocket, {
                            'type': 'content_part_added',
                            'part': event.get('part', {})
                        })

                    elif event_type == 'content_part_done':
                        await safe_websocket_send(websocket, {
                            'type': 'content_part_done',
                            'part': event.get('part', {})
                        })

            except (RuntimeError, ConnectionError, AttributeError, ValueError) as e:
                logger.error("Omni event error: %s", e, exc_info=True)
                await safe_websocket_send(websocket, {'type': 'error', 'error': str(e)})

        # Run both handlers concurrently
        await asyncio.gather(
            handle_client_messages(),
            handle_omni_events()
        )

    except WebSocketDisconnect:
        logger.debug("WebSocket disconnected: %s", voice_session_id)

    except (RuntimeError, ConnectionError, AttributeError) as e:
        logger.error("WebSocket error: %s", e, exc_info=True)
        try:
            await safe_websocket_send(websocket, {'type': 'error', 'error': str(e)})
        except Exception:  # pylint: disable=broad-except
            pass

    finally:
        # Cleanup
        if voice_session_id:
            end_voice_session(voice_session_id, reason='websocket_closed')

        # CRITICAL: Remove WebSocket from active connections tracking
        if diagram_session_id in active_websockets:
            try:
                active_websockets[diagram_session_id].remove(websocket)
                logger.debug("Removed WebSocket from active connections for diagram %s", diagram_session_id)
                # Clean up empty list
                if not active_websockets[diagram_session_id]:
                    del active_websockets[diagram_session_id]
            except ValueError:
                # WebSocket not in list (already removed)
                pass

        # CRITICAL: Close session-specific Omni client
        # Each voice session has its own OmniClient instance that must be closed
        if voice_session_id:
            session = get_voice_session(voice_session_id)
            if session and 'omni_client' in session:
                omni_client = session['omni_client']
                try:
                    # Native WebSocket client uses async close()
                    if (hasattr(omni_client, '_native_client') and
                        omni_client._native_client):  # pylint: disable=protected-access
                        await omni_client._native_client.close()  # pylint: disable=protected-access
                        logger.debug("Closed Omni client for session %s", voice_session_id)
                    elif hasattr(omni_client, 'close'):
                        # Handle both sync and async close methods
                        close_result = omni_client.close()
                        if asyncio.iscoroutine(close_result):
                            await close_result
                        logger.debug("Closed Omni client for session %s", voice_session_id)
                except (RuntimeError, ConnectionError, AttributeError) as e:  # pylint: disable=protected-access
                    logger.debug(
                        "Error closing Omni client for session %s (may already be closed): %s",
                        voice_session_id, e
                    )


@router.post("/api/voice/cleanup/{diagram_session_id}")
async def cleanup_voice_session(
    diagram_session_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Cleanup voice session and WebSocket connections when diagram session ends.
    Called by session manager on session end or navigation to gallery.

    CRITICAL: This closes all WebSocket connections and cleans up all voice agent state
    for the diagram session, ensuring fresh state when switching diagrams.

    This endpoint is controlled by the session manager and ensures proper
    cleanup of voice sessions when switching diagrams or navigating to gallery.
    """
    # Check if voice agent feature is enabled
    if not config.FEATURE_VOICE_AGENT:
        logger.debug("Voice agent cleanup skipped: feature disabled")
        return {"success": True, "message": "Voice agent feature is disabled"}

    try:
        cleaned = await cleanup_voice_by_diagram_session(diagram_session_id)

        if cleaned:
            logger.info(
                "Voice session and WebSocket connections cleaned up for diagram %s by user %d",
                diagram_session_id, current_user.id
            )
            message = (
                f"Voice session and WebSocket connections cleaned up "
                f"for diagram {diagram_session_id}"
            )
            return {"success": True, "message": message}
        else:
            logger.debug("No active voice session found for diagram %s", diagram_session_id)
            return {"success": True, "message": "No active voice session found"}

    except (RuntimeError, ConnectionError, AttributeError) as e:
        logger.error("Cleanup error: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}

