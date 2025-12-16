/**
 * Bubble Map Renderer for MindGraph
 * 
 * This module contains the bubble map, double bubble map, and circle map rendering functions.
 * Requires: shared-utilities.js, style-manager.js
 * 
 * Performance Impact: Loads only ~50KB instead of full 213KB
 * 
 * Last Updated: 2024-12-19 - Fixed adaptive sizing for double bubble maps
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
    logger.error('BubbleMapRenderer', 'MindGraphUtils not found. Please load shared-utilities.js first');
}

// Note: getTextRadius and addWatermark are available globally from shared-utilities.js

function renderBubbleMap(spec, theme = null, dimensions = null) {
    // VERBOSE LOGGING: Template receiving spec
    console.log('[BubbleMap-Renderer] 🚀 RENDER FUNCTION CALLED - NEW CODE VERSION');
    
    // CRITICAL: Set default boundaries IMMEDIATELY at function start
    // This ensures boundaries are ALWAYS available, even if render fails
    // Use safe defaults that will be updated once we calculate proper values
    const defaultCenterX = 350;
    const defaultCenterY = 250;
    const defaultTopicR = 30;
    const defaultNodeR = 31;
    const defaultTargetDistance = defaultTopicR + defaultNodeR + 50;
    const defaultMargin = defaultNodeR * 0.2;
    
    window.bubbleMapBoundaries = {
        centerX: defaultCenterX,
        centerY: defaultCenterY,
        innerRadius: defaultTopicR + defaultNodeR + 20,
        outerRadius: defaultTargetDistance + defaultNodeR + defaultMargin
    };
    
    console.log('[BubbleMap-Renderer] 🔵 DEFAULT boundaries set at function start:', {
        centerX: defaultCenterX,
        centerY: defaultCenterY,
        innerRadius: window.bubbleMapBoundaries.innerRadius,
        outerRadius: window.bubbleMapBoundaries.outerRadius,
        stored: !!window.bubbleMapBoundaries
    });
    
    logger.info('[BubbleMap-Renderer] ========================================');
    logger.info('[BubbleMap-Renderer] RECEIVING SPEC FOR RENDERING');
    logger.info('[BubbleMap-Renderer] ========================================');
    logger.info('[BubbleMap-Renderer] Spec validation:', {
        hasSpec: !!spec,
        hasTopic: !!spec?.topic,
        hasAttributes: Array.isArray(spec?.attributes),
        attributeCount: spec?.attributes?.length || 0,
        attributeType: typeof spec?.attributes
    });
    
    if (spec?.attributes) {
        logger.info('[BubbleMap-Renderer] Adjective nodes received:');
        spec.attributes.forEach((item, idx) => {
            logger.info(`  [${idx}] Type: ${typeof item} | Value: ${typeof item === 'object' ? JSON.stringify(item) : item}`);
        });
    }
    
    // Validate BEFORE clearing container - defensive programming
    // Use typeof check to allow empty string (for empty button functionality)
    if (!spec || typeof spec.topic !== 'string' || !Array.isArray(spec.attributes)) {
        logger.error('[BubbleMap-Renderer]', 'Invalid spec for bubble_map');
        // Even if spec is invalid, try to set default boundaries to prevent drag errors
        if (window.bubbleMapSimulation && window.bubbleMapCentralNode) {
            const centerX = window.bubbleMapCentralNode.x || 350;
            const centerY = window.bubbleMapCentralNode.y || 250;
            const topicR = window.bubbleMapCentralNode.radius || 30;
            const uniformAttributeR = 31;
            const targetDistance = topicR + uniformAttributeR + 50;
            const margin = uniformAttributeR * 0.2;
            window.bubbleMapBoundaries = {
                centerX: centerX,
                centerY: centerY,
                innerRadius: topicR + uniformAttributeR + 20,
                outerRadius: targetDistance + uniformAttributeR + margin
            };
            console.log('[BubbleMap-Renderer] ⚠️ Invalid spec - set fallback boundaries');
        }
        return;
    }
    
    d3.select('#d3-container').html('');
    
    // Helper function to measure text width for wrapping
    function getMeasurementContainer() {
        let container = d3.select('#measurement-container');
        if (container.empty()) {
            container = d3.select('body').append('div')
                .attr('id', 'measurement-container')
                .style('position', 'absolute')
                .style('visibility', 'hidden')
                .style('pointer-events', 'none');
        }
        return container;
    }
    
    function measureLineWidth(text, fontSize) {
        const container = getMeasurementContainer();
        const t = container.append('svg').append('text').attr('font-size', fontSize).text(text);
        const w = t.node().getBBox().width;
        t.remove();
        return w;
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
        baseWidth = dimensions.width || dimensions.baseWidth || 700;
        baseHeight = dimensions.height || dimensions.baseHeight || 500;
        padding = dimensions.padding || 40;
    } else {
        // Default dimensions
        baseWidth = 700;
        baseHeight = 500;
        padding = 40;
    }
    
    // Load theme from style manager - FIXED: No more hardcoded overrides
    let THEME;
    try {
        if (typeof styleManager !== 'undefined' && styleManager.getTheme) {
            THEME = styleManager.getTheme('bubble_map', theme, theme);
        } else {
            logger.error('BubbleMapRenderer', 'Style manager not available');
            throw new Error('Style manager not available for bubble map rendering');
        }
    } catch (error) {
        logger.error('BubbleMapRenderer', 'Error getting theme from style manager', error);
        throw new Error('Failed to load theme from style manager');
    }
    
    // Apply background to container and store for SVG
    const backgroundColor = theme?.background || THEME.background || '#f5f5f5';
    d3.select('#d3-container').style('background-color', backgroundColor);
    
    // Ensure container has no padding/margin that could cause white space
    d3.select('#d3-container').style('padding', '0').style('margin', '0');
    
    // Calculate sizes
    // Check for preserved dimensions first
    const nodeDimensions = spec._node_dimensions || {};
    
    // Topic radius - use preserved if available
    let topicR;
    if (nodeDimensions.topic && nodeDimensions.topic.r) {
        topicR = nodeDimensions.topic.r;
    } else {
        topicR = getTextRadius(spec.topic, THEME.fontTopic, 20);
    }
    
    // Calculate uniform radius for all attribute nodes
    // Handle both string and object attributes (t can be "text" or {text: "text"})
    // Use preserved dimensions if available, otherwise calculate
    const attributeRadii = spec.attributes.map((t, idx) => {
        const textStr = typeof t === 'object' ? (t.text || '') : (t || '');
        const nodeKey = `attribute-${idx}`;
        const preservedDims = nodeDimensions[nodeKey];
        
        if (preservedDims && preservedDims.r) {
            return preservedDims.r;
        } else if (preservedDims && preservedDims.w && preservedDims.h) {
            // Convert width/height to radius (use average)
            return Math.max(preservedDims.w, preservedDims.h) / 2;
        } else {
            return getTextRadius(textStr, THEME.fontAttribute, 10);
        }
    });
    const uniformAttributeR = Math.max(...attributeRadii, 30);
    
    logger.info(`[BubbleMap-Renderer] Rendering ${spec.attributes.length} adjective nodes with uniform radius: ${uniformAttributeR}px`); // Use the largest required radius for all
    
    // Calculate layout with collision detection
    const centerX = baseWidth / 2;
    let centerY = baseHeight / 2;
    
    // Calculate even distribution around the topic
    const targetDistance = topicR + uniformAttributeR + 50; // Distance from center
    
    // Inner radius: prevent nodes from overlapping central topic (donut hole)
    const innerRadius = topicR + uniformAttributeR + 20; // Minimum distance from center
    
    // CRITICAL: Set boundaries IMMEDIATELY after calculating layout parameters
    // This ensures boundaries are available even if render fails or returns early
    const margin = uniformAttributeR * 0.2; // 20% of bubble radius as margin
    const fixedOuterRadius = targetDistance + uniformAttributeR + margin; // Fixed at initial layout size
    const fixedInnerRadius = innerRadius; // Same as innerRadius
    
    window.bubbleMapBoundaries = {
        centerX: centerX,
        centerY: centerY,
        innerRadius: fixedInnerRadius,
        outerRadius: fixedOuterRadius
    };
    
    console.log('[BubbleMap-Renderer] 🔵 EARLY boundaries set (before node creation):', {
        centerX: Math.round(centerX),
        centerY: Math.round(centerY),
        innerRadius: Math.round(fixedInnerRadius),
        outerRadius: Math.round(fixedOuterRadius),
        stored: !!window.bubbleMapBoundaries
    });
    
    // Check for custom positions
    const customPositions = spec._customPositions || {};
    const hasCustomPositions = Object.keys(customPositions).length > 0;
    
    // Position attribute nodes around the central topic
    // If custom positions exist but some nodes don't have positions (new nodes added),
    // recalculate all positions evenly to maintain proper spacing
    const nodeCount = spec.attributes.length;
    
    // Count how many nodes have custom positions by checking each index
    // Use explicit property check to avoid false positives
    let nodesWithCustomPositions = 0;
    const missingPositionIndices = [];
    const positionCheckDetails = [];
    if (hasCustomPositions) {
        for (let i = 0; i < nodeCount; i++) {
            const nodeId = `attribute_${i}`;
            const hasPosition = customPositions.hasOwnProperty(nodeId) && customPositions[nodeId] !== null && customPositions[nodeId] !== undefined;
            positionCheckDetails.push({ index: i, nodeId, hasPosition, value: customPositions[nodeId] });
            if (hasPosition) {
                nodesWithCustomPositions++;
            } else {
                missingPositionIndices.push(i);
            }
        }
    }
    
    const hasNewNodesWithoutPositions = hasCustomPositions && nodesWithCustomPositions < nodeCount;
    
    // If new nodes were added (some nodes don't have custom positions), recalculate all evenly
    const shouldRecalculateEvenly = hasNewNodesWithoutPositions;
    
    // Debug logging to verify detection - ALWAYS log this (use console.log for visibility)
    const detectionInfo = {
        hasCustomPositions,
        nodeCount,
        nodesWithCustomPositions,
        missingPositionIndices,
        hasNewNodesWithoutPositions,
        shouldRecalculateEvenly,
        customPositionKeys: hasCustomPositions ? Object.keys(customPositions).filter(k => k.startsWith('attribute_')).sort() : [],
        checkResult: hasCustomPositions ? `${nodesWithCustomPositions} < ${nodeCount} = ${nodesWithCustomPositions < nodeCount}` : 'no custom positions',
        positionChecks: hasCustomPositions && nodeCount <= 15 ? positionCheckDetails : 'too many to show'
    };
    logger.info('[BubbleMap-Renderer] Position detection check', detectionInfo);
    console.log('[BubbleMap-Renderer] 🔍 Position detection check:', detectionInfo);
    
    if (shouldRecalculateEvenly) {
        logger.info('[BubbleMap-Renderer] ✓ New nodes detected without custom positions - recalculating all positions evenly', {
            totalNodes: nodeCount,
            nodesWithCustomPositions,
            nodesWithoutPositions: nodeCount - nodesWithCustomPositions,
            customPositionKeys: Object.keys(customPositions).filter(k => k.startsWith('attribute_'))
        });
        console.log('[BubbleMap-Renderer] ✅ RECALCULATING ALL POSITIONS EVENLY');
    } else if (hasCustomPositions) {
        logger.debug('[BubbleMap-Renderer] All nodes have custom positions, using them', {
            totalNodes: nodeCount,
            nodesWithCustomPositions,
            customPositionKeys: Object.keys(customPositions).filter(k => k.startsWith('attribute_'))
        });
        console.log('[BubbleMap-Renderer] ⚠️ All nodes have custom positions - NOT recalculating', {
            nodesWithCustomPositions,
            nodeCount
        });
    }
    
    // Create nodes for force simulation with uniform radius
    const nodes = spec.attributes.map((attr, i) => {
        const nodeId = `attribute_${i}`;
        
        // Check if custom position exists and we're not recalculating
        let targetX, targetY;
        if (hasCustomPositions && customPositions[nodeId] && !shouldRecalculateEvenly) {
            // Use custom position (only if not recalculating)
            // IMPORTANT: Use exact custom position - this is where the node was dragged to
            targetX = customPositions[nodeId].x;
            targetY = customPositions[nodeId].y;
            logger.debug(`[BubbleMap-Renderer] Using custom position for ${nodeId}`, {
                nodeId,
                x: Math.round(targetX),
                y: Math.round(targetY)
            });
        } else {
            // Calculate even angle distribution around the circle
            const angle = (i * 360 / nodeCount) - 90; // -90 to start from top
            targetX = centerX + targetDistance * Math.cos(angle * Math.PI / 180);
            targetY = centerY + targetDistance * Math.sin(angle * Math.PI / 180);
            
            if (shouldRecalculateEvenly) {
                logger.debug(`[BubbleMap-Renderer] Recalculating position for ${nodeId} (even spacing)`, {
                    nodeId,
                    angle: Math.round(angle),
                    x: Math.round(targetX),
                    y: Math.round(targetY)
                });
            }
        }
        
        // Handle both string and object attributes (attr can be "text" or {text: "text"})
        const attrText = typeof attr === 'object' ? (attr.text || '') : (attr || '');
        
        return {
            id: i,
            nodeId: nodeId, // Store nodeId for drag operations
            text: attrText,
            radius: uniformAttributeR, // All nodes use the same radius
            targetX: targetX,
            targetY: targetY,
            x: targetX, // Start at target position (custom position or calculated)
            y: targetY  // This will be used for constraint ring calculation
        };
    });
    
    // Add central topic as a fixed node
    const centralNode = {
        id: 'central',
        text: spec.topic,
        radius: topicR,
        x: centerX,
        y: centerY,
        fx: centerX, // Fixed position
        fy: centerY
    };
    
    // Create force simulation with target positioning
    const simulation = d3.forceSimulation([centralNode, ...nodes])
        .force('charge', d3.forceManyBody().strength(-800))
        .force('collide', d3.forceCollide().radius(d => d.radius + 5))
        .force('center', d3.forceCenter(centerX, centerY))
        .force('target', function() {
            nodes.forEach(node => {
                // Only apply target force if node is not being dragged (no fx/fy)
                if (node.targetX !== undefined && node.targetY !== undefined && node.fx === undefined && node.fy === undefined) {
                    const dx = node.targetX - node.x;
                    const dy = node.targetY - node.y;
                    node.vx += dx * 0.1; // Pull towards target position
                    node.vy += dy * 0.1;
                }
            });
        })
        .stop();
    
    // Boundaries are already set earlier (right after layout calculation)
    // Just verify they're still there before simulation runs
    if (!window.bubbleMapBoundaries) {
        console.error('[BubbleMap-Renderer] ❌ Boundaries missing before simulation! Re-setting...');
        const margin = uniformAttributeR * 0.2;
        const fixedOuterRadius = targetDistance + uniformAttributeR + margin;
        window.bubbleMapBoundaries = {
            centerX: centerX,
            centerY: centerY,
            innerRadius: innerRadius,
            outerRadius: fixedOuterRadius
        };
    }
    
    console.log('[BubbleMap-Renderer] ✅ Boundaries verified before simulation:', {
        centerX: Math.round(window.bubbleMapBoundaries.centerX),
        centerY: Math.round(window.bubbleMapBoundaries.centerY),
        innerRadius: Math.round(window.bubbleMapBoundaries.innerRadius),
        outerRadius: Math.round(window.bubbleMapBoundaries.outerRadius)
    });
    
    // Store simulation reference globally for drag operations
    window.bubbleMapSimulation = simulation;
    window.bubbleMapNodes = nodes;
    window.bubbleMapCentralNode = centralNode;
    
    // Run simulation to find optimal positions
    // If recalculating evenly, run simulation to settle positions
    // If custom positions exist and NOT recalculating, skip simulation (use exact positions)
    if (shouldRecalculateEvenly || !hasCustomPositions) {
        for (let i = 0; i < 300; ++i) simulation.tick();
    }
    
    // If we recalculated evenly (new nodes added), update custom positions silently
    // This ensures positions are saved for future renders without triggering re-render loop
    // Must happen AFTER simulation runs so positions are final
    if (shouldRecalculateEvenly) {
        console.log('[BubbleMap-Renderer] 🔄 UPDATING CUSTOM POSITIONS - Recalculated evenly for', nodeCount, 'nodes');
        if (!spec._customPositions) {
            spec._customPositions = {};
        }
        // Clear old custom positions and save new evenly-spaced positions
        Object.keys(spec._customPositions).forEach(key => {
            if (key.startsWith('attribute_')) {
                delete spec._customPositions[key];
            }
        });
        
        // Save all recalculated positions (after simulation has run and settled)
        nodes.forEach(node => {
            spec._customPositions[node.nodeId] = { x: node.x, y: node.y };
        });
        
        logger.info('[BubbleMap-Renderer] Updated custom positions with evenly-spaced layout', {
            updatedPositions: nodes.length
        });
        console.log('[BubbleMap-Renderer] ✅ Custom positions updated:', Object.keys(spec._customPositions).filter(k => k.startsWith('attribute_')).sort());
    } else {
        console.log('[BubbleMap-Renderer] ⏭️ SKIPPING recalculation - shouldRecalculateEvenly =', shouldRecalculateEvenly);
    }
    
    // Calculate bounds for SVG
    const positions = nodes.map(n => ({ x: n.x, y: n.y, radius: n.radius }));
    positions.push({ x: centerX, y: centerY, radius: topicR });
    
    const minX = Math.min(...positions.map(p => p.x - p.radius)) - padding;
    const maxX = Math.max(...positions.map(p => p.x + p.radius)) + padding;
    const minY = Math.min(...positions.map(p => p.y - p.radius)) - padding;
    const maxY = Math.max(...positions.map(p => p.y + p.radius)) + padding;
    const width = maxX - minX;
    const height = maxY - minY;
    
    const svg = d3.select('#d3-container').append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `${minX} ${minY} ${width} ${height}`)
        .attr('preserveAspectRatio', 'xMidYMid meet');
    
    // Add background rectangle to cover entire SVG area
    svg.append('rect')
        .attr('class', 'background')
        .attr('x', minX)
        .attr('y', minY)
        .attr('width', width)
        .attr('height', height)
        .attr('fill', backgroundColor)
        .attr('stroke', 'none');
    
    // Debug: Log the calculated dimensions
    
    // Draw connecting lines from topic to attributes
    nodes.forEach(node => {
        const nodeId = node.nodeId || `attribute_${node.id}`;
        const dx = node.x - centerX;
        const dy = node.y - centerY;
        const dist = Math.sqrt(dx * dx + dy * dy);
        
        if (dist > 0) {
            const lineStartX = centerX + (dx / dist) * topicR;
            const lineStartY = centerY + (dy / dist) * topicR;
            const lineEndX = node.x - (dx / dist) * node.radius;
            const lineEndY = node.y - (dy / dist) * node.radius;
            
            svg.append('line')
                .attr('x1', lineStartX)
                .attr('y1', lineStartY)
                .attr('x2', lineEndX)
                .attr('y2', lineEndY)
                .attr('stroke', '#888')
                .attr('stroke-width', 2)
                .attr('data-line-for', nodeId);
        }
    });
    
    // Draw topic circle (center)
    svg.append('circle')
        .attr('cx', centerX)
        .attr('cy', centerY)
        .attr('r', topicR)
        .attr('fill', THEME.topicFill)
        .attr('stroke', THEME.topicStroke)
        .attr('stroke-width', THEME.topicStrokeWidth)
        .attr('data-node-id', 'topic_center')
        .attr('data-node-type', 'topic');
    
    // Render topic text with automatic wrapping and tspan (always use tspan)
    const topicText = spec.topic || '';
    const topicMaxWidth = topicR * 1.8; // Max width based on circle radius
    const topicLines = (typeof window.splitAndWrapText === 'function')
        ? window.splitAndWrapText(topicText, THEME.fontTopic, topicMaxWidth, measureLineWidth)
        : (topicText ? topicText.split(/\n/) : ['']);
    const finalTopicLines = topicLines.length > 0 ? topicLines : [''];
    const topicLineHeight = Math.round(THEME.fontTopic * 1.2);
    
    // WORKAROUND: Use multiple text elements instead of tspan (tspan doesn't render)
    const topicStartY = centerY - (finalTopicLines.length - 1) * topicLineHeight / 2;
    finalTopicLines.forEach((line, i) => {
        svg.append('text')
            .attr('x', centerX)
            .attr('y', topicStartY + i * topicLineHeight)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.topicText)
            .attr('font-size', THEME.fontTopic)
            .attr('font-weight', 'bold')
            .attr('data-text-for', 'topic_center')
            .attr('data-node-id', 'topic_center')
            .attr('data-node-type', 'topic')
            .attr('data-line-index', i)
            .text(line);
    });
    
    // Draw attribute circles
    nodes.forEach(node => {
        svg.append('circle')
            .attr('cx', node.x)
            .attr('cy', node.y)
            .attr('r', node.radius)
            .attr('fill', THEME.attributeFill)
            .attr('stroke', THEME.attributeStroke)
            .attr('stroke-width', THEME.attributeStrokeWidth)
            .attr('data-node-id', `attribute_${node.id}`)
            .attr('data-node-type', 'attribute')
            .attr('data-array-index', node.id);
        
        // Render attribute text - use multiple text elements (tspan doesn't render)
        const attrText = node.text || '';
        const attrMaxWidth = node.radius * 1.8; // Max width based on circle radius
        const attrLines = (typeof window.splitAndWrapText === 'function')
            ? window.splitAndWrapText(attrText, THEME.fontAttribute, attrMaxWidth, measureLineWidth)
            : (attrText ? attrText.split(/\n/) : ['']);
        const finalAttrLines = attrLines.length > 0 ? attrLines : [''];
        const attrLineHeight = Math.round(THEME.fontAttribute * 1.2);
        
        // WORKAROUND: Use multiple text elements instead of tspan
        const attrStartY = node.y - (finalAttrLines.length - 1) * attrLineHeight / 2;
        finalAttrLines.forEach((line, i) => {
            svg.append('text')
                .attr('x', node.x)
                .attr('y', attrStartY + i * attrLineHeight)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', THEME.attributeText)
                .attr('font-size', THEME.fontAttribute)
                .attr('data-text-for', `attribute_${node.id}`)
                .attr('data-node-id', `attribute_${node.id}`)
                .attr('data-node-type', 'attribute')
                .attr('data-line-index', i)
                .text(line);
        });
    });
    
    // Apply learning sheet text knockout if needed
    if (spec.is_learning_sheet && spec.hidden_node_percentage > 0) {
        knockoutTextForLearningSheet(svg, spec.hidden_node_percentage);
    }
    
    // 🆕 FIX: Recalculate tight viewBox based on actual rendered content
    // This eliminates excessive white padding especially when nodes are added from Node Palette
    recalculateTightViewBox(svg, padding);
    
    logger.info('[BubbleMap-Renderer] ========================================');
    logger.info(`[BubbleMap-Renderer] ✓ RENDERING COMPLETE: ${spec.attributes.length} adjective nodes displayed`);
    logger.info('[BubbleMap-Renderer] ========================================');
}

/**
 * Recalculate SVG viewBox to tightly fit actual content bounds.
 * Eliminates excessive white padding by measuring actual rendered elements.
 * 
 * @param {d3.Selection} svg - D3 selection of the SVG element
 * @param {number} padding - Desired padding around content (default: 40)
 */
