/**
 * Tree Renderer for MindGraph
 * 
 * This module contains the tree map rendering function.
 * Requires: shared-utilities.js, style-manager.js
 * 
 * Performance Impact: Loads only ~60KB instead of full 213KB
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
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
    // Validate BEFORE clearing container - defensive programming
    // Use typeof check to allow empty string (for empty button functionality)
    if (!spec || typeof spec.topic !== 'string' || !Array.isArray(spec.children)) {
        logger.error('TreeRenderer', 'Invalid spec for tree map');
        return;
    }
    
    d3.select('#d3-container').html('');
    
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
        .attr('preserveAspectRatio', 'xMidYMid meet')
        .style('background-color', containerBackground); // Use the same background color

    // Helpers to measure text accurately for width-adaptive rectangles
    const avgCharPx = 0.6; // fallback approximation
    function measureTextApprox(text, fontPx, hPad = 14, vPad = 10) {
        const tw = Math.max(1, (text ? text.length : 0) * fontPx * avgCharPx);
        const th = Math.max(1, fontPx * 1.2);
        return { w: Math.ceil(tw + hPad * 2), h: Math.ceil(th + vPad * 2) };
    }
    
    // Helper for splitAndWrapText compatibility (takes text, fontSize, returns width)
    function measureLineWidthForWrap(text, fontSize) {
        try {
            const temp = svg.append('text')
                .attr('x', -10000)
                .attr('y', -10000)
                .attr('font-size', fontSize)
                .attr('font-family', 'Inter, Segoe UI, sans-serif')
                .attr('visibility', 'hidden')
                .text(text || '');
            const node = temp.node();
            let width = 0;
            if (node && node.getComputedTextLength) {
                width = node.getComputedTextLength();
            } else if (node && node.getBBox) {
                width = node.getBBox().width || 0;
            }
            temp.remove();
            return width;
        } catch (e) {
            // Fallback approximation
            return (text ? text.length : 0) * fontSize * avgCharPx;
        }
    }
    
    function measureSvgTextBox(svg, text, fontPx, hPad = 14, vPad = 10) {
        try {
            // Split text by newlines to handle multi-line text (Ctrl+Enter)
            const lines = (typeof window.splitTextLines === 'function') 
                ? window.splitTextLines(text) 
                : (text || '').split(/\n/);
            const lineHeight = Math.round(fontPx * 1.2);
            
            // Measure width of longest line
            let maxTextWidth = 0;
            lines.forEach(line => {
                const temp = svg.append('text')
                    .attr('x', -10000)
                    .attr('y', -10000)
                    .attr('font-size', fontPx)
                    .attr('font-family', 'Inter, Segoe UI, sans-serif')
                    .attr('visibility', 'hidden')
                    .text(line || '');
                const node = temp.node();
                let lineWidth = 0;
                if (node && node.getComputedTextLength) {
                    lineWidth = node.getComputedTextLength();
                } else if (node && node.getBBox) {
                    lineWidth = node.getBBox().width || 0;
                }
                temp.remove();
                maxTextWidth = Math.max(maxTextWidth, lineWidth);
            });
            
            // Calculate height based on number of lines
            const textHeight = Math.max(1, lines.length * lineHeight);
            return { w: Math.ceil(maxTextWidth + hPad * 2), h: Math.ceil(textHeight + vPad * 2) };
        } catch (e) {
            // Fallback to approximation if DOM measurement fails
            return measureTextApprox(text, fontPx, hPad, vPad);
        }
    }
    
    // Calculate layout - rootX will be calculated after branch positions are determined
    const rootY = 80;
    const rootFont = THEME.fontRoot || 20;
    
    // Check for preserved dimensions first
    const nodeDimensions = spec._node_dimensions || {};
    let rootBox;
    if (nodeDimensions.topic && nodeDimensions.topic.w && nodeDimensions.topic.h) {
        rootBox = { w: nodeDimensions.topic.w, h: nodeDimensions.topic.h };
    } else {
        rootBox = measureSvgTextBox(svg, spec.topic, rootFont, 16, 12);
    }
    
    // Draw branches
    const branchY = rootY + rootBox.h / 2 + 60;
    let requiredBottomY = branchY + 40;

    // First pass: measure branches and leaves, compute per-column width
    // CRITICAL FIX: Track original index in spec.children to ensure data-category-index matches spec structure
    const branchLayouts = spec.children.map((child, specIndex) => {
        // Validate child structure - accept both 'text' and 'label' properties
        // Use nullish coalescing to properly handle empty strings
        let childText;
        if (typeof child === 'string') {
            childText = child;
        } else if (child && typeof child === 'object') {
            // Use ?? instead of || to handle empty strings properly
            childText = child.text ?? child.label ?? '';
        } else {
            logger.warn('TreeRenderer', 'Invalid child structure', child);
            return null;
        }
        
        // Check for preserved dimensions for branch
        const branchNodeKey = `category-${specIndex}`;
        const hasPreservedDimensions = nodeDimensions[branchNodeKey] && 
                                       nodeDimensions[branchNodeKey].w && 
                                       nodeDimensions[branchNodeKey].h;
        
        // Filter out empty branches ONLY if they don't have preserved dimensions
        const trimmedChildText = (childText || '').trim();
        if (trimmedChildText.length === 0 && !hasPreservedDimensions) {
            logger.debug('TreeRenderer', 'Skipping empty branch without preserved dimensions');
            return null;
        }
        
        const branchFont = THEME.fontBranch || 16;
        
        // Check for preserved dimensions for branch
        let branchBox;
        if (hasPreservedDimensions) {
            branchBox = { w: nodeDimensions[branchNodeKey].w, h: nodeDimensions[branchNodeKey].h };
            logger.debug('TreeRenderer', 'Using preserved branch dimensions', { branchNodeKey, ...branchBox });
        } else {
            branchBox = measureSvgTextBox(svg, childText, branchFont, 14, 10);
        }
        
        const leafFont = THEME.fontLeaf || 14;
        let maxLeafW = 0;
        const leafBoxes = (Array.isArray(child.children) ? child.children : []).map((leaf, leafSpecIndex) => {
            // Use nullish coalescing to properly handle empty strings
            // leaf can be an object {text: "..."} or a string
            let leafText;
            if (typeof leaf === 'string') {
                leafText = leaf;
            } else if (leaf && typeof leaf === 'object') {
                // Use ?? instead of || to handle empty strings properly
                leafText = leaf.text ?? leaf.label ?? '';
            } else {
                logger.warn('TreeRenderer', 'Invalid leaf structure', leaf);
                return null;
            }
            
            // Check for preserved dimensions for this leaf
            const leafNodeKey = `leaf-${specIndex}-${leafSpecIndex}`;
            const hasPreservedDimensions = nodeDimensions[leafNodeKey] && 
                                           nodeDimensions[leafNodeKey].w && 
                                           nodeDimensions[leafNodeKey].h;
            
            // Filter out empty children/leaves ONLY if they don't have preserved dimensions
            const trimmedLeafText = (leafText || '').trim();
            if (trimmedLeafText.length === 0 && !hasPreservedDimensions) {
                logger.debug('TreeRenderer', 'Skipping empty leaf without preserved dimensions');
                return null;
            }

            // Check for preserved dimensions for leaf
            let b;
            if (hasPreservedDimensions) {
                b = { w: nodeDimensions[leafNodeKey].w, h: nodeDimensions[leafNodeKey].h };
                logger.debug('TreeRenderer', 'Using preserved leaf dimensions', { leafNodeKey, ...b });
            } else {
                b = measureSvgTextBox(svg, leafText, leafFont, 12, 8);
            }
            
            if (b.w > maxLeafW) maxLeafW = b.w;
            // CRITICAL FIX: Include original leaf index in spec.children[x].children
            return { ...b, text: leafText, specLeafIndex: leafSpecIndex };
        }).filter(box => box !== null); // Filter out invalid leaves
        
        const columnContentW = Math.max(branchBox.w, maxLeafW);
        const columnWidth = columnContentW + 60; // padding within column to avoid overlap
        // CRITICAL FIX: Include specIndex to ensure data-category-index matches spec.children index
        return { child, childText, branchFont, branchBox, leafFont, leafBoxes, maxLeafW, columnWidth, specIndex };
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
        
        // 水平线 - 分段绘制，避免穿过节点
        // Horizontal line - draw in segments to avoid going through nodes
        // Sort branches by X position
        const sortedBranches = [...branchLayouts].sort((a, b) => a.branchX - b.branchX);
        
        // Draw line segments between nodes
        for (let i = 0; i < sortedBranches.length; i++) {
            const branch = sortedBranches[i];
            const nodeLeft = branch.branchX - branch.branchBox.w / 2;
            const nodeRight = branch.branchX + branch.branchBox.w / 2;
            
            if (i === 0) {
                // First segment: from minX to left edge of first node
                if (minX < nodeLeft) {
                    svg.append('line')
                        .attr('x1', minX)
                        .attr('y1', tLineY)
                        .attr('x2', nodeLeft)
                        .attr('y2', tLineY)
                        .attr('stroke', '#bbb')
                        .attr('stroke-width', 2);
                }
            }
            
            if (i < sortedBranches.length - 1) {
                // Segment between current node and next node
                const nextBranch = sortedBranches[i + 1];
                const nextNodeLeft = nextBranch.branchX - nextBranch.branchBox.w / 2;
                
                if (nodeRight < nextNodeLeft) {
                    svg.append('line')
                        .attr('x1', nodeRight)
                        .attr('y1', tLineY)
                        .attr('x2', nextNodeLeft)
                        .attr('y2', tLineY)
                        .attr('stroke', '#bbb')
                        .attr('stroke-width', 2);
                }
            } else {
                // Last segment: from right edge of last node to maxX
                if (nodeRight < maxX) {
                    svg.append('line')
                        .attr('x1', nodeRight)
                        .attr('y1', tLineY)
                        .attr('x2', maxX)
                        .attr('y2', tLineY)
                        .attr('stroke', '#bbb')
                        .attr('stroke-width', 2);
                }
            }
        }
        
        // 不绘制从水平线到类别节点的竖线 - 水平线已经通过竖线连接到节点中心，不需要额外的竖线
        // Don't draw vertical lines from horizontal line to category nodes - horizontal line connects via vertical lines at node centers
        // The vertical lines are not needed since the horizontal line segments already connect properly
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
    // Render root topic text - use multiple text elements (tspan doesn't render)
    const rootText = spec.topic || '';
    const rootMaxWidth = rootBox.w * 0.9; // Max width based on box width
    const rootLineHeight = Math.round(rootFont * 1.2);
    
    // Use splitAndWrapText for automatic word wrapping
    const rootLines = (typeof window.splitAndWrapText === 'function')
        ? window.splitAndWrapText(rootText, rootFont, rootMaxWidth, measureLineWidthForWrap)
        : (rootText ? [rootText] : ['']);
    
    // Ensure at least one line for placeholder
    const finalRootLines = rootLines.length > 0 ? rootLines : [''];
    
    // WORKAROUND: Use multiple text elements instead of tspan
    const rootStartY = rootY - (finalRootLines.length - 1) * rootLineHeight / 2;
    finalRootLines.forEach((line, i) => {
        svg.append('text')
            .attr('x', rootX)
            .attr('y', rootStartY + i * rootLineHeight)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.rootText)
            .attr('font-size', rootFont)
            .attr('font-weight', 'bold')
            .attr('data-text-for', 'tree-topic')
            .attr('data-node-id', 'tree-topic')
            .attr('data-node-type', 'topic')
            .attr('cursor', 'pointer')
            .attr('data-line-index', i)
            .text(line);
    });
    
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
        const { child, childText, branchFont, branchBox, leafFont, leafBoxes, maxLeafW, specIndex } = layout;
        const branchX = layout.branchX;
        
        // CRITICAL FIX: Use specIndex (original index in spec.children) for data-category-index
        // instead of branchIndex (loop index in filtered branchLayouts)
        // This ensures updateNode() can correctly find the child in spec.children
        const categoryDataIndex = specIndex;

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
            .attr('data-node-id', `tree-category-${categoryDataIndex}`)
            .attr('data-node-type', 'category')
            .attr('data-category-index', categoryDataIndex);

        // Render branch text - use multiple text elements (tspan doesn't render)
        const branchText = childText || '';
        const branchMaxWidth = branchBox.w * 0.9; // Max width based on box width
        const branchLineHeight = Math.round(branchFont * 1.2);
        
        // Use splitAndWrapText for automatic word wrapping
        const branchLines = (typeof window.splitAndWrapText === 'function')
            ? window.splitAndWrapText(branchText, branchFont, branchMaxWidth, measureLineWidthForWrap)
            : (branchText ? [branchText] : ['']);
        
        // Ensure at least one line for placeholder
        const finalBranchLines = branchLines.length > 0 ? branchLines : [''];
        
        // WORKAROUND: Use multiple text elements instead of tspan
        const branchStartY = branchY - (finalBranchLines.length - 1) * branchLineHeight / 2;
        finalBranchLines.forEach((line, i) => {
            svg.append('text')
                .attr('x', branchX)
                .attr('y', branchStartY + i * branchLineHeight)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', THEME.branchText)
                .attr('font-size', branchFont)
                .attr('data-text-for', `tree-category-${categoryDataIndex}`)
                .attr('data-node-id', `tree-category-${categoryDataIndex}`)
                .attr('data-node-type', 'category')
                .attr('cursor', 'pointer')
                .attr('data-line-index', i)
                .text(line);
        });

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
            // Note: j is the loop index through original child.children array,
            // which matches the index used in spec.children[categoryDataIndex].children[j]
            leaves.forEach((leaf, j) => {
                // Use nullish coalescing to properly handle empty strings
                let leafText;
                if (typeof leaf === 'string') {
                    leafText = leaf;
                } else if (leaf && typeof leaf === 'object') {
                    leafText = leaf.text ?? leaf.label ?? '';
                } else {
                    leafText = '';
                }
                const box = leafBoxes[j] || measureSvgTextBox(svg, leafText, leafFont, 12, 8);
                const leafY = centersY[j];
                // Width adaptive to characters for each node
                const rectW = box.w;
                
                // Use categoryDataIndex (specIndex) for data-category-index to ensure
                // correct mapping back to spec.children
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
                    .attr('data-node-id', `tree-leaf-${categoryDataIndex}-${j}`)
                    .attr('data-node-type', 'leaf')
                    .attr('data-category-index', categoryDataIndex)
                    .attr('data-leaf-index', j);

                // Render leaf text - use multiple text elements (tspan doesn't render)
                const leafTextContent = leafText || '';
                const leafMaxWidth = rectW * 0.9; // Max width based on box width
                const leafLineHeight = Math.round(leafFont * 1.2);
                
                // Use splitAndWrapText for automatic word wrapping
                const leafLines = (typeof window.splitAndWrapText === 'function')
                    ? window.splitAndWrapText(leafTextContent, leafFont, leafMaxWidth, measureLineWidthForWrap)
                    : (leafTextContent ? [leafTextContent] : ['']);
                
                // Ensure at least one line for placeholder
                const finalLeafLines = leafLines.length > 0 ? leafLines : [''];
                
                // WORKAROUND: Use multiple text elements instead of tspan
                const leafStartY = leafY - (finalLeafLines.length - 1) * leafLineHeight / 2;
                finalLeafLines.forEach((line, idx) => {
                    svg.append('text')
                        .attr('x', branchX)
                        .attr('y', leafStartY + idx * leafLineHeight)
                        .attr('text-anchor', 'middle')
                        .attr('dominant-baseline', 'middle')
                        .attr('fill', THEME.leafText)
                        .attr('font-size', leafFont)
                        .attr('data-text-for', `tree-leaf-${categoryDataIndex}-${j}`)
                        .attr('data-node-id', `tree-leaf-${categoryDataIndex}-${j}`)
                        .attr('data-node-type', 'leaf')
                        .attr('cursor', 'pointer')
                        .attr('data-line-index', idx)
                        .text(line);
                });
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
        
        // Calculate actual content bounds from branch layouts (adaptive to diagram width)
        let separatorLeftX, separatorRightX;
        if (branchLayouts.length > 0) {
            // Calculate leftmost and rightmost edges of actual content
            // Find the branch with minimum X (leftmost) and maximum X (rightmost)
            let leftmostBranch = branchLayouts[0];
            let rightmostBranch = branchLayouts[0];
            branchLayouts.forEach(layout => {
                if (layout.branchX < leftmostBranch.branchX) {
                    leftmostBranch = layout;
                }
                if (layout.branchX > rightmostBranch.branchX) {
                    rightmostBranch = layout;
                }
            });
            // Calculate edges: branch center ± half column width
            separatorLeftX = leftmostBranch.branchX - leftmostBranch.columnWidth / 2;
            separatorRightX = rightmostBranch.branchX + rightmostBranch.columnWidth / 2;
        } else {
            // Fallback: use padding to width - padding if no branches
            separatorLeftX = padding;
            separatorRightX = width - padding;
        }
        
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
    
    // Recalculate viewBox to tightly fit actual content and center it
    recalculateTightViewBox(svg, padding);
}

/**
 * Recalculate SVG viewBox to tightly fit actual content bounds.
 * Eliminates excessive white padding and ensures proper centering with xMidYMid meet.
 * 
 * @param {d3.Selection} svg - D3 selection of the SVG element
 * @param {number} padding - Desired padding around content (default: 40)
 */
