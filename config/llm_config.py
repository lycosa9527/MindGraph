"""LLM configuration settings.

This module provides LLM-related configuration properties including
Qwen, Dashscope, DeepSeek, Kimi, Hunyuan, and ARK configurations.
"""
import logging
from typing import Optional, TYPE_CHECKING, Any

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
    def QWEN_API_KEY(self):
        """Get Qwen API key from environment."""
        api_key = self._get_cached_value('QWEN_API_KEY')
        if not api_key or not isinstance(api_key, str):
            logger.warning("Invalid or missing QWEN_API_KEY")
            return None
        return api_key.strip()

    @property
    def QWEN_API_URL(self):
        """Get Qwen API URL."""
        default_url = 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'
        return self._get_cached_value('QWEN_API_URL', default_url)

    @property
    def QWEN_MODEL(self):
        """Legacy property - now defaults to classification model for backward compatibility"""
        return self.QWEN_MODEL_CLASSIFICATION

    @property
    def QWEN_MODEL_CLASSIFICATION(self):
        """Model for classification tasks"""
        return self._get_cached_value('QWEN_MODEL_CLASSIFICATION', 'qwen-plus-latest')

    @property
    def QWEN_MODEL_GENERATION(self):
        """Model for generation tasks (higher quality)"""
        return self._get_cached_value('QWEN_MODEL_GENERATION', 'qwen-plus-latest')

    @property
    def DASHSCOPE_API_URL(self):
        """Dashscope API URL for all supported models"""
        return self._get_cached_value('DASHSCOPE_API_URL', 'https://dashscope.aliyuncs.com/api/v1/')

    @property
    def DEEPSEEK_MODEL(self):
        """DeepSeek model name - v3.1 is faster than R1 (no reasoning overhead)"""
        return self._get_cached_value('DEEPSEEK_MODEL', 'deepseek-v3.1')

    @property
    def KIMI_MODEL(self):
        """Kimi model name (Moonshot AI)"""
        return self._get_cached_value('KIMI_MODEL', 'Moonshot-Kimi-K2-Instruct')

    @property
    def HUNYUAN_API_KEY(self):
        """Tencent Hunyuan API Secret Key"""
        return self._get_cached_value('HUNYUAN_API_KEY', '')

    @property
    def HUNYUAN_SECRET_ID(self):
        """Tencent Hunyuan API Secret ID"""
        return self._get_cached_value('HUNYUAN_SECRET_ID', '')

    @property
    def HUNYUAN_API_URL(self):
        """Tencent Hunyuan API URL"""
        return self._get_cached_value('HUNYUAN_API_URL', 'https://hunyuan.tencentcloudapi.com')

    @property
    def HUNYUAN_MODEL(self):
        """Hunyuan model name"""
        return self._get_cached_value('HUNYUAN_MODEL', 'hunyuan-turbo')

    @property
    def ARK_API_KEY(self):
        """Volcengine ARK API Key"""
        return self._get_cached_value('ARK_API_KEY', '')

    @property
    def ARK_BASE_URL(self):
        """Volcengine ARK API Base URL"""
        return self._get_cached_value('ARK_BASE_URL', 'https://ark.cn-beijing.volces.com/api/v3')

    @property
    def ARK_QWEN_ENDPOINT(self):
        """Volcengine ARK Qwen endpoint ID (higher RPM than direct model name)"""
        return self._get_cached_value('ARK_QWEN_ENDPOINT', 'ep-20250101000000-dummy')

    @property
    def ARK_DEEPSEEK_ENDPOINT(self):
        """Volcengine ARK DeepSeek endpoint ID (higher RPM than direct model name)"""
        return self._get_cached_value('ARK_DEEPSEEK_ENDPOINT', 'ep-20250101000000-dummy')

    @property
    def ARK_KIMI_ENDPOINT(self):
        """Volcengine ARK Kimi endpoint ID (higher RPM than direct model name)"""
        return self._get_cached_value('ARK_KIMI_ENDPOINT', 'ep-20250101000000-dummy')

    @property
    def ARK_DOUBAO_ENDPOINT(self):
        """Volcengine ARK Doubao endpoint ID (higher RPM than direct model name)"""
        return self._get_cached_value('ARK_DOUBAO_ENDPOINT', 'ep-20250101000000-dummy')

    @property
    def DOUBAO_MODEL(self):
        """Doubao model name"""
        return self._get_cached_value('DOUBAO_MODEL', 'doubao-1-5-pro-32k-250115')

    @property
    def QWEN_TEMPERATURE(self):
        """Get Qwen temperature setting."""
        try:
            temp = float(self._get_cached_value('QWEN_TEMPERATURE', '0.7'))
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
            temp = float(self._get_cached_value('LLM_TEMPERATURE', '0.5'))
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
            val = int(self._get_cached_value('QWEN_TIMEOUT', '40'))
            if val < 5 or val > 120:
                logger.warning("QWEN_TIMEOUT %s out of range, using 40", val)
                return 40
            return val
        except (ValueError, TypeError):
            logger.warning("Invalid QWEN_TIMEOUT value, using 40")
            return 40

    @property
    def QWEN_OMNI_MODEL(self) -> str:
        """Qwen Omni model name"""
        return self._get_cached_value('QWEN_OMNI_MODEL', 'qwen3-omni-flash-realtime-2025-12-01')

    @property
    def QWEN_OMNI_VOICE(self) -> str:
        """Qwen Omni voice name"""
        return self._get_cached_value('QWEN_OMNI_VOICE', 'Cherry')

    @property
    def QWEN_OMNI_VAD_THRESHOLD(self) -> float:
        """Qwen Omni VAD threshold"""
        return float(self._get_cached_value('QWEN_OMNI_VAD_THRESHOLD', '0.5'))

    @property
    def QWEN_OMNI_VAD_SILENCE_MS(self) -> int:
        """Qwen Omni VAD silence duration (ms) - time to wait after user stops speaking"""
        return int(self._get_cached_value('QWEN_OMNI_VAD_SILENCE_MS', '1200'))

    @property
    def QWEN_OMNI_VAD_PREFIX_MS(self) -> int:
        """Qwen Omni VAD prefix padding (ms)"""
        return int(self._get_cached_value('QWEN_OMNI_VAD_PREFIX_MS', '300'))

    @property
    def QWEN_OMNI_SMOOTH_OUTPUT(self) -> bool:
        """Qwen Omni smooth output (flash models only)"""
        return self._get_cached_value('QWEN_OMNI_SMOOTH_OUTPUT', 'true').lower() == 'true'

    @property
    def QWEN_OMNI_INPUT_FORMAT(self) -> str:
        """Qwen Omni input audio format"""
        return self._get_cached_value('QWEN_OMNI_INPUT_FORMAT', 'pcm16')

    @property
    def QWEN_OMNI_OUTPUT_FORMAT(self) -> str:
        """Qwen Omni output audio format"""
        return self._get_cached_value('QWEN_OMNI_OUTPUT_FORMAT', 'pcm24')

    @property
    def QWEN_OMNI_TRANSCRIPTION_MODEL(self) -> str:
        """Qwen Omni transcription model"""
        return self._get_cached_value('QWEN_OMNI_TRANSCRIPTION_MODEL', 'gummy-realtime-v1')

    def get_qwen_headers(self) -> dict:
        """
        Get headers for Qwen API requests.

        Returns:
            dict: Headers dictionary for Qwen API requests
        """
        api_key = self.QWEN_API_KEY
        if api_key is None:
            raise ValueError("QWEN_API_KEY is not set")
        return {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }

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
            'model': model,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': self.QWEN_TEMPERATURE,
            'max_tokens': self.QWEN_MAX_TOKENS,
            'extra_body': {'enable_thinking': False}
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
            model (str): Model identifier ('qwen', 'deepseek', 'kimi', 'chatglm')

        Returns:
            dict: Request data dictionary for Dashscope API

        Note:
            Always includes enable_thinking: False for lightweight application
        """
        model_map = {
            'qwen': self.QWEN_MODEL_GENERATION,
            'deepseek': self.DEEPSEEK_MODEL,
            'kimi': self.KIMI_MODEL,
            'hunyuan': self.HUNYUAN_MODEL
        }

        model_name = model_map.get(model, self.QWEN_MODEL_GENERATION)

        return {
            'model': model_name,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': self.QWEN_TEMPERATURE,
            'max_tokens': self.QWEN_MAX_TOKENS,
            'extra_body': {'enable_thinking': False}
        }

    def prepare_llm_messages(self, system_prompt: str, user_prompt: str,
                            _model: str = 'qwen') -> list:
        """
        Centralized message preparation for all LLM clients.

        Args:
            system_prompt: The system/instruction prompt
            user_prompt: The user's input prompt
            _model: Model identifier ('qwen', 'deepseek', 'kimi', 'hunyuan') - reserved for future use

        Returns:
            list: Formatted messages array ready for chat_completion()
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
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

        if not self.QWEN_API_URL.startswith(('http://', 'https://')):
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
