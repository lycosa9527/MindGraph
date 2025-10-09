/**
 * Dynamic Renderer Loader for MindGraph
 * 
 * Simple, efficient loading of renderer modules based on graph type.
 * Only loads the specific renderer needed, reducing bundle size by 70-80%.
 */

class DynamicRendererLoader {
    constructor() {
        this.cache = new Map(); // moduleName -> { renderer, promise }
        
        // Single configuration object for all renderers
        this.config = {
            'mindmap': {
                module: 'mind-map-renderer',
                renderer: 'MindMapRenderer',
                function: 'renderMindMap'
            },
            'mind_map': {
                module: 'mind-map-renderer',
                renderer: 'MindMapRenderer',
                function: 'renderMindMap'
            },
            'concept_map': {
                module: 'concept-map-renderer',
                renderer: 'ConceptMapRenderer', 
                function: 'renderConceptMap'
            },
            'bubble_map': {
                module: 'bubble-map-renderer',
                renderer: 'BubbleMapRenderer',
                function: 'renderBubbleMap'
            },
            'double_bubble_map': {
                module: 'bubble-map-renderer',
                renderer: 'BubbleMapRenderer',
                function: 'renderDoubleBubbleMap'
            },
            'circle_map': {
                module: 'bubble-map-renderer',
                renderer: 'BubbleMapRenderer',
                function: 'renderCircleMap'
            },
            'tree_map': {
                module: 'tree-renderer',
                renderer: 'TreeRenderer',
                function: 'renderTreeMap'
            },
            'flow_map': {
                module: 'flow-renderer',
                renderer: 'FlowRenderer',
                function: 'renderFlowMap'
            },
            'multi_flow_map': {
                module: 'flow-renderer',
                renderer: 'FlowRenderer',
                function: 'renderMultiFlowMap'
            },
            'bridge_map': {
                module: 'flow-renderer',
                renderer: 'FlowRenderer',
                function: 'renderBridgeMap'
            },
            'brace_map': {
                module: 'brace-renderer',
                renderer: 'BraceRenderer',
                function: 'renderBraceMap'
            }
        };
    }
    
    /**
     * Load a JavaScript file dynamically
     */
    loadScript(src) {
        return new Promise((resolve, reject) => {
            // Check if script is already loaded
            const existingScript = document.querySelector(`script[src="${src}"]`);
            if (existingScript) {
                resolve();
                return;
            }
            
            const script = document.createElement('script');
            script.src = src;
            script.type = 'text/javascript';
            script.async = true;
            
            script.onload = () => resolve();
            script.onerror = () => reject(new Error(`Failed to load script: ${src}`));
            
            document.head.appendChild(script);
        });
    }
    
    /**
     * Load a renderer module
     */
    async loadRenderer(graphType) {
        const normalizedType = graphType.toLowerCase().replace(/[-_\s]/g, '_');
        const config = this.config[normalizedType];
        
        if (!config) {
            throw new Error(`Unknown graph type: ${graphType}. Supported types: ${Object.keys(this.config).join(', ')}`);
        }
        
        // Check cache first
        if (this.cache.has(config.module)) {
            const cached = this.cache.get(config.module);
            if (cached.renderer) {
                return cached.renderer;
            }
            if (cached.promise) {
                return cached.promise;
            }
        }
        
        // Load shared utilities first if not loaded
        if (!this.cache.has('shared-utilities')) {
            const sharedPromise = this.loadScript('/static/js/renderers/shared-utilities.js')
                .then(() => {
                    this.cache.set('shared-utilities', { renderer: true });
                })
                .catch(error => {
                    logger.error('DynamicRendererLoader', 'Failed to load shared utilities:', error);
                    throw error;
                });
            this.cache.set('shared-utilities', { promise: sharedPromise });
            await sharedPromise;
        }
        
        // Load the renderer module
        const loadPromise = this.loadScript(`/static/js/renderers/${config.module}.js`)
            .then(() => {
                const renderer = window[config.renderer];
                if (!renderer) {
                    throw new Error(`Renderer ${config.renderer} not found after loading ${config.module}`);
                }
                this.cache.set(config.module, { renderer });
                return renderer;
            })
            .catch(error => {
                logger.error('DynamicRendererLoader', `Failed to load renderer module ${config.module}:`, error);
                throw error;
            });
        
        this.cache.set(config.module, { promise: loadPromise });
        return loadPromise;
    }
    
    /**
     * Render a graph using the appropriate renderer
     */
    async renderGraph(graphType, spec, theme = null, dimensions = null) {
        try {
            const renderer = await this.loadRenderer(graphType);
            const normalizedType = graphType.toLowerCase().replace(/[-_\s]/g, '_');
            const config = this.config[normalizedType];
            
            const renderFunction = renderer[config.function];
            if (!renderFunction) {
                throw new Error(`Render function ${config.function} not found in ${config.renderer}`);
            }
            
            return renderFunction(spec, theme, dimensions);
        } catch (error) {
            logger.error('DynamicRendererLoader', `Dynamic rendering failed for ${graphType}:`, error);
            
            // Error logged to console only
            
            throw error;
        }
    }
}

// Create global instance
const dynamicRendererLoader = new DynamicRendererLoader();

// Export for module system
if (typeof window !== 'undefined') {
    window.DynamicRendererLoader = DynamicRendererLoader;
    window.dynamicRendererLoader = dynamicRendererLoader;
} else if (typeof module !== 'undefined' && module.exports) {
    module.exports = { DynamicRendererLoader, dynamicRendererLoader };
}
