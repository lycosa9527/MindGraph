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
    // Validate BEFORE clearing container - defensive programming
    // Use typeof check to allow empty string (for empty button functionality)
    if (!spec || typeof spec.topic !== 'string' || !Array.isArray(spec.children)) {
        logger.error('MindMapRenderer', 'Invalid spec for mindmap');
        return;
    }
    
    d3.select('#d3-container').html('');
    
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
        // Pass _node_dimensions for empty button dimension preservation
        renderMindMapWithLayout(spec._layout, svg, centerX, centerY, THEME, spec._node_dimensions);
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

// Helper function to calculate edge intersection point for a circle
function getCircleEdgePoint(centerX, centerY, radius, targetX, targetY) {
    const dx = targetX - centerX;
    const dy = targetY - centerY;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist === 0) return { x: centerX + radius, y: centerY };
    return {
        x: centerX + (dx / dist) * radius,
        y: centerY + (dy / dist) * radius
    };
}

// Helper function to calculate edge intersection point for a rectangle
function getRectangleEdgePoint(centerX, centerY, width, height, targetX, targetY) {
    const dx = targetX - centerX;
    const dy = targetY - centerY;
    const halfWidth = width / 2;
    const halfHeight = height / 2;
    
    // Calculate intersection with rectangle edge
    // Use the side that the line intersects first
    const slope = Math.abs(dy / dx);
    const rectSlope = halfHeight / halfWidth;
    
    let edgeX, edgeY;
    
    if (slope <= rectSlope) {
        // Intersects with left or right edge
        edgeX = dx > 0 ? centerX + halfWidth : centerX - halfWidth;
        edgeY = centerY + (dy / dx) * (edgeX - centerX);
    } else {
        // Intersects with top or bottom edge
        edgeY = dy > 0 ? centerY + halfHeight : centerY - halfHeight;
        edgeX = centerX + (dx / dy) * (edgeY - centerY);
    }
    
    return { x: edgeX, y: edgeY };
}

