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
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
from settings import config

# Load environment variables for logging configuration
load_dotenv()

logger = logging.getLogger(__name__)
log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
log_level = getattr(logging, log_level_str, logging.INFO)
logger.setLevel(log_level)


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
        
    async def chat_completion(self, messages: List[Dict], temperature: float = 0.7, 
                            max_tokens: int = 1000) -> str:
        """
        Send chat completion request to Qwen (async version)
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens in response
            
        Returns:
            Response content as string
        """
        try:
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

    def chat_completion(self, messages: List[Dict], temperature: float = 0.7, 
                       max_tokens: int = 1000) -> str:
        """
        Send chat completion request to Qwen (sync version for agents)
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens in response
            
        Returns:
            Response content as string
        """
        try:
            # Run the async version in a new event loop
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we're already in an event loop, create a new one
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(
                        self._chat_completion_async(messages, temperature, max_tokens)
                    )
                    loop.close()
                    return result
                else:
                    return loop.run_until_complete(
                        self._chat_completion_async(messages, temperature, max_tokens)
                    )
            except RuntimeError:
                # No event loop, create one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(
                    self._chat_completion_async(messages, temperature, max_tokens)
                )
                loop.close()
                return result
        except Exception as e:
            logger.error(f"Error in sync chat_completion: {e}")
            raise

    async def _chat_completion_async(self, messages: List[Dict], temperature: float = 0.7, 
                                    max_tokens: int = 1000) -> str:
        """
        Internal async method for chat completion
        """
        try:
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


# Global client instances
try:
    qwen_client_classification = QwenClient(model_type='classification')  # qwen-turbo
    qwen_client_generation = QwenClient(model_type='generation')         # qwen-plus
    qwen_client = qwen_client_classification  # Legacy compatibility
    logger.info("LLM clients initialized successfully")
except Exception as e:
    logger.warning(f"Failed to initialize LLM clients: {e}")
    qwen_client = None
    qwen_client_classification = None
    qwen_client_generation = None

def get_llm_client():
    """Get an available LLM client."""
    # Try to return the real Qwen client if available
    if qwen_client is not None:
        logger.info("Using real Qwen LLM client")
        return qwen_client
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