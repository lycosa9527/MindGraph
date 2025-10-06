from flask import Blueprint, request, jsonify, send_file
from agents import main_agent as agent
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

# Import Dify client at module level to catch import errors early
try:
    from dify_client import DifyClient
    DIFY_AVAILABLE = True
except ImportError as e:
    logging.error(f"Failed to import DifyClient: {e}")
    DIFY_AVAILABLE = False
    DifyClient = None

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

# Frontend logger for centralized logging
frontend_logger = logging.getLogger('frontend')

# Shared agent enhancement functions to reduce code duplication
def enhance_mindmap_spec(spec):
    """Shared function to enhance mind map specs with layout data."""
    try:
        from agents.mind_maps.mind_map_agent import MindMapAgent
        m_agent = MindMapAgent()
        
        # Preserve learning sheet metadata before enhancement
        is_learning_sheet = spec.get('is_learning_sheet')
        hidden_percentage = spec.get('hidden_node_percentage')
        
        agent_result = m_agent.enhance_spec(spec)
        if agent_result.get('success') and 'spec' in agent_result:
            enhanced_spec = agent_result['spec']
            # Restore learning sheet metadata after enhancement
            if is_learning_sheet:
                enhanced_spec['is_learning_sheet'] = is_learning_sheet
                enhanced_spec['hidden_node_percentage'] = hidden_percentage
                logger.debug(f"Restored learning sheet metadata to enhanced mindmap spec")
            return enhanced_spec
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
    
    # HTML entity encoding for special characters (but preserve Chinese characters)
    # Only encode characters that are actually dangerous, not all special characters
    # Temporarily disabled to test Chinese character preservation
    # html_entities = {
    #     '<': '&lt;',
    #     '>': '&gt;',
    #     '&': '&amp;',
    # }
    # 
    # for char, entity in html_entities.items():
    #     prompt = prompt.replace(char, entity)
    
    # Remove control characters and normalize whitespace
    prompt = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', prompt)
    prompt = re.sub(r'\s+', ' ', prompt)
    
    # Limit length and ensure it's not empty after sanitization
    sanitized = prompt[:1000].strip()
    return sanitized if sanitized else None

@api.route('/recalculate_mindmap_layout', methods=['POST'])
@handle_api_errors
def recalculate_mindmap_layout():
    """Recalculate mind map layout after adding/deleting nodes in the editor.
    
    This endpoint takes a mind map spec with updated children and returns
    the spec with recalculated layout positions.
    """
    data = request.json
    spec = data.get('spec')
    
    if not spec or not isinstance(spec, dict):
        return jsonify({'error': 'Invalid spec'}), 400
    
    if not spec.get('topic') or not isinstance(spec.get('children'), list):
        return jsonify({'error': 'Invalid mind map spec'}), 400
    
    try:
        # Enhance spec using MindMapAgent to recalculate layout
        enhanced_spec = enhance_mindmap_spec(spec)
        
        return jsonify({
            'spec': enhanced_spec,
            'success': True
        })
    except Exception as e:
        logger.error(f"Error recalculating mind map layout: {e}")
        return jsonify({'error': str(e)}), 500


