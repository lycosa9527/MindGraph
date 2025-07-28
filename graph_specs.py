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
    # Validate required fields
    is_valid, error = validate_required_fields(spec, ["left", "right", "similarities", "left_differences", "right_differences"])
    if not is_valid:
        return False, error
    
    # Validate string fields
    for field in ["left", "right"]:
        is_valid, error = validate_string_field(spec, field)
        if not is_valid:
            return False, error
    
    # Validate list fields
    for field in ["similarities", "left_differences", "right_differences"]:
        is_valid, error = validate_list_field(spec, field)
        if not is_valid:
            return False, error
    
    return True, ""

def validate_bubble_map(spec: Dict) -> Tuple[bool, str]:
    """Enhanced validation for bubble map (thinking map) - for describing attributes."""
    # Validate required fields
    is_valid, error = validate_required_fields(spec, ["topic", "attributes"])
    if not is_valid:
        return False, error
    
    # Validate topic field
    is_valid, error = validate_string_field(spec, "topic")
    if not is_valid:
        return False, error
    
    # Validate attributes list
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
                if not isinstance(subpart, dict):
                    return False, f"parts[{i}].subparts[{j}] must be a dictionary"
                
                if "name" not in subpart:
                    return False, f"parts[{i}].subparts[{j}] must have 'name' field"
                
                if not isinstance(subpart["name"], str) or not subpart["name"].strip():
                    return False, f"parts[{i}].subparts[{j}].name must be a non-empty string"
    
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
    # Validate required fields
    is_valid, error = validate_required_fields(spec, ["relating_factor", "analogies"])
    if not is_valid:
        return False, error
    
    # Validate relating factor
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
    
    # Validate concepts list
    is_valid, error = validate_list_field(spec, "concepts", max_items=15)
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

def validate_semantic_web(spec: Dict) -> Tuple[bool, str]:
    """Validation for semantic web (concept map variant)."""
    # Validate required fields
    is_valid, error = validate_required_fields(spec, ["topic", "branches"])
    if not is_valid:
        return False, error
    
    # Validate topic field
    is_valid, error = validate_string_field(spec, "topic")
    if not is_valid:
        return False, error
    
    # Validate branches
    if not isinstance(spec["branches"], list):
        return False, "branches must be a list"
    
    if len(spec["branches"]) == 0:
        return False, "branches cannot be empty"
    
    for i, branch in enumerate(spec["branches"]):
        if not isinstance(branch, dict):
            return False, f"branches[{i}] must be a dictionary"
        
        if "name" not in branch:
            return False, f"branches[{i}] must have 'name' field"
        
        # Validate name
        if not isinstance(branch["name"], str) or not branch["name"].strip():
            return False, f"branches[{i}].name must be a non-empty string"
        
        # Validate children if present
        if "children" in branch:
            if not isinstance(branch["children"], list):
                return False, f"branches[{i}].children must be a list"
            
            for j, child in enumerate(branch["children"]):
                if not isinstance(child, dict):
                    return False, f"branches[{i}].children[{j}] must be a dictionary"
                
                if "name" not in child:
                    return False, f"branches[{i}].children[{j}] must have 'name' field"
                
                if not isinstance(child["name"], str) or not child["name"].strip():
                    return False, f"branches[{i}].children[{j}].name must be a non-empty string"
    
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

