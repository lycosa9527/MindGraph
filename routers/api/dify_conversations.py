"""
Dify Conversation Management API Router
========================================

API endpoints for managing Dify conversations:
- GET /api/dify/conversations - List user's conversations
- DELETE /api/dify/conversations/{id} - Delete a conversation
- POST /api/dify/conversations/{id}/name - Rename/auto-generate title
- GET /api/dify/conversations/{id}/messages - Get conversation messages

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from models.auth import User
from utils.auth import get_current_user
from clients.dify import AsyncDifyClient

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])


def get_dify_user_id(user: User) -> str:
    """Generate consistent Dify user ID from MindGraph user"""
    return f"mg_user_{user.id}"


def get_dify_client() -> AsyncDifyClient:
    """Get configured Dify client"""
    api_key = os.getenv('DIFY_API_KEY')
    api_url = os.getenv('DIFY_API_URL', 'http://101.42.231.179/v1')
    timeout = int(os.getenv('DIFY_TIMEOUT', '30'))
    
    if not api_key:
        raise HTTPException(status_code=500, detail="AI service not configured")
    
    return AsyncDifyClient(api_key=api_key, api_url=api_url, timeout=timeout)


class RenameRequest(BaseModel):
    """Request body for renaming a conversation"""
    name: Optional[str] = None
    auto_generate: bool = False


class FeedbackRequest(BaseModel):
    """Request body for message feedback (like/dislike)"""
    rating: Optional[str] = None  # "like", "dislike", or null to clear
    content: Optional[str] = None  # Optional feedback text


@router.get('/dify/conversations')
async def list_conversations(
    last_id: Optional[str] = Query(None, description="Last conversation ID for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Number of conversations to return"),
    current_user: User = Depends(get_current_user)
):
    """
    List user's conversations from Dify.
    
    Returns conversations sorted by updated_at (newest first).
    Each conversation includes:
    - id: Conversation ID
    - name: Auto-generated or custom title
    - created_at: Creation timestamp
    - updated_at: Last activity timestamp
    """
    try:
        client = get_dify_client()
        dify_user_id = get_dify_user_id(current_user)
        
        result = await client.get_conversations(
            user_id=dify_user_id,
            last_id=last_id,
            limit=limit,
            sort_by="-updated_at"
        )
        
        logger.debug(f"Fetched {len(result.get('data', []))} conversations for user {current_user.id}")
        
        return {
            "success": True,
            "data": result.get("data", []),
            "has_more": result.get("has_more", False),
            "limit": result.get("limit", limit)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch conversations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete('/dify/conversations/{conversation_id}')
async def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Delete a conversation from Dify.
    
    This permanently removes the conversation and all its messages.
    """
    try:
        client = get_dify_client()
        dify_user_id = get_dify_user_id(current_user)
        
        await client.delete_conversation(
            conversation_id=conversation_id,
            user_id=dify_user_id
        )
        
        logger.info(f"Deleted conversation {conversation_id} for user {current_user.id}")
        
        return {"success": True, "message": "Conversation deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/dify/conversations/{conversation_id}/name')
async def rename_conversation(
    conversation_id: str,
    request: RenameRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Rename a conversation or auto-generate a title.
    
    If auto_generate is True, Dify will generate a title based on conversation content.
    Otherwise, use the provided name.
    """
    try:
        client = get_dify_client()
        dify_user_id = get_dify_user_id(current_user)
        
        result = await client.rename_conversation(
            conversation_id=conversation_id,
            user_id=dify_user_id,
            name=request.name,
            auto_generate=request.auto_generate
        )
        
        logger.info(f"Renamed conversation {conversation_id} for user {current_user.id}")
        
        return {
            "success": True,
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to rename conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/dify/conversations/{conversation_id}/messages')
async def get_conversation_messages(
    conversation_id: str,
    first_id: Optional[str] = Query(None, description="First message ID for pagination"),
    limit: int = Query(20, ge=1, le=100, description="Number of messages to return"),
    current_user: User = Depends(get_current_user)
):
    """
    Get messages for a specific conversation.
    
    Returns messages in chronological order.
    Each message includes:
    - id: Message ID
    - role: 'user' or 'assistant'
    - content: Message text
    - created_at: Timestamp
    """
    try:
        client = get_dify_client()
        dify_user_id = get_dify_user_id(current_user)
        
        result = await client.get_messages(
            conversation_id=conversation_id,
            user_id=dify_user_id,
            first_id=first_id,
            limit=limit
        )
        
        logger.debug(f"Fetched {len(result.get('data', []))} messages for conversation {conversation_id}")
        
        return {
            "success": True,
            "data": result.get("data", []),
            "has_more": result.get("has_more", False),
            "limit": result.get("limit", limit)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/dify/user-id')
async def get_user_dify_id(
    current_user: User = Depends(get_current_user)
):
    """
    Get the Dify user ID for the current MindGraph user.
    
    This is useful for the frontend to know which user ID to use
    when communicating directly with Dify.
    """
    return {
        "success": True,
        "dify_user_id": get_dify_user_id(current_user),
        "mindgraph_user_id": current_user.id
    }


@router.post('/dify/messages/{message_id}/feedback')
async def submit_message_feedback(
    message_id: str,
    request: FeedbackRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Submit feedback (like/dislike) for a specific message.
    
    Args:
        message_id: The Dify message ID to provide feedback for
        request: FeedbackRequest with rating ("like", "dislike", or null) and optional content
    
    Returns:
        Success response with feedback result
    """
    try:
        client = get_dify_client()
        dify_user_id = get_dify_user_id(current_user)
        
        result = await client.message_feedback(
            message_id=message_id,
            user_id=dify_user_id,
            rating=request.rating,
            content=request.content
        )
        
        logger.info(f"User {current_user.id} submitted {request.rating} feedback for message {message_id}")
        
        return {
            "success": True,
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit message feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))
