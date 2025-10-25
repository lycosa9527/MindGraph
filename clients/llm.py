"""
LLM Clients for Hybrid Agent Processing

This module provides async interfaces for Qwen LLM clients
used by diagram agents for layout optimization and style enhancement.
"""

import asyncio
import aiohttp
import json
import logging
import os
from typing import Dict, List, Optional, Any, AsyncGenerator
from dotenv import load_dotenv
from openai import AsyncOpenAI
from config.settings import config

# Load environment variables for logging configuration
load_dotenv()

logger = logging.getLogger(__name__)


class QwenClient:
    """Async client for Qwen LLM API"""
    
    def __init__(self, model_type='classification'):
        """
        Initialize QwenClient with specific model type
        
        Args:
            model_type (str): 'classification' for qwen-turbo, 'generation' for qwen-plus
        """
        self.api_url = config.QWEN_API_URL
        self.api_key = config.QWEN_API_KEY
        self.timeout = 30  # seconds
        self.model_type = model_type
        # DIVERSITY FIX: Use higher temperature for generation to increase variety
        self.default_temperature = 0.9 if model_type == 'generation' else 0.7
        
    async def chat_completion(self, messages: List[Dict], temperature: float = None,
                            max_tokens: int = 1000) -> str:
        """
        Send chat completion request to Qwen (async version)
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 1.0), None uses default
            max_tokens: Maximum tokens in response
            
        Returns:
            Response content as string
        """
        try:
            # Use instance default if not specified
            if temperature is None:
                temperature = self.default_temperature
            
            # Select appropriate model based on task type
            if self.model_type == 'classification':
                model_name = config.QWEN_MODEL_CLASSIFICATION
            else:  # generation
                model_name = config.QWEN_MODEL_GENERATION
                
            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
                # Qwen3 models require enable_thinking: False when not using streaming
                # to avoid API errors. This is automatically included in all Qwen API calls.
                "extra_body": {"enable_thinking": False}
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(self.api_url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('choices', [{}])[0].get('message', {}).get('content', '')
                    else:
                        error_text = await response.text()
                        logger.error(f"Qwen API error {response.status}: {error_text}")
                        raise Exception(f"Qwen API error: {response.status}")
                        
        except asyncio.TimeoutError:
            logger.error("Qwen API timeout")
            raise Exception("Qwen API timeout")
        except Exception as e:
            logger.error(f"Qwen API error: {e}")
            raise
    
    async def async_stream_chat_completion(
        self, 
        messages: List[Dict], 
        temperature: float = None,
        max_tokens: int = 1000
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion from Qwen API (async generator).
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 1.0), None uses default
            max_tokens: Maximum tokens in response
            
        Yields:
            str: Content chunks as they arrive from Qwen API
        """
        try:
            # Use instance default if not specified
            if temperature is None:
                temperature = self.default_temperature
            
            # Select appropriate model
            if self.model_type == 'classification':
                model_name = config.QWEN_MODEL_CLASSIFICATION
            else:
                model_name = config.QWEN_MODEL_GENERATION
            
            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": True,  # Enable streaming
                "extra_body": {"enable_thinking": False}
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Stream with timeout
            timeout = aiohttp.ClientTimeout(
                total=None,  # No total timeout for streaming
                connect=10,
                sock_read=self.timeout
            )
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self.api_url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Qwen stream error {response.status}: {error_text}")
                        raise Exception(f"Qwen stream error: {response.status}")
                    
                    # Read SSE stream line by line
                    async for line_bytes in response.content:
                        line = line_bytes.decode('utf-8').strip()
                        
                        if not line or not line.startswith('data: '):
                            continue
                        
                        data_content = line[6:]  # Remove 'data: ' prefix
                        
                        # Handle [DONE] signal
                        if data_content.strip() == '[DONE]':
                            break
                        
                        try:
                            data = json.loads(data_content)
                            # Extract content delta from streaming response
                            delta = data.get('choices', [{}])[0].get('delta', {})
                            content = delta.get('content', '')
                            
                            if content:
                                yield content
                        
                        except json.JSONDecodeError:
                            continue
        
        except Exception as e:
            logger.error(f"Qwen streaming error: {e}")
            raise


# ============================================================================
# MULTI-LLM CLIENT (DeepSeek, Kimi, ChatGLM)
# ============================================================================

class DeepSeekClient:
    """Client for DeepSeek R1 via Dashscope API"""
    
    def __init__(self):
        """Initialize DeepSeek client"""
        self.api_url = config.QWEN_API_URL  # Dashscope uses same endpoint
        self.api_key = config.QWEN_API_KEY
        self.timeout = 60  # seconds (DeepSeek R1 can be slower for reasoning)
        self.model_id = 'deepseek'
        self.model_name = config.DEEPSEEK_MODEL
        # DIVERSITY FIX: Lower temperature for DeepSeek (reasoning model, more deterministic)
        self.default_temperature = 0.6
        logger.debug(f"DeepSeekClient initialized with model: {self.model_name}")
    
    async def async_chat_completion(self, messages: List[Dict], temperature: float = None,
                                   max_tokens: int = 2000) -> str:
        """
        Send async chat completion request to DeepSeek R1
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 1.0), None uses default
            max_tokens: Maximum tokens in response
            
        Returns:
            Response content as string
        """
        try:
            # Use instance default if not specified
            if temperature is None:
                temperature = self.default_temperature
            
            payload = config.get_llm_data(
                messages[-1]['content'] if messages else '',
                self.model_id
            )
            payload['messages'] = messages
            payload['temperature'] = temperature
            payload['max_tokens'] = max_tokens
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            logger.debug(f"DeepSeek async API request: {self.model_name}")
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(self.api_url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                        logger.debug(f"DeepSeek response length: {len(content)} chars")
                        return content
                    else:
                        error_text = await response.text()
                        logger.error(f"DeepSeek API error {response.status}: {error_text}")
                        raise Exception(f"DeepSeek API error: {response.status}")
                        
        except asyncio.TimeoutError:
            logger.error("DeepSeek API timeout")
            raise Exception("DeepSeek API timeout")
        except Exception as e:
            logger.error(f"DeepSeek API error: {e}")
            raise
    
    # Alias for compatibility with agents that call chat_completion
    async def chat_completion(self, messages: List[Dict], temperature: float = None,
                             max_tokens: int = 2000) -> str:
        """Alias for async_chat_completion for API consistency"""
        return await self.async_chat_completion(messages, temperature, max_tokens)
    
    async def async_stream_chat_completion(
        self, 
        messages: List[Dict], 
        temperature: float = None,
        max_tokens: int = 2000
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion from DeepSeek R1 (async generator).
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 1.0), None uses default
            max_tokens: Maximum tokens in response
            
        Yields:
            str: Content chunks as they arrive
        """
        try:
            if temperature is None:
                temperature = self.default_temperature
            
            payload = config.get_llm_data(
                messages[-1]['content'] if messages else '',
                self.model_id
            )
            payload['messages'] = messages
            payload['temperature'] = temperature
            payload['max_tokens'] = max_tokens
            payload['stream'] = True  # Enable streaming
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            timeout = aiohttp.ClientTimeout(
                total=None,
                connect=10,
                sock_read=self.timeout
            )
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self.api_url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"DeepSeek stream error {response.status}: {error_text}")
                        raise Exception(f"DeepSeek stream error: {response.status}")
                    
                    async for line_bytes in response.content:
                        line = line_bytes.decode('utf-8').strip()
                        
                        if not line or not line.startswith('data: '):
                            continue
                        
                        data_content = line[6:]
                        
                        if data_content.strip() == '[DONE]':
                            break
                        
                        try:
                            data = json.loads(data_content)
                            delta = data.get('choices', [{}])[0].get('delta', {})
                            content = delta.get('content', '')
                            
                            if content:
                                yield content
                        
                        except json.JSONDecodeError:
                            continue
        
        except Exception as e:
            logger.error(f"DeepSeek streaming error: {e}")
            raise


