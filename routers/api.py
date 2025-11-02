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
import uuid
from pathlib import Path
import aiofiles
import httpx
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.responses import StreamingResponse, JSONResponse, Response, PlainTextResponse, FileResponse

# Import Pydantic models
from models import (
    AIAssistantRequest,
    GenerateRequest,
    GenerateResponse,
    ExportPNGRequest,
    GeneratePNGRequest,
    GenerateDingTalkRequest,
    FrontendLogRequest,
    FrontendLogBatchRequest,
    RecalculateLayoutRequest,
    FeedbackRequest,
    Messages,
    get_request_language
)

# Import async clients
from clients.dify import AsyncDifyClient
from clients.llm import qwen_client_generation, qwen_client_classification
from agents import main_agent as agent
from services.browser import BrowserContextManager
from services.llm_service import llm_service

# Import authentication
from models.auth import User
from utils.auth import get_current_user_or_api_key
from config.database import get_db
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api", tags=["api"])

# ============================================================================
# SSE STREAMING - CRITICAL FOR 4,000+ CONCURRENT USERS
# ============================================================================

@router.post('/ai_assistant/stream')
async def ai_assistant_stream(
    req: AIAssistantRequest,
    x_language: str = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key)
):
    """
    Stream AI assistant responses using Dify API with SSE (async version).
    
    This is the CRITICAL endpoint for supporting 100+ concurrent SSE connections.
    Uses AsyncDifyClient for non-blocking streaming.
    """
    
    # Get language for error messages
    lang = get_request_language(x_language)
    
    # Get message
    message = req.message.strip()
    
    # Handle Dify conversation opener trigger
    # When message is "start" with no conversation_id, this triggers Dify's opener
    if message.lower() == 'start' and not req.conversation_id:
        logger.info(f"[MindMate] Conversation opener triggered for user {req.user_id}")
        logger.debug("[MindMate] Dify will respond with configured opening message")
    
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
async def generate_graph(
    req: GenerateRequest,
    x_language: str = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key)
):
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
        # Pass user context for token tracking
        user_id = current_user.id if current_user else None
        organization_id = current_user.organization_id if current_user else None
        
        # Determine request type for token tracking (default to 'diagram_generation')
        request_type = req.request_type if req.request_type else 'diagram_generation'
        
        result = await agent.agent_graph_workflow_with_styles(
            prompt,
            language=language,
            forced_diagram_type=req.diagram_type.value if req.diagram_type else None,
            dimension_preference=req.dimension_preference,
            model=llm_model,  # Pass model explicitly (fixes race condition)
            # Token tracking parameters
            user_id=user_id,
            organization_id=organization_id,
            request_type=request_type,
            endpoint_path='/api/generate_graph'
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
async def export_png(
    req: ExportPNGRequest,
    x_language: str = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key)
):
    """
    Export diagram as PNG using Playwright browser automation (async).
    
    This is a STANDALONE endpoint - takes diagram data and renders PNG.
    Creates minimal HTML dynamically in headless browser with D3.js and renderers.
    No dependency on any existing pages or routes.
    
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
    
    # VERBOSE LOGGING: Complete diagram data from LLM
    logger.info("="*80)
    logger.info("VERBOSE PNG EXPORT - Complete Diagram Data:")
    logger.info(f"Diagram Type: {diagram_type}")
    logger.info(f"Diagram Data Keys: {list(diagram_data.keys())}")
    logger.info("Complete Diagram Data JSON:")
    logger.info(json.dumps(diagram_data, indent=2, ensure_ascii=False))
    
    # Check specific important fields
    if 'topic' in diagram_data:
        logger.info(f"Topic: {diagram_data['topic']}")
    if 'attributes' in diagram_data:
        logger.info(f"Number of attributes: {len(diagram_data['attributes'])}")
        for i, attr in enumerate(diagram_data.get('attributes', [])):
            logger.info(f"  Attribute {i}: {attr}")
    if 'nodes' in diagram_data:
        logger.info(f"Number of nodes: {len(diagram_data['nodes'])}")
        for i, node in enumerate(diagram_data.get('nodes', [])):
            logger.info(f"  Node {i}: {node}")
    if '_layout' in diagram_data:
        logger.info(f"Layout info: {diagram_data['_layout']}")
    if '_recommended_dimensions' in diagram_data:
        logger.info(f"Recommended dimensions: {diagram_data['_recommended_dimensions']}")
    if '_metadata' in diagram_data:
        logger.info(f"Metadata: {diagram_data['_metadata']}")
    
    logger.info(f"Request width: {req.width}, height: {req.height}, scale: {req.scale}")
    logger.info("="*80)
    
    try:
        # Use async browser manager
        async with BrowserContextManager() as context:
            page = await context.new_page()
            logger.debug("Browser context created successfully")
            
            # Get server URL
            port = os.getenv('PORT', '5000')
            base_url = f"http://localhost:{port}"
            
            logger.info(f"Creating HTML with base_url: {base_url}")
            logger.info(f"Container dimensions: {req.width or 1200}x{req.height or 800}")
            
            # Create minimal HTML page with rendering infrastructure
            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <script src="{base_url}/static/js/d3.min.js"></script>
</head>
<body>
    <div id="d3-container" style="width: {req.width or 1200}px; height: {req.height or 800}px;"></div>
    <script>
        window.renderingComplete = false;
        window.renderingError = null;
        
        // Load theme config, style manager, logger, and renderer
        const scripts = [
            '{base_url}/static/js/theme-config.js',
            '{base_url}/static/js/style-manager.js',
            '{base_url}/static/js/logger.js',
            '{base_url}/static/js/renderers/shared-utilities.js',
            '{base_url}/static/js/renderers/renderer-dispatcher.js'
        ];
        
        // Add diagram-specific renderer
        const rendererMap = {{
            // Thinking Maps
            'bubble_map': 'bubble-map-renderer.js',
            'double_bubble_map': 'bubble-map-renderer.js',
            'circle_map': 'bubble-map-renderer.js',
            'tree_map': 'tree-renderer.js',
            'flow_map': 'flow-renderer.js',
            'multi_flow_map': 'flow-renderer.js',
            'brace_map': 'brace-renderer.js',
            'bridge_map': 'flow-renderer.js',
            'flowchart': 'flow-renderer.js',
            // Mind Maps & Concept Maps
            'mindmap': 'mind-map-renderer.js',
            'mind_map': 'mind-map-renderer.js',
            'concept_map': 'concept-map-renderer.js'
        }};
        
        const diagramType = '{diagram_type}';
        if (rendererMap[diagramType]) {{
            scripts.push('{base_url}/static/js/renderers/' + rendererMap[diagramType]);
        }}
        
        // Load scripts sequentially
        async function loadScripts() {{
            for (const src of scripts) {{
                await new Promise((resolve, reject) => {{
                    const script = document.createElement('script');
                    script.src = src;
                    script.onload = () => {{
                        console.log('Loaded:', src);
                        resolve();
                    }};
                    script.onerror = (err) => {{
                        console.error('Failed to load:', src);
                        reject(err);
                    }};
                    document.head.appendChild(script);
                }});
                // Small delay between scripts to ensure execution
                await new Promise(resolve => setTimeout(resolve, 100));
            }}
        }}
        
        // Render diagram after scripts load
        loadScripts()
            .then(() => {{
                console.log('All scripts loaded, starting render...');
                console.log('renderGraph available:', typeof renderGraph);
                
                const diagramData = {json.dumps(diagram_data)};
                console.log('='.repeat(80));
                console.log('VERBOSE: Complete Diagram Data in Browser:');
                console.log('Diagram type:', '{diagram_type}');
                console.log('Diagram data keys:', Object.keys(diagramData));
                console.log('Topic:', diagramData.topic);
                if (diagramData.attributes) {{
                    console.log('Attributes count:', diagramData.attributes.length);
                    diagramData.attributes.forEach((attr, i) => {{
                        console.log(`  Attribute ${{i}}:`, attr);
                    }});
                }}
                if (diagramData.nodes) {{
                    console.log('Nodes count:', diagramData.nodes.length);
                    diagramData.nodes.forEach((node, i) => {{
                        console.log(`  Node ${{i}}:`, node);
                    }});
                }}
                console.log('Layout:', diagramData._layout);
                console.log('Recommended dimensions:', diagramData._recommended_dimensions);
                console.log('Metadata:', diagramData._metadata);
                console.log('='.repeat(80));
                
                if (typeof renderGraph !== 'function') {{
                    throw new Error('renderGraph function not available');
                }}
                
                // Render the diagram (may be async)
                console.log('Calling renderGraph with:');
                console.log('  - Type:', '{diagram_type}');
                console.log('  - Data:', diagramData);
                console.log('  - Theme:', null);
                console.log('  - Dimensions:', null);
                
                const renderResult = renderGraph('{diagram_type}', diagramData, null, null);
                console.log('renderGraph returned:', renderResult);
                console.log('Return value type:', typeof renderResult);
                console.log('Is promise?', renderResult && typeof renderResult.then === 'function');
                
                // Check if result is a promise
                if (renderResult && typeof renderResult.then === 'function') {{
                    console.log('renderGraph returned a promise, waiting...');
                    renderResult.then(() => {{
                        checkRendering();
                    }}).catch(err => {{
                        console.error('renderGraph promise rejected:', err);
                        window.renderingError = err.toString();
                        window.renderingComplete = true;
                    }});
                }} else {{
                    // Not a promise, wait a bit and check
                    console.log('renderGraph did not return a promise, waiting 2s...');
                    setTimeout(checkRendering, 2000);
                }}
                
                function checkRendering() {{
                    console.log('='.repeat(80));
                    console.log('CHECKING RENDERING RESULTS:');
                    const container = document.getElementById('d3-container');
                    console.log('Container found:', !!container);
                    
                    if (container) {{
                        console.log('Container dimensions:', container.offsetWidth, 'x', container.offsetHeight);
                        console.log('Container innerHTML length:', container.innerHTML.length);
                        console.log('Container children count:', container.children.length);
                        
                        const svg = container.querySelector('svg');
                        console.log('SVG found:', !!svg);
                        
                        if (svg) {{
                            console.log('SVG dimensions:', svg.getAttribute('width'), 'x', svg.getAttribute('height'));
                            console.log('SVG viewBox:', svg.getAttribute('viewBox'));
                            console.log('SVG children count:', svg.children.length);
                            console.log('SVG child tags:', Array.from(svg.children).map(c => c.tagName).join(', '));
                            
                            // Check for specific elements
                            const circles = svg.querySelectorAll('circle');
                            const rects = svg.querySelectorAll('rect');
                            const texts = svg.querySelectorAll('text');
                            const paths = svg.querySelectorAll('path');
                            console.log('SVG elements - circles:', circles.length, 'rects:', rects.length, 'texts:', texts.length, 'paths:', paths.length);
                            
                            // Add watermark to exported PNG
                            console.log('Adding watermark...');
                            if (typeof addWatermark === 'function' && typeof d3 !== 'undefined') {{
                                try {{
                                    const svgD3 = d3.select(svg);
                                    addWatermark(svgD3, null);
                                    console.log('Watermark added successfully');
                                }} catch (err) {{
                                    console.error('Error adding watermark:', err);
                                }}
                            }} else {{
                                console.warn('addWatermark or d3 not available - watermark skipped');
                            }}
                        }} else {{
                            console.log('NO SVG FOUND!');
                            console.log('Container innerHTML (first 500 chars):', container.innerHTML.substring(0, 500));
                            console.log('Container children:', Array.from(container.children).map(c => c.tagName).join(', '));
                        }}
                    }} else {{
                        console.log('NO CONTAINER FOUND!');
                    }}
                    console.log('='.repeat(80));
                    window.renderingComplete = true;
                }}
            }})
            .catch(err => {{
                console.error('Rendering error:', err);
                window.renderingError = err.toString();
                window.renderingComplete = true;
            }});
    </script>
</body>
</html>
            """
            
            # Set page content
            logger.info("Setting page content...")
            logger.debug(f"HTML content length: {len(html_content)} characters")
            await page.set_content(html_content)
            logger.info("Page content set successfully")
            
            # Capture console logs for debugging
            page.on("console", lambda msg: logger.debug(f"[Browser Console] {msg.type}: {msg.text}"))
            
            # Wait for rendering to complete by polling the flag
            max_wait = 10  # seconds
            waited = 0
            while waited < max_wait:
                rendering_complete = await page.evaluate("window.renderingComplete")
                if rendering_complete:
                    break
                await asyncio.sleep(0.5)
                waited += 0.5
            
            # Check if there was an error
            rendering_error = await page.evaluate("window.renderingError")
            if rendering_error:
                logger.error(f"Rendering error in browser: {rendering_error}")
                raise Exception(f"Browser rendering failed: {rendering_error}")
            
            # Verify SVG was created
            svg_exists = await page.evaluate("!!document.querySelector('#d3-container svg')")
            logger.info(f"SVG exists check: {svg_exists}")
            
            if not svg_exists:
                logger.error("="*80)
                logger.error("NO SVG ELEMENT FOUND!")
                
                # Get detailed info from browser
                container_info = await page.evaluate("""
                    (() => {
                        const container = document.getElementById('d3-container');
                        return {
                            found: !!container,
                            innerHTML: container ? container.innerHTML : null,
                            childCount: container ? container.children.length : 0,
                            children: container ? Array.from(container.children).map(c => c.tagName) : []
                        };
                    })()
                """)
                logger.error(f"Container info: {json.dumps(container_info, indent=2)}")
                
                # Get page HTML for debugging
                page_html = await page.content()
                logger.error(f"Full page HTML length: {len(page_html)}")
                logger.error(f"Page HTML (first 1000 chars):\n{page_html[:1000]}")
                logger.error("="*80)
                
                raise Exception("No SVG element created - rendering may have failed")
            
            logger.debug("Rendering completed successfully, extracting dimensions")
            
            # Extract actual SVG dimensions from viewBox
            svg_dimensions = await page.evaluate("""
                (() => {
                    const svg = document.querySelector('#d3-container svg');
                    if (!svg) return null;
                    
                    const viewBox = svg.getAttribute('viewBox');
                    if (viewBox) {
                        const parts = viewBox.split(' ').map(Number);
                        return {
                            x: parts[0],
                            y: parts[1],
                            width: parts[2],
                            height: parts[3],
                            source: 'viewBox'
                        };
                    }
                    
                    // Fallback to width/height attributes
                    const width = parseFloat(svg.getAttribute('width')) || 800;
                    const height = parseFloat(svg.getAttribute('height')) || 600;
                    return {
                        x: 0,
                        y: 0,
                        width: width,
                        height: height,
                        source: 'attributes'
                    };
                })()
            """)
            
            if not svg_dimensions:
                logger.error("Failed to extract SVG dimensions")
                raise Exception("Could not determine SVG dimensions")
            
            logger.info(f"SVG dimensions extracted: {svg_dimensions['width']}x{svg_dimensions['height']} (from {svg_dimensions['source']})")
            
            # Resize container to match actual SVG dimensions
            await page.evaluate(f"""
                (() => {{
                    const container = document.getElementById('d3-container');
                    if (container) {{
                        container.style.width = '{svg_dimensions["width"]}px';
                        container.style.height = '{svg_dimensions["height"]}px';
                        console.log('Container resized to:', '{svg_dimensions["width"]}x{svg_dimensions["height"]}');
                    }}
                }})()
            """)
            
            # Apply scale factor for high-DPI displays
            scale_factor = req.scale if req.scale else 2
            final_width = int(svg_dimensions['width'] * scale_factor)
            final_height = int(svg_dimensions['height'] * scale_factor)
            
            logger.info(f"Taking screenshot at {svg_dimensions['width']}x{svg_dimensions['height']} with scale {scale_factor}x (output: {final_width}x{final_height})")
            
            # Take screenshot of the resized container with scale
            d3_container = await page.query_selector('#d3-container')
            if d3_container:
                screenshot_bytes = await d3_container.screenshot(
                    type='png',
                    scale='device'  # Use device scale for quality
                )
            else:
                # Fallback to full page screenshot
                screenshot_bytes = await page.screenshot(full_page=True, type='png')
            
            logger.debug(f"PNG generated successfully ({len(screenshot_bytes)} bytes, scale={scale_factor}x)")
            
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
# BACKWARD COMPATIBILITY ENDPOINTS - Restored from Flask Migration
# ============================================================================