function recalculateTightViewBox(svg, padding = 40) {
    try {
        const svgNode = svg.node();
        if (!svgNode) {
            logger.warn('[recalculateTightViewBox] SVG node not found');
            return;
        }
        
        // Get bounding box of all rendered content
        const bbox = svgNode.getBBox();
        
        logger.debug('[recalculateTightViewBox] Content bounds:', {
            x: Math.round(bbox.x),
            y: Math.round(bbox.y),
            width: Math.round(bbox.width),
            height: Math.round(bbox.height)
        });
        
        // Calculate new viewBox with padding
        const newX = bbox.x - padding;
        const newY = bbox.y - padding;
        const newWidth = bbox.width + (padding * 2);
        const newHeight = bbox.height + (padding * 2);
        
        // Update viewBox and dimensions
        svg.attr('viewBox', `${newX} ${newY} ${newWidth} ${newHeight}`)
           .attr('width', newWidth)
           .attr('height', newHeight);
        
        logger.info('[recalculateTightViewBox] ✓ ViewBox recalculated:', {
            viewBox: `${Math.round(newX)} ${Math.round(newY)} ${Math.round(newWidth)} ${Math.round(newHeight)}`,
            reduction: `${Math.round((1 - (newWidth * newHeight) / (parseFloat(svgNode.getAttribute('width')) * parseFloat(svgNode.getAttribute('height')))) * 100)}% smaller`
        });
        
    } catch (error) {
        logger.error('[recalculateTightViewBox] Error:', error);
    }
}