function recalculateTightViewBox(svg, padding = 40) {
    try {
        const svgNode = svg.node();
        if (!svgNode) {
            logger.warn('TreeRenderer', 'SVG node not found for viewBox recalculation');
            return;
        }
        
        // Get bounding box of all rendered content
        const bbox = svgNode.getBBox();
        
        if (bbox.width <= 0 || bbox.height <= 0) {
            logger.warn('TreeRenderer', 'Invalid content bounds, skipping viewBox recalculation');
            return;
        }
        
        // Calculate new viewBox with padding on all sides
        const newX = bbox.x - padding;
        const newY = bbox.y - padding;
        const newWidth = bbox.width + (padding * 2);
        const newHeight = bbox.height + (padding * 2);
        
        // Update viewBox to tightly fit content - xMidYMid meet will center it
        svg.attr('viewBox', `${newX} ${newY} ${newWidth} ${newHeight}`)
           .attr('preserveAspectRatio', 'xMidYMid meet');
        
        logger.debug('TreeRenderer', 'ViewBox recalculated for proper centering:', {
            viewBox: `${Math.round(newX)} ${Math.round(newY)} ${Math.round(newWidth)} ${Math.round(newHeight)}`
        });
        
    } catch (error) {
        logger.error('TreeRenderer', 'Error recalculating viewBox:', error);
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