@router.post('/generate_png')
async def generate_png_from_prompt(
    req: GeneratePNGRequest,
    x_language: str = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key)
):
    """
    Generate PNG directly from user prompt (backward compatibility).
    
    This endpoint chains existing generate_graph() + export_png() internally.
    Uses main agent to extract topic and diagram type, exports default PNG result.
    Provides 1-step workflow for external clients.
    """
    lang = get_request_language(x_language)
    prompt = req.prompt.strip()
    
    if not prompt:
        raise HTTPException(
            status_code=400,
            detail=Messages.error("invalid_prompt", lang)
        )
    
    logger.info(f"[generate_png] Request: {prompt[:50]}... (llm={req.llm})")
    
    try:
        # Step 1: Generate diagram spec using main agent (reuse existing endpoint)
        generate_req = GenerateRequest(
            prompt=req.prompt,
            language=req.language,
            llm=req.llm,
            diagram_type=req.diagram_type,
            dimension_preference=req.dimension_preference
        )
        
        spec_result = await generate_graph(generate_req, x_language)
        
        logger.debug(f"[generate_png] Generated {spec_result.get('diagram_type')} spec")
        
        # Step 2: Export default PNG result from LLM (reuse existing endpoint)
        export_req = ExportPNGRequest(
            diagram_data=spec_result['spec'],
            diagram_type=spec_result['diagram_type'],
            width=req.width,
            height=req.height,
            scale=req.scale
        )
        
        png_response = await export_png(export_req, x_language)
        
        logger.info(f"[generate_png] Success: {spec_result.get('diagram_type')}")
        
        return png_response
        
    except HTTPException:
        # Let HTTP exceptions pass through
        raise
    except Exception as e:
        logger.error(f"[generate_png] Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=Messages.error("generation_failed", lang, str(e))
        )


