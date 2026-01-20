"""Async Dify API Client for FastAPI MindGraph Application.

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
from dataclasses import dataclass
from typing import AsyncGenerator, Dict, Any, Optional, List, Tuple
from io import BytesIO
import json
import logging
import os
import time
import aiohttp


logger = logging.getLogger(__name__)


# =========================================================================
# Error Classes
# =========================================================================

class DifyAPIError(Exception):
    """Base Dify API error"""
    def __init__(self, message: str, status_code: Optional[int] = None, error_code: Optional[str] = None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(self.message)


class DifyConversationNotFoundError(DifyAPIError):
    """404: Conversation does not exist"""
    def __init__(self, message: str = "Conversation does not exist"):
        super().__init__(message, status_code=404, error_code="conversation_not_exists")


class DifyInvalidParamError(DifyAPIError):
    """400: Invalid parameter input"""
    def __init__(self, message: str = "Invalid parameter input"):
        super().__init__(message, status_code=400, error_code="invalid_param")


class DifyAppUnavailableError(DifyAPIError):
    """400: App configuration unavailable"""
    def __init__(self, message: str = "App configuration unavailable"):
        super().__init__(message, status_code=400, error_code="app_unavailable")


class DifyProviderNotInitializeError(DifyAPIError):
    """400: No available model credential configuration"""
    def __init__(self, message: str = "No available model credential configuration"):
        super().__init__(message, status_code=400, error_code="provider_not_initialize")


class DifyQuotaExceededError(DifyAPIError):
    """400: Model invocation quota insufficient"""
    def __init__(self, message: str = "Model invocation quota insufficient"):
        super().__init__(message, status_code=400, error_code="provider_quota_exceeded")


class DifyModelNotSupportError(DifyAPIError):
    """400: Current model unavailable"""
    def __init__(self, message: str = "Current model unavailable"):
        super().__init__(message, status_code=400, error_code="model_currently_not_support")


class DifyWorkflowNotFoundError(DifyAPIError):
    """400: Specified workflow version not found"""
    def __init__(self, message: str = "Specified workflow version not found"):
        super().__init__(message, status_code=400, error_code="workflow_not_found")


class DifyDraftWorkflowError(DifyAPIError):
    """400: Cannot use draft workflow version"""
    def __init__(self, message: str = "Cannot use draft workflow version"):
        super().__init__(message, status_code=400, error_code="draft_workflow_error")


class DifyWorkflowIdFormatError(DifyAPIError):
    """400: Invalid workflow_id format, expected UUID format"""
    def __init__(self, message: str = "Invalid workflow_id format, expected UUID format"):
        super().__init__(message, status_code=400, error_code="workflow_id_format_error")


class DifyCompletionRequestError(DifyAPIError):
    """400: Text generation failed"""
    def __init__(self, message: str = "Text generation failed"):
        super().__init__(message, status_code=400, error_code="completion_request_error")


class DifyFileAccessDeniedError(DifyAPIError):
    """403: File access denied or file does not belong to current application"""
    def __init__(self, message: str = "File access denied or file does not belong to current application"):
        super().__init__(message, status_code=403, error_code="file_access_denied")


class DifyFileNotFoundError(DifyAPIError):
    """404: File not found or has been deleted"""
    def __init__(self, message: str = "File not found or has been deleted"):
        super().__init__(message, status_code=404, error_code="file_not_found")


# =========================================================================
# Response Models
# =========================================================================

@dataclass
class ChatCompletionResponse:
    """Response model for blocking chat completion"""
    event: str
    task_id: str
    id: str
    message_id: str
    conversation_id: str
    mode: str
    answer: str
    metadata: Optional[Dict[str, Any]] = None
    usage: Optional[Dict[str, Any]] = None
    retriever_resources: Optional[List[Dict[str, Any]]] = None
    created_at: int = 0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatCompletionResponse':
        """Create from API response dict"""
        metadata = data.get('metadata', {})
        return cls(
            event=data.get('event', 'message'),
            task_id=data.get('task_id', ''),
            id=data.get('id', ''),
            message_id=data.get('message_id', ''),
            conversation_id=data.get('conversation_id', ''),
            mode=data.get('mode', 'chat'),
            answer=data.get('answer', ''),
            metadata=metadata,
            usage=metadata.get('usage') if metadata else None,
            retriever_resources=metadata.get('retriever_resources') if metadata else None,
            created_at=data.get('created_at', 0)
        )


@dataclass
class FileUploadResponse:
    """Response model for file upload"""
    id: str
    name: str
    size: int
    extension: str
    mime_type: str
    created_by: str
    created_at: int

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FileUploadResponse':
        """Create from API response dict"""
        return cls(
            id=data.get('id', ''),
            name=data.get('name', ''),
            size=data.get('size', 0),
            extension=data.get('extension', ''),
            mime_type=data.get('mime_type', ''),
            created_by=data.get('created_by', ''),
            created_at=data.get('created_at', 0)
        )


@dataclass
class DifyFile:
    """File object for Dify API uploads"""
    type: str  # document, image, audio, video, custom
    transfer_method: str  # remote_url or local_file
    url: Optional[str] = None  # For remote_url
    upload_file_id: Optional[str] = None  # For local_file

    def to_dict(self) -> Dict[str, Any]:
        """Convert DifyFile to dictionary format for API requests."""
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
        data: Optional[aiohttp.FormData] = None,
        custom_headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Make a non-streaming HTTP request to Dify API"""
        url = f"{self.api_url}/{endpoint.lstrip('/')}"
        timeout = aiohttp.ClientTimeout(total=self.timeout)

        headers = self._get_headers() if not data else self._get_headers(content_type="")
        if custom_headers:
            headers.update(custom_headers)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(
                method, url, json=json_data, params=params, data=data, headers=headers
            ) as response:
                if response.status == 204:
                    return {"result": "success"}
                if response.status != 200:
                    error_msg = f"HTTP {response.status}"
                    error_code = None
                    try:
                        error_data = await response.json()
                        error_msg = error_data.get('message', error_msg)
                        error_code = error_data.get('code')
                    except (json.JSONDecodeError, ValueError):
                        pass

                    # Map status codes and error codes to specific exceptions
                    if response.status == 404:
                        if 'conversation' in endpoint.lower() or error_code == 'conversation_not_exists':
                            raise DifyConversationNotFoundError(error_msg)
                        elif 'file' in endpoint.lower() or error_code == 'file_not_found':
                            raise DifyFileNotFoundError(error_msg)
                    elif response.status == 403 and error_code == 'file_access_denied':
                        raise DifyFileAccessDeniedError(error_msg)
                    elif response.status == 400:
                        if error_code == 'invalid_param':
                            raise DifyInvalidParamError(error_msg)
                        elif error_code == 'app_unavailable':
                            raise DifyAppUnavailableError(error_msg)
                        elif error_code == 'provider_not_initialize':
                            raise DifyProviderNotInitializeError(error_msg)
                        elif error_code == 'provider_quota_exceeded':
                            raise DifyQuotaExceededError(error_msg)
                        elif error_code == 'model_currently_not_support':
                            raise DifyModelNotSupportError(error_msg)
                        elif error_code == 'workflow_not_found':
                            raise DifyWorkflowNotFoundError(error_msg)
                        elif error_code == 'draft_workflow_error':
                            raise DifyDraftWorkflowError(error_msg)
                        elif error_code == 'workflow_id_format_error':
                            raise DifyWorkflowIdFormatError(error_msg)
                        elif error_code == 'completion_request_error':
                            raise DifyCompletionRequestError(error_msg)

                    # Generic error for unmapped cases
                    raise DifyAPIError(error_msg, status_code=response.status, error_code=error_code)
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
        trace_id: Optional[str] = None,
        trace_id_header: bool = True
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
            trace_id_header: If True, use X-Trace-Id header (highest priority per docs).
                           If False, use trace_id in request body.

        Yields:
            Dict containing event data from Dify API
            Events: message, message_file, message_end, message_replace,
                    workflow_started, node_started, node_finished, workflow_finished,
                    tts_message, tts_message_end, error, ping
        """

        logger.debug("[DIFY] Async streaming message: %s... for user %s", message[:50], user_id)

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

        # Trace ID handling: header has highest priority per official docs
        headers = self._get_headers()
        if trace_id:
            if trace_id_header:
                headers["X-Trace-Id"] = trace_id
            else:
                payload["trace_id"] = trace_id

        try:
            url = f"{self.api_url}/chat-messages"
            logger.debug("[DIFY] Making async request to: %s", url)

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
                        except (json.JSONDecodeError, ValueError):
                            pass
                        logger.error("Dify API error: %s", error_msg)
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
                            logger.error("Error processing line: %s", e)
                            continue

                    logger.debug("[DIFY] Async stream completed successfully")

        except aiohttp.ClientError as e:
            logger.error("Dify API async request error: %s", e)
            yield {'event': 'error', 'error': str(e), 'timestamp': int(time.time() * 1000)}
        except Exception as e:
            logger.error("Dify API async error: %s", e)
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

    async def upload_file(
        self,
        user_id: str,
        file_path: Optional[str] = None,
        file_bytes: Optional[bytes] = None,
        filename: Optional[str] = None,
        content_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload a file for use in chat messages.

        Args:
            user_id: User identifier
            file_path: Path to file (mutually exclusive with file_bytes)
            file_bytes: File content as bytes (mutually exclusive with file_path)
            filename: Filename (required if using file_bytes, optional if using file_path)
            content_type: MIME type (optional, will be inferred if not provided)

        Returns:
            Dict containing file upload response with id, name, size, etc.
        """
        if not file_path and not file_bytes:
            raise ValueError("Either file_path or file_bytes must be provided")
        if file_path and file_bytes:
            raise ValueError("Cannot provide both file_path and file_bytes")

        data = aiohttp.FormData()
        data.add_field('user', user_id)

        if file_path:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            filename = filename or os.path.basename(file_path)
            # Read file content to avoid file handle closure issues
            with open(file_path, 'rb') as f:
                file_content = f.read()
            data.add_field('file', BytesIO(file_content), filename=filename, content_type=content_type)
        else:
            if not filename:
                raise ValueError("filename is required when using file_bytes")
            if file_bytes is None:
                raise ValueError("file_bytes cannot be None")
            data.add_field('file', BytesIO(file_bytes), filename=filename, content_type=content_type)

        return await self._request("POST", "/files/upload", data=data)

    async def get_file_preview_url(self, file_id: str, as_attachment: bool = False) -> str:
        """Get file preview/download URL"""
        url = f"{self.api_url}/files/{file_id}/preview"
        if as_attachment:
            url += "?as_attachment=true"
        return url

    async def download_file(
        self,
        file_id: str,
        as_attachment: bool = False
    ) -> Tuple[bytes, Dict[str, str]]:
        """
        Download/preview a file from Dify API.

        Args:
            file_id: The unique identifier of the file
            as_attachment: Whether to force download as attachment (default False for preview)

        Returns:
            Tuple of (file_content_bytes, response_headers_dict)

        Raises:
            DifyFileNotFoundError: If file not found (404)
            DifyFileAccessDeniedError: If file access denied (403)
            DifyAPIError: For other API errors
        """
        url = f"{self.api_url}/files/{file_id}/preview"
        params = {}
        if as_attachment:
            params["as_attachment"] = "true"

        timeout = aiohttp.ClientTimeout(total=self.timeout)
        headers = self._get_headers()

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params, headers=headers) as response:
                if response.status == 404:
                    raise DifyFileNotFoundError("File not found or has been deleted")
                if response.status == 403:
                    raise DifyFileAccessDeniedError("File access denied or file does not belong to current application")
                if response.status != 200:
                    error_msg = f"HTTP {response.status}"
                    try:
                        error_data = await response.json()
                        error_msg = error_data.get('message', error_msg)
                    except (json.JSONDecodeError, ValueError):
                        pass
                    raise DifyAPIError(error_msg, status_code=response.status)

                # Extract response headers
                response_headers = {
                    'Content-Type': response.headers.get('Content-Type', ''),
                    'Content-Length': response.headers.get('Content-Length', ''),
                    'Content-Disposition': response.headers.get('Content-Disposition', ''),
                    'Cache-Control': response.headers.get('Cache-Control', ''),
                    'Accept-Ranges': response.headers.get('Accept-Ranges', '')
                }

                content = await response.read()
                return content, response_headers

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
                    raise DifyAPIError(f"TTS failed: HTTP {response.status}", status_code=response.status)
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
        payload: Dict[str, Any] = {"score_threshold": score_threshold}
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
    logger.debug("[DifyClient] Dify client module loaded")
