"""Delete-node branch for voice diagram updates."""
from typing import Any, Dict, Optional

from fastapi import WebSocket, WebSocketDisconnect

from services.features.voice_agent import voice_agent_manager

from routers.features.voice.diagram_utils import get_diagram_prefix_map
from routers.features.voice.messaging import build_voice_instructions, safe_websocket_send
from routers.features.voice.session_ops import get_agent_session_id, get_session_omni_client
from routers.features.voice.state import logger, voice_sessions


async def voice_apply_delete_node_action(
    websocket: WebSocket,
    voice_session_id: str,
    command: Dict[str, Any],
    session_context: Dict[str, Any],
    target: Optional[str],
    node_index: Optional[Any],
    _node_identifier: Optional[Any],
) -> bool:
    """Handle delete_node with diagram-specific index and id resolution."""
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
