"""
FastAPI API Routes for MindGraph Application
==============================================

Async versions of diagram generation, PNG export, and SSE streaming endpoints.

@author lycosa9527
@made_by MindSpring Team

Migration Status: Phase 2.2 - FastAPI API Routes
"""

import json
import logging
import os
import time
import asyncio
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse, JSONResponse

# Import Pydantic models
from models import (
    AIAssistantRequest,
    GenerateRequest,
    GenerateResponse,
    ExportPNGRequest,
    FrontendLogRequest
)

# Import async clients
from clients.dify import AsyncDifyClient
from clients.llm import qwen_client_generation, qwen_client_classification
from agents import main_agent as agent
from services.browser import BrowserContextManager

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api", tags=["api"])

# ============================================================================
# SSE STREAMING - CRITICAL FOR 4,000+ CONCURRENT USERS
# ============================================================================

@router.post('/ai_assistant/stream')
async def ai_assistant_stream(req: AIAssistantRequest):
    """
    Stream AI assistant responses using Dify API with SSE (async version).
    
    This is the CRITICAL endpoint for supporting 100+ concurrent SSE connections.
    Uses AsyncDifyClient for non-blocking streaming.
    """
    
    # Validate message
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")
    
    # Get Dify configuration from environment
    api_key = os.getenv('DIFY_API_KEY')
    api_url = os.getenv('DIFY_API_URL', 'http://101.42.231.179/v1')
    timeout = int(os.getenv('DIFY_TIMEOUT', '30'))
    
    logger.info(f"Dify Configuration - API URL: {api_url}, Has API Key: {bool(api_key)}, Timeout: {timeout}")
    
    if not api_key:
        logger.error("DIFY_API_KEY not configured in environment")
        raise HTTPException(status_code=500, detail="AI assistant not configured")
    
    logger.info(f"AI assistant request from user {req.user_id}: {message[:50]}...")
    
    async def generate():
        """Async generator function for SSE streaming"""
        logger.info(f"[GENERATOR] Async generator function called - starting execution")
        try:
            logger.info(f"[STREAM] Creating AsyncDifyClient with URL: {api_url}")
            client = AsyncDifyClient(api_key=api_key, api_url=api_url, timeout=timeout)
            logger.info(f"[STREAM] AsyncDifyClient created successfully")
            
            logger.info(f"[STREAM] Starting async stream_chat for message: {message[:50]}...")
            chunk_count = 0
            async for chunk in client.stream_chat(message, req.user_id, req.conversation_id):
                chunk_count += 1
                logger.debug(f"[STREAM] Received chunk {chunk_count}: {chunk.get('event', 'unknown')}")
                # Format as SSE
                yield f"data: {json.dumps(chunk)}\n\n"
            
            logger.info(f"[STREAM] Streaming completed. Total chunks: {chunk_count}")
                
        except Exception as e:
            logger.error(f"[STREAM] AI assistant streaming error: {e}", exc_info=True)
            import traceback
            logger.error(f"[STREAM] Full traceback: {traceback.format_exc()}")
            error_data = {
                'event': 'error',
                'error': str(e),
                'error_type': type(e).__name__,
                'timestamp': int(time.time() * 1000)
            }
            yield f"data: {json.dumps(error_data)}\n\n"
    
    logger.info(f"[SETUP] Creating StreamingResponse with async generator")
    return StreamingResponse(
        generate(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


# ============================================================================
# DIAGRAM GENERATION - MAIN ENDPOINT
# ============================================================================

@router.post('/generate_graph', response_model=GenerateResponse)
async def generate_graph(req: GenerateRequest):
    """
    Generate graph specification from user prompt using selected LLM model (async).
    
    This endpoint returns JSON with the diagram specification for the frontend editor to render.
    For PNG file downloads, use /api/export_png instead.
    """
    
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Invalid or empty prompt")
    
    request_id = f"gen_{int(time.time()*1000)}"
    llm_model = req.llm.value if hasattr(req.llm, 'value') else str(req.llm)
    language = req.language.value if hasattr(req.language, 'value') else str(req.language)
    
    logger.info(f"[{request_id}] Request: llm={llm_model!r}, language={language!r}, diagram_type={req.diagram_type}")
    
    if req.dimension_preference:
        logger.info(f"[{request_id}] Dimension preference: {req.dimension_preference!r}")
    
    # Set the LLM model for this request
    # TODO: Make this thread-safe or use dependency injection
    agent.set_llm_model(llm_model)
    current_model = agent.get_llm_model()
    logger.info(f"[{request_id}] Set agent LLM model to: {current_model!r}")
    
    try:
        # Generate diagram specification using thread pool to unblock event loop
        # NOTE: agent.generate_graph_spec_with_styles() is sync - running in thread pool
        result = await asyncio.to_thread(
            agent.generate_graph_spec_with_styles,
            prompt,
            language=language,
            forced_diagram_type=req.diagram_type.value if req.diagram_type else None,
            dimension_preference=req.dimension_preference
        )
        
        logger.info(f"[{request_id}] Generated {result.get('diagram_type', 'unknown')} diagram")
        
        # Add metadata
        result['llm_model'] = current_model
        result['request_id'] = request_id
        
        return result
        
    except Exception as e:
        logger.error(f"[{request_id}] Error generating graph: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate graph: {str(e)}")


# ============================================================================
# PNG EXPORT - BROWSER AUTOMATION
# ============================================================================

@router.post('/export_png')
async def export_png(req: ExportPNGRequest):
    """
    Export diagram as PNG using Playwright browser automation (async).
    
    This endpoint is already async-compatible (BrowserContextManager uses async_playwright).
    """
    
    diagram_data = req.diagram_data
    diagram_type = req.diagram_type.value if hasattr(req.diagram_type, 'value') else str(req.diagram_type)
    
    if not diagram_data:
        raise HTTPException(status_code=400, detail="Diagram data is required")
    
    logger.info(f"PNG export request - diagram_type: {diagram_type}, data keys: {list(diagram_data.keys())}")
    
    try:
        # Use async browser manager
        async with BrowserContextManager() as (browser, page):
            logger.info("Browser context created successfully")
            
            # Navigate to editor page
            editor_url = f"http://localhost:{os.getenv('PORT', '5000')}/editor"
            await page.goto(editor_url, wait_until='networkidle', timeout=30000)
            
            logger.info(f"Navigated to {editor_url}")
            
            # Inject diagram data and render
            await page.evaluate(f"""
                window.loadDiagramFromData({json.dumps(diagram_data)}, '{diagram_type}');
            """)
            
            # Wait for rendering to complete
            await asyncio.sleep(2)
            
            # Take screenshot
            screenshot_bytes = await page.screenshot(full_page=True)
            
            logger.info(f"PNG generated successfully ({len(screenshot_bytes)} bytes)")
            
            # Return PNG as response
            from fastapi.responses import Response
            return Response(
                content=screenshot_bytes,
                media_type="image/png",
                headers={
                    'Content-Disposition': 'attachment; filename="diagram.png"'
                }
            )
            
    except Exception as e:
        logger.error(f"PNG export error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PNG export failed: {str(e)}")


# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@router.post('/frontend_log')
async def frontend_log(req: FrontendLogRequest):
    """Log frontend messages to backend console"""
    level_map = {
        'error': logging.ERROR,
        'warn': logging.WARNING,
        'info': logging.INFO,
        'debug': logging.DEBUG
    }
    level = level_map.get(req.level.lower(), logging.INFO)
    logger.log(level, f"[FRONTEND] {req.message}")
    return {'status': 'logged'}


logger.info("API router loaded successfully - SSE, diagram generation, PNG export")

