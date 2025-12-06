/**
 * Mind Map Renderer for MindGraph
 * 
 * This module provides standard mind map rendering using Python agent layout data.
 * - Always requires positioned layout from Python MindMapAgent
 * - Shows error message if Python agent fails (no fallback rendering)
 * 
 * Requires: shared-utilities.js, style-manager.js
 * Performance Impact: Loads only ~50KB instead of full 213KB
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

// Check if shared utilities are available
if (typeof window.MindGraphUtils === 'undefined') {
    logger.error('MindMapRenderer', 'MindGraphUtils not found. Please load shared-utilities.js first.');
}

// Note: getTextRadius and addWatermark are available globally from shared-utilities.js

// Helper for text measurement (for splitAndWrapText compatibility)
function createMeasureLineWidth() {
    // Create a temporary SVG for text measurement
    let measureSvg = d3.select('#mind-map-measure-svg');
    if (measureSvg.empty()) {
        measureSvg = d3.select('body').append('svg')
            .attr('id', 'mind-map-measure-svg')
            .style('position', 'absolute')
            .style('visibility', 'hidden')
            .style('pointer-events', 'none');
    }
    
    return function(text, fontSize) {
        const t = measureSvg.append('text')
            .attr('font-size', fontSize)
            .text(text || '');
        const width = t.node().getBBox().width;
        t.remove();
        return width;
    };
}

function renderMindMap(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    if (!spec || !spec.topic || !Array.isArray(spec.children)) {
        logger.error('MindMapRenderer', 'Invalid spec for mindmap');
        return;
    }
    
    // Determine canvas dimensions - use adaptive dimensions if provided
    let baseWidth, baseHeight, padding;
    
    if (spec._recommended_dimensions) {
        // Adaptive dimensions from template (calculated based on window size)
        baseWidth = spec._recommended_dimensions.width;
        baseHeight = spec._recommended_dimensions.height;
        padding = spec._recommended_dimensions.padding;
        logger.info('MindMapRenderer', 'Using adaptive dimensions:', { baseWidth, baseHeight, padding });
    } else if (dimensions) {
        // Provided dimensions (fallback)
        baseWidth = dimensions.width || dimensions.baseWidth || 700;
        baseHeight = dimensions.height || dimensions.baseHeight || 500;
        padding = dimensions.padding || 40;
    } else {
        // Default dimensions
        baseWidth = 700;
        baseHeight = 500;
        padding = 40;
    }
    
    // Load theme from style manager
    let THEME;
    try {
        if (typeof styleManager !== 'undefined' && styleManager.getTheme) {
            THEME = styleManager.getTheme('mindmap', null, null);
        } else {
            throw new Error('Style manager not available for mindmap rendering');
        }
    } catch (error) {
        logger.error('MindMapRenderer', 'Failed to load theme:', error);
        throw new Error('Failed to load theme from style manager');
    }
    
    // Apply container background - use THEME object that was loaded above
    const containerBackground = spec._layout?.params?.background || THEME?.background || '#f5f5f5';
    
    d3.select('#d3-container')
        .style('background-color', containerBackground, 'important')
        .style('width', '100%')
        .style('height', '100%')
        .style('min-height', `${baseHeight}px`);
    
    const width = baseWidth;
    const height = baseHeight;
    var svg = d3.select('#d3-container').append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `0 0 ${width} ${height}`)
        .attr('preserveAspectRatio', 'xMidYMid meet')
        .style('background-color', containerBackground, 'important');
    
    // Add background rectangle to cover entire SVG area (ensures consistent background in PNG exports)
    svg.append('rect')
        .attr('class', 'background')
        .attr('x', 0)
        .attr('y', 0)
        .attr('width', width)
        .attr('height', height)
        .attr('fill', containerBackground)
        .attr('stroke', 'none');
    
    // Require Python agent layout data
    const centerX = width / 2;
    const centerY = height / 2;
    
    if (spec._layout && spec._layout.positions) {
        // Render with positioned layout
        renderMindMapWithLayout(spec._layout, svg, centerX, centerY, THEME);
    } else {
        // Error: No layout data
        logger.error('MindMapRenderer', 'Mindmap rendering failed: No layout data from Python agent');
        return;
    }
    
    // Apply learning sheet text knockout if needed
    if (spec.is_learning_sheet && spec.hidden_node_percentage > 0) {
        knockoutTextForLearningSheet(svg, spec.hidden_node_percentage);
    }
}

function renderMindMapWithLayout(spec, svg, centerX, centerY, THEME) {
    const positions = spec.positions;
    const connections = spec.connections || [];
    
    // Draw connections first (so they appear behind nodes)
    connections.forEach(conn => {
        // Handle the actual connection format from Python agent
        // Connections have from: {x, y, type} and to: {x, y, type} format
        if (conn.from && conn.to && typeof conn.from === 'object' && typeof conn.to === 'object') {
            // Skip connections related to "Additional Aspect" branch
            if (isAdditionalAspectConnection(conn, positions)) {
                return; // Skip rendering this connection
            }
            
            const fromX = centerX + conn.from.x;
            const fromY = centerY + conn.from.y;
            const toX = centerX + conn.to.x;
            const toY = centerY + conn.to.y;
            
            // Draw connection line
            svg.append('line')
                .attr('x1', fromX)
                .attr('y1', fromY)
                .attr('x2', toX)
                .attr('y2', toY)
                .attr('stroke', conn.stroke_color || THEME?.connectionColor || '#666')
                .attr('stroke-width', conn.stroke_width || THEME?.connectionWidth || 2)
                .attr('opacity', 0.7);
        }
    });
    
    // Draw nodes
    Object.values(positions).forEach(pos => {
        // Skip "Additional Aspect" branch and its children
        if (isAdditionalAspectNode(pos, positions)) {
            return; // Skip rendering this node
        }
        
        if (pos.node_type === 'topic') {
            // Central topic (circle)
            const topicX = centerX + pos.x;
            const topicY = centerY + pos.y;
            
            const topicWidth = pos.width || 120;
            const topicHeight = pos.height || 60;
            
            // Calculate adaptive radius based on actual text dimensions
            let topicRadius;
            if (typeof getTextRadius === 'function') {
                topicRadius = getTextRadius(pos.text || 'Topic', THEME.fontTopic || '16px', 20);
            } else if (typeof window.MindGraphUtils !== 'undefined' && window.MindGraphUtils.getTextRadius) {
                topicRadius = window.MindGraphUtils.getTextRadius(pos.text || 'Topic', THEME.fontTopic || '16px', 20);
            } else {
                // Fallback calculation
                topicRadius = Math.max(30, Math.min(60, (pos.text || 'Topic').length * 3));
            }
            
            const finalFill = pos.fill || THEME.centralTopicFill || '#e3f2fd';
            const finalStroke = pos.stroke || THEME.centralTopicStroke || '#35506b';
            const finalTextColor = pos.text_color || THEME.centralTopicText || '#333333';
            
            // Draw circular node
            svg.append('circle')
                .attr('cx', topicX)
                .attr('cy', topicY)
                .attr('r', topicRadius)
                .attr('fill', finalFill)
                .attr('stroke', finalStroke)
                .attr('stroke-width', pos.stroke_width || 3)
                .attr('opacity', 1)
                .attr('data-node-id', 'topic_center')
                .attr('data-node-type', 'topic');
            
            // Render topic text - use multiple text elements (tspan doesn't render)
            const topicText = pos.text || 'Topic';
            const topicFontSize = parseFloat(THEME.fontTopic || '16px');
            const topicMaxWidth = topicRadius * 1.8; // Max width based on circle radius
            const topicLineHeight = Math.round(topicFontSize * 1.2);
            const measureLineWidth = createMeasureLineWidth();
            
            // Use splitAndWrapText for automatic word wrapping
            const topicLines = (typeof window.splitAndWrapText === 'function')
                ? window.splitAndWrapText(topicText, topicFontSize, topicMaxWidth, measureLineWidth)
                : (topicText ? [topicText] : ['']);
            
            // Ensure at least one line for placeholder
            const finalTopicLines = topicLines.length > 0 ? topicLines : [''];
            
            // WORKAROUND: Use multiple text elements instead of tspan
            const topicStartY = topicY - (finalTopicLines.length - 1) * topicLineHeight / 2;
            finalTopicLines.forEach((line, i) => {
                svg.append('text')
                    .attr('x', topicX)
                    .attr('y', topicStartY + i * topicLineHeight)
                    .attr('text-anchor', 'middle')
                    .attr('dominant-baseline', 'middle')
                    .attr('fill', finalTextColor)
                    .attr('font-size', THEME.fontTopic || '16px')
                    .attr('font-weight', 'bold')
                    .attr('data-text-for', 'topic_center')
                    .attr('data-node-id', 'topic_center')
                    .attr('data-node-type', 'topic')
                    .attr('data-line-index', i)
                    .text(line);
            });
                
        } else if (pos.node_type === 'branch') {
            // Branch (rectangle)
            const branchX = centerX + pos.x;
            const branchY = centerY + pos.y;

            // Create measureLineWidth function FIRST for accurate text measurement
            const measureLineWidth = createMeasureLineWidth();
            
            // Calculate adaptive width and height for multi-line text
            const branchText = pos.text || 'Branch';
            const branchFontSize = parseFloat(THEME.fontBranch || '16px');
            const branchLineHeight = Math.round(branchFontSize * 1.2);
            const branchMaxTextWidth = 200; // Max width before wrapping
            
            // Split by newlines first, then wrap if needed
            const branchLines = (typeof window.splitAndWrapText === 'function')
                ? window.splitAndWrapText(branchText, branchFontSize, branchMaxTextWidth, measureLineWidth)
                : branchText.split(/\n/);
            const branchTextHeight = branchLines.length * branchLineHeight;
            
            // Calculate width based on actual text measurement
            const branchMeasuredWidth = Math.max(...branchLines.map(l => measureLineWidth(l, branchFontSize)), 20);
            const branchWidth = pos.width || Math.max(100, branchMeasuredWidth + 24); // Min 100px, add 24px padding
            const branchHeight = pos.height || Math.max(50, branchTextHeight + 20);
            
            const finalBranchFill = pos.fill || THEME.branchFill || '#e3f2fd';
            const finalBranchStroke = pos.stroke || THEME.branchStroke || '#4e79a7';
            const finalBranchTextColor = pos.text_color || THEME.branchText || '#333333';
            
            // Generate node ID for branch
            const branchNodeId = `branch_${pos.branch_index}`;
            
            // Draw rectangular node
            svg.append('rect')
                .attr('x', branchX - branchWidth / 2)
                .attr('y', branchY - branchHeight / 2)
                .attr('width', branchWidth)
                .attr('height', branchHeight)
                .attr('rx', 8)
                .attr('ry', 8)
                .attr('fill', finalBranchFill)
                .attr('stroke', finalBranchStroke)
                .attr('stroke-width', pos.stroke_width || THEME.branchStrokeWidth || 2)
                .attr('opacity', 1)
                .attr('data-node-id', branchNodeId)
                .attr('data-node-type', 'branch')
                .attr('data-branch-index', pos.branch_index)
                .attr('data-array-index', pos.branch_index);
            
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
                    .attr('fill', finalBranchTextColor)
                    .attr('font-size', THEME.fontBranch || '16px')
                    .attr('data-text-for', branchNodeId)
                    .attr('data-node-id', branchNodeId)
                    .attr('data-node-type', 'branch')
                    .attr('data-line-index', i)
                    .text(line);
            });
                
        } else if (pos.node_type === 'child') {
            // Child (rectangle)
            const childX = centerX + pos.x;
            const childY = centerY + pos.y;

            // Create measureLineWidth function FIRST for accurate text measurement
            const measureLineWidth = createMeasureLineWidth();
            
            // Calculate adaptive width and height for multi-line text
            const childText = pos.text || 'Child';
            const childFontSize = parseFloat(THEME.fontChild || '14px');
            const childLineHeight = Math.round(childFontSize * 1.2);
            const childMaxTextWidth = 180; // Max width before wrapping
            
            // Split by newlines first, then wrap if needed
            const childLines = (typeof window.splitAndWrapText === 'function')
                ? window.splitAndWrapText(childText, childFontSize, childMaxTextWidth, measureLineWidth)
                : childText.split(/\n/);
            const childTextHeight = childLines.length * childLineHeight;
            
            // Calculate width based on actual text measurement
            const childMeasuredWidth = Math.max(...childLines.map(l => measureLineWidth(l, childFontSize)), 20);
            const childWidth = pos.width || Math.max(80, childMeasuredWidth + 20); // Min 80px, add 20px padding
            const childHeight = pos.height || Math.max(40, childTextHeight + 16);
            
            const finalChildFill = pos.fill || THEME.childFill || '#f8f9fa';
            const finalChildStroke = pos.stroke || THEME.childStroke || '#6c757d';
            const finalChildTextColor = pos.text_color || THEME.childText || '#333333';
            
            // Generate node ID for child
            const childNodeId = `child_${pos.branch_index}_${pos.child_index}`;
            
            // Draw rectangular node
            svg.append('rect')
                .attr('x', childX - childWidth / 2)
                .attr('y', childY - childHeight / 2)
                .attr('width', childWidth)
                .attr('height', childHeight)
                .attr('rx', 6)
                .attr('ry', 6)
                .attr('fill', finalChildFill)
                .attr('stroke', finalChildStroke)
                .attr('stroke-width', pos.stroke_width || 2)
                .attr('opacity', 1)
                .attr('data-node-id', childNodeId)
                .attr('data-node-type', 'child')
                .attr('data-branch-index', pos.branch_index)
                .attr('data-child-index', pos.child_index)
                .attr('data-array-index', pos.child_index);
            
            // Ensure at least one line for placeholder
            const finalChildLines = childLines.length > 0 ? childLines : [''];
            
            // WORKAROUND: Use multiple text elements instead of tspan
            const childStartY = childY - (finalChildLines.length - 1) * childLineHeight / 2;
            finalChildLines.forEach((line, i) => {
                svg.append('text')
                    .attr('x', childX)
                    .attr('y', childStartY + i * childLineHeight)
                    .attr('text-anchor', 'middle')
                    .attr('dominant-baseline', 'middle')
                    .attr('fill', finalChildTextColor)
                    .attr('font-size', THEME.fontChild || '14px')
                    .attr('data-text-for', childNodeId)
                    .attr('data-node-id', childNodeId)
                    .attr('data-node-type', 'child')
                    .attr('data-branch-index', pos.branch_index)
                    .attr('data-child-index', pos.child_index)
                    .attr('data-line-index', i)
                    .text(line);
            });
        }
    });
}

// Helper function to check if a node is part of the "Additional Aspect" branch
function isAdditionalAspectNode(pos, positions) {
    // Check if the node text contains "Additional Aspect"
    if (pos.text && pos.text.includes('Additional Aspect')) {
        return true;
    }
    
    // Check if it's a child of the Additional Aspect branch
    if (pos.node_type === 'child' && pos.branch_index !== undefined) {
        // Find the parent branch and check if it's Additional Aspect
        const branchKey = `branch_${pos.branch_index}`;
        const parentBranch = positions[branchKey];
        if (parentBranch && parentBranch.text && parentBranch.text.includes('Additional Aspect')) {
            return true;
        }
    }
    
    return false;
}

// Helper function to check if a connection involves the "Additional Aspect" branch
function isAdditionalAspectConnection(conn, positions) {
    // Find the node at the connection endpoints
    const tolerance = 0.1; // Small tolerance for coordinate comparison
    
    for (const [nodeId, nodePos] of Object.entries(positions)) {
        // Check if connection 'from' point matches this node's position
        if (Math.abs(conn.from.x - nodePos.x) < tolerance && Math.abs(conn.from.y - nodePos.y) < tolerance) {
            if (nodePos.text && nodePos.text.includes('Additional Aspect')) {
                return true;
            }
        }
        
        // Check if connection 'to' point matches this node's position
        if (Math.abs(conn.to.x - nodePos.x) < tolerance && Math.abs(conn.to.y - nodePos.y) < tolerance) {
            if (nodePos.text && nodePos.text.includes('Additional Aspect')) {
                return true;
            }
            
            // Also check if this is a child of Additional Aspect branch by checking its parent
            if (nodePos.node_type === 'child' && nodePos.branch_index !== undefined) {
                // Find the parent branch
                const branchKey = `branch_${nodePos.branch_index}`;
                const parentBranch = positions[branchKey];
                if (parentBranch && parentBranch.text && parentBranch.text.includes('Additional Aspect')) {
                    return true;
                }
            }
        }
    }
    
    return false;
}

// Export functions for module system
if (typeof window !== 'undefined') {
    // Browser environment - attach to window
    window.MindMapRenderer = {
        renderMindMap,
        renderMindMapWithLayout
    };
} else if (typeof module !== 'undefined' && module.exports) {
    // Node.js environment
    module.exports = {
        renderMindMap,
        renderMindMapWithLayout
    };
}
