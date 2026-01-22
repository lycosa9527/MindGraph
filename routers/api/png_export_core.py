"""
PNG Export Core Module
======================

Core functionality for PNG export that embeds JS and fonts directly.
This module contains the low-level export logic separated from the API endpoints.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from pathlib import Path
from typing import Dict, Any, Optional
import asyncio
import base64
import json
import logging
import re

from config.settings import Config
from services.infrastructure.utils.browser import BrowserContextManager

logger = logging.getLogger(__name__)


def get_font_base64(font_filename: str) -> str:
    """Convert font file to base64 for embedding in HTML."""
    try:
        font_path = Path(__file__).parent.parent.parent / 'static' / 'fonts' / font_filename
        if font_path.exists():
            with open(font_path, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')
        else:
            logger.debug("[ExportPNG] Font file not found: %s", font_path)
            return ""
    except Exception as e:
        logger.warning("[ExportPNG] Failed to load font %s: %s", font_filename, e)
        return ""


async def export_png_core(
    diagram_data: Dict[str, Any],
    diagram_type: str,
    width: int = 1200,
    height: int = 800,
    scale: int = 2,
    _x_language: Optional[str] = None,
    _base_url: Optional[str] = None
) -> bytes:
    """
    Core PNG export function that embeds JS and fonts directly (like old working version).

    This function avoids Depends() issues by being a pure async function.
    Returns raw PNG bytes.
    """
    config_instance = Config()

    logger.debug(
        "[ExportPNG] Starting PNG export: diagram_type=%s, width=%s, height=%s, scale=%s",
        diagram_type, width, height, scale
    )
    if isinstance(diagram_data, dict):
        logger.debug("[ExportPNG] Diagram data keys: %s", list(diagram_data.keys()))
        if 'topic' in diagram_data:
            logger.debug("[ExportPNG] Topic: %s", diagram_data['topic'])

    # Normalize data format for renderers (transform LLM output format to renderer expected format)
    if isinstance(diagram_data, dict):
        if diagram_type == 'double_bubble_map':
            # Transform left_topic/right_topic to left/right (renderer expects left/right)
            if 'left_topic' in diagram_data and 'left' not in diagram_data:
                diagram_data['left'] = diagram_data.pop('left_topic')
            if 'right_topic' in diagram_data and 'right' not in diagram_data:
                diagram_data['right'] = diagram_data.pop('right_topic')
            logger.debug(
                "[ExportPNG] Normalized double_bubble_map: left=%s, right=%s",
                diagram_data.get('left'), diagram_data.get('right')
            )

        elif diagram_type == 'circle_map':
            # Transform contexts (plural) to context (singular) - renderer expects spec.context
            if 'contexts' in diagram_data and 'context' not in diagram_data:
                diagram_data['context'] = diagram_data.pop('contexts')
            logger.debug(
                "[ExportPNG] Normalized circle_map: context count=%s",
                len(diagram_data.get('context', []))
            )

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
                logger.debug(
                    "[ExportPNG] Normalized tree_map: children count=%s",
                    len(diagram_data.get('children', []))
                )

        elif diagram_type == 'brace_map':
            # Transform topic to whole (renderer expects 'whole' field)
            if 'topic' in diagram_data and 'whole' not in diagram_data:
                diagram_data['whole'] = diagram_data.pop('topic')
                logger.debug("[ExportPNG] Normalized brace_map: topic -> whole = '%s'", diagram_data['whole'])

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
                logger.debug(
                    "[ExportPNG] Normalized brace_map: parts count=%s",
                    len(diagram_data.get('parts', []))
                )

    try:
        # Load JS files from disk for embedding (like old version)
        logger.debug("[ExportPNG] Loading JavaScript files for embedding")

        # Read local D3.js content for embedding in PNG generation (like old version)
        d3_js_path = Path(__file__).parent.parent.parent / 'static' / 'js' / 'd3.min.js'
        try:
            with open(d3_js_path, 'r', encoding='utf-8') as f:
                d3_js_content = f.read()
            logger.debug("[ExportPNG] D3.js loaded (%s bytes)", len(d3_js_content))
            d3_script_tag = f'<script>{d3_js_content}</script>'
        except Exception as e:
            logger.error("[ExportPNG] Failed to load D3.js: %s", e)
            raise RuntimeError(f"Local D3.js library not available at {d3_js_path}") from e

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
            base_path = Path(__file__).parent.parent.parent / 'static' / 'js' / 'renderers'
            js_files_to_embed['renderer'] = base_path / renderer_filename
            js_files_to_embed['shared_utilities'] = base_path / 'shared-utilities.js'

        embedded_js_content = {}
        for key, path in js_files_to_embed.items():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if key == 'dynamic_loader':
                        # Patch dynamic-renderer-loader.js to prevent HTTP loading when files are embedded
                        # AND fix loadRenderer() to validate cached renderer objects

                        # Patch the loadScript method to check if script is already in DOM before making HTTP request
                        # This prevents failures when scripts are embedded directly in HTML
                        # Find the loadScript method and wrap it

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
                    if (cached && cached.renderer && typeof cached.renderer === 'object' &&
                        Object.keys(cached.renderer).length > 0) {
                        const keys = Object.keys(cached.renderer).join(', ');
                        console.log('[ExportPNG] Skipping HTTP load for ' + src +
                            ' (renderer object already cached: ' + keys + ')');
                        resolve();
                        return;
                    }
                    // If cache has flag but no renderer object, clear it and load via HTTP
                    console.log('[ExportPNG] Cache has flag but no renderer object for ' +
                        moduleName + ', loading via HTTP');
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
                            logger.debug("[ExportPNG] Successfully patched loadScript method")

                        # CRITICAL: Patch loadRenderer() to validate cached renderer objects
                        # The cache might have {renderer: true} from old code, which is not a renderer object
                        # Find and replace the cache check: "if (cached.renderer) { return cached.renderer; }"
                        cache_check_pattern = r'if \(cached\.renderer\) \{\s+return cached\.renderer;\s+\}'
                        if re.search(cache_check_pattern, content):
                            patched_cache_check = (
                                r'''if (cached.renderer && typeof cached.renderer === 'object' '''
                                r'''&& Object.keys(cached.renderer).length > 0) {
                console.log('[ExportPNG] Using cached renderer object]: ', '''
                                r'''Object.keys(cached.renderer));
                return cached.renderer;
            }
            // If cached.renderer is just a flag (true) or empty object, '''
                                r'''clear it and load properly
            if (cached.renderer === true || (cached.renderer && '''
                                r'''typeof cached.renderer === 'object' && '''
                                r'''Object.keys(cached.renderer).length === 0)) {
                console.warn('[ExportPNG] Cache has invalid renderer entry for ' + '''
                                r'''config.module + ' (flag or empty), clearing cache');
                this.cache.delete(config.module);
            }'''
                            )
                            content = re.sub(cache_check_pattern, patched_cache_check, content)
                            logger.debug("[ExportPNG] Successfully patched loadRenderer cache validation")
                        else:
                            logger.warning("[ExportPNG] Could not find loadScript method to patch - using fallback")
                            # Fallback: patch the specific loadScript calls in loadRenderer
                            # Try multiple variations of the string
                            replacements = [
                                ("const sharedPromise = this.loadScript('/static/js/renderers/shared-utilities.js')",
                                 """const sharedPromise = (() => {
                                    if (this.cache && this.cache.has('shared-utilities')) {
                                        console.log('[ExportPNG] Skipping HTTP load for '''
                                        r'''shared-utilities.js (already in cache)');
                                        return Promise.resolve();
                                    }
                                    return this.loadScript('/static/js/renderers/shared-utilities.js');
                                })()"""),
                                ("const sharedPromise = this.loadScript(\"/static/js/renderers/shared-utilities.js\")",
                                 """const sharedPromise = (() => {
                                    if (this.cache && this.cache.has('shared-utilities')) {
                                        console.log('[ExportPNG] Skipping HTTP load for '''
                                        r'''shared-utilities.js (already in cache)');
                                        return Promise.resolve();
                                    }
                                    return this.loadScript("/static/js/renderers/shared-utilities.js");
                                })()""")
                            ]

                            for old_str, new_str in replacements:
                                if old_str in content:
                                    content = content.replace(old_str, new_str)
                                    logger.debug("[ExportPNG] Patched shared-utilities loadScript call")
                                    break
                            else:
                                # Try matching with the .then() call included
                                old_with_then = (
                                    "const sharedPromise = this.loadScript("
                                    "'/static/js/renderers/shared-utilities.js')\n"
                                    "                .then(() => {"
                                )
                                if old_with_then in content:
                                    # Replace the entire block including .then()
                                    new_with_then = (
                                        """const sharedPromise = (() => {
                                    if (this.cache && this.cache.has('shared-utilities')) {
                                        console.log('[ExportPNG] Skipping HTTP load for '''
                                        r'''shared-utilities.js (already in cache)');
                                        return Promise.resolve().then(() => {
                                            this.cache.set('shared-utilities', { renderer: true });
                                        });
                                    }
                                    return this.loadScript('/static/js/renderers/shared-utilities.js').then(() => {"""
                                    )
                                    content = content.replace(old_with_then, new_with_then)
                                    logger.debug("[ExportPNG] Patched shared-utilities loadScript call (with .then())")
                                else:
                                    logger.warning(
                                        "[ExportPNG] Could not find shared-utilities "
                                        "loadScript call to patch"
                                    )
                    embedded_js_content[key] = content
                logger.debug("[ExportPNG] JS file '%s' loaded (%s bytes)", key, len(content))
            except Exception as e:
                logger.error("[ExportPNG] Failed to load JS file '%s': %s", key, e)
                raise RuntimeError(f"Required JavaScript file '{key}' not available at {path}") from e

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
        renderer_info_map.get(diagram_type, {})

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
        base_static_path = Path(__file__).parent.parent.parent / 'static' / 'js' / 'renderers'
        renderer_dispatcher_path = base_static_path / 'renderer-dispatcher.js'
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
                logger.debug("[ExportPNG] Loaded renderer-dispatcher.js (%s bytes)", len(renderer_dispatcher_js))
            except Exception as e:
                logger.error("[ExportPNG] Failed to load renderer-dispatcher.js: %s", e)
                raise RuntimeError(
                    f"Required JavaScript file 'renderer-dispatcher.js' "
                    f"not available at {renderer_dispatcher_path}"
                ) from e

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
        dimensions = config_instance.get_d3_dimensions()

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
        elif (diagram_type in ('multi_flow_map', 'flow_map', 'tree_map', 'concept_map') and
              isinstance(diagram_data, dict)):
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
                logger.warning("[ExportPNG] Failed to apply recommended dimensions: %s", e)

        # Build font-face declarations only for fonts that exist
        font_faces = []
        font_files = [
            ("inter-400.ttf", 400),
            ("inter-600.ttf", 600),
            ("inter-700.ttf", 700),
        ]

        for font_file, weight in font_files:
            font_base64 = get_font_base64(font_file)
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
                    if (!rendererObj || typeof rendererObj !== 'object' ||
                        Object.keys(rendererObj).length === 0) {{
                        const availableRenderers = Object.keys(window)
                            .filter(k => k.includes('Renderer'));
                        throw new Error('Renderer ' + rendererInfo.renderer +
                            ' not found or empty. Available: ' +
                            availableRenderers.join(', '));
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
                    const watermarkConfig = {json.dumps(config_instance.get_watermark_config(), ensure_ascii=False)};
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
                            renderPromise = renderGraph(
                                window.graph_type, window.spec,
                                backendTheme, window.dimensions
                            );
                        }} catch (e) {{
                            console.error('[ExportPNG] Error calling renderGraph:', e);
                            throw new Error('renderGraph call failed: ' + e.message);
                        }}
                    }} else if (typeof window.dynamicRendererLoader !== 'undefined' &&
                               typeof window.dynamicRendererLoader.renderGraph === 'function') {{
                        // Fallback to dynamicRendererLoader.renderGraph
                        console.log('[ExportPNG] Using dynamicRendererLoader.renderGraph');
                        try {{
                            renderPromise = window.dynamicRendererLoader.renderGraph(
                                window.graph_type, window.spec,
                                backendTheme, window.dimensions
                            );
                        }} catch (e) {{
                            console.error('[ExportPNG] Error calling dynamicRendererLoader.renderGraph:', e);
                            const cacheKeys = Array.from(
                                window.dynamicRendererLoader.cache.keys()
                            );
                            console.error('[ExportPNG] Cache state:', cacheKeys);
                            const cached = window.dynamicRendererLoader.cache.get(
                                rendererInfo.module
                            );
                            const cachedKeys = cached ?
                                Object.keys(cached.renderer || {{}}) : 'null';
                            console.error('[ExportPNG] Cached renderer:', cachedKeys);
                            throw new Error('dynamicRendererLoader.renderGraph call failed: ' +
                                e.message);
                        }}
                    }} else {{
                        const availableInfo = {{
                            renderGraph: typeof renderGraph,
                            dynamicRendererLoader: typeof window.dynamicRendererLoader,
                            dynamicRendererLoaderRenderGraph:
                                typeof window.dynamicRendererLoader?.renderGraph,
                            cacheKeys: Array.from(
                                window.dynamicRendererLoader?.cache?.keys() || []
                            )
                        }};
                        console.error('[ExportPNG] Available functions:', availableInfo);
                        const errorMsg = 'Neither renderGraph nor ' +
                            'dynamicRendererLoader.renderGraph is available. ' +
                            JSON.stringify(availableInfo);
                        throw new Error(errorMsg);
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

        logger.debug("[ExportPNG] HTML content length: %s characters", len(html))

        # Create browser context (like old version)
        logger.debug("[ExportPNG] Creating browser context")
        async with BrowserContextManager() as context:
            page = await context.new_page()

            # Set up route handler to serve renderer files from disk
            # This allows dynamic-renderer-loader.js to load renderer modules via HTTP
            async def handle_route(route):
                url = route.request.url
                logger.debug("[ExportPNG] Route intercepted: %s", url)

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
                                logger.debug("[ExportPNG] Served renderer file via route: %s", filename)
                                return
                            except Exception as e:
                                logger.error("[ExportPNG] Failed to read renderer file %s: %s",
                                           filename, e)
                        else:
                            logger.warning(
                                "[ExportPNG] Renderer file not found: %s (requested: %s)",
                                renderer_path, url
                            )

                # Let other requests pass through (for D3.js if loaded via URL)
                await route.continue_()

            # Set up route interception BEFORE loading content
            await page.route('**/*', handle_route)

            # Set timeout and log HTML size and structure (like old version)
            html_size = len(html)
            timeout_ms = 60000  # 60 seconds for all content
            logger.debug("[ExportPNG] HTML content size: %s characters", html_size)

            # Set up comprehensive console and error logging BEFORE loading content (like old version)
            console_messages = []
            page_errors = []

            def log_console_message(msg):
                message = f"{msg.type}: {msg.text}"
                console_messages.append(message)
                logger.debug("BROWSER CONSOLE: %s", message)

            def log_page_error(err):
                error_str = str(err)
                page_errors.append(error_str)
                logger.error("BROWSER ERROR: %s", error_str)

            page.on("console", log_console_message)
            page.on("pageerror", log_page_error)
            page.on("requestfailed", lambda request: logger.error(
                "RESOURCE FAILED: %s - %s", request.url, request.failure
            ))
            page.on("response", lambda response: logger.debug(
                "RESOURCE LOADED: %s - %s", response.url, response.status
            ) if response.status >= 400 else None)

            # Set timeout (like old version)
            page.set_default_timeout(60000)
            page.set_default_navigation_timeout(60000)

            # Try to load the content with more detailed error handling (like old version)
            try:
                await page.set_content(html, timeout=timeout_ms)
                logger.debug("[ExportPNG] HTML content loaded successfully")
            except Exception as e:
                logger.error("[ExportPNG] Failed to set HTML content: %s", e)
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
                logger.error("[ExportPNG] Rendering error in browser: %s", rendering_error)
                # Log console messages for debugging
                if console_messages:
                    console_count = len(console_messages)
                    logger.error("[ExportPNG] Browser console messages: %s", console_count)
                    for i, msg in enumerate(console_messages[-20:]):
                        logger.error("[ExportPNG] Console %s: %s", i+1, msg)
                if page_errors:
                    errors_count = len(page_errors)
                    logger.error("[ExportPNG] Browser errors: %s", errors_count)
                    for i, error in enumerate(page_errors):
                        logger.error("[ExportPNG] Browser Error %s: %s", i+1, error)
                raise RuntimeError(f"Browser rendering failed: {rendering_error}")

            # Wait for SVG element to appear
            logger.debug("[ExportPNG] Waiting for SVG element")
            try:
                await page.wait_for_selector('svg', timeout=5000)
                logger.debug("[ExportPNG] SVG element found")
            except Exception as e:
                logger.error("[ExportPNG] Timeout waiting for SVG element: %s", e)
                # Log console messages and errors for debugging
                if console_messages:
                    console_count = len(console_messages)
                    logger.error("[ExportPNG] Browser console messages: %s", console_count)
                    for i, msg in enumerate(console_messages[-20:]):
                        logger.error("[ExportPNG] Console %s: %s", i+1, msg)
                if page_errors:
                    errors_count = len(page_errors)
                    logger.error("[ExportPNG] Browser errors: %s", errors_count)
                    for i, error in enumerate(page_errors):
                        logger.error("[ExportPNG] Browser Error %s: %s", i+1, error)
                raise ValueError("SVG element not found. The graph could not be rendered.") from e

            # Log console messages and errors (like old version)
            if console_messages:
                logger.debug("[ExportPNG] Browser console messages: %s", len(console_messages))
                for i, msg in enumerate(console_messages[-10:]):
                    logger.debug("[ExportPNG] Console %s: %s", i+1, msg)
            if page_errors:
                errors_count = len(page_errors)
                logger.error("[ExportPNG] Browser errors: %s", errors_count)
                for i, error in enumerate(page_errors):
                    logger.error("[ExportPNG] Browser Error %s: %s", i+1, error)

            # Wait for SVG element to be created with timeout (like old version)
            try:
                element = await page.wait_for_selector("svg", timeout=10000)
                logger.debug("[ExportPNG] SVG element found successfully")
            except Exception as e:
                logger.error("[ExportPNG] Timeout waiting for SVG element: %s", e)
                element = await page.query_selector("svg")  # Try one more time

            # Check if SVG exists and has content (like old version)
            if element is None:
                logger.error("[ExportPNG] SVG element not found in rendered page")
                raise ValueError("SVG element not found. The graph could not be rendered.")

            # Check SVG dimensions (like old version)
            svg_width = await element.get_attribute('width')
            svg_height = await element.get_attribute('height')
            logger.debug("[ExportPNG] SVG dimensions: width=%s, height=%s", svg_width, svg_height)

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
                logger.warning("[ExportPNG] Element not ready for screenshot within 2s timeout: %s", e)
                await page.wait_for_timeout(200)  # Fallback wait

            # Take screenshot using SVG element directly (like old version)
            logger.debug("[ExportPNG] Taking screenshot")
            screenshot_bytes = await element.screenshot(omit_background=False, timeout=60000)
            logger.debug("[ExportPNG] Screenshot taken: %s bytes", len(screenshot_bytes))

        logger.info("[ExportPNG] PNG generated successfully: %s bytes", len(screenshot_bytes))
        return screenshot_bytes

    except Exception as e:
        logger.error("[ExportPNG] Error during PNG export: %s", e, exc_info=True)
        raise