@router.post('/generate_dingtalk')
async def generate_dingtalk_png(
    req: GenerateDingTalkRequest,
    x_language: str = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key)
):
    """
    Generate PNG for DingTalk integration (backward compatibility).
    
    Uses main agent to extract topic and diagram type from prompt.
    Exports default PNG result from LLM.
    Returns plain text in ![topic](url) format for DingTalk bot integration.
    """
    lang = get_request_language(x_language)
    prompt = req.prompt.strip()
    
    if not prompt:
        raise HTTPException(
            status_code=400,
            detail=Messages.error("invalid_prompt", lang)
        )
    
    logger.info(f"[generate_dingtalk] Request: {prompt[:50]}...")
    
    try:
        # Step 1: Main agent extracts topic + generates diagram spec
        generate_req = GenerateRequest(
            prompt=req.prompt,
            language=req.language,
            llm=req.llm,
            diagram_type=req.diagram_type,
            dimension_preference=req.dimension_preference
        )
        
        spec_result = await generate_graph(generate_req, x_language)
        
        logger.debug(f"[generate_dingtalk] Generated {spec_result.get('diagram_type')} spec")
        
        # Step 2: Export default PNG result from LLM
        export_req = ExportPNGRequest(
            diagram_data=spec_result['spec'],
            diagram_type=spec_result['diagram_type'],
            width=1200,
            height=800,
            scale=2
        )
        
        png_response = await export_png(export_req, x_language)
        
        # Step 3: Save PNG to temp directory (ASYNC file I/O)
        temp_dir = Path("temp_images")
        temp_dir.mkdir(exist_ok=True)
        
        # Generate unique filename
        unique_id = uuid.uuid4().hex[:8]
        timestamp = int(time.time())
        filename = f"dingtalk_{unique_id}_{timestamp}.png"
        temp_path = temp_dir / filename
        
        # Write PNG content to file using aiofiles (100% async, non-blocking)
        # Note: png_response is a Response object with .body property
        async with aiofiles.open(temp_path, 'wb') as f:
            await f.write(png_response.body)
        
        logger.debug(f"[generate_dingtalk] Saved to {temp_path}")
        
        # Step 4: Build plain text response in ![](url) format (empty alt text)
        external_host = os.getenv('EXTERNAL_HOST', 'localhost')
        port = os.getenv('PORT', '9527')
        image_url = f"http://{external_host}:{port}/api/temp_images/{filename}"
        plain_text = f"![]({image_url})"
        
        logger.info(f"[generate_dingtalk] Success: {image_url}")
        
        return PlainTextResponse(content=plain_text)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[generate_dingtalk] Error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=Messages.error("generation_failed", lang, str(e))
        )


