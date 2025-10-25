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
    logger.error('TreeRenderer', 'MindGraphUtils not found! Please load shared-utilities.js first');
    // Don't continue if dependencies are missing
    throw new Error('MindGraphUtils not available - shared-utilities.js must be loaded first');
}

// Import required functions from shared utilities - with error handling
// CRITICAL FIX: Don't redeclare addWatermark, use the global one
if (typeof window.MindGraphUtils === 'undefined' || typeof window.MindGraphUtils.addWatermark !== 'function') {
    logger.error('TreeRenderer', 'addWatermark function not found in MindGraphUtils');
    throw new Error('addWatermark function not available - shared-utilities.js must be loaded first');
}

// Main tree map rendering function - EXPOSE TO GLOBAL SCOPE
function renderTreeMap(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    
    // Validate spec
    if (!spec || !spec.topic || !Array.isArray(spec.children)) {
        logger.error('TreeRenderer', 'Invalid spec for tree map');
        return;
    }
    
    // Handle empty children case
    if (spec.children.length === 0) {
        logger.warn('TreeRenderer', 'Tree map has no branches to display');
        return;
    }
    
    // Use adaptive dimensions if provided, otherwise use fallback dimensions
    let baseWidth, baseHeight, padding;
    
    if (spec._recommended_dimensions) {
        // Adaptive dimensions from template (calculated based on window size)
        baseWidth = spec._recommended_dimensions.width;
        baseHeight = spec._recommended_dimensions.height;
        padding = spec._recommended_dimensions.padding;
    } else if (dimensions) {
        // Provided dimensions (fallback)
        baseWidth = dimensions.width || dimensions.baseWidth || 800;
        baseHeight = dimensions.height || dimensions.baseHeight || 600;
        padding = dimensions.padding || 40;
    } else {
        // Default dimensions
        baseWidth = 800;
        baseHeight = 600;
        padding = 40;
    }
    
    // Load theme from style manager - FIXED: No more hardcoded overrides
    let THEME;
    try {
        if (typeof styleManager !== 'undefined' && styleManager.getTheme) {
            THEME = styleManager.getTheme('tree_map', theme, theme);
        } else {
            logger.error('TreeRenderer', 'Style manager not available');
            throw new Error('Style manager not available for tree map rendering');
        }
    } catch (error) {
        logger.error('TreeRenderer', 'Error getting theme from style manager', error);
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
        .attr('viewBox', `0 0 ${width} ${height}`)
        .attr('preserveAspectRatio', 'xMinYMin meet')
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
    
    // Calculate layout - rootX will be calculated after branch positions are determined
    const rootY = 80;
    const rootFont = THEME.fontRoot || 20;
    const rootBox = measureSvgTextBox(svg, spec.topic, rootFont, 16, 12);
    
    // Draw branches
    const branchY = rootY + rootBox.h / 2 + 60;
    let requiredBottomY = branchY + 40;

    // First pass: measure branches and leaves, compute per-column width
    const branchLayouts = spec.children.map((child) => {
        // Validate child structure - accept both 'text' and 'label' properties
        const childText = child?.text || child?.label;
        if (!child || typeof childText !== 'string') {
            logger.warn('TreeRenderer', 'Invalid child structure', child);
            return null;
        }
        
        const branchFont = THEME.fontBranch || 16;
        const branchBox = measureSvgTextBox(svg, childText, branchFont, 14, 10);
        const leafFont = THEME.fontLeaf || 14;
        let maxLeafW = 0;
        const leafBoxes = (Array.isArray(child.children) ? child.children : []).map(leaf => {
            const leafText = leaf?.text || leaf?.label;
            if (!leaf || typeof leafText !== 'string') {
                logger.warn('TreeRenderer', 'Invalid leaf structure', leaf);
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
        // CRITICAL: Also update viewBox to match the expanded width
        d3.select(svg.node()).attr('viewBox', `0 0 ${contentWidth} ${height}`);
    }
    branchLayouts.forEach(layout => { layout.branchX += offsetX; });

    // Calculate rootX position - center of all branch nodes
    let rootX;
    if (branchLayouts.length > 0) {
        if (branchLayouts.length === 1) {
            // Single child: align root with child center
            rootX = branchLayouts[0].branchX;
        } else if (branchLayouts.length % 2 === 1) {
            // Odd number of children: align root with middle child
            const middleIndex = Math.floor(branchLayouts.length / 2);
            rootX = branchLayouts[middleIndex].branchX;
        } else {
            // Even number of children: center between all children
            const branchXs = branchLayouts.map(l => l.branchX);
            const minBranchX = Math.min(...branchXs);
            const maxBranchX = Math.max(...branchXs);
            rootX = minBranchX + (maxBranchX - minBranchX) / 2;
        }
    } else {
        rootX = width / 2; // fallback to center if no branches
    }

    // RENDERING ORDER: Draw T-connector lines FIRST (underneath), then nodes on top
    // ---------- T形连线实现 (Draw T-connectors FIRST for proper z-order) ----------
    if (branchLayouts.length > 0) {
        // Calculate vertical line positions
        // Dimension label is at rootY + rootBox.h / 2 + 20
        const rootBottom = rootY + rootBox.h / 2;
        const dimensionLabelY = rootBottom + 20;  // Dimension label position
        const branchTop = branchY - branchLayouts[0].branchBox.h / 2;
        
        // T-junction Y: ensure it's at least 40px below dimension label for clear visual separation
        const minTLineY = dimensionLabelY + 40;  // At least 40px below label
        const calculatedTLineY = rootBottom + (branchTop - rootBottom) / 2;
        const tLineY = Math.max(minTLineY, calculatedTLineY);  // Use the lower of the two
        
        // 所有子节点 X 范围
        const branchXs = branchLayouts.map(l => l.branchX);
        const minX = Math.min(...branchXs);
        const maxX = Math.max(...branchXs);
        
        // 垂直干线：从根节点底部延伸，穿过dimension label区域
        // Extended line: starts at root bottom, extends through and beyond dimension label area
        svg.append('line')
            .attr('x1', rootX)
            .attr('y1', rootY + rootBox.h / 2)  // Start at root node bottom
            .attr('x2', rootX)
            .attr('y2', tLineY)  // Extend down to T-junction (already beyond label at +25px)
            .attr('stroke', '#bbb')
            .attr('stroke-width', 2);
        
        // 水平线
        svg.append('line')
            .attr('x1', minX)
            .attr('y1', tLineY)
            .attr('x2', maxX)
            .attr('y2', tLineY)
            .attr('stroke', '#bbb')
            .attr('stroke-width', 2);
        
        // 每个子节点竖线连接到水平线
        branchLayouts.forEach(layout => {
            svg.append('line')
                .attr('x1', layout.branchX)
                .attr('y1', tLineY)
                .attr('x2', layout.branchX)
                .attr('y2', branchY - layout.branchBox.h / 2)
                .attr('stroke', '#bbb')
                .attr('stroke-width', 2);
        });
    }

    // Draw root node as rectangle (AFTER T-connectors for proper z-order)
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
        .attr('data-node-id', 'tree-topic')
        .attr('data-node-type', 'topic')
        .attr('cursor', 'pointer')
        .text(spec.topic);
    
    // ALWAYS show dimension label (even for old diagrams without dimension field)
    // This allows users to click and add/edit the classification dimension
    const dimensionY = rootY + rootBox.h / 2 + 20;  // 20px below topic box
    const dimensionFontSize = 14;
    
    let dimensionText;
    let textOpacity;
    
    if (spec.dimension && spec.dimension.trim() !== '') {
        // Dimension has value - show it with label
        const hasChinese = /[\u4e00-\u9fa5]/.test(spec.dimension);
        const dimensionLabel = hasChinese ? '分类维度' : 'Classification by';
        dimensionText = `[${dimensionLabel}: ${spec.dimension}]`;
        textOpacity = 0.8;
    } else {
        // Dimension is empty or doesn't exist - show placeholder
        // Detect language from topic to show appropriate placeholder
        const hasChinese = /[\u4e00-\u9fa5]/.test(spec.topic);
        dimensionText = hasChinese ? '[分类维度: 点击填写...]' : '[Classification by: click to specify...]';
        textOpacity = 0.4;  // Lower opacity for placeholder
    }
    
    // Make dimension text EDITABLE - users can click to change/fill classification standard
    svg.append('text')
        .attr('x', rootX)
        .attr('y', dimensionY)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('fill', THEME.dimensionLabelColor || '#1976d2')  // Dark blue for classroom visibility
        .attr('font-size', dimensionFontSize)
        .attr('font-family', 'Inter, Segoe UI, sans-serif')
        .attr('font-style', 'italic')
        .style('opacity', textOpacity)
        .style('cursor', 'pointer')  // Show it's clickable
        .attr('data-node-id', 'dimension_label')  // Make it editable
        .attr('data-node-type', 'dimension')  // Identify as dimension node
        .attr('data-dimension-value', spec.dimension || '')  // Store actual dimension value (or empty)
        .text(dimensionText);

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
            .attr('data-node-id', `tree-category-${branchIndex}`)
            .attr('data-node-type', 'category')
            .attr('cursor', 'pointer')
            .text(childText);

        // T形连线将在所有子节点绘制完成后统一绘制

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
                    .attr('data-node-id', `tree-leaf-${branchIndex}-${j}`)
                    .attr('data-node-type', 'leaf')
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

    // T-connectors already drawn at the beginning (before root node) for proper z-order
    // This ensures connector lines appear UNDERNEATH all nodes (root, branches, and leaves)

    // Add alternative dimensions at the bottom (if alternative_dimensions field exists)
    if (spec.alternative_dimensions && Array.isArray(spec.alternative_dimensions) && spec.alternative_dimensions.length > 0) {
        // Position exactly 15px below the last rendered content
        const separatorY = requiredBottomY + 15;  // Separator line 15px below the bottom edge of last content
        const alternativesY = separatorY + 20;  // Label 20px below separator
        const fontSize = 13;
        
        // Detect language from first alternative dimension (if contains Chinese characters, use Chinese)
        const hasChinese = /[\u4e00-\u9fa5]/.test(spec.alternative_dimensions[0]);
        const alternativeLabel = hasChinese ? '本主题的其他可能分类维度：' : 'Other possible dimensions for this topic:';
        
        // Calculate center position based on content width
        const contentCenterX = rootX;  // Center on root node position
        
        // Draw separator line spanning the full width of diagram (from left to right padding)
        const separatorLeftX = padding;
        const separatorRightX = width - padding;
        
        svg.append('line')
            .attr('x1', separatorLeftX)
            .attr('y1', separatorY)
            .attr('x2', separatorRightX)
            .attr('y2', separatorY)
            .attr('stroke', THEME.dimensionLabelColor || '#1976d2')  // Dark blue for classroom visibility
            .attr('stroke-width', 1)
            .attr('stroke-dasharray', '4,4')
            .style('opacity', 0.4);
        
        // Add label centered on content
        svg.append('text')
            .attr('x', contentCenterX)
            .attr('y', alternativesY - 5)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.dimensionLabelColor || '#1976d2')  // Dark blue for classroom visibility
            .attr('font-size', fontSize)
            .attr('font-family', 'Inter, Segoe UI, sans-serif')
            .style('opacity', 0.7)
            .text(alternativeLabel);
        
        // Add dimension chips/badges centered on content
        const dimensionChips = spec.alternative_dimensions.map(d => `• ${d}`).join('  ');
        svg.append('text')
            .attr('x', contentCenterX)
            .attr('y', alternativesY + 18)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.dimensionLabelColor || '#1976d2')  // Dark blue for classroom visibility
            .attr('font-size', fontSize - 1)
            .attr('font-family', 'Inter, Segoe UI, sans-serif')
            .attr('font-weight', '600')
            .style('opacity', 0.8)
            .text(dimensionChips);
        
        // Update required bottom Y to account for alternative dimensions section
        requiredBottomY = alternativesY + 35; // Add space for the alternative dimensions content
    }
    
    // Expand SVG height if content exceeds current height
    const finalNeededHeight = Math.ceil(requiredBottomY + padding);
    if (finalNeededHeight > height) {
        // Get current width (may have been expanded earlier)
        const currentWidth = parseFloat(svg.attr('width')) || width;
        svg.attr('height', finalNeededHeight);
        // CRITICAL: Also update viewBox to match the expanded dimensions
        svg.attr('viewBox', `0 0 ${currentWidth} ${finalNeededHeight}`);
    }
    
    // Watermark removed from canvas display - will be added during PNG export only
    // The export functionality will handle adding the watermark to the final image
    
    // Apply learning sheet text knockout if needed
    if (spec.is_learning_sheet && spec.hidden_node_percentage > 0) {
        knockoutTextForLearningSheet(svg, spec.hidden_node_percentage);
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
            logger.error('TreeRenderer', '�?FAILED: renderTreeMap is not available globally');
        }
        
        if (typeof window.TreeRenderer === 'object' && window.TreeRenderer.renderTreeMap) {
            // renderTreeMap property defined
        } else {
            logger.error('TreeRenderer', '�?FAILED: TreeRenderer.renderTreeMap is not available globally');
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
    logger.error('TreeRenderer', '�?CRITICAL ERROR during function export:', error);
    // Try alternative export method
    try {
        // Alternative export completed
        if (typeof window !== 'undefined') {
            window.renderTreeMap = renderTreeMap;
            window.TreeRenderer = { renderTreeMap: renderTreeMap };
            // Alternative export completed
        }
    } catch (altError) {
        logger.error('TreeRenderer', '�?Alternative export also failed:', altError);
    }
}

// CRITICAL FIX: Final execution confirmation
// Script execution completed
// Final status check completed
// renderTreeMap property defined
// renderTreeMap property defined
// TreeRenderer property defined
