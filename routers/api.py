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
    FrontendLogRequest,
    Messages,
    get_request_language
)

# Import async clients
from clients.dify import AsyncDifyClient
from clients.llm import qwen_client_generation, qwen_client_classification
from agents import main_agent as agent
from services.browser import BrowserContextManager
from services.llm_service import llm_service

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api", tags=["api"])

# ============================================================================
# SSE STREAMING - CRITICAL FOR 4,000+ CONCURRENT USERS
# ============================================================================

@router.post('/ai_assistant/stream')
async def ai_assistant_stream(req: AIAssistantRequest, x_language: str = None):
    """
    Stream AI assistant responses using Dify API with SSE (async version).
    
    This is the CRITICAL endpoint for supporting 100+ concurrent SSE connections.
    Uses AsyncDifyClient for non-blocking streaming.
    """
    
    # Get language for error messages
    lang = get_request_language(x_language)
    
    # Validate message
    message = req.message.strip()
    if not message:
        raise HTTPException(
            status_code=400,
            detail=Messages.error("message_required", lang)
        )
    
    # Get Dify configuration from environment
    api_key = os.getenv('DIFY_API_KEY')
    api_url = os.getenv('DIFY_API_URL', 'http://101.42.231.179/v1')
    timeout = int(os.getenv('DIFY_TIMEOUT', '30'))
    
    logger.debug(f"Dify Configuration - API URL: {api_url}, Has API Key: {bool(api_key)}, Timeout: {timeout}")
    
    if not api_key:
        logger.error("DIFY_API_KEY not configured in environment")
        raise HTTPException(
            status_code=500,
            detail=Messages.error("ai_not_configured", lang)
        )
    
    logger.debug(f"AI assistant request from user {req.user_id}: {message[:50]}...")
    
    async def generate():
        """Async generator function for SSE streaming"""
        logger.debug(f"[GENERATOR] Async generator function called - starting execution")
        try:
            logger.debug(f"[STREAM] Creating AsyncDifyClient with URL: {api_url}")
            client = AsyncDifyClient(api_key=api_key, api_url=api_url, timeout=timeout)
            logger.debug(f"[STREAM] AsyncDifyClient created successfully")
            
            logger.debug(f"[STREAM] Starting async stream_chat for message: {message[:50]}...")
            chunk_count = 0
            async for chunk in client.stream_chat(message, req.user_id, req.conversation_id):
                chunk_count += 1
                logger.debug(f"[STREAM] Received chunk {chunk_count}: {chunk.get('event', 'unknown')}")
                # Format as SSE
                yield f"data: {json.dumps(chunk)}\n\n"
            
            logger.debug(f"[STREAM] Streaming completed. Total chunks: {chunk_count}")
                
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
    
    logger.debug(f"[SETUP] Creating StreamingResponse with async generator")
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
async def generate_graph(req: GenerateRequest, x_language: str = None):
    """
    Generate graph specification from user prompt using selected LLM model (async).
    
    This endpoint returns JSON with the diagram specification for the frontend editor to render.
    For PNG file downloads, use /api/export_png instead.
    """
    
    # Get language for error messages
    lang = get_request_language(x_language)
    
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(
            status_code=400,
            detail=Messages.error("invalid_prompt", lang)
        )
    
    request_id = f"gen_{int(time.time()*1000)}"
    llm_model = req.llm.value if hasattr(req.llm, 'value') else str(req.llm)
    language = req.language.value if hasattr(req.language, 'value') else str(req.language)
    
    logger.debug(f"[{request_id}] Request: llm={llm_model!r}, language={language!r}, diagram_type={req.diagram_type}")
    
    if req.dimension_preference:
        logger.debug(f"[{request_id}] Dimension preference: {req.dimension_preference!r}")
    
    logger.debug(f"[{request_id}] Using LLM model: {llm_model!r}")
    
    try:
        # Generate diagram specification - fully async
        # Pass model directly through call chain (no global state)
        result = await agent.agent_graph_workflow_with_styles(
            prompt,
            language=language,
            forced_diagram_type=req.diagram_type.value if req.diagram_type else None,
            dimension_preference=req.dimension_preference,
            model=llm_model  # Pass model explicitly (fixes race condition)
        )
        
        logger.debug(f"[{request_id}] Generated {result.get('diagram_type', 'unknown')} diagram with {llm_model}")
        
        # Add metadata
        result['llm_model'] = llm_model
        result['request_id'] = request_id
        
        return result
        
    except Exception as e:
        logger.error(f"[{request_id}] Error generating graph: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=Messages.error("generation_failed", lang, str(e))
        )