@router.get('/temp_images/{filename}')
async def serve_temp_image(filename: str):
    """
    Serve temporary PNG files for DingTalk integration.
    
    Images auto-cleanup after 24 hours.
    """
    # Security: Validate filename to prevent directory traversal
    if '..' in filename or '/' in filename or '\\' in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    temp_path = Path("temp_images") / filename
    
    if not temp_path.exists():
        raise HTTPException(status_code=404, detail="Image not found or expired")
    
    return FileResponse(
        path=str(temp_path),
        media_type="image/png",
        headers={
            'Cache-Control': 'public, max-age=86400',
            'X-Content-Type-Options': 'nosniff'
        }
        )


# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@router.post('/frontend_log')
async def frontend_log(req: FrontendLogRequest):
    """
    Log single frontend message to backend console.
    Receives logs from browser and displays them in Python terminal.
    """
    level_map = {
        'error': logging.ERROR,
        'warn': logging.WARNING,
        'info': logging.INFO,
        'debug': logging.DEBUG
    }
    level = level_map.get(req.level.lower(), logging.INFO)
    
    # Create a dedicated frontend logger
    frontend_logger = logging.getLogger('frontend')
    frontend_logger.setLevel(logging.DEBUG)  # Accept all levels
    
    # Log message directly - Python logger will add its own timestamp
    # Don't include frontend timestamp to avoid duplication
    message = req.message
    
    # Log with clean formatting
    frontend_logger.log(level, message)
    
    return {'status': 'logged'}


@router.post('/frontend_log_batch')
async def frontend_log_batch(req: FrontendLogBatchRequest):
    """
    Log batched frontend messages to backend console (efficient bulk logging).
    Receives multiple logs from browser and displays them in Python terminal.
    """
    level_map = {
        'error': logging.ERROR,
        'warn': logging.WARNING,
        'info': logging.INFO,
        'debug': logging.DEBUG
    }
    
    # Create a dedicated frontend logger
    frontend_logger = logging.getLogger('frontend')
    frontend_logger.setLevel(logging.DEBUG)  # Accept all levels
    
    # Log batch header
    frontend_logger.info(f"=== FRONTEND LOG BATCH ({req.batch_size} logs) ===")
    
    # Log each message in the batch
    for log_entry in req.logs:
        level = level_map.get(log_entry.level.lower(), logging.INFO)
        
        # Log message directly - Python logger will add its own timestamp
        # Don't include frontend timestamp to avoid duplication
        message = log_entry.message
        
        # Log to backend console
        frontend_logger.log(level, message)
    
    return {'status': 'logged', 'count': req.batch_size}


@router.post('/recalculate_mindmap_layout')
async def recalculate_mindmap_layout(
    req: RecalculateLayoutRequest,
    current_user: Optional[User] = Depends(get_current_user_or_api_key)
):
    """
    Recalculate mind map layout after nodes are added/removed via node palette.
    
    This endpoint takes the current spec with new branches and recalculates
    the _layout and positioning data using the MindMapAgent.
    """
    try:
        spec = req.spec
        
        # Validate that it's a mindmap
        if not spec.get('topic'):
            raise HTTPException(
                status_code=400,
                detail="Invalid spec: 'topic' field is required for mindmaps"
            )
        
        # Import MindMapAgent
        from agents.mind_maps.mind_map_agent import MindMapAgent
        
        # Create agent instance
        mind_map_agent = MindMapAgent(model='qwen')
        
        # Use enhance_spec to recalculate layout
        enhanced_spec = await mind_map_agent.enhance_spec(spec)
        
        if not enhanced_spec.get('_layout'):
            raise HTTPException(
                status_code=500,
                detail="Failed to calculate layout"
            )
        
        logger.info(f"[RecalculateLayout] Layout recalculated for {len(spec.get('children', []))} branches")
        
        return {
            'success': True,
            'spec': enhanced_spec
        }
        
    except Exception as e:
        logger.error(f"[RecalculateLayout] Error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Layout recalculation failed: {str(e)}"
        )


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
async def generate_multi_parallel(
    req: GenerateRequest,
    x_language: str = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key)
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
async def generate_multi_progressive(
    req: GenerateRequest,
    x_language: str = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key)
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


@router.post('/feedback')
async def submit_feedback(
    req: FeedbackRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Submit user feedback (bugs, features, issues) via email to support team.
    Uses Resend API (https://resend.com) for simple email delivery without SMTP setup.
    Includes captcha verification to prevent spam.
    """
    try:
        from datetime import datetime
        import time
        
        # Import captcha store from auth router
        # Note: In production, use Redis for multi-server support
        from routers.auth import captcha_store
        
        # Validate captcha first (anti-spam protection)
        if req.captcha_id not in captcha_store:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Captcha expired or invalid. Please refresh."
            )
        
        stored_captcha = captcha_store[req.captcha_id]
        
        # Check expiration
        if time.time() > stored_captcha["expires"]:
            del captcha_store[req.captcha_id]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Captcha expired. Please refresh."
            )
        
        # Verify captcha code (case-insensitive)
        if stored_captcha['code'].upper() != req.captcha.upper():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect captcha code"
            )
        
        # Captcha verified, remove from store (one-time use)
        del captcha_store[req.captcha_id]
        logger.debug(f"Captcha verified for feedback from user {req.user_id or 'anonymous'}")
        
        # Support email
        support_email = 'support@mindspringedu.cn'
        
        # Try to get user from JWT token if available (optional - allows anonymous feedback)
        current_user = None
        try:
            # Try to get token from Authorization header first
            auth_header = request.headers.get('Authorization', '')
            token = None
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]
            else:
                # Try to get token from cookies (how browser-based auth typically works)
                token = request.cookies.get('access_token')
            
            if token:
                from utils.auth import decode_access_token
                payload = decode_access_token(token)
                user_id_from_token = payload.get("sub")
                if user_id_from_token:
                    current_user = db.query(User).filter(User.id == int(user_id_from_token)).first()
        except Exception:
            # No valid token, continue as anonymous (this is OK for feedback)
            pass
        
        # Get user info (use from request if provided, otherwise from token, otherwise anonymous)
        user_id = req.user_id or (current_user.id if current_user else 'anonymous')
        user_name = req.user_name or (current_user.name if current_user else 'Anonymous User')
        
        # Always log feedback to application logs first
        logger.info(f"[FEEDBACK] User: {user_name} ({user_id})")
        logger.info(f"[FEEDBACK] Message: {req.message}")
        
        # Try to send via Resend API if configured
        resend_api_key = os.getenv('RESEND_API_KEY')
        
        if resend_api_key:
            try:
                # Prepare email content
                email_subject = f'[MindGraph Feedback] From {user_name}'
                email_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9f9f9; padding: 20px; border-radius: 0 0 8px 8px; }}
        .info-row {{ margin: 10px 0; }}
        .label {{ font-weight: bold; color: #667eea; }}
        .message-box {{ background: white; padding: 15px; border-left: 4px solid #667eea; margin: 15px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>MindGraph Feedback Submission</h2>
        </div>
        <div class="content">
            <div class="info-row">
                <span class="label">User ID:</span> {user_id}
            </div>
            <div class="info-row">
                <span class="label">User Name:</span> {user_name}
            </div>
            <div class="info-row">
                <span class="label">Timestamp:</span> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </div>
            <div class="message-box">
                <div class="label">Message:</div>
                <div style="margin-top: 10px; white-space: pre-wrap;">{req.message}</div>
            </div>
            <p style="margin-top: 20px; font-size: 12px; color: #666;">
                This feedback was submitted through MindGraph application.
            </p>
        </div>
    </div>
</body>
</html>
"""
                
                email_text = f"""
User ID: {user_id}
User Name: {user_name}
Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Message:
{req.message}

---
This feedback was submitted through MindGraph application.
"""
                
                # Send via Resend API
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        'https://api.resend.com/emails',
                        headers={
                            'Authorization': f'Bearer {resend_api_key}',
                            'Content-Type': 'application/json'
                        },
                        json={
                            'from': os.getenv('RESEND_FROM_EMAIL', 'MindGraph <feedback@mindspringedu.cn>'),
                            'to': [support_email],
                            'subject': email_subject,
                            'html': email_html,
                            'text': email_text
                        }
                    )
                    
                    if response.status_code == 200:
                        logger.info(f"Feedback email sent successfully via Resend from user {user_id} ({user_name})")
                    else:
                        logger.error(f"Resend API error: {response.status_code} - {response.text}")
                        # Continue - feedback is still logged
                        
            except Exception as e:
                logger.error(f"Failed to send feedback email via Resend: {e}", exc_info=True)
                # Continue - feedback is still logged
        else:
            logger.warning("RESEND_API_KEY not configured, feedback logged only. Set RESEND_API_KEY in .env to enable email delivery.")
        
        return JSONResponse(
            status_code=200,
            content={
                'success': True,
                'message': 'Feedback submitted successfully'
            }
        )
        
    except Exception as e:
        logger.error(f"Error processing feedback: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail='Failed to submit feedback. Please try again later.'
        )


# Only log from main worker to avoid duplicate messages
import os
if os.getenv('UVICORN_WORKER_ID') is None or os.getenv('UVICORN_WORKER_ID') == '0':
    logger.info("API router loaded successfully")

