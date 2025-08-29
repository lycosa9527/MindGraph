from flask import Blueprint, request, jsonify, send_file
from agents import main_agent as agent
import graph_specs
import logging
import tempfile
import asyncio
import re
import os
import atexit
import json
import time
import traceback
from werkzeug.exceptions import HTTPException
from functools import wraps
from settings import config

# URL configuration (fallback if urls module doesn't exist)
try:
    from urls import get_api_urls
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

# Shared agent enhancement functions to reduce code duplication
def enhance_mindmap_spec(spec):
    """Shared function to enhance mind map specs with layout data."""
    try:
        from agents.mind_maps.mind_map_agent import MindMapAgent
        m_agent = MindMapAgent()
        agent_result = m_agent.enhance_spec(spec)
        if agent_result.get('success') and 'spec' in agent_result:
            return agent_result['spec']
        else:
            logger.warning(f"MindMapAgent enhancement skipped: {agent_result.get('error')}")
            return spec
    except Exception as e:
        logger.error(f"Error enhancing mindmap spec: {e}")
        return spec

# Global timing tracking for rendering
rendering_timing_stats = {
    'total_renders': 0,
    'total_render_time': 0.0,
    'render_times': [],
    'last_render_time': 0.0,
    'llm_time_per_render': 0.0,
    'pure_render_time_per_render': 0.0
}

# ---------------------------------------------------------------------------
# Short-lived cache to avoid duplicate LLM runs between JSON and PNG endpoints
# Keyed by (prompt + language). Stores final agent result: {'spec', 'diagram_type', 'language'}
# ---------------------------------------------------------------------------
_LLM_RESULT_CACHE = {}
_LLM_CACHE_TTL_SECONDS = 300  # 5 minutes

def _llm_cache_key(prompt: str, language: str):
    try:
        return f"{language}:{prompt}".strip()
    except Exception:
        return f"{language}:".strip()

def _llm_cache_get(prompt: str, language: str):
    key = _llm_cache_key(prompt, language)
    entry = _LLM_RESULT_CACHE.get(key)
    if not entry:
        return None
    ts = entry.get('ts', 0)
    if (time.time() - ts) > _LLM_CACHE_TTL_SECONDS:
        try:
            del _LLM_RESULT_CACHE[key]
        except Exception:
            pass
        return None
    return entry.get('result')

def _llm_cache_set(prompt: str, language: str, result: dict):
    key = _llm_cache_key(prompt, language)
    _LLM_RESULT_CACHE[key] = {'ts': time.time(), 'result': result}

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

# Track generated images for DingTalk endpoint with timestamps
# Use file-based storage instead of in-memory dictionary for multi-process compatibility
dingtalk_images_file = os.path.join(tempfile.gettempdir(), 'dingtalk_images.json')

def _get_font_base64(font_filename):
    """Convert font file to base64 for embedding in HTML."""
    try:
        font_path = os.path.join(os.path.dirname(__file__), 'static', 'fonts', font_filename)
        if os.path.exists(font_path):
            with open(font_path, 'rb') as f:
                import base64
                return base64.b64encode(f.read()).decode('utf-8')
        else:
            logger.warning(f"Font file not found: {font_path}")
            return ""
    except Exception as e:
        logger.error(f"Failed to load font {font_filename}: {e}")
        return ""