# ============================================================================
# PNG EXPORT - BROWSER AUTOMATION
# ============================================================================

@router.post('/export_png')
async def export_png(req: ExportPNGRequest, x_language: str = None):
    """
    Export diagram as PNG using Playwright browser automation (async).
    
    This endpoint is already async-compatible (BrowserContextManager uses async_playwright).
    """
    
    # Get language for error messages
    lang = get_request_language(x_language)
    
    diagram_data = req.diagram_data
    diagram_type = req.diagram_type.value if hasattr(req.diagram_type, 'value') else str(req.diagram_type)
    
    if not diagram_data:
        raise HTTPException(
            status_code=400,
            detail=Messages.error("diagram_data_required", lang)
        )
    
    logger.debug(f"PNG export request - diagram_type: {diagram_type}, data keys: {list(diagram_data.keys())}")
    
    try:
        # Use async browser manager
        async with BrowserContextManager() as (browser, page):
            logger.debug("Browser context created successfully")
            
            # Navigate to editor page
            editor_url = f"http://localhost:{os.getenv('PORT', '5000')}/editor"
            await page.goto(editor_url, wait_until='networkidle', timeout=30000)
            
            logger.debug(f"Navigated to {editor_url}")
            
            # Inject diagram data and render
            await page.evaluate(f"""
                window.loadDiagramFromData({json.dumps(diagram_data)}, '{diagram_type}');
            """)
            
            # Wait for rendering to complete
            await asyncio.sleep(2)
            
            # Take screenshot
            screenshot_bytes = await page.screenshot(full_page=True)
            
            logger.debug(f"PNG generated successfully ({len(screenshot_bytes)} bytes)")
            
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
        raise HTTPException(
            status_code=500,
            detail=Messages.error("export_failed", lang, str(e))
        )


# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@router.post('/frontend_log')
async def frontend_log(req: FrontendLogRequest):
    """
    Log frontend messages to backend console.
    Receives logs from browser and displays them in Python terminal.
    """
    level_map = {
        'error': logging.ERROR,
        'warn': logging.WARNING,
        'info': logging.INFO,
        'debug': logging.DEBUG
    }
    level = level_map.get(req.level.lower(), logging.INFO)
    
    # Create a dedicated frontend logger with custom formatter
    frontend_logger = logging.getLogger('frontend')
    frontend_logger.setLevel(logging.DEBUG)  # Accept all levels
    
    # Log with clean formatting
    frontend_logger.log(level, req.message)
    
    return {'status': 'logged'}