class KimiClient:
    """Client for Kimi (Moonshot AI) via Dashscope API"""
    
    def __init__(self):
        """Initialize Kimi client"""
        self.api_url = config.QWEN_API_URL  # Dashscope uses same endpoint
        self.api_key = config.QWEN_API_KEY
        self.timeout = 60  # seconds
        self.model_id = 'kimi'
        self.model_name = config.KIMI_MODEL
        # DIVERSITY FIX: Higher temperature for Kimi to increase creative variation
        self.default_temperature = 1.0
        logger.debug(f"KimiClient initialized with model: {self.model_name}")
    
    async def async_chat_completion(self, messages: List[Dict], temperature: float = None,
                                   max_tokens: int = 2000) -> str:
        """Async chat completion for Kimi"""
        try:
            # Use instance default if not specified
            if temperature is None:
                temperature = self.default_temperature
            
            payload = config.get_llm_data(
                messages[-1]['content'] if messages else '',
                self.model_id
            )
            payload['messages'] = messages
            payload['temperature'] = temperature
            payload['max_tokens'] = max_tokens
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            logger.debug(f"Kimi async API request: {self.model_name}")
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
                async with session.post(self.api_url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
                        logger.debug(f"Kimi response length: {len(content)} chars")
                        return content
                    else:
                        error_text = await response.text()
                        logger.error(f"Kimi API error {response.status}: {error_text}")
                        raise Exception(f"Kimi API error: {response.status}")
                        
        except asyncio.TimeoutError:
            logger.error("Kimi API timeout")
            raise Exception("Kimi API timeout")
        except Exception as e:
            logger.error(f"Kimi API error: {e}")
            raise
    
    # Alias for compatibility with agents that call chat_completion
    async def chat_completion(self, messages: List[Dict], temperature: float = None,
                             max_tokens: int = 2000) -> str:
        """Alias for async_chat_completion for API consistency"""
        return await self.async_chat_completion(messages, temperature, max_tokens)
    
    async def async_stream_chat_completion(
        self, 
        messages: List[Dict], 
        temperature: float = None,
        max_tokens: int = 2000
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion from Kimi (async generator).
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 1.0), None uses default
            max_tokens: Maximum tokens in response
            
        Yields:
            str: Content chunks as they arrive
        """
        try:
            if temperature is None:
                temperature = self.default_temperature
            
            payload = config.get_llm_data(
                messages[-1]['content'] if messages else '',
                self.model_id
            )
            payload['messages'] = messages
            payload['temperature'] = temperature
            payload['max_tokens'] = max_tokens
            payload['stream'] = True  # Enable streaming
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            timeout = aiohttp.ClientTimeout(
                total=None,
                connect=10,
                sock_read=self.timeout
            )
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(self.api_url, json=payload, headers=headers) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Kimi stream error {response.status}: {error_text}")
                        raise Exception(f"Kimi stream error: {response.status}")
                    
                    async for line_bytes in response.content:
                        line = line_bytes.decode('utf-8').strip()
                        
                        if not line or not line.startswith('data: '):
                            continue
                        
                        data_content = line[6:]
                        
                        if data_content.strip() == '[DONE]':
                            break
                        
                        try:
                            data = json.loads(data_content)
                            delta = data.get('choices', [{}])[0].get('delta', {})
                            content = delta.get('content', '')
                            
                            if content:
                                yield content
                        
                        except json.JSONDecodeError:
                            continue
        
        except Exception as e:
            logger.error(f"Kimi streaming error: {e}")
            raise


class HunyuanClient:
    """Client for Tencent Hunyuan (混元) using OpenAI-compatible API"""
    
    def __init__(self):
        """Initialize Hunyuan client with OpenAI SDK"""
        self.api_key = config.HUNYUAN_API_KEY
        self.base_url = "https://api.hunyuan.cloud.tencent.com/v1"
        self.model_name = "hunyuan-turbo"  # Using standard model name
        self.timeout = 60  # seconds
        
        # DIVERSITY FIX: Highest temperature for HunYuan for maximum variation
        self.default_temperature = 1.2
        
        # Initialize AsyncOpenAI client with custom base URL
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout
        )
        
        logger.info(f"HunyuanClient initialized with OpenAI-compatible API: {self.model_name}")
    
    async def async_chat_completion(self, messages: List[Dict], temperature: float = None,
                                   max_tokens: int = 2000) -> str:
        """
        Send async chat completion request to Tencent Hunyuan (OpenAI-compatible)
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 2.0), None uses default
            max_tokens: Maximum tokens in response
            
        Returns:
            Response content as string
        """
        try:
            # Use instance default if not specified
            if temperature is None:
                temperature = self.default_temperature
            
            logger.debug(f"Hunyuan async API request: {self.model_name} (temp: {temperature})")
            
            # Call OpenAI-compatible API
            completion = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Extract content from response
            content = completion.choices[0].message.content
            
            if content:
                logger.debug(f"Hunyuan response length: {len(content)} chars")
                return content
            else:
                logger.error("Hunyuan API returned empty content")
                raise Exception("Hunyuan API returned empty content")
                
        except Exception as e:
            logger.error(f"Hunyuan API error: {e}")
            raise
    
    # Alias for compatibility with agents that call chat_completion
    async def chat_completion(self, messages: List[Dict], temperature: float = None,
                             max_tokens: int = 2000) -> str:
        """Alias for async_chat_completion for API consistency"""
        return await self.async_chat_completion(messages, temperature, max_tokens)
    
    async def async_stream_chat_completion(
        self, 
        messages: List[Dict], 
        temperature: float = None,
        max_tokens: int = 2000
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion from Hunyuan using OpenAI-compatible API.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 2.0), None uses default
            max_tokens: Maximum tokens in response
            
        Yields:
            str: Content chunks as they arrive
        """
        try:
            if temperature is None:
                temperature = self.default_temperature
            
            logger.debug(f"Hunyuan stream API request: {self.model_name} (temp: {temperature})")
            
            # Use OpenAI SDK's streaming
            stream = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True  # Enable streaming
            )
            
            async for chunk in stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield delta.content
        
        except Exception as e:
            logger.error(f"Hunyuan streaming error: {e}")
            raise

