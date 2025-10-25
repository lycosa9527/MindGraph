/**
 * Three-Position Analysis Renderer
 * Uses mind map rendering structure
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 */

// Reuse mind map renderer since the structure is identical
function renderThreePositionAnalysis(spec, theme = null, dimensions = null) {
    if (typeof renderMindMap === 'function') {
        return renderMindMap(spec, theme, dimensions);
    } else {
        logger.error('ThreePositionAnalysisRenderer', 'renderMindMap function not found. Please load mind-map-renderer.js first.');
    }
}

// Export for module system
if (typeof window !== 'undefined') {
    window.ThreePositionAnalysisRenderer = {
        renderThreePositionAnalysis
    };
}