@router.get('/llm/metrics')
async def get_llm_metrics(model: Optional[str] = None):
    """
    Get performance metrics for LLM models.
    
    Query Parameters:
        model (optional): Specific model name to get metrics for
        
    Returns:
        JSON with performance metrics including:
        - Total requests
        - Success/failure counts
        - Response times (avg, min, max)
        - Circuit breaker state
        - Recent errors
        
    Examples:
        GET /api/llm/metrics - Get metrics for all models
        GET /api/llm/metrics?model=qwen - Get metrics for specific model
    """
    try:
        metrics = llm_service.get_performance_metrics(model)
        
        return JSONResponse(
            content={
                'status': 'success',
                'metrics': metrics,
                'timestamp': int(time.time())
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting LLM metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve metrics: {str(e)}"
        )


@router.post('/generate_multi_parallel')
async def generate_multi_parallel(req: GenerateRequest, x_language: str = None):
    """
    Generate diagram using PARALLEL multi-LLM approach.
    
    Calls all specified LLMs in parallel and returns results as each completes.
    This is much faster than sequential calls!
    
    Benefits:
    - All LLMs called simultaneously (not one by one)
    - Results returned progressively as each LLM completes
    - Uses middleware for error handling, retries, and metrics
    - Circuit breaker protection
    - Performance tracking
    
    Request Body:
        {
            "prompt": "User's diagram description",
            "diagram_type": "bubble_map",
            "language": "zh",
            "models": ["qwen", "deepseek", "kimi", "hunyuan"],  // optional
            "dimension_preference": "optional dimension"
        }
    
    Returns:
        {
            "results": {
                "qwen": { "success": true, "spec": {...}, "duration": 1.2 },
                "deepseek": { "success": true, "spec": {...}, "duration": 1.5 },
                "kimi": { "success": false, "error": "...", "duration": 2.0 },
                "hunyuan": { "success": true, "spec": {...}, "duration": 1.8 }
            },
            "total_time": 2.1,  // Time for slowest model (parallel execution!)
            "success_count": 3,
            "first_successful": "qwen"
        }
    """
    lang = get_request_language(x_language)
    
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(
            status_code=400,
            detail=Messages.error("invalid_prompt", lang)
        )
    
    # Get models to use (default to all 4)
    models = req.models if hasattr(req, 'models') and req.models else ['qwen', 'deepseek', 'kimi', 'hunyuan']
    
    language = req.language.value if hasattr(req.language, 'value') else str(req.language)
    diagram_type = req.diagram_type.value if req.diagram_type and hasattr(req.diagram_type, 'value') else None
    
    logger.info(f"[generate_multi_parallel] Starting parallel generation with {len(models)} models")
    
    import time
    import asyncio
    start_time = time.time()
    results = {}
    first_successful = None
    
    try:
        # Create parallel tasks for each model using the AGENT
        # This ensures proper system prompts from prompts/thinking_maps.py are used
        async def generate_for_model(model: str):
            """Generate diagram for a single model using the full agent workflow."""
            model_start = time.time()
            try:
                # Call agent - this uses proper system prompts!
                spec_result = await agent.agent_graph_workflow_with_styles(
                    prompt,
                    language=language,
                    forced_diagram_type=diagram_type,
                    dimension_preference=req.dimension_preference if hasattr(req, 'dimension_preference') else None,
                    model=model
                )
                
                duration = time.time() - model_start
                
                # Check if agent actually succeeded (agent might return {"success": false, "error": "..."})
                if spec_result.get('success') is False or 'error' in spec_result:
                    error_msg = spec_result.get('error', 'Agent returned no spec')
                    logger.error(f"[generate_multi_parallel] {model} agent failed: {error_msg}")
                    return {
                        'model': model,
                        'success': False,
                        'error': error_msg,
                        'duration': duration
                    }
                
                return {
                    'model': model,
                    'success': True,
                    'spec': spec_result.get('spec'),
                    'diagram_type': spec_result.get('diagram_type'),
                    'topics': spec_result.get('topics', []),
                    'style_preferences': spec_result.get('style_preferences', {}),
                    'duration': duration,
                    'llm_model': model
                }
                
            except Exception as e:
                duration = time.time() - model_start
                logger.error(f"[generate_multi_parallel] {model} failed: {e}")
                return {
                    'model': model,
                    'success': False,
                    'error': str(e),
                    'duration': duration
                }
        
        # Run all models in PARALLEL using asyncio.gather
        tasks = [generate_for_model(model) for model in models]
        task_results = await asyncio.gather(*tasks)
        
        # Process results
        for task_result in task_results:
            model = task_result.pop('model')
            results[model] = task_result
            
            if task_result['success'] and first_successful is None:
                first_successful = model
                
            status = 'completed successfully' if task_result['success'] else 'failed'
            logger.debug(f"[generate_multi_parallel] {model} {status} in {task_result['duration']:.2f}s")
        
        total_time = time.time() - start_time
        success_count = sum(1 for r in results.values() if r['success'])
        
        logger.info(f"[generate_multi_parallel] Completed: {success_count}/{len(models)} successful in {total_time:.2f}s")
        
        return {
            'results': results,
            'total_time': total_time,
            'success_count': success_count,
            'first_successful': first_successful,
            'models_requested': models
        }
        
    except Exception as e:
        logger.error(f"[generate_multi_parallel] Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=Messages.error("generation_failed", lang, str(e))
        )


@router.get('/llm/health')
async def llm_health_check():
    """
    Health check for LLM service.
    
    Returns:
        JSON with service health status including:
        - Available models
        - Circuit breaker states
        - Rate limiter status
        
    Example:
        GET /api/llm/health
    """
    try:
        health_data = await llm_service.health_check()
        
        # Add circuit breaker states
        metrics = llm_service.get_performance_metrics()
        circuit_states = {
            model: data.get('circuit_state', 'closed')
            for model, data in metrics.items()
        }
        
        health_data['circuit_states'] = circuit_states
        
        return JSONResponse(
            content={
                'status': 'success',
                'health': health_data,
                'timestamp': int(time.time())
            }
        )
        
    except Exception as e:
        logger.error(f"LLM health check error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Health check failed: {str(e)}"
        )


@router.post('/generate_multi_progressive')
async def generate_multi_progressive(req: GenerateRequest, x_language: str = None):
    """
    Progressive parallel generation - send results as each LLM completes.
    
    Uses SSE (Server-Sent Events) to stream results progressively.
    Same pattern as /ai_assistant/stream and /thinking_mode/stream.
    
    Returns:
        SSE stream with events:
        - data: {"model": "qwen", "success": true, "spec": {...}, "duration": 8.05, ...}
        - data: {"model": "deepseek", "success": true, ...}
        - data: {"event": "complete", "total_time": 12.57}
    """
    # Get language for error messages (same pattern as line 59)
    lang = get_request_language(x_language)
    
    # Validate prompt (same pattern as lines 362-367)
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(
            status_code=400,
            detail=Messages.error("invalid_prompt", lang)
        )
    
    # Get models to use (same as line 370)
    models = req.models if hasattr(req, 'models') and req.models else ['qwen', 'deepseek', 'kimi', 'hunyuan']
    
    # Extract language and diagram_type (same as lines 372-373)
    language = req.language.value if hasattr(req.language, 'value') else str(req.language)
    diagram_type = req.diagram_type.value if req.diagram_type and hasattr(req.diagram_type, 'value') else None
    
    logger.info(f"[generate_multi_progressive] Starting progressive generation with {len(models)} models")
    
    start_time = time.time()
    
    async def generate():
        """Async generator for SSE streaming (same pattern as line 85)."""
        try:
            # IMPORTANT: Define generate_for_model as nested function (same as lines 386-431)
            async def generate_for_model(model: str):
                """Generate diagram for a single model using the full agent workflow."""
                model_start = time.time()
                try:
                    # Call agent (exact same call as line 391)
                    spec_result = await agent.agent_graph_workflow_with_styles(
                        prompt,
                        language=language,
                        forced_diagram_type=diagram_type,
                        dimension_preference=req.dimension_preference if hasattr(req, 'dimension_preference') else None,
                        model=model
                    )
                    
                    duration = time.time() - model_start
                    
                    # Check if agent actually succeeded (same logic as lines 402-410)
                    if spec_result.get('success') is False or 'error' in spec_result:
                        error_msg = spec_result.get('error', 'Agent returned no spec')
                        logger.error(f"[generate_multi_progressive] {model} agent failed: {error_msg}")
                        return {
                            'model': model,
                            'success': False,
                            'error': error_msg,
                            'duration': duration
                        }
                    
                    # Success case (same structure as lines 412-421)
                    return {
                        'model': model,
                        'success': True,
                        'spec': spec_result.get('spec'),
                        'diagram_type': spec_result.get('diagram_type'),
                        'topics': spec_result.get('topics', []),
                        'style_preferences': spec_result.get('style_preferences', {}),
                        'duration': duration,
                        'llm_model': model
                    }
                    
                except Exception as e:
                    duration = time.time() - model_start
                    logger.error(f"[generate_multi_progressive] {model} failed: {e}")
                    return {
                        'model': model,
                        'success': False,
                        'error': str(e),
                        'duration': duration
                    }
            
            # Create parallel tasks (same as line 434)
            tasks = [generate_for_model(model) for model in models]
            
            # ⭐ KEY CHANGE: Use asyncio.as_completed instead of gather
            # This yields results as each completes, not waiting for all
            for coro in asyncio.as_completed(tasks):
                result = await coro
                
                # Send SSE event for this model (same format as line 99)
                logger.debug(f"[generate_multi_progressive] Sending {result['model']} result")
                yield f"data: {json.dumps(result)}\n\n"
            
            # Send completion event
            total_time = time.time() - start_time
            logger.info(f"[generate_multi_progressive] All models completed in {total_time:.2f}s")
            yield f"data: {json.dumps({'event': 'complete', 'total_time': total_time})}\n\n"
            
        except Exception as e:
            logger.error(f"[generate_multi_progressive] Error: {e}", exc_info=True)
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"
    
    # Return SSE stream (same pattern as lines 116-124)
    return StreamingResponse(
        generate(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


# Only log from main worker to avoid duplicate messages
import os
if os.getenv('UVICORN_WORKER_ID') is None or os.getenv('UVICORN_WORKER_ID') == '0':
    logger.info("API router loaded successfully")