# ============================================================================
# GLOBAL CLIENT INSTANCES
# ============================================================================

# Global client instances
try:
    qwen_client_classification = QwenClient(model_type='classification')  # qwen-turbo
    qwen_client_generation = QwenClient(model_type='generation')         # qwen-plus
    qwen_client = qwen_client_classification  # Legacy compatibility
    
    # Multi-LLM clients - Dedicated classes for each provider
    deepseek_client = DeepSeekClient()
    kimi_client = KimiClient()
    hunyuan_client = HunyuanClient()
    
    # Only log from main worker to avoid duplicate messages
    import os
    if os.getenv('UVICORN_WORKER_ID') is None or os.getenv('UVICORN_WORKER_ID') == '0':
        logger.info("LLM clients initialized successfully (Qwen, DeepSeek, Kimi, Hunyuan)")
except Exception as e:
    logger.warning(f"Failed to initialize LLM clients: {e}")
    qwen_client = None
    qwen_client_classification = None
    qwen_client_generation = None
    deepseek_client = None
    kimi_client = None
    hunyuan_client = None

def get_llm_client(model_id='qwen'):
    """
    Get an LLM client by model ID.
    
    Args:
        model_id (str): 'qwen', 'deepseek', 'kimi', or 'hunyuan'
        
    Returns:
        LLM client instance
    """
    client_map = {
        'qwen': qwen_client_generation,
        'deepseek': deepseek_client,
        'kimi': kimi_client,
        'hunyuan': hunyuan_client
    }
    
    client = client_map.get(model_id)
    
    if client is not None:
        logger.info(f"Using {model_id} LLM client")
        return client
    else:
        logger.warning("Qwen client not available, using mock client for testing")
        # Return a mock client for testing when real client is not available
        class MockLLMClient:
            def chat_completion(self, messages, temperature=0.7, max_tokens=1000):
                """Mock LLM client that returns structured responses for testing."""
                # Handle the message format that agents use
                if isinstance(messages, list) and len(messages) > 0:
                    # Extract content from messages
                    content = ""
                    for msg in messages:
                        if msg.get('role') == 'user':
                            content += msg.get('content', '')
                        elif msg.get('role') == 'system':
                            content += msg.get('content', '')
                    
                    # Generate appropriate mock responses based on the prompt content
                    if 'double bubble' in content.lower():
                        return {
                            "topic1": "Topic A",
                            "topic2": "Topic B",
                            "topic1_attributes": [
                                {"id": "la1", "text": "Unique to A", "category": "A-only"},
                                {"id": "la2", "text": "Another A trait", "category": "A-only"}
                            ],
                            "topic2_attributes": [
                                {"id": "ra1", "text": "Unique to B", "category": "B-only"},
                                {"id": "ra2", "text": "Another B trait", "category": "B-only"}
                            ],
                            "shared_attributes": [
                                {"id": "shared1", "text": "Common trait", "category": "Shared"},
                                {"id": "shared2", "text": "Another common trait", "category": "Shared"}
                            ],
                            "connections": [
                                {"from": "topic1", "to": "la1", "label": "has"},
                                {"from": "topic1", "to": "la2", "label": "has"},
                                {"from": "topic2", "to": "ra1", "label": "has"},
                                {"from": "topic2", "to": "ra2", "label": "has"},
                                {"from": "topic1", "to": "shared1", "label": "shares"},
                                {"from": "topic2", "to": "shared1", "label": "shares"},
                                {"from": "topic1", "to": "shared2", "label": "shares"},
                                {"from": "topic2", "to": "shared2", "label": "shares"}
                            ]
                        }
                    elif 'bubble map' in content.lower():
                        return {
                            "topic": "Test Topic",
                            "attributes": [
                                {"id": "attr1", "text": "Attribute 1", "category": "Category 1"},
                                {"id": "attr2", "text": "Attribute 2", "category": "Category 2"},
                                {"id": "attr3", "text": "Attribute 3", "category": "Category 3"}
                            ],
                            "connections": [
                                {"from": "topic", "to": "attr1", "label": "has"},
                                {"from": "topic", "to": "attr2", "label": "includes"},
                                {"from": "topic", "to": "attr3", "label": "contains"}
                            ]
                        }
                    elif 'circle map' in content.lower():
                        return {
                            "central_topic": "Central Concept",
                            "inner_circle": {"title": "Definition", "content": "A clear definition of the concept"},
                            "middle_circle": {"title": "Examples", "content": "Example 1, Example 2, Example 3"},
                            "outer_circle": {"title": "Context", "content": "The broader context where this concept applies"},
                            "context_elements": [
                                {"id": "elem1", "text": "Context Element 1"},
                                {"id": "elem2", "text": "Context Element 2"}
                            ],
                            "connections": [
                                {"from": "central_topic", "to": "elem1", "label": "relates to"},
                                {"from": "central_topic", "to": "elem2", "label": "connects to"}
                            ]
                        }
                    elif 'bridge map' in content.lower():
                        return {
                            "analogy_bridge": "Common relationship",
                            "left_side": {
                                "topic": "Source Topic",
                                "elements": [
                                    {"id": "source1", "text": "Source Element 1"},
                                    {"id": "source2", "text": "Source Element 2"}
                                ]
                            },
                            "right_side": {
                                "topic": "Target Topic",
                                "elements": [
                                    {"id": "target1", "text": "Target Element 1"},
                                    {"id": "target2", "text": "Target Element 2"}
                                ]
                            },
                            "bridge_connections": [
                                {"from": "source1", "to": "target1", "label": "relates to", "bridge_text": "Common relationship"},
                                {"from": "source2", "to": "target2", "label": "connects to", "bridge_text": "Common relationship"}
                            ]
                        }
                    elif 'concept map' in content.lower():
                        return {
                            "topic": "Central Topic",
                            "concepts": ["Concept 1", "Concept 2", "Concept 3", "Concept 4"],
                            "relationships": [
                                {"from": "Concept 1", "to": "Concept 2", "label": "relates to"},
                                {"from": "Concept 2", "to": "Concept 3", "label": "includes"},
                                {"from": "Concept 3", "to": "Concept 4", "label": "part of"}
                            ]
                        }
                    elif 'brace map' in content.lower():
                        return {
                            "topic": "Central Topic",
                            "parts": [
                                {"name": "Part 1", "subparts": [{"name": "Subpart 1"}]},
                                {"name": "Part 2", "subparts": [{"name": "Subpart 2"}]}
                            ]
                        }
                    elif 'multi-flow' in content.lower():
                        return {
                            "event": "Multi-Flow Event",
                            "causes": ["Cause 1", "Cause 2", "Cause 3"],
                            "effects": ["Effect 1", "Effect 2", "Effect 3"]
                        }
                    elif 'flow map' in content.lower() or 'flow maps' in content.lower():
                        return {
                            "title": "Flow Topic",
                            "steps": ["Step 1", "Step 2", "Step 3"]
                        }
                    elif 'mind map' in content.lower():
                        return {
                            "topic": "Central Topic",
                            "children": [
                                {"id": "branch1", "label": "Branch 1", "children": [{"id": "sub1", "label": "Sub-item 1"}]},
                                {"id": "branch2", "label": "Branch 2", "children": [{"id": "sub2", "label": "Sub-item 2"}]}
                            ]
                        }
                    elif 'tree map' in content.lower():
                        return {
                            "topic": "Root Topic",
                            "children": [
                                {"id": "branch1", "label": "Branch 1", "children": [{"id": "sub1", "label": "Sub-item 1"}]},
                                {"id": "branch2", "label": "Branch 2", "children": [{"id": "sub2", "label": "Sub-item 2"}]}
                            ]
                        }
                    else:
                        # Generic response for other diagram types
                        return {"result": "mock response", "type": "generic"}
                else:
                    # Fallback for other formats
                    return {"result": "mock response", "type": "fallback"}
        return MockLLMClient() 