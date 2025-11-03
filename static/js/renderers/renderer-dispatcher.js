/**
 * Renderer Dispatcher for MindGraph
 * 
 * This module provides the main rendering dispatcher function.
 * Supports both dynamic loading (preferred) and static fallback.
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
    
    // Use dynamic loading if available (PREFERRED)
    if (USE_DYNAMIC_LOADING && window.dynamicRendererLoader) {
        try {
            await window.dynamicRendererLoader.renderGraph(type, spec, integratedTheme, dimensions);
            return;
        } catch (error) {
            logger.warn('RendererDispatcher', 'Dynamic rendering failed, falling back to static', error);
            // Fall through to static rendering below
        }
    }
    
    // Fallback: Static rendering (existing switch statement)
    // NOTE: This will only work if renderers were manually loaded
    logger.warn('RendererDispatcher', 'Using static renderer fallback (not recommended)');
    
    switch (type) {
        case 'double_bubble_map':
            if (typeof renderDoubleBubbleMap === 'function') {
                renderDoubleBubbleMap(spec, integratedTheme, dimensions);
            } else {
                logger.error('RendererDispatcher', 'renderDoubleBubbleMap function not found');
                showRendererError('double_bubble_map');
            }
            break;
        case 'bubble_map':
            if (typeof renderBubbleMap === 'function') {
                renderBubbleMap(spec, integratedTheme, dimensions);
            } else {
                logger.error('RendererDispatcher', 'renderBubbleMap function not found');
                showRendererError('bubble_map');
            }
            break;
        case 'circle_map':
            if (typeof renderCircleMap === 'function') {
                renderCircleMap(spec, integratedTheme, dimensions);
            } else {
                logger.error('RendererDispatcher', 'renderCircleMap function not found');
                showRendererError('circle_map');
            }
            break;
        case 'tree_map':
                    // Processing tree_map case
            if (window.TreeRenderer) {
                // window.TreeRenderer.renderTreeMap available
            }
            
            // CRITICAL FIX: Check all possible locations for the function
            let treeMapRenderer = null;
            if (typeof renderTreeMap === 'function') {
                treeMapRenderer = renderTreeMap;
                // Using global renderTreeMap
            } else if (typeof window.renderTreeMap === 'function') {
                treeMapRenderer = window.renderTreeMap;
                // Using window.renderTreeMap
            } else if (window.TreeRenderer && typeof window.TreeRenderer.renderTreeMap === 'function') {
                treeMapRenderer = window.TreeRenderer.renderTreeMap;
                // Using window.TreeRenderer.renderTreeMap
            }
            
            if (treeMapRenderer) {
                // Calling tree map renderer
                treeMapRenderer(spec, integratedTheme, dimensions);
            } else {
                logger.error('RendererDispatcher', 'renderTreeMap function not found');
                showRendererError('tree_map');
            }
            break;
        case 'concept_map':
            // Check all possible locations for the function
            let conceptMapRenderer = null;
            if (typeof renderConceptMap === 'function') {
                conceptMapRenderer = renderConceptMap;
            } else if (window.ConceptMapRenderer && typeof window.ConceptMapRenderer.renderConceptMap === 'function') {
                conceptMapRenderer = window.ConceptMapRenderer.renderConceptMap;
            }
            
            if (conceptMapRenderer) {
                // Calling concept map renderer
                try {
                    conceptMapRenderer(spec, integratedTheme, dimensions);
                } catch (error) {
                    logger.error('RendererDispatcher', 'Error rendering concept map', error);
                    showRendererError('concept_map', error.message);
                }
            } else {
                logger.error('RendererDispatcher', 'renderConceptMap function not found');
                showRendererError('concept_map');
            }
            break;
        case 'mindmap':
        case 'mind_map':
            if (typeof renderMindMap === 'function') {
                renderMindMap(spec, integratedTheme, dimensions);
            } else {
                logger.error('RendererDispatcher', 'renderMindMap function not found');
                showRendererError('mind_map');
            }
            break;
        case 'flowchart':
            if (typeof renderFlowchart === 'function') {
                renderFlowchart(spec, integratedTheme, dimensions);
            } else {
                logger.error('RendererDispatcher', 'renderFlowchart function not found');
                showRendererError('flowchart');
            }
            break;

        case 'bridge_map':
            logger.debug('RendererDispatcher', 'Rendering bridge map', {
                analogiesCount: spec?.analogies?.length || 0
            });
            
            if (typeof renderBridgeMap === 'function') {
                renderBridgeMap(spec, integratedTheme, dimensions, 'd3-container');
            } else {
                logger.error('RendererDispatcher', 'renderBridgeMap function not found');
                showRendererError('bridge_map');
            }
            break;
        case 'brace_map':
                    // Processing brace_map case
            
            // CRITICAL FIX: Check all possible locations for the function
            let braceMapRenderer = null;
            if (typeof renderBraceMap === 'function') {
                braceMapRenderer = renderBraceMap;
                // Using global renderBraceMap
            } else if (window.BraceRenderer && typeof window.BraceRenderer.renderBraceMap === 'function') {
                braceMapRenderer = window.BraceRenderer.renderBraceMap;
                // Using window.BraceRenderer.renderBraceMap
            }
            
            if (braceMapRenderer) {
                // Calling brace map renderer
                try {
                    braceMapRenderer(spec, integratedTheme, dimensions);
                } catch (error) {
                    logger.error('RendererDispatcher', 'Error rendering brace map', error);
                    showRendererError('brace_map', error.message);
                }
            } else {
                logger.error('RendererDispatcher', 'renderBraceMap function not found');
                showRendererError('brace_map');
            }
            break;
        case 'flow_map':
            if (typeof renderFlowMap === 'function') {
                renderFlowMap(spec, integratedTheme, dimensions);
            } else {
                logger.error('RendererDispatcher', 'renderFlowMap function not found');
                showRendererError('flow_map');
            }
            break;
        case 'multi_flow_map':
            if (typeof renderMultiFlowMap === 'function') {
                renderMultiFlowMap(spec, integratedTheme, dimensions);
            } else {
                logger.error('RendererDispatcher', 'renderMultiFlowMap function not found');
                showRendererError('multi_flow_map');
            }
            break;
        
        // Thinking Tools (all use mind map rendering structure)
        case 'factor_analysis':
            if (typeof renderFactorAnalysis === 'function') {
                renderFactorAnalysis(spec, integratedTheme, dimensions);
            } else {
                logger.error('RendererDispatcher', 'renderFactorAnalysis function not found');
                showRendererError('factor_analysis');
            }
            break;
        case 'three_position_analysis':
            if (typeof renderThreePositionAnalysis === 'function') {
                renderThreePositionAnalysis(spec, integratedTheme, dimensions);
            } else {
                logger.error('RendererDispatcher', 'renderThreePositionAnalysis function not found');
                showRendererError('three_position_analysis');
            }
            break;
        case 'perspective_analysis':
            if (typeof renderPerspectiveAnalysis === 'function') {
                renderPerspectiveAnalysis(spec, integratedTheme, dimensions);
            } else {
                logger.error('RendererDispatcher', 'renderPerspectiveAnalysis function not found');
                showRendererError('perspective_analysis');
            }
            break;
        case 'goal_analysis':
            if (typeof renderGoalAnalysis === 'function') {
                renderGoalAnalysis(spec, integratedTheme, dimensions);
            } else {
                logger.error('RendererDispatcher', 'renderGoalAnalysis function not found');
                showRendererError('goal_analysis');
            }
            break;
        case 'possibility_analysis':
            if (typeof renderPossibilityAnalysis === 'function') {
                renderPossibilityAnalysis(spec, integratedTheme, dimensions);
            } else {
                logger.error('RendererDispatcher', 'renderPossibilityAnalysis function not found');
                showRendererError('possibility_analysis');
            }
            break;
        case 'result_analysis':
            if (typeof renderResultAnalysis === 'function') {
                renderResultAnalysis(spec, integratedTheme, dimensions);
            } else {
                logger.error('RendererDispatcher', 'renderResultAnalysis function not found');
                showRendererError('result_analysis');
            }
            break;
        case 'five_w_one_h':
            if (typeof renderFiveWOneH === 'function') {
                renderFiveWOneH(spec, integratedTheme, dimensions);
            } else {
                logger.error('RendererDispatcher', 'renderFiveWOneH function not found');
                showRendererError('five_w_one_h');
            }
            break;
        case 'whwm_analysis':
            if (typeof renderWHWMAnalysis === 'function') {
                renderWHWMAnalysis(spec, integratedTheme, dimensions);
            } else {
                logger.error('RendererDispatcher', 'renderWHWMAnalysis function not found');
                showRendererError('whwm_analysis');
            }
            break;
        case 'four_quadrant':
            if (typeof renderFourQuadrant === 'function') {
                renderFourQuadrant(spec, integratedTheme, dimensions);
            } else {
                logger.error('RendererDispatcher', 'renderFourQuadrant function not found');
                showRendererError('four_quadrant');
            }
            break;
        
        default:
            logger.error('RendererDispatcher', `Unknown graph type: ${type}`);
            showRendererError('unknown', `Unknown graph type '${type}'`);
    }
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
