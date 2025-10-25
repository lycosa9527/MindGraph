/**
 * Bubble Map Renderer for MindGraph
 * 
 * This module contains the bubble map, double bubble map, and circle map rendering functions.
 * Requires: shared-utilities.js, style-manager.js
 * 
 * Performance Impact: Loads only ~50KB instead of full 213KB
 * 
 * Last Updated: 2024-12-19 - Fixed adaptive sizing for double bubble maps
 */

// Check if shared utilities are available
if (typeof window.MindGraphUtils === 'undefined') {
    logger.error('BubbleMapRenderer', 'MindGraphUtils not found. Please load shared-utilities.js first');
}

// Note: getTextRadius and addWatermark are available globally from shared-utilities.js

function renderBubbleMap(spec, theme = null, dimensions = null) {
    // VERBOSE LOGGING: Template receiving spec
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
    
    d3.select('#d3-container').html('');
    if (!spec || !spec.topic || !Array.isArray(spec.attributes)) {
        logger.error('[BubbleMap-Renderer]', 'Invalid spec for bubble_map');
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
    const topicR = getTextRadius(spec.topic, THEME.fontTopic, 20);
    
    // Calculate uniform radius for all attribute nodes
    const attributeRadii = spec.attributes.map(t => getTextRadius(t, THEME.fontAttribute, 10));
    const uniformAttributeR = Math.max(...attributeRadii, 30);
    
    logger.info(`[BubbleMap-Renderer] Rendering ${spec.attributes.length} adjective nodes with uniform radius: ${uniformAttributeR}px`); // Use the largest required radius for all
    
    // Calculate layout with collision detection
    const centerX = baseWidth / 2;
    let centerY = baseHeight / 2;
    
    // Calculate even distribution around the topic
    const targetDistance = topicR + uniformAttributeR + 50; // Distance from center
    
    // Create nodes for force simulation with uniform radius
    const nodes = spec.attributes.map((attr, i) => {
        // Calculate even angle distribution around the circle
        const angle = (i * 360 / spec.attributes.length) - 90; // -90 to start from top
        const targetX = centerX + targetDistance * Math.cos(angle * Math.PI / 180);
        const targetY = centerY + targetDistance * Math.sin(angle * Math.PI / 180);
        
        return {
            id: i,
            text: attr,
            radius: uniformAttributeR, // All nodes use the same radius
            targetX: targetX,
            targetY: targetY,
            x: targetX, // Start at target position
            y: targetY
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
                if (node.targetX !== undefined && node.targetY !== undefined) {
                    const dx = node.targetX - node.x;
                    const dy = node.targetY - node.y;
                    node.vx += dx * 0.1; // Pull towards target position
                    node.vy += dy * 0.1;
                }
            });
        })
        .stop();
    
    // Run simulation to find optimal positions
    for (let i = 0; i < 300; ++i) simulation.tick();
    
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
        .attr('preserveAspectRatio', 'xMinYMin meet');
    
    // Add background rectangle to cover entire SVG area
    svg.append('rect')
        .attr('x', minX)
        .attr('y', minY)
        .attr('width', width)
        .attr('height', height)
        .attr('fill', backgroundColor)
        .attr('stroke', 'none');
    
    // Debug: Log the calculated dimensions
    
    // Draw connecting lines from topic to attributes
    nodes.forEach(node => {
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
                .attr('stroke-width', 2);
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
    
    svg.append('text')
        .attr('x', centerX)
        .attr('y', centerY)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('fill', THEME.topicText)
        .attr('font-size', THEME.fontTopic)
        .attr('font-weight', 'bold')
        .attr('data-text-for', 'topic_center')
        .attr('data-node-id', 'topic_center')
        .attr('data-node-type', 'topic')
        .text(spec.topic);
    
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
        
        svg.append('text')
            .attr('x', node.x)
            .attr('y', node.y)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.attributeText)
            .attr('font-size', THEME.fontAttribute)
            .attr('data-text-for', `attribute_${node.id}`)
            .attr('data-node-id', `attribute_${node.id}`)
            .attr('data-node-type', 'attribute')
            .text(node.text);
    });
    
    // Watermark removed from canvas display - will be added during PNG export only
    
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
    
    d3.select('#d3-container').html('');
    if (!spec || !spec.topic || !Array.isArray(spec.context)) {
        logger.error('[CircleMap-Renderer] Invalid spec for circle_map');
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
    
    // Calculate uniform radius for all context nodes
    const contextRadii = spec.context.map(t => getTextRadius(t, THEME.fontContext, 10));
    const uniformContextR = Math.max(...contextRadii, 30); // Use the largest required radius for all
    
    logger.info(`[CircleMap-Renderer] Rendering ${spec.context.length} context nodes with uniform radius: ${uniformContextR}px`);
    
    // Calculate topic circle size (made smaller like original)
    const topicTextRadius = getTextRadius(spec.topic, THEME.fontTopic, 15);
    const topicR = Math.max(topicTextRadius + 15, 45); // Smaller topic circle at center
    
    // Calculate layout
    const centerX = baseWidth / 2;
    const centerY = baseHeight / 2;
    
    // Calculate outer circle radius to accommodate all context circles
    // Context circles should be adjacent to the outer circle but inside it
    // Ensure minimum distance between topic and context circles to prevent overlap
    // Half a circle size away between topic and context nodes
    const minDistanceBetweenCircles = topicR + uniformContextR + Math.max(topicR, uniformContextR) * 0.5; // Half a circle size gap
    const outerCircleR = Math.max(minDistanceBetweenCircles + 60, topicR + uniformContextR + 120); // Space between topic and context circles
    
    // Position context circles evenly around the inner perimeter of the outer circle
    const nodes = spec.context.map((ctx, i) => {
        // Calculate even angle distribution around the circle
        const angle = (i * 360 / spec.context.length) - 90; // -90 to start from top
        // Position context circles adjacent to but inside the outer circle
        const targetDistance = outerCircleR - uniformContextR - 5; // 5px margin from outer circle edge
        const targetX = centerX + targetDistance * Math.cos(angle * Math.PI / 180);
        const targetY = centerY + targetDistance * Math.sin(angle * Math.PI / 180);
        
        return {
            id: i,
            text: ctx,
            radius: uniformContextR,
            x: targetX,
            y: targetY
        };
    });
    
    logger.info('[CircleMap-Renderer] Node positioning calculated:');
    nodes.forEach((node, idx) => {
        logger.info(`  [${idx}] "${node.text}" at (${Math.round(node.x)}, ${Math.round(node.y)})`);
    });
    
    // Calculate bounds for SVG (outer circle + padding)
    const minX = centerX - outerCircleR - padding;
    const maxX = centerX + outerCircleR + padding;
    const minY = centerY - outerCircleR - padding;
    const maxY = centerY + outerCircleR + padding;
    const width = maxX - minX;
    const height = maxY - minY;
    
    const svg = d3.select('#d3-container').append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `${minX} ${minY} ${width} ${height}`)
        .attr('preserveAspectRatio', 'xMinYMin meet');
    
    // Add background rectangle to cover entire SVG area (consistency with other maps)
    // Use backgroundColor already declared at line 266
    svg.append('rect')
        .attr('x', minX)
        .attr('y', minY)
        .attr('width', width)
        .attr('height', height)
        .attr('fill', backgroundColor)
        .attr('stroke', 'none');
    
    // Draw outer circle first (background boundary)
    svg.append('circle')
        .attr('cx', centerX)
        .attr('cy', centerY)
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
        
        svg.append('text')
            .attr('x', node.x)
            .attr('y', node.y)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.contextText)
            .attr('font-size', THEME.fontContext)
            .attr('data-text-for', `context_${node.id}`)
            .attr('data-node-id', `context_${node.id}`)
            .attr('data-node-type', 'context')
            .style('cursor', 'pointer')
            .text(node.text);
    });
    
    // Draw topic circle at center
    svg.append('circle')
        .attr('cx', centerX)
        .attr('cy', centerY)
        .attr('r', topicR)
        .attr('fill', THEME.topicFill)
        .attr('stroke', THEME.topicStroke)
        .attr('stroke-width', THEME.topicStrokeWidth)
        .attr('data-node-id', 'center_topic')
        .attr('data-node-type', 'center')
        .style('cursor', 'pointer');
    
    // Draw topic text on top
    svg.append('text')
        .attr('x', centerX)
        .attr('y', centerY)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('fill', THEME.topicText)
        .attr('font-size', THEME.fontTopic)
        .attr('font-weight', 'bold')
        .attr('data-text-for', 'center_topic')
        .attr('data-node-id', 'center_topic')
        .attr('data-node-type', 'center')
        .style('cursor', 'pointer')
        .text(spec.topic);
    
    // Watermark removed from canvas display - will be added during PNG export only
    
    // Apply learning sheet text knockout if needed
    if (spec.is_learning_sheet && spec.hidden_node_percentage > 0) {
        knockoutTextForLearningSheet(svg, spec.hidden_node_percentage);
    }
    
    // 🆕 FIX: Recalculate tight viewBox based on actual rendered content
    // This eliminates excessive white padding especially when nodes are added from Node Palette
    recalculateTightViewBox(svg, padding);
    
    logger.info('[CircleMap-Renderer] ========================================');
    logger.info(`[CircleMap-Renderer] ✓ RENDERING COMPLETE: ${spec.context.length} context nodes displayed`);
    logger.info('[CircleMap-Renderer] ========================================');
}

