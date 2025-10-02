"""
Dify API Client for Flask MindGraph Application
Handles streaming responses from Dify API

@author lycosa9527
@made_by MindSpring Team
"""

import requests
import json
import time
import logging
from typing import Generator, Dict, Any, Optional

logger = logging.getLogger(__name__)

class DifyClient:
    """Client for interacting with Dify API"""
    
    def __init__(self, api_key: str, api_url: str, timeout: int = 30):
        self.api_key = api_key
        self.api_url = api_url.rstrip('/')
        self.timeout = timeout
        
    def stream_chat(
        self, 
        message: str, 
        user_id: str, 
        conversation_id: Optional[str] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """Stream chat response from Dify API
        
        Args:
            message: User's message
            user_id: Unique user identifier
            conversation_id: Optional conversation ID for context
            
        Yields:
            Dict containing event data from Dify API
        """
        
        logger.info(f"Sending message to Dify: {message[:50]}... for user {user_id}")
        
        payload = {
            "inputs": {},
            "query": message,
            "response_mode": "streaming",
            "user": user_id
        }
        
        if conversation_id:
            payload["conversation_id"] = conversation_id
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            url = f"{self.api_url}/chat-messages"
            logger.info(f"Making request to: {url}")
            
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                stream=True,
                timeout=(10, self.timeout)  # 10s connect timeout, configurable read timeout
            )
            
            logger.info(f"Response status: {response.status_code}")
            
            # Check status code
            if response.status_code != 200:
                error_msg = f"HTTP {response.status_code}: API request failed"
                try:
                    error_data = response.json()
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
            
            # Stream the response
            for line in response.iter_lines(decode_unicode=True):
                try:
                    # Handle empty lines
                    if not line or not line.strip():
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
                            logger.info("Received [DONE] signal from Dify")
                            break
                        
                        chunk_data = json.loads(data_content.strip())
                        chunk_data['timestamp'] = int(time.time() * 1000)
                        
                        logger.debug(f"Received chunk: {chunk_data.get('event', 'unknown')}")
                        yield chunk_data
                        
                except json.JSONDecodeError as e:
                    logger.debug(f"Skipping malformed JSON line: {line[:100]}...")
                    continue
                except Exception as e:
                    logger.error(f"Error processing line: {e}")
                    continue
                    
        except requests.exceptions.RequestException as e:
            logger.error(f"Dify API request error: {e}")
            yield {
                'event': 'error',
                'error': str(e),
                'timestamp': int(time.time() * 1000)
            }
        except Exception as e:
            logger.error(f"Dify API error: {e}")
            yield {
                'event': 'error',
                'error': str(e),
                'timestamp': int(time.time() * 1000)
            }