function renderCircleMap(spec, theme = null, dimensions = null) {
    // Helper functions for text measurement
    function getMeasurementContainer() {
        let container = d3.select('#measurement-container');
        if (container.empty()) {
            container = d3.select('body').append('div')
                .attr('id', 'measurement-container')
                .style('position', 'absolute')
                .style('visibility', 'hidden')
                .style('pointer-events', 'none');
        }
        return container;
    }
    
    function measureLineWidth(text, fontSize) {
        const container = getMeasurementContainer();
        const t = container.append('svg').append('text').attr('font-size', fontSize).text(text);
        const w = t.node().getBBox().width;
        t.remove();
        return w;
    }
    
    // VERBOSE LOGGING: Template receiving spec
    logger.info('[CircleMap-Renderer] ========================================');
    logger.info('[CircleMap-Renderer] RECEIVING SPEC FOR RENDERING');
    logger.info('[CircleMap-Renderer] ========================================');
    logger.info('[CircleMap-Renderer] Spec validation:', {
        hasSpec: !!spec,
        hasTopic: !!spec?.topic,
        hasContext: Array.isArray(spec?.context),
        contextCount: spec?.context?.length || 0,
        contextType: typeof spec?.context
    });
    
    if (spec?.context) {
        logger.info('[CircleMap-Renderer] Context nodes received:');
        spec.context.forEach((item, idx) => {
            logger.info(`  [${idx}] Type: ${typeof item} | Value: ${typeof item === 'object' ? JSON.stringify(item) : item}`);
        });
    }
    
    // Validate BEFORE clearing container - defensive programming
    // Circle map supports topic as string OR object {text: "..."} - allow both
    // Use typeof check to allow empty string (for empty button functionality)
    const topicValid = typeof spec?.topic === 'string' || (typeof spec?.topic === 'object' && spec?.topic !== null);
    if (!spec || !topicValid || !Array.isArray(spec.context)) {
        logger.error('[CircleMap-Renderer] Invalid spec for circle_map');
        return;
    }
    
    d3.select('#d3-container').html('');
    
    // Use adaptive dimensions if provided, otherwise use fallback dimensions
    let baseWidth, baseHeight, padding;
    
    if (spec._recommended_dimensions) {
        // Adaptive dimensions from template (calculated based on window size)
        baseWidth = spec._recommended_dimensions.width;
        baseHeight = spec._recommended_dimensions.height;
        padding = spec._recommended_dimensions.padding;
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
    
    // Apply background to container for consistency with other maps
    const backgroundColor = theme?.background || '#f5f5f5';
    d3.select('#d3-container').style('background-color', backgroundColor);
    
    const THEME = {
        outerCircleFill: 'none',
        outerCircleStroke: '#666666',
        outerCircleStrokeWidth: 2,
        topicFill: '#1976d2',
        topicText: '#fff',
        topicStroke: '#0d47a1',
        topicStrokeWidth: 3,
        contextFill: '#e3f2fd',
        contextText: '#333',
        contextStroke: '#1976d2',
        contextStrokeWidth: 2,
        fontTopic: 20,
        fontContext: 14,
        ...theme
    };
    
    // Check for preserved dimensions from empty button operation
    const nodeDimensions = spec._node_dimensions || {};
    
    // Calculate uniform radius for all context nodes - use preserved dimensions if available
    const contextRadii = spec.context.map((t, idx) => {
        // Handle both string and object context items (t can be "text" or {text: "text"})
        const textStr = typeof t === 'object' ? (t.text || '') : (t || '');
        const nodeKey = `context-${idx}`;
        const preservedDims = nodeDimensions[nodeKey];
        
        let radius;
        if (preservedDims && preservedDims.r && textStr === '') {
            // Use preserved radius for empty node
            radius = preservedDims.r;
            logger.debug('CircleMapRenderer', 'Using preserved context radius', { idx, radius });
        } else {
            // Calculate from text
            radius = getTextRadius(textStr, THEME.fontContext, 10);
        }
        return { index: idx, text: textStr, radius };
    });
    const uniformContextR = Math.max(...contextRadii.map(n => n.radius), 30); // Use the largest required radius for all
    
    // Find which node(s) determined the uniform radius
    const largestNodes = contextRadii.filter(n => n.radius === uniformContextR);
    
    logger.info(`[CircleMap-Renderer] Rendering ${spec.context.length} context nodes with uniform radius: ${uniformContextR}px`);
    console.log('[CircleMap-Renderer] 📏 Node sizing:', {
        totalNodes: spec.context.length,
        uniformRadius: Math.round(uniformContextR),
        largestNode: largestNodes.length > 0 ? {
            index: largestNodes[0].index,
            text: largestNodes[0].text.substring(0, 30) + (largestNodes[0].text.length > 30 ? '...' : ''),
            radius: Math.round(largestNodes[0].radius)
        } : 'N/A',
        allRadii: contextRadii.map(n => Math.round(n.radius))
    });
    
    // Calculate topic circle size (made smaller like original)
    // Handle both string and object topic (spec.topic can be "text" or {text: "text"})
    const topicForRadius = typeof spec.topic === 'object' ? (spec.topic.text || '') : (spec.topic || '');
    
    let topicR;
    if (nodeDimensions.topic && nodeDimensions.topic.r && topicForRadius === '') {
        // Use preserved radius for empty topic
        topicR = nodeDimensions.topic.r;
        logger.debug('CircleMapRenderer', 'Using preserved topic radius', { topicR });
    } else {
        // Calculate from text
        const topicTextRadius = getTextRadius(topicForRadius, THEME.fontTopic, 15);
        topicR = Math.max(topicTextRadius + 15, 45); // Smaller topic circle at center
    }
    
    // Calculate layout
    const centerX = baseWidth / 2;
    const centerY = baseHeight / 2;
    
    // Calculate optimal radius for children nodes (aim for ~half radius from center)
    // TWO CONSTRAINTS must be satisfied:
    
    // 1. RADIAL CONSTRAINT: Minimum distance from center for nodes
    //    Target: topicR + 0.5×topicR (half radius gap) + context node radius
    //    This keeps nodes close to center while preventing overlap with center node
    const targetRadialDistance = topicR + (topicR * 0.5) + uniformContextR + 5; // Reduced safety margin from 10px to 5px
    
    // 2. CIRCUMFERENTIAL CONSTRAINT: Nodes must not overlap around the perimeter
    //    Arc length between adjacent node centers must be >= spacingMultiplier × nodeRadius
    //    Formula: (2π × radius) / nodeCount >= spacingMultiplier × nodeRadius
    //    Solving for minimum radius: radius >= (spacingMultiplier × nodeRadius × nodeCount) / (2π)
    //    
    //    Dynamic spacing based on node count:
    //      - Few nodes (≤3): minimum spacing (nodes touching)
    //      - Medium nodes (4-6): tight spacing (5% gap)
    //      - Many nodes (7+): comfortable spacing (10% gap)
    let spacingMultiplier;
    if (spec.context.length <= 3) {
        spacingMultiplier = 2.0;  // Minimum - nodes just touching
    } else if (spec.context.length <= 6) {
        spacingMultiplier = 2.05; // Tight - 5% gap
    } else {
        spacingMultiplier = 2.1;  // Comfortable - 10% gap
    }
    
    // CORRECTED FORMULA: Divide by 2π (not just π) - this was causing nodes to be 2× too far apart!
    const circumferentialMinRadius = (uniformContextR * spec.context.length * spacingMultiplier) / (2 * Math.PI);
    
    // Use the LARGER of both constraints to ensure no overlap
    // This ensures nodes are as close as possible while preventing overlaps
    const childrenRadius = Math.max(targetRadialDistance, circumferentialMinRadius, 100); // Reduced minimum from 120px to 100px
    
    // Outer circle is children nodes + their radius + margin (for visual outer ring)
    const outerCircleR = childrenRadius + uniformContextR + 10; // Reduced margin from 15px to 10px
    
    // Log detailed calculation for debugging
    const calculationDetails = {
        nodeCount: spec.context.length,
        uniformContextR: Math.round(uniformContextR),
        topicR: Math.round(topicR),
        targetRadialDistance: Math.round(targetRadialDistance),
        circumferentialMinRadius: Math.round(circumferentialMinRadius),
        childrenRadius: Math.round(childrenRadius),
        finalOuterR: Math.round(outerCircleR),
        constraintUsed: childrenRadius === circumferentialMinRadius ? 'circumferential' : 'radial',
        spacingMultiplier: spacingMultiplier,
        formula: circumferentialMinRadius > targetRadialDistance 
            ? `(${Math.round(uniformContextR)} × ${spec.context.length} × ${spacingMultiplier}) / (2π) = ${Math.round(circumferentialMinRadius)}`
            : `topicR(${Math.round(topicR)}) + 0.5×topicR(${Math.round(topicR * 0.5)}) + nodeR(${Math.round(uniformContextR)}) = ${Math.round(targetRadialDistance)}`,
        distanceFromCenter: Math.round(childrenRadius),
        gapFromCenter: Math.round(childrenRadius - topicR)
    };
    logger.info('[CircleMap-Renderer] Node positioning calculation:', calculationDetails);
    console.log('[CircleMap-Renderer] 🔵 CIRCLE MAP LAYOUT:', calculationDetails);
    
    // Check for custom positions
    // CRITICAL: This code MUST run for circle maps - verify we're in the right function
    console.log('[CircleMap-Renderer] 🔵 ENTERING CUSTOM POSITIONS CHECK - renderCircleMap function');
    const customPositions = spec._customPositions || {};
    const hasCustomPositions = Object.keys(customPositions).length > 0;
    console.log('[CircleMap-Renderer] 🔵 Custom positions check:', {
        hasCustomPositions,
        customPositionsCount: Object.keys(customPositions).length,
        nodeCount: spec.context.length,
        specHasCustomPositions: !!spec._customPositions
    });
    
    const customPositionsRead = Object.keys(customPositions).reduce((acc, key) => {
        acc[key] = {
            x: Math.round(customPositions[key].x),
            y: Math.round(customPositions[key].y)
        };
        return acc;
    }, {});
    
    const customPositionsList = Object.keys(customPositions).sort().map(key => ({
        nodeId: key,
        x: Math.round(customPositions[key].x),
        y: Math.round(customPositions[key].y)
    }));
    
    // Position context circles at calculated radius from center (closer to center, ~half radius gap)
    // If custom positions exist but some nodes don't have positions (new nodes added),
    // recalculate all positions evenly to maintain proper spacing
    const nodeCount = spec.context.length;
    
    // ALWAYS log this - use console.log to ensure visibility
    console.log('[CircleMap-Renderer] 📖 Reading custom positions:', {
        hasCustomPositions,
        customPositionsCount: Object.keys(customPositions).length,
        nodeCount,
        customPositionKeys: Object.keys(customPositions).filter(k => k.startsWith('context_')).sort(),
        positions: customPositionsList.map(p => `${p.nodeId}: (${p.x}, ${p.y})`).join(', ')
    });
    logger.info('[CircleMap-Renderer] Reading custom positions from spec._customPositions', {
        hasCustomPositions,
        customPositionsCount: Object.keys(customPositions).length,
        nodeCount,
        positions: customPositionsList.map(p => `${p.nodeId}: (${p.x}, ${p.y})`).join(', ')
    });
    customPositionsList.forEach(pos => {
        logger.info('[CircleMap-Renderer]', `  Reading: ${pos.nodeId}`, { x: pos.x, y: pos.y });
    });
    
    // Count how many nodes have custom positions by checking each index
    // Use explicit property check to avoid false positives
    let nodesWithCustomPositions = 0;
    const missingPositionIndices = [];
    const positionCheckDetails = [];
    if (hasCustomPositions) {
        for (let i = 0; i < nodeCount; i++) {
            const nodeId = `context_${i}`;
            const hasPosition = customPositions.hasOwnProperty(nodeId) && customPositions[nodeId] !== null && customPositions[nodeId] !== undefined;
            positionCheckDetails.push({ index: i, nodeId, hasPosition, value: customPositions[nodeId] });
            if (hasPosition) {
                nodesWithCustomPositions++;
            } else {
                missingPositionIndices.push(i);
            }
        }
    }
    
    const hasNewNodesWithoutPositions = hasCustomPositions && nodesWithCustomPositions < nodeCount;
    
    // If new nodes were added (some nodes don't have custom positions), recalculate all evenly
    const shouldRecalculateEvenly = hasNewNodesWithoutPositions;
    
    // Debug logging to verify detection - ALWAYS log this (use console.log for visibility)
    const detectionInfo = {
        hasCustomPositions,
        nodeCount,
        nodesWithCustomPositions,
        missingPositionIndices,
        hasNewNodesWithoutPositions,
        shouldRecalculateEvenly,
        customPositionKeys: hasCustomPositions ? Object.keys(customPositions).filter(k => k.startsWith('context_')).sort() : [],
        checkResult: hasCustomPositions ? `${nodesWithCustomPositions} < ${nodeCount} = ${nodesWithCustomPositions < nodeCount}` : 'no custom positions',
        positionChecks: hasCustomPositions && nodeCount <= 15 ? positionCheckDetails : 'too many to show'
    };
    logger.info('[CircleMap-Renderer] Position detection check', detectionInfo);
    console.log('[CircleMap-Renderer] 🔍 Position detection check:', detectionInfo);
    
    if (shouldRecalculateEvenly) {
        logger.info('[CircleMap-Renderer] ✓ New nodes detected without custom positions - recalculating all positions evenly', {
            totalNodes: nodeCount,
            nodesWithCustomPositions,
            nodesWithoutPositions: nodeCount - nodesWithCustomPositions,
            customPositionKeys: Object.keys(customPositions).filter(k => k.startsWith('context_'))
        });
        console.log('[CircleMap-Renderer] ✅ RECALCULATING ALL POSITIONS EVENLY');
    } else if (hasCustomPositions) {
        logger.debug('[CircleMap-Renderer] All nodes have custom positions, using them', {
            totalNodes: nodeCount,
            nodesWithCustomPositions,
            customPositionKeys: Object.keys(customPositions).filter(k => k.startsWith('context_'))
        });
        console.log('[CircleMap-Renderer] ⚠️ All nodes have custom positions - NOT recalculating', {
            nodesWithCustomPositions,
            nodeCount
        });
    }
    
    const nodes = spec.context.map((ctx, i) => {
        const nodeId = `context_${i}`;
        
        // Check if custom position exists and we're not recalculating
        let targetX, targetY;
        if (hasCustomPositions && customPositions[nodeId] && !shouldRecalculateEvenly) {
            // Use custom position (only if not recalculating)
            targetX = customPositions[nodeId].x;
            targetY = customPositions[nodeId].y;
            logger.debug(`[CircleMap-Renderer] Using custom position for ${nodeId}`, {
                nodeId,
                x: Math.round(targetX),
                y: Math.round(targetY)
            });
        } else {
            // Calculate even angle distribution around the circle
            const angle = (i * 360 / nodeCount) - 90; // -90 to start from top
            // Position at childrenRadius from center (this ensures ~half radius gap when possible)
            targetX = centerX + childrenRadius * Math.cos(angle * Math.PI / 180);
            targetY = centerY + childrenRadius * Math.sin(angle * Math.PI / 180);
            
            if (shouldRecalculateEvenly) {
                logger.debug(`[CircleMap-Renderer] Recalculating position for ${nodeId} (even spacing)`, {
                    nodeId,
                    angle: Math.round(angle),
                    x: Math.round(targetX),
                    y: Math.round(targetY)
                });
            }
        }
        
        // Handle both string and object context items (ctx can be "text" or {text: "text"})
        const contextItemText = typeof ctx === 'object' ? (ctx.text || '') : (ctx || '');
        
        return {
            id: i,
            nodeId: nodeId, // Store nodeId for drag operations
            text: contextItemText,
            radius: uniformContextR,
            targetX: targetX,
            targetY: targetY,
            x: targetX, // Start at target position
            y: targetY
        };
    });
    
    // If we recalculated evenly (new nodes added), update custom positions silently
    // This ensures positions are saved for future renders without triggering re-render loop
    if (shouldRecalculateEvenly) {
        console.log('[CircleMap-Renderer] 🔄 UPDATING CUSTOM POSITIONS - Recalculated evenly for', nodeCount, 'nodes');
        if (!spec._customPositions) {
            spec._customPositions = {};
        }
        // Clear old custom positions and save new evenly-spaced positions
        Object.keys(spec._customPositions).forEach(key => {
            if (key.startsWith('context_')) {
                delete spec._customPositions[key];
            }
        });
        
        // Save all recalculated positions
        nodes.forEach(node => {
            spec._customPositions[node.nodeId] = { x: node.x, y: node.y };
        });
        
        logger.info('[CircleMap-Renderer] Updated custom positions with evenly-spaced layout', {
            updatedPositions: nodes.length
        });
        console.log('[CircleMap-Renderer] ✅ Custom positions updated:', Object.keys(spec._customPositions).filter(k => k.startsWith('context_')).sort());
    } else {
        console.log('[CircleMap-Renderer] ⏭️ SKIPPING recalculation - shouldRecalculateEvenly =', shouldRecalculateEvenly);
    }
    
    logger.info('[CircleMap-Renderer] Node positioning calculated:');
    nodes.forEach((node, idx) => {
        logger.info(`  [${idx}] "${node.text}" at (${Math.round(node.x)}, ${Math.round(node.y)})`);
    });
    
    // Calculate bounds for SVG (outer circle + padding)
    // Ensure the canvas is large enough to fit the calculated outer circle
    const requiredDimension = (outerCircleR + padding) * 2;
    const actualWidth = Math.max(baseWidth, requiredDimension);
    const actualHeight = Math.max(baseHeight, requiredDimension);
    
    // Recalculate center if canvas was expanded
    const actualCenterX = actualWidth / 2;
    const actualCenterY = actualHeight / 2;
    
    // Update node positions with actual center
    // If using custom positions, they're already in SVG coordinates, so use them directly
    // If not using custom positions, adjust for actual center
    if (!hasCustomPositions) {
        nodes.forEach(node => {
            const dx = node.x - centerX;
            const dy = node.y - centerY;
            node.x = actualCenterX + dx;
            node.y = actualCenterY + dy;
            // Update target positions too
            node.targetX = actualCenterX + (node.targetX - centerX);
            node.targetY = actualCenterY + (node.targetY - centerY);
        });
    } else {
        // For custom positions, they're already in SVG coordinates from previous render
        // Use them directly - they should match the current SVG coordinate system
        nodes.forEach(node => {
            // Positions already set from custom positions - use as-is
            // Update targetX/targetY to match so force simulation doesn't pull them away
            node.targetX = node.x;
            node.targetY = node.y;
        });
    }
    
    // Add central topic as a fixed node for force simulation
    const centralNode = {
        id: 'central',
        text: typeof spec.topic === 'object' ? (spec.topic.text || '') : (spec.topic || ''),
        radius: topicR,
        x: actualCenterX,
        y: actualCenterY,
        fx: actualCenterX, // Fixed position
        fy: actualCenterY
    };
    
    // Create force simulation for drag operations
    // Always enable forces for "marbles in a donut" effect - nodes adapt dynamically
    // Inner radius: central topic radius + margin (donut hole)
    // Outer radius: outerCircleR (donut edge)
    const innerRadius = topicR + uniformContextR + 5; // Inner boundary (donut hole edge)
    const outerRadius = outerCircleR - uniformContextR - 5; // Outer boundary (donut edge)
    
    console.log('[CircleMap-Renderer] 🔵 ABOUT TO CREATE SIMULATION:', {
        hasNodes: !!nodes,
        nodeCount: nodes?.length || 0,
        hasCentralNode: !!centralNode,
        innerRadius,
        outerRadius
    });
    
    try {
        const simulation = d3.forceSimulation([centralNode, ...nodes])
            .force('charge', d3.forceManyBody().strength(-800))
            .force('collide', d3.forceCollide().radius(d => d.radius + 8).strength(0.9))
            .force('center', d3.forceCenter(actualCenterX, actualCenterY))
            .force('donutBoundary', function() {
                // Constrain nodes to stay within the donut ring (between inner and outer radius)
                nodes.forEach(node => {
                    const dx = node.x - actualCenterX;
                    const dy = node.y - actualCenterY;
                    const distance = Math.sqrt(dx * dx + dy * dy);
                    
                    if (distance > 0) {
                        // Constrain to outer boundary
                        if (distance > outerRadius) {
                            const scale = outerRadius / distance;
                            node.x = actualCenterX + dx * scale;
                            node.y = actualCenterY + dy * scale;
                            // Dampen velocity when hitting boundary
                            node.vx *= 0.3;
                            node.vy *= 0.3;
                        }
                        
                        // Constrain to inner boundary (push away from center if too close)
                        if (distance < innerRadius) {
                            const scale = innerRadius / distance;
                            node.x = actualCenterX + dx * scale;
                            node.y = actualCenterY + dy * scale;
                            // Push away from center
                            const pushStrength = (innerRadius - distance) * 0.1;
                            node.vx += (dx / distance) * pushStrength;
                            node.vy += (dy / distance) * pushStrength;
                        }
                    }
                });
            })
            .force('target', function() {
                // Apply target force to pull nodes towards their initial positions
                // But only if they're not being dragged (no fx/fy)
                // When custom positions exist, use stronger force to lock positions
                nodes.forEach(node => {
                    if (node.targetX !== undefined && node.targetY !== undefined && node.fx === undefined && node.fy === undefined) {
                        const dx = node.targetX - node.x;
                        const dy = node.targetY - node.y;
                        // Use stronger target force when custom positions exist to preserve exact positions
                        const strength = hasCustomPositions ? 0.5 : 0.1;
                        node.vx += dx * strength;
                        node.vy += dy * strength;
                    }
                });
            })
            .stop();
        
        // Store simulation reference globally for drag operations
        // Also store boundary info for drag constraints
        console.log('[CircleMap-Renderer] 🔵 STORING SIMULATION:', {
            hasSimulation: !!simulation,
            hasNodes: !!nodes,
            nodeCount: nodes?.length || 0,
            nodeIds: nodes?.map(n => n.nodeId) || []
        });
        
        window.circleMapSimulation = simulation;
        window.circleMapNodes = nodes;
        window.circleMapCentralNode = centralNode;
        window.circleMapBoundaries = {
            centerX: actualCenterX,
            centerY: actualCenterY,
            innerRadius: innerRadius,
            outerRadius: outerRadius
        };
        
        console.log('[CircleMap-Renderer] 🔵 SIMULATION STORED IN WINDOW:', {
            hasSimulation: !!window.circleMapSimulation,
            hasNodes: !!window.circleMapNodes,
            nodeCount: window.circleMapNodes?.length || 0,
            nodeIds: window.circleMapNodes?.map(n => n.nodeId) || []
        });
        
        logger.info('[CircleMap-Renderer] Simulation stored globally', {
            hasSimulation: !!window.circleMapSimulation,
            hasNodes: !!window.circleMapNodes,
            nodeCount: window.circleMapNodes?.length || 0,
            nodeIds: window.circleMapNodes?.map(n => n.nodeId) || []
        });
    } catch (error) {
        console.error('[CircleMap-Renderer] ❌ ERROR creating/storing simulation:', error);
        logger.error('[CircleMap-Renderer]', 'Error creating/storing simulation', error);
        // If simulation creation failed, we can't continue - return early
        return;
    }
    
    // Run simulation to find optimal positions
    // Always run simulation to resolve overlaps, even with custom positions
    // Custom positions are used as starting points, then simulation resolves collisions
    if (window.circleMapSimulation) {
        // Set nodes to their target positions (custom or calculated)
        nodes.forEach(node => {
            node.x = node.targetX;
            node.y = node.targetY;
        });
        
        if (hasCustomPositions) {
            // Custom positions exist - preserve user's exact placement
            // Do NOT run simulation - use saved positions directly
            // The "marbles" effect only happens during drag, not on re-render
            nodes.forEach(node => {
                // Set nodes to their exact saved positions
                node.x = node.targetX;
                node.y = node.targetY;
            });
            
            // Only apply boundary constraints if nodes somehow went outside
            // This should rarely happen since positions are already validated
            nodes.forEach(node => {
                const dx = node.x - actualCenterX;
                const dy = node.y - actualCenterY;
                const distance = Math.sqrt(dx * dx + dy * dy);
                
                if (distance > 0) {
                    // Constrain to outer boundary
                    if (distance > outerRadius) {
                        const scale = outerRadius / distance;
                        node.x = actualCenterX + dx * scale;
                        node.y = actualCenterY + dy * scale;
                    }
                    
                    // Constrain to inner boundary
                    if (distance < innerRadius) {
                        const scale = innerRadius / distance;
                        node.x = actualCenterX + dx * scale;
                        node.y = actualCenterY + dy * scale;
                    }
                }
            });
            
            // Update target positions to match final positions (should be same as saved)
            nodes.forEach(node => {
                node.targetX = node.x;
                node.targetY = node.y;
            });
            
            // Compare saved positions vs final rendered positions
            const customPositionsForComparison = Object.keys(customPositions).reduce((acc, key) => {
                acc[key] = {
                    x: Math.round(customPositions[key].x),
                    y: Math.round(customPositions[key].y)
                };
                return acc;
            }, {});
            
            const positionComparison = nodes.map(n => {
                const saved = customPositionsForComparison[n.nodeId];
                const final = { x: Math.round(n.x), y: Math.round(n.y) };
                if (saved) {
                    const dx = final.x - saved.x;
                    const dy = final.y - saved.y;
                    const distance = Math.sqrt(dx * dx + dy * dy);
                    return {
                        nodeId: n.nodeId,
                        text: n.text,
                        saved: saved,
                        final: final,
                        delta: { x: dx, y: dy, distance: Math.round(distance) }
                    };
                }
                return {
                    nodeId: n.nodeId,
                    text: n.text,
                    saved: null,
                    final: final,
                    delta: null
                };
            });
            
            const finalPositionsList = nodes.map(n => ({
                nodeId: n.nodeId,
                text: n.text,
                x: Math.round(n.x),
                y: Math.round(n.y),
                targetX: Math.round(n.targetX),
                targetY: Math.round(n.targetY)
            }));
            
            logger.info('[CircleMap-Renderer] Final positions after simulation (with custom positions)', {
                nodeCount: nodes.length,
                positions: finalPositionsList.map(p => `${p.nodeId}: (${p.x}, ${p.y})`).join(', ')
            });
            finalPositionsList.forEach(pos => {
                logger.info('[CircleMap-Renderer]', `  Final: ${pos.nodeId}`, { x: pos.x, y: pos.y, targetX: pos.targetX, targetY: pos.targetY });
            });
            
            logger.info('[CircleMap-Renderer] Position comparison: Saved → Final', {
                count: positionComparison.length,
                summary: positionComparison.map(c => {
                    if (c.saved) {
                        return `${c.nodeId}: (${c.saved.x}, ${c.saved.y}) → (${c.final.x}, ${c.final.y}) [Δ${c.delta.distance}px]`;
                    }
                    return `${c.nodeId}: (no saved) → (${c.final.x}, ${c.final.y})`;
                }).join(', ')
            });
            positionComparison.forEach(comp => {
                if (comp.saved) {
                    logger.info('[CircleMap-Renderer]', `  ${comp.nodeId}`, {
                        saved: { x: comp.saved.x, y: comp.saved.y },
                        final: { x: comp.final.x, y: comp.final.y },
                        delta: { x: comp.delta.x, y: comp.delta.y, distance: comp.delta.distance }
                    });
                } else {
                    logger.info('[CircleMap-Renderer]', `  ${comp.nodeId}`, {
                        saved: null,
                        final: { x: comp.final.x, y: comp.final.y }
                    });
                }
            });
        } else {
            // No custom positions - run simulation to create nice circular layout
            // First, ensure nodes start at their calculated target positions
            nodes.forEach(node => {
                node.x = node.targetX;
                node.y = node.targetY;
            });
            
            // Run simulation to create nice circular distribution
            // The simulation will use the donutBoundary force to keep nodes in the ring
            // Run enough ticks to ensure good layout
            for (let i = 0; i < 400; ++i) {
                window.circleMapSimulation.tick();
            }
            
            // Ensure nodes are within boundaries after simulation
            nodes.forEach(node => {
                const dx = node.x - actualCenterX;
                const dy = node.y - actualCenterY;
                const distance = Math.sqrt(dx * dx + dy * dy);
                
                if (distance > 0) {
                    // Constrain to outer boundary
                    if (distance > outerRadius) {
                        const scale = outerRadius / distance;
                        node.x = actualCenterX + dx * scale;
                        node.y = actualCenterY + dy * scale;
                    }
                    
                    // Constrain to inner boundary
                    if (distance < innerRadius) {
                        const scale = innerRadius / distance;
                        node.x = actualCenterX + dx * scale;
                        node.y = actualCenterY + dy * scale;
                    }
                }
            });
            
            // Update target positions to match final simulation positions
            // This ensures if user drags later, nodes start from good positions
            nodes.forEach(node => {
                node.targetX = node.x;
                node.targetY = node.y;
            });
        }
    }
    
    const minX = actualCenterX - outerCircleR - padding;
    const maxX = actualCenterX + outerCircleR + padding;
    const minY = actualCenterY - outerCircleR - padding;
    const maxY = actualCenterY + outerCircleR + padding;
    const width = maxX - minX;
    const height = maxY - minY;
    
    logger.info('[CircleMap-Renderer] Canvas dimensions:', {
        requestedBase: { width: baseWidth, height: baseHeight },
        required: requiredDimension,
        actual: { width: actualWidth, height: actualHeight },
        finalSVG: { width: Math.round(width), height: Math.round(height) }
    });
    
    const svg = d3.select('#d3-container').append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `${minX} ${minY} ${width} ${height}`)
        .attr('preserveAspectRatio', 'xMidYMid meet');
    
    // Add background rectangle to cover entire SVG area (consistency with other maps)
    // Use backgroundColor already declared at line 266
    svg.append('rect')
        .attr('class', 'background')
        .attr('x', minX)
        .attr('y', minY)
        .attr('width', width)
        .attr('height', height)
        .attr('fill', backgroundColor)
        .attr('stroke', 'none');
    
    // Draw outer circle first (background boundary)
    svg.append('circle')
        .attr('cx', actualCenterX)
        .attr('cy', actualCenterY)
        .attr('r', outerCircleR)
        .attr('fill', THEME.outerCircleFill)
        .attr('stroke', THEME.outerCircleStroke)
        .attr('stroke-width', THEME.outerCircleStrokeWidth)
        .attr('data-node-id', 'outer_boundary')
        .attr('data-node-type', 'boundary');
    
    // Draw context circles around the perimeter
    nodes.forEach(node => {
        svg.append('circle')
            .attr('cx', node.x)
            .attr('cy', node.y)
            .attr('r', node.radius)
            .attr('fill', THEME.contextFill)
            .attr('stroke', THEME.contextStroke)
            .attr('stroke-width', THEME.contextStrokeWidth)
            .attr('data-node-id', `context_${node.id}`)
            .attr('data-node-type', 'context')
            .attr('data-array-index', node.id)
            .style('cursor', 'pointer');
        
        // Render context text with automatic wrapping and tspan (always use tspan)
        const contextText = node.text || '';
        const contextMaxWidth = node.radius * 1.8; // Max width based on circle radius
        const contextLineHeight = Math.round(THEME.fontContext * 1.2);
        
        // Use splitAndWrapText for automatic word wrapping
        const contextLines = (typeof window.splitAndWrapText === 'function')
            ? window.splitAndWrapText(contextText, THEME.fontContext, contextMaxWidth, measureLineWidth)
            : (contextText ? [contextText] : ['']);
        
        // Ensure at least one line for placeholder
        const finalContextLines = contextLines.length > 0 ? contextLines : [''];
        
        // WORKAROUND: Since tspan doesn't render, use multiple text elements
        const contextStartY = node.y - (finalContextLines.length - 1) * contextLineHeight / 2;
        
        finalContextLines.forEach((line, i) => {
            svg.append('text')
                .attr('x', node.x)
                .attr('y', contextStartY + i * contextLineHeight)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', THEME.contextText)
                .attr('font-size', THEME.fontContext)
                .attr('data-text-for', `context_${node.id}`)
                .attr('data-node-id', `context_${node.id}`)
                .attr('data-node-type', 'context')
                .attr('data-line-index', i)
                .style('cursor', 'pointer')
                .text(line);
        });
    });
    
    // Draw topic circle at center
    svg.append('circle')
        .attr('cx', actualCenterX)
        .attr('cy', actualCenterY)
        .attr('r', topicR)
        .attr('fill', THEME.topicFill)
        .attr('stroke', THEME.topicStroke)
        .attr('stroke-width', THEME.topicStrokeWidth)
        .attr('data-node-id', 'center_topic')
        .attr('data-node-type', 'center')
        .style('cursor', 'pointer');
    
    // Render topic text with automatic wrapping and tspan (always use tspan)
    // Handle both string and object topic (spec.topic can be "text" or {text: "text"})
    const topicTextStr = typeof spec.topic === 'object' ? (spec.topic.text || '') : (spec.topic || '');
    const topicMaxWidth = topicR * 1.8; // Max width based on circle radius
    const topicLineHeight = Math.round(THEME.fontTopic * 1.2);
    
    // Use splitAndWrapText for automatic word wrapping
    const topicLines = (typeof window.splitAndWrapText === 'function')
        ? window.splitAndWrapText(topicTextStr, THEME.fontTopic, topicMaxWidth, measureLineWidth)
        : (topicTextStr ? [topicTextStr] : ['']);
    
    // Ensure at least one line for placeholder
    const finalTopicLines = topicLines.length > 0 ? topicLines : [''];
    
    // DEBUG: Log actual center position and styling
    console.log('[CircleMap-Renderer] Topic text positioning:', {
        x: actualCenterX,
        y: actualCenterY - (finalTopicLines.length - 1) * topicLineHeight / 2,
        fill: THEME.topicText,
        fontSize: THEME.fontTopic,
        lineCount: finalTopicLines.length,
        lineHeight: topicLineHeight
    });
    
    // WORKAROUND: Since tspan doesn't render in this environment,
    // use multiple text elements for multi-line text
    const topicStartY = actualCenterY - (finalTopicLines.length - 1) * topicLineHeight / 2;
    
    finalTopicLines.forEach((line, i) => {
        svg.append('text')
            .attr('x', actualCenterX)
            .attr('y', topicStartY + i * topicLineHeight)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.topicText)
            .attr('font-size', THEME.fontTopic)
            .attr('font-weight', 'bold')
            .attr('data-text-for', 'center_topic')
            .attr('data-node-id', 'center_topic')
            .attr('data-node-type', 'center')
            .attr('data-line-index', i)
            .style('cursor', 'pointer')
            .text(line);
    });
    
    
    // Apply learning sheet text knockout if needed
    if (spec.is_learning_sheet && spec.hidden_node_percentage > 0) {
        knockoutTextForLearningSheet(svg, spec.hidden_node_percentage);
    }
    
    // 🆕 FIX: Recalculate tight viewBox based on actual rendered content
    // This eliminates excessive white padding especially when nodes are added from Node Palette
    recalculateTightViewBox(svg, padding);
    
    logger.info('[CircleMap-Renderer] ========================================');
    logger.info(`[CircleMap-Renderer] ✓ RENDERING COMPLETE: ${spec.context.length} context nodes displayed`);
    
    // Log final rendered positions for verification
    if (hasCustomPositions) {
        const renderedPositions = nodes.map(n => ({
            nodeId: n.nodeId,
            text: n.text,
            x: Math.round(n.x),
            y: Math.round(n.y)
        }));
        logger.info('[CircleMap-Renderer] Final rendered positions (for verification)', {
            count: renderedPositions.length,
            positions: renderedPositions.map(p => `${p.nodeId}: (${p.x}, ${p.y})`).join(', ')
        });
        renderedPositions.forEach(pos => {
            logger.info('[CircleMap-Renderer]', `  Rendered: ${pos.nodeId}`, { x: pos.x, y: pos.y, text: pos.text });
        });
    }
    
    logger.info('[CircleMap-Renderer] ========================================');
}

