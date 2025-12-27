"""
PNG Export API Router
=====================

API endpoints for PNG export functionality:
- /api/export_png: Export diagram as PNG from diagram data
- /api/generate_png: Generate PNG directly from user prompt
- /api/generate_dingtalk: Generate PNG for DingTalk integration
- /api/temp_images/{filepath}: Serve temporary PNG files

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import json
import logging
import os
import time
import uuid
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional
import aiofiles
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import Response, PlainTextResponse, FileResponse
from models.auth import User
from utils.auth import get_current_user_or_api_key
from models import (
    ExportPNGRequest,
    GeneratePNGRequest,
    GenerateDingTalkRequest,
    Messages,
    get_request_language
)
from services.browser import BrowserContextManager
from .helpers import get_rate_limit_identifier, check_endpoint_rate_limit, generate_signed_url, verify_signed_url

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])


def _get_font_base64(font_filename: str) -> str:
    """Convert font file to base64 for embedding in HTML."""
    try:
        font_path = Path(__file__).parent.parent.parent / 'static' / 'fonts' / font_filename
        if font_path.exists():
            with open(font_path, 'rb') as f:
                import base64
                return base64.b64encode(f.read()).decode('utf-8')
        else:
            logger.debug(f"[ExportPNG] Font file not found: {font_path}")
            return ""
    except Exception as e:
        logger.warning(f"[ExportPNG] Failed to load font {font_filename}: {e}")
        return ""


async def _export_png_core(
    diagram_data: Dict[str, Any],
    diagram_type: str,
    width: int = 1200,
    height: int = 800,
    scale: int = 2,
    x_language: Optional[str] = None,
    base_url: Optional[str] = None
) -> bytes:
    """
    Core PNG export function that embeds JS and fonts directly (like old working version).
    
    This function avoids Depends() issues by being a pure async function.
    Returns raw PNG bytes.
    """
    from config.settings import Config
    config = Config()
    
    logger.debug(f"[ExportPNG] Starting PNG export: diagram_type={diagram_type}, width={width}, height={height}, scale={scale}")
    if isinstance(diagram_data, dict):
        logger.debug(f"[ExportPNG] Diagram data keys: {list(diagram_data.keys())}")
        if 'topic' in diagram_data:
            logger.debug(f"[ExportPNG] Topic: {diagram_data['topic']}")
    
    # Normalize data format for renderers (transform LLM output format to renderer expected format)
    if isinstance(diagram_data, dict):
        if diagram_type == 'double_bubble_map':
            # Transform left_topic/right_topic to left/right (renderer expects left/right)
            if 'left_topic' in diagram_data and 'left' not in diagram_data:
                diagram_data['left'] = diagram_data.pop('left_topic')
            if 'right_topic' in diagram_data and 'right' not in diagram_data:
                diagram_data['right'] = diagram_data.pop('right_topic')
            logger.debug(f"[ExportPNG] Normalized double_bubble_map: left={diagram_data.get('left')}, right={diagram_data.get('right')}")
        
        elif diagram_type == 'circle_map':
            # Transform contexts (plural) to context (singular) - renderer expects spec.context
            if 'contexts' in diagram_data and 'context' not in diagram_data:
                diagram_data['context'] = diagram_data.pop('contexts')
            logger.debug(f"[ExportPNG] Normalized circle_map: context count={len(diagram_data.get('context', []))}")
        
        elif diagram_type == 'tree_map':
            # Transform categories to children - renderer expects spec.children
            # Each category: {name: "...", items: [...]} → {text: "...", children: [...]}
            if 'categories' in diagram_data and 'children' not in diagram_data:
                categories = diagram_data.pop('categories')
                diagram_data['children'] = []
                for cat in categories:
                    if isinstance(cat, dict):
                        child = {
                            'text': cat.get('name', cat.get('label', '')),
                            'children': cat.get('items', [])
                        }
                        diagram_data['children'].append(child)
                    elif isinstance(cat, str):
                        # Simple string category
                        diagram_data['children'].append({'text': cat, 'children': []})
                logger.debug(f"[ExportPNG] Normalized tree_map: children count={len(diagram_data.get('children', []))}")
        
        elif diagram_type == 'brace_map':
            # Transform topic to whole (renderer expects 'whole' field)
            if 'topic' in diagram_data and 'whole' not in diagram_data:
                diagram_data['whole'] = diagram_data.pop('topic')
                logger.debug(f"[ExportPNG] Normalized brace_map: topic -> whole = '{diagram_data['whole']}'")
            
            # Transform parts array: strings → objects with name property
            # Renderer expects: parts = [{name: "...", subparts: [{name: "..."}]}]
            # Prompt returns: parts = ["Part 1", "Part 2", ...]
            if 'parts' in diagram_data and isinstance(diagram_data['parts'], list):
                normalized_parts = []
                for part in diagram_data['parts']:
                    if isinstance(part, str):
                        # String part → object with name
                        normalized_parts.append({'name': part})
                    elif isinstance(part, dict):
                        # Already an object, ensure it has 'name' property
                        if 'name' not in part and 'text' in part:
                            part['name'] = part.pop('text')
                        normalized_parts.append(part)
                diagram_data['parts'] = normalized_parts
                logger.debug(f"[ExportPNG] Normalized brace_map: parts count={len(diagram_data.get('parts', []))}")
    
    try:
        # Load JS files from disk for embedding (like old version)
        logger.debug(f"[ExportPNG] Loading JavaScript files for embedding")
        
        # Read local D3.js content for embedding in PNG generation (like old version)
        d3_js_path = Path(__file__).parent.parent.parent / 'static' / 'js' / 'd3.min.js'
        try:
            with open(d3_js_path, 'r', encoding='utf-8') as f:
                d3_js_content = f.read()
            logger.debug(f"[ExportPNG] D3.js loaded ({len(d3_js_content)} bytes)")
            d3_script_tag = f'<script>{d3_js_content}</script>'
        except Exception as e:
            logger.error(f"[ExportPNG] Failed to load D3.js: {e}")
            raise RuntimeError(f"Local D3.js library not available at {d3_js_path}")
        
        # Load other JS files for embedding
        # IMPORTANT: Load order matters - logger must be loaded BEFORE dynamic_loader
        js_files_to_embed = {
            'logger': Path(__file__).parent.parent.parent / 'static' / 'js' / 'logger.js',
            'theme_config': Path(__file__).parent.parent.parent / 'static' / 'js' / 'theme-config.js',
            'style_manager': Path(__file__).parent.parent.parent / 'static' / 'js' / 'style-manager.js',
            'dynamic_loader': Path(__file__).parent.parent.parent / 'static' / 'js' / 'dynamic-renderer-loader.js',
        }
        
        # Determine which renderer file to embed based on diagram type
        renderer_map = {
            'bubble_map': 'bubble-map-renderer.js',
            'double_bubble_map': 'bubble-map-renderer.js',
            'circle_map': 'bubble-map-renderer.js',
            'tree_map': 'tree-renderer.js',
            'flow_map': 'flow-renderer.js',
            'multi_flow_map': 'flow-renderer.js',
            'brace_map': 'brace-renderer.js',
            'bridge_map': 'flow-renderer.js',
            'flowchart': 'flow-renderer.js',
            'mindmap': 'mind-map-renderer.js',
            'mind_map': 'mind-map-renderer.js',
            'concept_map': 'concept-map-renderer.js'
        }
        
        renderer_filename = renderer_map.get(diagram_type)
        if renderer_filename:
            js_files_to_embed['renderer'] = Path(__file__).parent.parent.parent / 'static' / 'js' / 'renderers' / renderer_filename
            js_files_to_embed['shared_utilities'] = Path(__file__).parent.parent.parent / 'static' / 'js' / 'renderers' / 'shared-utilities.js'
        
        embedded_js_content = {}
        for key, path in js_files_to_embed.items():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if key == 'dynamic_loader':
                        # Patch dynamic-renderer-loader.js to prevent HTTP loading when files are embedded
                        # AND fix loadRenderer() to validate cached renderer objects
                        import re
                        
                        # Patch the loadScript method to check if script is already in DOM before making HTTP request
                        # This prevents failures when scripts are embedded directly in HTML
                        # Find the loadScript method and wrap it
                        load_script_pattern = r'(loadScript\(src\) \{[^}]+const existingScript = document\.querySelector[^}]+\}[^}]+if \(existingScript\) \{[^}]+\}[^}]+)'
                        
                        # Enhanced version that also checks cache
                        patched_load_script = r'''loadScript(src) {
        return new Promise((resolve, reject) => {
            // CRITICAL: Check cache first - if module is marked as loaded, skip HTTP request
            // BUT: Only skip if it's shared-utilities (which uses {renderer: true})
            // For actual renderer modules, we need the real renderer object, not just a flag
            const moduleMatch = src.match(/renderers\/([^/]+)\.js/);
            if (moduleMatch) {
                let moduleName = moduleMatch[1];
                // Only skip for shared-utilities (which uses {renderer: true} flag)
                // For renderer modules, we need the actual renderer object, so don't skip
                if (moduleName === 'shared-utilities' && this.cache && this.cache.has(moduleName)) {
                    console.log('[ExportPNG] Skipping HTTP load for ' + src + ' (shared-utilities already in cache)');
                    resolve();
                    return;
                }
                // For renderer modules, check if we have the actual renderer object (not just a flag)
                if (moduleName !== 'shared-utilities' && this.cache && this.cache.has(moduleName)) {
                    const cached = this.cache.get(moduleName);
                    // Only skip if we have the actual renderer object with functions
                    if (cached && cached.renderer && typeof cached.renderer === 'object' && Object.keys(cached.renderer).length > 0) {
                        console.log('[ExportPNG] Skipping HTTP load for ' + src + ' (renderer object already cached: ' + Object.keys(cached.renderer).join(', ') + ')');
                        resolve();
                        return;
                    }
                    // If cache has flag but no renderer object, clear it and load via HTTP
                    console.log('[ExportPNG] Cache has flag but no renderer object for ' + moduleName + ', loading via HTTP');
                    this.cache.delete(moduleName);
                }
            }
            
            // Append version query string for cache busting
            let versionedSrc = src;
            if (window.MINDGRAPH_VERSION) {
                const separator = src.includes('?') ? '&' : '?';
                versionedSrc = `${src}${separator}v=${window.MINDGRAPH_VERSION}`;
            }
            
            // Check if script is already loaded (check both versioned and unversioned)
            const existingScript = document.querySelector(`script[src="${versionedSrc}"]`) ||
                                   document.querySelector(`script[src="${src}"]`);
            if (existingScript) {
                resolve();
                return;
            }
            
            const script = document.createElement('script');
            script.src = versionedSrc;
            script.type = 'text/javascript';
            script.async = true;
            
            script.onload = () => resolve();
            script.onerror = () => reject(new Error(`Failed to load script: ${versionedSrc}`));
            
            document.head.appendChild(script);
        });
    }'''
                        
                        # Replace the loadScript method - need to match multiline function
                        # Match from "loadScript(src) {" to the closing "}" of the method
                        load_script_match = re.search(
                            r'loadScript\(src\) \{(.*?)\n    \}',
                            content,
                            flags=re.DOTALL
                        )
                        
                        if load_script_match:
                            # Replace the entire method
                            old_method = load_script_match.group(0)
                            content = content.replace(old_method, patched_load_script)
                            logger.debug(f"[ExportPNG] Successfully patched loadScript method")
                        
                        # CRITICAL: Patch loadRenderer() to validate cached renderer objects
                        # The cache might have {renderer: true} from old code, which is not a renderer object
                        # Find and replace the cache check: "if (cached.renderer) { return cached.renderer; }"
                        cache_check_pattern = r'if \(cached\.renderer\) \{\s+return cached\.renderer;\s+\}'
                        if re.search(cache_check_pattern, content):
                            patched_cache_check = r'''if (cached.renderer && typeof cached.renderer === 'object' && Object.keys(cached.renderer).length > 0) {
                console.log('[ExportPNG] Using cached renderer object:', Object.keys(cached.renderer));
                return cached.renderer;
            }
            // If cached.renderer is just a flag (true) or empty object, clear it and load properly
            if (cached.renderer === true || (cached.renderer && typeof cached.renderer === 'object' && Object.keys(cached.renderer).length === 0)) {
                console.warn('[ExportPNG] Cache has invalid renderer entry for ' + config.module + ' (flag or empty), clearing cache');
                this.cache.delete(config.module);
            }'''
                            content = re.sub(cache_check_pattern, patched_cache_check, content)
                            logger.debug(f"[ExportPNG] Successfully patched loadRenderer cache validation")
                        else:
                            logger.warning(f"[ExportPNG] Could not find loadScript method to patch - using fallback")
                            # Fallback: patch the specific loadScript calls in loadRenderer
                            # Try multiple variations of the string
                            replacements = [
                                ("const sharedPromise = this.loadScript('/static/js/renderers/shared-utilities.js')",
                                 """const sharedPromise = (() => {
                                    if (this.cache && this.cache.has('shared-utilities')) {
                                        console.log('[ExportPNG] Skipping HTTP load for shared-utilities.js (already in cache)');
                                        return Promise.resolve();
                                    }
                                    return this.loadScript('/static/js/renderers/shared-utilities.js');
                                })()"""),
                                ("const sharedPromise = this.loadScript(\"/static/js/renderers/shared-utilities.js\")",
                                 """const sharedPromise = (() => {
                                    if (this.cache && this.cache.has('shared-utilities')) {
                                        console.log('[ExportPNG] Skipping HTTP load for shared-utilities.js (already in cache)');
                                        return Promise.resolve();
                                    }
                                    return this.loadScript("/static/js/renderers/shared-utilities.js");
                                })()""")
                            ]
                            
                            for old_str, new_str in replacements:
                                if old_str in content:
                                    content = content.replace(old_str, new_str)
                                    logger.debug(f"[ExportPNG] Patched shared-utilities loadScript call")
                                    break
                            else:
                                # Try matching with the .then() call included
                                old_with_then = "const sharedPromise = this.loadScript('/static/js/renderers/shared-utilities.js')\n                .then(() => {"
                                if old_with_then in content:
                                    # Replace the entire block including .then()
                                    new_with_then = """const sharedPromise = (() => {
                                    if (this.cache && this.cache.has('shared-utilities')) {
                                        console.log('[ExportPNG] Skipping HTTP load for shared-utilities.js (already in cache)');
                                        return Promise.resolve().then(() => {
                                            this.cache.set('shared-utilities', { renderer: true });
                                        });
                                    }
                                    return this.loadScript('/static/js/renderers/shared-utilities.js').then(() => {"""
                                    content = content.replace(old_with_then, new_with_then)
                                    logger.debug(f"[ExportPNG] Patched shared-utilities loadScript call (with .then())")
                                else:
                                    logger.warning(f"[ExportPNG] Could not find shared-utilities loadScript call to patch")
                    embedded_js_content[key] = content
                logger.debug(f"[ExportPNG] JS file '{key}' loaded ({len(content)} bytes)")
            except Exception as e:
                logger.error(f"[ExportPNG] Failed to load JS file '{key}': {e}")
                raise RuntimeError(f"Required JavaScript file '{key}' not available at {path}")
        
        logger_js = embedded_js_content['logger']
        theme_config = embedded_js_content['theme_config']
        style_manager = embedded_js_content['style_manager']
        dynamic_loader = embedded_js_content['dynamic_loader']
        
        # Map diagram type to renderer info (needed for caching)
        renderer_info_map = {
            'bubble_map': {'module': 'bubble-map-renderer', 'renderer': 'BubbleMapRenderer'},
            'double_bubble_map': {'module': 'bubble-map-renderer', 'renderer': 'BubbleMapRenderer'},
            'circle_map': {'module': 'bubble-map-renderer', 'renderer': 'BubbleMapRenderer'},
            'tree_map': {'module': 'tree-renderer', 'renderer': 'TreeRenderer'},
            'flow_map': {'module': 'flow-renderer', 'renderer': 'FlowRenderer'},
            'multi_flow_map': {'module': 'flow-renderer', 'renderer': 'FlowRenderer'},
            'brace_map': {'module': 'brace-renderer', 'renderer': 'BraceRenderer'},
            'bridge_map': {'module': 'flow-renderer', 'renderer': 'FlowRenderer'},
            'flowchart': {'module': 'flow-renderer', 'renderer': 'FlowRenderer'},
            'mindmap': {'module': 'mind-map-renderer', 'renderer': 'MindMapRenderer'},
            'mind_map': {'module': 'mind-map-renderer', 'renderer': 'MindMapRenderer'},
            'concept_map': {'module': 'concept-map-renderer', 'renderer': 'ConceptMapRenderer'}
        }
        renderer_info = renderer_info_map.get(diagram_type, {})
        
        # Build renderer scripts section
        renderer_scripts_parts = [
            '<!-- Logger (MUST load first - required by dynamic-renderer-loader) -->',
            '<script>',
            logger_js,
            '</script>'
        ]
        
        # Add shared-utilities if we have a renderer
        if 'shared_utilities' in embedded_js_content:
            renderer_scripts_parts.extend([
                '<!-- Shared Utilities (required by renderers) -->',
                '<script>',
                embedded_js_content['shared_utilities'],
                '</script>'
            ])
        
        # Add renderer if we have one
        if 'renderer' in embedded_js_content:
            renderer_scripts_parts.extend([
                f'<!-- Renderer for {diagram_type} -->',
                '<script>',
                embedded_js_content['renderer'],
                '</script>'
            ])
        
        # Add renderer-dispatcher.js (provides renderGraph function)
        renderer_dispatcher_path = Path(__file__).parent.parent.parent / 'static' / 'js' / 'renderers' / 'renderer-dispatcher.js'
        if renderer_dispatcher_path.exists():
            try:
                with open(renderer_dispatcher_path, 'r', encoding='utf-8') as f:
                    renderer_dispatcher_js = f.read()
                renderer_scripts_parts.extend([
                    '<!-- Renderer Dispatcher (provides renderGraph function) -->',
                    '<script>',
                    renderer_dispatcher_js,
                    '</script>'
                ])
                logger.debug(f"[ExportPNG] Loaded renderer-dispatcher.js ({len(renderer_dispatcher_js)} bytes)")
            except Exception as e:
                logger.error(f"[ExportPNG] Failed to load renderer-dispatcher.js: {e}")
                raise RuntimeError(f"Required JavaScript file 'renderer-dispatcher.js' not available at {renderer_dispatcher_path}")
        
        # Add dynamic renderer loader last (it will use the already-loaded renderer)
        renderer_scripts_parts.extend([
            '<!-- Dynamic Renderer Loader -->',
            '<script>',
            dynamic_loader,
            '</script>',
            '<!-- Note: Renderer caching happens in waitForD3() BEFORE renderGraph() is called -->'
        ])
        
        renderer_scripts = '\n        '.join(renderer_scripts_parts)
        
        # Calculate optimized dimensions for different graph types (like old version)
        dimensions = config.get_d3_dimensions()
        
        if diagram_type == 'bridge_map' and diagram_data and 'analogies' in diagram_data:
            num_analogies = len(diagram_data['analogies'])
            min_width_per_analogy = 120
            min_padding = 40
            content_width = (num_analogies * min_width_per_analogy) + ((num_analogies - 1) * 60)
            optimal_width = max(content_width + (2 * min_padding), 600)
            optimal_height = max(90 + (2 * min_padding), 200)
            
            dimensions = {
                'baseWidth': optimal_width,
                'baseHeight': optimal_height,
                'padding': min_padding,
                'width': optimal_width,
                'height': optimal_height,
                'topicFontSize': dimensions.get('topicFontSize', 26),
                'charFontSize': dimensions.get('charFontSize', 22)
            }
        elif diagram_type == 'brace_map' and diagram_data:
            optimal_dims = diagram_data.get('_optimal_dimensions', {})
            svg_data = diagram_data.get('_svg_data', {})
            
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
            elif diagram_data.get('success') and svg_data and 'width' in svg_data and 'height' in svg_data:
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
            else:
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
        elif diagram_type in ('multi_flow_map', 'flow_map', 'tree_map', 'concept_map') and isinstance(diagram_data, dict):
            try:
                rd = diagram_data.get('_recommended_dimensions') or {}
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
                logger.warning(f"[ExportPNG] Failed to apply recommended dimensions: {e}")
        
        # Build font-face declarations only for fonts that exist
        font_faces = []
        font_files = [
            ("inter-400.ttf", 400),
            ("inter-600.ttf", 600),
            ("inter-700.ttf", 700),
        ]
        
        for font_file, weight in font_files:
            font_base64 = _get_font_base64(font_file)
            if font_base64:  # Only add if font was successfully loaded
                font_faces.append(f'''
            @font-face {{
                font-display: swap;
                font-family: 'Inter';
                font-style: normal;
                font-weight: {weight};
                src: url('data:font/truetype;base64,{font_base64}') format('truetype');
            }}''')
        
        font_css = '\n'.join(font_faces) if font_faces else '/* No fonts available - using system fonts */'
        
        # Build HTML exactly like old version
        html = f'''<!DOCTYPE html>
        <html><head>
        <meta charset="utf-8">
        {d3_script_tag}
        <style>
            body {{ margin:0; background:#fff; }}
            #d3-container {{ 
                width: 100%; 
                height: 100vh; 
                display: block; 
            }}
            
            /* Inter Font Loading for Ubuntu Server Compatibility */
            {font_css}
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
        // Initialize rendering flags
        window.renderingComplete = false;
        window.renderingError = null;
        
        // Wait for D3.js and all scripts to load
        async function waitForD3() {{
            if (typeof d3 !== "undefined") {{
                try {{
                    // Wait a moment for all scripts to fully initialize
                    await new Promise(resolve => setTimeout(resolve, 100));
                    
                    // Mark shared-utilities as loaded (it doesn't need a renderer object)
                    if (typeof window.dynamicRendererLoader !== "undefined" && window.dynamicRendererLoader.cache) {{
                        if (!window.dynamicRendererLoader.cache.has('shared-utilities')) {{
                            window.dynamicRendererLoader.cache.set('shared-utilities', {{ renderer: true }});
                        }}
                    }}
                    
                    // Since scripts are embedded and execute synchronously, renderer should be available immediately
                    // Pre-cache the renderer object so loadRenderer() can find it
                    const rendererModuleMap = {{
                        'bubble_map': {{ module: 'bubble-map-renderer', renderer: 'BubbleMapRenderer' }},
                        'double_bubble_map': {{ module: 'bubble-map-renderer', renderer: 'BubbleMapRenderer' }},
                        'circle_map': {{ module: 'bubble-map-renderer', renderer: 'BubbleMapRenderer' }},
                        'tree_map': {{ module: 'tree-renderer', renderer: 'TreeRenderer' }},
                        'flow_map': {{ module: 'flow-renderer', renderer: 'FlowRenderer' }},
                        'multi_flow_map': {{ module: 'flow-renderer', renderer: 'FlowRenderer' }},
                        'brace_map': {{ module: 'brace-renderer', renderer: 'BraceRenderer' }},
                        'bridge_map': {{ module: 'flow-renderer', renderer: 'FlowRenderer' }},
                        'flowchart': {{ module: 'flow-renderer', renderer: 'FlowRenderer' }},
                        'mindmap': {{ module: 'mind-map-renderer', renderer: 'MindMapRenderer' }},
                        'mind_map': {{ module: 'mind-map-renderer', renderer: 'MindMapRenderer' }},
                        'concept_map': {{ module: 'concept-map-renderer', renderer: 'ConceptMapRenderer' }}
                    }};
                    
                    const rendererInfo = rendererModuleMap['{diagram_type}'];
                    if (!rendererInfo) {{
                        throw new Error('No renderer info found for diagram type: ' + '{diagram_type}');
                    }}
                    
                    if (!window.dynamicRendererLoader || !window.dynamicRendererLoader.cache) {{
                        throw new Error('dynamicRendererLoader not available');
                    }}
                    
                    // Get renderer from window (should be available immediately since scripts are embedded)
                    const rendererObj = window[rendererInfo.renderer];
                    if (!rendererObj || typeof rendererObj !== 'object' || Object.keys(rendererObj).length === 0) {{
                        const availableRenderers = Object.keys(window).filter(k => k.includes('Renderer'));
                        throw new Error('Renderer ' + rendererInfo.renderer + ' not found or empty. Available: ' + availableRenderers.join(', '));
                    }}
                    
                    // Cache the renderer object so loadRenderer() can find it
                    window.dynamicRendererLoader.cache.set(rendererInfo.module, {{ renderer: rendererObj }});
                    
                    window.spec = {json.dumps(diagram_data, ensure_ascii=False)};
                    window.graph_type = "{diagram_type}";
                    
                    // Get theme using style manager (centralized theme system)
                    let theme;
                    let backendTheme;
                    if (typeof styleManager !== "undefined" && typeof styleManager.getTheme === "function") {{
                        theme = styleManager.getTheme(window.graph_type);
                    }} else {{
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
                    }}
                    
                    // Check for renderGraph function (from renderer-dispatcher) or dynamicRendererLoader
                    let renderPromise;
                    
                    if (typeof renderGraph === 'function') {{
                        // Use renderGraph from renderer-dispatcher (preferred)
                        console.log('[ExportPNG] Using renderGraph from renderer-dispatcher');
                        try {{
                            renderPromise = renderGraph(window.graph_type, window.spec, backendTheme, window.dimensions);
                        }} catch (e) {{
                            console.error('[ExportPNG] Error calling renderGraph:', e);
                            throw new Error('renderGraph call failed: ' + e.message);
                        }}
                    }} else if (typeof window.dynamicRendererLoader !== 'undefined' && typeof window.dynamicRendererLoader.renderGraph === 'function') {{
                        // Fallback to dynamicRendererLoader.renderGraph
                        console.log('[ExportPNG] Using dynamicRendererLoader.renderGraph');
                        try {{
                            renderPromise = window.dynamicRendererLoader.renderGraph(window.graph_type, window.spec, backendTheme, window.dimensions);
                        }} catch (e) {{
                            console.error('[ExportPNG] Error calling dynamicRendererLoader.renderGraph:', e);
                            console.error('[ExportPNG] Cache state:', Array.from(window.dynamicRendererLoader.cache.keys()));
                            const cached = window.dynamicRendererLoader.cache.get(rendererInfo.module);
                            console.error('[ExportPNG] Cached renderer:', cached ? Object.keys(cached.renderer || {{}}) : 'null');
                            throw new Error('dynamicRendererLoader.renderGraph call failed: ' + e.message);
                        }}
                    }} else {{
                        const availableInfo = {{
                            renderGraph: typeof renderGraph,
                            dynamicRendererLoader: typeof window.dynamicRendererLoader,
                            dynamicRendererLoaderRenderGraph: typeof window.dynamicRendererLoader?.renderGraph,
                            cacheKeys: Array.from(window.dynamicRendererLoader?.cache?.keys() || [])
                        }};
                        console.error('[ExportPNG] Available functions:', availableInfo);
                        throw new Error('Neither renderGraph nor dynamicRendererLoader.renderGraph is available. ' + JSON.stringify(availableInfo));
                    }}
                    
                    // Wait for rendering to complete and set flag
                    if (renderPromise && typeof renderPromise.then === 'function') {{
                        await renderPromise;
                        console.log('[ExportPNG] Rendering completed successfully');
                        window.renderingComplete = true;
                    }} else {{
                        // Not a promise, wait a bit for rendering to complete
                        console.log('[ExportPNG] Render function did not return a promise, waiting 2s...');
                        await new Promise(resolve => setTimeout(resolve, 2000));
                        window.renderingComplete = true;
                    }}
                }} catch (error) {{
                    console.error("Render error:", error);
                    window.renderingError = error.toString();
                    window.renderingComplete = true;
                }}
            }} else {{
                setTimeout(waitForD3, 100);
            }}
        }}
        waitForD3();
        </script>
        </body></html>
        '''
        
        logger.debug(f"[ExportPNG] HTML content length: {len(html)} characters")
        
        # Create browser context (like old version)
        logger.debug(f"[ExportPNG] Creating browser context")
        async with BrowserContextManager() as context:
            page = await context.new_page()
            
            # Set up route handler to serve renderer files from disk
            # This allows dynamic-renderer-loader.js to load renderer modules via HTTP
            async def handle_route(route):
                url = route.request.url
                logger.debug(f"[ExportPNG] Route intercepted: {url}")
                
                # Extract path from URL (handles both absolute and relative paths)
                # Match patterns like: /static/js/renderers/shared-utilities.js
                # or: http://localhost:9527/static/js/renderers/shared-utilities.js
                # or: about:blank/static/js/renderers/shared-utilities.js (from set_content)
                if '/static/js/renderers/' in url or url.endswith('.js') and 'renderers' in url:
                    # Extract filename from URL - handle various URL formats
                    if '/static/js/renderers/' in url:
                        filename = url.split('/static/js/renderers/')[-1].split('?')[0]
                    elif url.endswith('.js'):
                        # Handle relative paths
                        filename = url.split('/')[-1].split('?')[0]
                    else:
                        filename = None
                    
                    if filename:
                        renderer_path = Path(__file__).parent.parent.parent / 'static' / 'js' / 'renderers' / filename
                        
                        if renderer_path.exists():
                            try:
                                with open(renderer_path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                await route.fulfill(
                                    status=200,
                                    content_type='application/javascript',
                                    body=content
                                )
                                logger.debug(f"[ExportPNG] Served renderer file via route: {filename}")
                                return
                            except Exception as e:
                                logger.error(f"[ExportPNG] Failed to read renderer file {filename}: {e}")
                        else:
                            logger.warning(f"[ExportPNG] Renderer file not found: {renderer_path} (requested: {url})")
                
                # Let other requests pass through (for D3.js if loaded via URL)
                await route.continue_()
            
            # Set up route interception BEFORE loading content
            await page.route('**/*', handle_route)
            
            # Set timeout and log HTML size and structure (like old version)
            html_size = len(html)
            timeout_ms = 60000  # 60 seconds for all content
            logger.debug(f"[ExportPNG] HTML content size: {html_size} characters")
            
            # Set up comprehensive console and error logging BEFORE loading content (like old version)
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
            page.on("requestfailed", lambda request: logger.error(f"RESOURCE FAILED: {request.url} - {request.failure}"))
            page.on("response", lambda response: logger.debug(f"RESOURCE LOADED: {response.url} - {response.status}") if response.status >= 400 else None)
            
            # Set timeout (like old version)
            page.set_default_timeout(60000)
            page.set_default_navigation_timeout(60000)
            
            # Try to load the content with more detailed error handling (like old version)
            try:
                await page.set_content(html, timeout=timeout_ms)
                logger.debug("[ExportPNG] HTML content loaded successfully")
            except Exception as e:
                logger.error(f"[ExportPNG] Failed to set HTML content: {e}")
                raise
            
            # Wait for rendering to complete by polling the flag
            logger.debug("[ExportPNG] Waiting for rendering to complete")
            max_wait = 15  # seconds
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
                logger.error(f"[ExportPNG] Rendering error in browser: {rendering_error}")
                # Log console messages for debugging
                if console_messages:
                    logger.error(f"[ExportPNG] Browser console messages: {len(console_messages)}")
                    for i, msg in enumerate(console_messages[-20:]):
                        logger.error(f"[ExportPNG] Console {i+1}: {msg}")
                if page_errors:
                    logger.error(f"[ExportPNG] Browser errors: {len(page_errors)}")
                    for i, error in enumerate(page_errors):
                        logger.error(f"[ExportPNG] Browser Error {i+1}: {error}")
                raise Exception(f"Browser rendering failed: {rendering_error}")
            
            # Wait for SVG element to appear
            logger.debug("[ExportPNG] Waiting for SVG element")
            try:
                await page.wait_for_selector('svg', timeout=5000)
                logger.debug("[ExportPNG] SVG element found")
            except Exception as e:
                logger.error(f"[ExportPNG] Timeout waiting for SVG element: {e}")
                # Log console messages and errors for debugging
                if console_messages:
                    logger.error(f"[ExportPNG] Browser console messages: {len(console_messages)}")
                    for i, msg in enumerate(console_messages[-20:]):
                        logger.error(f"[ExportPNG] Console {i+1}: {msg}")
                if page_errors:
                    logger.error(f"[ExportPNG] Browser errors: {len(page_errors)}")
                    for i, error in enumerate(page_errors):
                        logger.error(f"[ExportPNG] Browser Error {i+1}: {error}")
                raise ValueError("SVG element not found. The graph could not be rendered.")
            
            # Log console messages and errors (like old version)
            if console_messages:
                logger.debug(f"[ExportPNG] Browser console messages: {len(console_messages)}")
                for i, msg in enumerate(console_messages[-10:]):
                    logger.debug(f"[ExportPNG] Console {i+1}: {msg}")
            if page_errors:
                logger.error(f"[ExportPNG] Browser errors: {len(page_errors)}")
                for i, error in enumerate(page_errors):
                    logger.error(f"[ExportPNG] Browser Error {i+1}: {error}")
            
            # Wait for SVG element to be created with timeout (like old version)
            try:
                element = await page.wait_for_selector("svg", timeout=10000)
                logger.debug("[ExportPNG] SVG element found successfully")
            except Exception as e:
                logger.error(f"[ExportPNG] Timeout waiting for SVG element: {e}")
                element = await page.query_selector("svg")  # Try one more time
            
            # Check if SVG exists and has content (like old version)
            if element is None:
                logger.error("[ExportPNG] SVG element not found in rendered page")
                raise ValueError("SVG element not found. The graph could not be rendered.")
            
            # Check SVG dimensions (like old version)
            svg_width = await element.get_attribute('width')
            svg_height = await element.get_attribute('height')
            logger.debug(f"[ExportPNG] SVG dimensions: width={svg_width}, height={svg_height}")
            
            # Ensure element is visible before screenshot (like old version)
            await element.scroll_into_view_if_needed()
            
            # Wait for element to be ready for screenshot (like old version)
            try:
                await page.wait_for_function('''
                    () => {
                        const svg = document.querySelector('svg');
                        if (!svg) return false;
                        const rect = svg.getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0;
                    }
                ''', timeout=2000)
                logger.debug("[ExportPNG] Element ready for screenshot")
            except Exception as e:
                logger.warning(f"[ExportPNG] Element not ready for screenshot within 2s timeout: {e}")
                await page.wait_for_timeout(200)  # Fallback wait
            
            # Take screenshot using SVG element directly (like old version)
            logger.debug("[ExportPNG] Taking screenshot")
            screenshot_bytes = await element.screenshot(omit_background=False, timeout=60000)
            logger.debug(f"[ExportPNG] Screenshot taken: {len(screenshot_bytes)} bytes")
        
        logger.info(f"[ExportPNG] PNG generated successfully: {len(screenshot_bytes)} bytes")
        return screenshot_bytes
        
    except Exception as e:
        logger.error(f"[ExportPNG] Error during PNG export: {e}", exc_info=True)
        raise


@router.post('/export_png')
async def export_png(
    req: ExportPNGRequest,
    request: Request,
    x_language: str = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key)
):
    """
    Export diagram as PNG using Playwright browser automation (async).
    
    Uses the core export function that embeds JS directly for reliability.
    This avoids HTTP script loading issues and ensures consistent behavior.
    
    Rate limited: 100 requests per minute per user/IP (PNG generation is expensive).
    """
    # Rate limiting: 100 requests per minute per user/IP (PNG generation is expensive)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit('export_png', identifier, max_requests=100, window_seconds=60)
    
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
        # Normalize diagram type (same as generate_dingtalk)
        if diagram_type == 'mindmap':
            diagram_type = 'mind_map'
        
        # Ensure diagram_data is a dict and add any missing metadata (same as generate_dingtalk)
        if isinstance(diagram_data, dict):
            # Add learning sheet metadata if not present (defaults to False/0)
            if 'is_learning_sheet' not in diagram_data:
                diagram_data['is_learning_sheet'] = False
            if 'hidden_node_percentage' not in diagram_data:
                diagram_data['hidden_node_percentage'] = 0
        
        # Use the core export function which embeds JS directly (more reliable than HTTP loading)
        # Match generate_dingtalk exactly: same defaults, same parameters
        screenshot_bytes = await _export_png_core(
            diagram_data=diagram_data,
            diagram_type=diagram_type,
            width=req.width or 1200,
            height=req.height or 800,
            scale=req.scale or 2,
            x_language=x_language
        )
        
        # Return PNG as response
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


@router.post('/generate_png')
async def generate_png_from_prompt(
    req: GeneratePNGRequest,
    request: Request,
    x_language: str = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key)
):
    """
    Generate PNG directly from user prompt using simplified prompt-to-diagram agent.
    
    Uses only Qwen in a single LLM call for fast, efficient diagram generation.
    
    Rate limited: 100 requests per minute per user/IP (PNG generation is expensive).
    """
    # Rate limiting: 100 requests per minute per user/IP (PNG generation is expensive)
    identifier = get_rate_limit_identifier(current_user, request)
    await check_endpoint_rate_limit('generate_png', identifier, max_requests=100, window_seconds=60)
    
    lang = get_request_language(x_language)
    prompt = req.prompt.strip()
    
    if not prompt:
        raise HTTPException(status_code=400, detail=Messages.error("invalid_prompt", lang))
    
    language = req.language.value if req.language and hasattr(req.language, 'value') else str(req.language) if req.language else 'zh'
    if language not in ['zh', 'en']:
        raise HTTPException(status_code=400, detail="Invalid language. Must be 'zh' or 'en'")
    
    logger.info(f"[GeneratePNG] Request: prompt='{prompt}', language='{language}'")
    
    try:
        # Use simplified prompt-to-diagram approach (single Qwen call)
        user_id = current_user.id if current_user and hasattr(current_user, 'id') else None
        organization_id = getattr(current_user, 'organization_id', None) if current_user and hasattr(current_user, 'id') else None
        
        # Detect learning sheet from prompt
        from agents.main_agent import _detect_learning_sheet_from_prompt, _clean_prompt_for_learning_sheet
        is_learning_sheet = _detect_learning_sheet_from_prompt(prompt, language)
        logger.debug(f"[GeneratePNG] Learning sheet detected: {is_learning_sheet}")
        
        # Clean prompt for learning sheets to generate actual content, not meta-content
        generation_prompt = _clean_prompt_for_learning_sheet(prompt) if is_learning_sheet else prompt
        if is_learning_sheet:
            logger.debug(f"[GeneratePNG] Using cleaned prompt for generation: '{generation_prompt}'")
        
        # Get prompt from centralized system
        from prompts import get_prompt
        prompt_template = get_prompt('prompt_to_diagram', language, 'generation')
        
        if not prompt_template:
            raise HTTPException(status_code=500, detail=Messages.error("generation_failed", lang, f"No prompt template found for language {language}"))
        
        # Format prompt with cleaned user input
        formatted_prompt = prompt_template.format(user_prompt=generation_prompt)
        
        # Call LLM service - single call with Qwen only
        from services.llm_service import llm_service
        from services.redis_token_buffer import get_token_tracker
        from config.settings import config
        from agents.core.agent_utils import extract_json_from_response
        
        # Get API key ID from request state if API key was used
        api_key_id = None
        if hasattr(request, 'state'):
            api_key_id = getattr(request.state, 'api_key_id', None)
            if api_key_id:
                logger.debug(f"[GeneratePNG] Using API key ID {api_key_id} for token tracking")
        else:
            logger.debug(f"[GeneratePNG] Request state not available")
        
        start_time = time.time()
        response, usage_data = await llm_service.chat_with_usage(
            prompt=formatted_prompt,
            model='qwen',  # Force Qwen only
            max_tokens=2000,
            temperature=config.LLM_TEMPERATURE,
            user_id=user_id,
            organization_id=organization_id,
            api_key_id=api_key_id,
            request_type='diagram_generation',
            endpoint_path='/api/generate_png'
        )
        
        if not response:
            raise HTTPException(status_code=500, detail=Messages.error("generation_failed", lang, "No response from LLM"))
        
        # Extract JSON from response
        result = extract_json_from_response(response)
        
        if not isinstance(result, dict) or 'spec' not in result:
            raise HTTPException(status_code=500, detail=Messages.error("generation_failed", lang, "Invalid response format from LLM"))
        
        spec = result.get('spec', {})
        diagram_type = result.get('diagram_type', 'bubble_map')
        
        # Normalize diagram type
        if diagram_type == 'mindmap':
            diagram_type = 'mind_map'
        
        # Add learning sheet metadata to spec object so renderers can access it
        if isinstance(spec, dict):
            hidden_percentage = 0.2 if is_learning_sheet else 0
            spec['is_learning_sheet'] = is_learning_sheet
            spec['hidden_node_percentage'] = hidden_percentage
            logger.debug(f"[GeneratePNG] Added learning sheet metadata to spec: is_learning_sheet={is_learning_sheet}, hidden_percentage={hidden_percentage}")
        
        # Track tokens with correct diagram_type
        if usage_data:
            try:
                input_tokens = usage_data.get('prompt_tokens') or usage_data.get('input_tokens') or 0
                output_tokens = usage_data.get('completion_tokens') or usage_data.get('output_tokens') or 0
                total_tokens = usage_data.get('total_tokens') or None
                response_time = time.time() - start_time
                
                token_tracker = get_token_tracker()
                await token_tracker.track_usage(
                    model_alias='qwen',
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    request_type='diagram_generation',
                    diagram_type=diagram_type,
                    user_id=user_id,
                    organization_id=organization_id,
                    api_key_id=api_key_id,
                    endpoint_path='/api/generate_png',
                    response_time=response_time,
                    success=True
                )
            except Exception as e:
                logger.warning(f"[GeneratePNG] Token tracking failed (non-critical): {e}", exc_info=False)
        
        if isinstance(spec, dict) and spec.get('error'):
            raise HTTPException(status_code=400, detail=spec.get('error'))
        
        # For mindmaps, enhance spec with layout data if missing
        if diagram_type == 'mind_map' and isinstance(spec, dict):
            if not spec.get('_layout') or not spec.get('_layout', {}).get('positions'):
                logger.debug("[GeneratePNG] Mindmap spec missing layout data, enhancing with MindMapAgent")
                try:
                    from agents.mind_maps.mind_map_agent import MindMapAgent
                    mind_map_agent = MindMapAgent(model='qwen')
                    enhanced_spec = await mind_map_agent.enhance_spec(spec)
                    
                    if enhanced_spec.get('_layout'):
                        spec = enhanced_spec
                        logger.debug("[GeneratePNG] Mindmap layout data added successfully")
                    else:
                        logger.warning("[GeneratePNG] MindMapAgent failed to generate layout data")
                except Exception as e:
                    logger.error(f"[GeneratePNG] Error enhancing mindmap spec: {e}", exc_info=True)
                    # Continue with original spec - renderer will show error message
        
        # Export PNG using core function
        screenshot_bytes = await _export_png_core(
            diagram_data=spec,
            diagram_type=diagram_type,
            width=req.width or 1200,
            height=req.height or 800,
            scale=req.scale or 2,
            x_language=x_language
        )
        
        # Broadcast activity to dashboard stream (if user is authenticated)
        if user_id:
            try:
                from services.activity_stream import get_activity_stream_service
                activity_service = get_activity_stream_service()
                user_name = getattr(current_user, 'name', None) if current_user else None
                
                # Format topic based on diagram type
                topic_display = prompt[:50]  # Default: truncate prompt
                if diagram_type == 'double_bubble_map' and isinstance(spec, dict):
                    left = spec.get('left', '')
                    right = spec.get('right', '')
                    if left and right:
                        # Format as "Left vs Right" (English) or "左和右" (Chinese)
                        topic_display = f"{left} vs {right}" if language == 'en' else f"{left}和{right}"
                    elif left or right:
                        topic_display = left or right
                
                await activity_service.broadcast_activity(
                    user_id=user_id,
                    action="generated",
                    diagram_type=diagram_type,
                    topic=topic_display[:50],  # Truncate to 50 chars
                    user_name=user_name
                )
            except Exception as e:
                logger.debug(f"Failed to broadcast activity: {e}")
        
        return Response(
            content=screenshot_bytes,
            media_type="image/png",
            headers={'Content-Disposition': 'attachment; filename="diagram.png"'}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[GeneratePNG] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=Messages.error("generation_failed", lang, str(e)))


@router.post('/generate_dingtalk')
async def generate_dingtalk_png(
    req: GenerateDingTalkRequest,
    request: Request,
    x_language: str = None,
    current_user: Optional[User] = Depends(get_current_user_or_api_key)
):
    """
    Generate PNG for DingTalk integration using simplified prompt-to-diagram agent.
    
    Uses only Qwen in a single LLM call. Saves PNG to temp folder and returns
    plain text in ![]() format for DingTalk bot integration.
    """
    lang = get_request_language(x_language)
    prompt = req.prompt.strip()
    
    if not prompt:
        raise HTTPException(
            status_code=400,
            detail=Messages.error("invalid_prompt", lang)
        )
    
    try:
        # Handle language - default to 'zh' if not provided
        language = req.language.value if req.language and hasattr(req.language, 'value') else str(req.language) if req.language else 'zh'
        if language not in ['zh', 'en']:
            raise HTTPException(status_code=400, detail="Invalid language. Must be 'zh' or 'en'")
        
        logger.info("[GenerateDingTalk] Request: prompt='%s', language='%s'", prompt, language)
        
        # Handle current_user
        user_id = None
        organization_id = None
        if current_user and hasattr(current_user, 'id'):
            user_id = current_user.id
            organization_id = getattr(current_user, 'organization_id', None)
        
        # Detect learning sheet from prompt
        from agents.main_agent import _detect_learning_sheet_from_prompt, _clean_prompt_for_learning_sheet
        is_learning_sheet = _detect_learning_sheet_from_prompt(prompt, language)
        logger.debug(f"[GenerateDingTalk] Learning sheet detected: {is_learning_sheet}")
        
        # Clean prompt for learning sheets to generate actual content, not meta-content
        generation_prompt = _clean_prompt_for_learning_sheet(prompt) if is_learning_sheet else prompt
        if is_learning_sheet:
            logger.debug(f"[GenerateDingTalk] Using cleaned prompt for generation: '{generation_prompt}'")
        
        # Use simplified prompt-to-diagram approach (single Qwen call)
        from prompts import get_prompt
        prompt_template = get_prompt('prompt_to_diagram', language, 'generation')
        
        if not prompt_template:
            raise HTTPException(
                status_code=500,
                detail=Messages.error("generation_failed", lang, f"No prompt template found for language {language}")
            )
        
        # Format prompt with cleaned user input
        formatted_prompt = prompt_template.format(user_prompt=generation_prompt)
        
        # Call LLM service - single call with Qwen only
        from services.llm_service import llm_service
        from services.redis_token_buffer import get_token_tracker
        from config.settings import config
        from agents.core.agent_utils import extract_json_from_response
        
        # Get API key ID from request state if API key was used
        api_key_id = None
        if hasattr(request, 'state'):
            api_key_id = getattr(request.state, 'api_key_id', None)
        
        start_time = time.time()
        response, usage_data = await llm_service.chat_with_usage(
            prompt=formatted_prompt,
            model='qwen',  # Force Qwen only
            max_tokens=2000,
            temperature=config.LLM_TEMPERATURE,
            user_id=user_id,
            organization_id=organization_id,
            api_key_id=api_key_id,
            request_type='diagram_generation',
            endpoint_path='/api/generate_dingtalk'
        )
        
        if not response:
            raise HTTPException(
                status_code=500,
                detail=Messages.error("generation_failed", lang, "No response from LLM")
            )
        
        # Extract JSON from response
        result = extract_json_from_response(response)
        
        if not isinstance(result, dict) or 'spec' not in result:
            raise HTTPException(
                status_code=500,
                detail=Messages.error("generation_failed", lang, "Invalid response format from LLM")
            )
        
        spec = result.get('spec', {})
        diagram_type = result.get('diagram_type', 'bubble_map')
        
        # Normalize diagram type
        if diagram_type == 'mindmap':
            diagram_type = 'mind_map'
        
        # Add learning sheet metadata to spec object so renderers can access it
        if isinstance(spec, dict):
            hidden_percentage = 0.2 if is_learning_sheet else 0
            spec['is_learning_sheet'] = is_learning_sheet
            spec['hidden_node_percentage'] = hidden_percentage
            logger.debug(f"[GenerateDingTalk] Added learning sheet metadata to spec: is_learning_sheet={is_learning_sheet}, hidden_percentage={hidden_percentage}")
        
        # Track tokens with correct diagram_type
        if usage_data:
            try:
                input_tokens = usage_data.get('prompt_tokens') or usage_data.get('input_tokens') or 0
                output_tokens = usage_data.get('completion_tokens') or usage_data.get('output_tokens') or 0
                total_tokens = usage_data.get('total_tokens') or None
                response_time = time.time() - start_time
                
                token_tracker = get_token_tracker()
                await token_tracker.track_usage(
                    model_alias='qwen',
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    request_type='diagram_generation',
                    diagram_type=diagram_type,
                    user_id=user_id,
                    organization_id=organization_id,
                    api_key_id=api_key_id,
                    endpoint_path='/api/generate_dingtalk',
                    response_time=response_time,
                    success=True
                )
            except Exception as e:
                logger.warning(f"[GenerateDingTalk] Token tracking failed (non-critical): {e}", exc_info=False)
        
        if isinstance(spec, dict) and spec.get('error'):
            raise HTTPException(status_code=400, detail=spec.get('error'))
        
        # For mindmaps, enhance spec with layout data if missing
        if diagram_type == 'mind_map' and isinstance(spec, dict):
            if not spec.get('_layout') or not spec.get('_layout', {}).get('positions'):
                logger.debug("[GenerateDingTalk] Mindmap spec missing layout data, enhancing with MindMapAgent")
                try:
                    from agents.mind_maps.mind_map_agent import MindMapAgent
                    mind_map_agent = MindMapAgent(model='qwen')
                    enhanced_spec = await mind_map_agent.enhance_spec(spec)
                    
                    if enhanced_spec.get('_layout'):
                        spec = enhanced_spec
                        logger.debug("[GenerateDingTalk] Mindmap layout data added successfully")
                    else:
                        logger.warning("[GenerateDingTalk] MindMapAgent failed to generate layout data")
                except Exception as e:
                    logger.error("[GenerateDingTalk] Error enhancing mindmap spec: %s", e, exc_info=True)
                    # Continue with original spec - renderer will show error message
        
        # Export PNG using core helper function
        screenshot_bytes = await _export_png_core(
            diagram_data=spec,
            diagram_type=diagram_type,
            width=1200,
            height=800,
            scale=2,
            x_language=x_language
        )
        
        # Broadcast activity to dashboard stream (if user is authenticated)
        if user_id:
            try:
                from services.activity_stream import get_activity_stream_service
                activity_service = get_activity_stream_service()
                user_name = getattr(current_user, 'name', None) if current_user else None
                
                # Format topic based on diagram type
                topic_display = prompt[:50]  # Default: truncate prompt
                if diagram_type == 'double_bubble_map' and isinstance(spec, dict):
                    left = spec.get('left', '')
                    right = spec.get('right', '')
                    if left and right:
                        # Format as "Left vs Right" (English) or "左和右" (Chinese)
                        topic_display = f"{left} vs {right}" if language == 'en' else f"{left}和{right}"
                    elif left or right:
                        topic_display = left or right
                
                await activity_service.broadcast_activity(
                    user_id=user_id,
                    action="generated",
                    diagram_type=diagram_type,
                    topic=topic_display[:50],  # Truncate to 50 chars
                    user_name=user_name
                )
            except Exception as e:
                logger.debug(f"Failed to broadcast activity: {e}")
        
        # Save PNG to temp directory (ASYNC file I/O)
        temp_dir = Path("temp_images")
        temp_dir.mkdir(exist_ok=True)
        
        # Generate unique filename
        unique_id = uuid.uuid4().hex[:8]
        timestamp = int(time.time())
        filename = f"dingtalk_{unique_id}_{timestamp}.png"
        temp_path = temp_dir / filename
        
        # Write PNG content to file using aiofiles (100% async, non-blocking)
        async with aiofiles.open(temp_path, 'wb') as f:
            await f.write(screenshot_bytes)
        
        # Generate signed URL for security (24 hour expiration)
        signed_path = generate_signed_url(filename, expiration_seconds=86400)
        
        # Build plain text response in ![](url) format (empty alt text)
        # Priority order: EXTERNAL_BASE_URL → X-Forwarded-* headers → EXTERNAL_HOST:PORT
        # This ensures HTTPS URLs are used when EXTERNAL_BASE_URL is set, preventing mixed content issues
        external_base_url = os.getenv('EXTERNAL_BASE_URL', '').rstrip('/')
        
        if external_base_url:
            # Explicit override - use EXTERNAL_BASE_URL directly (highest priority)
            image_url = f"{external_base_url}/api/temp_images/{signed_path}"
        else:
            # Try reverse proxy headers
            forwarded_proto = request.headers.get('X-Forwarded-Proto')
            forwarded_host = request.headers.get('X-Forwarded-Host')
            
            if forwarded_proto and forwarded_host:
                # Behind reverse proxy - use forwarded values (no port needed)
                protocol = forwarded_proto
                image_url = f"{protocol}://{forwarded_host}/api/temp_images/{signed_path}"
            else:
                # Direct access - use backend protocol and EXTERNAL_HOST with port
                protocol = request.url.scheme
                external_host = os.getenv('EXTERNAL_HOST', 'localhost')
                port = os.getenv('PORT', '9527')
                image_url = f"{protocol}://{external_host}:{port}/api/temp_images/{signed_path}"
        
        plain_text = f"![]({image_url})"
        
        logger.info("[GenerateDingTalk] Success: %s", image_url)
        
        return PlainTextResponse(content=plain_text)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("[GenerateDingTalk] Error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=Messages.error("generation_failed", lang, str(e))
        )


@router.get('/temp_images/{filepath:path}')
async def serve_temp_image(filepath: str, sig: Optional[str] = None, exp: Optional[int] = None):
    """
    Serve temporary PNG files for DingTalk integration.
    
    Images require signed URLs with expiration for security.
    Images auto-cleanup after 24 hours via background cleaner task.
    
    Security Flow:
    1. Check file exists (cleaner may have deleted it) → 404 if not found
    2. Verify signed URL expiration → 403 if expired
    3. Verify signature → 403 if invalid
    4. Serve file if all checks pass
    
    Coordination with Temp Image Cleaner:
    - Cleaner deletes files older than 24h based on file mtime
    - Signed URLs expire after 24h from generation time
    - Both use same 24-hour window for consistency
    - If cleaner deleted file → 404 (file not found)
    - If URL expired but file exists → 403 (URL expired)
    """
    # Parse filename and signature from path
    # Path format: filename.png?sig=...&exp=...
    if '?' in filepath:
        filename = filepath.split('?')[0]
    else:
        filename = filepath
    
    # Security: Validate filename to prevent directory traversal
    if '..' in filename or '/' in filename or '\\' in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    temp_path = Path("temp_images") / filename
    
    # Step 1: Check if file exists (cleaner may have deleted it)
    # This check happens FIRST to distinguish between "file deleted" (404) and "URL expired" (403)
    if not temp_path.exists():
        # File doesn't exist - could be deleted by cleaner or never existed
        # Check if this is a signed URL to provide better error message
        if sig and exp:
            # Signed URL but file doesn't exist - likely deleted by cleaner
            logger.debug(f"Temp image file not found (may have been cleaned): {filename}")
        raise HTTPException(status_code=404, detail="Image not found or expired")
    
    # Step 2: Verify signed URL if signature provided (new format)
    if sig and exp:
        # Verify signature and expiration
        if not verify_signed_url(filename, sig, exp):
            logger.warning(f"Invalid or expired signed URL for temp image: {filename}")
            raise HTTPException(status_code=403, detail="Invalid or expired image URL")
    else:
        # Legacy support: Check if file exists and is not too old (max 24 hours)
        # This allows existing URLs to work temporarily
        # Uses same logic as temp_image_cleaner (24 hour max age)
        import aiofiles.os
        try:
            stat_result = await aiofiles.os.stat(temp_path)
            file_age = time.time() - stat_result.st_mtime
            if file_age > 86400:  # 24 hours (matches cleanup threshold)
                logger.warning(f"Legacy temp image URL expired: {filename} (age: {file_age/3600:.1f}h)")
                raise HTTPException(status_code=403, detail="Image URL expired")
        except Exception as e:
            logger.error(f"Failed to check file age: {e}")
            raise HTTPException(status_code=404, detail="Image not found")
    
    return FileResponse(
        path=str(temp_path),
        media_type="image/png",
        headers={
            'Cache-Control': 'public, max-age=86400',
            'X-Content-Type-Options': 'nosniff'
        }
        )

