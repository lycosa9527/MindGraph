from flask import Blueprint, request, jsonify, send_file
import agent
import graph_specs
import logging
import tempfile
import asyncio
import re
import os
import atexit
from werkzeug.exceptions import HTTPException
from functools import wraps
from config import config

api = Blueprint('api', __name__, url_prefix='/api')
logger = logging.getLogger(__name__)

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
    
    # Use enhanced agent workflow with integrated style system
    try:
        result = agent.agent_graph_workflow_with_styles(prompt, language)
        
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
        
        # Calculate optimized dimensions for bridge maps
        dimensions = config.get_d3_dimensions()
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
            'watermark': config.get_watermark_config()
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
    
    # Generate graph specification using the same workflow as generate_graph
    try:
        result = agent.agent_graph_workflow_with_styles(prompt, language)
        
        spec = result.get('spec', {})
        graph_type = result.get('diagram_type', 'bubble_map')
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
    
    # Check if spec has required structure for rendering
    if not spec or isinstance(spec, dict) and spec.get('error'):
        return jsonify({'error': 'Failed to generate valid graph specification'}), 400
    
    # Render SVG and convert to PNG using Playwright
    try:
        import nest_asyncio
        nest_asyncio.apply()
        import json
        from playwright.async_api import async_playwright
        
        async def render_svg_to_png(spec, graph_type):
            # Load the correct D3.js renderers from the static file
            with open('static/js/d3-renderers.js', 'r', encoding='utf-8') as f:
                d3_renderers = f.read()
            
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
            console.log('Page loaded, waiting for D3.js...');
            
            // Wait for D3.js to load
            function waitForD3() {{
                if (typeof d3 !== 'undefined') {{
                    console.log('D3.js loaded, starting rendering...');
                    try {{
                        window.spec = {json.dumps(spec, ensure_ascii=False)};
                        window.graph_type = '{graph_type}';
                        
                        // Merge D3 theme with watermark config
                        const d3Theme = {json.dumps(config.get_d3_theme(), ensure_ascii=False)};
                        const watermarkConfig = {json.dumps(config.get_watermark_config(), ensure_ascii=False)};
                        window.theme = {{...d3Theme, ...watermarkConfig}};
                        window.dimensions = {json.dumps(dimensions, ensure_ascii=False)};
                        
                        console.log('Rendering graph:', window.graph_type, window.spec);
                        
                        {d3_renderers}
                        
                        // Use agent renderer for brace maps
                        if (window.graph_type === 'brace_map' && window.spec.success) {{
                            console.log('Using brace map agent renderer');
                            renderBraceMapAgent(window.spec, window.theme, window.dimensions);
                        }} else {{
                            renderGraph(window.graph_type, window.spec, window.theme, window.dimensions);
                        }}
                        
                        console.log('Graph rendering completed');
                    }} catch (error) {{
                        console.error('Render error:', error);
                        document.body.innerHTML += '<div style="color: red; padding: 20px;">Render error: ' + error.message + '</div>';
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
                
                # Log HTML size for debugging
                html_size = len(html)
                logger.info(f"HTML content size: {html_size} characters")
                if html_size > 100000:  # Log if HTML is very large
                    logger.warning(f"Large HTML content: {html_size} characters")
                
                await page.set_content(html)
                
                # Wait for rendering
                await asyncio.sleep(2.0)
                
                # Wait for rendering
                await asyncio.sleep(2.0)
                
                # Wait a bit more for rendering to complete
                await asyncio.sleep(1.0)
                
                # Check if SVG exists and has content
                element = await page.query_selector('svg')
                if element is None:
                    logger.error("SVG element not found in rendered page.")
                    # Log page content for debugging
                    page_content = await page.content()
                    logger.error(f"Page content: {page_content[:1000]}...")
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