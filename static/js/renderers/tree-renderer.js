/**
 * Tree Renderer for MindGraph
 * 
 * This module contains the tree map rendering function.
 * Requires: shared-utilities.js, style-manager.js
 * 
 * Performance Impact: Loads only ~60KB instead of full 213KB
 */

// CRITICAL FIX: Add execution tracking
// Tree renderer script execution started

// Check if shared utilities are available
// Checking dependencies

if (typeof window.MindGraphUtils === 'undefined') {
    console.error('🌳 Tree renderer: MindGraphUtils not found! Please load shared-utilities.js first.');
    // Don't continue if dependencies are missing
    throw new Error('MindGraphUtils not available - shared-utilities.js must be loaded first');
}

// Import required functions from shared utilities - with error handling
// CRITICAL FIX: Don't redeclare addWatermark, use the global one
if (typeof window.MindGraphUtils === 'undefined' || typeof window.MindGraphUtils.addWatermark !== 'function') {
    console.error('🌳 Tree renderer: addWatermark function not found in MindGraphUtils');
    throw new Error('addWatermark function not available - shared-utilities.js must be loaded first');
}

// Main tree map rendering function - EXPOSE TO GLOBAL SCOPE
function renderTreeMap(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    
    // Validate spec
    if (!spec || !spec.topic || !Array.isArray(spec.children)) {
        console.error('Invalid spec for tree map');
        return;
    }
    
    // Handle empty children case
    if (spec.children.length === 0) {
        console.warn('Tree map has no branches to display');
        return;
    }
    
    // Use provided theme and dimensions or defaults
    const baseWidth = dimensions?.baseWidth || 800;
    const baseHeight = dimensions?.baseHeight || 600;
    const padding = dimensions?.padding || 40;
    
    // Load theme from style manager - FIXED: No more hardcoded overrides
    let THEME;
    try {
        if (typeof styleManager !== 'undefined' && styleManager.getTheme) {
            THEME = styleManager.getTheme('tree_map', theme, theme);
            console.log('Tree: Using centralized theme from style manager');
        } else {
            console.error('Style manager not available - this should not happen');
            throw new Error('Style manager not available for tree map rendering');
        }
    } catch (error) {
        console.error('Error getting theme from style manager:', error);
        throw new Error('Failed to load theme from style manager');
    }
    
    const width = baseWidth;
    const height = baseHeight;
    
    // Apply container background - matching mind map renderer
    const containerBackground = theme?.background || '#f5f5f5';
    d3.select('#d3-container')
        .style('background-color', containerBackground)
        .style('width', '100%')
        .style('height', '100%')
        .style('min-height', `${baseHeight}px`);
    
    var svg = d3.select('#d3-container').append('svg')
        .attr('width', width)
        .attr('height', height)
        .style('background-color', containerBackground); // Use the same background color

    // Helpers to measure text accurately for width-adaptive rectangles
    const avgCharPx = 0.6; // fallback approximation
    function measureTextApprox(text, fontPx, hPad = 14, vPad = 10) {
        const tw = Math.max(1, (text ? text.length : 0) * fontPx * avgCharPx);
        const th = Math.max(1, fontPx * 1.2);
        return { w: Math.ceil(tw + hPad * 2), h: Math.ceil(th + vPad * 2) };
    }
    function measureSvgTextBox(svg, text, fontPx, hPad = 14, vPad = 10) {
        try {
            const temp = svg.append('text')
                .attr('x', -10000)
                .attr('y', -10000)
                .attr('font-size', fontPx)
                .attr('font-family', 'Inter, Segoe UI, sans-serif')
                .attr('visibility', 'hidden')
                .text(text || '');
            const node = temp.node();
            let textWidth = 0;
            if (node && node.getComputedTextLength) {
                textWidth = node.getComputedTextLength();
            } else if (node && node.getBBox) {
                textWidth = node.getBBox().width || 0;
            }
            temp.remove();
            const textHeight = Math.max(1, fontPx * 1.2);
            return { w: Math.ceil(textWidth + hPad * 2), h: Math.ceil(textHeight + vPad * 2) };
        } catch (e) {
            // Fallback to approximation if DOM measurement fails
            return measureTextApprox(text, fontPx, hPad, vPad);
        }
    }
    
    // Calculate layout
    const rootX = width / 2;
    const rootY = 80;
    const rootFont = THEME.fontRoot || 20;
    const rootBox = measureSvgTextBox(svg, spec.topic, rootFont, 16, 12);
    // Draw root node as rectangle
    svg.append('rect')
        .attr('x', rootX - rootBox.w / 2)
        .attr('y', rootY - rootBox.h / 2)
        .attr('width', rootBox.w)
        .attr('height', rootBox.h)
        .attr('rx', 6)
        .attr('ry', 6)
        .attr('fill', THEME.rootFill)
        .attr('stroke', THEME.rootStroke)
        .attr('stroke-width', THEME.rootStrokeWidth)
        .attr('data-node-id', 'tree-topic')
        .attr('data-node-type', 'topic');
    svg.append('text')
        .attr('x', rootX)
        .attr('y', rootY)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('fill', THEME.rootText)
        .attr('font-size', rootFont)
        .attr('font-weight', 'bold')
        .attr('data-text-for', 'tree-topic')
        .attr('cursor', 'pointer')
        .text(spec.topic);
    
    // Draw branches
    const branchY = rootY + rootBox.h / 2 + 60;
    let requiredBottomY = branchY + 40;

    // First pass: measure branches and leaves, compute per-column width
    const branchLayouts = spec.children.map((child) => {
        // Validate child structure - accept both 'text' and 'label' properties
        const childText = child?.text || child?.label;
        if (!child || typeof childText !== 'string') {
            console.warn('Invalid child structure:', child);
            return null;
        }
        
        const branchFont = THEME.fontBranch || 16;
        const branchBox = measureSvgTextBox(svg, childText, branchFont, 14, 10);
        const leafFont = THEME.fontLeaf || 14;
        let maxLeafW = 0;
        const leafBoxes = (Array.isArray(child.children) ? child.children : []).map(leaf => {
            const leafText = leaf?.text || leaf?.label;
            if (!leaf || typeof leafText !== 'string') {
                console.warn('Invalid leaf structure:', leaf);
                return null;
            }
            const b = measureSvgTextBox(svg, leafText, leafFont, 12, 8);
            if (b.w > maxLeafW) maxLeafW = b.w;
            return { ...b, text: leafText };
        }).filter(box => box !== null); // Filter out invalid leaves
        
        const columnContentW = Math.max(branchBox.w, maxLeafW);
        const columnWidth = columnContentW + 60; // padding within column to avoid overlap
        return { child, childText, branchFont, branchBox, leafFont, leafBoxes, maxLeafW, columnWidth };
    }).filter(layout => layout !== null); // Filter out invalid layouts

    // Second pass: assign x positions cumulatively to prevent overlap
    let runningX = padding;
    branchLayouts.forEach((layout) => {
        const xCenter = runningX + layout.columnWidth / 2;
        layout.branchX = xCenter;
        runningX += layout.columnWidth; // advance to next column start
    });

    // Compute content width and adapt canvas width if needed; otherwise center within available space
    const totalColumnsWidth = runningX - padding;
    const contentWidth = padding * 2 + totalColumnsWidth;
    let offsetX = 0;
    if (contentWidth <= width) {
        offsetX = (width - contentWidth) / 2;
    } else {
        // Expand SVG canvas to fit content
        d3.select(svg.node()).attr('width', contentWidth);
    }
    branchLayouts.forEach(layout => { layout.branchX += offsetX; });

    // Render branches and children stacked vertically with straight connectors
    branchLayouts.forEach((layout, branchIndex) => {
        const { child, childText, branchFont, branchBox, leafFont, leafBoxes, maxLeafW } = layout;
        const branchX = layout.branchX;

        // Draw branch rectangle and label with width adaptive to characters
        svg.append('rect')
            .attr('x', branchX - branchBox.w / 2)
            .attr('y', branchY - branchBox.h / 2)
            .attr('width', branchBox.w)
            .attr('height', branchBox.h)
            .attr('rx', 6)
            .attr('ry', 6)
            .attr('fill', THEME.branchFill)
            .attr('stroke', THEME.branchStroke)
            .attr('stroke-width', THEME.branchStrokeWidth)
            .attr('data-node-id', `tree-category-${branchIndex}`)
            .attr('data-node-type', 'category')
            .attr('data-category-index', branchIndex);

        svg.append('text')
            .attr('x', branchX)
            .attr('y', branchY)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.branchText)
            .attr('font-size', branchFont)
            .attr('data-text-for', `tree-category-${branchIndex}`)
            .attr('cursor', 'pointer')
            .text(childText);

        // Root to branch straight connector
        svg.append('line')
            .attr('x1', rootX)
            .attr('y1', rootY + rootBox.h / 2)
            .attr('x2', branchX)
            .attr('y2', branchY - branchBox.h / 2)
            .attr('stroke', '#bbb')
            .attr('stroke-width', 2);

        // Children: stacked vertically, centered, with straight vertical connectors
        const leaves = Array.isArray(child.children) ? child.children : [];
        if (leaves.length > 0) {
            const vGap = 12;
            const startY = branchY + branchBox.h / 2 + 20;

            // Compute vertical centers bottom-up using actual heights (center-aligned at branchX)
            const centersY = [];
            let cy = startY + (leafBoxes[0]?.h || (leafFont * 1.2 + 10)) / 2;
            leaves.forEach((_, j) => {
                const prevH = j === 0 ? 0 : (leafBoxes[j - 1]?.h || (leafFont * 1.2 + 10));
                const h = leafBoxes[j]?.h || (leafFont * 1.2 + 10);
                if (j === 0) {
                    centersY.push(cy);
                } else {
                    cy = centersY[j - 1] + prevH / 2 + vGap + h / 2;
                    centersY.push(cy);
                }
            });

            // Draw child rectangles and labels centered at branchX
            leaves.forEach((leaf, j) => {
                const leafText = leaf?.text || leaf?.label;
                const box = leafBoxes[j] || measureSvgTextBox(svg, leafText, leafFont, 12, 8);
                const leafY = centersY[j];
                // Width adaptive to characters for each node
                const rectW = box.w;
                svg.append('rect')
                    .attr('x', branchX - rectW / 2)
                    .attr('y', leafY - box.h / 2)
                    .attr('width', rectW)
                    .attr('height', box.h)
                    .attr('rx', 4)
                    .attr('ry', 4)
                    .attr('fill', THEME.leafFill || '#ffffff')
                    .attr('stroke', THEME.leafStroke || '#c8d6e5')
                    .attr('stroke-width', THEME.leafStrokeWidth != null ? THEME.leafStrokeWidth : 1)
                    .attr('data-node-id', `tree-leaf-${branchIndex}-${j}`)
                    .attr('data-node-type', 'leaf')
                    .attr('data-category-index', branchIndex)
                    .attr('data-leaf-index', j);

                svg.append('text')
                    .attr('x', branchX)
                    .attr('y', leafY)
                    .attr('text-anchor', 'middle')
                    .attr('dominant-baseline', 'middle')
                    .attr('fill', THEME.leafText)
                    .attr('font-size', leafFont)
                    .attr('data-text-for', `tree-leaf-${branchIndex}-${j}`)
                    .attr('cursor', 'pointer')
                    .text(leafText);
            });

            // Draw straight vertical connectors: branch -> first child, then between consecutive children
            const firstTop = centersY[0] - (leafBoxes[0]?.h || (leafFont * 1.2 + 10)) / 2;
            svg.append('line')
                .attr('x1', branchX)
                .attr('y1', branchY + branchBox.h / 2)
                .attr('x2', branchX)
                .attr('y2', firstTop)
                .attr('stroke', '#cccccc')
                .attr('stroke-width', 1.5);

            for (let j = 0; j < centersY.length - 1; j++) {
                const thisBottom = centersY[j] + (leafBoxes[j]?.h || (leafFont * 1.2 + 10)) / 2;
                const nextTop = centersY[j + 1] - (leafBoxes[j + 1]?.h || (leafFont * 1.2 + 10)) / 2;
                svg.append('line')
                    .attr('x1', branchX)
                    .attr('y1', thisBottom)
                    .attr('x2', branchX)
                    .attr('y2', nextTop)
                    .attr('stroke', '#cccccc')
                    .attr('stroke-width', 1.5);
            }

            const lastBottom = centersY[centersY.length - 1] + (leafBoxes[leafBoxes.length - 1]?.h || (leafFont * 1.2 + 10)) / 2;
            requiredBottomY = Math.max(requiredBottomY, lastBottom + 30);
        } else {
            requiredBottomY = Math.max(requiredBottomY, branchY + branchBox.h / 2 + 40);
        }
    });

    // Expand SVG height if content exceeds current height
    const finalNeededHeight = Math.ceil(requiredBottomY + padding);
    if (finalNeededHeight > height) {
        svg.attr('height', finalNeededHeight);
    }
    
    // Apply learning sheet text knockout if needed
    console.log('Tree renderer: Checking learning sheet metadata:', {
        is_learning_sheet: spec.is_learning_sheet,
        hidden_node_percentage: spec.hidden_node_percentage,
        spec_keys: Object.keys(spec)
    });
    if (spec.is_learning_sheet && spec.hidden_node_percentage > 0) {
        console.log('Tree renderer: Calling knockout function with percentage:', spec.hidden_node_percentage);
        knockoutTextForLearningSheet(svg, spec.hidden_node_percentage);
    } else {
        console.log('Tree renderer: Skipping knockout - conditions not met');
    }
}