def validate_radial_mindmap(spec: Dict) -> Tuple[bool, str]:
    """Validation for radial mind map."""
    # Validate required fields
    is_valid, error = validate_required_fields(spec, ["topic", "branches"])
    if not is_valid:
        return False, error
    
    # Validate topic field
    is_valid, error = validate_string_field(spec, "topic")
    if not is_valid:
        return False, error
    
    # Validate branches
    if not isinstance(spec["branches"], list):
        return False, "branches must be a list"
    
    if len(spec["branches"]) == 0:
        return False, "branches cannot be empty"
    
    if len(spec["branches"]) > 8:  # Limit for radial layout
        return False, "branches cannot have more than 8 items"
    
    for i, branch in enumerate(spec["branches"]):
        if not isinstance(branch, dict):
            return False, f"branches[{i}] must be a dictionary"
        
        if "name" not in branch:
            return False, f"branches[{i}] must have 'name' field"
        
        # Validate name
        if not isinstance(branch["name"], str) or not branch["name"].strip():
            return False, f"branches[{i}].name must be a non-empty string"
        
        # Validate children if present
        if "children" in branch:
            if not isinstance(branch["children"], list):
                return False, f"branches[{i}].children must be a list"
            
            for j, child in enumerate(branch["children"]):
                if not isinstance(child, dict):
                    return False, f"branches[{i}].children[{j}] must be a dictionary"
                
                if "name" not in child:
                    return False, f"branches[{i}].children[{j}] must have 'name' field"
                
                if not isinstance(child["name"], str) or not child["name"].strip():
                    return False, f"branches[{i}].children[{j}].name must be a non-empty string"
    
    return True, ""

# ============================================================================
# COMMON DIAGRAMS CATEGORY
# ============================================================================

def validate_venn_diagram(spec: Dict) -> Tuple[bool, str]:
    """Validation for Venn diagram."""
    # Validate required fields
    is_valid, error = validate_required_fields(spec, ["sets"])
    if not is_valid:
        return False, error
    
    # Validate sets
    if not isinstance(spec["sets"], list):
        return False, "sets must be a list"
    
    if len(spec["sets"]) < 2 or len(spec["sets"]) > 4:  # Support 2-4 sets
        return False, "sets must have between 2 and 4 items"
    
    for i, set_data in enumerate(spec["sets"]):
        if not isinstance(set_data, dict):
            return False, f"sets[{i}] must be a dictionary"
        
        if "name" not in set_data or "items" not in set_data:
            return False, f"sets[{i}] must have 'name' and 'items' fields"
        
        # Validate set name
        if not isinstance(set_data["name"], str) or not set_data["name"].strip():
            return False, f"sets[{i}].name must be a non-empty string"
        
        # Validate set items
        is_valid, error = validate_list_field(set_data, "items", max_items=15)
        if not is_valid:
            return False, f"sets[{i}].{error}"
    
    return True, ""

def validate_fishbone_diagram(spec: Dict) -> Tuple[bool, str]:
    """Validation for fishbone (Ishikawa) diagram."""
    # Validate required fields
    is_valid, error = validate_required_fields(spec, ["problem", "categories"])
    if not is_valid:
        return False, error
    
    # Validate problem
    is_valid, error = validate_string_field(spec, "problem")
    if not is_valid:
        return False, error
    
    # Validate categories
    if not isinstance(spec["categories"], list):
        return False, "categories must be a list"
    
    if len(spec["categories"]) == 0:
        return False, "categories cannot be empty"
    
    if len(spec["categories"]) > 6:  # Limit for fishbone layout
        return False, "categories cannot have more than 6 items"
    
    for i, category in enumerate(spec["categories"]):
        if not isinstance(category, dict):
            return False, f"categories[{i}] must be a dictionary"
        
        if "name" not in category or "causes" not in category:
            return False, f"categories[{i}] must have 'name' and 'causes' fields"
        
        # Validate category name
        if not isinstance(category["name"], str) or not category["name"].strip():
            return False, f"categories[{i}].name must be a non-empty string"
        
        # Validate causes
        if not isinstance(category["causes"], list):
            return False, f"categories[{i}].causes must be a list"
        
        for j, cause in enumerate(category["causes"]):
            if not isinstance(cause, str) or not cause.strip():
                return False, f"categories[{i}].causes[{j}] must be a non-empty string"
    
    return True, ""

