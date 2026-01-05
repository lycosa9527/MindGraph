"""
Async Dify API Client for FastAPI MindGraph Application
========================================================

Async version of DifyClient using aiohttp for non-blocking SSE streaming.
This is the CRITICAL component enabling 4,000+ concurrent SSE connections.

Supports Dify Chatflow API v1 with full feature set:
- Streaming chat with file uploads and workflow support
- Conversation management (list, delete, rename, variables)
- Message history and feedback
- File upload and preview
- Audio conversion (TTS/STT)
- App info, parameters (opening_statement), meta, site

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import aiohttp
import json
import time
import logging
import os
from typing import AsyncGenerator, Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DifyFile:
    """File object for Dify API uploads"""
    type: str  # document, image, audio, video, custom
    transfer_method: str  # remote_url or local_file
    url: Optional[str] = None  # For remote_url
    upload_file_id: Optional[str] = None  # For local_file

    def to_dict(self) -> Dict[str, Any]:
        result = {"type": self.type, "transfer_method": self.transfer_method}
        if self.url:
            result["url"] = self.url
        if self.upload_file_id:
            result["upload_file_id"] = self.upload_file_id
        return result


class AsyncDifyClient:
    """Async client for interacting with Dify API using aiohttp"""
    
    def __init__(self, api_key: str, api_url: str, timeout: int = 30):
        self.api_key = api_key
        self.api_url = api_url.rstrip('/')
        self.timeout = timeout
        
    def _get_headers(self, content_type: str = "application/json") -> Dict[str, str]:
        """Get common request headers"""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    async def _request(
        self, 
        method: str, 
        endpoint: str, 
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        data: Optional[aiohttp.FormData] = None
    ) -> Dict[str, Any]:
        """Make a non-streaming HTTP request to Dify API"""
        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        
        headers = self._get_headers() if not data else self._get_headers(content_type="")
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(
                method, url, json=json_data, params=params, data=data, headers=headers
            ) as response:
                if response.status == 204:
                    return {"result": "success"}
                if response.status != 200:
                    error_msg = f"HTTP {response.status}"
                    try:
                        error_data = await response.json()
                        error_msg = error_data.get('message', error_msg)
                    except:
                        pass
                    raise Exception(error_msg)
                return await response.json()

    # =========================================================================
    # Chat Messages
    # =========================================================================
    
    async def stream_chat(
        self, 
        message: str, 
        user_id: str, 
        conversation_id: Optional[str] = None,
        files: Optional[List[DifyFile]] = None,
        inputs: Optional[Dict[str, Any]] = None,
        auto_generate_name: bool = True,
        workflow_id: Optional[str] = None,
        trace_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream chat response from Dify API (async version).
        
        Args:
            message: User's message (query)
            user_id: Unique user identifier
            conversation_id: Optional conversation ID for context
            files: Optional list of DifyFile objects for Vision/Video
            inputs: Optional app-defined variable values
            auto_generate_name: Auto-generate conversation title (default True)
            workflow_id: Optional workflow version ID
            trace_id: Optional trace ID for distributed tracing
            
        Yields:
            Dict containing event data from Dify API
            Events: message, message_file, message_end, message_replace,
                    workflow_started, node_started, node_finished, workflow_finished,
                    tts_message, tts_message_end, error, ping
        """
        
        logger.debug(f"[DIFY] Async streaming message: {message[:50]}... for user {user_id}")
        
        payload = {
            "inputs": inputs or {},
            "query": message,
            "response_mode": "streaming",
            "user": user_id,
            "auto_generate_name": auto_generate_name
        }
        
        if conversation_id:
            payload["conversation_id"] = conversation_id
        if files:
            payload["files"] = [f.to_dict() for f in files]
        if workflow_id:
            payload["workflow_id"] = workflow_id
        if trace_id:
            payload["trace_id"] = trace_id
            
        headers = self._get_headers()
        
        try:
            url = f"{self.api_url}/chat-messages"
            logger.debug(f"[DIFY] Making async request to: {url}")
            
            timeout = aiohttp.ClientTimeout(
                total=None,
                connect=10,
                sock_read=self.timeout
            )
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    
                    if response.status != 200:
                        error_msg = f"HTTP {response.status}: API request failed"
                        try:
                            error_data = await response.json()
                            error_msg = error_data.get('message', error_msg)
                        except:
                            pass
                        logger.error(f"Dify API error: {error_msg}")
                        yield {'event': 'error', 'error': error_msg, 'timestamp': int(time.time() * 1000)}
                        return
                    
                    async for line_bytes in response.content:
                        try:
                            line = line_bytes.decode('utf-8').strip()
                            if not line:
                                continue
                            
                            if line.startswith('data: '):
                                data_content = line[6:]
                            elif line.startswith('data:'):
                                data_content = line[5:]
                            else:
                                continue
                            
                            if data_content.strip():
                                if data_content.strip() == '[DONE]':
                                    logger.debug("Received [DONE] signal from Dify")
                                    break
                                
                                chunk_data = json.loads(data_content.strip())
                                chunk_data['timestamp'] = int(time.time() * 1000)
                                yield chunk_data
                                
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            logger.error(f"Error processing line: {e}")
                            continue
                    
                    logger.debug(f"[DIFY] Async stream completed successfully")
                            
        except aiohttp.ClientError as e:
            logger.error(f"Dify API async request error: {e}")
            yield {'event': 'error', 'error': str(e), 'timestamp': int(time.time() * 1000)}
        except Exception as e:
            logger.error(f"Dify API async error: {e}")
            yield {'event': 'error', 'error': str(e), 'timestamp': int(time.time() * 1000)}

    async def chat_blocking(
        self,
        message: str,
        user_id: str,
        conversation_id: Optional[str] = None,
        files: Optional[List[DifyFile]] = None,
        inputs: Optional[Dict[str, Any]] = None,
        auto_generate_name: bool = True,
        workflow_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send chat message in blocking mode (wait for complete response)"""
        payload = {
            "inputs": inputs or {},
            "query": message,
            "response_mode": "blocking",
            "user": user_id,
            "auto_generate_name": auto_generate_name
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id
        if files:
            payload["files"] = [f.to_dict() for f in files]
        if workflow_id:
            payload["workflow_id"] = workflow_id
            
        return await self._request("POST", "/chat-messages", json_data=payload)

    async def stop_chat(self, task_id: str, user_id: str) -> Dict[str, Any]:
        """Stop a streaming response"""
        return await self._request(
            "POST", f"/chat-messages/{task_id}/stop", 
            json_data={"user": user_id}
        )

    # =========================================================================
    # Messages
    # =========================================================================
    
    async def get_messages(
        self,
        conversation_id: str,
        user_id: str,
        first_id: Optional[str] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """Get conversation history messages"""
        params = {"conversation_id": conversation_id, "user": user_id, "limit": limit}
        if first_id:
            params["first_id"] = first_id
        return await self._request("GET", "/messages", params=params)

    async def message_feedback(
        self,
        message_id: str,
        user_id: str,
        rating: Optional[str] = None,
        content: Optional[str] = None
    ) -> Dict[str, Any]:
        """Submit message feedback (like/dislike)"""
        payload = {"user": user_id}
        if rating:
            payload["rating"] = rating  # "like", "dislike", or null
        if content:
            payload["content"] = content
        return await self._request("POST", f"/messages/{message_id}/feedbacks", json_data=payload)

    async def get_suggested_questions(self, message_id: str, user_id: str) -> Dict[str, Any]:
        """Get suggested follow-up questions"""
        return await self._request("GET", f"/messages/{message_id}/suggested", params={"user": user_id})

    # =========================================================================
    # Conversations
    # =========================================================================
    
    async def get_conversations(
        self,
        user_id: str,
        last_id: Optional[str] = None,
        limit: int = 20,
        sort_by: str = "-updated_at"
    ) -> Dict[str, Any]:
        """Get user's conversation list"""
        params = {"user": user_id, "limit": limit, "sort_by": sort_by}
        if last_id:
            params["last_id"] = last_id
        return await self._request("GET", "/conversations", params=params)

    async def delete_conversation(self, conversation_id: str, user_id: str) -> Dict[str, Any]:
        """Delete a conversation"""
        return await self._request(
            "DELETE", f"/conversations/{conversation_id}", 
            json_data={"user": user_id}
        )

    async def rename_conversation(
        self,
        conversation_id: str,
        user_id: str,
        name: Optional[str] = None,
        auto_generate: bool = False
    ) -> Dict[str, Any]:
        """Rename a conversation"""
        payload = {"user": user_id, "auto_generate": auto_generate}
        if name:
            payload["name"] = name
        return await self._request("POST", f"/conversations/{conversation_id}/name", json_data=payload)

    async def get_conversation_variables(
        self,
        conversation_id: str,
        user_id: str,
        last_id: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """Get conversation variables"""
        params = {"user": user_id, "limit": limit}
        if last_id:
            params["last_id"] = last_id
        return await self._request("GET", f"/conversations/{conversation_id}/variables", params=params)

    async def update_conversation_variable(
        self,
        conversation_id: str,
        variable_id: str,
        user_id: str,
        value: Any
    ) -> Dict[str, Any]:
        """Update a conversation variable"""
        return await self._request(
            "PUT", f"/conversations/{conversation_id}/variables/{variable_id}",
            json_data={"user": user_id, "value": value}
        )

    # =========================================================================
    # Files
    # =========================================================================
    
    async def upload_file(self, file_path: str, user_id: str) -> Dict[str, Any]:
        """Upload a file for use in chat messages"""
        data = aiohttp.FormData()
        data.add_field('user', user_id)
        data.add_field('file', open(file_path, 'rb'), filename=os.path.basename(file_path))
        return await self._request("POST", "/files/upload", data=data)

    async def get_file_preview_url(self, file_id: str, as_attachment: bool = False) -> str:
        """Get file preview/download URL"""
        url = f"{self.api_url}/files/{file_id}/preview"
        if as_attachment:
            url += "?as_attachment=true"
        return url

    # =========================================================================
    # Audio
    # =========================================================================
    
    async def audio_to_text(self, audio_file_path: str, user_id: str) -> Dict[str, Any]:
        """Convert speech to text"""
        data = aiohttp.FormData()
        data.add_field('user', user_id)
        data.add_field('file', open(audio_file_path, 'rb'), filename=os.path.basename(audio_file_path))
        return await self._request("POST", "/audio-to-text", data=data)

    async def text_to_audio(
        self,
        user_id: str,
        text: Optional[str] = None,
        message_id: Optional[str] = None
    ) -> bytes:
        """Convert text to speech, returns audio bytes"""
        url = f"{self.api_url}/text-to-audio"
        payload = {"user": user_id}
        if message_id:
            payload["message_id"] = message_id
        if text:
            payload["text"] = text
            
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload, headers=self._get_headers()) as response:
                if response.status != 200:
                    raise Exception(f"TTS failed: HTTP {response.status}")
                return await response.read()

    # =========================================================================
    # App Information
    # =========================================================================
    
    async def get_app_info(self) -> Dict[str, Any]:
        """Get app basic information (name, description, tags)"""
        return await self._request("GET", "/info")

    async def get_app_parameters(self) -> Dict[str, Any]:
        """
        Get app parameters including opening_statement, suggested_questions,
        user_input_form, file_upload settings, speech settings, etc.
        
        Returns:
            Dict containing:
            - opening_statement: Opening greeting message
            - suggested_questions: List of suggested initial questions
            - suggested_questions_after_answer: Settings for follow-up suggestions
            - speech_to_text/text_to_speech: Audio feature settings
            - retriever_resource: Citation settings
            - user_input_form: Form field configurations
            - file_upload: File upload settings by type
            - system_parameters: System limits
        """
        return await self._request("GET", "/parameters")

    async def get_app_meta(self) -> Dict[str, Any]:
        """Get app meta information (tool icons)"""
        return await self._request("GET", "/meta")

    async def get_app_site(self) -> Dict[str, Any]:
        """Get WebApp settings (title, theme, icon, description, etc.)"""
        return await self._request("GET", "/site")

    # =========================================================================
    # Feedbacks
    # =========================================================================
    
    async def get_app_feedbacks(self, page: int = 1, limit: int = 20) -> Dict[str, Any]:
        """Get all app feedbacks"""
        return await self._request("GET", "/app/feedbacks", params={"page": page, "limit": limit})

    # =========================================================================
    # Annotations
    # =========================================================================
    
    async def get_annotations(self, page: int = 1, limit: int = 20) -> Dict[str, Any]:
        """Get annotation list"""
        return await self._request("GET", "/apps/annotations", params={"page": page, "limit": limit})

    async def create_annotation(self, question: str, answer: str) -> Dict[str, Any]:
        """Create an annotation"""
        return await self._request("POST", "/apps/annotations", json_data={"question": question, "answer": answer})

    async def update_annotation(self, annotation_id: str, question: str, answer: str) -> Dict[str, Any]:
        """Update an annotation"""
        return await self._request(
            "PUT", f"/apps/annotations/{annotation_id}",
            json_data={"question": question, "answer": answer}
        )

    async def delete_annotation(self, annotation_id: str) -> Dict[str, Any]:
        """Delete an annotation"""
        return await self._request("DELETE", f"/apps/annotations/{annotation_id}")

    async def set_annotation_reply(
        self,
        action: str,
        score_threshold: float = 0.9,
        embedding_provider_name: Optional[str] = None,
        embedding_model_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Enable or disable annotation reply"""
        payload = {"score_threshold": score_threshold}
        if embedding_provider_name:
            payload["embedding_provider_name"] = embedding_provider_name
        if embedding_model_name:
            payload["embedding_model_name"] = embedding_model_name
        return await self._request("POST", f"/apps/annotation-reply/{action}", json_data=payload)

    async def get_annotation_reply_status(self, action: str, job_id: str) -> Dict[str, Any]:
        """Get annotation reply job status"""
        return await self._request("GET", f"/apps/annotation-reply/{action}/status/{job_id}")


# Only log from main worker to avoid duplicate messages
if os.getenv('UVICORN_WORKER_ID') is None or os.getenv('UVICORN_WORKER_ID') == '0':
    logger.debug("Dify client module loaded")