def load_dingtalk_images():
    """Load DingTalk images tracking from file."""
    try:
        if os.path.exists(dingtalk_images_file):
            with open(dingtalk_images_file, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.warning(f"Failed to load DingTalk images tracking: {e}")
        return {}

def save_dingtalk_images(images_dict):
    """Save DingTalk images tracking to file."""
    try:
        with open(dingtalk_images_file, 'w') as f:
            json.dump(images_dict, f)
    except Exception as e:
        logger.error(f"Failed to save DingTalk images tracking: {e}")

def get_dingtalk_images():
    """Get current DingTalk images tracking."""
    return load_dingtalk_images()

def add_dingtalk_image(image_path, creation_time):
    """Add a new DingTalk image to tracking."""
    images = get_dingtalk_images()
    images[image_path] = creation_time
    save_dingtalk_images(images)

def remove_dingtalk_image(image_path):
    """Remove a DingTalk image from tracking."""
    images = get_dingtalk_images()
    if image_path in images:
        del images[image_path]
        save_dingtalk_images(images)

# Import threading for periodic cleanup
import threading

def cleanup_temp_files():
    """Clean up temporary files on exit."""
    for temp_file in temp_files:
        try:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
        except OSError:
            pass
    
    # Clean up DingTalk images
    for image_path in get_dingtalk_images():
        try:
            if os.path.exists(image_path):
                os.unlink(image_path)
        except OSError:
            pass

def cleanup_expired_dingtalk_images():
    """Clean up DingTalk images older than 24 hours."""
    current_time = time.time()
    expired_images = []
    
    for image_path, creation_time in get_dingtalk_images().items():
        if current_time - creation_time > 24 * 60 * 60:  # 24 hours in seconds
            expired_images.append(image_path)
    
    for image_path in expired_images:
        try:
            if os.path.exists(image_path):
                os.unlink(image_path)
                logger.info(f"Cleaned up expired DingTalk image: {image_path}")
        except OSError as e:
            logger.warning(f"Failed to clean up expired image {image_path}: {e}")
        finally:
            remove_dingtalk_image(image_path)
    
    # Schedule next cleanup in 24 hours
    timer = threading.Timer(24 * 60 * 60, cleanup_expired_dingtalk_images)
    timer.daemon = True
    timer.start()
    
    logger.info(f"Cleaned up {len(expired_images)} expired DingTalk images. Next cleanup scheduled in 24 hours.")

# Start the periodic cleanup when the module is imported
cleanup_timer = threading.Timer(24 * 60 * 60, cleanup_expired_dingtalk_images)
cleanup_timer.daemon = True
cleanup_timer.start()

# Register cleanup function for application exit
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
    # Debug-only endpoint: block in non-debug environments
    try:
        if not config.DEBUG:
            logger.warning("/api/generate_graph called in non-debug mode; returning 410 Gone. Use /api/generate_png instead.")
            resp = jsonify({'error': '/api/generate_graph is debug-only. Use /api/generate_png for image generation.'})
            return resp, 410
        else:
            logger.info("/api/generate_graph is running in DEBUG mode (debug-only endpoint)")
    except Exception:
        # If config.DEBUG isn't available for some reason, fail closed
        logger.warning("/api/generate_graph debug check failed; returning 410 Gone by default")
        resp = jsonify({'error': '/api/generate_graph is debug-only. Use /api/generate_png for image generation.'})
        return resp, 410
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
        # Try cache first to avoid duplicate LLM work for identical prompt/language
        cached = _llm_cache_get(prompt, language)
        if cached:
            logger.info("Cache hit for /generate_graph - returning cached spec")
            result = cached
        else:
            result = agent.agent_graph_workflow_with_styles(prompt, language)
            # Cache on success
            try:
                if isinstance(result, dict) and result.get('spec') and not result['spec'].get('error'):
                    _llm_cache_set(prompt, language, result)
            except Exception:
                pass
        
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
        
        # Optionally enhance spec using specialized agents FIRST
        if diagram_type == 'multi_flow_map':
            try:
                from agents.thinking_maps import MultiFlowMapAgent
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
                from agents.thinking_maps import FlowMapAgent
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
                from agents.thinking_maps import TreeMapAgent
                t_agent = TreeMapAgent()
                agent_result = t_agent.enhance_spec(spec)
                if agent_result.get('success') and 'spec' in agent_result:
                    spec = agent_result['spec']
                else:
                    logger.warning(f"TreeMapAgent enhancement skipped: {agent_result.get('error')}")
            except Exception as e:
                logger.error(f"Error enhancing tree_map spec: {e}")
        elif diagram_type == 'concept_map':
            try:
                from agents.concept_maps.concept_map_agent import ConceptMapAgent
                c_agent = ConceptMapAgent()
                agent_result = c_agent.enhance_spec(spec)
                if agent_result.get('success') and 'spec' in agent_result:
                    spec = agent_result['spec']
                else:
                    logger.warning(f"ConceptMapAgent enhancement skipped: {agent_result.get('error')}")
            except Exception as e:
                logger.error(f"Error enhancing concept_map spec: {e}")
        elif diagram_type == 'mindmap':
            spec = enhance_mindmap_spec(spec)
        elif diagram_type == 'bubble_map':
            try:
                from agents.thinking_maps import BubbleMapAgent
                b_agent = BubbleMapAgent()
                agent_result = b_agent.enhance_spec(spec)
                if agent_result.get('success') and 'spec' in agent_result:
                    spec = agent_result['spec']
                else:
                    logger.warning(f"BubbleMapAgent enhancement skipped: {agent_result.get('error')}")
            except Exception as e:
                logger.error(f"Error enhancing bubble_map spec: {e}")
        elif diagram_type == 'double_bubble_map':
            try:
                from agents.thinking_maps import DoubleBubbleMapAgent
                db_agent = DoubleBubbleMapAgent()
                agent_result = db_agent.enhance_spec(spec)
                if agent_result.get('success') and 'spec' in agent_result:
                    spec = agent_result['spec']
                else:
                    logger.warning(f"DoubleBubbleMapAgent enhancement skipped: {agent_result.get('error')}")
            except Exception as e:
                logger.error(f"Error enhancing double_bubble_map spec: {e}")
        elif diagram_type == 'circle_map':
            try:
                from agents.thinking_maps import CircleMapAgent
                c_agent = CircleMapAgent()
                agent_result = c_agent.enhance_spec(spec)
                if agent_result.get('success') and 'spec' in agent_result:
                    spec = agent_result['spec']
                else:
                    logger.warning(f"CircleMapAgent enhancement skipped: {agent_result.get('error')}")
            except Exception as e:
                logger.error(f"Error enhancing circle_map spec: {e}")
        elif diagram_type == 'bridge_map':
            try:
                logger.info("=== API BRIDGE MAP ENHANCEMENT START ===")
                logger.info(f"Input spec keys: {list(spec.keys()) if isinstance(spec, dict) else 'Not a dict'}")
                logger.info(f"Input spec type: {type(spec)}")
                
                from agents.thinking_maps import BridgeMapAgent
                br_agent = BridgeMapAgent()
                agent_result = br_agent.enhance_spec(spec)
                
                logger.info(f"BridgeMapAgent result: {agent_result}")
                
                if agent_result.get('success') and 'spec' in agent_result:
                    spec = agent_result['spec']
                    logger.info(f"Enhanced spec keys: {list(spec.keys())}")
                    logger.info(f"Enhanced analogies count: {len(spec.get('analogies', []))}")
                    
                    # Log each analogy for debugging
                    analogies = spec.get('analogies', [])
                    for i, analogy in enumerate(analogies):
                        logger.info(f"API analogy {i}: {analogy.get('left')} -> {analogy.get('right')}")
                else:
                    logger.warning(f"BridgeMapAgent enhancement skipped: {agent_result.get('error')}")
                
                logger.info("=== API BRIDGE MAP ENHANCEMENT COMPLETE ===")
            except Exception as e:
                logger.error(f"Error enhancing bridge_map spec: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")

        # Check for generation errors (keep this essential error handling)
        if isinstance(spec, dict) and spec.get('error'):
            return jsonify({'error': spec.get('error')}), 400

        # Calculate optimized dimensions
        dimensions = config.get_d3_dimensions()
        # Use agent-recommended dimensions if provided
        if diagram_type in ('multi_flow_map', 'flow_map', 'tree_map', 'concept_map', 'mindmap', 'bubble_map', 'double_bubble_map', 'circle_map', 'bridge_map') and isinstance(spec, dict) and spec.get('_recommended_dimensions'):
            rd = spec['_recommended_dimensions']
            try:
                dimensions = {
                    'baseWidth': rd.get('baseWidth', dimensions.get('baseWidth', 900)),
                    'baseHeight': rd.get('baseHeight', dimensions.get('baseHeight', 500)),
                    'padding': rd.get('padding', dimensions.get('padding', 40)),
                    'width': rd.get('width', rd.get('baseWidth', dimensions.get('baseWidth', 900))),
                    'height': rd.get('height', rd.get('baseHeight', dimensions.get('baseHeight', 500))),
                    'topicFontSize': dimensions.get('topicFontSize', 26),
                    'charFontSize': dimensions.get('charFontSize', 22)
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
        
        # === API DEBUG: FINAL RESPONSE TO FRONTEND ===
        if diagram_type == 'bridge_map':
            logger.info("=== API DEBUG: FINAL RESPONSE TO FRONTEND ===")
            logger.info(f"Final spec keys: {list(spec.keys())}")
            logger.info(f"Final analogies count: {len(spec.get('analogies', []))}")
            
            # Log each analogy being sent to frontend
            analogies = spec.get('analogies', [])
            for i, analogy in enumerate(analogies):
                logger.info(f"Frontend-bound analogy {i}: {analogy.get('left')} -> {analogy.get('right')}")
            
            logger.info(f"Dimensions being sent: {dimensions}")
            logger.info("=== API DEBUG: RESPONSE COMPLETE ===")
        
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
        # Prefer client-provided spec to avoid LLM call
        client_spec = data.get('spec') if isinstance(data, dict) else None
        result = None
        if isinstance(client_spec, dict) and client_spec:
            logger.info("/generate_png received client spec; skipping LLM workflow")
            result = {
                'spec': client_spec,
                'diagram_type': data.get('diagram_type', client_spec.get('diagram_type', 'concept_map')),
                'language': language
            }
        else:
            # Try cache next
            cached = _llm_cache_get(prompt, language)
            if cached:
                logger.info("Cache hit for /generate_png - using cached spec")
                result = cached
            else:
                result = agent.agent_graph_workflow_with_styles(prompt, language)
                # Cache on success
                try:
                    if isinstance(result, dict) and result.get('spec') and not result['spec'].get('error'):
                        _llm_cache_set(prompt, language, result)
                except Exception:
                    pass
        llm_time = time.time() - llm_start_time
        
        spec = result.get('spec', {})
        graph_type = result.get('diagram_type', 'bubble_map')
        
        logger.info(f"LLM processing completed in {llm_time:.3f}s")
    except Exception as e:
        logger.error(f"Agent workflow failed: {e}")
        return jsonify({'error': 'Failed to generate graph specification'}), 500
    
    # Check for generation errors (keep this essential error handling)
    if isinstance(spec, dict) and spec.get('error'):
        return jsonify({'error': spec.get('error')}), 400
    
    # Use brace map agent for brace maps
    if graph_type == 'brace_map':
        from agents.thinking_maps import BraceMapAgent
        brace_agent = BraceMapAgent()
        agent_result = brace_agent.generate_diagram(spec)
        if agent_result['success']:
            # CRITICAL FIX: Keep original spec structure and enhance it with agent data
            # This prevents breaking the JavaScript renderer which expects the original format
            enhanced_spec = spec.copy() if isinstance(spec, dict) else spec
            enhanced_spec['_agent_result'] = agent_result
            enhanced_spec['_layout_data'] = agent_result.get('layout_data')
            enhanced_spec['_svg_data'] = agent_result.get('svg_data')
            enhanced_spec['_optimal_dimensions'] = {
                'width': agent_result.get('svg_data', {}).get('width'),
                'height': agent_result.get('svg_data', {}).get('height')
            }
            spec = enhanced_spec
            logger.info(f"Enhanced brace map spec with agent data (original structure preserved)")
        else:
            logger.error(f"Brace map agent failed: {agent_result.get('error')}")
            return jsonify({'error': f"Brace map generation failed: {agent_result.get('error')}"}), 500
    elif graph_type == 'multi_flow_map':
        # Enhance multi-flow map spec and optionally use recommended dimensions later
        try:
            from agents.thinking_maps import MultiFlowMapAgent
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
            from agents.thinking_maps import FlowMapAgent
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
            from agents.thinking_maps import TreeMapAgent
            t_agent = TreeMapAgent()
            agent_result = t_agent.enhance_spec(spec)
            if agent_result.get('success') and 'spec' in agent_result:
                spec = agent_result['spec']
            else:
                logger.warning(f"TreeMapAgent enhancement skipped: {agent_result.get('error')}")
        except Exception as e:
            logger.error(f"Error enhancing tree_map spec: {e}")
    elif graph_type == 'concept_map':
        try:
            from agents.concept_maps.concept_map_agent import ConceptMapAgent
            c_agent = ConceptMapAgent()
            agent_result = c_agent.enhance_spec(spec)
            if agent_result.get('success') and 'spec' in agent_result:
                spec = agent_result['spec']
            else:
                logger.warning(f"ConceptMapAgent enhancement skipped: {agent_result.get('error')}")
        except Exception as e:
                            logger.error(f"Error enhancing concept_map spec: {e}")
    elif graph_type == 'mindmap':
        spec = enhance_mindmap_spec(spec)
    elif graph_type == 'bubble_map':
        try:
            from agents.thinking_maps import BubbleMapAgent
            b_agent = BubbleMapAgent()
            agent_result = b_agent.enhance_spec(spec)
            if agent_result.get('success') and 'spec' in agent_result:
                spec = agent_result['spec']
            else:
                logger.warning(f"BubbleMapAgent enhancement skipped: {agent_result.get('error')}")
        except Exception as e:
            logger.error(f"Error enhancing bubble_map spec: {e}")
    elif graph_type == 'double_bubble_map':
        try:
            from agents.thinking_maps import DoubleBubbleMapAgent
            db_agent = DoubleBubbleMapAgent()
            agent_result = db_agent.enhance_spec(spec)
            if agent_result.get('success') and 'spec' in agent_result:
                spec = agent_result['spec']
            else:
                logger.warning(f"DoubleBubbleMapAgent enhancement skipped: {agent_result.get('error')}")
        except Exception as e:
            logger.error(f"Error enhancing double_bubble_map spec: {e}")
    elif graph_type == 'circle_map':
        try:
            from agents.thinking_maps import CircleMapAgent
            c_agent = CircleMapAgent()
            agent_result = c_agent.enhance_spec(spec)
            if agent_result.get('success') and 'spec' in agent_result:
                spec = agent_result['spec']
            else:
                logger.warning(f"CircleMapAgent enhancement skipped: {agent_result.get('error')}")
        except Exception as e:
            logger.error(f"Error enhancing circle_map spec: {e}")
    elif graph_type == 'bridge_map':
        try:
            logger.info("=== PNG BRIDGE MAP ENHANCEMENT START ===")
            logger.info(f"Input spec keys: {list(spec.keys()) if isinstance(spec, dict) else 'Not a dict'}")
            logger.info(f"Input spec type: {type(spec)}")
            
            from agents.thinking_maps import BridgeMapAgent
            br_agent = BridgeMapAgent()
            agent_result = br_agent.enhance_spec(spec)
            
            logger.info(f"PNG BridgeMapAgent result: {agent_result}")
            
            if agent_result.get('success') and 'spec' in agent_result:
                spec = agent_result['spec']
                logger.info(f"PNG Enhanced spec keys: {list(spec.keys())}")
                logger.info(f"PNG Enhanced analogies count: {len(spec.get('analogies', []))}")
                
                # Log each analogy for debugging
                analogies = spec.get('analogies', [])
                for i, analogy in enumerate(analogies):
                    logger.info(f"PNG analogy {i}: {analogy.get('left')} -> {analogy.get('right')}")
            else:
                logger.warning(f"PNG BridgeMapAgent enhancement skipped: {agent_result.get('error')}")
            
            logger.info("=== PNG BRIDGE MAP ENHANCEMENT COMPLETE ===")
            
            # === PNG DEBUG: FINAL SPEC BEFORE RENDERING ===
            logger.info("=== PNG DEBUG: FINAL SPEC BEFORE RENDERING ===")
            logger.info(f"Final PNG spec keys: {list(spec.keys())}")
            logger.info(f"Final PNG analogies count: {len(spec.get('analogies', []))}")
            
            # Log each analogy before PNG rendering
            analogies = spec.get('analogies', [])
            for i, analogy in enumerate(analogies):
                logger.info(f"PNG rendering analogy {i}: {analogy.get('left')} -> {analogy.get('right')}")
            
            logger.info("=== PNG DEBUG: RENDERING START ===")
        except Exception as e:
            logger.error(f"Error enhancing bridge_map spec: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    # Render SVG and convert to PNG using Playwright
    try:
        import nest_asyncio
        nest_asyncio.apply()
        import json
        from playwright.async_api import async_playwright
        
        # Track rendering start time
        render_start_time = time.time()
        
        async def render_svg_to_png(spec, graph_type):
            # Import config for dimensions
            from settings import config
            
            # Use the old working approach - load D3 renderers directly
            try:
                # Load the theme configuration
                with open('static/js/theme-config.js', 'r', encoding='utf-8') as f:
                    theme_config = f.read()

                # Load the modular D3.js renderers
                renderer_files = [
                    'static/js/renderers/shared-utilities.js',
                    'static/js/renderers/renderer-dispatcher.js',
                    'static/js/renderers/mind-map-renderer.js',
                    'static/js/renderers/concept-map-renderer.js',
                    'static/js/renderers/bubble-map-renderer.js',
                    'static/js/renderers/tree-renderer.js',
                    'static/js/renderers/flow-renderer.js',
                    'static/js/renderers/brace-renderer.js'
                ]
                
                d3_renderers = ''
                for renderer_file in renderer_files:
                    try:
                        with open(renderer_file, 'r', encoding='utf-8') as f:
                            d3_renderers += f.read() + '\n\n'
                    except FileNotFoundError:
                        logger.warning(f"Renderer file not found: {renderer_file}")
                        continue

                # Load the style manager
                with open('static/js/style-manager.js', 'r', encoding='utf-8') as f:
                    style_manager = f.read()
                
                # Use the old working approach - single script tag
                renderer_scripts = f'<script>{d3_renderers}</script>'
                
                logger.info(f"Loading modular D3 renderers for {graph_type}")
                
                # Debug: Log layout information for concept maps
                if graph_type == 'concept_map' and isinstance(spec, dict):
                    layout_info = spec.get('_layout', {})
                    algorithm = layout_info.get('algorithm', 'unknown')
                    logger.info(f"=== CONCEPT MAP LAYOUT DEBUG ===")
                    logger.info(f"Layout algorithm: {algorithm}")
                    logger.info(f"Layout keys: {list(layout_info.keys())}")
                    if 'positions' in layout_info:
                        pos_count = len(layout_info['positions'])
                        logger.info(f"Position count: {pos_count}")
                    if 'rings' in layout_info:
                        ring_count = len(layout_info['rings'])
                        logger.info(f"Ring count: {ring_count}")
                    if 'clusters' in layout_info:
                        cluster_count = len(layout_info['clusters'])
                        logger.info(f"Cluster count: {cluster_count}")
                    logger.info(f"=== END LAYOUT DEBUG ===")
                
            except Exception as e:
                logger.error(f"Failed to load D3 renderers for {graph_type}: {e}")
                raise ValueError(f"Failed to load required JavaScript for {graph_type}")
            
            # Log spec data summary for debugging
            if isinstance(spec, dict):
                spec_keys = list(spec.keys())
                svg_info = ""
                if 'svg_data' in spec and isinstance(spec['svg_data'], dict):
                    svg_keys = list(spec['svg_data'].keys())
                    element_count = len(spec['svg_data'].get('elements', [])) if 'elements' in spec['svg_data'] else 0
                    svg_info = f", svg_data: {svg_keys}, elements: {element_count}"
                logger.info(f"Spec data: {spec_keys}{svg_info}")
            else:
                logger.info("Spec data: Not a dict")
            
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
                    'topicFontSize': dimensions.get('topicFontSize', 26),
                    'charFontSize': dimensions.get('charFontSize', 22)
                }
            elif graph_type == 'brace_map' and spec:
                # Check for enhanced spec format first (new format)
                optimal_dims = spec.get('_optimal_dimensions', {})
                svg_data = spec.get('_svg_data', {})
                
                # Use enhanced format dimensions if available
                if optimal_dims and optimal_dims.get('width') and optimal_dims.get('height'):
                    dimensions = {
                        'baseWidth': optimal_dims['width'],
                        'baseHeight': optimal_dims['height'],
                        'padding': 50,
                        'width': optimal_dims['width'],
                        'height': optimal_dims['height'],
                        'topicFontSize': dimensions.get('topicFontSize', 20),
                        'partFontSize': dimensions.get('partFontSize', 16),
                        'subpartFontSize': dimensions.get('subpartFontSize', 14)
                    }
                    logger.info(f"Using enhanced spec optimal dimensions: {optimal_dims['width']}x{optimal_dims['height']}")
                # Legacy format fallback
                elif spec.get('success') and svg_data and 'width' in svg_data and 'height' in svg_data:
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
                    logger.info(f"Using legacy format optimal dimensions: {svg_data['width']}x{svg_data['height']}")
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
            elif graph_type in ('multi_flow_map', 'flow_map', 'tree_map', 'concept_map') and isinstance(spec, dict):
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
            
            # Read local D3.js content for embedding in PNG generation
            d3_js_path = os.path.join(os.path.dirname(__file__), 'static', 'js', 'd3.min.js')
            try:
                with open(d3_js_path, 'r', encoding='utf-8') as f:
                    d3_js_content = f.read()
                logger.info(f"Local D3.js loaded for PNG generation ({len(d3_js_content)} bytes)")
                d3_script_tag = f'<script>{d3_js_content}</script>'
            except Exception as e:
                logger.error(f"Failed to load local D3.js: {e}")
                raise RuntimeError(f"Local D3.js library not available at {d3_js_path}. Please ensure the D3.js bundle is properly installed.")
            
            html = f'''
            <html><head>
            <meta charset="utf-8">
            {d3_script_tag}
            <style>
                body {{ margin:0; background:#fff; }}
                #d3-container {{ 
                    width: 100%; 
                    height: 100vh; 
                    display: block; 
                    /* background: #f0f0f0; */  /* Removed to fix concept map visibility */
                }}
                
                /* Inter Font Loading for Ubuntu Server Compatibility */
                @font-face {{
                    font-display: swap;
                    font-family: 'Inter';
                    font-style: normal;
                    font-weight: 300;
                    src: url('data:font/truetype;base64,{_get_font_base64("inter-300.ttf")}') format('truetype');
                }}
                @font-face {{
                    font-display: swap;
                    font-family: 'Inter';
                    font-style: normal;
                    font-weight: 400;
                    src: url('data:font/truetype;base64,{_get_font_base64("inter-400.ttf")}') format('truetype');
                }}
                @font-face {{
                    font-display: swap;
                    font-family: 'Inter';
                    font-style: normal;
                    font-weight: 500;
                    src: url('data:font/truetype;base64,{_get_font_base64("inter-500.ttf")}') format('truetype');
                }}
                @font-face {{
                    font-display: swap;
                    font-family: 'Inter';
                    font-style: normal;
                    font-weight: 600;
                    src: url('data:font/truetype;base64,{_get_font_base64("inter-600.ttf")}') format('truetype');
                }}
                @font-face {{
                    font-display: swap;
                    font-family: 'Inter';
                    font-style: normal;
                    font-weight: 700;
                    src: url('data:font/truetype;base64,{_get_font_base64("inter-700.ttf")}') format('truetype');
                }}
            </style>
            </head><body>
            <div id="d3-container"></div>
            
            <!-- Theme Configuration -->
            <script>
            {theme_config}
            </script>
            
            <!-- Style Manager -->
            <script>
            {style_manager}
            </script>
            
            <!-- Modular D3 Renderers (Loaded in dependency order) -->
            {renderer_scripts}
            
            <!-- Main Rendering Logic -->
            <script>
            console.log("Page loaded, waiting for D3.js...");
            console.log("Debug: Checking module availability...");
            
            // Debug: Check what modules are loaded
            setTimeout(() => {{
                console.log("Debug: Module availability check:");
                console.log("  - renderTreeMap:", typeof renderTreeMap);
                console.log("  - TreeRenderer:", typeof TreeRenderer);
                console.log("  - MindGraphUtils:", typeof MindGraphUtils);
                console.log("  - addWatermark:", typeof addWatermark);
                console.log("  - styleManager:", typeof styleManager);
                console.log("  - renderGraph:", typeof renderGraph);
                
                if (window.TreeRenderer) {{
                    console.log("  - TreeRenderer.renderTreeMap:", typeof window.TreeRenderer.renderTreeMap);
                }}
                if (window.MindGraphUtils) {{
                    console.log("  - MindGraphUtils.addWatermark:", typeof window.MindGraphUtils.addWatermark);
                }}
            }}, 1000);
            
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
                        if (window.graph_type === "brace_map") {{
                            console.log("Using brace map agent renderer");
                            console.log("Debug: window.spec:", window.spec);
                            console.log("Debug: spec keys:", Object.keys(window.spec || {{}}));
                            
                            // Handle both enhanced format (with original structure) and legacy formats
                            const hasValidSpec = window.spec && (
                                (window.spec.topic && Array.isArray(window.spec.parts)) || // Enhanced format
                                window.spec.success || // Legacy format
                                window.spec.data || window.spec.svg_data || window.spec.layout_data
                            );
                            
                            console.log("Debug: hasValidSpec:", hasValidSpec);
                            console.log("Debug: renderBraceMap available:", typeof renderBraceMap);
                            console.log("Debug: BraceRenderer available:", typeof window.BraceRenderer);
                            
                            if (hasValidSpec) {{
                                if (typeof renderBraceMap === "function") {{
                                    console.log("Calling global renderBraceMap function");
                                    try {{
                                        renderBraceMap(window.spec, backendTheme, window.dimensions);
                                        console.log("renderBraceMap completed successfully");
                                    }} catch (error) {{
                                        console.error("Error in renderBraceMap:", error);
                                        document.body.innerHTML += "<div style=\\"color: red; padding: 20px;\\">Render error: " + error.message + "</div>";
                                    }}
                                }} else if (typeof window.BraceRenderer !== "undefined" && typeof window.BraceRenderer.renderBraceMap === "function") {{
                                    console.log("Calling BraceRenderer.renderBraceMap function");
                                    try {{
                                        window.BraceRenderer.renderBraceMap(window.spec, backendTheme, window.dimensions);
                                        console.log("BraceRenderer.renderBraceMap completed successfully");
                                    }} catch (error) {{
                                        console.error("Error in BraceRenderer.renderBraceMap:", error);
                                        document.body.innerHTML += "<div style=\\"color: red; padding: 20px;\\">Render error: " + error.message + "</div>";
                                    }}
                                }} else {{
                                    console.error("renderBraceMap function not available");
                                    document.body.innerHTML += "<div style=\\"color: red; padding: 20px;\\">Brace map renderer not loaded</div>";
                                }}
                            }} else {{
                                console.error("Invalid brace map specification");
                                document.body.innerHTML += "<div style=\\"color: red; padding: 20px;\\">Invalid brace map specification</div>";
                            }}
                        }} else if (window.graph_type === "flow_map") {{
                            console.log("Using flow map renderer directly");
                            if (typeof renderFlowMap === "function") {{
                                renderFlowMap(window.spec, backendTheme, window.dimensions);
                            }} else {{
                                console.error("renderFlowMap function not available");
                                document.body.innerHTML += "<div style=\\"color: red; padding: 20px;\\">Flow map renderer not loaded</div>";
                            }}
                        }} else if (window.graph_type === "concept_map") {{
                            console.log("Using concept map renderer directly");
                            if (typeof renderConceptMap === "function") {{
                                renderConceptMap(window.spec, backendTheme, window.dimensions);
                            }} else {{
                                console.error("renderConceptMap function not available");
                                document.body.innerHTML += "<div style=\\"color: red; padding: 20px;\\">Concept map renderer not loaded</div>";
                            }}
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
            # Get browser context from pool for optimal performance
            # According to Playwright best practices:
            # - Each isolated operation should have its own browser context
            # - Contexts cannot cross event loop boundaries
            # - For PNG generation, create a fresh context each time
            # - Reference: https://playwright.dev/docs/browser-contexts#isolation
            
            logger.info("DEBUG: Creating fresh browser context for PNG generation (following Playwright isolation principles)")
            
            # Create a fresh browser instance and context for this PNG generation
            # This ensures proper isolation and event loop compatibility
            from playwright.async_api import async_playwright
            playwright = await async_playwright().start()
            
            browser = await playwright.chromium.launch()
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='MindGraph PNG Generator/1.0',
                java_script_enabled=True,
                ignore_https_errors=True
            )
            
            logger.info(f"DEBUG: Fresh context created - type: {type(context)}, id: {id(context)}")
            
            try:
                # Use the fresh context for PNG generation
                page = await context.new_page()
                
                # Set timeout to 60 seconds for all content
                page.set_default_timeout(60000)  # 60 seconds default
                page.set_default_navigation_timeout(60000)
                
                # Set up console and error logging BEFORE loading content
                console_messages = []
                page_errors = []
                
                page.on("console", lambda msg: console_messages.append(f"{msg.type}: {msg.text}"))
                page.on("pageerror", lambda err: page_errors.append(str(err)))
                
                # Set timeout and log HTML size if large
                html_size = len(html)
                timeout_ms = 60000  # 60 seconds for all content
                if html_size > 100000:  # Log if HTML is very large
                    logger.info(f"Large HTML content: {html_size} characters, setting timeout to {timeout_ms}ms")
                
                await page.set_content(html, timeout=timeout_ms)
                
                # Wait for rendering and check for console errors
                logger.info("Waiting for initial rendering...")
                await asyncio.sleep(2.0)  # Reduced from 5.0 to 2.0 seconds
                
                # Log console messages and errors (consolidated)
                if console_messages:
                    logger.info(f"Browser console messages: {len(console_messages)}")
                    # Log the actual console messages for debugging
                    for i, msg in enumerate(console_messages[-10:]):  # Last 10 messages
                        logger.info(f"Console {i+1}: {msg}")
                if page_errors:
                    logger.error(f"Browser errors: {len(page_errors)}")
                    for i, error in enumerate(page_errors):
                        logger.error(f"Browser Error {i+1}: {error}")
                
                # Wait for rendering to complete with dynamic timing based on graph complexity
                logger.info("Waiting for rendering to complete...")
                
                # Simple wait for rendering to complete (no more complex calculations)
                await asyncio.sleep(3.0)  # Reduced from 6.0 to 3.0 seconds
                
                # Check what functions are actually available in the browser
                try:
                    function_check = await page.evaluate("""
                        () => {
                            const functions = {};
                            functions.renderTreeMap = typeof renderTreeMap;
                            functions.TreeRenderer = typeof TreeRenderer;
                            functions.MindGraphUtils = typeof MindGraphUtils;
                            functions.addWatermark = typeof addWatermark;
                            functions.styleManager = typeof styleManager;
                            functions.d3 = typeof d3;
                            functions.renderGraph = typeof renderGraph;
                            
                            // Check if specific objects exist
                            if (window.TreeRenderer) {
                                functions.TreeRenderer_renderTreeMap = typeof window.TreeRenderer.renderTreeMap;
                            }
                            if (window.MindGraphUtils) {
                                functions.MindGraphUtils_addWatermark = typeof window.MindGraphUtils.addWatermark;
                            }
                            
                            return functions;
                        }
                    """)
                    logger.info(f"Function availability check: {function_check}")
                except Exception as e:
                    logger.error(f"Failed to check function availability: {e}")
                
                # Wait for SVG element to be created with timeout and content
                try:
                    element = await page.wait_for_selector("svg", timeout=15000)  # Increased timeout
                    logger.info("SVG element found successfully")
                    
                    # Wait for SVG to actually contain content (not just empty)
                    logger.info("Waiting for SVG content to render...")
                    for attempt in range(10):  # Try up to 10 times
                        svg_content = await element.inner_html()
                        if svg_content.strip() and len(svg_content) > 100:  # SVG has substantial content
                            logger.info(f"SVG content rendered successfully (length: {len(svg_content)})")
                            # Log a sample of the SVG content for debugging
                            if attempt == 0:  # Only log on first successful attempt
                                svg_sample = svg_content[:500] + "..." if len(svg_content) > 500 else svg_content
                                logger.info(f"SVG content sample: {svg_sample}")
                            break
                        elif attempt < 9:  # Don't sleep on last attempt
                            logger.info(f"SVG content not ready yet (attempt {attempt + 1}/10), waiting...")
                            await asyncio.sleep(1.0)
                        else:
                            logger.warning("SVG content may not be fully rendered")
                            # Log what we got for debugging
                            if svg_content:
                                logger.warning(f"Final SVG content (may be incomplete): {svg_content[:200]}...")
                            else:
                                logger.warning("SVG content is completely empty")
                    
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
                
                # Final wait to ensure all rendering is complete
                logger.info("Final wait for rendering completion...")
                await asyncio.sleep(1.0)  # Reduced from 2.0 to 1.0 seconds
                
                # Ensure element is visible before screenshot
                await element.scroll_into_view_if_needed()
                await page.wait_for_timeout(500)  # Reduced from 1000 to 500ms
                
                png_bytes = await element.screenshot(omit_background=False, timeout=60000)
                return png_bytes
            finally:
                # Clean up resources properly
                logger.info("DEBUG: Cleaning up PNG generation resources")
                try:
                    if 'page' in locals():
                        await page.close()
                        logger.info("DEBUG: Page closed")
                    if 'context' in locals():
                        await context.close()
                        logger.info("DEBUG: Context closed")
                    if 'browser' in locals():
                        await browser.close()
                        logger.info("DEBUG: Browser closed")
                    if 'playwright' in locals():
                        await playwright.stop()
                        logger.info("DEBUG: Playwright stopped")
                except Exception as cleanup_error:
                    logger.warning(f"DEBUG: Error during cleanup: {cleanup_error}")
        
        # Close the async function definition
        # Now call the async function with proper event loop handling
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                # If the loop is closed, we need to create a new one for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            png_bytes = loop.run_until_complete(render_svg_to_png(spec, graph_type))
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                # Fallback: create a new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                png_bytes = loop.run_until_complete(render_svg_to_png(spec, graph_type))
            else:
                raise
        
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


@api.route('/generate_dingtalk', methods=['POST'])
@handle_api_errors
def generate_dingtalk():
    """Generate PNG image for DingTalk platform and return data for integration."""
    # Input validation
    data = request.json
    valid, msg = validate_request_data(data, ['prompt'])
    if not valid:
        return f"❌ 请求验证失败：{msg}", 400
    
    prompt = sanitize_prompt(data['prompt'])
    if not prompt:
        return "❌ 提示词无效或为空", 400
    
    language = data.get('language', 'zh')
    if not isinstance(language, str) or language not in ['zh', 'en']:
        return "❌ 语言无效。必须是 'zh' 或 'en'", 400
    
    logger.info(f"DingTalk /generate_dingtalk: prompt={prompt!r}, language={language!r}")
    
    # Track timing for the entire process
    total_start_time = time.time()
    
    # Generate graph specification using the same workflow as generate_png
    try:
        llm_start_time = time.time()
        result = agent.agent_graph_workflow_with_styles(prompt, language)
        llm_time = time.time() - llm_start_time
        
        spec = result.get('spec', {})
        graph_type = result.get('diagram_type', 'bubble_map')
        
        logger.info(f"LLM processing completed in {llm_time:.3f}s")
    except Exception as e:
        logger.error(f"Agent workflow failed: {e}")
        return f"❌ 图表规格生成失败：{str(e)}", 500
    
    # Check for generation errors (keep this essential error handling)
    if isinstance(spec, dict) and spec.get('error'):
        return f"❌ 图表规格验证失败：{spec.get('error')}", 400
    
    # Use brace map agent for brace maps
    if graph_type == 'brace_map':
        from agents.thinking_maps import BraceMapAgent
        brace_agent = BraceMapAgent()
        agent_result = brace_agent.generate_diagram(spec)
        if agent_result['success']:
            # CRITICAL FIX: Keep original spec structure and enhance it with agent data
            # This prevents breaking the JavaScript renderer which expects the original format
            enhanced_spec = spec.copy() if isinstance(spec, dict) else spec
            enhanced_spec['_agent_result'] = agent_result
            enhanced_spec['_layout_data'] = agent_result.get('layout_data')
            enhanced_spec['_svg_data'] = agent_result.get('svg_data')
            enhanced_spec['_optimal_dimensions'] = {
                'width': agent_result.get('svg_data', {}).get('width'),
                'height': agent_result.get('svg_data', {}).get('height')
            }
            spec = enhanced_spec
            logger.info(f"Enhanced brace map spec with agent data (original structure preserved)")
        else:
            logger.error(f"Brace map agent failed: {agent_result.get('error')}")
            return jsonify({
                "msgtype": "text",
                "text": {
                    "content": f"❌ 括号图生成失败：{agent_result.get('error')}"
                }
            }), 500
    elif graph_type == 'multi_flow_map':
        # Enhance multi-flow map spec and optionally use recommended dimensions later
        try:
            from agents.thinking_maps import MultiFlowMapAgent
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
            from agents.thinking_maps import FlowMapAgent
            f_agent = FlowMapAgent()
            agent_result = f_agent.enhance_spec(spec)
            if agent_result.get('success') and 'spec' in agent_result:
                spec = agent_result['spec']
            else:
                logger.warning(f"FlowMapAgent enhancement skipped: {agent_result.get('error')}")
        except Exception as e:
            logger.error(f"Error enhancing flow_map spec: {e}")
    elif graph_type == 'mindmap':
        spec = enhance_mindmap_spec(spec)
    elif graph_type == 'bubble_map':
        try:
            from agents.thinking_maps import BubbleMapAgent
            b_agent = BubbleMapAgent()
            agent_result = b_agent.enhance_spec(spec)
            if agent_result.get('success') and 'spec' in agent_result:
                spec = agent_result['spec']
            else:
                logger.warning(f"BubbleMapAgent enhancement skipped: {agent_result.get('error')}")
        except Exception as e:
            logger.error(f"Error enhancing bubble_map spec: {e}")
    elif graph_type == 'double_bubble_map':
        try:
            from agents.thinking_maps import DoubleBubbleMapAgent
            db_agent = DoubleBubbleMapAgent()
            agent_result = db_agent.enhance_spec(spec)
            if agent_result.get('success') and 'spec' in agent_result:
                spec = agent_result['spec']
            else:
                logger.warning(f"DoubleBubbleMapAgent enhancement skipped: {agent_result.get('error')}")
        except Exception as e:
            logger.error(f"Error enhancing double_bubble_map spec: {e}")
    elif graph_type == 'circle_map':
        try:
            from agents.thinking_maps import CircleMapAgent
            c_agent = CircleMapAgent()
            agent_result = c_agent.enhance_spec(spec)
            if agent_result.get('success') and 'spec' in agent_result:
                spec = agent_result['spec']
            else:
                logger.warning(f"CircleMapAgent enhancement skipped: {agent_result.get('error')}")
        except Exception as e:
            logger.error(f"Error enhancing circle_map spec: {e}")
    elif graph_type == 'bridge_map':
        try:
            from agents.thinking_maps import BridgeMapAgent
            br_agent = BridgeMapAgent()
            agent_result = br_agent.enhance_spec(spec)
            if agent_result.get('success') and 'spec' in agent_result:
                spec = agent_result['spec']
            else:
                logger.warning(f"BridgeMapAgent enhancement skipped: {agent_result.get('error')}")
        except Exception as e:
            logger.error(f"Error enhancing bridge_map spec: {e}")
    
    # Render SVG and convert to PNG using Playwright
    try:
        import nest_asyncio
        nest_asyncio.apply()
        import json
        from playwright.async_api import async_playwright
        
        # Track rendering start time
        render_start_time = time.time()
        
        async def render_svg_to_png(spec, graph_type):
            # Import config for dimensions
            from settings import config
            
            # Use the old working approach - load D3 renderers directly
            try:
                # Load the theme configuration
                with open('static/js/theme-config.js', 'r', encoding='utf-8') as f:
                    theme_config = f.read()

                # Load the modular D3.js renderers
                renderer_files = [
                    'static/js/renderers/shared-utilities.js',
                    'static/js/renderers/renderer-dispatcher.js',
                    'static/js/renderers/mind-map-renderer.js',
                    'static/js/renderers/concept-map-renderer.js',
                    'static/js/renderers/bubble-map-renderer.js',
                    'static/js/renderers/tree-renderer.js',
                    'static/js/renderers/flow-renderer.js',
                    'static/js/renderers/brace-renderer.js'
                ]
                
                d3_renderers = ''
                for renderer_file in renderer_files:
                    try:
                        with open(renderer_file, 'r', encoding='utf-8') as f:
                            d3_renderers += f.read() + '\n\n'
                    except FileNotFoundError:
                        logger.warning(f"Renderer file not found: {renderer_file}")
                        continue

                # Load the style manager
                with open('static/js/style-manager.js', 'r', encoding='utf-8') as f:
                    style_manager = f.read()
                
                # Use the old working approach - single script tag
                renderer_scripts = f'<script>{d3_renderers}</script>'
                
                logger.info(f"Loading modular D3 renderers for {graph_type}")
                
                # Debug: Log layout information for concept maps
                if graph_type == 'concept_map' and isinstance(spec, dict):
                    layout_info = spec.get('_layout', {})
                    algorithm = layout_info.get('algorithm', 'unknown')
                    logger.info(f"=== CONCEPT MAP LAYOUT DEBUG ===")
                    logger.info(f"Layout algorithm: {algorithm}")
                    logger.info(f"Layout keys: {list(layout_info.keys())}")
                    if 'positions' in layout_info:
                        pos_count = len(layout_info['positions'])
                        logger.info(f"Position count: {pos_count}")
                    if 'rings' in layout_info:
                        ring_count = len(layout_info['rings'])
                        logger.info(f"Ring count: {ring_count}")
                    if 'clusters' in layout_info:
                        cluster_count = len(layout_info['clusters'])
                        logger.info(f"Cluster count: {cluster_count}")
                    logger.info(f"=== END LAYOUT DEBUG ===")
                
            except Exception as e:
                logger.error(f"Failed to load D3 renderers for {graph_type}: {e}")
                raise ValueError(f"Failed to load required JavaScript for {graph_type}")
            
            # Log spec data summary for debugging
            if isinstance(spec, dict):
                spec_keys = list(spec.keys())
                svg_info = ""
                if 'svg_data' in spec and isinstance(spec['svg_data'], dict):
                    svg_keys = list(spec['svg_data'].keys())
                    element_count = len(spec['svg_data'].get('elements', [])) if 'elements' in spec['svg_data'] else 0
                    svg_info = f", svg_data: {svg_keys}, elements: {element_count}"
                logger.info(f"Spec data: {spec_keys}{svg_info}")
            else:
                logger.info("Spec data: Not a dict")
            
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
                    'topicFontSize': dimensions.get('topicFontSize', 26),
                    'charFontSize': dimensions.get('charFontSize', 22)
                }
            elif graph_type == 'brace_map' and spec:
                # Check for enhanced spec format first (new format)
                optimal_dims = spec.get('_optimal_dimensions', {})
                svg_data = spec.get('_svg_data', {})
                
                # Use enhanced format dimensions if available
                if optimal_dims and optimal_dims.get('width') and optimal_dims.get('height'):
                    dimensions = {
                        'baseWidth': optimal_dims['width'],
                        'baseHeight': optimal_dims['height'],
                        'padding': 50,
                        'width': optimal_dims['width'],
                        'height': optimal_dims['height'],
                        'topicFontSize': dimensions.get('topicFontSize', 20),
                        'partFontSize': dimensions.get('partFontSize', 16),
                        'subpartFontSize': dimensions.get('subpartFontSize', 14)
                    }
                    logger.info(f"Using enhanced spec optimal dimensions: {optimal_dims['width']}x{optimal_dims['height']}")
                # Legacy format fallback
                elif spec.get('success') and svg_data and 'width' in svg_data and 'height' in svg_data:
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
                    logger.info(f"Using legacy format optimal dimensions: {svg_data['width']}x{svg_data['height']}")
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
            elif graph_type in ('multi_flow_map', 'flow_map', 'tree_map', 'concept_map') and isinstance(spec, dict):
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
            
            # Read local D3.js content for embedding in PNG generation
            d3_js_path = os.path.join(os.path.dirname(__file__), 'static', 'js', 'd3.min.js')
            try:
                with open(d3_js_path, 'r', encoding='utf-8') as f:
                    d3_js_content = f.read()
                logger.info(f"Local D3.js loaded for PNG generation ({len(d3_js_content)} bytes)")
                d3_script_tag = f'<script>{d3_js_content}</script>'
            except Exception as e:
                logger.error(f"Failed to load local D3.js: {e}")
                raise RuntimeError(f"Local D3.js library not available at {d3_js_path}. Please ensure the D3.js bundle is properly installed.")
            
            html = f'''
            <html><head>
            <meta charset="utf-8">
            {d3_script_tag}
            <style>
                body {{ margin:0; background:#fff; }}
                #d3-container {{ 
                    width: 100%; 
                    height: 100vh; 
                    display: block; 
                    /* background: #f0f0f0; */  /* Removed to fix concept map visibility */
                }}
                
                /* Inter Font Loading for Ubuntu Server Compatibility */
                @font-face {{
                    font-display: swap;
                    font-family: 'Inter';
                    font-style: normal;
                    font-weight: 300;
                    src: url('data:font/truetype;base64,{_get_font_base64("inter-300.ttf")}') format('truetype');
                }}
                @font-face {{
                    font-display: swap;
                    font-family: 'Inter';
                    font-style: normal;
                    font-weight: 400;
                    src: url('data:font/truetype;base64,{_get_font_base64("inter-400.ttf")}') format('truetype');
                }}
                @font-face {{
                    font-display: swap;
                    font-family: 'Inter';
                    font-style: normal;
                    font-weight: 500;
                    src: url('data:font/truetype;base64,{_get_font_base64("inter-500.ttf")}') format('truetype');
                }}
                @font-face {{
                    font-display: swap;
                    font-family: 'Inter';
                    font-style: normal;
                    font-weight: 600;
                    src: url('data:font/truetype;base64,{_get_font_base64("inter-600.ttf")}') format('truetype');
                }}
                @font-face {{
                    font-display: swap;
                    font-family: 'Inter';
                    font-style: normal;
                    font-weight: 700;
                    src: url('data:font/truetype;base64,{_get_font_base64("inter-700.ttf")}') format('truetype');
                }}
            </style>
            </head><body>
            <div id="d3-container"></div>
            
            <!-- Theme Configuration -->
            <script>
            {theme_config}
            </script>
            
            <!-- Style Manager -->
            <script>
            {style_manager}
            </script>
            
            <!-- Modular D3 Renderers (Loaded in dependency order) -->
            {renderer_scripts}
            
            <!-- Main Rendering Logic -->
            <script>
            console.log("Page loaded, waiting for D3.js...");
            console.log("Debug: Checking module availability...");
            
            // Debug: Check what modules are loaded
            setTimeout(() => {{
                console.log("Debug: Module availability check:");
                console.log("  - renderTreeMap:", typeof renderTreeMap);
                console.log("  - TreeRenderer:", typeof TreeRenderer);
                console.log("  - MindGraphUtils:", typeof MindGraphUtils);
                console.log("  - addWatermark:", typeof addWatermark);
                console.log("  - styleManager:", typeof styleManager);
                console.log("  - renderGraph:", typeof renderGraph);
                
                if (window.TreeRenderer) {{
                    console.log("  - TreeRenderer.renderTreeMap:", typeof window.TreeRenderer.renderTreeMap);
                }}
                if (window.MindGraphUtils) {{
                    console.log("  - MindGraphUtils.addWatermark:", typeof window.MindGraphUtils.addWatermark);
                }}
            }}, 1000);
            
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
                        if (window.graph_type === "brace_map") {{
                            console.log("Using brace map agent renderer");
                            console.log("Debug: window.spec:", window.spec);
                            console.log("Debug: spec keys:", Object.keys(window.spec || {{}}));
                            
                            // Handle both enhanced format (with original structure) and legacy formats
                            const hasValidSpec = window.spec && (
                                (window.spec.topic && Array.isArray(window.spec.parts)) || // Enhanced format
                                window.spec.success || // Legacy format
                                window.spec.data || window.spec.svg_data || window.spec.layout_data
                            );
                            
                            console.log("Debug: hasValidSpec:", hasValidSpec);
                            console.log("Debug: renderBraceMap available:", typeof renderBraceMap);
                            console.log("Debug: BraceRenderer available:", typeof window.BraceRenderer);
                            
                            if (hasValidSpec) {{
                                if (typeof renderBraceMap === "function") {{
                                    console.log("Calling global renderBraceMap function");
                                    try {{
                                        renderBraceMap(window.spec, backendTheme, window.dimensions);
                                        console.log("renderBraceMap completed successfully");
                                    }} catch (error) {{
                                        console.error("Error in renderBraceMap:", error);
                                        document.body.innerHTML += "<div style=\\"color: red; padding: 20px;\\">Render error: " + error.message + "</div>";
                                    }}
                                }} else if (typeof window.BraceRenderer !== "undefined" && typeof window.BraceRenderer.renderBraceMap === "function") {{
                                    console.log("Calling BraceRenderer.renderBraceMap function");
                                    try {{
                                        window.BraceRenderer.renderBraceMap(window.spec, backendTheme, window.dimensions);
                                        console.log("BraceRenderer.renderBraceMap completed successfully");
                                    }} catch (error) {{
                                        console.error("Error in BraceRenderer.renderBraceMap:", error);
                                        document.body.innerHTML += "<div style=\\"color: red; padding: 20px;\\">Render error: " + error.message + "</div>";
                                    }}
                                }} else {{
                                    console.error("renderBraceMap function not available");
                                    document.body.innerHTML += "<div style=\\"color: red; padding: 20px;\\">Brace map renderer not loaded</div>";
                                }}
                            }} else {{
                                console.error("Invalid brace map specification");
                                document.body.innerHTML += "<div style=\\"color: red; padding: 20px;\\">Invalid brace map specification</div>";
                            }}
                        }} else if (window.graph_type === "flow_map") {{
                            console.log("Using flow map renderer directly");
                            if (typeof renderFlowMap === "function") {{
                                renderFlowMap(window.spec, backendTheme, window.dimensions);
                            }} else {{
                                console.error("renderFlowMap function not available");
                                document.body.innerHTML += "<div style=\\"color: red; padding: 20px;\\">Flow map renderer not loaded</div>";
                            }}
                        }} else if (window.graph_type === "concept_map") {{
                            console.log("Using concept map renderer directly");
                            if (typeof renderConceptMap === "function") {{
                                renderConceptMap(window.spec, backendTheme, window.dimensions);
                            }} else {{
                                console.error("renderConceptMap function not available");
                                document.body.innerHTML += "<div style=\\"color: red; padding: 20px;\\">Concept map renderer not loaded</div>";
                            }}
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
            # Get browser context from pool for optimal performance
            # According to Playwright best practices:
            # - Each isolated operation should have its own browser context
            # - Contexts cannot cross event loop boundaries
            # - For PNG generation, create a fresh context each time
            # - Reference: https://playwright.dev/docs/browser-contexts#isolation
            
            logger.info("DEBUG: Creating fresh browser context for PNG generation (following Playwright isolation principles)")
            
            # Create a fresh browser instance and context for this PNG generation
            # This ensures proper isolation and event loop compatibility
            from playwright.async_api import async_playwright
            playwright = await async_playwright().start()
            
            browser = await playwright.chromium.launch()
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='MindGraph PNG Generator/1.0',
                java_script_enabled=True,
                ignore_https_errors=True
            )
            
            logger.info(f"DEBUG: Fresh context created - type: {type(context)}, id: {id(context)}")
            
            try:
                # Use the fresh context for PNG generation
                page = await context.new_page()
                
                # Set timeout to 60 seconds for all content
                page.set_default_timeout(60000)  # 60 seconds default
                page.set_default_navigation_timeout(60000)
                
                # Set up console and error logging BEFORE loading content
                console_messages = []
                page_errors = []
                
                page.on("console", lambda msg: console_messages.append(f"{msg.type}: {msg.text}"))
                page.on("pageerror", lambda err: page_errors.append(str(err)))
                
                # Set timeout and log HTML size if large
                html_size = len(html)
                timeout_ms = 60000  # 60 seconds for all content
                if html_size > 100000:  # Log if HTML is very large
                    logger.info(f"Large HTML content: {html_size} characters, setting timeout to {timeout_ms}ms")
                
                await page.set_content(html, timeout=timeout_ms)
                
                # Wait for rendering and check for console errors
                logger.info("Waiting for initial rendering...")
                await asyncio.sleep(3.0)
                
                # Log console messages and errors (consolidated)
                if console_messages:
                    logger.info(f"Browser console messages: {len(console_messages)}")
                    # Log the actual console messages for debugging
                    for i, msg in enumerate(console_messages[-10:]):  # Last 10 messages
                        logger.info(f"Console {i+1}: {msg}")
                if page_errors:
                    logger.error(f"Browser errors: {len(page_errors)}")
                    for i, error in enumerate(page_errors):
                        logger.error(f"Browser Error {i+1}: {error}")
                
                # Wait for rendering to complete
                logger.info("Waiting for rendering to complete...")
                await asyncio.sleep(2.0)  # Reduced from 4.0 to 2.0 seconds
                
                # Check what functions are actually available in the browser
                try:
                    function_check = await page.evaluate("""
                        () => {
                            const functions = {};
                            functions.renderTreeMap = typeof renderTreeMap;
                            functions.TreeRenderer = typeof TreeRenderer;
                            functions.MindGraphUtils = typeof MindGraphUtils;
                            functions.addWatermark = typeof addWatermark;
                            functions.styleManager = typeof styleManager;
                            functions.d3 = typeof d3;
                            functions.renderGraph = typeof renderGraph;
                            
                            // Check if specific objects exist
                            if (window.TreeRenderer) {
                                functions.TreeRenderer_renderTreeMap = typeof window.TreeRenderer.renderTreeMap;
                            }
                            if (window.MindGraphUtils) {
                                functions.MindGraphUtils_addWatermark = typeof window.MindGraphUtils.addWatermark;
                            }
                            
                            return functions;
                        }
                    """)
                    logger.info(f"Function availability check: {function_check}")
                except Exception as e:
                    logger.error(f"Failed to check function availability: {e}")
                
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
                await page.wait_for_timeout(500)  # Reduced from 1000 to 500ms
                
                png_bytes = await element.screenshot(omit_background=False, timeout=60000)
                return png_bytes
            finally:
                # Clean up resources properly
                logger.info("DEBUG: Cleaning up PNG generation resources")
                try:
                    if 'page' in locals():
                        await page.close()
                        logger.info("DEBUG: Page closed")
                    if 'context' in locals():
                        await context.close()
                        logger.info("DEBUG: Context closed")
                    if 'browser' in locals():
                        await browser.close()
                        logger.info("DEBUG: Browser closed")
                    if 'playwright' in locals():
                        await playwright.stop()
                        logger.info("DEBUG: Playwright stopped")
                except Exception as cleanup_error:
                    logger.warning(f"DEBUG: Error during cleanup: {cleanup_error}")
        
        # Execute the async rendering
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            png_bytes = loop.run_until_complete(render_svg_to_png(spec, graph_type))
        finally:
            loop.close()
        
        render_time = time.time() - render_start_time
        total_time = time.time() - total_start_time
        
        # Update timing statistics
        rendering_timing_stats['total_renders'] += 1
        rendering_timing_stats['total_render_time'] += render_time
        rendering_timing_stats['render_times'].append(render_time)
        rendering_timing_stats['last_render_time'] = render_time
        rendering_timing_stats['llm_time_per_render'] += llm_time
        rendering_timing_stats['pure_render_time_per_render'] += render_time
        
        # Keep only last 100 render times to prevent memory bloat
        if len(rendering_timing_stats['render_times']) > 100:
            rendering_timing_stats['render_times'] = rendering_timing_stats['render_times'][-100:]
        
        logger.info(f"DingTalk PNG generation completed - LLM: {llm_time:.3f}s, Rendering: {render_time:.3f}s, Total: {total_time:.3f}s")
        
        # Save PNG to temporary location for DingTalk
        try:
            # Use tempfile for temporary storage
            import tempfile
            import uuid
            
            # Create a temporary file with a descriptive name
            temp_fd, temp_path = tempfile.mkstemp(
                suffix='.png',
                prefix=f'dingtalk_{uuid.uuid4().hex[:8]}_',
                dir=tempfile.gettempdir()
            )
            
            logger.info(f"Created temporary file: {temp_path}")
            
            # Close the file descriptor and reopen for writing
            os.close(temp_fd)
            
            # Save PNG file to temporary location
            with open(temp_path, 'wb') as f:
                f.write(png_bytes)
            
            logger.info(f"Saved PNG data ({len(png_bytes)} bytes) to {temp_path}")
            
            # Track for cleanup with timestamp
            add_dingtalk_image(temp_path, time.time())
            logger.info(f"Added to dingtalk_images tracking: {temp_path}")
            logger.info(f"Current tracked images count: {len(get_dingtalk_images())}")
            
            # Generate a unique filename for the URL (without the full temp path)
            filename = os.path.basename(temp_path)
            logger.info(f"Generated filename for URL: {filename}")
            
            # Get server URL for image access
            from settings import config
            server_url = config.SERVER_URL
            image_url = f"{server_url}/api/temp_images/{filename}"
            logger.info(f"Generated image URL: {image_url}")
            
            # Return plain text in markdown image format: ![](image_url)
            return f"![]({image_url})"
            
        except Exception as e:
            logger.error(f"Failed to save DingTalk image: {e}")
            return f"❌ 图片保存失败：{str(e)}", 500
            
    except Exception as e:
        logger.error(f"/generate_dingtalk failed: {e}", exc_info=True)
        # If the error is about missing SVG, return a specific message
        if isinstance(e, ValueError) and str(e).startswith("SVG element not found"):
            error_msg = "❌ 图表渲染失败：SVG元素未找到。请检查您的输入或尝试不同的提示词。"
        else:
            error_msg = f"❌ 图表生成失败：{str(e)}"
        
        # Return plain text error message
        return error_msg, 500


 

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

@api.route('/browser_context_pool_stats', methods=['GET'])
@handle_api_errors
def get_browser_context_pool_stats():
    """Browser context pool statistics endpoint (disabled for quick deployment)"""
    return jsonify({
        'message': 'Browser context pool statistics endpoint is disabled for quick deployment',
        'status': 'disabled'
    })

@api.route('/temp_images/<filename>', methods=['GET'])
def serve_temp_dingtalk_image(filename):
    """Serve temporary DingTalk images from the temporary directory."""
    try:
        logger.info(f"Attempting to serve image: {filename}")
        dingtalk_images = get_dingtalk_images()
        logger.info(f"Current dingtalk_images keys: {list(dingtalk_images.keys())}")
        
        # Find the image in our tracked temporary files
        temp_dir = tempfile.gettempdir()
        image_path = None
        
        # Look for the file in our tracked images
        for tracked_path in dingtalk_images.keys():
            if os.path.basename(tracked_path) == filename:
                image_path = tracked_path
                logger.info(f"Found image at: {image_path}")
                break
        
        if not image_path:
            logger.error(f"Image {filename} not found in tracked images")
            return jsonify({'error': 'Image not found in tracked images'}), 404
        
        if not os.path.exists(image_path):
            logger.error(f"Image file {image_path} does not exist on disk")
            return jsonify({'error': 'Image file not found on disk'}), 404
        
        # Check file permissions and size
        try:
            stat_info = os.stat(image_path)
            logger.info(f"Image file stats: size={stat_info.st_size}, permissions={oct(stat_info.st_mode)}")
        except Exception as e:
            logger.error(f"Failed to get file stats: {e}")
        
        # Check if the image has expired (older than 24 hours)
        current_time = time.time()
        creation_time = dingtalk_images.get(image_path, 0)
        age_hours = (current_time - creation_time) / 3600
        logger.info(f"Image age: {age_hours:.2f} hours")
        
        if current_time - creation_time > 24 * 60 * 60:  # 24 hours in seconds
            # Remove expired image
            try:
                os.unlink(image_path)
                remove_dingtalk_image(image_path)
                logger.info(f"Removed expired image during access: {image_path}")
            except OSError:
                pass
            return jsonify({'error': 'Image has expired'}), 410  # Gone
        
        # Serve the image file
        logger.info(f"Serving image file: {image_path}")
        return send_file(image_path, mimetype='image/png')
        
    except Exception as e:
        logger.error(f"Error serving temporary image {filename}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to serve image'}), 500

@api.route('/clear_cache', methods=['POST'])
def clear_cache():
    """Clear the modular cache for development"""
    try:
        from static.js.modular_cache_python import modular_js_manager
        modular_js_manager.clear_cache()
        return jsonify({"status": "success", "message": "Cache cleared successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500 

@api.route('/debug_dingtalk_images', methods=['GET'])
def debug_dingtalk_images():
    """Debug endpoint to check DingTalk image tracking status."""
    try:
        dingtalk_images = get_dingtalk_images()
        temp_dir = tempfile.gettempdir()
        
        debug_info = {
            'tracking_file': dingtalk_images_file,
            'temp_directory': temp_dir,
            'tracked_images_count': len(dingtalk_images),
            'tracked_images': {},
            'temp_directory_contents': []
        }
        
        # Check each tracked image
        for image_path, creation_time in dingtalk_images.items():
            exists = os.path.exists(image_path)
            if exists:
                try:
                    stat_info = os.stat(image_path)
                    size = stat_info.st_size
                    permissions = oct(stat_info.st_mode)
                except Exception as e:
                    size = "error"
                    permissions = "error"
            else:
                size = "file_not_found"
                permissions = "file_not_found"
            
            debug_info['tracked_images'][image_path] = {
                'filename': os.path.basename(image_path),
                'exists': exists,
                'size': size,
                'permissions': permissions,
                'creation_time': creation_time,
                'age_hours': (time.time() - creation_time) / 3600 if creation_time else 0
            }
        
        # List temp directory contents
        try:
            temp_files = os.listdir(temp_dir)
            png_files = [f for f in temp_files if f.endswith('.png') and 'dingtalk_' in f]
            debug_info['temp_directory_contents'] = png_files
        except Exception as e:
            debug_info['temp_directory_contents'] = f"Error listing directory: {e}"
        
        return jsonify(debug_info)
        
    except Exception as e:
        logger.error(f"Error in debug endpoint: {e}", exc_info=True)
        return jsonify({'error': f'Debug failed: {e}'}), 500