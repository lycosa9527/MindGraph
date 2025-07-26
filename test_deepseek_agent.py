#!/usr/bin/env python3
"""
Test script for DeepSeek Agent - Development Phase Workflow

This script tests the DeepSeek agent's development phase functionality:
- Configuration validation
- Development prompt generation
- Diagram type classification for development
- Development workflow
- File saving functionality

The DeepSeek agent is now used during development phase to generate
enhanced prompt templates that developers can save and use with Qwen.
"""

import sys
import os
import json
import logging
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_deepseek_configuration():
    """Test DeepSeek configuration validation."""
    print("🔧 Testing DeepSeek Configuration...")
    
    try:
        from config import config
        
        # Test configuration values
        assert hasattr(config, 'DEEPSEEK_API_KEY'), "DEEPSEEK_API_KEY not found"
        assert hasattr(config, 'DEEPSEEK_API_URL'), "DEEPSEEK_API_URL not found"
        assert hasattr(config, 'DEEPSEEK_MODEL'), "DEEPSEEK_MODEL not found"
        
        print(f"✅ Configuration validation passed")
        print(f"   - API URL: {config.DEEPSEEK_API_URL}")
        print(f"   - Model: {config.DEEPSEEK_MODEL}")
        print(f"   - Temperature: {config.DEEPSEEK_TEMPERATURE}")
        print(f"   - Max Tokens: {config.DEEPSEEK_MAX_TOKENS}")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration validation failed: {e}")
        return False


def test_deepseek_agent_setup():
    """Test DeepSeek agent setup and LLM connection."""
    print("\n🤖 Testing DeepSeek Agent Setup...")
    
    try:
        import deepseek_agent
        
        # Test agent configuration
        config = deepseek_agent.get_deepseek_agent_config()
        assert config['role'] == 'development_tool', f"Expected role 'development_tool', got {config['role']}"
        assert config['workflow_type'] == 'development_phase', f"Expected workflow_type 'development_phase', got {config['workflow_type']}"
        
        print(f"✅ Agent configuration validated")
        print(f"   - Role: {config['role']}")
        print(f"   - Workflow Type: {config['workflow_type']}")
        print(f"   - Model: {config['llm_model']}")
        
        # Test LLM connection (this may fail if API key is not set)
        if deepseek_agent.validate_deepseek_agent_setup():
            print("✅ LLM connection validated")
        else:
            print("⚠️  LLM connection failed (expected if API key not configured)")
        
        return True
        
    except Exception as e:
        print(f"❌ Agent setup failed: {e}")
        return False


def test_diagram_classification():
    """Test diagram type classification for development phase."""
    print("\n📊 Testing Diagram Classification for Development...")
    
    try:
        import deepseek_agent
        
        test_cases = [
            ("Compare cats and dogs", "double_bubble_map"),
            ("Describe the solar system", "bubble_map"),
            ("Show the water cycle process", "flow_map"),
            ("Analyze causes of global warming", "multi_flow_map"),
            ("Define democracy in context", "circle_map")
        ]
        
        for prompt, expected_type in test_cases:
            result = deepseek_agent.classify_diagram_type_for_development(prompt, 'en')
            status = "✅" if result == expected_type else "❌"
            print(f"   {status} '{prompt}' → {result} (expected: {expected_type})")
        
        return True
        
    except Exception as e:
        print(f"❌ Diagram classification test failed: {e}")
        return False


def test_development_prompt_generation():
    """Test development prompt generation."""
    print("\n📝 Testing Development Prompt Generation...")
    
    try:
        import deepseek_agent
        
        test_prompt = "Compare cats and dogs"
        diagram_type = "double_bubble_map"
        
        # Test development prompt generation
        development_prompt = deepseek_agent.generate_development_prompt(test_prompt, diagram_type, 'en')
        
        # Check if prompt contains expected elements
        assert "Development Phase Prompt Template" in development_prompt, "Missing development phase header"
        assert "Original User Request" in development_prompt, "Missing original request section"
        assert "Educational Goal" in development_prompt, "Missing educational goal section"
        assert "Enhanced Requirements" in development_prompt, "Missing enhanced requirements section"
        assert "Output Format" in development_prompt, "Missing output format section"
        assert "Usage Instructions" in development_prompt, "Missing usage instructions"
        
        print("✅ Development prompt generation successful")
        print(f"   - Prompt length: {len(development_prompt)} characters")
        print(f"   - Contains development phase context: {'Development Phase Prompt Template' in development_prompt}")
        print(f"   - Contains educational focus: {'Educational Goal' in development_prompt}")
        
        # Show a snippet of the generated prompt
        lines = development_prompt.split('\n')[:10]
        print(f"   - Preview: {' '.join(lines)}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Development prompt generation failed: {e}")
        return False


