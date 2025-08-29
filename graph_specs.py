# graph_specs.py
"""
Graph spec schemas and validation for D3.js rendering.
Organized by diagram categories for easy maintenance and extension.
"""

from typing import Dict, List, Tuple, Any, Optional
import re

# ============================================================================
# BASE VALIDATION UTILITIES
# ============================================================================

def validate_required_fields(spec: Dict, required_fields: List[str]) -> Tuple[bool, str]:
    """Validate that all required fields are present in the spec."""
    if not isinstance(spec, dict):
        return False, "Spec must be a dictionary"
    
    for field in required_fields:
        if field not in spec:
            return False, f"Missing required field: {field}"
    
    return True, ""

def validate_string_field(spec: Dict, field_name: str, max_length: int = 100) -> Tuple[bool, str]:
    """Validate a string field in the spec."""
    if not isinstance(spec[field_name], str) or not spec[field_name].strip():
        return False, f"{field_name} must be a non-empty string"
    
    if len(spec[field_name]) > max_length:
        return False, f"{field_name} cannot be longer than {max_length} characters"
    
    return True, ""

def validate_list_field(spec: Dict, field_name: str, max_items: int = 20, 
                       item_max_length: int = 100, allow_empty: bool = False) -> Tuple[bool, str]:
    """Validate a list field in the spec."""
    if not isinstance(spec[field_name], list):
        return False, f"{field_name} must be a list"
    
    if not allow_empty and len(spec[field_name]) == 0:
        return False, f"{field_name} cannot be empty"
    
    if len(spec[field_name]) > max_items:
        return False, f"{field_name} cannot have more than {max_items} items"
    
    # Validate each item in the list
    for i, item in enumerate(spec[field_name]):
        if not isinstance(item, str) or not item.strip():
            return False, f"{field_name}[{i}] must be a non-empty string"
        if len(item) > item_max_length:
            return False, f"{field_name}[{i}] cannot be longer than {item_max_length} characters"
    
    return True, ""

def validate_node_structure(node: Dict, node_type: str = "node") -> Tuple[bool, str]:
    """Validate a node structure with id, label, and optional children."""
    if not isinstance(node, dict):
        return False, f"{node_type} must be a dictionary"
    
    if "id" not in node or "label" not in node:
        return False, f"{node_type} must have 'id' and 'label' fields"
    
    # Validate id and label
    if not isinstance(node["id"], str) or not node["id"].strip():
        return False, f"{node_type}.id must be a non-empty string"
    
    if not isinstance(node["label"], str) or not node["label"].strip():
        return False, f"{node_type}.label must be a non-empty string"
    
    # Validate children if present
    if "children" in node:
        if not isinstance(node["children"], list):
            return False, f"{node_type}.children must be a list"
        
        for i, child in enumerate(node["children"]):
            is_valid, error = validate_node_structure(child, f"{node_type}.children[{i}]")
            if not is_valid:
                return False, error
    
    return True, ""

# ============================================================================
# THINKING MAPS CATEGORY
# ============================================================================

def validate_double_bubble_map(spec: Dict) -> Tuple[bool, str]:
    """Enhanced validation for double bubble map (thinking map)."""
    # Support both formats: agent format (topic1/topic2) and renderer format (left/right)
    
    # Check for agent format first (topic1/topic2/topic1_attributes/etc.)
    has_agent_format = all(field in spec for field in ["topic1", "topic2", "topic1_attributes", "topic2_attributes", "shared_attributes"])
    
    # Check for renderer format (left/right/similarities/etc.)
    has_renderer_format = all(field in spec for field in ["left", "right", "similarities", "left_differences", "right_differences"])
    
    if has_agent_format:
        # Validate agent format
        for field in ["topic1", "topic2"]:
            is_valid, error = validate_string_field(spec, field)
            if not is_valid:
                return False, error
        
        for field in ["topic1_attributes", "topic2_attributes", "shared_attributes"]:
            is_valid, error = validate_list_field(spec, field)
            if not is_valid:
                return False, error
                
    elif has_renderer_format:
        # Validate renderer format
        for field in ["left", "right"]:
            is_valid, error = validate_string_field(spec, field)
            if not is_valid:
                return False, error
        
        for field in ["similarities", "left_differences", "right_differences"]:
            is_valid, error = validate_list_field(spec, field)
            if not is_valid:
                return False, error
    else:
        return False, "Missing required fields for double bubble map. Expected either (topic1, topic2, topic1_attributes, topic2_attributes, shared_attributes) or (left, right, similarities, left_differences, right_differences)"
    
    return True, ""

