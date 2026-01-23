"""
LLM Clients Package

Provides LLM clients for various providers:
- DashScope: QwenClient, DeepSeekClient, KimiClient
- Volcengine: DoubaoClient, VolcengineClient
- Hunyuan: HunyuanClient

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Union
import logging
import os

from clients.llm.dashscope import QwenClient, DeepSeekClient, KimiClient
from clients.llm.volcengine import DoubaoClient, VolcengineClient
from clients.llm.hunyuan import HunyuanClient
from clients.llm.mock import MockLLMClient
from clients.llm.http_client_manager import close_httpx_clients

logger = logging.getLogger(__name__)


def _initialize_clients():
    """
    Initialize global client instances.

    Returns:
        Tuple of all client instances
    """
    qwen_client_cls = None
    qwen_client_gen = None
    qwen_client_main = None
    deepseek_cli = None
    kimi_cli = None
    hunyuan_cli = None
    doubao_cli = None

    try:
        qwen_client_cls = QwenClient(model_type='classification')  # qwen-plus-latest
        qwen_client_gen = QwenClient(model_type='generation')         # qwen-plus
        qwen_client_main = qwen_client_cls  # Legacy compatibility

        # Multi-LLM clients - Dedicated classes for each provider
        deepseek_cli = DeepSeekClient()
        kimi_cli = KimiClient()
        hunyuan_cli = HunyuanClient()
        # Note: doubao_client uses VolcengineClient with endpoint for higher RPM
        # Fallback to DoubaoClient only if endpoint not configured (for backward compatibility)
        try:
            doubao_cli = VolcengineClient('ark-doubao')
        except ValueError:
            # Endpoint not configured, fallback to legacy DoubaoClient
            logger.warning(
                "[clients.llm] ARK_DOUBAO_ENDPOINT not configured, using legacy DoubaoClient"
            )
            doubao_cli = DoubaoClient()

        # Only log from main worker to avoid duplicate messages
        if os.getenv('UVICORN_WORKER_ID') is None or os.getenv('UVICORN_WORKER_ID') == '0':
            logger.info("[LLMClients] LLM clients initialized successfully (Qwen, DeepSeek, Kimi, Hunyuan, Doubao)")
    except Exception as e:
        logger.warning('Failed to initialize LLM clients: %s', e)

    return (
        qwen_client_main,
        qwen_client_cls,
        qwen_client_gen,
        deepseek_cli,
        kimi_cli,
        hunyuan_cli,
        doubao_cli
    )


# Global client instances - assigned from function to avoid pylint constant warnings
(
    qwen_client,
    qwen_client_classification,
    qwen_client_generation,
    deepseek_client,
    kimi_client,
    hunyuan_client,
    doubao_client
) = _initialize_clients()


def get_llm_client(
    model_id: str = 'qwen'
) -> Union[
    QwenClient,
    DeepSeekClient,
    KimiClient,
    HunyuanClient,
    DoubaoClient,
    VolcengineClient,
    MockLLMClient
]:
    """
    Get an LLM client by model ID.

    Args:
        model_id: 'qwen', 'deepseek', 'kimi', 'hunyuan', or 'doubao'

    Returns:
        LLM client instance or MockLLMClient if client not available
    """
    client_map = {
        'qwen': qwen_client_generation,
        'deepseek': deepseek_client,
        'kimi': kimi_client,
        'hunyuan': hunyuan_client,
        'doubao': doubao_client
    }

    client = client_map.get(model_id)

    if client is not None:
        logger.debug('Using %s LLM client', model_id)
        return client
    else:
        logger.error(
            'LLM client not available for model "%s". This should not happen in production. '
            'Falling back to deprecated mock client. Please check LLM configuration.',
            model_id
        )
        # DEPRECATED: Mock client fallback - should not be used in production
        # Real LLM clients should always be configured
        return MockLLMClient()


__all__ = [
    'QwenClient',
    'DeepSeekClient',
    'KimiClient',
    'DoubaoClient',
    'VolcengineClient',
    'HunyuanClient',
    'MockLLMClient',
    'qwen_client',
    'qwen_client_classification',
    'qwen_client_generation',
    'deepseek_client',
    'kimi_client',
    'hunyuan_client',
    'doubao_client',
    'get_llm_client',
    'close_httpx_clients',
]
