/**
 * Renderer Dispatcher for MindGraph
 * 
 * This module provides the main rendering dispatcher function.
 * It must be loaded AFTER all individual renderer modules.
 * 
 * Performance Impact: Minimal - just function routing
 */

// Main rendering dispatcher function
function renderGraph(type, spec, theme = null, dimensions = null) {
    console.log('=== RENDERER DISPATCHER: MAIN FUNCTION START ===');
    console.log(`Graph type: ${type}`);
    console.log('Spec:', spec);
    console.log('Spec type:', typeof spec);
    console.log('Spec keys:', Object.keys(spec || {}));
    console.log('Theme:', theme);
    console.log('Dimensions:', dimensions);
    
    // Special debug for bridge maps
    if (type === 'bridge_map') {
        console.log('=== BRIDGE MAP SPECIAL DEBUG ===');
        console.log('Analogies array:', spec?.analogies);
        console.log('Analogies count:', spec?.analogies?.length || 0);
        
        if (spec?.analogies && Array.isArray(spec.analogies)) {
            spec.analogies.forEach((analogy, index) => {
                console.log(`Main function analogy ${index}:`, analogy);
                console.log(`  Left: "${analogy.left}"`);
                console.log(`  Right: "${analogy.right}"`);
            });
        }
    }
    
    // Clear the container first
    d3.select('#d3-container').html('');
    
    // Extract style information from spec if available
    let integratedTheme = theme;
    if (spec && spec._style) {
        // Using integrated styles from spec
        // Merge spec styles with backend theme (backend background takes priority)
        integratedTheme = {
            ...spec._style,
            background: theme?.background
        };
        // Merged theme background (backend priority)
    } else {
        // Use theme as-is (no fallbacks)
        integratedTheme = theme;
        // Using backend theme background
    }
    
    // Extract style metadata for debugging
    if (spec && spec._style_metadata) {
        // Style metadata available
    }
    
    switch (type) {
        case 'double_bubble_map':
            if (typeof renderDoubleBubbleMap === 'function') {
                renderDoubleBubbleMap(spec, integratedTheme, dimensions);
            } else {
                console.error('renderDoubleBubbleMap function not found');
                showRendererError('double_bubble_map');
            }
            break;
        case 'bubble_map':
            if (typeof renderBubbleMap === 'function') {
                renderBubbleMap(spec, integratedTheme, dimensions);
            } else {
                console.error('renderBubbleMap function not found');
                showRendererError('bubble_map');
            }
            break;
        case 'circle_map':
            if (typeof renderCircleMap === 'function') {
                renderCircleMap(spec, integratedTheme, dimensions);
            } else {
                console.error('renderCircleMap function not found');
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
                console.error('renderTreeMap function not found anywhere');
                showRendererError('tree_map');
            }
            break;
        case 'concept_map':
            // CRITICAL FIX: Check all possible locations for the function
            console.log('🔍 Renderer dispatcher: Looking for concept_map renderer...');
            console.log('🔍 Available functions:', {
                'renderConceptMap (global)': typeof renderConceptMap,
                'window.ConceptMapRenderer': typeof window.ConceptMapRenderer,
                'window.ConceptMapRenderer.renderConceptMap': window.ConceptMapRenderer ? typeof window.ConceptMapRenderer.renderConceptMap : 'N/A'
            });
            
            let conceptMapRenderer = null;
            if (typeof renderConceptMap === 'function') {
                conceptMapRenderer = renderConceptMap;
                console.log('✅ Using global renderConceptMap function');
            } else if (window.ConceptMapRenderer && typeof window.ConceptMapRenderer.renderConceptMap === 'function') {
                conceptMapRenderer = window.ConceptMapRenderer.renderConceptMap;
                console.log('✅ Using window.ConceptMapRenderer.renderConceptMap function');
            }
            
            if (conceptMapRenderer) {
                // Calling concept map renderer
                try {
                    console.log('🚀 Calling concept map renderer...');
                    conceptMapRenderer(spec, integratedTheme, dimensions);
                    console.log('✅ Concept map rendering completed');
                } catch (error) {
                    console.error('❌ Error rendering concept map:', error);
                    showRendererError('concept_map', error.message);
                }
            } else {
                console.error('❌ renderConceptMap function not found anywhere');
                showRendererError('concept_map');
            }
            break;
        case 'mindmap':
        case 'mind_map':
            if (typeof renderMindMap === 'function') {
                renderMindMap(spec, integratedTheme, dimensions);
            } else {
                console.error('renderMindMap function not found');
                showRendererError('mind_map');
            }
            break;
        case 'flowchart':
            if (typeof renderFlowchart === 'function') {
                renderFlowchart(spec, integratedTheme, dimensions);
            } else {
                console.error('renderFlowchart function not found');
                showRendererError('flowchart');
            }
            break;

        case 'bridge_map':
            console.log('=== RENDERER DISPATCHER: BRIDGE MAP CASE ===');
            console.log('Spec received:', spec);
            console.log('Spec type:', typeof spec);
            console.log('Spec keys:', Object.keys(spec || {}));
            console.log('Analogies array:', spec?.analogies);
            console.log('Analogies count:', spec?.analogies?.length || 0);
            
            // Log each analogy before calling renderer
            if (spec?.analogies && Array.isArray(spec.analogies)) {
                spec.analogies.forEach((analogy, index) => {
                    console.log(`Dispatcher Analogy ${index}:`, analogy);
                    console.log(`  Left: "${analogy.left}"`);
                    console.log(`  Right: "${analogy.right}"`);
                });
            }
            
            console.log('Calling renderBridgeMap...');
            if (typeof renderBridgeMap === 'function') {
                renderBridgeMap(spec, integratedTheme, dimensions, 'd3-container');
                console.log('renderBridgeMap call completed');
            } else {
                console.error('renderBridgeMap function not found');
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
                    // Brace map rendering completed
                } catch (error) {
                    console.error('Error rendering brace map:', error);
                    showRendererError('brace_map', error.message);
                }
            } else {
                console.error('renderBraceMap function not found anywhere');
                showRendererError('brace_map');
            }
            break;
        case 'flow_map':
            if (typeof renderFlowMap === 'function') {
                renderFlowMap(spec, integratedTheme, dimensions);
            } else {
                console.error('renderFlowMap function not found');
                showRendererError('flow_map');
            }
            break;
        case 'multi_flow_map':
            if (typeof renderMultiFlowMap === 'function') {
                renderMultiFlowMap(spec, integratedTheme, dimensions);
            } else {
                console.error('renderMultiFlowMap function not found');
                showRendererError('multi_flow_map');
            }
            break;
        default:
            console.error(`Unknown graph type: ${type}`);
            showRendererError('unknown', `Unknown graph type '${type}'`);
    }
}

// Helper function to show renderer errors
function showRendererError(type, message = null) {
    const errorMsg = message || `Renderer for '${type}' not loaded or not available`;
    d3.select('#d3-container').append('div')
        .style('color', 'red')
        .style('font-size', '18px')
        .style('text-align', 'center')
        .style('padding', '50px')
        .text(`Error: ${errorMsg}`);
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