def validate_bubble_map(spec: Dict) -> Tuple[bool, str]:
    """Enhanced validation for bubble map (thinking map) - for describing attributes. Updated 2025-08-29 07:35"""
    # Validate required fields
    is_valid, error = validate_required_fields(spec, ["topic", "attributes"])
    if not is_valid:
        return False, error
    
    # Validate topic field
    is_valid, error = validate_string_field(spec, "topic")
    if not is_valid:
        return False, error
    
    # Validate attributes list (renderer expects strings)
    is_valid, error = validate_list_field(spec, "attributes")
    if not is_valid:
        return False, error
    
    return True, ""

def validate_circle_map(spec: Dict) -> Tuple[bool, str]:
    """Enhanced validation for circle map (thinking map) - for defining in context."""
    # Validate required fields
    is_valid, error = validate_required_fields(spec, ["topic", "context"])
    if not is_valid:
        return False, error
    
    # Validate topic field
    is_valid, error = validate_string_field(spec, "topic")
    if not is_valid:
        return False, error
    
    # Validate context list
    is_valid, error = validate_list_field(spec, "context")
    if not is_valid:
        return False, error
    
    return True, ""

def validate_flow_map(spec: Dict) -> Tuple[bool, str]:
    """Validation for flow map (thinking map)."""
    # Validate required fields
    is_valid, error = validate_required_fields(spec, ["title", "steps"])
    if not is_valid:
        return False, error
    
    # Validate title field
    is_valid, error = validate_string_field(spec, "title")
    if not is_valid:
        return False, error
    
    # Validate steps list
    is_valid, error = validate_list_field(spec, "steps", max_items=15)
    if not is_valid:
        return False, error
    
    return True, ""

def validate_brace_map(spec: Dict) -> Tuple[bool, str]:
    """Validation for brace map (thinking map)."""
    # Validate required fields
    is_valid, error = validate_required_fields(spec, ["topic", "parts"])
    if not is_valid:
        return False, error
    
    # Validate topic field
    is_valid, error = validate_string_field(spec, "topic")
    if not is_valid:
        return False, error
    
    # Validate parts structure
    if not isinstance(spec["parts"], list):
        return False, "parts must be a list"
    
    if len(spec["parts"]) == 0:
        return False, "parts cannot be empty"
    
    if len(spec["parts"]) > 10:
        return False, "parts cannot have more than 10 items"
    
    # Validate each part structure
    for i, part in enumerate(spec["parts"]):
        if not isinstance(part, dict):
            return False, f"parts[{i}] must be a dictionary"
        
        if "name" not in part:
            return False, f"parts[{i}] must have 'name' field"
        
        # Validate part name
        if not isinstance(part["name"], str) or not part["name"].strip():
            return False, f"parts[{i}].name must be a non-empty string"
        
        # Validate subparts if present
        if "subparts" in part:
            if not isinstance(part["subparts"], list):
                return False, f"parts[{i}].subparts must be a list"
            
            for j, subpart in enumerate(part["subparts"]):
                # Accept both strings and dictionaries for subparts
                if isinstance(subpart, str):
                    # If subpart is a string, validate it's not empty
                    if not subpart.strip():
                        return False, f"parts[{i}].subparts[{j}] cannot be empty"
                elif isinstance(subpart, dict):
                    # If subpart is a dictionary, validate it has required fields
                    if "name" not in subpart:
                        return False, f"parts[{i}].subparts[{j}] must have 'name' field"
                    
                    if not isinstance(subpart["name"], str) or not subpart["name"].strip():
                        return False, f"parts[{i}].subparts[{j}].name must be a non-empty string"
                else:
                    return False, f"parts[{i}].subparts[{j}] must be a string or dictionary"
    
    return True, ""

