"""
Prompt Manager
==============

Centralized prompt management with validation and organization.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import re
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class PromptTemplateError(Exception):
    """Raised when prompt template is invalid or missing."""


class PromptManager:
    """
    Centralized prompt management system.

    Organizes prompts by:
    - Diagram type (circle_map, bubble_map, etc.)
    - Function (assistant, generation, classification)
    - Language (zh, en)

    Features:
    - Template variable validation
    - Multi-language support
    - Fallback to default prompts
    - Lazy loading for performance
    """

    def __init__(self):
        self._prompts: Dict[str, Dict[str, Dict[str, Dict[str, str]]]] = {}
        self._initialized = False
        logger.info("[PromptManager] Initialized")

    def initialize(self):
        """Initialize prompt manager with default prompts."""
        if self._initialized:
            return

        logger.info("[PromptManager] Loading default prompts...")
        self._load_default_prompts()
        self._initialized = True
        logger.info("[PromptManager] Ready")

    def _load_default_prompts(self):
        """Load default prompt templates."""
        # Common system messages
        self.register_prompt(
            category='common',
            function='system',
            name='default',
            language='en',
            template="You are a helpful AI assistant. Provide clear and concise responses."
        )

        self.register_prompt(
            category='common',
            function='system',
            name='default',
            language='zh',
            template="你是一个有帮助的AI助手。请提供清晰简洁的回答。"
        )

        # AI Assistant prompts
        self.register_prompt(
            category='assistant',
            function='welcome',
            name='default',
            language='en',
            template=(
                "Hello! I'm here to help you optimize your {diagram_type} "
                "diagram about '{topic}'. How can I assist you?"
            )
        )

        self.register_prompt(
            category='assistant',
            function='welcome',
            name='default',
            language='zh',
            template='你好！我来帮你优化关于"{topic}"的{diagram_type}图。需要什么帮助吗？'
        )

        # Node generation prompts
        self.register_prompt(
            category='generation',
            function='nodes',
            name='circle_map',
            language='en',
            template=(
                "Generate {count} descriptive attributes or observations "
                "about: {center_topic}\n\nProvide diverse, specific "
                "characteristics."
            )
        )

        self.register_prompt(
            category='generation',
            function='nodes',
            name='circle_map',
            language='zh',
            template='为"{center_topic}"生成{count}个描述性特征或观察。\n\n请提供多样化、具体的特征。'
        )

        # Classification prompts
        self.register_prompt(
            category='classification',
            function='intent',
            name='default',
            language='en',
            template=(
                "Classify the user's intent from this message: "
                "'{user_message}'\n\nPossible intents: {intents}\n\n"
                "Respond with JSON: {{\"intent\": \"...\", "
                "\"parameters\": {{}}}}"
            )
        )

        self.register_prompt(
            category='classification',
            function='intent',
            name='default',
            language='zh',
            template=(
                "分类用户意图: '{user_message}'\n\n可能的意图: {intents}\n\n"
                "用JSON格式回答: {{\"intent\": \"...\", "
                "\"parameters\": {{}}}}"
            )
        )

    def register_prompt(
        self,
        category: str,
        function: str,
        name: str,
        language: str,
        template: str
    ):
        """
        Register a prompt template.

        Args:
            category: Prompt category (e.g., 'assistant', 'generation')
            function: Function name (e.g., 'welcome', 'nodes')
            name: Specific prompt name (e.g., 'circle_map', 'default')
            language: Language code ('en', 'zh')
            template: Prompt template with {placeholders}
        """
        if category not in self._prompts:
            self._prompts[category] = {}

        if function not in self._prompts[category]:
            self._prompts[category][function] = {}

        if name not in self._prompts[category][function]:
            self._prompts[category][function][name] = {}

        self._prompts[category][function][name][language] = template

        logger.debug(
            "[PromptManager] Registered: %s/%s/%s/%s",
            category, function, name, language
        )

    def get_prompt(
        self,
        category: str,
        function: str,
        name: str = 'default',
        language: str = 'en',
        **kwargs
    ) -> str:
        """
        Get a formatted prompt template.

        Args:
            category: Prompt category
            function: Function name
            name: Specific prompt name
            language: Language code
            **kwargs: Variables to fill in template

        Returns:
            Formatted prompt string

        Raises:
            PromptTemplateError: If prompt not found or variables missing

        Example:
            prompt = prompt_manager.get_prompt(
                category='assistant',
                function='welcome',
                name='default',
                language='zh',
                diagram_type='圆圈图',
                topic='汽车'
            )
        """
        if not self._initialized:
            self.initialize()

        # Try to get specific prompt
        template = self._find_template(category, function, name, language)

        if template is None:
            raise PromptTemplateError(
                f"Prompt not found: {category}/{function}/{name}/{language}"
            )

        # Validate required variables
        required_vars = self._extract_variables(template)
        missing_vars = required_vars - set(kwargs.keys())

        if missing_vars:
            raise PromptTemplateError(
                f"Missing required variables: {missing_vars}. "
                f"Template: {template[:100]}..."
            )

        # Format template
        try:
            return template.format(**kwargs)
        except KeyError as e:
            raise PromptTemplateError(
                f"Error formatting template: {e}"
            ) from e

    def _find_template(
        self,
        category: str,
        function: str,
        name: str,
        language: str
    ) -> Optional[str]:
        """
        Find template with fallback logic.

        Fallback order:
        1. Exact match: category/function/name/language
        2. Default name: category/function/default/language
        3. English fallback: category/function/name/en
        4. Default English: category/function/default/en
        """
        # Try exact match
        if (category in self._prompts and
            function in self._prompts[category] and
            name in self._prompts[category][function] and
            language in self._prompts[category][function][name]):
            return self._prompts[category][function][name][language]

        # Try default name
        if (category in self._prompts and
            function in self._prompts[category] and
            'default' in self._prompts[category][function] and
            language in self._prompts[category][function]['default']):
            logger.debug(
                "[PromptManager] Using default name for %s", name
            )
            return self._prompts[category][function]['default'][language]

        # Try English fallback
        if (category in self._prompts and
            function in self._prompts[category] and
            name in self._prompts[category][function] and
            'en' in self._prompts[category][function][name]):
            logger.debug(
                "[PromptManager] Using English fallback for %s", language
            )
            return self._prompts[category][function][name]['en']

        # Try default English
        if (category in self._prompts and
            function in self._prompts[category] and
            'default' in self._prompts[category][function] and
            'en' in self._prompts[category][function]['default']):
            logger.debug("[PromptManager] Using default English")
            return self._prompts[category][function]['default']['en']

        return None

    def _extract_variables(self, template: str) -> Set[str]:
        """
        Extract variable names from template.

        Args:
            template: Template string with {variables}

        Returns:
            Set of variable names
        """
        pattern = r'\{(\w+)\}'
        matches = re.findall(pattern, template)
        return set(matches)

    def get_available_prompts(self) -> Dict[str, List[str]]:
        """
        Get list of available prompts by category.

        Returns:
            Dict mapping categories to function lists
        """
        if not self._initialized:
            self.initialize()

        result = {}
        for category, functions in self._prompts.items():
            result[category] = list(functions.keys())

        return result

    def validate_template(
        self,
        template: str,
        required_vars: Optional[List[str]] = None
    ) -> bool:
        """
        Validate a prompt template.

        Args:
            template: Template string
            required_vars: Optional list of required variables

        Returns:
            True if valid

        Raises:
            PromptTemplateError: If template is invalid
        """
        # Extract variables from template
        template_vars = self._extract_variables(template)

        # Check if required vars are present
        if required_vars:
            missing = set(required_vars) - template_vars
            if missing:
                raise PromptTemplateError(
                    f"Template missing required variables: {missing}"
                )

        # Try to format with dummy values
        try:
            dummy_values = {var: 'test' for var in template_vars}
            template.format(**dummy_values)
        except Exception as e:
            raise PromptTemplateError(
                f"Template formatting error: {e}"
            ) from e

        return True

    def list_categories(self) -> List[str]:
        """Get list of all prompt categories."""
        if not self._initialized:
            self.initialize()
        return list(self._prompts.keys())

    def list_functions(self, category: str) -> List[str]:
        """Get list of functions in a category."""
        if not self._initialized:
            self.initialize()

        if category not in self._prompts:
            return []

        return list(self._prompts[category].keys())

    def list_names(self, category: str, function: str) -> List[str]:
        """Get list of prompt names for a category/function."""
        if not self._initialized:
            self.initialize()

        if (category not in self._prompts or
            function not in self._prompts[category]):
            return []

        return list(self._prompts[category][function].keys())


# Singleton instance
prompt_manager = PromptManager()