function renderDoubleBubbleMap(spec, theme = null, dimensions = null) {
    // Helper function to measure text width for wrapping
    function getMeasurementContainer() {
        let container = d3.select('#measurement-container');
        if (container.empty()) {
            container = d3.select('body').append('div')
                .attr('id', 'measurement-container')
                .style('position', 'absolute')
                .style('visibility', 'hidden')
                .style('pointer-events', 'none');
        }
        return container;
    }
    
    function measureLineWidth(text, fontSize) {
        const container = getMeasurementContainer();
        const t = container.append('svg').append('text').attr('font-size', fontSize).text(text);
        const w = t.node().getBBox().width;
        t.remove();
        return w;
    }
    // Validate BEFORE clearing container - defensive programming
    // Use typeof check to allow empty string (for empty button functionality)
    if (!spec) {
        logger.error('BubbleMapRenderer', 'spec is null or undefined');
        return;
    }
    
    if (typeof spec.left !== 'string' || typeof spec.right !== 'string') {
        logger.error('BubbleMapRenderer', 'missing left or right topic', { left: spec.left, right: spec.right });
        return;
    }
    
    if (!Array.isArray(spec.similarities)) {
        logger.error('BubbleMapRenderer', 'similarities is not an array', spec.similarities);
        return;
    }
    
    if (!Array.isArray(spec.left_differences)) {
        logger.error('BubbleMapRenderer', 'left_differences is not an array', spec.left_differences);
        return;
    }
    
    if (!Array.isArray(spec.right_differences)) {
        logger.error('BubbleMapRenderer', 'right_differences is not an array', spec.right_differences);
        return;
    }
    
    // Validation passed, clear container and proceed with rendering
    d3.select('#d3-container').html('');
    
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
    
    // Apply background if specified (like bubble map)
    if (theme && theme.background) {
        // Setting container background to theme background
        d3.select('#d3-container').style('background-color', theme.background);
    }
    
    const THEME = {
        topicFill: '#1976d2',          // Deep blue for both topics (matches original)
        topicText: '#ffffff',          // White text for both topics (matches original)
        topicStroke: '#000000',        // Black border for both topics (matches original)
        topicStrokeWidth: 2,
        simFill: '#e3f2fd',            // Light blue for similarities (matching flow map substeps)
        simText: '#333333',            // Dark text for similarities (matches original)
        simStroke: '#1976d2',          // Blue border (matching flow map substeps)
        simStrokeWidth: 2,
        diffFill: '#e3f2fd',           // Light blue for differences (matching flow map substeps)
        diffText: '#333333',           // Dark text for differences (matches original)
        diffStroke: '#1976d2',         // Blue border (matching flow map substeps)
        diffStrokeWidth: 2,
        fontTopic: 18,                 // Use numeric value like original
        fontSim: 14,
        fontDiff: 14,
        ...theme
    };
    
    // Check for preserved dimensions from empty button operation
    const nodeDimensions = spec._node_dimensions || {};
    
    // Helper to extract text from string or object
    const extractText = (item) => typeof item === 'object' ? (item.text || '') : (item || '');
    
    // Calculate text sizes and radii - use preserved dimensions if available
    const leftText = extractText(spec.left);
    const rightText = extractText(spec.right);
    
    let leftTopicR, rightTopicR;
    if (nodeDimensions.left && nodeDimensions.left.r && leftText === '') {
        leftTopicR = nodeDimensions.left.r;
        logger.debug('DoubleBubbleMapRenderer', 'Using preserved left topic radius', { leftTopicR });
    } else {
        leftTopicR = getTextRadius(leftText, THEME.fontTopic, 20);
    }
    
    if (nodeDimensions.right && nodeDimensions.right.r && rightText === '') {
        rightTopicR = nodeDimensions.right.r;
        logger.debug('DoubleBubbleMapRenderer', 'Using preserved right topic radius', { rightTopicR });
    } else {
        rightTopicR = getTextRadius(rightText, THEME.fontTopic, 20);
    }
    const topicR = Math.max(leftTopicR, rightTopicR, 60);
    
    // Calculate similarity radii - use preserved dimensions if available
    const simRadii = spec.similarities.map((t, idx) => {
        const text = extractText(t);
        const nodeKey = `similarity-${idx}`;
        const preservedDims = nodeDimensions[nodeKey];
        
        if (preservedDims && preservedDims.r && text === '') {
            logger.debug('DoubleBubbleMapRenderer', 'Using preserved similarity radius', { idx, r: preservedDims.r });
            return preservedDims.r;
        }
        return getTextRadius(text, THEME.fontSim, 10);
    });
    const simR = Math.max(...simRadii, 28);
    
    // Calculate uniform radius for ALL difference circles (both left and right) - use preserved dimensions
    const leftDiffRadii = spec.left_differences.map((t, idx) => {
        const text = extractText(t);
        const nodeKey = `left_difference-${idx}`;
        const preservedDims = nodeDimensions[nodeKey];
        
        if (preservedDims && preservedDims.r && text === '') {
            logger.debug('DoubleBubbleMapRenderer', 'Using preserved left_difference radius', { idx, r: preservedDims.r });
            return preservedDims.r;
        }
        return getTextRadius(text, THEME.fontDiff, 8);
    });
    
    const rightDiffRadii = spec.right_differences.map((t, idx) => {
        const text = extractText(t);
        const nodeKey = `right_difference-${idx}`;
        const preservedDims = nodeDimensions[nodeKey];
        
        if (preservedDims && preservedDims.r && text === '') {
            logger.debug('DoubleBubbleMapRenderer', 'Using preserved right_difference radius', { idx, r: preservedDims.r });
            return preservedDims.r;
        }
        return getTextRadius(text, THEME.fontDiff, 8);
    });
    
    const uniformDiffR = Math.max(...leftDiffRadii, ...rightDiffRadii, 24);
    const leftDiffR = uniformDiffR;
    const rightDiffR = uniformDiffR;
    
    // Calculate counts
    const simCount = spec.similarities.length;
    const leftDiffCount = spec.left_differences.length;
    const rightDiffCount = spec.right_differences.length;
    
    // Calculate column heights
    const simColHeight = simCount > 0 ? (simCount - 1) * (simR * 2 + 12) + simR * 2 : 0;
    const leftColHeight = leftDiffCount > 0 ? (leftDiffCount - 1) * (leftDiffR * 2 + 10) + leftDiffR * 2 : 0;
    const rightColHeight = rightDiffCount > 0 ? (rightDiffCount - 1) * (rightDiffR * 2 + 10) + rightDiffR * 2 : 0;
    const maxColHeight = Math.max(simColHeight, leftColHeight, rightColHeight, topicR * 2);
    const requiredHeight = maxColHeight + padding * 2;
    
    // Use adaptive height if provided, otherwise use content-based height
    // This ensures consistent sizing with other diagrams
    const height = spec._recommended_dimensions ? baseHeight : Math.max(baseHeight, requiredHeight);
    
    // Position columns with 50px spacing between them (matching original)
    const columnSpacing = 50;
    
    // First calculate positions without centering offset
    let leftDiffX = padding + leftDiffR;
    let leftTopicX = leftDiffX + leftDiffR + columnSpacing + topicR;
    let simX = leftTopicX + topicR + columnSpacing + simR;
    let rightTopicX = simX + simR + columnSpacing + topicR;
    let rightDiffX = rightTopicX + topicR + columnSpacing + rightDiffR;
    
    // Calculate width to accommodate all columns
    const requiredWidth = rightDiffX + rightDiffR + padding * 2;
    
    // Use adaptive width if provided, otherwise use content-based width
    // This prevents the diagram from being too wide and causing scrollbars
    const width = spec._recommended_dimensions ? baseWidth : Math.max(baseWidth, requiredWidth);
    
    // Center content horizontally within adaptive width
    let horizontalOffset = 0;
    if (spec._recommended_dimensions && width > requiredWidth) {
        horizontalOffset = (width - requiredWidth) / 2;
    }
    
    // Apply horizontal centering offset
    leftDiffX += horizontalOffset;
    leftTopicX += horizontalOffset;
    simX += horizontalOffset;
    rightTopicX += horizontalOffset;
    rightDiffX += horizontalOffset;
    
    // Center content vertically within the adaptive height
    // If using adaptive dimensions, center the content properly
    const contentHeight = maxColHeight + padding * 2;
    const topicY = spec._recommended_dimensions ? 
        (height - contentHeight) / 2 + contentHeight / 2 : // Center within adaptive height
        height / 2; // Use middle for content-based height
    
    const svg = d3.select('#d3-container').append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `0 0 ${width} ${height}`)
        .attr('preserveAspectRatio', 'xMidYMid meet');
    
    // Add background rect to cover entire SVG area (prevents white bar)
    const bgColor = (theme && theme.background) ? theme.background : '#f5f5f5';
    svg.append('rect')
        .attr('class', 'background')
        .attr('width', width)
        .attr('height', height)
        .attr('fill', bgColor)
        .attr('stroke', 'none')
        .attr('x', 0)
        .attr('y', 0);
    
    // Apply container background if specified (like bubble map)
    if (theme && theme.background) {
        // Setting container background and dimensions
        d3.select('#d3-container').style('background-color', theme.background);
    }
    
    // Draw all connecting lines first (so they appear behind nodes)
    // Lines from left topic to similarities
    if (spec.similarities && Array.isArray(spec.similarities)) {
        const simStartY = topicY - ((simCount - 1) * (simR * 2 + 12)) / 2;
        spec.similarities.forEach((item, i) => {
            const y = simStartY + i * (simR * 2 + 12);
            
            // Line from left topic to similarity
            const dxL = leftTopicX - simX;
            const dyL = topicY - y;
            const distL = Math.sqrt(dxL * dxL + dyL * dyL);
            if (distL > 0) {
                const x1L = simX + (dxL / distL) * simR;
                const y1L = y + (dyL / distL) * simR;
                const x2L = leftTopicX - (dxL / distL) * topicR;
                const y2L = topicY - (dyL / distL) * topicR;
                
                svg.append('line')
                    .attr('x1', x1L)
                    .attr('y1', y1L)
                    .attr('x2', x2L)
                    .attr('y2', y2L)
                    .attr('stroke', '#888')
                    .attr('stroke-width', 2)
                    .attr('data-line-for', `similarity_${i}`)
                    .attr('data-line-type', 'left-to-similarity');
            }
            
            // Line from right topic to similarity
            const dxR = rightTopicX - simX;
            const dyR = topicY - y;
            const distR = Math.sqrt(dxR * dxR + dyR * dyR);
            if (distR > 0) {
                const x1R = simX + (dxR / distR) * simR;
                const y1R = y + (dyR / distR) * simR;
                const x2R = rightTopicX - (dxR / distR) * topicR;
                const y2R = topicY - (dyR / distR) * topicR;
                
                svg.append('line')
                    .attr('x1', x1R)
                    .attr('y1', y1R)
                    .attr('x2', x2R)
                    .attr('y2', y2R)
                    .attr('stroke', '#888')
                    .attr('stroke-width', 2)
                    .attr('data-line-for', `similarity_${i}`)
                    .attr('data-line-type', 'right-to-similarity');
            }
        });
    }
    
    // Lines from left topic to left differences
    if (spec.left_differences && Array.isArray(spec.left_differences)) {
        const leftDiffStartY = topicY - ((leftDiffCount - 1) * (leftDiffR * 2 + 10)) / 2;
        spec.left_differences.forEach((item, i) => {
            const y = leftDiffStartY + i * (leftDiffR * 2 + 10);
            
            const dx = leftTopicX - leftDiffX;
            const dy = topicY - y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist > 0) {
                const x1 = leftDiffX + (dx / dist) * leftDiffR;
                const y1 = y + (dy / dist) * leftDiffR;
                const x2 = leftTopicX - (dx / dist) * topicR;
                const y2 = topicY - (dy / dist) * topicR;
                
                svg.append('line')
                    .attr('x1', x1)
                    .attr('y1', y1)
                    .attr('x2', x2)
                    .attr('y2', y2)
                    .attr('stroke', '#888')
                    .attr('stroke-width', 2)
                    .attr('data-line-for', `left_diff_${i}`)
                    .attr('data-line-type', 'left-to-left-diff');
            }
        });
    }
    
    // Lines from right topic to right differences
    if (spec.right_differences && Array.isArray(spec.right_differences)) {
        const rightDiffStartY = topicY - ((rightDiffCount - 1) * (rightDiffR * 2 + 10)) / 2;
        spec.right_differences.forEach((item, i) => {
            const y = rightDiffStartY + i * (rightDiffR * 2 + 10);
            
            const dx = rightTopicX - rightDiffX;
            const dy = topicY - y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist > 0) {
                const x1 = rightDiffX + (dx / dist) * rightDiffR;
                const y1 = y + (dy / dist) * rightDiffR;
                const x2 = rightTopicX - (dx / dist) * topicR;
                const y2 = topicY - (dy / dist) * topicR;
                
                svg.append('line')
                    .attr('x1', x1)
                    .attr('y1', y1)
                    .attr('x2', x2)
                    .attr('y2', y2)
                    .attr('stroke', '#888')
                    .attr('stroke-width', 2)
                    .attr('data-line-for', `right_diff_${i}`)
                    .attr('data-line-type', 'right-to-right-diff');
                }
        });
    }
    
    // Draw left topic
    svg.append('circle')
        .attr('cx', leftTopicX)
        .attr('cy', topicY)
        .attr('r', topicR)
        .attr('fill', THEME.topicFill)
        .attr('stroke', THEME.topicStroke)
        .attr('stroke-width', THEME.topicStrokeWidth)
        .attr('data-node-id', 'topic_left')
        .attr('data-node-type', 'left');
    
    // Render left topic text - use multiple text elements (tspan doesn't render)
    // leftText already extracted above for dimension calculations
    const leftMaxWidth = topicR * 1.8; // Max width based on circle radius
    const leftLines = (typeof window.splitAndWrapText === 'function')
        ? window.splitAndWrapText(leftText, THEME.fontTopic, leftMaxWidth, measureLineWidth)
        : (leftText ? leftText.split(/\n/) : ['']);
    const finalLeftLines = leftLines.length > 0 ? leftLines : [''];
    const leftLineHeight = Math.round(THEME.fontTopic * 1.2);
    
    // WORKAROUND: Use multiple text elements instead of tspan
    const leftStartY = topicY - (finalLeftLines.length - 1) * leftLineHeight / 2;
    finalLeftLines.forEach((line, i) => {
        svg.append('text')
            .attr('x', leftTopicX)
            .attr('y', leftStartY + i * leftLineHeight)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.topicText)
            .attr('font-size', THEME.fontTopic)
            .attr('font-weight', 600)
            .attr('data-node-id', 'topic_left')
            .attr('data-node-type', 'left')
            .attr('data-line-index', i)
            .text(line);
    });
    
    // Draw right topic
    svg.append('circle')
        .attr('cx', rightTopicX)
        .attr('cy', topicY)
        .attr('r', topicR)
        .attr('fill', THEME.topicFill)
        .attr('stroke', THEME.topicStroke)
        .attr('stroke-width', THEME.topicStrokeWidth)
        .attr('data-node-id', 'topic_right')
        .attr('data-node-type', 'right');
    
    // Render right topic text - use multiple text elements (tspan doesn't render)
    // rightText already extracted above for dimension calculations
    const rightMaxWidth = topicR * 1.8; // Max width based on circle radius
    const rightLines = (typeof window.splitAndWrapText === 'function')
        ? window.splitAndWrapText(rightText, THEME.fontTopic, rightMaxWidth, measureLineWidth)
        : (rightText ? rightText.split(/\n/) : ['']);
    const finalRightLines = rightLines.length > 0 ? rightLines : [''];
    const rightLineHeight = Math.round(THEME.fontTopic * 1.2);
    
    // WORKAROUND: Use multiple text elements instead of tspan
    const rightStartY = topicY - (finalRightLines.length - 1) * rightLineHeight / 2;
    finalRightLines.forEach((line, i) => {
        svg.append('text')
            .attr('x', rightTopicX)
            .attr('y', rightStartY + i * rightLineHeight)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.topicText)
            .attr('font-size', THEME.fontTopic)
            .attr('font-weight', 600)
            .attr('data-node-id', 'topic_right')
            .attr('data-node-type', 'right')
            .attr('data-line-index', i)
            .text(line);
    });
    
    // Check for custom positions
    const customPositions = spec._customPositions || {};
    const hasCustomPositions = Object.keys(customPositions).length > 0;
    
    // Position nodes
    // If custom positions exist but some nodes don't have positions (new nodes added),
    // recalculate all positions evenly to maintain proper spacing
    // Note: simCount, leftDiffCount, rightDiffCount are already declared above
    
    // Count how many nodes have custom positions for each type
    let similaritiesWithCustomPositions = 0;
    let leftDiffsWithCustomPositions = 0;
    let rightDiffsWithCustomPositions = 0;
    
    if (hasCustomPositions) {
        for (let i = 0; i < simCount; i++) {
            const nodeId = `similarity_${i}`;
            if (customPositions.hasOwnProperty(nodeId) && customPositions[nodeId] !== null && customPositions[nodeId] !== undefined) {
                similaritiesWithCustomPositions++;
            }
        }
        for (let i = 0; i < leftDiffCount; i++) {
            const nodeId = `left_diff_${i}`;
            if (customPositions.hasOwnProperty(nodeId) && customPositions[nodeId] !== null && customPositions[nodeId] !== undefined) {
                leftDiffsWithCustomPositions++;
            }
        }
        for (let i = 0; i < rightDiffCount; i++) {
            const nodeId = `right_diff_${i}`;
            if (customPositions.hasOwnProperty(nodeId) && customPositions[nodeId] !== null && customPositions[nodeId] !== undefined) {
                rightDiffsWithCustomPositions++;
            }
        }
    }
    
    const hasNewSimilaritiesWithoutPositions = hasCustomPositions && similaritiesWithCustomPositions < simCount;
    const hasNewLeftDiffsWithoutPositions = hasCustomPositions && leftDiffsWithCustomPositions < leftDiffCount;
    const hasNewRightDiffsWithoutPositions = hasCustomPositions && rightDiffsWithCustomPositions < rightDiffCount;
    const shouldRecalculateSimilarities = hasNewSimilaritiesWithoutPositions;
    const shouldRecalculateLeftDiffs = hasNewLeftDiffsWithoutPositions;
    const shouldRecalculateRightDiffs = hasNewRightDiffsWithoutPositions;
    
    logger.info('[DoubleBubbleMap-Renderer] Position detection check', {
        hasCustomPositions,
        simCount,
        similaritiesWithCustomPositions,
        leftDiffCount,
        leftDiffsWithCustomPositions,
        rightDiffCount,
        rightDiffsWithCustomPositions,
        shouldRecalculateSimilarities,
        shouldRecalculateLeftDiffs,
        shouldRecalculateRightDiffs
    });
    console.log('[DoubleBubbleMap-Renderer] 🔍 Position detection check:', {
        hasCustomPositions,
        simCount,
        similaritiesWithCustomPositions,
        leftDiffCount,
        leftDiffsWithCustomPositions,
        rightDiffCount,
        rightDiffsWithCustomPositions,
        shouldRecalculateSimilarities,
        shouldRecalculateLeftDiffs,
        shouldRecalculateRightDiffs
    });
    
    // Store node references globally for drag operations
    const doubleBubbleNodes = [];
    
    // Draw similarities in center column
    if (spec.similarities && Array.isArray(spec.similarities)) {
        const simStartY = topicY - ((simCount - 1) * (simR * 2 + 12)) / 2;
        spec.similarities.forEach((item, i) => {
            const nodeId = `similarity_${i}`;
            
            // Check if custom position exists and we're not recalculating
            let x, y;
            if (hasCustomPositions && customPositions[nodeId] && !shouldRecalculateSimilarities) {
                x = customPositions[nodeId].x;
                y = customPositions[nodeId].y;
            } else {
                x = simX;
                y = simStartY + i * (simR * 2 + 12);
            }
            
            // Store node reference
            doubleBubbleNodes.push({
                id: i,
                nodeId: nodeId,
                type: 'similarity',
                x: x,
                y: y,
                radius: simR
            });
            
            svg.append('circle')
                .attr('cx', x)
                .attr('cy', y)
                .attr('r', simR)
                .attr('fill', THEME.simFill)
                .attr('stroke', THEME.simStroke)
                .attr('stroke-width', THEME.simStrokeWidth)
                .attr('data-node-id', nodeId)
                .attr('data-node-type', 'similarity')
                .attr('data-array-index', i);
            
            // Render similarity text - use multiple text elements (tspan doesn't render)
            const simText = typeof item === 'string' ? item : (item?.text || item?.content || String(item || ''));
            const simMaxWidth = simR * 1.8; // Max width based on circle radius
            const simLines = (typeof window.splitAndWrapText === 'function')
                ? window.splitAndWrapText(simText, THEME.fontSim, simMaxWidth, measureLineWidth)
                : (simText ? simText.split(/\n/) : ['']);
            const finalSimLines = simLines.length > 0 ? simLines : [''];
            const simLineHeight = Math.round(THEME.fontSim * 1.2);
            
            // WORKAROUND: Use multiple text elements instead of tspan
            const simTextStartY = y - (finalSimLines.length - 1) * simLineHeight / 2;
            finalSimLines.forEach((line, idx) => {
                svg.append('text')
                    .attr('x', x)
                    .attr('y', simTextStartY + idx * simLineHeight)
                    .attr('text-anchor', 'middle')
                    .attr('dominant-baseline', 'middle')
                    .attr('fill', THEME.simText)
                    .attr('font-size', THEME.fontSim)
                    .attr('data-node-id', nodeId)
                    .attr('data-node-type', 'similarity')
                    .attr('data-array-index', i)
                    .attr('data-line-index', idx)
                    .text(line);
            });
        });
    }
    
    // Draw left differences in leftmost column
    if (spec.left_differences && Array.isArray(spec.left_differences)) {
        const leftDiffStartY = topicY - ((leftDiffCount - 1) * (leftDiffR * 2 + 10)) / 2;
        spec.left_differences.forEach((item, i) => {
            const nodeId = `left_diff_${i}`;
            
            // Check if custom position exists and we're not recalculating
            let x, y;
            if (hasCustomPositions && customPositions[nodeId] && !shouldRecalculateLeftDiffs) {
                x = customPositions[nodeId].x;
                y = customPositions[nodeId].y;
            } else {
                x = leftDiffX;
                y = leftDiffStartY + i * (leftDiffR * 2 + 10);
            }
            
            // Store node reference
            doubleBubbleNodes.push({
                id: i,
                nodeId: nodeId,
                type: 'left_difference',
                x: x,
                y: y,
                radius: leftDiffR
            });
            
            svg.append('circle')
                .attr('cx', x)
                .attr('cy', y)
                .attr('r', leftDiffR)
                .attr('fill', THEME.diffFill)
                .attr('stroke', THEME.diffStroke)
                .attr('stroke-width', THEME.diffStrokeWidth)
                .attr('data-node-id', nodeId)
                .attr('data-node-type', 'left_difference')
                .attr('data-array-index', i);
            
            // Render left difference text - use multiple text elements (tspan doesn't render)
            const itemText = typeof item === 'string' ? item : (item?.text || item?.content || String(item || ''));
            const leftDiffMaxWidth = leftDiffR * 1.8; // Max width based on circle radius
            const leftDiffLines = (typeof window.splitAndWrapText === 'function')
                ? window.splitAndWrapText(itemText, THEME.fontDiff, leftDiffMaxWidth, measureLineWidth)
                : (itemText ? itemText.split(/\n/) : ['']);
            const finalLeftDiffLines = leftDiffLines.length > 0 ? leftDiffLines : [''];
            const leftDiffLineHeight = Math.round(THEME.fontDiff * 1.2);
            
            // WORKAROUND: Use multiple text elements instead of tspan
            const leftDiffTextStartY = y - (finalLeftDiffLines.length - 1) * leftDiffLineHeight / 2;
            finalLeftDiffLines.forEach((line, idx) => {
                svg.append('text')
                    .attr('x', x)
                    .attr('y', leftDiffTextStartY + idx * leftDiffLineHeight)
                    .attr('text-anchor', 'middle')
                    .attr('dominant-baseline', 'middle')
                    .attr('fill', THEME.diffText)
                    .attr('font-size', THEME.fontDiff)
                    .attr('data-node-id', nodeId)
                    .attr('data-node-type', 'left_difference')
                    .attr('data-array-index', i)
                    .attr('data-line-index', idx)
                    .text(line);
            });
        });
    }
    
    // Draw right differences in rightmost column
    if (spec.right_differences && Array.isArray(spec.right_differences)) {
        const rightDiffStartY = topicY - ((rightDiffCount - 1) * (rightDiffR * 2 + 10)) / 2;
        spec.right_differences.forEach((item, i) => {
            const nodeId = `right_diff_${i}`;
            
            // Check if custom position exists and we're not recalculating
            let x, y;
            if (hasCustomPositions && customPositions[nodeId] && !shouldRecalculateRightDiffs) {
                x = customPositions[nodeId].x;
                y = customPositions[nodeId].y;
            } else {
                x = rightDiffX;
                y = rightDiffStartY + i * (rightDiffR * 2 + 10);
            }
            
            // Store node reference
            doubleBubbleNodes.push({
                id: i,
                nodeId: nodeId,
                type: 'right_difference',
                x: x,
                y: y,
                radius: rightDiffR
            });
            
            svg.append('circle')
                .attr('cx', x)
                .attr('cy', y)
                .attr('r', rightDiffR)
                .attr('fill', THEME.diffFill)
                .attr('stroke', THEME.diffStroke)
                .attr('stroke-width', THEME.diffStrokeWidth)
                .attr('data-node-id', nodeId)
                .attr('data-node-type', 'right_difference')
                .attr('data-array-index', i);
            
            // Render right difference text - use multiple text elements (tspan doesn't render)
            const itemText = typeof item === 'string' ? item : (item?.text || item?.content || String(item || ''));
            const rightDiffMaxWidth = rightDiffR * 1.8; // Max width based on circle radius
            const rightDiffLines = (typeof window.splitAndWrapText === 'function')
                ? window.splitAndWrapText(itemText, THEME.fontDiff, rightDiffMaxWidth, measureLineWidth)
                : (itemText ? itemText.split(/\n/) : ['']);
            const finalRightDiffLines = rightDiffLines.length > 0 ? rightDiffLines : [''];
            const rightDiffLineHeight = Math.round(THEME.fontDiff * 1.2);
            
            // WORKAROUND: Use multiple text elements instead of tspan
            const rightDiffTextStartY = y - (finalRightDiffLines.length - 1) * rightDiffLineHeight / 2;
            finalRightDiffLines.forEach((line, idx) => {
                svg.append('text')
                    .attr('x', x)
                    .attr('y', rightDiffTextStartY + idx * rightDiffLineHeight)
                    .attr('text-anchor', 'middle')
                    .attr('dominant-baseline', 'middle')
                    .attr('fill', THEME.diffText)
                    .attr('font-size', THEME.fontDiff)
                    .attr('data-node-id', nodeId)
                    .attr('data-node-type', 'right_difference')
                    .attr('data-array-index', i)
                    .attr('data-line-index', idx)
                    .text(line);
            });
        });
    }
    
    // Store node references globally for drag operations
    window.doubleBubbleMapNodes = doubleBubbleNodes;
    
    // Create force simulation for drag operations (marbles effect)
    // Add central topics as fixed nodes
    const leftTopicNode = {
        id: 'topic_left',
        nodeId: 'topic_left',
        type: 'left',
        x: leftTopicX,
        y: topicY,
        radius: topicR,
        fx: leftTopicX, // Fixed position
        fy: topicY
    };
    
    const rightTopicNode = {
        id: 'topic_right',
        nodeId: 'topic_right',
        type: 'right',
        x: rightTopicX,
        y: topicY,
        radius: topicR,
        fx: rightTopicX, // Fixed position
        fy: topicY
    };
    
    // Create force simulation with all nodes
    const simulation = d3.forceSimulation([leftTopicNode, rightTopicNode, ...doubleBubbleNodes])
        .force('charge', d3.forceManyBody().strength(-600))
        .force('collide', d3.forceCollide().radius(d => d.radius + 5))
        .force('x', d3.forceX().strength(0.3).x(d => {
            // Constrain nodes to their columns
            if (d.type === 'similarity') return simX;
            if (d.type === 'left_difference') return leftDiffX;
            if (d.type === 'right_difference') return rightDiffX;
            return d.x; // Keep central topics fixed
        }))
        .force('y', d3.forceY().strength(0.1).y(topicY)) // Slight pull towards center Y
        .stop();
    
    // Only run simulation if we're recalculating or if no custom positions exist
    // If custom positions exist and we're not recalculating, use exact positions
    const shouldRunSimulation = shouldRecalculateSimilarities || shouldRecalculateLeftDiffs || shouldRecalculateRightDiffs || !hasCustomPositions;
    
    if (shouldRunSimulation) {
        // Run simulation to settle initial positions
        for (let i = 0; i < 300; ++i) simulation.tick();
    } else {
        // If using custom positions, ensure nodes are at exact positions
        // Don't fix with fx/fy - we want them draggable, just ensure positions match
        doubleBubbleNodes.forEach(node => {
            // Positions should already be set from custom positions during node creation
            // Just verify they match (simulation will use these as starting positions)
            if (customPositions[node.nodeId]) {
                node.x = customPositions[node.nodeId].x;
                node.y = customPositions[node.nodeId].y;
                // Don't set fx/fy - nodes need to be draggable
            }
        });
    }
    
    // Log node positions after simulation/position setting
    console.log('[DoubleBubbleMap-Renderer] 🔵 Node positions after setup:', {
        shouldRunSimulation,
        hasCustomPositions,
        nodePositions: doubleBubbleNodes.map(n => ({
            nodeId: n.nodeId,
            type: n.type,
            x: Math.round(n.x),
            y: Math.round(n.y),
            fx: n.fx,
            fy: n.fy
        }))
    });
    
    // Store simulation globally for drag operations
    window.doubleBubbleMapSimulation = simulation;
    window.doubleBubbleMapCentralNodes = {
        left: leftTopicNode,
        right: rightTopicNode
    };
    
    // Store column positions globally for drag constraints
    window.doubleBubbleMapColumns = {
        simX: simX,
        leftDiffX: leftDiffX,
        rightDiffX: rightDiffX,
        leftTopicX: leftTopicX,
        rightTopicX: rightTopicX,
        topicY: topicY
    };
    
    console.log('[DoubleBubbleMap-Renderer] 🔵 Force simulation created:', {
        hasSimulation: !!simulation,
        nodeCount: doubleBubbleNodes.length,
        similarities: doubleBubbleNodes.filter(n => n.type === 'similarity').length,
        leftDiffs: doubleBubbleNodes.filter(n => n.type === 'left_difference').length,
        rightDiffs: doubleBubbleNodes.filter(n => n.type === 'right_difference').length,
        columns: {
            simX: Math.round(simX),
            leftDiffX: Math.round(leftDiffX),
            rightDiffX: Math.round(rightDiffX)
        }
    });
    
    // If we recalculated evenly (new nodes added), update custom positions silently
    // This ensures positions are saved for future renders without triggering re-render loop
    if (shouldRecalculateSimilarities || shouldRecalculateLeftDiffs || shouldRecalculateRightDiffs) {
        console.log('[DoubleBubbleMap-Renderer] 🔄 UPDATING CUSTOM POSITIONS - Recalculated evenly');
        if (!spec._customPositions) {
            spec._customPositions = {};
        }
        // Clear old custom positions for double bubble nodes
        Object.keys(spec._customPositions).forEach(key => {
            if (key.startsWith('similarity_') || key.startsWith('left_diff_') || key.startsWith('right_diff_')) {
                delete spec._customPositions[key];
            }
        });
        
        // Save all recalculated positions
        doubleBubbleNodes.forEach(node => {
            spec._customPositions[node.nodeId] = { x: node.x, y: node.y };
        });
        
        logger.info('[DoubleBubbleMap-Renderer] Updated custom positions with evenly-spaced layout', {
            updatedPositions: doubleBubbleNodes.length
        });
        console.log('[DoubleBubbleMap-Renderer] ✅ Custom positions updated:', Object.keys(spec._customPositions).filter(k => k.startsWith('similarity_') || k.startsWith('left_diff_') || k.startsWith('right_diff_')).sort());
    }
    
    // Apply learning sheet text knockout if needed
    if (spec.is_learning_sheet && spec.hidden_node_percentage > 0) {
        knockoutTextForLearningSheet(svg, spec.hidden_node_percentage);
    }
    
    // 🆕 FIX: Recalculate tight viewBox based on actual rendered content
    // This eliminates excessive white padding especially when nodes are added from Node Palette
    recalculateTightViewBox(svg, padding);
}

// Export functions for module system
if (typeof window !== 'undefined') {
    // Browser environment - attach to window
    window.BubbleMapRenderer = {
        renderBubbleMap,
        renderCircleMap,
        renderDoubleBubbleMap
    };
} else if (typeof module !== 'undefined' && module.exports) {
    // Node.js environment
    module.exports = {
        renderBubbleMap,
        renderCircleMap,
        renderDoubleBubbleMap
    };
}