def validate_tree_map(spec: Dict) -> Tuple[bool, str]:
    """Enhanced validation for tree map (thinking map)."""
    # Validate required fields
    is_valid, error = validate_required_fields(spec, ["topic", "children"])
    if not is_valid:
        return False, error
    
    # Validate topic field
    is_valid, error = validate_string_field(spec, "topic")
    if not is_valid:
        return False, error
    
    # Validate children list
    if not isinstance(spec["children"], list):
        return False, "children must be a list"
    
    if len(spec["children"]) == 0:
        return False, "children cannot be empty"
    
    # Validate each child node
    for i, child in enumerate(spec["children"]):
        is_valid, error = validate_node_structure(child, f"children[{i}]")
        if not is_valid:
            return False, error
    
    return True, ""

def validate_multi_flow_map(spec: Dict) -> Tuple[bool, str]:
    """Validation for multi-flow map (thinking map)."""
    # Validate required fields
    is_valid, error = validate_required_fields(spec, ["event", "causes", "effects"])
    if not is_valid:
        return False, error
    
    # Validate event field
    is_valid, error = validate_string_field(spec, "event")
    if not is_valid:
        return False, error
    
    # Validate causes and effects lists
    for field in ["causes", "effects"]:
        is_valid, error = validate_list_field(spec, field, max_items=10)
        if not is_valid:
            return False, error
    
    return True, ""

def validate_bridge_map(spec: Dict) -> Tuple[bool, str]:
    """Validation for bridge map (thinking map) - for analogies and similarities between relationships."""
    # Support both formats: agent format (analogy_bridge/left_side/right_side) and renderer format (relating_factor/analogies)
    
    # Check for agent format first (analogy_bridge/left_side/right_side/bridge_connections)
    has_agent_format = all(field in spec for field in ["analogy_bridge", "left_side", "right_side", "bridge_connections"])
    
    # Check for renderer format (relating_factor/analogies)
    has_renderer_format = all(field in spec for field in ["relating_factor", "analogies"])
    
    if has_agent_format:
        # Validate agent format
        is_valid, error = validate_string_field(spec, "analogy_bridge")
        if not is_valid:
            return False, error
        
        # Validate left_side and right_side structures
        for side in ["left_side", "right_side"]:
            if not isinstance(spec[side], dict):
                return False, f"{side} must be a dictionary"
            if 'topic' not in spec[side] or not spec[side]['topic']:
                return False, f"Missing or empty {side} topic"
            if 'elements' not in spec[side] or not isinstance(spec[side]['elements'], list):
                return False, f"Missing or invalid {side} elements"
        
        # Validate bridge_connections
        if not isinstance(spec["bridge_connections"], list):
            return False, "bridge_connections must be a list"
            
    elif has_renderer_format:
        # Validate renderer format
        is_valid, error = validate_string_field(spec, "relating_factor")
        if not is_valid:
            return False, error
        
        # Validate analogies list
        if not isinstance(spec["analogies"], list):
            return False, "analogies must be a list"
        
        if len(spec["analogies"]) == 0:
            return False, "analogies cannot be empty"
        
        if len(spec["analogies"]) > 10:  # Reasonable limit for analogies
            return False, "analogies cannot have more than 10 items"
        
        # Validate individual analogies
        for i, analogy in enumerate(spec["analogies"]):
            if not isinstance(analogy, dict):
                return False, f"analogies[{i}] must be a dictionary"
            
            if "left" not in analogy or "right" not in analogy:
                return False, f"analogies[{i}] must have 'left' and 'right' fields"
            
            # Validate left field
            if not isinstance(analogy["left"], str) or not analogy["left"].strip():
                return False, f"analogies[{i}].left must be a non-empty string"
            
            # Validate right field
            if not isinstance(analogy["right"], str) or not analogy["right"].strip():
                return False, f"analogies[{i}].right must be a non-empty string"
            
            # Validate id field (optional but recommended)
            if "id" in analogy:
                if not isinstance(analogy["id"], int):
                    return False, f"analogies[{i}].id must be an integer"
    else:
        return False, "Missing required fields for bridge map. Expected either (analogy_bridge, left_side, right_side, bridge_connections) or (relating_factor, analogies)"
    
    return True, ""

# ============================================================================
# CONCEPT MAPS CATEGORY
# ============================================================================

