"""
LLM Operations API Router
==========================

API endpoints for LLM service operations:
- /api/llm/metrics: Get performance metrics for LLM models
- /api/llm/health: Health check for LLM service
- /api/generate_multi_parallel: Parallel multi-LLM generation
- /api/generate_multi_progressive: Progressive multi-LLM generation with SSE

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Optional
import asyncio
import json
import logging
import time

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse, StreamingResponse

from agents.core.workflow import agent_graph_workflow_with_styles
from models import GenerateRequest, LLMHealthResponse, Messages, get_request_language
from models.domain.auth import User
from services.llm import llm_service
from utils.auth import get_current_user, get_current_user_or_api_key


logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])


@router.get('/llm/metrics')
async def get_llm_metrics(
    model: Optional[str] = None,
    _current_user: User = Depends(get_current_user)
):
    """
    Get performance metrics for LLM models.

    Requires authentication to prevent information leakage about system internals.

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
        logger.error("Error getting LLM metrics: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve metrics: {str(e)}"
        ) from e


@router.get('/llm/health', response_model=LLMHealthResponse)
async def llm_health_check(
    _current_user: User = Depends(get_current_user)
):
    """
    Health check for LLM service.

    Requires authentication to prevent information leakage about system internals.

    Returns:
        JSON with service health status including:
        - Available models
        - Circuit breaker states
        - Rate limiter status

    HTTP Status Codes:
        - 200 OK: All models healthy
        - 503 Service Unavailable: Some models unhealthy (degraded state)
        - 500 Internal Server Error: Health check itself failed

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

        # Check if any models are unhealthy
        available_models = health_data.get('available_models', [])
        unhealthy_count = sum(
            1 for model in available_models
            if model in health_data
            and health_data[model].get('status') != 'healthy'
        )

        response_data = {
            'status': 'success',
            'health': health_data,
            'timestamp': int(time.time())
        }

        # Return appropriate HTTP status code based on health
        if unhealthy_count == 0:
            status_code = 200  # All healthy
        else:
            status_code = 503  # Degraded (some unhealthy)
            response_data['degraded'] = True
            response_data['unhealthy_count'] = unhealthy_count
            response_data['total_models'] = len(available_models)
            response_data['healthy_count'] = len(available_models) - unhealthy_count

        return JSONResponse(
            content=response_data,
            status_code=status_code
        )

    except Exception as e:
        logger.error("LLM health check error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Health check failed: {str(e)}"
        ) from e


@router.post('/generate_multi_parallel')
async def generate_multi_parallel(
    req: GenerateRequest,
    x_language: Optional[str] = None,
    _current_user: Optional[User] = Depends(get_current_user_or_api_key)
):
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
            "models": ["qwen", "deepseek", "kimi", "doubao"],  // optional
            "dimension_preference": "optional dimension"
        }

    Returns:
        {
            "results": {
                "qwen": { "success": true, "spec": {...}, "duration": 1.2 },
                "deepseek": { "success": true, "spec": {...}, "duration": 1.5 },
                "kimi": { "success": false, "error": "...", "duration": 2.0 },
                "doubao": { "success": true, "spec": {...}, "duration": 1.8 }
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

    # Get models to use (default to all 4, Hunyuan disabled due to 5 concurrent limit)
    models = req.models if hasattr(req, 'models') and req.models else ['qwen', 'deepseek', 'kimi', 'doubao']

    language = req.language.value if hasattr(req.language, 'value') else str(req.language)
    diagram_type = req.diagram_type.value if req.diagram_type and hasattr(req.diagram_type, 'value') else None

    logger.debug("[generate_multi_parallel] Starting parallel generation with %d models", len(models))

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
                spec_result = await agent_graph_workflow_with_styles(
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
                    logger.error("[generate_multi_parallel] %s agent failed: %s", model, error_msg)
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
                logger.error("[generate_multi_parallel] %s failed: %s", model, e)
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
            logger.debug(
                "[generate_multi_parallel] %s %s in %.2fs",
                model, status, task_result['duration']
            )

        total_time = time.time() - start_time
        success_count = sum(1 for r in results.values() if r['success'])

        logger.info(
            "[generate_multi_parallel] Completed: %d/%d successful in %.2fs",
            success_count, len(models), total_time
        )

        return {
            'results': results,
            'total_time': total_time,
            'success_count': success_count,
            'first_successful': first_successful,
            'models_requested': models
        }

    except Exception as e:
        logger.error("[generate_multi_parallel] Error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=Messages.error("generation_failed", lang, str(e))
        ) from e


@router.post('/generate_multi_progressive')
async def generate_multi_progressive(
    req: GenerateRequest,
    x_language: Optional[str] = None,
    _current_user: Optional[User] = Depends(get_current_user_or_api_key)
):
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
    # Get language for error messages
    lang = get_request_language(x_language)

    # Validate prompt
    prompt = req.prompt.strip()
    if not prompt:
        raise HTTPException(
            status_code=400,
            detail=Messages.error("invalid_prompt", lang)
        )

    # Get models to use (Hunyuan disabled due to 5 concurrent limit)
    models = req.models if hasattr(req, 'models') and req.models else ['qwen', 'deepseek', 'kimi', 'doubao']

    # Extract language and diagram_type
    language = req.language.value if hasattr(req.language, 'value') else str(req.language)
    diagram_type = req.diagram_type.value if req.diagram_type and hasattr(req.diagram_type, 'value') else None

    logger.debug(
        "[generate_multi_progressive] Starting progressive generation with %d models",
        len(models)
    )

    start_time = time.time()

    async def generate():
        """Async generator for SSE streaming."""
        try:
            # Define generate_for_model as nested function
            async def generate_for_model(model: str):
                """Generate diagram for a single model using the full agent workflow."""
                model_start = time.time()
                try:
                    # Call agent
                    spec_result = await agent_graph_workflow_with_styles(
                        prompt,
                        language=language,
                        forced_diagram_type=diagram_type,
                        dimension_preference=req.dimension_preference if hasattr(req, 'dimension_preference') else None,
                        model=model
                    )

                    duration = time.time() - model_start

                    # Check if agent actually succeeded
                    if spec_result.get('success') is False or 'error' in spec_result:
                        error_msg = spec_result.get('error', 'Agent returned no spec')
                        logger.error(
                            "[generate_multi_progressive] %s agent failed: %s",
                            model, error_msg
                        )
                        return {
                            'model': model,
                            'success': False,
                            'error': error_msg,
                            'duration': duration
                        }

                    # Success case
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
                    logger.error("[generate_multi_progressive] %s failed: %s", model, e)
                    return {
                        'model': model,
                        'success': False,
                        'error': str(e),
                        'duration': duration
                    }

            # Create parallel tasks
            tasks = [generate_for_model(model) for model in models]

            # Use asyncio.as_completed instead of gather
            # This yields results as each completes, not waiting for all
            for coro in asyncio.as_completed(tasks):
                result = await coro

                # Send SSE event for this model
                logger.debug("[generate_multi_progressive] Sending %s result", result['model'])
                yield f"data: {json.dumps(result)}\n\n"

            # Send completion event
            total_time = time.time() - start_time
            logger.info(
                "[generate_multi_progressive] All models completed in %.2fs", total_time
            )
            yield f"data: {json.dumps({'event': 'complete', 'total_time': total_time})}\n\n"

        except Exception as e:
            logger.error("[generate_multi_progressive] Error: %s", e, exc_info=True)
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"

    # Return SSE stream
    return StreamingResponse(
        generate(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )
