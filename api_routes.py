from flask import Blueprint, request, jsonify, send_file
import agent
import graph_specs
import logging
import tempfile
import asyncio
import re
import os
import atexit
import json
import time
from werkzeug.exceptions import HTTPException
from functools import wraps
from config import config

# URL configuration (fallback if url_config module doesn't exist)
try:
    from url_config import get_api_urls
    URLS = get_api_urls()
except ImportError:
    # Fallback URL configuration
    URLS = {
        'generate_graph': '/api/generate_graph',
        'render_svg_to_png': '/api/render_svg_to_png',
        'update_style': '/api/update_style'
    }

api = Blueprint('api', __name__, url_prefix='/api')
logger = logging.getLogger(__name__)

# Global timing tracking for rendering
rendering_timing_stats = {
    'total_renders': 0,
    'total_render_time': 0.0,
    'render_times': [],
    'last_render_time': 0.0,
    'llm_time_per_render': 0.0,
    'pure_render_time_per_render': 0.0
}

def get_rendering_timing_stats():
    """Get current rendering timing statistics."""
    if rendering_timing_stats['total_renders'] > 0:
        avg_render_time = rendering_timing_stats['total_render_time'] / rendering_timing_stats['total_renders']
        avg_llm_time = rendering_timing_stats['llm_time_per_render'] / rendering_timing_stats['total_renders']
        avg_pure_render_time = rendering_timing_stats['pure_render_time_per_render'] / rendering_timing_stats['total_renders']
    else:
        avg_render_time = 0.0
        avg_llm_time = 0.0
        avg_pure_render_time = 0.0
    
    return {
        'total_renders': rendering_timing_stats['total_renders'],
        'total_render_time': rendering_timing_stats['total_render_time'],
        'average_render_time': avg_render_time,
        'average_llm_time': avg_llm_time,
        'average_pure_render_time': avg_pure_render_time,
        'last_render_time': rendering_timing_stats['last_render_time'],
        'render_times': rendering_timing_stats['render_times'][-10:]  # Last 10 renders
    }

def get_comprehensive_timing_stats():
    """Get comprehensive timing statistics including both LLM and rendering."""
    llm_stats = agent.get_llm_timing_stats()
    render_stats = get_rendering_timing_stats()
    
    return {
        'llm': llm_stats,
        'rendering': render_stats,
        'summary': {
            'total_llm_calls': llm_stats['total_calls'],
            'total_llm_time': llm_stats['total_time'],
            'total_renders': render_stats['total_renders'],
            'total_render_time': render_stats['total_render_time'],
            'llm_percentage': (llm_stats['total_time'] / (llm_stats['total_time'] + render_stats['total_render_time']) * 100) if (llm_stats['total_time'] + render_stats['total_render_time']) > 0 else 0,
            'render_percentage': (render_stats['total_render_time'] / (llm_stats['total_time'] + render_stats['total_render_time']) * 100) if (llm_stats['total_time'] + render_stats['total_render_time']) > 0 else 0
        }
    }

# Track temporary files for cleanup
temp_files = set()

def cleanup_temp_files():
    """Clean up temporary files on exit."""
    for temp_file in temp_files:
        try:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
        except OSError:
            pass

atexit.register(cleanup_temp_files)

