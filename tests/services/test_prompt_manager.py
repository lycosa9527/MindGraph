"""
Unit Tests for Prompt Manager
==============================

@author lycosa9527
@made_by MindSpring Team
"""

import pytest
from services.prompt_manager import (
    prompt_manager,
    PromptManager,
    PromptTemplateError
)


class TestPromptManager:
    """Test suite for PromptManager."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for each test."""
        # Initialize prompt manager
        if not prompt_manager._initialized:
            prompt_manager.initialize()
    
    def test_initialization(self):
        """Test prompt manager initialization."""
        pm = PromptManager()
        pm.initialize()
        
        assert pm._initialized
        assert len(pm._prompts) > 0
        print(f"Initialized with {len(pm._prompts)} categories")
    
    def test_get_prompt_basic(self):
        """Test getting a basic prompt."""
        prompt = prompt_manager.get_prompt(
            category='common',
            function='system',
            name='default',
            language='en'
        )
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        print(f"Got prompt: {prompt[:50]}...")
    
    def test_get_prompt_with_variables(self):
        """Test getting prompt with variable substitution."""
        prompt = prompt_manager.get_prompt(
            category='thinkguide',
            function='welcome',
            name='default',
            language='en',
            diagram_type='Circle Map',
            topic='Cars'
        )
        
        assert 'Circle Map' in prompt
        assert 'Cars' in prompt
        print(f"Formatted prompt: {prompt}")
    
    def test_get_prompt_chinese(self):
        """Test getting Chinese prompt."""
        prompt = prompt_manager.get_prompt(
            category='thinkguide',
            function='welcome',
            name='default',
            language='zh',
            diagram_type='圆圈图',
            topic='汽车'
        )
        
        assert '圆圈图' in prompt
        assert '汽车' in prompt
        print(f"Chinese prompt: {prompt}")
    
    def test_missing_variables_raises_error(self):
        """Test that missing variables raise error."""
        with pytest.raises(PromptTemplateError) as excinfo:
            prompt_manager.get_prompt(
                category='thinkguide',
                function='welcome',
                language='en'
                # Missing: diagram_type, topic
            )
        
        assert 'Missing required variables' in str(excinfo.value)
        print(f"Error message: {excinfo.value}")
    
    def test_nonexistent_prompt_raises_error(self):
        """Test that nonexistent prompt raises error."""
        with pytest.raises(PromptTemplateError) as excinfo:
            prompt_manager.get_prompt(
                category='nonexistent',
                function='test',
                language='en'
            )
        
        assert 'Prompt not found' in str(excinfo.value)
    
    def test_register_custom_prompt(self):
        """Test registering custom prompt."""
        pm = PromptManager()
        pm.initialize()
        
        pm.register_prompt(
            category='custom',
            function='test',
            name='example',
            language='en',
            template='Hello {user_name}, welcome to {place}!'
        )
        
        prompt = pm.get_prompt(
            category='custom',
            function='test',
            name='example',
            language='en',
            user_name='Alice',
            place='Wonderland'
        )
        
        assert 'Alice' in prompt
        assert 'Wonderland' in prompt
        print(f"Custom prompt: {prompt}")
    
    def test_fallback_to_default_name(self):
        """Test fallback to default prompt name."""
        # Should fall back to 'default' if specific name not found
        prompt = prompt_manager.get_prompt(
            category='common',
            function='system',
            name='nonexistent',  # Falls back to 'default'
            language='en'
        )
        
        assert isinstance(prompt, str)
        assert len(prompt) > 0
        print("Fallback to default name worked")
    
    def test_fallback_to_english(self):
        """Test fallback to English when language not available."""
        # Register only English version
        pm = PromptManager()
        pm.initialize()
        
        pm.register_prompt(
            category='test',
            function='example',
            name='only_english',
            language='en',
            template='English only'
        )
        
        # Request in unsupported language, should fall back to English
        prompt = pm.get_prompt(
            category='test',
            function='example',
            name='only_english',
            language='fr'  # French not available, falls back to EN
        )
        
        assert prompt == 'English only'
        print("Fallback to English worked")
    
    def test_extract_variables(self):
        """Test variable extraction from template."""
        template = "Hello {name}, you are {age} years old in {city}!"
        
        variables = prompt_manager._extract_variables(template)
        
        assert variables == {'name', 'age', 'city'}
        print(f"Extracted variables: {variables}")
    
    def test_validate_template(self):
        """Test template validation."""
        # Valid template
        assert prompt_manager.validate_template(
            "Hello {name}!",
            required_vars=['name']
        )
        
        # Invalid - missing required var
        with pytest.raises(PromptTemplateError):
            prompt_manager.validate_template(
                "Hello {name}!",
                required_vars=['name', 'age']
            )
        
        print("Template validation works")
    
    def test_list_categories(self):
        """Test listing categories."""
        categories = prompt_manager.list_categories()
        
        assert isinstance(categories, list)
        assert 'common' in categories
        assert 'thinkguide' in categories
        print(f"Categories: {categories}")
    
    def test_list_functions(self):
        """Test listing functions in a category."""
        functions = prompt_manager.list_functions('common')
        
        assert isinstance(functions, list)
        assert 'system' in functions
        print(f"Functions in 'common': {functions}")
    
    def test_list_names(self):
        """Test listing prompt names."""
        names = prompt_manager.list_names('common', 'system')
        
        assert isinstance(names, list)
        assert 'default' in names
        print(f"Names in 'common/system': {names}")
    
    def test_get_available_prompts(self):
        """Test getting available prompts overview."""
        prompts = prompt_manager.get_available_prompts()
        
        assert isinstance(prompts, dict)
        assert 'common' in prompts
        assert 'thinkguide' in prompts
        print(f"Available prompts: {prompts}")
    
    def test_node_generation_prompt(self):
        """Test node generation prompt."""
        prompt = prompt_manager.get_prompt(
            category='generation',
            function='nodes',
            name='circle_map',
            language='en',
            count=10,
            center_topic='Cars'
        )
        
        assert '10' in prompt or 'ten' in prompt.lower()
        assert 'Cars' in prompt
        print(f"Node generation prompt: {prompt}")
    
    def test_classification_prompt(self):
        """Test classification prompt."""
        prompt = prompt_manager.get_prompt(
            category='classification',
            function='intent',
            language='en',
            user_message='Change the center to cars',
            intents='change_center, add_node, delete_node'
        )
        
        assert 'Change the center to cars' in prompt
        assert 'change_center' in prompt
        print(f"Classification prompt: {prompt[:100]}...")