@api.route('/generate_graph', methods=['POST'])
@handle_api_errors
def generate_graph():
    """Generate graph specification from user prompt using Qwen (default, with enhanced extraction and style integration).
    
    This endpoint returns JSON with the diagram specification for the frontend editor to render.
    For PNG file downloads, use /api/generate_png instead.
    """
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
    
    # Get optional forced diagram type (for auto-complete feature)
    forced_diagram_type = data.get('diagram_type', None)
    if forced_diagram_type:
        logger.info(f"Frontend generate_graph request received: prompt={prompt!r}, language={language!r}, forced_type={forced_diagram_type!r}")
    else:
        logger.info(f"Frontend generate_graph request received: prompt={prompt!r}, language={language!r}")
    
    # Track timing for LLM processing
    start_time = time.time()
    
    # Use enhanced agent workflow with integrated style system
    try:
        # Try cache first to avoid duplicate LLM work for identical prompt/language
        # Note: Cache is language-specific but not diagram-type-specific for now
        cached = _llm_cache_get(prompt, language)
        if cached and not forced_diagram_type:
            logger.debug("Cache hit for generate_graph - returning cached spec")
            result = cached
        else:
            result = agent.agent_graph_workflow_with_styles(prompt, language, forced_diagram_type=forced_diagram_type)
            # Cache on success
            try:
                if isinstance(result, dict) and result.get('spec') and not result['spec'].get('error'):
                    _llm_cache_set(prompt, language, result)
            except Exception:
                pass
        
        # Calculate LLM processing time
        llm_time = time.time() - start_time
        logger.info(f"LLM processing completed successfully in {llm_time:.3f}s")
        
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
                logger.debug("Bridge map enhancement started")
                logger.debug(f"Input spec keys: {list(spec.keys()) if isinstance(spec, dict) else 'Not a dict'}")
                logger.debug(f"Input spec type: {type(spec)}")
                
                from agents.thinking_maps import BridgeMapAgent
                br_agent = BridgeMapAgent()
                agent_result = br_agent.enhance_spec(spec)
                
                logger.debug(f"BridgeMapAgent result: {agent_result}")
                
                if agent_result.get('success') and 'spec' in agent_result:
                    spec = agent_result['spec']
                    logger.debug(f"Enhanced spec keys: {list(spec.keys())}")
                    logger.debug(f"Enhanced analogies count: {len(spec.get('analogies', []))}")
                    
                    # Log each analogy for debugging
                    analogies = spec.get('analogies', [])
                    for i, analogy in enumerate(analogies):
                        logger.debug(f"API analogy {i}: {analogy.get('left')} -> {analogy.get('right')}")
                else:
                    logger.warning(f"BridgeMapAgent enhancement skipped: {agent_result.get('error')}")
                
                logger.debug("Bridge map enhancement completed")
            except Exception as e:
                logger.error(f"Error enhancing bridge_map spec: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Thinking Tools (all use mindmap structure)
        elif diagram_type == 'factor_analysis':
            spec = enhance_mindmap_spec(spec)
        elif diagram_type == 'three_position_analysis':
            spec = enhance_mindmap_spec(spec)
        elif diagram_type == 'perspective_analysis':
            spec = enhance_mindmap_spec(spec)
        elif diagram_type == 'goal_analysis':
            spec = enhance_mindmap_spec(spec)
        elif diagram_type == 'possibility_analysis':
            spec = enhance_mindmap_spec(spec)
        elif diagram_type == 'result_analysis':
            spec = enhance_mindmap_spec(spec)
        elif diagram_type == 'five_w_one_h':
            spec = enhance_mindmap_spec(spec)
        elif diagram_type == 'whwm_analysis':
            spec = enhance_mindmap_spec(spec)
        elif diagram_type == 'four_quadrant':
            spec = enhance_mindmap_spec(spec)

        # Check for generation errors (keep this essential error handling)
        if isinstance(spec, dict) and spec.get('error'):
            return jsonify({'error': spec.get('error')}), 400

        # Calculate optimized dimensions
        dimensions = config.get_d3_dimensions()
        # Use agent-recommended dimensions if provided
        if diagram_type in ('multi_flow_map', 'flow_map', 'tree_map', 'concept_map', 'mindmap', 'bubble_map', 'double_bubble_map', 'circle_map', 'bridge_map', 'factor_analysis', 'three_position_analysis', 'perspective_analysis', 'goal_analysis', 'possibility_analysis', 'result_analysis', 'five_w_one_h', 'whwm_analysis', 'four_quadrant') and isinstance(spec, dict) and spec.get('_recommended_dimensions'):
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
            logger.debug("Final response preparation for frontend")
            logger.debug(f"Final spec keys: {list(spec.keys())}")
            logger.debug(f"Final analogies count: {len(spec.get('analogies', []))}")
            
            # Log each analogy being sent to frontend
            analogies = spec.get('analogies', [])
            for i, analogy in enumerate(analogies):
                logger.debug(f"Frontend-bound analogy {i}: {analogy.get('left')} -> {analogy.get('right')}")
            
            logger.debug(f"Dimensions being sent: {dimensions}")
            logger.debug("Response preparation completed")
        
        return jsonify({
            'type': diagram_type,
            'spec': spec,
            'agent': 'qwen',
            'topics': topics,
            'style_preferences': style_preferences,
            'diagram_type': diagram_type,
            'has_styles': '_style' in spec,
            'theme': {},  # Frontend uses style-manager.js for themes
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
    # Thread tracking for concurrency debugging
    import threading
    thread_id = threading.current_thread().ident
    thread_name = threading.current_thread().name
    
    # Input validation
    data = request.json
    valid, msg = validate_request_data(data, ['prompt'])
    if not valid:
        return jsonify({'error': msg}), 400
    
    prompt = sanitize_prompt(data['prompt'])
    if not prompt:
        return jsonify({'error': 'Invalid or empty prompt'}), 400
    
    language = data.get('language', 'zh')
    
    logger.info(f"Frontend generate_png request received [Thread-{thread_id}|{thread_name}]: prompt='{prompt}', language='{language}'")
    if not isinstance(language, str) or language not in ['zh', 'en']:
        return jsonify({'error': 'Invalid language. Must be "zh" or "en"'}), 400
    
    # Track timing for the entire process
    total_start_time = time.time()
    
    # Generate graph specification using the same workflow as generate_graph
    try:
        llm_start_time = time.time()
        # Prefer client-provided spec to avoid LLM call
        client_spec = data.get('spec') if isinstance(data, dict) else None
        result = None
        if isinstance(client_spec, dict) and client_spec:
            logger.debug("generate_png received client spec; skipping LLM workflow")
            result = {
                'spec': client_spec,
                'diagram_type': data.get('diagram_type', client_spec.get('diagram_type', 'concept_map')),
                'language': language
            }
        else:
            # Try cache next
            cached = _llm_cache_get(prompt, language)
            if cached:
                logger.debug("Cache hit for generate_png - using cached spec")
                result = cached
            else:
                result = agent.agent_graph_workflow_with_styles(prompt, language)
                
                # Add learning sheet metadata to spec for frontend rendering BEFORE caching
                spec = result.get('spec', {})
                logger.info(f"DEBUG: result keys: {list(result.keys())}")
                logger.info(f"DEBUG: result.is_learning_sheet = {result.get('is_learning_sheet')}")
                logger.info(f"DEBUG: result.hidden_node_percentage = {result.get('hidden_node_percentage')}")
                if result.get('is_learning_sheet'):
                    spec['is_learning_sheet'] = True
                    spec['hidden_node_percentage'] = result.get('hidden_node_percentage', 0.5)
                    logger.info(f"Added learning sheet metadata to spec: is_learning_sheet={spec.get('is_learning_sheet')}, hidden_percentage={spec.get('hidden_node_percentage')}")
                else:
                    logger.info(f"No learning sheet metadata added - is_learning_sheet={result.get('is_learning_sheet')}")
                
                # Update the result with the modified spec
                result['spec'] = spec
                
                # Cache on success (now includes learning sheet metadata)
                try:
                    if isinstance(result, dict) and result.get('spec') and not result['spec'].get('error'):
                        _llm_cache_set(prompt, language, result)
                except Exception:
                    pass
        
        # Add learning sheet metadata to spec for frontend rendering (for both cached and fresh results)
        spec = result.get('spec', {})
        if result.get('is_learning_sheet'):
            spec['is_learning_sheet'] = True
            spec['hidden_node_percentage'] = result.get('hidden_node_percentage', 0.5)
            logger.info(f"Added learning sheet metadata to spec: is_learning_sheet={spec.get('is_learning_sheet')}, hidden_percentage={spec.get('hidden_node_percentage')}")
            result['spec'] = spec
        else:
            logger.info(f"No learning sheet metadata needed - is_learning_sheet={result.get('is_learning_sheet')}")
        
        llm_time = time.time() - llm_start_time
        spec = result.get('spec', {})  # This now contains the learning sheet metadata
        graph_type = result.get('diagram_type', 'bubble_map')
        
        logger.info(f"DEBUG: Final spec keys: {list(spec.keys())}")
        logger.info(f"DEBUG: Final spec.is_learning_sheet = {spec.get('is_learning_sheet')}")
        logger.info(f"DEBUG: Final spec.hidden_node_percentage = {spec.get('hidden_node_percentage')}")
        
        # Debug: Check what's being serialized to JSON
        import json
        spec_json = json.dumps(spec, ensure_ascii=False)
        logger.info(f"DEBUG: Spec JSON length: {len(spec_json)}")
        logger.info(f"DEBUG: Spec JSON contains is_learning_sheet: {'is_learning_sheet' in spec_json}")
        logger.info(f"DEBUG: Spec JSON contains hidden_node_percentage: {'hidden_node_percentage' in spec_json}")
        logger.info(f"DEBUG: Spec JSON preview: {spec_json[:500]}...")
        
        logger.info(f"LLM processing completed in {llm_time:.3f}s")
    except Exception as e:
        logger.error(f"Agent workflow failed: {e}")
        return jsonify({'error': 'Failed to generate graph specification'}), 500
    
    # Thinking Tools (all use mindmap structure)
    if graph_type == 'factor_analysis':
        spec = enhance_mindmap_spec(spec)
    elif graph_type == 'three_position_analysis':
        spec = enhance_mindmap_spec(spec)
    elif graph_type == 'perspective_analysis':
        spec = enhance_mindmap_spec(spec)
    elif graph_type == 'goal_analysis':
        spec = enhance_mindmap_spec(spec)
    elif graph_type == 'possibility_analysis':
        spec = enhance_mindmap_spec(spec)
    elif graph_type == 'result_analysis':
        spec = enhance_mindmap_spec(spec)
    elif graph_type == 'five_w_one_h':
        spec = enhance_mindmap_spec(spec)
    elif graph_type == 'whwm_analysis':
        spec = enhance_mindmap_spec(spec)
    elif graph_type == 'four_quadrant':
        spec = enhance_mindmap_spec(spec)
    
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
            logger.debug(f"Enhanced brace map spec with agent data (original structure preserved)")
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
                # Preserve learning sheet metadata when enhancing spec
                enhanced_spec = agent_result['spec']
                if 'is_learning_sheet' in spec:
                    enhanced_spec['is_learning_sheet'] = spec['is_learning_sheet']
                if 'hidden_node_percentage' in spec:
                    enhanced_spec['hidden_node_percentage'] = spec['hidden_node_percentage']
                spec = enhanced_spec
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
                # Preserve learning sheet metadata when enhancing spec
                enhanced_spec = agent_result['spec']
                if 'is_learning_sheet' in spec:
                    enhanced_spec['is_learning_sheet'] = spec['is_learning_sheet']
                if 'hidden_node_percentage' in spec:
                    enhanced_spec['hidden_node_percentage'] = spec['hidden_node_percentage']
                spec = enhanced_spec
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
                # Preserve learning sheet metadata when enhancing spec
                enhanced_spec = agent_result['spec']
                if 'is_learning_sheet' in spec:
                    enhanced_spec['is_learning_sheet'] = spec['is_learning_sheet']
                if 'hidden_node_percentage' in spec:
                    enhanced_spec['hidden_node_percentage'] = spec['hidden_node_percentage']
                spec = enhanced_spec
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
            logger.debug("PNG bridge map enhancement started")
            logger.debug(f"Input spec keys: {list(spec.keys()) if isinstance(spec, dict) else 'Not a dict'}")
            logger.debug(f"Input spec type: {type(spec)}")
            
            from agents.thinking_maps import BridgeMapAgent
            br_agent = BridgeMapAgent()
            agent_result = br_agent.enhance_spec(spec)
            
            logger.debug(f"PNG BridgeMapAgent result: {agent_result}")
            
            if agent_result.get('success') and 'spec' in agent_result:
                spec = agent_result['spec']
                logger.debug(f"PNG Enhanced spec keys: {list(spec.keys())}")
                logger.debug(f"PNG Enhanced analogies count: {len(spec.get('analogies', []))}")
                
                # Log each analogy for debugging
                analogies = spec.get('analogies', [])
                for i, analogy in enumerate(analogies):
                    logger.debug(f"PNG analogy {i}: {analogy.get('left')} -> {analogy.get('right')}")
            else:
                logger.warning(f"PNG BridgeMapAgent enhancement skipped: {agent_result.get('error')}")
            
            logger.debug("PNG bridge map enhancement completed")
            
            # === PNG DEBUG: FINAL SPEC BEFORE RENDERING ===
            logger.debug("PNG final spec preparation started")
            logger.debug(f"Final PNG spec keys: {list(spec.keys())}")
            logger.debug(f"Final PNG analogies count: {len(spec.get('analogies', []))}")
            
            # Log each analogy before PNG rendering
            analogies = spec.get('analogies', [])
            for i, analogy in enumerate(analogies):
                logger.debug(f"PNG rendering analogy {i}: {analogy.get('left')} -> {analogy.get('right')}")
            
            logger.debug("PNG rendering preparation completed")
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
                
                # Load the style manager
                with open('static/js/style-manager.js', 'r', encoding='utf-8') as f:
                    style_manager = f.read()

                # Load the dynamic renderer loader and modify it for absolute URLs
                with open('static/js/dynamic-renderer-loader.js', 'r', encoding='utf-8') as f:
                    dynamic_loader = f.read()
                
                # Replace relative URLs with absolute ones for PNG generation context
                dynamic_loader = dynamic_loader.replace('/static/js/renderers/', 'http://localhost:9527/static/js/renderers/')
                
                renderer_scripts = f'''
                <!-- Dynamic Renderer Loader (Modified for PNG Generation) -->
                <script>
                {dynamic_loader}
                </script>
                '''
                
                logger.debug(f"Loading modular D3 renderers for {graph_type}")
                
                # Debug: Log layout information for concept maps
                if graph_type == 'concept_map' and isinstance(spec, dict):
                    layout_info = spec.get('_layout', {})
                    algorithm = layout_info.get('algorithm', 'unknown')
                    logger.debug(f"=== CONCEPT MAP LAYOUT DEBUG ===")
                    logger.debug(f"Layout algorithm: {algorithm}")
                    logger.debug(f"Layout keys: {list(layout_info.keys())}")
                    if 'positions' in layout_info:
                        pos_count = len(layout_info['positions'])
                        logger.debug(f"Position count: {pos_count}")
                    if 'rings' in layout_info:
                        ring_count = len(layout_info['rings'])
                        logger.debug(f"Ring count: {ring_count}")
                    if 'clusters' in layout_info:
                        cluster_count = len(layout_info['clusters'])
                        logger.debug(f"Cluster count: {cluster_count}")
                    logger.debug(f"=== END LAYOUT DEBUG ===")
                
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
                logger.debug(f"Spec data: {spec_keys}{svg_info}")
            else:
                logger.debug("Spec data: Not a dict")
            
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
                    logger.debug(f"Using enhanced spec optimal dimensions: {optimal_dims['width']}x{optimal_dims['height']}")
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
                    logger.debug(f"Using legacy format optimal dimensions: {svg_data['width']}x{svg_data['height']}")
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
                logger.debug(f"Local D3.js loaded for PNG generation ({len(d3_js_content)} bytes)")
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


            
            // Debug: Check what modules are loaded
            setTimeout(() => {{


                
                if (window.TreeRenderer) {{
                    console.log("  - TreeRenderer.renderTreeMap:", typeof window.TreeRenderer.renderTreeMap);
                }}
                if (window.MindGraphUtils) {{

                }}
            }}, 1000);
            
            // Wait for D3.js to load
            function waitForD3() {{
                if (typeof d3 !== "undefined") {{

                    try {{
                        window.spec = {json.dumps(spec, ensure_ascii=False)};
                        window.graph_type = "{graph_type}";
                        
                        // Get theme using style manager (centralized theme system)
                        let theme;
                        let backendTheme;
                        if (typeof styleManager !== "undefined" && typeof styleManager.getTheme === "function") {{
                            theme = styleManager.getTheme(graph_type);
            
                        }} else {{
                            // No fallback - style manager should always be available
                            theme = {{}};
                            console.error("Style manager not available - this should not happen");
                        }}
                        const watermarkConfig = {json.dumps(config.get_watermark_config(), ensure_ascii=False)};
                        backendTheme = {{...theme, ...watermarkConfig}};
                        window.dimensions = {json.dumps(dimensions, ensure_ascii=False)};
                        

                        
                        // Ensure style manager is available
                        if (typeof styleManager === "undefined") {{
                            console.error("Style manager not loaded!");

                            throw new Error("Style manager not available");
                        }} else {{

                        }}
                        
                        // Use dynamic renderer loader for all graph types

                        
                        if (typeof window.dynamicRendererLoader === "undefined") {{
                            console.error("Dynamic renderer loader not available");
                            console.error("Available window properties:", Object.keys(window).slice(0, 20));

                            throw new Error("Dynamic renderer loader not available");
                        }} else {{

                        }}
                        
                        try {{
                            // Use the dynamic renderer loader to render the graph
                            window.dynamicRendererLoader.renderGraph(window.graph_type, window.spec, backendTheme, window.dimensions)
                                .then(() => {{

                                }})
                                .catch(error => {{
                                    console.error("Dynamic rendering failed:", error);

                                }});
                        }} catch (error) {{
                            console.error("Error calling dynamic renderer:", error);

                        }}
                        

                        
                        // Wait a moment for SVG to be created
                        setTimeout(() => {{
                            const svg = document.querySelector("svg");
                            if (svg) {{

                            }} else {{
                                console.error("No SVG element found after rendering");

                            }}
                        }}, 1000);
                    }} catch (error) {{
                        console.error("Render error:", error);

                    }}
                }} else {{
                    setTimeout(waitForD3, 100);
                }}
            }}
            waitForD3();
            </script>
            </body></html>
            '''
            # Create fresh browser instance for each request for optimal reliability
            # According to Playwright best practices:
            # - Each isolated operation should have its own browser context
            # - Contexts cannot cross event loop boundaries
            # - For PNG generation, create a fresh browser instance each time
            # - Reference: https://playwright.dev/docs/browser-contexts#isolation
            
            logger.debug("Creating fresh browser instance for PNG generation")
            
            # Use fresh browser manager for reliable, thread-safe operations
            # This approach ensures complete isolation between requests
            from browser_manager import BrowserContextManager
            
            logger.debug("Using fresh browser manager for PNG generation")
            
            # Use context manager to automatically handle context acquisition and return
            async with BrowserContextManager() as context:
                logger.debug(f"Fresh browser context created - type: {type(context)}, id: {id(context)}")
                
                # Use the fresh context for PNG generation
                page = await context.new_page()
                
                # Set timeout to 60 seconds for all content
                page.set_default_timeout(60000)  # 60 seconds default
                page.set_default_navigation_timeout(60000)
                
                # Set up comprehensive console and error logging BEFORE loading content
                console_messages = []
                page_errors = []
                
                def log_console_message(msg):
                    message = f"{msg.type}: {msg.text}"
                    console_messages.append(message)
                    logger.debug(f"BROWSER CONSOLE: {message}")
                
                def log_page_error(err):
                    error_str = str(err)
                    page_errors.append(error_str)
                    logger.error(f"BROWSER ERROR: {error_str}")
                
                page.on("console", log_console_message)
                page.on("pageerror", log_page_error)
                
                # Also log when resources fail to load
                page.on("requestfailed", lambda request: logger.error(f"RESOURCE FAILED: {request.url} - {request.failure}"))
                page.on("response", lambda response: logger.debug(f"RESOURCE LOADED: {response.url} - {response.status}") if response.status >= 400 else None)
                
                # Set timeout and log HTML size and structure
                html_size = len(html)
                timeout_ms = 60000  # 60 seconds for all content
                logger.debug(f"HTML content size: {html_size} characters")
                
                # Log script tags in HTML for debugging
                script_count = html.count('<script>')
                logger.debug(f"Script tags in HTML: {script_count}")
                
                # Log if we have our test marker
                has_test_marker = 'test-marker' in html
                logger.debug(f"Test marker present in HTML: {has_test_marker}")
                
                # Log dynamic loader presence
                has_dynamic_loader = 'dynamicRendererLoader' in html
                logger.debug(f"Dynamic loader present in HTML: {has_dynamic_loader}")
                
                if html_size > 100000:  # Log if HTML is very large
                    logger.debug(f"Large HTML content: {html_size} characters, setting timeout to {timeout_ms}ms")
                
                # Try to load the content with more detailed error handling
                try:
                    await page.set_content(html, timeout=timeout_ms)
                    logger.debug("HTML content loaded successfully")
                except Exception as e:
                    logger.error(f"Failed to set HTML content: {e}")
                    raise
                
                # Wait for rendering and check for console errors
                logger.debug("Waiting for initial rendering...")
                
                # Check if basic elements exist before waiting for SVG
                try:
                    body_exists = await page.wait_for_selector('body', timeout=2000)
                    logger.debug("Body element found")
                    
                    container_exists = await page.wait_for_selector('#d3-container', timeout=2000)
                    logger.debug("D3 container found")
                    
                    # Check for our test marker
                    test_marker = await page.query_selector('#test-marker')
                    if test_marker:
                        logger.debug("Test marker found - JavaScript is executing")
                    else:
                        logger.error("Test marker NOT found - JavaScript may not be executing")
                    
                    # Check what's actually in the page
                    page_content = await page.evaluate('() => document.body.innerHTML')
                    logger.debug(f"Page body content length: {len(page_content)}")
                    logger.debug(f"Page body content preview: {page_content[:200]}...")
                    
                except Exception as e:
                    logger.error(f"Error checking basic page elements: {e}")
                
                # Event-driven SVG detection
                try:
                    await page.wait_for_selector('svg', timeout=5000)
                    logger.debug("SVG element found - initial rendering complete")
                except Exception as e:
                    logger.error(f"SVG element not found within timeout: {e}")
                    
                    # Additional debugging when SVG fails
                    try:
                        all_elements = await page.evaluate('() => document.querySelectorAll("*").length')
                        logger.debug(f"Total elements in page: {all_elements}")
                        
                        scripts = await page.evaluate('() => document.querySelectorAll("script").length')
                        logger.debug(f"Script elements in page: {scripts}")
                        
                        divs = await page.evaluate('() => document.querySelectorAll("div").length')
                        logger.debug(f"Div elements in page: {divs}")
                        
                        # Check console for any errors
                        logger.debug(f"Console messages so far: {len(console_messages)}")
                        for i, msg in enumerate(console_messages):
                            logger.debug(f"Console {i+1}: {msg}")
                        
                        logger.debug(f"Page errors so far: {len(page_errors)}")
                        for i, error in enumerate(page_errors):
                            logger.error(f"Page Error {i+1}: {error}")
                            
                    except Exception as debug_e:
                        logger.error(f"Error during additional debugging: {debug_e}")
                    
                    raise
                
                # Log console messages and errors (consolidated)
                if console_messages:
                    logger.debug(f"Browser console messages: {len(console_messages)}")
                    # Log the actual console messages for debugging
                    for i, msg in enumerate(console_messages[-10:]):  # Last 10 messages
                        logger.debug(f"Console {i+1}: {msg}")
                if page_errors:
                    logger.error(f"Browser errors: {len(page_errors)}")
                    for i, error in enumerate(page_errors):
                        logger.error(f"Browser Error {i+1}: {error}")
                
                # Wait for rendering to complete with dynamic timing based on graph complexity
                logger.debug("Waiting for rendering to complete...")
                
                # Event-driven SVG content detection
                await page.wait_for_function('''
                    () => {
                        const svg = document.querySelector('svg');
                        return svg && svg.children.length > 0;
                    }
                ''', timeout=5000)
                logger.debug("SVG content populated - rendering complete")
                
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
                    logger.debug(f"Function availability check: {function_check}")
                except Exception as e:
                    logger.error(f"Failed to check function availability: {e}")
                
                # Wait for SVG element to be created with timeout and content
                try:
                    element = await page.wait_for_selector("svg", timeout=15000)  # Increased timeout
                    logger.debug("SVG element found successfully")
                    
                    # Verify SVG content is substantial
                    logger.debug("Verifying SVG content...")
                    svg_content = await element.inner_html()
                    if svg_content.strip() and len(svg_content) > 100:  # SVG has substantial content
                        logger.debug(f"SVG content verified successfully (length: {len(svg_content)})")
                        # Log a sample of the SVG content for debugging
                        svg_sample = svg_content[:500] + "..." if len(svg_content) > 500 else svg_content
                        logger.debug(f"SVG content sample: {svg_sample}")
                    else:
                        logger.warning("SVG content may not be fully rendered")
                        if svg_content:
                            logger.warning(f"SVG content (may be incomplete): {svg_content[:200]}...")
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
                logger.debug(f"SVG dimensions: width={svg_width}, height={svg_height}")
                
                # Final wait to ensure all rendering is complete
                logger.debug("Final wait for rendering completion...")
                # Event-driven D3.js completion detection
                await page.wait_for_function('''
                    () => {
                        const svg = document.querySelector('svg');
                        if (!svg) return false;
                        
                        // Check if D3.js has finished rendering
                        const renderedElements = svg.querySelectorAll('g, circle, rect, text, path');
                        return renderedElements.length > 10; // D3.js typically creates many elements
                    }
                ''', timeout=3000)
                logger.debug("D3.js rendering complete - final wait done")
                
                # Ensure element is visible before screenshot
                await element.scroll_into_view_if_needed()
                # Event-driven element readiness detection
                await page.wait_for_function('''
                    () => {
                        const svg = document.querySelector('svg');
                        if (!svg) return false;
                        
                        // Check if element is visible and ready for screenshot
                        const rect = svg.getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0;
                    }
                ''', timeout=2000)
                logger.debug("Element ready for screenshot")
                
                png_bytes = await element.screenshot(omit_background=False, timeout=60000)
                return png_bytes
        
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
        
        # Add learning sheet metadata to spec for frontend rendering
        logger.debug(f"DingTalk: result keys: {list(result.keys())}")
        logger.debug(f"DingTalk: result.is_learning_sheet = {result.get('is_learning_sheet')}")
        logger.debug(f"DingTalk: result.hidden_node_percentage = {result.get('hidden_node_percentage')}")
        if result.get('is_learning_sheet'):
            spec['is_learning_sheet'] = True
            spec['hidden_node_percentage'] = result.get('hidden_node_percentage', 0.5)
            logger.info(f"DingTalk: Added learning sheet metadata to spec: is_learning_sheet={spec.get('is_learning_sheet')}, hidden_percentage={spec.get('hidden_node_percentage')}")
        else:
            logger.info(f"DingTalk: No learning sheet metadata added - is_learning_sheet={result.get('is_learning_sheet')}")
        
        logger.debug(f"DingTalk: Final spec keys: {list(spec.keys())}")
        logger.debug(f"DingTalk: Final spec.is_learning_sheet = {spec.get('is_learning_sheet')}")
        logger.debug(f"DingTalk: Final spec.hidden_node_percentage = {spec.get('hidden_node_percentage')}")
        logger.info(f"LLM processing completed in {llm_time:.3f}s")
    except Exception as e:
        logger.error(f"Agent workflow failed: {e}")
        return f"❌ 图表规格生成失败：{str(e)}", 500
    
    # Thinking Tools (all use mindmap structure)
    if graph_type == 'factor_analysis':
        spec = enhance_mindmap_spec(spec)
    elif graph_type == 'three_position_analysis':
        spec = enhance_mindmap_spec(spec)
    elif graph_type == 'perspective_analysis':
        spec = enhance_mindmap_spec(spec)
    elif graph_type == 'goal_analysis':
        spec = enhance_mindmap_spec(spec)
    elif graph_type == 'possibility_analysis':
        spec = enhance_mindmap_spec(spec)
    elif graph_type == 'result_analysis':
        spec = enhance_mindmap_spec(spec)
    elif graph_type == 'five_w_one_h':
        spec = enhance_mindmap_spec(spec)
    elif graph_type == 'whwm_analysis':
        spec = enhance_mindmap_spec(spec)
    elif graph_type == 'four_quadrant':
        spec = enhance_mindmap_spec(spec)
    
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
            logger.debug(f"Enhanced brace map spec with agent data (original structure preserved)")
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
            
            # Preserve learning sheet metadata before enhancement
            is_learning_sheet = spec.get('is_learning_sheet')
            hidden_percentage = spec.get('hidden_node_percentage')
            
            agent_result = mf_agent.enhance_spec(spec)
            if agent_result.get('success') and 'spec' in agent_result:
                spec = agent_result['spec']
                # Restore learning sheet metadata after enhancement
                if is_learning_sheet:
                    spec['is_learning_sheet'] = is_learning_sheet
                    spec['hidden_node_percentage'] = hidden_percentage
                    logger.debug(f"Restored learning sheet metadata to enhanced multi_flow_map spec")
            else:
                logger.warning(f"MultiFlowMapAgent enhancement skipped: {agent_result.get('error')}")
        except Exception as e:
            logger.error(f"Error enhancing multi_flow_map spec: {e}")
    elif graph_type == 'flow_map':
        # Enhance flow map spec and use recommended dimensions
        try:
            from agents.thinking_maps import FlowMapAgent
            f_agent = FlowMapAgent()
            
            # Preserve learning sheet metadata before enhancement
            is_learning_sheet = spec.get('is_learning_sheet')
            hidden_percentage = spec.get('hidden_node_percentage')
            
            agent_result = f_agent.enhance_spec(spec)
            if agent_result.get('success') and 'spec' in agent_result:
                spec = agent_result['spec']
                # Restore learning sheet metadata after enhancement
                if is_learning_sheet:
                    spec['is_learning_sheet'] = is_learning_sheet
                    spec['hidden_node_percentage'] = hidden_percentage
                    logger.debug(f"Restored learning sheet metadata to enhanced flow_map spec")
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
            
            # Preserve learning sheet metadata before enhancement
            is_learning_sheet = spec.get('is_learning_sheet')
            hidden_percentage = spec.get('hidden_node_percentage')
            
            agent_result = b_agent.enhance_spec(spec)
            if agent_result.get('success') and 'spec' in agent_result:
                spec = agent_result['spec']
                # Restore learning sheet metadata after enhancement
                if is_learning_sheet:
                    spec['is_learning_sheet'] = is_learning_sheet
                    spec['hidden_node_percentage'] = hidden_percentage
                    logger.debug(f"Restored learning sheet metadata to enhanced bubble_map spec")
            else:
                logger.warning(f"BubbleMapAgent enhancement skipped: {agent_result.get('error')}")
        except Exception as e:
            logger.error(f"Error enhancing bubble_map spec: {e}")
    elif graph_type == 'double_bubble_map':
        try:
            from agents.thinking_maps import DoubleBubbleMapAgent
            db_agent = DoubleBubbleMapAgent()
            
            # Preserve learning sheet metadata before enhancement
            is_learning_sheet = spec.get('is_learning_sheet')
            hidden_percentage = spec.get('hidden_node_percentage')
            
            agent_result = db_agent.enhance_spec(spec)
            if agent_result.get('success') and 'spec' in agent_result:
                spec = agent_result['spec']
                # Restore learning sheet metadata after enhancement
                if is_learning_sheet:
                    spec['is_learning_sheet'] = is_learning_sheet
                    spec['hidden_node_percentage'] = hidden_percentage
                    logger.debug(f"Restored learning sheet metadata to enhanced double_bubble_map spec")
            else:
                logger.warning(f"DoubleBubbleMapAgent enhancement skipped: {agent_result.get('error')}")
        except Exception as e:
            logger.error(f"Error enhancing double_bubble_map spec: {e}")
    elif graph_type == 'circle_map':
        try:
            from agents.thinking_maps import CircleMapAgent
            c_agent = CircleMapAgent()
            
            # Preserve learning sheet metadata before enhancement
            is_learning_sheet = spec.get('is_learning_sheet')
            hidden_percentage = spec.get('hidden_node_percentage')
            
            agent_result = c_agent.enhance_spec(spec)
            if agent_result.get('success') and 'spec' in agent_result:
                spec = agent_result['spec']
                # Restore learning sheet metadata after enhancement
                if is_learning_sheet:
                    spec['is_learning_sheet'] = is_learning_sheet
                    spec['hidden_node_percentage'] = hidden_percentage
                    logger.debug(f"Restored learning sheet metadata to enhanced circle_map spec")
            else:
                logger.warning(f"CircleMapAgent enhancement skipped: {agent_result.get('error')}")
        except Exception as e:
            logger.error(f"Error enhancing circle_map spec: {e}")
    elif graph_type == 'bridge_map':
        try:
            from agents.thinking_maps import BridgeMapAgent
            br_agent = BridgeMapAgent()
            
            # Preserve learning sheet metadata before enhancement
            is_learning_sheet = spec.get('is_learning_sheet')
            hidden_percentage = spec.get('hidden_node_percentage')
            
            agent_result = br_agent.enhance_spec(spec)
            if agent_result.get('success') and 'spec' in agent_result:
                spec = agent_result['spec']
                # Restore learning sheet metadata after enhancement
                if is_learning_sheet:
                    spec['is_learning_sheet'] = is_learning_sheet
                    spec['hidden_node_percentage'] = hidden_percentage
                    logger.debug(f"Restored learning sheet metadata to enhanced bridge_map spec")
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
                
                # Load the style manager
                with open('static/js/style-manager.js', 'r', encoding='utf-8') as f:
                    style_manager = f.read()

                # Load the dynamic renderer loader and modify it for absolute URLs
                with open('static/js/dynamic-renderer-loader.js', 'r', encoding='utf-8') as f:
                    dynamic_loader = f.read()
                
                # Replace relative URLs with absolute ones for PNG generation context
                dynamic_loader = dynamic_loader.replace('/static/js/renderers/', 'http://localhost:9527/static/js/renderers/')
                
                renderer_scripts = f'''
                <!-- Dynamic Renderer Loader (Modified for PNG Generation) -->
                <script>
                {dynamic_loader}
                </script>
                '''
                
                logger.debug(f"Loading modular D3 renderers for {graph_type}")
                
                # Debug: Log layout information for concept maps
                if graph_type == 'concept_map' and isinstance(spec, dict):
                    layout_info = spec.get('_layout', {})
                    algorithm = layout_info.get('algorithm', 'unknown')
                    logger.debug(f"=== CONCEPT MAP LAYOUT DEBUG ===")
                    logger.debug(f"Layout algorithm: {algorithm}")
                    logger.debug(f"Layout keys: {list(layout_info.keys())}")
                    if 'positions' in layout_info:
                        pos_count = len(layout_info['positions'])
                        logger.debug(f"Position count: {pos_count}")
                    if 'rings' in layout_info:
                        ring_count = len(layout_info['rings'])
                        logger.debug(f"Ring count: {ring_count}")
                    if 'clusters' in layout_info:
                        cluster_count = len(layout_info['clusters'])
                        logger.debug(f"Cluster count: {cluster_count}")
                    logger.debug(f"=== END LAYOUT DEBUG ===")
                
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
                logger.debug(f"Spec data: {spec_keys}{svg_info}")
            else:
                logger.debug("Spec data: Not a dict")
            
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
                    logger.debug(f"Using enhanced spec optimal dimensions: {optimal_dims['width']}x{optimal_dims['height']}")
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
                    logger.debug(f"Using legacy format optimal dimensions: {svg_data['width']}x{svg_data['height']}")
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
                logger.debug(f"Local D3.js loaded for PNG generation ({len(d3_js_content)} bytes)")
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


            
            // Debug: Check what modules are loaded
            setTimeout(() => {{


                
                if (window.TreeRenderer) {{
                    console.log("  - TreeRenderer.renderTreeMap:", typeof window.TreeRenderer.renderTreeMap);
                }}
                if (window.MindGraphUtils) {{

                }}
            }}, 1000);
            
            // Wait for D3.js to load
            function waitForD3() {{
                if (typeof d3 !== "undefined") {{

                    try {{
                        window.spec = {json.dumps(spec, ensure_ascii=False)};
                        window.graph_type = "{graph_type}";
                        
                        // Get theme using style manager (centralized theme system)
                        let theme;
                        let backendTheme;
                        if (typeof styleManager !== "undefined" && typeof styleManager.getTheme === "function") {{
                            theme = styleManager.getTheme(graph_type);
            
                        }} else {{
                            // No fallback - style manager should always be available
                            theme = {{}};
                            console.error("Style manager not available - this should not happen");
                        }}
                        const watermarkConfig = {json.dumps(config.get_watermark_config(), ensure_ascii=False)};
                        backendTheme = {{...theme, ...watermarkConfig}};
                        window.dimensions = {json.dumps(dimensions, ensure_ascii=False)};
                        

                        
                        // Ensure style manager is available
                        if (typeof styleManager === "undefined") {{
                            console.error("Style manager not loaded!");

                            throw new Error("Style manager not available");
                        }} else {{

                        }}
                        
                        // Use dynamic renderer loader for all graph types

                        
                        if (typeof window.dynamicRendererLoader === "undefined") {{
                            console.error("Dynamic renderer loader not available");
                            console.error("Available window properties:", Object.keys(window).slice(0, 20));

                            throw new Error("Dynamic renderer loader not available");
                        }} else {{

                        }}
                        
                        try {{
                            // Use the dynamic renderer loader to render the graph
                            window.dynamicRendererLoader.renderGraph(window.graph_type, window.spec, backendTheme, window.dimensions)
                                .then(() => {{

                                }})
                                .catch(error => {{
                                    console.error("Dynamic rendering failed:", error);

                                }});
                        }} catch (error) {{
                            console.error("Error calling dynamic renderer:", error);

                        }}
                        

                        
                        // Wait a moment for SVG to be created
                        setTimeout(() => {{
                            const svg = document.querySelector("svg");
                            if (svg) {{

                            }} else {{
                                console.error("No SVG element found after rendering");

                            }}
                        }}, 1000);
                    }} catch (error) {{
                        console.error("Render error:", error);

                    }}
                }} else {{
                    setTimeout(waitForD3, 100);
                }}
            }}
            waitForD3();
            </script>
            </body></html>
            '''
            # Create fresh browser instance for each request for optimal reliability
            # According to Playwright best practices:
            # - Each isolated operation should have its own browser context
            # - Contexts cannot cross event loop boundaries
            # - For PNG generation, create a fresh browser instance each time
            # - Reference: https://playwright.dev/docs/browser-contexts#isolation
            
            logger.debug("Creating fresh browser instance for PNG generation")
            
            # Use fresh browser manager for reliable, thread-safe operations
            # This approach ensures complete isolation between requests
            from browser_manager import BrowserContextManager
            
            logger.debug("Using fresh browser manager for PNG generation")
            
            # Use context manager to automatically handle context acquisition and return
            async with BrowserContextManager() as context:
                logger.debug(f"Fresh browser context created - type: {type(context)}, id: {id(context)}")
                
                # Use the fresh context for PNG generation
                page = await context.new_page()
                
                # Set timeout to 60 seconds for all content
                page.set_default_timeout(60000)  # 60 seconds default
                page.set_default_navigation_timeout(60000)
                
                # Set up comprehensive console and error logging BEFORE loading content
                console_messages = []
                page_errors = []
                
                def log_console_message(msg):
                    message = f"{msg.type}: {msg.text}"
                    console_messages.append(message)
                    logger.debug(f"BROWSER CONSOLE: {message}")
                
                def log_page_error(err):
                    error_str = str(err)
                    page_errors.append(error_str)
                    logger.error(f"BROWSER ERROR: {error_str}")
                
                page.on("console", log_console_message)
                page.on("pageerror", log_page_error)
                
                # Also log when resources fail to load
                page.on("requestfailed", lambda request: logger.error(f"RESOURCE FAILED: {request.url} - {request.failure}"))
                page.on("response", lambda response: logger.debug(f"RESOURCE LOADED: {response.url} - {response.status}") if response.status >= 400 else None)
                
                # Set timeout and log HTML size and structure
                html_size = len(html)
                timeout_ms = 60000  # 60 seconds for all content
                logger.debug(f"HTML content size: {html_size} characters")
                
                # Log script tags in HTML for debugging
                script_count = html.count('<script>')
                logger.debug(f"Script tags in HTML: {script_count}")
                
                # Log if we have our test marker
                has_test_marker = 'test-marker' in html
                logger.debug(f"Test marker present in HTML: {has_test_marker}")
                
                # Log dynamic loader presence
                has_dynamic_loader = 'dynamicRendererLoader' in html
                logger.debug(f"Dynamic loader present in HTML: {has_dynamic_loader}")
                
                if html_size > 100000:  # Log if HTML is very large
                    logger.debug(f"Large HTML content: {html_size} characters, setting timeout to {timeout_ms}ms")
                
                # Try to load the content with more detailed error handling
                try:
                    await page.set_content(html, timeout=timeout_ms)
                    logger.debug("HTML content loaded successfully")
                except Exception as e:
                    logger.error(f"Failed to set HTML content: {e}")
                    raise
                
                # Wait for rendering and check for console errors
                logger.debug("Waiting for initial rendering...")
                # Replace fixed timeout with event-driven SVG detection
                await page.wait_for_selector('svg', timeout=5000)
                logger.debug("SVG element found - initial rendering complete")
                
                # Log console messages and errors (consolidated)
                if console_messages:
                    logger.debug(f"Browser console messages: {len(console_messages)}")
                    # Log the actual console messages for debugging
                    for i, msg in enumerate(console_messages[-10:]):  # Last 10 messages
                        logger.debug(f"Console {i+1}: {msg}")
                if page_errors:
                    logger.error(f"Browser errors: {len(page_errors)}")
                    for i, error in enumerate(page_errors):
                        logger.error(f"Browser Error {i+1}: {error}")
                
                # Wait for rendering to complete
                logger.debug("Waiting for rendering to complete...")
                # Event-driven SVG content detection
                await page.wait_for_function('''
                    () => {
                        const svg = document.querySelector('svg');
                        return svg && svg.children.length > 0;
                    }
                ''', timeout=5000)
                logger.debug("SVG content populated - rendering complete")
                
                # Check what functions are actually available in the browser
                try:
                    function_check = await page.evaluate("""
                        () => {
                            const functions = {};
                            functions.renderTreeMap = typeof renderTreeMap;
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
                    logger.debug(f"Function availability check: {function_check}")
                except Exception as e:
                    logger.error(f"Failed to check function availability: {e}")
                
                # Wait for SVG element to be created with timeout
                try:
                    element = await page.wait_for_selector("svg", timeout=10000)
                    logger.debug("SVG element found successfully")
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
                logger.debug(f"SVG dimensions: width={svg_width}, height={svg_height}")
                
                # Ensure element is visible before screenshot
                await element.scroll_into_view_if_needed()
                # Replace fixed timeout with event-driven element readiness detection
                try:
                    await page.wait_for_function('''
                        () => {
                            const svg = document.querySelector('svg');
                            if (!svg) return false;
                            
                            // Check if element is visible and ready for screenshot
                            const rect = svg.getBoundingClientRect();
                            return rect.width > 0 && rect.height > 0;
                        }
                    ''', timeout=2000)
                    logger.debug("Element ready for screenshot")
                except Exception as e:
                    logger.warning(f"Element not ready for screenshot within 2s timeout: {e}")
                    # Fallback to shorter fixed wait
                    await page.wait_for_timeout(200)
                
                png_bytes = await element.screenshot(omit_background=False, timeout=60000)
                return png_bytes
        
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
            
            logger.debug(f"Created temporary file: {temp_path}")
            
            # Close the file descriptor and reopen for writing
            os.close(temp_fd)
            
            # Save PNG file to temporary location
            with open(temp_path, 'wb') as f:
                f.write(png_bytes)
            
            logger.debug(f"Saved PNG data ({len(png_bytes)} bytes) to {temp_path}")
            
            # Track for cleanup with timestamp
            add_dingtalk_image(temp_path, time.time())
            logger.debug(f"Added to dingtalk_images tracking: {temp_path}")
            logger.debug(f"Current tracked images count: {len(get_dingtalk_images())}")
            
            # Generate a unique filename for the URL (without the full temp path)
            filename = os.path.basename(temp_path)
            logger.debug(f"Generated filename for URL: {filename}")
            
            # Get server URL for image access
            from settings import config
            server_url = config.SERVER_URL
            image_url = f"{server_url}/api/temp_images/{filename}"
            logger.debug(f"Generated image URL: {image_url}")
            
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
    
    # REMOVED: diagram_styles.py imports and usage - dead code
    # Style manager provides complete theme system
    return jsonify({
        'success': True,
        'message': f'Style updates now handled by frontend style manager',
        'note': 'Use style manager for theme customization'
    })
    
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

@api.route('/browser_manager_stats', methods=['GET'])
@handle_api_errors
def get_browser_manager_stats():
    """Browser manager statistics endpoint - fresh browser per request approach"""
    return jsonify({
        'message': 'Browser manager uses fresh browser instance per request for optimal reliability',
        'status': 'active',
        'approach': 'fresh_browser_per_request',
        'benefits': [
            'Complete thread isolation',
            'No resource conflicts',
            'Reliable cleanup',
            'Simplified architecture'
        ]
    })

@api.route('/temp_images/<filename>', methods=['GET'])
def serve_temp_dingtalk_image(filename):
    """Serve temporary DingTalk images from the temporary directory."""
    try:
        logger.debug(f"Attempting to serve image: {filename}")
        dingtalk_images = get_dingtalk_images()
        logger.debug(f"Current dingtalk_images keys: {list(dingtalk_images.keys())}")
        
        # Find the image in our tracked temporary files
        temp_dir = tempfile.gettempdir()
        image_path = None
        
        # Look for the file in our tracked images
        for tracked_path in dingtalk_images.keys():
            if os.path.basename(tracked_path) == filename:
                image_path = tracked_path
                logger.debug(f"Found image at: {image_path}")
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
            logger.debug(f"Image file stats: size={stat_info.st_size}, permissions={oct(stat_info.st_mode)}")
        except Exception as e:
            logger.error(f"Failed to get file stats: {e}")
        
        # Check if the image has expired (older than 24 hours)
        current_time = time.time()
        creation_time = dingtalk_images.get(image_path, 0)
        age_hours = (current_time - creation_time) / 3600
        logger.debug(f"Image age: {age_hours:.2f} hours")
        
        if current_time - creation_time > 24 * 60 * 60:  # 24 hours in seconds
            # Remove expired image
            try:
                os.unlink(image_path)
                remove_dingtalk_image(image_path)
                logger.debug(f"Removed expired image during access: {image_path}")
            except OSError:
                pass
            return jsonify({'error': 'Image has expired'}), 410  # Gone
        
        # Serve the image file
        logger.debug(f"Serving image file: {image_path}")
        return send_file(image_path, mimetype='image/png')
        
    except Exception as e:
        logger.error(f"Error serving temporary image {filename}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to serve image'}), 500

@api.route('/frontend_log', methods=['POST'])
def frontend_log():
    """
    Centralized frontend logging endpoint.
    Receives logs from JavaScript frontend and outputs to terminal console.
    
    Request body:
    {
        "level": "INFO|DEBUG|WARNING|ERROR",
        "message": "Log message",
        "data": {...},  // optional
        "source": "module_name",  // optional
        "sessionId": "session_id",  // optional
        "timestamp": "HH:MM:SS"  // optional
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Extract log details
        level = data.get('level', 'INFO').upper()
        message = data.get('message', '')
        log_data = data.get('data')
        source = data.get('source', 'frontend')
        session_id = data.get('sessionId', '')
        
        # Abbreviate frontend sources for compact logging (3-4 letter codes)
        source_abbrev_map = {
            'InteractiveEditor': 'IEDT',
            'ToolbarManager': 'TOOL',
            'DiagramSelector': 'DSEL',
            'frontend': 'FRNT'
        }
        source_abbrev = source_abbrev_map.get(source, source[:4].upper())
        
        # Format log message for terminal (no timestamp - UnifiedFormatter adds it)
        session_info = f"Session: {session_id[:8]} | " if session_id else ""
        source_info = f"{source_abbrev} | "
        
        # Build complete message
        if log_data:
            complete_message = f"{session_info}{source_info}{message} | Data: {json.dumps(log_data, ensure_ascii=False)}"
        else:
            complete_message = f"{session_info}{source_info}{message}"
        
        # Log to appropriate level
        if level == 'DEBUG':
            frontend_logger.debug(complete_message)
        elif level == 'WARNING':
            frontend_logger.warning(complete_message)
        elif level == 'ERROR':
            frontend_logger.error(complete_message)
        else:  # INFO or default
            frontend_logger.info(complete_message)
        
        return jsonify({'status': 'logged'}), 200
        
    except Exception as e:
        # Don't fail the frontend if logging fails
        logger.error(f"Frontend logging endpoint error: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

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

@api.route('/ai_assistant/stream', methods=['POST'])
@handle_api_errors
def ai_assistant_stream():
    """Stream AI assistant responses using Dify API with SSE"""
    from flask import Response, stream_with_context
    
    # Check if Dify client is available
    if not DIFY_AVAILABLE or DifyClient is None:
        logger.error("DifyClient not available - check if dify_client.py exists and imports correctly")
        return jsonify({'error': 'AI assistant service not available'}), 500
    
    # Input validation
    data = request.json
    valid, msg = validate_request_data(data, ['message', 'user_id'])
    if not valid:
        return jsonify({'error': msg}), 400
    
    message = data.get('message', '').strip()
    user_id = data.get('user_id')
    conversation_id = data.get('conversation_id')
    
    if not message:
        return jsonify({'error': 'Message is required'}), 400
    
    # Get Dify configuration from environment
    api_key = os.getenv('DIFY_API_KEY')
    api_url = os.getenv('DIFY_API_URL', 'http://101.42.231.179/v1')
    timeout = int(os.getenv('DIFY_TIMEOUT', '30'))
    
    logger.info(f"Dify Configuration - API URL: {api_url}, Has API Key: {bool(api_key)}, Timeout: {timeout}")
    
    if not api_key:
        logger.error("DIFY_API_KEY not configured in environment")
        return jsonify({'error': 'AI assistant not configured'}), 500
    
    logger.info(f"AI assistant request from user {user_id}: {message[:50]}...")
    logger.info(f"[SETUP] About to create generator function")
    
    def generate():
        """Generator function for SSE streaming"""
        logger.info(f"[GENERATOR] Generator function called - starting execution")
        try:
            logger.info(f"[STREAM] Creating DifyClient with URL: {api_url}")
            client = DifyClient(api_key=api_key, api_url=api_url, timeout=timeout)
            logger.info(f"[STREAM] DifyClient created successfully")
            
            logger.info(f"[STREAM] Starting stream_chat for message: {message[:50]}...")
            chunk_count = 0
            for chunk in client.stream_chat(message, user_id, conversation_id):
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
    
    logger.info(f"[SETUP] Creating Response with stream_with_context")
    try:
        response = Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no',
                'Connection': 'keep-alive'
            }
        )
        logger.info(f"[SETUP] Response object created successfully")
        return response
    except Exception as e:
        logger.error(f"[SETUP] Failed to create streaming response: {e}", exc_info=True)
        raise