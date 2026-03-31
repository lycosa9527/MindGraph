"""Paragraph processing with Qwen Plus for voice input."""

from typing import Any, Dict
import json
import re

from fastapi import WebSocket

from services.features.voice_agent import voice_agent_manager
from services.llm import llm_service

from routers.features.voice.diagram_execute import execute_diagram_update
from routers.features.voice.messaging import (
    build_voice_instructions,
    safe_websocket_send,
)
from routers.features.voice.session_ops import (
    get_agent_session_id,
    get_session_omni_client,
)
from routers.features.voice.state import logger, voice_sessions
from utils.prompt_locale import output_language_instruction

try:
    from prompts.voice_agent import VOICE_AGENT_PROMPTS
except ImportError:
    VOICE_AGENT_PROMPTS = None


async def process_paragraph_with_qwen_plus(
    websocket: WebSocket,
    voice_session_id: str,
    paragraph_text: str,
    session_context: Dict[str, Any],
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
        current_diagram_type = voice_sessions[voice_session_id].get("diagram_type", "circle_map")
        diagram_data = session_context.get("diagram_data", {})

        # Get current diagram state
        current_topic = diagram_data.get("topic") or diagram_data.get("center", {}).get("text", "")
        current_nodes = diagram_data.get("children", []) or diagram_data.get("attributes", []) or []
        has_existing_content = bool(current_topic or current_nodes)

        logger.info(
            "Processing paragraph with Qwen Plus (current diagram: %s)",
            current_diagram_type,
        )
        logger.debug(
            "Paragraph length: %d characters, has existing content: %s",
            len(paragraph_text),
            has_existing_content,
        )

        # CRITICAL: Send loading indicator to teacher
        await safe_websocket_send(websocket, {"type": "text_chunk", "text": "📝 正在分析段落内容，请稍候..."})

        # CRITICAL: Load prompt template from centralized prompts folder
        # Determine language based on paragraph content
        # (simple heuristic: check for Chinese characters)
        has_chinese = bool(re.search(r"[\u4e00-\u9fff]", paragraph_text))
        language = "zh" if has_chinese else "en"

        if VOICE_AGENT_PROMPTS:
            prompt_key = f"paragraph_processing_{language}"
            fallback_key = "paragraph_processing_en"
            prompt_template = VOICE_AGENT_PROMPTS.get(prompt_key, VOICE_AGENT_PROMPTS.get(fallback_key))
        else:
            logger.warning("Could not import voice_agent prompts, using fallback")
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
            current_topic=current_topic if current_topic else "Not set",
            current_nodes_count=len(current_nodes),
            has_existing_content=has_existing_content,
        )
        prompt = prompt + output_language_instruction(language)

        # Use Qwen Plus (generation model) for paragraph processing
        response = await llm_service.chat(
            prompt=prompt,
            model="qwen-plus",  # Use Plus for generation/extraction tasks
            temperature=0.3,  # Lower temperature for more consistent extraction
            max_tokens=1500,  # Allow longer responses for multiple nodes
            timeout=30.0,
        )

        logger.debug("Qwen Plus response: %s...", response[:200])

        # Parse JSON response
        try:
            # Extract JSON from response (handle cases where LLM adds extra text)
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                extracted_data = json.loads(json_match.group())
            else:
                extracted_data = json.loads(response)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse Qwen Plus JSON response: %s", e)
            logger.debug("Raw response: %s", response)
            # Fallback: send acknowledgment and return False
            await safe_websocket_send(
                websocket,
                {
                    "type": "text_chunk",
                    "text": "❌ 抱歉，我无法解析这段文本。请尝试更简洁的描述，或分段输入。",
                },
            )
            return False

        # CRITICAL: Validate extracted content
        if not extracted_data:
            logger.warning("Qwen Plus returned empty data")
            await safe_websocket_send(
                websocket,
                {
                    "type": "text_chunk",
                    "text": "❌ 未能从段落中提取到有效内容。请检查文本是否包含可提取的信息。",
                },
            )
            return False

        # Validate nodes exist and are not empty
        nodes = extracted_data.get("nodes", [])
        topic = (
            extracted_data.get("topic")
            or extracted_data.get("title")
            or extracted_data.get("event")
            or extracted_data.get("whole")
        )

        # Check if we have meaningful content
        has_nodes = bool(nodes and len(nodes) > 0)
        has_topic = bool(topic and topic.strip())

        if not has_nodes and not has_topic:
            logger.warning("No nodes or topic extracted from paragraph")
            await safe_websocket_send(
                websocket,
                {
                    "type": "text_chunk",
                    "text": "❌ 未能从段落中提取到主题或节点。请确保文本包含具体的内容信息。",
                },
            )
            return False

        # Filter out empty nodes
        if nodes:
            nodes = [node for node in nodes if node and str(node).strip()]
            extracted_data["nodes"] = nodes

        if not nodes and not has_topic:
            logger.warning("All nodes were empty after filtering")
            await safe_websocket_send(
                websocket,
                {
                    "type": "text_chunk",
                    "text": "❌ 提取的节点内容为空。请检查文本格式。",
                },
            )
            return False

        # Validate node count (reasonable range)
        if len(nodes) > 20:
            logger.warning("Too many nodes extracted (%d), limiting to 15", len(nodes))
            nodes = nodes[:15]
            extracted_data["nodes"] = nodes

        logger.info(
            "Validated extracted content: topic=%s, nodes=%d",
            bool(has_topic),
            len(nodes),
        )

        # Check if diagram type should be changed
        recommended_type = extracted_data.get("recommended_diagram_type", current_diagram_type)
        should_change_type = extracted_data.get("should_change_diagram_type", False)
        reasoning = extracted_data.get("reasoning", "")

        # CRITICAL: Error handling - if recommended type doesn't match current type
        if recommended_type != current_diagram_type:
            logger.warning(
                "Diagram type mismatch detected: current=%s, recommended=%s",
                current_diagram_type,
                recommended_type,
            )

            # Map diagram type names to Chinese for user-friendly messages
            diagram_type_names = {
                "circle_map": "圆圈图",
                "bubble_map": "气泡图",
                "double_bubble_map": "双气泡图",
                "tree_map": "树形图",
                "flow_map": "流程图",
                "multi_flow_map": "复流程图",
                "brace_map": "括号图",
                "bridge_map": "桥形图",
                "mindmap": "思维导图",
                "concept_map": "概念图",
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

            await safe_websocket_send(websocket, {"type": "text_chunk", "text": warning_message})

            # Notify frontend about diagram type change recommendation
            await safe_websocket_send(
                websocket,
                {
                    "type": "action",
                    "action": "diagram_type_recommendation",
                    "params": {
                        "current_type": current_diagram_type,
                        "current_type_name": current_name,
                        "recommended_type": recommended_type,
                        "recommended_type_name": recommended_name,
                        "reasoning": reasoning or "内容更适合此图表类型",
                        "warning": True,
                        "message": warning_message,
                    },
                },
            )

            # CRITICAL: Don't proceed with content extraction if types don't match
            # Wait for teacher's confirmation or let them switch diagram type first
            # For now, we'll still extract but use current diagram type (with warning)
            # In future, we could add a confirmation step
            logger.info(
                "Proceeding with current diagram type %s despite recommendation for %s",
                current_diagram_type,
                recommended_type,
            )
            diagram_type = current_diagram_type  # Use current type to avoid breaking existing diagram

            # Send additional message explaining what will happen
            await safe_websocket_send(
                websocket,
                {
                    "type": "text_chunk",
                    "text": f"\n注意：内容将按照{current_name}的结构提取，可能无法完全匹配内容特点。",
                },
            )
        elif should_change_type:
            # Types match but LLM suggested change (shouldn't happen, but handle gracefully)
            diagram_type = current_diagram_type
        else:
            # Types match, proceed normally
            diagram_type = current_diagram_type

        intent = extracted_data.get("intent", "extract_content")
        logger.info(
            "Detected intent: %s, using diagram type: %s (recommended: %s)",
            intent,
            diagram_type,
            recommended_type,
        )

        # Send progress update
        if nodes:
            await safe_websocket_send(
                websocket,
                {
                    "type": "text_chunk",
                    "text": f"✓ 已提取 {len(nodes)} 个节点，正在更新图表...",
                },
            )

        # Update diagram based on extracted data

        if diagram_type == "double_bubble_map":
            left_topic = extracted_data.get("left_topic")
            right_topic = extracted_data.get("right_topic")
            if left_topic and right_topic:
                # Also update nodes: similarities, left_differences, right_differences
                similarities = extracted_data.get("similarities", [])
                left_differences = extracted_data.get("left_differences", [])
                right_differences = extracted_data.get("right_differences", [])
                await execute_diagram_update(
                    websocket,
                    voice_session_id,
                    "update_center",
                    {
                        "action": "update_center",
                        "left": left_topic,
                        "right": right_topic,
                        "target": f"{left_topic} vs {right_topic}",
                    },
                    session_context,
                )
                # CRITICAL: Batch add nodes instead of one-by-one for efficiency
                # Collect all nodes first, then send batch update
                nodes_to_add = []

                # Add similarities nodes
                for node_text in similarities[:5]:
                    if node_text and str(node_text).strip():
                        nodes_to_add.append({"text": str(node_text).strip(), "category": "similarities"})

                # Add left differences nodes
                for node_text in left_differences[:5]:
                    if node_text and str(node_text).strip():
                        nodes_to_add.append(
                            {
                                "text": str(node_text).strip(),
                                "category": "left_differences",
                            }
                        )

                # Add right differences nodes
                for node_text in right_differences[:5]:
                    if node_text and str(node_text).strip():
                        nodes_to_add.append(
                            {
                                "text": str(node_text).strip(),
                                "category": "right_differences",
                            }
                        )

                # Send batch update if we have nodes
                if nodes_to_add:
                    await safe_websocket_send(
                        websocket,
                        {
                            "type": "diagram_update",
                            "action": "add_nodes",
                            "updates": nodes_to_add,
                        },
                    )

                    # Update session context
                    if "diagram_data" not in session_context:
                        session_context["diagram_data"] = {}

                    # Update agent state
                    agent_session_id = get_agent_session_id(voice_session_id)
                    agent = voice_agent_manager.get_or_create(agent_session_id)
                    diagram_data = session_context.get("diagram_data", {})
                    diagram_data["diagram_type"] = voice_sessions[voice_session_id].get("diagram_type")
                    agent.update_diagram_state(diagram_data)

                    updated_context = {
                        "diagram_type": voice_sessions[voice_session_id].get("diagram_type"),
                        "active_panel": voice_sessions[voice_session_id].get("active_panel", "none"),
                        "conversation_history": voice_sessions[voice_session_id].get("conversation_history", []),
                        "selected_nodes": session_context.get("selected_nodes", []),
                        "diagram_data": diagram_data,
                    }
                    new_instructions = build_voice_instructions(updated_context)
                    omni_client = get_session_omni_client(voice_session_id)
                    if omni_client:
                        await omni_client.update_instructions(new_instructions)

                    logger.debug("Batch added %d nodes for double bubble map", len(nodes_to_add))
        elif diagram_type == "flow_map":
            title = extracted_data.get("title") or extracted_data.get("topic")
            if title:
                await execute_diagram_update(
                    websocket,
                    voice_session_id,
                    "update_center",
                    {"action": "update_center", "title": title, "target": title},
                    session_context,
                )
            nodes = extracted_data.get("nodes", [])
            # CRITICAL: Batch add nodes instead of one-by-one
            nodes_to_add = [
                {"text": str(node_text).strip()} for node_text in nodes[:10] if node_text and str(node_text).strip()
            ]
            if nodes_to_add:
                await safe_websocket_send(
                    websocket,
                    {
                        "type": "diagram_update",
                        "action": "add_nodes",
                        "updates": nodes_to_add,
                    },
                )

                # Update session context and agent state
                if "diagram_data" not in session_context:
                    session_context["diagram_data"] = {}
                if "children" not in session_context["diagram_data"]:
                    session_context["diagram_data"]["children"] = []
                session_context["diagram_data"]["children"].extend([{"text": n["text"]} for n in nodes_to_add])

                agent_session_id = get_agent_session_id(voice_session_id)
                agent = voice_agent_manager.get_or_create(agent_session_id)
                diagram_data = session_context.get("diagram_data", {})
                diagram_data["diagram_type"] = voice_sessions[voice_session_id].get("diagram_type")
                agent.update_diagram_state(diagram_data)

                updated_context = {
                    "diagram_type": voice_sessions[voice_session_id].get("diagram_type"),
                    "active_panel": voice_sessions[voice_session_id].get("active_panel", "none"),
                    "conversation_history": voice_sessions[voice_session_id].get("conversation_history", []),
                    "selected_nodes": session_context.get("selected_nodes", []),
                    "diagram_data": diagram_data,
                }
                new_instructions = build_voice_instructions(updated_context)
                omni_client = get_session_omni_client(voice_session_id)
                if omni_client:
                    await omni_client.update_instructions(new_instructions)

                logger.debug("Batch added %d nodes for flow map", len(nodes_to_add))
        elif diagram_type == "multi_flow_map":
            event = extracted_data.get("event") or extracted_data.get("topic")
            if event:
                await execute_diagram_update(
                    websocket,
                    voice_session_id,
                    "update_center",
                    {"action": "update_center", "event": event, "target": event},
                    session_context,
                )
            causes = extracted_data.get("causes", [])
            effects = extracted_data.get("effects", [])
            # CRITICAL: Batch add nodes
            nodes_to_add = []
            for node_text in causes[:5]:
                if node_text and str(node_text).strip():
                    nodes_to_add.append({"text": str(node_text).strip(), "category": "causes"})
            for node_text in effects[:5]:
                if node_text and str(node_text).strip():
                    nodes_to_add.append({"text": str(node_text).strip(), "category": "effects"})

            if nodes_to_add:
                await safe_websocket_send(
                    websocket,
                    {
                        "type": "diagram_update",
                        "action": "add_nodes",
                        "updates": nodes_to_add,
                    },
                )

                # Update session context and agent state
                if "diagram_data" not in session_context:
                    session_context["diagram_data"] = {}

                agent_session_id = get_agent_session_id(voice_session_id)
                agent = voice_agent_manager.get_or_create(agent_session_id)
                diagram_data = session_context.get("diagram_data", {})
                diagram_data["diagram_type"] = voice_sessions[voice_session_id].get("diagram_type")
                agent.update_diagram_state(diagram_data)

                updated_context = {
                    "diagram_type": voice_sessions[voice_session_id].get("diagram_type"),
                    "active_panel": voice_sessions[voice_session_id].get("active_panel", "none"),
                    "conversation_history": voice_sessions[voice_session_id].get("conversation_history", []),
                    "selected_nodes": session_context.get("selected_nodes", []),
                    "diagram_data": diagram_data,
                }
                new_instructions = build_voice_instructions(updated_context)
                omni_client = get_session_omni_client(voice_session_id)
                if omni_client:
                    await omni_client.update_instructions(new_instructions)

                logger.debug("Batch added %d nodes for multi-flow map", len(nodes_to_add))
        elif diagram_type == "brace_map":
            whole = extracted_data.get("whole") or extracted_data.get("topic")
            if whole:
                await execute_diagram_update(
                    websocket,
                    voice_session_id,
                    "update_center",
                    {"action": "update_center", "whole": whole, "target": whole},
                    session_context,
                )
            parts = extracted_data.get("parts", []) or extracted_data.get("nodes", [])
            # CRITICAL: Batch add nodes
            nodes_to_add = [
                {"text": str(node_text).strip()} for node_text in parts[:10] if node_text and str(node_text).strip()
            ]
            if nodes_to_add:
                await safe_websocket_send(
                    websocket,
                    {
                        "type": "diagram_update",
                        "action": "add_nodes",
                        "updates": nodes_to_add,
                    },
                )

                # Update session context and agent state
                if "diagram_data" not in session_context:
                    session_context["diagram_data"] = {}
                if "children" not in session_context["diagram_data"]:
                    session_context["diagram_data"]["children"] = []
                session_context["diagram_data"]["children"].extend([{"text": n["text"]} for n in nodes_to_add])

                agent_session_id = get_agent_session_id(voice_session_id)
                agent = voice_agent_manager.get_or_create(agent_session_id)
                diagram_data = session_context.get("diagram_data", {})
                diagram_data["diagram_type"] = voice_sessions[voice_session_id].get("diagram_type")
                agent.update_diagram_state(diagram_data)

                updated_context = {
                    "diagram_type": voice_sessions[voice_session_id].get("diagram_type"),
                    "active_panel": voice_sessions[voice_session_id].get("active_panel", "none"),
                    "conversation_history": voice_sessions[voice_session_id].get("conversation_history", []),
                    "selected_nodes": session_context.get("selected_nodes", []),
                    "diagram_data": diagram_data,
                }
                new_instructions = build_voice_instructions(updated_context)
                omni_client = get_session_omni_client(voice_session_id)
                if omni_client:
                    await omni_client.update_instructions(new_instructions)

                logger.debug("Batch added %d nodes for brace map", len(nodes_to_add))
        elif diagram_type == "bridge_map":
            dimension = extracted_data.get("dimension") or extracted_data.get("topic", "")
            if dimension:
                await execute_diagram_update(
                    websocket,
                    voice_session_id,
                    "update_center",
                    {
                        "action": "update_center",
                        "dimension": dimension,
                        "target": dimension,
                    },
                    session_context,
                )
            analogies = extracted_data.get("analogies", [])
            # CRITICAL: Batch add nodes
            nodes_to_add = []
            for analogy in analogies[:5]:
                if isinstance(analogy, dict):
                    left = analogy.get("left")
                    right = analogy.get("right")
                    if left and right:
                        nodes_to_add.append(
                            {
                                "text": f"{left} : {right}",
                                "left": str(left).strip(),
                                "right": str(right).strip(),
                            }
                        )

            if nodes_to_add:
                await safe_websocket_send(
                    websocket,
                    {
                        "type": "diagram_update",
                        "action": "add_nodes",
                        "updates": nodes_to_add,
                    },
                )

                # Update session context and agent state
                if "diagram_data" not in session_context:
                    session_context["diagram_data"] = {}

                agent_session_id = get_agent_session_id(voice_session_id)
                agent = voice_agent_manager.get_or_create(agent_session_id)
                diagram_data = session_context.get("diagram_data", {})
                diagram_data["diagram_type"] = voice_sessions[voice_session_id].get("diagram_type")
                agent.update_diagram_state(diagram_data)

                updated_context = {
                    "diagram_type": voice_sessions[voice_session_id].get("diagram_type"),
                    "active_panel": voice_sessions[voice_session_id].get("active_panel", "none"),
                    "conversation_history": voice_sessions[voice_session_id].get("conversation_history", []),
                    "selected_nodes": session_context.get("selected_nodes", []),
                    "diagram_data": diagram_data,
                }
                new_instructions = build_voice_instructions(updated_context)
                omni_client = get_session_omni_client(voice_session_id)
                if omni_client:
                    await omni_client.update_instructions(new_instructions)

                logger.debug("Batch added %d nodes for bridge map", len(nodes_to_add))
        else:
            # Standard diagrams (circle_map, bubble_map, tree_map, mindmap, concept_map)
            topic = extracted_data.get("topic")
            if topic:
                await execute_diagram_update(
                    websocket,
                    voice_session_id,
                    "update_center",
                    {"action": "update_center", "target": topic},
                    session_context,
                )
            nodes = extracted_data.get("nodes", [])
            # CRITICAL: Batch add nodes instead of one-by-one
            nodes_to_add = [
                {"text": str(node_text).strip()} for node_text in nodes[:10] if node_text and str(node_text).strip()
            ]
            if nodes_to_add:
                await safe_websocket_send(
                    websocket,
                    {
                        "type": "diagram_update",
                        "action": "add_nodes",
                        "updates": nodes_to_add,
                    },
                )

                # Update session context and agent state
                if "diagram_data" not in session_context:
                    session_context["diagram_data"] = {}
                if "children" not in session_context["diagram_data"]:
                    session_context["diagram_data"]["children"] = []
                session_context["diagram_data"]["children"].extend([{"text": n["text"]} for n in nodes_to_add])

                agent_session_id = get_agent_session_id(voice_session_id)
                agent = voice_agent_manager.get_or_create(agent_session_id)
                diagram_data = session_context.get("diagram_data", {})
                diagram_data["diagram_type"] = voice_sessions[voice_session_id].get("diagram_type")
                agent.update_diagram_state(diagram_data)

                updated_context = {
                    "diagram_type": voice_sessions[voice_session_id].get("diagram_type"),
                    "active_panel": voice_sessions[voice_session_id].get("active_panel", "none"),
                    "conversation_history": voice_sessions[voice_session_id].get("conversation_history", []),
                    "selected_nodes": session_context.get("selected_nodes", []),
                    "diagram_data": diagram_data,
                }
                new_instructions = build_voice_instructions(updated_context)
                omni_client = get_session_omni_client(voice_session_id)
                if omni_client:
                    await omni_client.update_instructions(new_instructions)

                logger.debug("Batch added %d nodes for standard diagram", len(nodes_to_add))

        # Send acknowledgment with reasoning (only if no type mismatch warning was sent)
        summary = extracted_data.get("summary", "已从段落中提取内容并更新图表")

        # Only send acknowledgment if we didn't already send a warning message
        if recommended_type == current_diagram_type:
            acknowledgment_text = f"✅ 已处理段落内容：{summary}"
            if reasoning:
                acknowledgment_text += f"\n\n说明：{reasoning}"

            await safe_websocket_send(websocket, {"type": "text_chunk", "text": acknowledgment_text})
        else:
            # Type mismatch - summary already included in warning message
            # Just send a completion message
            await safe_websocket_send(
                websocket,
                {"type": "text_chunk", "text": "\n✅ 内容已提取并添加到当前图表中。"},
            )

        nodes_added = len(extracted_data.get("nodes", []))
        logger.info(
            "Successfully processed paragraph: intent=%s, diagram_type=%s, recommended=%s, nodes_added=%d",
            intent,
            diagram_type,
            recommended_type,
            nodes_added,
        )
        return True

    except (ValueError, KeyError, json.JSONDecodeError, RuntimeError) as e:
        logger.error("Paragraph processing error: %s", e, exc_info=True)
        await safe_websocket_send(
            websocket,
            {"type": "text_chunk", "text": "处理段落时出现错误，请稍后重试。"},
        )
        return False
