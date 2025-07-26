#!/usr/bin/env python3
"""
Simple test script to verify the main improvements work correctly.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import config
import agent
import graph_specs

def test_config_validation():
    """Test configuration validation."""
    print("Testing configuration validation...")
    
    # Test basic validation
    assert config.validate_qwen_config() or not config.QWEN_API_KEY, "Qwen config validation failed"
    assert config.validate_numeric_config(), "Numeric config validation failed"
    
    # Test D3.js theme and dimensions
    theme = config.get_d3_theme()
    dimensions = config.get_d3_dimensions()
    
    assert isinstance(theme, dict), "Theme should be a dictionary"
    assert isinstance(dimensions, dict), "Dimensions should be a dictionary"
    assert 'topicFill' in theme, "Theme should contain topicFill"
    assert 'baseWidth' in dimensions, "Dimensions should contain baseWidth"
    
    print("✅ Configuration validation passed")

def test_graph_type_classification():
    """Test graph type classification."""
    print("Testing graph type classification...")
    
    # Test Chinese prompts
    result1 = agent.classify_graph_type_with_llm("比较猫和狗", "zh")
    assert result1 in ['double_bubble_map', 'bubble_map', 'circle_map'], f"Invalid result: {result1}"
    
    # Test English prompts
    result2 = agent.classify_graph_type_with_llm("compare cats and dogs", "en")
    assert result2 in ['double_bubble_map', 'bubble_map', 'circle_map'], f"Invalid result: {result2}"
    
    print("✅ Graph type classification passed")

def test_graph_spec_validation():
    """Test graph specification validation."""
    print("Testing graph specification validation...")
    
    # Test double bubble map validation
    valid_spec = {
        "left": "Topic A",
        "right": "Topic B", 
        "similarities": ["Similarity 1", "Similarity 2"],
        "left_differences": ["Difference 1", "Difference 2"],
        "right_differences": ["Difference 1", "Difference 2"]
    }
    
    is_valid, message = graph_specs.validate_double_bubble_map(valid_spec)
    assert is_valid, f"Valid spec should pass validation: {message}"
    
    # Test invalid spec
    invalid_spec = {"left": "Topic A"}  # Missing required fields
    is_valid, message = graph_specs.validate_double_bubble_map(invalid_spec)
    assert not is_valid, "Invalid spec should fail validation"
    
    print("✅ Graph specification validation passed")

def test_sanitization():
    """Test input sanitization."""
    print("Testing input sanitization...")
    
    from api_routes import sanitize_prompt
    
    # Test normal input
    normal_input = "Compare cats and dogs"
    sanitized = sanitize_prompt(normal_input)
    assert sanitized == normal_input, f"Normal input should not be changed: {sanitized}"
    
    # Test XSS attempt
    xss_input = "<script>alert('xss')</script>Compare cats and dogs"
    sanitized = sanitize_prompt(xss_input)
    assert "<script>" not in sanitized, f"XSS should be removed: {sanitized}"
    
    # Test color validation
    assert config.D3_TOPIC_TEXT == '#ffffff', f"Default color should be 6-character hex: {config.D3_TOPIC_TEXT}"
    assert config.D3_SIM_TEXT == '#333333', f"Default color should be 6-character hex: {config.D3_SIM_TEXT}"
    
    # Test empty input
    empty_input = ""
    sanitized = sanitize_prompt(empty_input)
    assert sanitized is None, "Empty input should return None"
    
    print("✅ Input sanitization passed")

def main():
    """Run all tests."""
    print("🧪 Running D3.js_Dify improvement tests...\n")
    
    try:
        test_config_validation()
        test_graph_type_classification()
        test_graph_spec_validation()
        test_sanitization()
        
        print("\n🎉 All tests passed! The improvements are working correctly.")
        return 0
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main()) 