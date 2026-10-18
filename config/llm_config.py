"""LLM configuration settings.

This module provides LLM-related configuration properties including
Qwen, Dashscope, DeepSeek, Kimi, and ARK configurations.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from typing import TYPE_CHECKING, Any, Optional

from config.dashscope_urls import build_dashscope_headers
from services.infrastructure.utils.llm_routing_store import peek_override

logger = logging.getLogger(__name__)


class LLMConfigMixin:
    """Mixin class for LLM configuration properties.

    This mixin expects the class to inherit from BaseConfig or provide
    a _get_cached_value method.
    """

    if TYPE_CHECKING:

        def _get_cached_value(self, _key: str, _default: Any = None) -> Any:
            """Type stub: method provided by BaseConfig."""
            return _default

        @property
        def QWEN_API_URL(self) -> str:
            """Type stub: provided by DashScopeEndpointConfigMixin."""
            return ""

        @property
        def DASHSCOPE_WORKSPACE_ID(self) -> Optional[str]:
            """Type stub: provided by DashScopeEndpointConfigMixin."""
            return None

    @property
    def QWEN_API_KEY(self):
        """Get Qwen API key from environment."""
        api_key = self._get_cached_value("QWEN_API_KEY")
        if not api_key or not isinstance(api_key, str):
            logger.warning("Invalid or missing QWEN_API_KEY")
            return None
        return api_key.strip()

    @property
    def QWEN_MODEL(self):
        """Legacy property - now defaults to classification model for backward compatibility"""
        return self.QWEN_MODEL_CLASSIFICATION

    @property
    def QWEN_MODEL_CLASSIFICATION(self):
        """Model for classification tasks. A superadmin override replaces env."""
        return self._with_routing_override("QWEN_MODEL_CLASSIFICATION", "qwen3.6-flash")

    def _with_routing_override(self, key: str, default: str) -> str:
        """Prefer a superadmin Redis override, then the env cache."""
        overridden = peek_override(key)
        if overridden:
            return overridden
        return self._get_cached_value(key, default)

    @property
    def QWEN_MODEL_GENERATION(self):
        """Model for generation tasks (higher quality)."""
        return self._with_routing_override("QWEN_MODEL_GENERATION", "qwen3.6-flash")

    @property
    def QWEN_FLASH_MODEL(self):
        """DashScope model id for the canvas Balanced choice (Qwen Flash)."""
        return self._with_routing_override("QWEN_FLASH_MODEL", "qwen3.8-flash")

    @property
    def QWEN_MAX_MODEL(self):
        """DashScope model id for the canvas Max choice (Qwen Max)."""
        return self._with_routing_override("QWEN_MAX_MODEL", "qwen3.8-max")

    @property
    def QWEN_MODEL_NODE_EXPLAIN(self):
        """Physical id for the Qwen 3.8 rate window.

        Node explain uses Express. This id still matches the pinned qwen3.8-flash
        client and any leftover override so that traffic stays on the qwen38 cap.
        """
        return self._with_routing_override("QWEN_MODEL_NODE_EXPLAIN", "qwen3.8-flash")

    @property
    def DEEPSEEK_MODEL(self):
        """DashScope model for the logical ``deepseek`` route.

        Pairs with the Volcengine ``DS_v4.1flash`` endpoint in the load balancer.
        ``enable_thinking`` still selects thinking mode on this DashScope id.
        A superadmin override replaces the env value until it is cleared.
        """
        return self._with_routing_override("DEEPSEEK_MODEL", "deepseek-v4.1-flash")

    @property
    def EXPRESS_MODEL(self):
        """DashScope model for canvas Express mode.

        Always DashScope. Not load-balanced to Volcengine.
        A superadmin override replaces the env value until it is cleared.
        """
        return self._with_routing_override("EXPRESS_MODEL", "deepseek-v4.1-flash")

    @property
    def KIMI_MODEL(self):
        """Kimi model name (Moonshot AI)"""
        return self._get_cached_value("KIMI_MODEL", "Moonshot-Kimi-K2-Instruct")

    @property
    def ARK_API_KEY(self):
        """Volcengine ARK API Key"""
        return self._get_cached_value("ARK_API_KEY", "")

    @property
    def ARK_BASE_URL(self):
        """Volcengine ARK API Base URL"""
        return self._get_cached_value("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")

    @property
    def ARK_QWEN_ENDPOINT(self):
        """Volcengine ARK Qwen endpoint ID (higher RPM than direct model name)"""
        return self._get_cached_value("ARK_QWEN_ENDPOINT", "ep-20250101000000-dummy")

    @property
    def ARK_DEEPSEEK_ENDPOINT(self):
        """Volcengine ARK DeepSeek endpoint ID (higher RPM than direct model name)."""
        return self._with_routing_override("ARK_DEEPSEEK_ENDPOINT", "ep-20250101000000-dummy")

    @property
    def GLM_FLASH_MODEL(self):
        """Volcengine model id for the canvas GLM Flash choice.

        Read from ``GLM_FLASH_MODEL``. Sent as the chat ``model`` field.
        An ``ep-`` value is an endpoint id.
        """
        raw = self._with_routing_override("GLM_FLASH_MODEL", "")
        if not isinstance(raw, str):
            return ""
        return raw.strip()

    @property
    def ARK_DOUBAO_ENDPOINT(self):
        """Volcengine ARK Doubao endpoint ID (higher RPM than direct model name)."""
        return self._with_routing_override("ARK_DOUBAO_ENDPOINT", "ep-20250101000000-dummy")

    @property
    def DOUBAO_MODEL(self):
        """Volcengine model id for the canvas Doubao choice.

        Read from ``DOUBAO_MODEL``. Sent as the chat ``model`` field.
        An ``ep-`` value is an endpoint id.
        This does not replace ``ARK_DOUBAO_ENDPOINT`` (doubao_1.5pro_32k).
        """
        raw = self._with_routing_override("DOUBAO_MODEL", "")
        if not isinstance(raw, str):
            return ""
        return raw.strip()

    def canvas_menu_model_ids(self) -> dict[str, str]:
        """Physical model ids for the canvas LLM menu.

        Keys are menu aliases. Values follow env and superadmin overrides.
        An empty string means that choice has no model id configured.
        """
        return {
            "express": self.EXPRESS_MODEL,
            "qwen3.8-flash": self.QWEN_FLASH_MODEL,
            "qwen3-max": self.QWEN_MAX_MODEL,
            "kimi": self.GLM_FLASH_MODEL,
            "doubao21": self.DOUBAO_MODEL,
        }

    @property
    def QWEN_TEMPERATURE(self):
        """Get Qwen temperature setting."""
        try:
            temp = float(self._get_cached_value("QWEN_TEMPERATURE", "0.7"))
            if not 0.0 <= temp <= 1.0:
                logger.warning("Temperature %s out of range [0.0, 1.0], using 0.7", temp)
                return 0.7
            return temp
        except (ValueError, TypeError):
            logger.warning("Invalid temperature value, using 0.7")
            return 0.7

    @property
    def LLM_TEMPERATURE(self):
        """Unified temperature for all diagram generation agents (structured output)."""
        try:
            temp = float(self._get_cached_value("LLM_TEMPERATURE", "0.5"))
            if not 0.0 <= temp <= 2.0:
                logger.warning("Temperature %s out of range [0.0, 2.0], using 0.5", temp)
                return 0.5
            return temp
        except (ValueError, TypeError):
            logger.warning("Invalid LLM_TEMPERATURE value, using 0.5")
            return 0.5

    @property
    def QWEN_MAX_TOKENS(self):
        """Unified max tokens setting for all LLM calls."""
        return 3000

    @property
    def QWEN_TIMEOUT(self):
        """Get Qwen timeout setting."""
        try:
            val = int(self._get_cached_value("QWEN_TIMEOUT", "40"))
            if val < 5 or val > 120:
                logger.warning("QWEN_TIMEOUT %s out of range, using 40", val)
                return 40
            return val
        except (ValueError, TypeError):
            logger.warning("Invalid QWEN_TIMEOUT value, using 40")
            return 40

    @property
    def DASHSCOPE_API_KEY(self) -> Optional[str]:
        """
        DashScope API key (optional).

        Aliyun realtime ASR docs recommend ``DASHSCOPE_API_KEY``; Singapore and
        Beijing keys differ by region. When unset, ASR falls back to ``QWEN_API_KEY``.
        """
        raw = self._get_cached_value("DASHSCOPE_API_KEY", "")
        if not raw or not isinstance(raw, str):
            return None
        stripped = raw.strip()
        return stripped or None

    @property
    def QWEN_ASR_REALTIME_MODEL(self) -> str:
        """
        Qwen3 ASR Flash Realtime model id for WebSocket ``?model=``.

        Stable default per product doc: ``qwen3-asr-flash-realtime`` (snapshots
        e.g. ``qwen3-asr-flash-realtime-2026-02-10`` remain valid).
        """
        return self._get_cached_value(
            "QWEN_ASR_REALTIME_MODEL",
            "qwen3-asr-flash-realtime",
        )

    @property
    def QWEN_LIVE_TRANSLATE_MODEL(self) -> str:
        """
        Qwen LiveTranslate Flash Realtime model id for WebSocket ``?model=``.

        Stable default: ``qwen3.8-livetranslate-flash-realtime`` (60 text targets).
        Override with ``QWEN_LIVE_TRANSLATE_MODEL`` env var.
        """
        return self._get_cached_value(
            "QWEN_LIVE_TRANSLATE_MODEL",
            "qwen3.8-livetranslate-flash-realtime",
        )

    def get_qwen_headers(self) -> dict:
        """
        Get headers for Qwen / DashScope model API requests.

        Includes ``X-DashScope-WorkSpace`` when ``DASHSCOPE_WORKSPACE_ID`` is set.
        """
        api_key = self.QWEN_API_KEY
        if api_key is None:
            raise ValueError("QWEN_API_KEY is not set")
        return build_dashscope_headers(
            api_key,
            workspace_id=self.DASHSCOPE_WORKSPACE_ID,
        )

    def get_qwen_data(self, prompt: str, model: Optional[str] = None) -> dict:
        """
        Get request data for Qwen API calls.

        Args:
            prompt (str): The prompt to send to Qwen
            model (str): Model to use (None for default classification model)

        Returns:
            dict: Request data dictionary for Qwen API

        Note:
            Qwen3 models require enable_thinking: False when not using streaming
            to avoid API errors. This is automatically included in the payload.
        """
        if model is None:
            model = self.QWEN_MODEL_CLASSIFICATION

        return {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.QWEN_TEMPERATURE,
            "max_tokens": self.QWEN_MAX_TOKENS,
            "extra_body": {"enable_thinking": False},
        }

    def get_qwen_classification_data(self, prompt: str) -> dict:
        """Get request data for Qwen classification tasks"""
        return self.get_qwen_data(prompt, self.QWEN_MODEL_CLASSIFICATION)

    def get_qwen_generation_data(self, prompt: str) -> dict:
        """Get request data for Qwen generation tasks (high quality)"""
        return self.get_qwen_data(prompt, self.QWEN_MODEL_GENERATION)

    def get_llm_data(self, prompt: str, model: str) -> dict:
        """
        Get request data for any LLM model via Dashscope.

        Args:
            prompt (str): The prompt to send
            model (str): Model identifier ('qwen', 'deepseek', 'kimi')

        Returns:
            dict: Request data dictionary for Dashscope API

        Note:
            Always includes enable_thinking: False for lightweight application
        """
        model_map = {
            "qwen": self.QWEN_MODEL_GENERATION,
            "deepseek": self.DEEPSEEK_MODEL,
            "express": self.EXPRESS_MODEL,
            "kimi": self.KIMI_MODEL,
        }

        model_name = model_map.get(model, self.QWEN_MODEL_GENERATION)

        return {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.QWEN_TEMPERATURE,
            "max_tokens": self.QWEN_MAX_TOKENS,
            "extra_body": {"enable_thinking": False},
        }

    def prepare_llm_messages(self, system_prompt: str, user_prompt: str, _model: str = "qwen") -> list:
        """
        Centralized message preparation for all LLM clients.

        Args:
            system_prompt: The system/instruction prompt
            user_prompt: The user's input prompt
            _model: Model identifier ('qwen', 'deepseek', 'kimi') - reserved for future use

        Returns:
            list: Formatted messages array ready for chat_completion()
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        return messages

    def validate_qwen_config(self) -> bool:
        """
        Validate Qwen API configuration.

        Returns:
            bool: True if Qwen configuration is valid, False otherwise
        """
        if not self.QWEN_API_KEY:
            return False

        if not self.QWEN_API_URL.startswith(("http://", "https://")):
            return False

        try:
            if not 0 <= self.QWEN_TEMPERATURE <= 1:
                return False
            if self.QWEN_MAX_TOKENS <= 0:
                return False
            if self.QWEN_TIMEOUT <= 0:
                return False
        except (ValueError, TypeError):
            return False

        return True