function renderMindMapWithLayout(spec, svg, centerX, centerY, THEME, preservedNodeDimensions = null) {
    const positions = spec.positions;
    const connections = spec.connections || [];
    
    // Check for preserved dimensions from empty button operation
    const preservedDims = preservedNodeDimensions || {};
    
    // Debug: Log connection count and positions
    logger.debug('MindMapRenderer', `Rendering ${connections.length} connections, ${Object.keys(positions).length} positions`);
    if (connections.length > 0) {
        const sampleConn = connections[0];
        logger.debug('MindMapRenderer', `Sample connection: from(${sampleConn.from?.x}, ${sampleConn.from?.y}) to(${sampleConn.to?.x}, ${sampleConn.to?.y})`);
    }
    
    // Create SVG groups for proper layering: connections behind, nodes in front
    // Remove existing groups if they exist (for re-rendering)
    svg.selectAll('g.connections-layer, g.nodes-layer').remove();
    
    // Create connections layer (will be behind nodes, but after background)
    // Insert after background rectangle to ensure it's visible in regular mode
    const backgroundRect = svg.select('rect.background');
    let connectionsLayer;
    if (!backgroundRect.empty()) {
        // Insert connections layer right after background rectangle
        const bgNode = backgroundRect.node();
        const newGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        newGroup.setAttribute('class', 'connections-layer');
        // Insert after background node
        bgNode.parentNode.insertBefore(newGroup, bgNode.nextSibling);
        connectionsLayer = d3.select(newGroup);
    } else {
        // No background, just append (will be first element)
        connectionsLayer = svg.append('g').attr('class', 'connections-layer');
    }
    
    // Create nodes layer (will be in front of connections)
    const nodesLayer = svg.append('g')
        .attr('class', 'nodes-layer');
    
    // Store node dimensions for connection calculations
    // Key: node position key (from positions object), Value: {type, centerX, centerY, radius/width/height}
    const nodeDimensions = new Map();
    
    // Draw nodes first and store their dimensions
    Object.values(positions).forEach(pos => {
        // Skip "Additional Aspect" branch and its children
        if (isAdditionalAspectNode(pos, positions)) {
            return; // Skip rendering this node
        }
        
        if (pos.node_type === 'topic') {
            // Central topic (circle)
            const topicX = centerX + pos.x;
            const topicY = centerY + pos.y;
            
            // Check if text is empty or whitespace - don't use placeholder text
            const topicTextRaw = pos.text || '';
            const topicText = topicTextRaw.trim();
            
            // Calculate adaptive radius based on actual text dimensions
            // Use empty string for radius calculation if text is empty, but maintain minimum radius
            // Check for preserved dimensions first (from empty button)
            let topicRadius;
            if (preservedDims.topic && preservedDims.topic.r && topicText === '') {
                // Use preserved radius for empty topic
                topicRadius = preservedDims.topic.r;
                logger.debug('MindMapRenderer', 'Using preserved topic radius', { topicRadius });
            } else if (typeof getTextRadius === 'function') {
                topicRadius = getTextRadius(topicText || '', THEME.fontTopic || '16px', 20);
            } else if (typeof window.MindGraphUtils !== 'undefined' && window.MindGraphUtils.getTextRadius) {
                topicRadius = window.MindGraphUtils.getTextRadius(topicText || '', THEME.fontTopic || '16px', 20);
            } else {
                // Fallback calculation - maintain minimum radius even for empty text
                topicRadius = topicText.length > 0 
                    ? Math.max(30, Math.min(60, topicText.length * 3))
                    : 30; // Minimum radius for empty topic
            }
            
            // Use white fill to hide connections behind nodes
            const finalFill = pos.fill || THEME.centralTopicFill || '#ffffff';
            const finalStroke = pos.stroke || THEME.centralTopicStroke || '#35506b';
            const finalTextColor = pos.text_color || THEME.centralTopicText || '#333333';
            
            // Store node dimensions for connection calculations
            const nodeKey = `${pos.x}_${pos.y}`;
            nodeDimensions.set(nodeKey, {
                type: 'circle',
                centerX: topicX,
                centerY: topicY,
                radius: topicRadius,
                nodeType: 'topic'
            });
            
            // Draw circular node in nodes layer
            nodesLayer.append('circle')
                .attr('cx', topicX)
                .attr('cy', topicY)
                .attr('r', topicRadius)
                .attr('fill', finalFill)
                .attr('stroke', finalStroke)
                .attr('stroke-width', pos.stroke_width || 3)
                .attr('opacity', 1)
                .attr('data-node-id', 'topic_center')
                .attr('data-node-type', 'topic');
            
            // Only render text if there's actual content
            if (topicText.length > 0) {
                const topicFontSize = parseFloat(THEME.fontTopic || '16px');
                const topicMaxWidth = topicRadius * 1.8; // Max width based on circle radius
                const topicLineHeight = Math.round(topicFontSize * 1.2);
                const measureLineWidth = createMeasureLineWidth();
                
                // Use splitAndWrapText for automatic word wrapping
                const topicLines = (typeof window.splitAndWrapText === 'function')
                    ? window.splitAndWrapText(topicText, topicFontSize, topicMaxWidth, measureLineWidth)
                    : [topicText];
                
                // WORKAROUND: Use multiple text elements instead of tspan
                const topicStartY = topicY - (topicLines.length - 1) * topicLineHeight / 2;
                topicLines.forEach((line, i) => {
                    nodesLayer.append('text')
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
            }
                
        } else if (pos.node_type === 'branch') {
            // Branch (rectangle)
            const branchX = centerX + pos.x;
            const branchY = centerY + pos.y;

            // Create measureLineWidth function FIRST for accurate text measurement
            const measureLineWidth = createMeasureLineWidth();
            
            // Check if text is empty or whitespace - don't use placeholder text
            const branchTextRaw = pos.text || '';
            const branchText = branchTextRaw.trim();
            const branchFontSize = parseFloat(THEME.fontBranch || '16px');
            const branchLineHeight = Math.round(branchFontSize * 1.2);
            const branchMaxTextWidth = 200; // Max width before wrapping
            
            // Split by newlines first, then wrap if needed
            const branchLines = branchText.length > 0
                ? ((typeof window.splitAndWrapText === 'function')
                    ? window.splitAndWrapText(branchText, branchFontSize, branchMaxTextWidth, measureLineWidth)
                    : branchText.split(/\n/))
                : [];
            const branchTextHeight = branchLines.length > 0 ? branchLines.length * branchLineHeight : 0;
            
            // Calculate width based on actual text measurement
            // Check for preserved dimensions first (from empty button)
            const branchNodeKey = `branch-${pos.branch_index}`;
            const branchPreserved = preservedDims[branchNodeKey];
            
            let branchWidth, branchHeight;
            if (branchPreserved && branchPreserved.w && branchPreserved.h && branchText === '') {
                // Use preserved dimensions for empty branch
                branchWidth = branchPreserved.w;
                branchHeight = branchPreserved.h;
                logger.debug('MindMapRenderer', 'Using preserved branch dimensions', { branchNodeKey, branchWidth, branchHeight });
            } else {
                // ALWAYS recalculate based on wrapped lines - ignore pos.width from Python
                // This ensures node width adapts correctly when text is edited
                const branchMeasuredWidth = branchLines.length > 0
                    ? Math.max(...branchLines.map(l => measureLineWidth(l, branchFontSize)), 20)
                    : 20;
                branchWidth = Math.max(100, branchMeasuredWidth + 24); // Min 100px, add 24px padding
                branchHeight = Math.max(50, branchTextHeight + 20);
            }
            
            // Use white fill to hide connections behind nodes
            const finalBranchFill = pos.fill || THEME.branchFill || '#ffffff';
            const finalBranchStroke = pos.stroke || THEME.branchStroke || '#4e79a7';
            const finalBranchTextColor = pos.text_color || THEME.branchText || '#333333';
            
            // Generate node ID for branch
            const branchNodeId = `branch_${pos.branch_index}`;
            
            // Store node dimensions for connection calculations
            const nodeKey = `${pos.x}_${pos.y}`;
            nodeDimensions.set(nodeKey, {
                type: 'rectangle',
                centerX: branchX,
                centerY: branchY,
                width: branchWidth,
                height: branchHeight,
                nodeType: 'branch'
            });
            
            // Draw rectangular node in nodes layer
            nodesLayer.append('rect')
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
            
            // Only render text if there's actual content
            if (branchLines.length > 0) {
                // WORKAROUND: Use multiple text elements instead of tspan
                const branchStartY = branchY - (branchLines.length - 1) * branchLineHeight / 2;
                branchLines.forEach((line, i) => {
                    nodesLayer.append('text')
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
            }
                
        } else if (pos.node_type === 'child') {
            // Child (rectangle)
            const childX = centerX + pos.x;
            const childY = centerY + pos.y;

            // Create measureLineWidth function FIRST for accurate text measurement
            const measureLineWidth = createMeasureLineWidth();
            
            // Check if text is empty or whitespace - don't use placeholder text
            const childTextRaw = pos.text || '';
            const childText = childTextRaw.trim();
            const childFontSize = parseFloat(THEME.fontChild || '14px');
            const childLineHeight = Math.round(childFontSize * 1.2);
            const childMaxTextWidth = 180; // Max width before wrapping
            
            // Split by newlines first, then wrap if needed
            const childLines = childText.length > 0
                ? ((typeof window.splitAndWrapText === 'function')
                    ? window.splitAndWrapText(childText, childFontSize, childMaxTextWidth, measureLineWidth)
                    : childText.split(/\n/))
                : [];
            const childTextHeight = childLines.length > 0 ? childLines.length * childLineHeight : 0;
            
            // Calculate width based on actual text measurement
            // Check for preserved dimensions first (from empty button)
            const childNodeKey = `child-${pos.branch_index}-${pos.child_index}`;
            const childPreserved = preservedDims[childNodeKey];
            
            let childWidth, childHeight;
            if (childPreserved && childPreserved.w && childPreserved.h && childText === '') {
                // Use preserved dimensions for empty child
                childWidth = childPreserved.w;
                childHeight = childPreserved.h;
                logger.debug('MindMapRenderer', 'Using preserved child dimensions', { childNodeKey, childWidth, childHeight });
            } else {
                // ALWAYS recalculate based on wrapped lines - ignore pos.width from Python
                // This ensures node width adapts correctly when text is edited
                const childMeasuredWidth = childLines.length > 0
                    ? Math.max(...childLines.map(l => measureLineWidth(l, childFontSize)), 20)
                    : 20;
                childWidth = Math.max(80, childMeasuredWidth + 20); // Min 80px, add 20px padding
                childHeight = Math.max(40, childTextHeight + 16);
            }
            
            // Use white fill to hide connections behind nodes
            const finalChildFill = pos.fill || THEME.childFill || '#ffffff';
            const finalChildStroke = pos.stroke || THEME.childStroke || '#6c757d';
            const finalChildTextColor = pos.text_color || THEME.childText || '#333333';
            
            // Generate node ID for child
            const childNodeId = `child_${pos.branch_index}_${pos.child_index}`;
            
            // Store node dimensions for connection calculations
            const nodeKey = `${pos.x}_${pos.y}`;
            nodeDimensions.set(nodeKey, {
                type: 'rectangle',
                centerX: childX,
                centerY: childY,
                width: childWidth,
                height: childHeight,
                nodeType: 'child'
            });
            
            // Draw rectangular node in nodes layer
            nodesLayer.append('rect')
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
            
            // Only render text if there's actual content
            if (childLines.length > 0) {
                // WORKAROUND: Use multiple text elements instead of tspan
                const childStartY = childY - (childLines.length - 1) * childLineHeight / 2;
                childLines.forEach((line, i) => {
                    nodesLayer.append('text')
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
        }
    });
    
    // Now render connections using edge-to-edge calculations
    // Helper function to find node dimensions by matching coordinates
    function findNodeDimensions(x, y) {
        const tolerance = 0.5; // Small tolerance for coordinate matching (in pixels)
        const nodeKey = `${x}_${y}`;
        
        // Try exact match first
        if (nodeDimensions.has(nodeKey)) {
            return nodeDimensions.get(nodeKey);
        }
        
        // Try to find closest match within tolerance
        let bestMatch = null;
        let minDistance = Infinity;
        
        for (const [key, dims] of nodeDimensions.entries()) {
            const keyParts = key.split('_');
            const keyX = parseFloat(keyParts[0]);
            const keyY = parseFloat(keyParts[1]);
            
            // Calculate distance from connection point to node center
            const distance = Math.sqrt((keyX - x) * (keyX - x) + (keyY - y) * (keyY - y));
            
            if (distance < tolerance && distance < minDistance) {
                bestMatch = dims;
                minDistance = distance;
            }
        }
        
        return bestMatch;
    }
    
    // Render connections with edge-to-edge calculations
    connections.forEach(conn => {
        // Handle the actual connection format from Python agent
        // Connections have from: {x, y, type} and to: {x, y, type} format
        if (conn.from && conn.to && typeof conn.from === 'object' && typeof conn.to === 'object') {
            // Skip connections related to "Additional Aspect" branch
            if (isAdditionalAspectConnection(conn, positions)) {
                return; // Skip rendering this connection
            }
            
            const fromCenterX = centerX + conn.from.x;
            const fromCenterY = centerY + conn.from.y;
            const toCenterX = centerX + conn.to.x;
            const toCenterY = centerY + conn.to.y;
            
            // Find node dimensions for both endpoints
            const fromDims = findNodeDimensions(conn.from.x, conn.from.y);
            const toDims = findNodeDimensions(conn.to.x, conn.to.y);
            
            let fromX, fromY, toX, toY;
            
            if (fromDims) {
                // Calculate edge point for source node
                if (fromDims.type === 'circle') {
                    const edgePoint = getCircleEdgePoint(
                        fromDims.centerX, fromDims.centerY, fromDims.radius,
                        toCenterX, toCenterY
                    );
                    fromX = edgePoint.x;
                    fromY = edgePoint.y;
                } else if (fromDims.type === 'rectangle') {
                    const edgePoint = getRectangleEdgePoint(
                        fromDims.centerX, fromDims.centerY, fromDims.width, fromDims.height,
                        toCenterX, toCenterY
                    );
                    fromX = edgePoint.x;
                    fromY = edgePoint.y;
                } else {
                    // Fallback to center
                    fromX = fromCenterX;
                    fromY = fromCenterY;
                }
            } else {
                // Fallback to center if dimensions not found
                fromX = fromCenterX;
                fromY = fromCenterY;
            }
            
            if (toDims) {
                // Calculate edge point for target node
                if (toDims.type === 'circle') {
                    const edgePoint = getCircleEdgePoint(
                        toDims.centerX, toDims.centerY, toDims.radius,
                        fromCenterX, fromCenterY
                    );
                    toX = edgePoint.x;
                    toY = edgePoint.y;
                } else if (toDims.type === 'rectangle') {
                    const edgePoint = getRectangleEdgePoint(
                        toDims.centerX, toDims.centerY, toDims.width, toDims.height,
                        fromCenterX, fromCenterY
                    );
                    toX = edgePoint.x;
                    toY = edgePoint.y;
                } else {
                    // Fallback to center
                    toX = toCenterX;
                    toY = toCenterY;
                }
            } else {
                // Fallback to center if dimensions not found
                toX = toCenterX;
                toY = toCenterY;
            }
            
            // Draw connection line in connections layer (edge-to-edge)
            connectionsLayer.append('line')
                .attr('x1', fromX)
                .attr('y1', fromY)
                .attr('x2', toX)
                .attr('y2', toY)
                .attr('stroke', conn.stroke_color || THEME?.connectionColor || '#666')
                .attr('stroke-width', conn.stroke_width || THEME?.connectionWidth || 2)
                .attr('opacity', 0.7)
                .attr('class', 'connection-line');
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