def handle_api_errors(f):
    """Decorator for centralized API error handling with consistent error format."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except Exception as e:
            logger.error(f"API error in {f.__name__}: {e}", exc_info=True)
            error_message = "An unexpected error occurred. Please try again later."
            if config.DEBUG:
                error_message = f"{error_message} Details: {str(e)}"
            return jsonify({
                'error': error_message,
                'type': 'internal_error'
            }), 500
    return decorated_function

def validate_request_data(data, required_fields=None):
    """Validate request data structure."""
    if not data:
        return False, "Missing request data"
    
    if required_fields:
        for field in required_fields:
            if field not in data:
                return False, f"Missing required field: {field}"
    
    return True, ""

def sanitize_prompt(prompt):
    """Enhanced sanitization with comprehensive security measures."""
    if not isinstance(prompt, str):
        return None
    prompt = prompt.strip()
    if not prompt:
        return None
    
    # Remove potentially dangerous patterns
    dangerous_patterns = [
        r'<script[^>]*>.*?</script>',  # Script tags
        r'<iframe[^>]*>.*?</iframe>',  # Iframe tags
        r'<object[^>]*>.*?</object>',  # Object tags
        r'<embed[^>]*>',  # Embed tags
        r'javascript:',  # JavaScript protocol
        r'data:',  # Data protocol
        r'vbscript:',  # VBScript protocol
        r'on\w+\s*=',  # Event handlers
        r'<[^>]*>',  # Any remaining HTML tags
        r'expression\s*\(',  # CSS expressions
        r'url\s*\(',  # CSS url functions
        r'import\s+',  # CSS imports
        r'@import',  # CSS @import
        r'\\',  # Backslashes
        r'<!--',  # HTML comments
        r'-->',  # HTML comments
    ]
    
    for pattern in dangerous_patterns:
        prompt = re.sub(pattern, '', prompt, flags=re.IGNORECASE | re.DOTALL)
    
    # HTML entity encoding for special characters
    html_entities = {
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#x27;',
        '&': '&amp;',
        '/': '&#x2F;',
        '\\': '&#x5C;',
    }
    
    for char, entity in html_entities.items():
        prompt = prompt.replace(char, entity)
    
    # Remove control characters and normalize whitespace
    prompt = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', prompt)
    prompt = re.sub(r'\s+', ' ', prompt)
    
    # Limit length and ensure it's not empty after sanitization
    sanitized = prompt[:1000].strip()
    return sanitized if sanitized else None

@api.route('/generate_graph', methods=['POST'])
@handle_api_errors
def generate_graph():
    """Generate graph specification from user prompt using Qwen (default, with enhanced extraction and style integration)."""
    # Input validation
    data = request.json
    valid, msg = validate_request_data(data, ['prompt'])
    if not valid:
        return jsonify({'error': msg}), 400
    
    prompt = sanitize_prompt(data['prompt'])
    if not prompt:
        return jsonify({'error': 'Invalid or empty prompt'}), 400
    
    language = data.get('language', 'zh')  # Default to Chinese for Qwen
    if not isinstance(language, str) or language not in ['zh', 'en']:
        return jsonify({'error': 'Invalid language. Must be "zh" or "en"'}), 400
    
    logger.info(f"Frontend /generate_graph (Qwen with styles): prompt={prompt!r}, language={language!r}")
    
    # Track timing for LLM processing
    start_time = time.time()
    
    # Use enhanced agent workflow with integrated style system
    try:
        result = agent.agent_graph_workflow_with_styles(prompt, language)
        
        # Calculate LLM processing time
        llm_time = time.time() - start_time
        logger.info(f"LLM processing completed in {llm_time:.3f}s")
        
        # Add timing information to response
        timing_info = {
            'llm_processing_time': llm_time,
            'llm_stats': agent.get_llm_timing_stats()
        }
        
        spec = result.get('spec', {})
        diagram_type = result.get('diagram_type', 'bubble_map')
        topics = result.get('topics', [])
        style_preferences = result.get('style_preferences', {})
        
        # Validate the generated spec
        from graph_specs import DIAGRAM_VALIDATORS
        if diagram_type in DIAGRAM_VALIDATORS:
            validate_fn = DIAGRAM_VALIDATORS[diagram_type]
            valid, msg = validate_fn(spec)
            if not valid:
                logger.warning(f"Generated invalid spec for {diagram_type}: {msg}")
                return jsonify({'error': f'Failed to generate valid graph specification: {msg}'}), 400
        else:
            logger.warning(f"No validator found for diagram type: {diagram_type}")
        
        # Optionally enhance spec using specialized agents
        if diagram_type == 'multi_flow_map':
            try:
                from multi_flow_map_agent import MultiFlowMapAgent
                mf_agent = MultiFlowMapAgent()
                agent_result = mf_agent.enhance_spec(spec)
                if agent_result.get('success') and 'spec' in agent_result:
                    spec = agent_result['spec']
                else:
                    logger.warning(f"MultiFlowMapAgent enhancement skipped: {agent_result.get('error')}")
            except Exception as e:
                logger.error(f"Error enhancing multi_flow_map spec: {e}")
        elif diagram_type == 'flow_map':
            try:
                from flow_map_agent import FlowMapAgent
                f_agent = FlowMapAgent()
                agent_result = f_agent.enhance_spec(spec)
                if agent_result.get('success') and 'spec' in agent_result:
                    spec = agent_result['spec']
                else:
                    logger.warning(f"FlowMapAgent enhancement skipped: {agent_result.get('error')}")
            except Exception as e:
                logger.error(f"Error enhancing flow_map spec: {e}")
        elif diagram_type == 'tree_map':
            try:
                from tree_map_agent import TreeMapAgent
                t_agent = TreeMapAgent()
                agent_result = t_agent.enhance_spec(spec)
                if agent_result.get('success') and 'spec' in agent_result:
                    spec = agent_result['spec']
                else:
                    logger.warning(f"TreeMapAgent enhancement skipped: {agent_result.get('error')}")
            except Exception as e:
                logger.error(f"Error enhancing tree_map spec: {e}")

        # Calculate optimized dimensions
        dimensions = config.get_d3_dimensions()
        # Use agent-recommended dimensions if provided
        if diagram_type in ('multi_flow_map', 'flow_map', 'tree_map') and isinstance(spec, dict) and spec.get('_recommended_dimensions'):
            rd = spec['_recommended_dimensions']
            try:
                dimensions = {
                    'baseWidth': rd.get('baseWidth', dimensions.get('baseWidth', 900)),
                    'baseHeight': rd.get('baseHeight', dimensions.get('baseHeight', 500)),
                    'padding': rd.get('padding', dimensions.get('padding', 40)),
                    'width': rd.get('width', rd.get('baseWidth', dimensions.get('baseWidth', 900))),
                    'height': rd.get('height', rd.get('baseHeight', dimensions.get('baseHeight', 500))),
                    'topicFontSize': dimensions.get('topicFontSize', 18),
                    'charFontSize': dimensions.get('charFontSize', 14)
                }
            except Exception as e:
                logger.warning(f"Failed to apply recommended dimensions: {e}")
        if diagram_type == 'bridge_map' and spec and 'analogies' in spec:
            num_analogies = len(spec['analogies'])
            min_width_per_analogy = 120
            min_padding = 40
            content_width = (num_analogies * min_width_per_analogy) + ((num_analogies - 1) * 60)
            optimal_width = max(content_width + (2 * min_padding), 600)
            optimal_height = max(90 + (2 * min_padding), 200)  # 90px for text + lines
            
            dimensions = {
                'baseWidth': optimal_width,
                'baseHeight': optimal_height,
                'padding': min_padding,
                'width': optimal_width,
                'height': optimal_height,
                'topicFontSize': dimensions.get('topicFontSize', 18),
                'charFontSize': dimensions.get('charFontSize', 14)
            }
        
        return jsonify({
            'type': diagram_type,
            'spec': spec,
            'agent': 'qwen',
            'topics': topics,
            'style_preferences': style_preferences,
            'diagram_type': diagram_type,
            'has_styles': '_style' in spec,
            'theme': config.get_d3_theme(),
            'dimensions': dimensions,
            'watermark': config.get_watermark_config(),
            'timing': timing_info
        })
        
    except Exception as e:
        logger.error(f"Enhanced agent workflow failed: {e}")
        return jsonify({'error': 'Failed to generate graph specification'}), 500


@api.route('/generate_png', methods=['POST'])
@handle_api_errors
def generate_png():
    """Generate PNG image from user prompt."""
    # Input validation
    data = request.json
    valid, msg = validate_request_data(data, ['prompt'])
    if not valid:
        return jsonify({'error': msg}), 400
    
    prompt = sanitize_prompt(data['prompt'])
    if not prompt:
        return jsonify({'error': 'Invalid or empty prompt'}), 400
    
    language = data.get('language', 'zh')
    if not isinstance(language, str) or language not in ['zh', 'en']:
        return jsonify({'error': 'Invalid language. Must be "zh" or "en"'}), 400
    
    logger.info(f"Frontend /generate_png: prompt={prompt!r}, language={language!r}")
    
    # Track timing for the entire process
    total_start_time = time.time()
    
    # Generate graph specification using the same workflow as generate_graph
    try:
        llm_start_time = time.time()
        result = agent.agent_graph_workflow_with_styles(prompt, language)
        llm_time = time.time() - llm_start_time
        
        spec = result.get('spec', {})
        graph_type = result.get('diagram_type', 'bubble_map')
        
        logger.info(f"LLM processing completed in {llm_time:.3f}s")
    except Exception as e:
        logger.error(f"Agent workflow failed: {e}")
        return jsonify({'error': 'Failed to generate graph specification'}), 500
    
    # Validate the generated spec before processing
    from graph_specs import DIAGRAM_VALIDATORS
    if graph_type in DIAGRAM_VALIDATORS:
        validate_fn = DIAGRAM_VALIDATORS[graph_type]
        valid, msg = validate_fn(spec)
        if not valid:
            logger.warning(f"Generated invalid spec for {graph_type}: {msg}")
            return jsonify({'error': f'Failed to generate valid graph specification: {msg}'}), 400
    else:
        logger.warning(f"No validator found for diagram type: {graph_type}")
    
    # Use brace map agent for brace maps
    if graph_type == 'brace_map':
        try:
            from brace_map_agent import BraceMapAgent
            brace_agent = BraceMapAgent()
            agent_result = brace_agent.generate_diagram(spec)
            if agent_result['success']:
                # Use agent result instead of spec for brace maps
                spec = agent_result
            else:
                logger.warning(f"Brace map agent failed: {agent_result.get('error')}")
                # Fall back to original spec
        except Exception as e:
            logger.error(f"Error using brace map agent: {e}")
            # Fall back to original spec
    elif graph_type == 'multi_flow_map':
        # Enhance multi-flow map spec and optionally use recommended dimensions later
        try:
            from multi_flow_map_agent import MultiFlowMapAgent
            mf_agent = MultiFlowMapAgent()
            agent_result = mf_agent.enhance_spec(spec)
            if agent_result.get('success') and 'spec' in agent_result:
                spec = agent_result['spec']
            else:
                logger.warning(f"MultiFlowMapAgent enhancement skipped: {agent_result.get('error')}")
        except Exception as e:
            logger.error(f"Error enhancing multi_flow_map spec: {e}")
    elif graph_type == 'flow_map':
        # Enhance flow map spec and use recommended dimensions
        try:
            from flow_map_agent import FlowMapAgent
            f_agent = FlowMapAgent()
            agent_result = f_agent.enhance_spec(spec)
            if agent_result.get('success') and 'spec' in agent_result:
                spec = agent_result['spec']
            else:
                logger.warning(f"FlowMapAgent enhancement skipped: {agent_result.get('error')}")
        except Exception as e:
            logger.error(f"Error enhancing flow_map spec: {e}")
    elif graph_type == 'tree_map':
        # Enhance tree map spec and use recommended dimensions
        try:
            from tree_map_agent import TreeMapAgent
            t_agent = TreeMapAgent()
            agent_result = t_agent.enhance_spec(spec)
            if agent_result.get('success') and 'spec' in agent_result:
                spec = agent_result['spec']
            else:
                logger.warning(f"TreeMapAgent enhancement skipped: {agent_result.get('error')}")
        except Exception as e:
            logger.error(f"Error enhancing tree_map spec: {e}")
    
    # Check if spec has required structure for rendering
    if not spec or isinstance(spec, dict) and spec.get('error'):
        return jsonify({'error': 'Failed to generate valid graph specification'}), 400
    
    # Render SVG and convert to PNG using Playwright
    try:
        import nest_asyncio
        nest_asyncio.apply()
        import json
        from playwright.async_api import async_playwright
        
        # Track rendering start time
        render_start_time = time.time()
        
        async def render_svg_to_png(spec, graph_type):
            # Load the theme configuration
            with open('static/js/theme-config.js', 'r', encoding='utf-8') as f:
                theme_config = f.read()
            
            # Load the correct D3.js renderers from the static file
            with open('static/js/d3-renderers.js', 'r', encoding='utf-8') as f:
                d3_renderers = f.read()
            
            # Load the style manager
            with open('static/js/style-manager.js', 'r', encoding='utf-8') as f:
                style_manager = f.read()
            
            # Log spec data for debugging
            logger.info(f"Spec data keys: {list(spec.keys()) if isinstance(spec, dict) else 'Not a dict'}")
            if isinstance(spec, dict) and 'svg_data' in spec:
                logger.info(f"SVG data keys: {list(spec['svg_data'].keys()) if isinstance(spec['svg_data'], dict) else 'Not a dict'}")
                if isinstance(spec['svg_data'], dict) and 'elements' in spec['svg_data']:
                    logger.info(f"Number of SVG elements: {len(spec['svg_data']['elements'])}")
            
            # Calculate optimized dimensions for different graph types
            dimensions = config.get_d3_dimensions()
            
            if graph_type == 'bridge_map' and spec and 'analogies' in spec:
                num_analogies = len(spec['analogies'])
                min_width_per_analogy = 120
                min_padding = 40
                content_width = (num_analogies * min_width_per_analogy) + ((num_analogies - 1) * 60)
                optimal_width = max(content_width + (2 * min_padding), 600)
                optimal_height = max(90 + (2 * min_padding), 200)  # 90px for text + lines
                
                dimensions = {
                    'baseWidth': optimal_width,
                    'baseHeight': optimal_height,
                    'padding': min_padding,
                    'width': optimal_width,
                    'height': optimal_height,
                    'topicFontSize': dimensions.get('topicFontSize', 18),
                    'charFontSize': dimensions.get('charFontSize', 14)
                }
            elif graph_type == 'brace_map' and spec and spec.get('success') and 'svg_data' in spec:
                # Use agent's optimal dimensions for brace maps
                svg_data = spec['svg_data']
                if 'width' in svg_data and 'height' in svg_data:
                    # Use the agent's calculated optimal dimensions
                    dimensions = {
                        'baseWidth': svg_data['width'],
                        'baseHeight': svg_data['height'],
                        'padding': 50,
                        'width': svg_data['width'],
                        'height': svg_data['height'],
                        'topicFontSize': dimensions.get('topicFontSize', 20),
                        'partFontSize': dimensions.get('partFontSize', 16),
                        'subpartFontSize': dimensions.get('subpartFontSize', 14)
                    }
                    logger.info(f"Using agent's optimal dimensions: {svg_data['width']}x{svg_data['height']}")
                else:
                    # Fallback to default dimensions if agent data is not available
                    dimensions = {
                        'baseWidth': 800,
                        'baseHeight': 600,
                        'padding': 50,
                        'width': 800,
                        'height': 600,
                        'topicFontSize': dimensions.get('topicFontSize', 20),
                        'partFontSize': dimensions.get('partFontSize', 16),
                        'subpartFontSize': dimensions.get('subpartFontSize', 14)
                    }
                    logger.warning("Agent dimensions not available, using fallback dimensions")
            elif graph_type in ('multi_flow_map', 'flow_map', 'tree_map') and isinstance(spec, dict):
                try:
                    rd = spec.get('_recommended_dimensions') or {}
                    if rd:
                        dimensions = {
                            'baseWidth': rd.get('baseWidth', dimensions.get('baseWidth', 900)),
                            'baseHeight': rd.get('baseHeight', dimensions.get('baseHeight', 500)),
                            'padding': rd.get('padding', dimensions.get('padding', 40)),
                            'width': rd.get('width', rd.get('baseWidth', dimensions.get('baseWidth', 900))),
                            'height': rd.get('height', rd.get('baseHeight', dimensions.get('baseHeight', 500))),
                            'topicFontSize': dimensions.get('topicFontSize', 18),
                            'charFontSize': dimensions.get('charFontSize', 14)
                        }
                except Exception as e:
                    logger.warning(f"Failed to apply recommended dimensions: {e}")
            
            html = f'''
            <html><head>
            <meta charset="utf-8">
            <script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
            <style>
                body {{ margin:0; background:#fff; }}
                #d3-container {{ 
                    width: 100%; 
                    height: 100vh; 
                    display: block; 
                    background: #f0f0f0; 
                }}
            </style>
            </head><body>
            <div id="d3-container"></div>
            <script>
            {theme_config}
            {style_manager}
            {d3_renderers}
            console.log("Page loaded, waiting for D3.js...");
            
            // Wait for D3.js to load
            function waitForD3() {{
                if (typeof d3 !== "undefined") {{
                    console.log("D3.js loaded, starting rendering...");
                    try {{
                        window.spec = {json.dumps(spec, ensure_ascii=False)};
                        window.graph_type = "{graph_type}";
                        
                        // Get theme using centralized configuration
                        let theme;
                        let backendTheme;
                        if (typeof getD3Theme === "function") {{
                            theme = getD3Theme(graph_type);
                            console.log("Using centralized theme configuration");
                        }} else {{
                            // Fallback to style manager
                            const d3Theme = {json.dumps(config.get_d3_theme(), ensure_ascii=False)};
                            theme = d3Theme;
                            console.log("Using style manager theme");
                        }}
                        const watermarkConfig = {json.dumps(config.get_watermark_config(), ensure_ascii=False)};
                        backendTheme = {{...theme, ...watermarkConfig}};
                        window.dimensions = {json.dumps(dimensions, ensure_ascii=False)};
                        
                        {style_manager}
                        {d3_renderers}
                        
                        console.log("Rendering graph:", window.graph_type, window.spec);
                        console.log("Style manager loaded:", typeof styleManager);
                        console.log("Backend theme:", backendTheme);
                        
                        // Ensure style manager is available
                        if (typeof styleManager === "undefined") {{
                            console.error("Style manager not loaded!");
                            document.body.innerHTML += "<div style=\\"color: red; padding: 20px;\\">Style manager not loaded!</div>";
                            throw new Error("Style manager not available");
                        }} else {{
                            console.log("Style manager is available");
                        }}
                        
                        // Use agent renderer for brace maps
                        if (window.graph_type === "brace_map" && window.spec.success) {{
                            console.log("Using brace map agent renderer");
                            renderBraceMapAgent(window.spec, backendTheme, window.dimensions);
                        }} else {{
                            renderGraph(window.graph_type, window.spec, backendTheme, window.dimensions);
                        }}
                        
                        console.log("Graph rendering completed");
                        
                        // Wait a moment for SVG to be created
                        setTimeout(() => {{
                            const svg = document.querySelector("svg");
                            if (svg) {{
                                console.log("SVG found with dimensions:", svg.getAttribute("width"), "x", svg.getAttribute("height"));
                            }} else {{
                                console.error("No SVG element found after rendering");
                                document.body.innerHTML += "<div style=\\"color: red; padding: 20px;\\">No SVG created after rendering</div>";
                            }}
                        }}, 1000);
                    }} catch (error) {{
                        console.error("Render error:", error);
                        document.body.innerHTML += "<div style=\\"color: red; padding: 20px;\\">Render error: " + error.message + "</div>";
                    }}
                }} else {{
                    setTimeout(waitForD3, 100);
                }}
            }}
            waitForD3();
            </script>
            </body></html>
            '''
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # Set up console and error logging BEFORE loading content
                console_messages = []
                page_errors = []
                
                page.on("console", lambda msg: console_messages.append(f"{msg.type}: {msg.text}"))
                page.on("pageerror", lambda err: page_errors.append(str(err)))
                
                # Log HTML size for debugging
                html_size = len(html)
                logger.info(f"HTML content size: {html_size} characters")
                if html_size > 100000:  # Log if HTML is very large
                    logger.warning(f"Large HTML content: {html_size} characters")
                
                await page.set_content(html)
                
                # Wait for rendering and check for console errors
                await asyncio.sleep(3.0)
                
                # Log all console messages and errors
                for msg in console_messages:
                    logger.info(f"Browser console: {msg}")
                for error in page_errors:
                    logger.error(f"Browser error: {error}")
                
                # Wait a bit more for rendering to complete
                await asyncio.sleep(2.0)
                
                # Wait for SVG element to be created with timeout
                try:
                    element = await page.wait_for_selector("svg", timeout=10000)
                    logger.info("SVG element found successfully")
                except Exception as e:
                    logger.error(f"Timeout waiting for SVG element: {e}")
                    element = await page.query_selector("svg")  # Try one more time
                
                # Check if SVG exists and has content
                if element is None:
                    logger.error("SVG element not found in rendered page.")
                    
                    # Check if d3-container has any content
                    container = await page.query_selector("#d3-container")
                    if container:
                        container_content = await container.inner_html()
                        logger.error(f"Container content: {container_content[:500]}...")
                    else:
                        logger.error("d3-container element not found")
                    
                    # Log page content for debugging
                    page_content = await page.content()
                    logger.error(f"Page content: {page_content[:1000]}...")
                    
                    # Check if any JavaScript functions are available
                    try:
                        d3_available = await page.evaluate("typeof d3 !== \"undefined\"")
                        style_manager_available = await page.evaluate("typeof styleManager !== \"undefined\"")
                        render_graph_available = await page.evaluate("typeof renderGraph !== \"undefined\"")
                        
                        logger.error(f"JavaScript availability - D3: {d3_available}, StyleManager: {style_manager_available}, renderGraph: {render_graph_available}")
                    except Exception as e:
                        logger.error(f"Could not check JavaScript availability: {e}")
                    
                    raise ValueError("SVG element not found. The graph could not be rendered.")
                
                # Check SVG dimensions
                svg_width = await element.get_attribute('width')
                svg_height = await element.get_attribute('height')
                logger.info(f"SVG dimensions: width={svg_width}, height={svg_height}")
                
                # Ensure element is visible before screenshot
                await element.scroll_into_view_if_needed()
                await page.wait_for_timeout(1000)  # Wait for any animations to complete
                
                png_bytes = await element.screenshot(omit_background=False, timeout=60000)
                await browser.close()
                return png_bytes
        
        png_bytes = asyncio.run(render_svg_to_png(spec, graph_type))
        
        # Calculate rendering time
        render_time = time.time() - render_start_time
        total_time = time.time() - total_start_time
        
        # Update rendering statistics
        rendering_timing_stats['total_renders'] += 1
        rendering_timing_stats['total_render_time'] += render_time
        rendering_timing_stats['last_render_time'] = render_time
        rendering_timing_stats['render_times'].append(render_time)
        rendering_timing_stats['llm_time_per_render'] += llm_time
        rendering_timing_stats['pure_render_time_per_render'] += render_time
        
        # Keep only last 100 render times to prevent memory bloat
        if len(rendering_timing_stats['render_times']) > 100:
            rendering_timing_stats['render_times'] = rendering_timing_stats['render_times'][-100:]
        
        logger.info(f"PNG generation completed - LLM: {llm_time:.3f}s, Rendering: {render_time:.3f}s, Total: {total_time:.3f}s")
        
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png', mode='wb') as tmp:
                # Set restrictive permissions
                os.chmod(tmp.name, 0o600)
                temp_files.add(tmp.name)
                
                tmp.write(png_bytes)
                tmp.flush()
                tmp.seek(0)
                
                return send_file(
                    tmp.name, 
                    mimetype='image/png', 
                    as_attachment=True, 
                    download_name='graph.png'
                )
        except Exception as e:
            # Clean up temp file on error
            if 'tmp' in locals() and hasattr(tmp, 'name'):
                try:
                    os.unlink(tmp.name)
                    temp_files.discard(tmp.name)
                except OSError:
                    pass
            raise
    except Exception as e:
        logger.error(f"/generate_png failed: {e}", exc_info=True)
        # If the error is about missing SVG, return a specific message
        if isinstance(e, ValueError) and str(e).startswith("SVG element not found"):
            return jsonify({'error': 'Failed to render the graph: SVG element not found. Please check your input or try a different prompt.'}), 400
        return jsonify({'error': f'Failed to generate PNG: {e}'}), 500


@api.route('/generate_graph_deepseek', methods=['POST'])
@handle_api_errors
def generate_graph_deepseek():
    """Generate graph specification using DeepSeek for prompt enhancement and Qwen for JSON generation (optional)."""
    # Input validation
    data = request.json
    valid, msg = validate_request_data(data, ['prompt'])
    if not valid:
        return jsonify({'error': msg}), 400
    
    prompt = sanitize_prompt(data['prompt'])
    if not prompt:
        return jsonify({'error': 'Invalid or empty prompt'}), 400
    
    language = data.get('language', 'en')  # Default to English for DeepSeek
    if not isinstance(language, str) or language not in ['zh', 'en']:
        return jsonify({'error': 'Invalid language. Must be "zh" or "en"'}), 400
    
    logger.info(f"Frontend /generate_graph_deepseek: prompt={prompt!r}, language={language!r}")
    
    try:
        import deepseek_agent
        # Use enhanced agent for combined extraction
        enhanced_result = deepseek_agent.enhanced_development_workflow(prompt, language, save_to_file=False)
        if isinstance(enhanced_result, dict) and enhanced_result.get('error'):
            logger.error(f"DeepSeek enhanced workflow failed: {enhanced_result['error']}")
            return jsonify({'error': enhanced_result['error']}), 400
        
        diagram_type = enhanced_result.get('diagram_type', 'bubble_map')
        enhanced_prompt = enhanced_result.get('development_prompt', prompt)
        topics = enhanced_result.get('topics', [])
        style_preferences = enhanced_result.get('style_preferences', {})
        
        logger.info(f"DeepSeek: Classified as {diagram_type}, enhanced prompt generated")
        
        # Use Qwen to generate the actual JSON specification
        spec = agent.generate_graph_spec(enhanced_prompt, diagram_type, language)
        
        if isinstance(spec, dict) and spec.get('error'):
            logger.error(f"Qwen JSON generation failed: {spec['error']}")
            return jsonify({'error': spec['error']}), 400
        
        logger.info(f"Qwen: Generated JSON specification for {diagram_type}")
        
        return jsonify({
            'type': diagram_type,
            'spec': spec,
            'agent': 'deepseek+qwen',
            'enhanced_prompt': enhanced_prompt,
            'topics': topics,
            'style_preferences': style_preferences,
            'theme': config.get_d3_theme(),
            'dimensions': config.get_d3_dimensions(),
            'watermark': config.get_watermark_config()
        })
        
    except ImportError:
        logger.error("DeepSeek agent module not available")
        return jsonify({'error': 'DeepSeek agent is not available. Please check configuration.'}), 500
    except Exception as e:
        logger.error(f"DeepSeek + Qwen workflow failed: {e}", exc_info=True)
        return jsonify({'error': f'Workflow failed: {str(e)}'}), 500


@api.route('/generate_development_prompt', methods=['POST'])
@handle_api_errors
def generate_development_prompt():
    """Generate development phase prompt template using DeepSeek (for developers)."""
    # Input validation
    data = request.json
    valid, msg = validate_request_data(data, ['prompt'])
    if not valid:
        return jsonify({'error': msg}), 400
    
    prompt = sanitize_prompt(data['prompt'])
    if not prompt:
        return jsonify({'error': 'Invalid or empty prompt'}), 400
    
    language = data.get('language', 'en')  # Default to English for DeepSeek
    if not isinstance(language, str) or language not in ['zh', 'en']:
        return jsonify({'error': 'Invalid language. Must be "zh" or "en"'}), 400
    
    save_to_file = data.get('save_to_file', True)  # Default to saving
    
    logger.info(f"Frontend /generate_development_prompt: prompt={prompt!r}, language={language!r}")
    
    try:
        # Use DeepSeek for development phase prompt generation
        import deepseek_agent
        
        # Generate development prompt template
        result = deepseek_agent.development_workflow(prompt, language, save_to_file)
        
        # Check if DeepSeek processing was successful
        if isinstance(result, dict) and result.get('error'):
            logger.error(f"DeepSeek development prompt generation failed: {result['error']}")
            return jsonify({'error': result['error']}), 400
        
        logger.info(f"DeepSeek: Generated development prompt for {result.get('diagram_type', 'unknown')}")
        
        return jsonify({
            'diagram_type': result.get('diagram_type'),
            'development_prompt': result.get('development_prompt'),
            'original_prompt': result.get('original_prompt'),
            'language': result.get('language'),
            'workflow_type': result.get('workflow_type'),
            'saved_filename': result.get('saved_filename'),
            'agent': 'deepseek_development'
        })
        
    except ImportError:
        logger.error("DeepSeek agent module not available")
        return jsonify({'error': 'DeepSeek agent is not available. Please check configuration.'}), 500
    except Exception as e:
        logger.error(f"DeepSeek development workflow failed: {e}", exc_info=True)
        return jsonify({'error': f'Development workflow failed: {str(e)}'}), 500 

@api.route('/update_style', methods=['POST'])
@handle_api_errors
def update_style():
    """Update diagram style instantly - demonstrates the flexibility of the new style system."""
    data = request.json
    valid, msg = validate_request_data(data, ['diagram_type', 'element', 'color'])
    if not valid:
        return jsonify({'error': msg}), 400
    
    diagram_type = data['diagram_type']
    element = data['element']  # e.g., 'topicFill', 'topicText', 'attributeFill'
    color = data['color']
    
    # Validate color format
    if not color.startswith('#') or len(color) != 7:
        return jsonify({'error': 'Invalid color format. Use hex format (e.g., #ff0000)'}), 400
    
    # Get current style for the diagram type
    from diagram_styles import get_style
    current_style = get_style(diagram_type)
    
    # Update the specific element
    current_style[element] = color
    
    # Ensure readability is maintained
    from diagram_styles import get_contrasting_text_color
    if 'Fill' in element and 'Text' not in element:
        # If we're changing a fill color, ensure text color is readable
        text_element = element.replace('Fill', 'TextColor')
        if text_element not in current_style:
            current_style[text_element] = get_contrasting_text_color(color)
    
    return jsonify({
        'success': True,
        'message': f'Updated {element} to {color}',
        'updated_style': current_style
    })

@api.route('/timing_stats', methods=['GET'])
@handle_api_errors
def get_timing_stats():
    """Get comprehensive timing statistics for LLM calls and rendering."""
    stats = get_comprehensive_timing_stats()
    
    # Format the response for better readability
    formatted_stats = {
        'llm': {
            'total_calls': stats['llm']['total_calls'],
            'total_time_seconds': round(stats['llm']['total_time'], 3),
            'average_time_seconds': round(stats['llm']['average_time'], 3),
            'last_call_time_seconds': round(stats['llm']['last_call_time'], 3),
            'recent_call_times': [round(t, 3) for t in stats['llm']['call_times']]
        },
        'rendering': {
            'total_renders': stats['rendering']['total_renders'],
            'total_render_time_seconds': round(stats['rendering']['total_render_time'], 3),
            'average_render_time_seconds': round(stats['rendering']['average_render_time'], 3),
            'average_llm_time_per_render_seconds': round(stats['rendering']['average_llm_time'], 3),
            'average_pure_render_time_seconds': round(stats['rendering']['average_pure_render_time'], 3),
            'last_render_time_seconds': round(stats['rendering']['last_render_time'], 3),
            'recent_render_times': [round(t, 3) for t in stats['rendering']['render_times']]
        },
        'summary': {
            'total_llm_calls': stats['summary']['total_llm_calls'],
            'total_llm_time_seconds': round(stats['summary']['total_llm_time'], 3),
            'total_renders': stats['summary']['total_renders'],
            'total_render_time_seconds': round(stats['summary']['total_render_time'], 3),
            'llm_percentage': round(stats['summary']['llm_percentage'], 1),
            'render_percentage': round(stats['summary']['render_percentage'], 1)
        }
    }
    
    return jsonify(formatted_stats) 