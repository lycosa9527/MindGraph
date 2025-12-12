"""
Async Dify API Client for FastAPI MindGraph Application
========================================================

Async version of DifyClient using aiohttp for non-blocking SSE streaming.
This is the CRITICAL component enabling 4,000+ concurrent SSE connections.

@author lycosa9527
@made_by MindSpring Team

Migration Status: Phase 3.1 - Async HTTP Client
"""

import aiohttp
import json
import time
import logging
from typing import AsyncGenerator, Dict, Any, Optional

logger = logging.getLogger(__name__)

class AsyncDifyClient:
    """Async client for interacting with Dify API using aiohttp"""
    
    def __init__(self, api_key: str, api_url: str, timeout: int = 30):
        self.api_key = api_key
        self.api_url = api_url.rstrip('/')
        self.timeout = timeout
        
    async def stream_chat(
        self, 
        message: str, 
        user_id: str, 
        conversation_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream chat response from Dify API (async version).
        
        Args:
            message: User's message
            user_id: Unique user identifier
            conversation_id: Optional conversation ID for context
            
        Yields:
            Dict containing event data from Dify API
            
        Note:
            This is an async generator - use `async for chunk in stream_chat(...)`
        """
        
        logger.debug(f"[DIFY] Async streaming message: {message[:50]}... for user {user_id}")
        logger.debug(f"[DIFY] API URL: {self.api_url}, Timeout: {self.timeout}")
        
        payload = {
            "inputs": {},
            "query": message,
            "response_mode": "streaming",
            "user": user_id
        }
        
        if conversation_id:
            payload["conversation_id"] = conversation_id
            logger.debug(f"[DIFY] Using conversation_id: {conversation_id}")
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        logger.debug(f"[DIFY] Request headers: Authorization=Bearer ***")
        
        try:
            url = f"{self.api_url}/chat-messages"
            logger.debug(f"[DIFY] Making async request to: {url}")
            logger.debug(f"[DIFY] Request payload: {json.dumps(payload, ensure_ascii=False)}")
            
            # Create async HTTP session with timeout
            timeout = aiohttp.ClientTimeout(
                total=None,  # No total timeout for streaming
                connect=10,  # 10s connect timeout
                sock_read=self.timeout  # Configurable read timeout per chunk
            )
            
            logger.debug(f"[DIFY] Sending async POST request...")
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    
                    logger.debug(f"[DIFY] Response status: {response.status}")
                    logger.debug(f"[DIFY] Response headers: {dict(response.headers)}")
                    
                    # Check status code
                    if response.status != 200:
                        error_msg = f"HTTP {response.status}: API request failed"
                        try:
                            error_data = await response.json()
                            error_msg = error_data.get('message', error_msg)
                        except:
                            pass
                            
                        logger.error(f"Dify API error: {error_msg}")
                        yield {
                            'event': 'error',
                            'error': error_msg,
                            'timestamp': int(time.time() * 1000)
                        }
                        return
                    
                    # Stream the response line by line (async)
                    async for line_bytes in response.content:
                        try:
                            # Decode bytes to string
                            line = line_bytes.decode('utf-8').strip()
                            
                            # Handle empty lines
                            if not line:
                                continue
                            
                            # Parse SSE format
                            if line.startswith('data: '):
                                data_content = line[6:]  # Remove 'data: ' prefix
                            elif line.startswith('data:'):
                                data_content = line[5:]  # Remove 'data:' prefix
                            else:
                                continue
                            
                            if data_content.strip():
                                # Handle [DONE] signal
                                if data_content.strip() == '[DONE]':
                                    logger.debug("Received [DONE] signal from Dify")
                                    break
                                
                                chunk_data = json.loads(data_content.strip())
                                chunk_data['timestamp'] = int(time.time() * 1000)
                                
                                logger.debug(f"Received chunk: {chunk_data.get('event', 'unknown')}")
                                yield chunk_data
                                
                        except json.JSONDecodeError as e:
                            logger.debug(f"Skipping malformed JSON line: {line[:100] if line else 'empty'}...")
                            continue
                        except Exception as e:
                            logger.error(f"Error processing line: {e}")
                            continue
                    
                    logger.debug(f"[DIFY] Async stream completed successfully")
                            
        except aiohttp.ClientError as e:
            logger.error(f"Dify API async request error: {e}")
            yield {
                'event': 'error',
                'error': str(e),
                'timestamp': int(time.time() * 1000)
            }
        except Exception as e:
            logger.error(f"Dify API async error: {e}")
            yield {
                'event': 'error',
                'error': str(e),
                'timestamp': int(time.time() * 1000)
            }

# Only log from main worker to avoid duplicate messages
import os
if os.getenv('UVICORN_WORKER_ID') is None or os.getenv('UVICORN_WORKER_ID') == '0':
    logger.debug("Dify client module loaded")

