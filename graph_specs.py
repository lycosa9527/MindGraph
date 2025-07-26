# graph_specs.py
"""
Graph spec schemas and validation for D3.js rendering.
"""
# Each function validates the JSON spec for a specific graph type

def validate_double_bubble_map(spec):
    """Enhanced validation for double bubble map."""
    if not isinstance(spec, dict):
        return False, "Spec must be a dictionary"
    
    required = ["left", "right", "similarities", "left_differences", "right_differences"]
    for k in required:
        if k not in spec:
            return False, f"Missing key: {k}"
    
    # Validate string fields
    if not isinstance(spec["left"], str) or not spec["left"].strip():
        return False, "left must be a non-empty string"
    if not isinstance(spec["right"], str) or not spec["right"].strip():
        return False, "right must be a non-empty string"
    
    # Validate array fields
    for field in ["similarities", "left_differences", "right_differences"]:
        if not isinstance(spec[field], list):
            return False, f"{field} must be a list"
        if len(spec[field]) == 0:
            return False, f"{field} cannot be empty"
        if len(spec[field]) > 20:  # Reasonable limit
            return False, f"{field} cannot have more than 20 items"
        
        # Validate each item in the array
        for i, item in enumerate(spec[field]):
            if not isinstance(item, str) or not item.strip():
                return False, f"{field}[{i}] must be a non-empty string"
            if len(item) > 100:  # Reasonable length limit
                return False, f"{field}[{i}] cannot be longer than 100 characters"
    
    return True, ''

def validate_bubble_map(spec):
    """Enhanced validation for bubble map."""
    if not isinstance(spec, dict):
        return False, "Spec must be a dictionary"
    
    required = ["topic", "left", "right"]
    for k in required:
        if k not in spec:
            return False, f"Missing key: {k}"
    
    # Validate string fields
    if not isinstance(spec["topic"], str) or not spec["topic"].strip():
        return False, "topic must be a non-empty string"
    
    # Validate array fields
    for field in ["left", "right"]:
        if not isinstance(spec[field], list):
            return False, f"{field} must be a list"
        if len(spec[field]) == 0:
            return False, f"{field} cannot be empty"
        if len(spec[field]) > 20:  # Reasonable limit
            return False, f"{field} cannot have more than 20 items"
        
        # Validate each item in the array
        for i, item in enumerate(spec[field]):
            if not isinstance(item, str) or not item.strip():
                return False, f"{field}[{i}] must be a non-empty string"
            if len(item) > 100:  # Reasonable length limit
                return False, f"{field}[{i}] cannot be longer than 100 characters"
    
    return True, ''

def validate_circle_map(spec):
    """Enhanced validation for circle map."""
    if not isinstance(spec, dict):
        return False, "Spec must be a dictionary"
    
    required = ["topic", "characteristics"]
    for k in required:
        if k not in spec:
            return False, f"Missing key: {k}"
    
    # Validate string fields
    if not isinstance(spec["topic"], str) or not spec["topic"].strip():
        return False, "topic must be a non-empty string"
    
    # Validate characteristics array
    if not isinstance(spec["characteristics"], list):
        return False, "characteristics must be a list"
    if len(spec["characteristics"]) == 0:
        return False, "characteristics cannot be empty"
    if len(spec["characteristics"]) > 20:  # Reasonable limit
        return False, "characteristics cannot have more than 20 items"
    
    # Validate each characteristic
    for i, item in enumerate(spec["characteristics"]):
        if not isinstance(item, str) or not item.strip():
            return False, f"characteristics[{i}] must be a non-empty string"
        if len(item) > 100:  # Reasonable length limit
            return False, f"characteristics[{i}] cannot be longer than 100 characters"
    
    return True, ''

def validate_tree_map(spec):
    required = ["topic", "children"]
    for k in required:
        if k not in spec:
            return False, f"Missing key: {k}"
    if not isinstance(spec["children"], list):
        return False, "children must be a list"
    return True, ''

def validate_concept_map(spec):
    required = ["topic", "concepts"]
    for k in required:
        if k not in spec:
            return False, f"Missing key: {k}"
    if not isinstance(spec["concepts"], list):
        return False, "concepts must be a list"
    return True, ''

def validate_mindmap(spec):
    required = ["topic", "children"]
    for k in required:
        if k not in spec:
            return False, f"Missing key: {k}"
    if not isinstance(spec["children"], list):
        return False, "children must be a list"
    return True, '' 