function renderDoubleBubbleMap(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    
    // Enhanced validation with detailed error messages
    if (!spec) {
        logger.error('BubbleMapRenderer', 'spec is null or undefined');

        return;
    }
    
    if (!spec.left || !spec.right) {
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
    
    // Validation passed, proceeding with rendering
    
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
    
    // Calculate text sizes and radii
    const leftTopicR = getTextRadius(spec.left, THEME.fontTopic, 20);
    const rightTopicR = getTextRadius(spec.right, THEME.fontTopic, 20);
    const topicR = Math.max(leftTopicR, rightTopicR, 60);
    
    const simR = Math.max(...spec.similarities.map(t => getTextRadius(t, THEME.fontSim, 10)), 28);
    
    // Calculate uniform radius for ALL difference circles (both left and right)
    const allDiffTexts = [...spec.left_differences, ...spec.right_differences];
    const uniformDiffR = Math.max(...allDiffTexts.map(t => getTextRadius(t, THEME.fontDiff, 8)), 24);
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
        .attr('preserveAspectRatio', 'xMinYMin meet');
    
    // Add background rect to cover entire SVG area (prevents white bar)
    const bgColor = (theme && theme.background) ? theme.background : '#f5f5f5';
    svg.append('rect')
        .attr('width', width)
        .attr('height', height)
        .attr('fill', bgColor)
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
                    .attr('stroke-width', 2);
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
                    .attr('stroke-width', 2);
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
                    .attr('stroke', '#bbb')
                    .attr('stroke-width', 2);
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
                    .attr('stroke', '#bbb')
                    .attr('stroke-width', 2);
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
    
    svg.append('text')
        .attr('x', leftTopicX)
        .attr('y', topicY)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('fill', THEME.topicText)
        .attr('font-size', THEME.fontTopic)
        .attr('font-weight', 600)
        .text(spec.left)
        .attr('data-node-id', 'topic_left')
        .attr('data-node-type', 'left');
    
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
    
    svg.append('text')
        .attr('x', rightTopicX)
        .attr('y', topicY)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('fill', THEME.topicText)
        .attr('font-size', THEME.fontTopic)
        .attr('font-weight', 600)
        .text(spec.right)
        .attr('data-node-id', 'topic_right')
        .attr('data-node-type', 'right');
    
    // Draw similarities in center column
    if (spec.similarities && Array.isArray(spec.similarities)) {
        const simStartY = topicY - ((simCount - 1) * (simR * 2 + 12)) / 2;
        spec.similarities.forEach((item, i) => {
            const y = simStartY + i * (simR * 2 + 12);
            
            svg.append('circle')
                .attr('cx', simX)
                .attr('cy', y)
                .attr('r', simR)
                .attr('fill', THEME.simFill)
                .attr('stroke', THEME.simStroke)
                .attr('stroke-width', THEME.simStrokeWidth)
                .attr('data-node-id', `similarity_${i}`)
                .attr('data-node-type', 'similarity')
                .attr('data-array-index', i);
            
            svg.append('text')
                .attr('x', simX)
                .attr('y', y)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', THEME.simText)
                .attr('font-size', THEME.fontSim)
                .text(item)
                .attr('data-node-id', `similarity_${i}`)
                .attr('data-node-type', 'similarity')
                .attr('data-array-index', i);
        });
    }
    
    // Draw left differences in leftmost column
    if (spec.left_differences && Array.isArray(spec.left_differences)) {
        const leftDiffStartY = topicY - ((leftDiffCount - 1) * (leftDiffR * 2 + 10)) / 2;
        spec.left_differences.forEach((item, i) => {
            const y = leftDiffStartY + i * (leftDiffR * 2 + 10);
            
            svg.append('circle')
                .attr('cx', leftDiffX)
                .attr('cy', y)
                .attr('r', leftDiffR)
                .attr('fill', THEME.diffFill)
                .attr('stroke', THEME.diffStroke)
                .attr('stroke-width', THEME.diffStrokeWidth)
                .attr('data-node-id', `left_diff_${i}`)
                .attr('data-node-type', 'left_difference')
                .attr('data-array-index', i);
            
            svg.append('text')
                .attr('x', leftDiffX)
                .attr('y', y)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', THEME.diffText)
                .attr('font-size', THEME.fontDiff)
                .text(item)
                .attr('data-node-id', `left_diff_${i}`)
                .attr('data-node-type', 'left_difference')
                .attr('data-array-index', i);
        });
    }
    
    // Draw right differences in rightmost column
    if (spec.right_differences && Array.isArray(spec.right_differences)) {
        const rightDiffStartY = topicY - ((rightDiffCount - 1) * (rightDiffR * 2 + 10)) / 2;
        spec.right_differences.forEach((item, i) => {
            const y = rightDiffStartY + i * (rightDiffR * 2 + 10);
            
            svg.append('circle')
                .attr('cx', rightDiffX)
                .attr('cy', y)
                .attr('r', rightDiffR)
                .attr('fill', THEME.diffFill)
                .attr('stroke', THEME.diffStroke)
                .attr('stroke-width', THEME.diffStrokeWidth)
                .attr('data-node-id', `right_diff_${i}`)
                .attr('data-node-type', 'right_difference')
                .attr('data-array-index', i);
            
            svg.append('text')
                .attr('x', rightDiffX)
                .attr('y', y)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', THEME.diffText)
                .attr('font-size', THEME.fontDiff)
                .text(item)
                .attr('data-node-id', `right_diff_${i}`)
                .attr('data-node-type', 'right_difference')
                .attr('data-array-index', i);
        });
    }
    
    // Watermark removed from canvas display - will be added during PNG export only
    
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
