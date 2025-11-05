/**
 * Renderer Dispatcher for MindGraph
 * 
 * This module provides the main rendering dispatcher function.
 * Uses dynamic loading exclusively - no static fallback.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

// Enable dynamic loading for better performance
const USE_DYNAMIC_LOADING = true;

// Main rendering dispatcher function
async function renderGraph(type, spec, theme = null, dimensions = null) {
    logger.debug('RendererDispatcher', 'Rendering graph', { type });
    
    // Clear the container first
    d3.select('#d3-container').html('');
    
    // Prepare integrated theme
    let integratedTheme = theme;
    if (spec && spec._style) {
        integratedTheme = {
            ...spec._style,
            background: theme?.background
        };
    }
    
    // Use dynamic loading (REQUIRED - no fallback)
    if (USE_DYNAMIC_LOADING && window.dynamicRendererLoader) {
        await window.dynamicRendererLoader.renderGraph(type, spec, integratedTheme, dimensions);
        return;
    }
    
    // If dynamic loading is disabled or unavailable, throw error
    throw new Error(`Dynamic renderer loader is required but ${USE_DYNAMIC_LOADING ? 'not available' : 'disabled'}. Cannot render ${type}.`);
}

// Helper function to show renderer errors
function showRendererError(type, message = null) {
    const errorMsg = message || `Renderer for '${type}' not loaded or not available`;
    logger.error('RendererDispatcher', errorMsg);
}

// Export functions for module system
if (typeof window !== 'undefined') {
    // Browser environment - attach to window
    window.renderGraph = renderGraph;
    window.showRendererError = showRendererError;
} else if (typeof module !== 'undefined' && module.exports) {
    // Node.js environment
    module.exports = {
        renderGraph,
        showRendererError
    };
}