// CRITICAL FIX: Export functions to global scope for dispatcher access
    // Starting function export

// CRITICAL FIX: Use try-catch to ensure export doesn't fail silently
try {
    if (typeof window !== 'undefined') {
        // Browser environment - attach to window
        // Attaching to window object
        
        // Force the assignment - check if properties already exist
        if (!window.hasOwnProperty('renderTreeMap')) {
            Object.defineProperty(window, 'renderTreeMap', {
                value: renderTreeMap,
                writable: true,
                configurable: true
            });
            // renderTreeMap property defined
        } else {
            // renderTreeMap property defined
            window.renderTreeMap = renderTreeMap;
        }
        
        if (!window.hasOwnProperty('TreeRenderer')) {
            Object.defineProperty(window, 'TreeRenderer', {
                value: {
                    renderTreeMap: renderTreeMap
                },
                writable: true,
                configurable: true
            });
            // TreeRenderer property defined
        } else {
            // TreeRenderer property defined
            window.TreeRenderer = { renderTreeMap: renderTreeMap };
        }
        
        // Tree renderer functions exported to global scope
        // renderTreeMap property defined
        // TreeRenderer property defined
        
        // Verify the export worked
        if (typeof window.renderTreeMap === 'function') {
            // renderTreeMap property defined
        } else {
            console.error('�?FAILED: renderTreeMap is not available globally');
        }
        
        if (typeof window.TreeRenderer === 'object' && window.TreeRenderer.renderTreeMap) {
            // renderTreeMap property defined
        } else {
            console.error('�?FAILED: TreeRenderer.renderTreeMap is not available globally');
        }
        
    } else if (typeof module !== 'undefined' && module.exports) {
        // Node.js environment
        module.exports = {
            renderTreeMap,
            TreeRenderer: {
                renderTreeMap
            }
        };
    }
} catch (error) {
    console.error('�?CRITICAL ERROR during function export:', error);
    // Try alternative export method
    try {
        // Alternative export completed
        if (typeof window !== 'undefined') {
            window.renderTreeMap = renderTreeMap;
            window.TreeRenderer = { renderTreeMap: renderTreeMap };
            // Alternative export completed
        }
    } catch (altError) {
        console.error('�?Alternative export also failed:', altError);
    }
}

// CRITICAL FIX: Final execution confirmation
// Script execution completed
// Final status check completed
// renderTreeMap property defined
// renderTreeMap property defined
// TreeRenderer property defined