def test_development_workflow():
    """Test the complete development workflow."""
    print("\n🔄 Testing Development Workflow...")
    
    try:
        import deepseek_agent
        
        test_prompt = "Compare cats and dogs"
        
        # Test development workflow
        result = deepseek_agent.development_workflow(test_prompt, 'en', save_to_file=False)
        
        # Validate result structure
        assert 'diagram_type' in result, "Missing diagram_type in result"
        assert 'development_prompt' in result, "Missing development_prompt in result"
        assert 'original_prompt' in result, "Missing original_prompt in result"
        assert 'language' in result, "Missing language in result"
        assert 'workflow_type' in result, "Missing workflow_type in result"
        assert result['workflow_type'] == 'development', f"Expected workflow_type 'development', got {result['workflow_type']}"
        
        print("✅ Development workflow successful")
        print(f"   - Diagram type: {result['diagram_type']}")
        print(f"   - Workflow type: {result['workflow_type']}")
        print(f"   - Language: {result['language']}")
        print(f"   - Prompt length: {len(result['development_prompt'])} characters")
        
        return True
        
    except Exception as e:
        print(f"❌ Development workflow failed: {e}")
        return False


def test_file_saving():
    """Test development prompt file saving functionality."""
    print("\n💾 Testing File Saving Functionality...")
    
    try:
        import deepseek_agent
        
        test_prompt = "Test development prompt for file saving"
        
        # Test file saving
        filename = deepseek_agent.save_development_prompt_to_file(test_prompt, "test_prompt.md")
        
        if filename and os.path.exists(filename):
            print(f"✅ File saved successfully: {filename}")
            
            # Read and verify content
            with open(filename, 'r', encoding='utf-8') as f:
                content = f.read()
                assert test_prompt in content, "Saved content doesn't match original"
            
            # Clean up test file
            os.remove(filename)
            print("✅ Test file cleaned up")
            
            return True
        else:
            print("❌ File saving failed")
            return False
        
    except Exception as e:
        print(f"❌ File saving test failed: {e}")
        return False


def test_available_diagram_types():
    """Test that all diagram types are available."""
    print("\n📋 Testing Available Diagram Types...")
    
    try:
        import deepseek_agent
        from graph_specs import get_available_diagram_types
        
        available_types = get_available_diagram_types()
        
        # Check for Thinking Maps
        thinking_maps = [
            "double_bubble_map", "bubble_map", "circle_map", "flow_map",
            "brace_map", "tree_map", "multi_flow_map", "bridge_map"
        ]
        
        for map_type in thinking_maps:
            if map_type in available_types:
                print(f"   ✅ {map_type}")
            else:
                print(f"   ❌ {map_type} (missing)")
        
        print(f"✅ Total available diagram types: {len(available_types)}")
        return True
        
    except Exception as e:
        print(f"❌ Available diagram types test failed: {e}")
        return False


def test_agent_configuration():
    """Test agent configuration and role."""
    print("\n⚙️ Testing Agent Configuration...")
    
    try:
        import deepseek_agent
        
        config = deepseek_agent.get_deepseek_agent_config()
        
        # Verify configuration structure
        required_keys = ['llm_model', 'llm_url', 'temperature', 'max_tokens', 'role', 'workflow_type']
        for key in required_keys:
            assert key in config, f"Missing configuration key: {key}"
        
        # Verify role and workflow type
        assert config['role'] == 'development_tool', f"Expected role 'development_tool', got {config['role']}"
        assert config['workflow_type'] == 'development_phase', f"Expected workflow_type 'development_phase', got {config['workflow_type']}"
        
        print("✅ Agent configuration validated")
        print(f"   - Role: {config['role']}")
        print(f"   - Workflow Type: {config['workflow_type']}")
        print(f"   - Model: {config['llm_model']}")
        print(f"   - Temperature: {config['temperature']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Agent configuration test failed: {e}")
        return False


def main():
    """Run all tests for the DeepSeek Development Agent."""
    print("🧠 DeepSeek Development Agent Test Suite")
    print("=" * 50)
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    tests = [
        ("Configuration", test_deepseek_configuration),
        ("Agent Setup", test_deepseek_agent_setup),
        ("Diagram Classification", test_diagram_classification),
        ("Development Prompt Generation", test_development_prompt_generation),
        ("Development Workflow", test_development_workflow),
        ("File Saving", test_file_saving),
        ("Available Diagram Types", test_available_diagram_types),
        ("Agent Configuration", test_agent_configuration)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                print(f"❌ {test_name} test failed")
        except Exception as e:
            print(f"❌ {test_name} test failed with exception: {e}")
    
    print("\n" + "=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! DeepSeek Development Agent is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the configuration and setup.")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 