def validate_flowchart(spec: Dict) -> Tuple[bool, str]:
    """Validation for flowchart."""
    # Validate required fields
    is_valid, error = validate_required_fields(spec, ["title", "steps"])
    if not is_valid:
        return False, error
    
    # Validate title
    is_valid, error = validate_string_field(spec, "title")
    if not is_valid:
        return False, error
    
    # Validate steps
    if not isinstance(spec["steps"], list):
        return False, "steps must be a list"
    
    if len(spec["steps"]) == 0:
        return False, "steps cannot be empty"
    
    for i, step in enumerate(spec["steps"]):
        if not isinstance(step, dict):
            return False, f"steps[{i}] must be a dictionary"
        
        if "id" not in step or "type" not in step or "text" not in step:
            return False, f"steps[{i}] must have 'id', 'type', and 'text' fields"
        
        # Validate step fields
        for field in ["id", "text"]:
            if not isinstance(step[field], str) or not step[field].strip():
                return False, f"steps[{i}].{field} must be a non-empty string"
        
        # Validate type
        valid_types = ["start", "process", "decision", "end", "input", "output"]
        if step["type"] not in valid_types:
            return False, f"steps[{i}].type must be one of: {valid_types}"
    
    return True, ""

def validate_org_chart(spec: Dict) -> Tuple[bool, str]:
    """Validation for organizational chart."""
    # Validate required fields
    is_valid, error = validate_required_fields(spec, ["title", "structure"])
    if not is_valid:
        return False, error
    
    # Validate title
    is_valid, error = validate_string_field(spec, "title")
    if not is_valid:
        return False, error
    
    # Validate structure
    if not isinstance(spec["structure"], dict):
        return False, "structure must be a dictionary"
    
    # Validate root node structure
    is_valid, error = validate_org_node_structure(spec["structure"], "structure")
    if not is_valid:
        return False, error
    
    return True, ""

def validate_org_node_structure(node: Dict, node_type: str = "node") -> Tuple[bool, str]:
    """Validate organizational chart node structure."""
    if not isinstance(node, dict):
        return False, f"{node_type} must be a dictionary"
    
    if "name" not in node or "title" not in node:
        return False, f"{node_type} must have 'name' and 'title' fields"
    
    # Validate name and title
    for field in ["name", "title"]:
        if not isinstance(node[field], str) or not node[field].strip():
            return False, f"{node_type}.{field} must be a non-empty string"
    
    # Validate children if present
    if "children" in node:
        if not isinstance(node["children"], list):
            return False, f"{node_type}.children must be a list"
        
        for i, child in enumerate(node["children"]):
            is_valid, error = validate_org_node_structure(child, f"{node_type}.children[{i}]")
            if not is_valid:
                return False, error
    
    return True, ""

def validate_timeline(spec: Dict) -> Tuple[bool, str]:
    """Validation for timeline diagram."""
    # Validate required fields
    is_valid, error = validate_required_fields(spec, ["title", "events"])
    if not is_valid:
        return False, error
    
    # Validate title
    is_valid, error = validate_string_field(spec, "title")
    if not is_valid:
        return False, error
    
    # Validate events
    if not isinstance(spec["events"], list):
        return False, "events must be a list"
    
    if len(spec["events"]) == 0:
        return False, "events cannot be empty"
    
    for i, event in enumerate(spec["events"]):
        if not isinstance(event, dict):
            return False, f"events[{i}] must be a dictionary"
        
        if "date" not in event or "title" not in event or "description" not in event:
            return False, f"events[{i}] must have 'date', 'title', and 'description' fields"
        
        # Validate event fields
        for field in ["date", "title", "description"]:
            if not isinstance(event[field], str) or not event[field].strip():
                return False, f"events[{i}].{field} must be a non-empty string"
    
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
    "semantic_web": validate_semantic_web,
    
    # Mind Maps
    "mindmap": validate_mindmap,
    "radial_mindmap": validate_radial_mindmap,
    
    # Common Diagrams
    "venn_diagram": validate_venn_diagram,
    "fishbone_diagram": validate_fishbone_diagram,
    "flowchart": validate_flowchart,
    "org_chart": validate_org_chart,
    "timeline": validate_timeline,
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