def validate_concept_map(spec: Dict) -> Tuple[bool, str]:
    """Enhanced validation for concept map."""
    # Validate required fields
    is_valid, error = validate_required_fields(spec, ["topic", "concepts", "relationships"])
    if not is_valid:
        return False, error
    
    # Validate topic field
    is_valid, error = validate_string_field(spec, "topic")
    if not is_valid:
        return False, error
    
    # Validate concepts list (allow richer maps)
    is_valid, error = validate_list_field(spec, "concepts", max_items=30)
    if not is_valid:
        return False, error
    
    # Validate relationships
    if not isinstance(spec["relationships"], list):
        return False, "relationships must be a list"
    
    for i, rel in enumerate(spec["relationships"]):
        if not isinstance(rel, dict):
            return False, f"relationships[{i}] must be a dictionary"
        
        if "from" not in rel or "to" not in rel or "label" not in rel:
            return False, f"relationships[{i}] must have 'from', 'to', and 'label' fields"
        
        # Validate relationship fields
        for field in ["from", "to", "label"]:
            if not isinstance(rel[field], str) or not rel[field].strip():
                return False, f"relationships[{i}].{field} must be a non-empty string"
    
    return True, ""



# ============================================================================
# MIND MAPS CATEGORY
# ============================================================================

def validate_mindmap(spec: Dict) -> Tuple[bool, str]:
    """Enhanced validation for mind map."""
    # Validate required fields
    is_valid, error = validate_required_fields(spec, ["topic", "children"])
    if not is_valid:
        return False, error
    
    # Validate topic field
    is_valid, error = validate_string_field(spec, "topic")
    if not is_valid:
        return False, error
    
    # Validate children list
    if not isinstance(spec["children"], list):
        return False, "children must be a list"
    
    if len(spec["children"]) == 0:
        return False, "children cannot be empty"
    
    # Validate each child node
    for i, child in enumerate(spec["children"]):
        is_valid, error = validate_node_structure(child, f"children[{i}]")
        if not is_valid:
            return False, error
    
    return True, ""



# ============================================================================
# DIAGRAM REGISTRY AND DISPATCHER
# ============================================================================

# Registry of all available diagram validators
DIAGRAM_VALIDATORS = {
    # Thinking Maps
    "double_bubble_map": validate_double_bubble_map,
    "bubble_map": validate_bubble_map,
    "circle_map": validate_circle_map,
    "flow_map": validate_flow_map,
    "brace_map": validate_brace_map,
    "tree_map": validate_tree_map,
    "multi_flow_map": validate_multi_flow_map,
    "bridge_map": validate_bridge_map,
    
    # Concept Maps
    "concept_map": validate_concept_map,
    
    # Mind Maps
    "mindmap": validate_mindmap,
    
    # Common Diagrams
}

def get_available_diagram_types() -> List[str]:
    """Get list of all available diagram types."""
    return list(DIAGRAM_VALIDATORS.keys())

def validate_diagram_spec(diagram_type: str, spec: Dict) -> Tuple[bool, str]:
    """
    Main validation function that dispatches to the appropriate validator.
    
    Args:
        diagram_type: Type of diagram to validate
        spec: The diagram specification dictionary
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if diagram_type not in DIAGRAM_VALIDATORS:
        return False, f"Unknown diagram type: {diagram_type}. Available types: {get_available_diagram_types()}"
    
    validator = DIAGRAM_VALIDATORS[diagram_type]
    return validator(spec)

def add_diagram_validator(diagram_type: str, validator_func) -> None:
    """
    Add a new diagram validator to the registry.
    
    Args:
        diagram_type: Name of the diagram type
        validator_func: Function that takes a spec dict and returns (bool, str)
    """
    if not callable(validator_func):
        raise ValueError("validator_func must be callable")
    
    DIAGRAM_VALIDATORS[diagram_type] = validator_func

# ============================================================================
# LEGACY COMPATIBILITY
# ============================================================================

# Keep the original function names for backward compatibility
# These will be removed in a future version

def validate_tree_map_legacy(spec):
    """Legacy tree map validation - use validate_tree_map instead."""
    return validate_tree_map(spec)

def validate_concept_map_legacy(spec):
    """Legacy concept map validation - use validate_concept_map instead."""
    return validate_concept_map(spec)

def validate_mindmap_legacy(spec):
    """Legacy mind map validation - use validate_mindmap instead."""
    return validate_mindmap(spec) 