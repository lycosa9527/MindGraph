"""Add-node branch for voice diagram updates."""

from typing import Any, Dict

from fastapi import WebSocket

from services.features.voice_agent import voice_agent_manager

from routers.features.voice.diagram_utils import get_diagram_prefix_map
from routers.features.voice.messaging import (
    build_voice_instructions,
    safe_websocket_send,
)
from routers.features.voice.session_ops import (
    get_agent_session_id,
    get_session_omni_client,
)
from routers.features.voice.state import logger, voice_sessions


async def voice_apply_add_node_action(
    websocket: WebSocket,
    voice_session_id: str,
    command: Dict[str, Any],
    session_context: Dict[str, Any],
) -> bool:
    """Handle add_node actions including palette-open when target is empty."""
    target = command.get("target")
    if target:
        # Check if node_index is specified (for structured input like "branch 1", "branch 2")
        add_node_index = command.get("node_index")
        step_index = command.get("step_index")  # For flow_map substeps
        substep_index = command.get("substep_index")  # For flow_map substeps

        diagram_type = voice_sessions[voice_session_id].get("diagram_type", "circle_map")

        # Extract hierarchical indices for different diagram types
        category_index = command.get("category_index")  # For tree_map items
        item_index = command.get("item_index")  # For tree_map items
        part_index = command.get("part_index")  # For brace_map subparts
        subpart_index = command.get("subpart_index")  # For brace_map subparts
        branch_index = command.get("branch_index")  # For mindmap children
        child_index = command.get("child_index")  # For mindmap children

        # Special handling for tree_map items (category_index + item_index)
        if diagram_type == "tree_map" and category_index is not None and item_index is not None:
            logger.info(
                "Adding item to category %d at position %d: %s",
                category_index,
                item_index,
                target,
            )

            update_payload = {
                "text": target,
                "category_index": category_index,
                "item_index": item_index,
            }

            await safe_websocket_send(
                websocket,
                {
                    "type": "diagram_update",
                    "action": "add_nodes",
                    "updates": [update_payload],
                },
            )

            # Update session context
            diagram_data = session_context.get("diagram_data", {})
            children = diagram_data.get("children", [])

            if 0 <= category_index < len(children):
                category = children[category_index]
                if isinstance(category, dict):
                    if "children" not in category or not isinstance(category["children"], list):
                        category["children"] = []

                    if item_index < len(category["children"]):
                        category["children"].insert(item_index, {"text": target, "children": []})
                    else:
                        while len(category["children"]) < item_index:
                            category["children"].append({"text": "", "children": []})
                        category["children"].insert(item_index, {"text": target, "children": []})

            # Update agent state
            agent_session_id = get_agent_session_id(voice_session_id)
            agent = voice_agent_manager.get_or_create(agent_session_id)
            diagram_data["diagram_type"] = diagram_type
            agent.update_diagram_state(diagram_data)

            updated_context = {
                "diagram_type": diagram_type,
                "active_panel": voice_sessions[voice_session_id].get("active_panel", "none"),
                "conversation_history": voice_sessions[voice_session_id].get("conversation_history", []),
                "selected_nodes": session_context.get("selected_nodes", []),
                "diagram_data": diagram_data,
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

            logger.debug(
                "Item added: category %d, item %d -> %s",
                category_index,
                item_index,
                target,
            )
            return True

        # Special handling for brace_map subparts (part_index + subpart_index)
        if diagram_type == "brace_map" and part_index is not None and subpart_index is not None:
            logger.info(
                "Adding subpart to part %d at position %d: %s",
                part_index,
                subpart_index,
                target,
            )

            update_payload = {
                "text": target,
                "part_index": part_index,
                "subpart_index": subpart_index,
            }

            await safe_websocket_send(
                websocket,
                {
                    "type": "diagram_update",
                    "action": "add_nodes",
                    "updates": [update_payload],
                },
            )

            # Update session context
            diagram_data = session_context.get("diagram_data", {})
            parts = diagram_data.get("parts", [])

            if 0 <= part_index < len(parts):
                part = parts[part_index]
                if isinstance(part, dict):
                    if "subparts" not in part or not isinstance(part["subparts"], list):
                        part["subparts"] = []

                    if subpart_index < len(part["subparts"]):
                        part["subparts"].insert(subpart_index, {"name": target})
                    else:
                        while len(part["subparts"]) < subpart_index:
                            part["subparts"].append({"name": ""})
                        part["subparts"].insert(subpart_index, {"name": target})

            # Update agent state
            agent_session_id = get_agent_session_id(voice_session_id)
            agent = voice_agent_manager.get_or_create(agent_session_id)
            diagram_data["diagram_type"] = diagram_type
            agent.update_diagram_state(diagram_data)

            updated_context = {
                "diagram_type": diagram_type,
                "active_panel": voice_sessions[voice_session_id].get("active_panel", "none"),
                "conversation_history": voice_sessions[voice_session_id].get("conversation_history", []),
                "selected_nodes": session_context.get("selected_nodes", []),
                "diagram_data": diagram_data,
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

            logger.debug(
                "Subpart added: part %d, subpart %d -> %s",
                part_index,
                subpart_index,
                target,
            )
            return True

        # Special handling for mindmap children (branch_index + child_index)
        if diagram_type == "mindmap" and branch_index is not None and child_index is not None:
            logger.info(
                "Adding child to branch %d at position %d: %s",
                branch_index,
                child_index,
                target,
            )

            update_payload = {
                "text": target,
                "branch_index": branch_index,
                "child_index": child_index,
            }

            await safe_websocket_send(
                websocket,
                {
                    "type": "diagram_update",
                    "action": "add_nodes",
                    "updates": [update_payload],
                },
            )

            # Update session context
            diagram_data = session_context.get("diagram_data", {})
            children = diagram_data.get("children", [])

            if 0 <= branch_index < len(children):
                branch = children[branch_index]
                if isinstance(branch, dict):
                    if "children" not in branch or not isinstance(branch["children"], list):
                        branch["children"] = []

                    child_id = f"sub_{branch_index}_{len(branch['children'])}"
                    new_child = {
                        "id": child_id,
                        "label": target,
                        "text": target,
                        "children": [],
                    }

                    if child_index < len(branch["children"]):
                        branch["children"].insert(child_index, new_child)
                    else:
                        branch["children"].append(new_child)

            # Update agent state
            agent_session_id = get_agent_session_id(voice_session_id)
            agent = voice_agent_manager.get_or_create(agent_session_id)
            diagram_data["diagram_type"] = diagram_type
            agent.update_diagram_state(diagram_data)

            updated_context = {
                "diagram_type": diagram_type,
                "active_panel": voice_sessions[voice_session_id].get("active_panel", "none"),
                "conversation_history": voice_sessions[voice_session_id].get("conversation_history", []),
                "selected_nodes": session_context.get("selected_nodes", []),
                "diagram_data": diagram_data,
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

            logger.debug(
                "Child added: branch %d, child %d -> %s",
                branch_index,
                child_index,
                target,
            )
            return True

        # Special handling for concept_map relationships (from, to, label)
        if diagram_type == "concept_map" and command.get("from") and command.get("to") and command.get("label"):
            from_concept = command.get("from")
            to_concept = command.get("to")
            rel_label = command.get("label")

            logger.info(
                "Adding relationship: %s --[%s]--> %s",
                from_concept,
                rel_label,
                to_concept,
            )

            update_payload = {
                "from": from_concept,
                "to": to_concept,
                "label": rel_label,
            }

            await safe_websocket_send(
                websocket,
                {
                    "type": "diagram_update",
                    "action": "add_nodes",
                    "updates": [update_payload],
                },
            )

            # Update session context
            diagram_data = session_context.get("diagram_data", {})
            relationships = diagram_data.get("relationships", [])
            relationships.append({"from": from_concept, "to": to_concept, "label": rel_label})
            diagram_data["relationships"] = relationships

            # Update agent state
            agent_session_id = get_agent_session_id(voice_session_id)
            agent = voice_agent_manager.get_or_create(agent_session_id)
            diagram_data["diagram_type"] = diagram_type
            agent.update_diagram_state(diagram_data)

            updated_context = {
                "diagram_type": diagram_type,
                "active_panel": voice_sessions[voice_session_id].get("active_panel", "none"),
                "conversation_history": voice_sessions[voice_session_id].get("conversation_history", []),
                "selected_nodes": session_context.get("selected_nodes", []),
                "diagram_data": diagram_data,
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

            logger.debug(
                "Relationship added: %s --[%s]--> %s",
                from_concept,
                rel_label,
                to_concept,
            )
            return True

        # Special handling for flow_map substeps
        if diagram_type == "flow_map" and step_index is not None:
            # Adding a substep to a specific step
            logger.info(
                "Adding substep to step %d at position %d: %s",
                step_index,
                substep_index,
                target,
            )

            # Build update payload with step_index and substep_index
            update_payload = {"text": target, "step_index": step_index}
            if substep_index is not None:
                update_payload["substep_index"] = substep_index

            await safe_websocket_send(
                websocket,
                {
                    "type": "diagram_update",
                    "action": "add_nodes",
                    "updates": [update_payload],
                },
            )

            # Update session context
            diagram_data = session_context.get("diagram_data", {})
            steps = diagram_data.get("steps", [])
            substeps = diagram_data.get("substeps", [])

            if 0 <= step_index < len(steps):
                if isinstance(steps[step_index], str):
                    step_name = steps[step_index]
                else:
                    step_name = steps[step_index].get("text", "")

                # Find or create substeps entry for this step
                substeps_entry = None
                for entry in substeps:
                    if isinstance(entry, dict) and entry.get("step") == step_name:
                        substeps_entry = entry
                        break

                if not substeps_entry:
                    if not isinstance(substeps, list):
                        diagram_data["substeps"] = []
                        substeps = diagram_data["substeps"]
                    substeps_entry = {"step": step_name, "substeps": []}
                    substeps.append(substeps_entry)

                # Add substep at specified position
                if not isinstance(substeps_entry.get("substeps"), list):
                    substeps_entry["substeps"] = []

                if substep_index is not None:
                    if substep_index < len(substeps_entry["substeps"]):
                        substeps_entry["substeps"].insert(substep_index, target)
                    else:
                        # Pad with empty strings if needed
                        while len(substeps_entry["substeps"]) < substep_index:
                            substeps_entry["substeps"].append("")
                        substeps_entry["substeps"].insert(substep_index, target)
                else:
                    substeps_entry["substeps"].append(target)

            # Update agent state
            agent_session_id = get_agent_session_id(voice_session_id)
            agent = voice_agent_manager.get_or_create(agent_session_id)
            diagram_data["diagram_type"] = diagram_type
            agent.update_diagram_state(diagram_data)

            updated_context = {
                "diagram_type": diagram_type,
                "active_panel": voice_sessions[voice_session_id].get("active_panel", "none"),
                "conversation_history": voice_sessions[voice_session_id].get("conversation_history", []),
                "selected_nodes": session_context.get("selected_nodes", []),
                "diagram_data": diagram_data,
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

            logger.debug(
                "Substep added: step %d, substep %d -> %s",
                step_index,
                substep_index,
                target,
            )
            return True

        # Get current nodes
        nodes = session_context.get("diagram_data", {}).get("children", [])
        prefix_map = get_diagram_prefix_map()
        prefix = prefix_map.get(diagram_type, "node")

        # If node_index is specified, check if node exists at that position
        if add_node_index is not None:
            # Check if node already exists at this position
            if 0 <= add_node_index < len(nodes):
                # Node exists - use update_node instead
                logger.info(
                    "Node exists at index %d, updating instead of adding: %s",
                    add_node_index,
                    target,
                )
                existing_node = nodes[add_node_index]
                if isinstance(existing_node, dict):
                    existing_node_id = existing_node.get("id")
                else:
                    existing_node_id = f"{prefix}_{add_node_index}"

                await safe_websocket_send(
                    websocket,
                    {
                        "type": "diagram_update",
                        "action": "update_nodes",
                        "updates": [{"node_id": existing_node_id, "new_text": target}],
                    },
                )

                # Update session context
                if isinstance(existing_node, dict):
                    existing_node["text"] = target
                else:
                    nodes[add_node_index] = target
            else:
                # Node doesn't exist - insert at specified position
                logger.info("Adding node at position %d: %s", add_node_index, target)
                new_node = {
                    "id": f"{prefix}_{add_node_index}",
                    "index": add_node_index,
                    "text": target,
                }

                # Insert at specified position (pad with None if needed)
                while len(nodes) < add_node_index:
                    nodes.append(None)
                nodes.insert(add_node_index, new_node)

                # Build update payload with diagram-specific fields
                update_payload = {"text": target, "index": add_node_index}

                # Add category if specified (for double bubble map, multi-flow map)
                category = command.get("category")
                if category:
                    update_payload["category"] = category

                # Add left/right if specified (for bridge map analogies)
                left = command.get("left")
                right = command.get("right")
                if left and right:
                    update_payload["left"] = left
                    update_payload["right"] = right

                # Send update with position information and diagram-specific fields
                await safe_websocket_send(
                    websocket,
                    {
                        "type": "diagram_update",
                        "action": "add_nodes",
                        "updates": [update_payload],
                    },
                )
        else:
            # No position specified - add to end (default behavior)
            logger.info("Adding node to end: %s", target)
            new_node = {
                "id": f"{prefix}_{len(nodes)}",
                "index": len(nodes),
                "text": target,
            }
            nodes.append(new_node)

            # Build update payload with diagram-specific fields
            update_payload = {"text": target}

            # Add category if specified (for double bubble map, multi-flow map)
            category = command.get("category")
            if category:
                update_payload["category"] = category

            # Add left/right if specified (for bridge map analogies)
            left = command.get("left")
            right = command.get("right")
            if left and right:
                update_payload["left"] = left
                update_payload["right"] = right

            await safe_websocket_send(
                websocket,
                {
                    "type": "diagram_update",
                    "action": "add_nodes",
                    "updates": [update_payload],
                },
            )

        # Update agent state and instructions
        # CRITICAL: Agent is scoped to diagram_session_id, not voice_session_id
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

        logger.debug("Node added: %s", target)
        return True
    else:
        count = command.get("count", 1)
        logger.debug("Opening node palette for adding %d node(s)", count)
        await safe_websocket_send(
            websocket,
            {
                "type": "action",
                "action": "open_node_palette",
                "params": {"count": count},
            },
        )
        return True
