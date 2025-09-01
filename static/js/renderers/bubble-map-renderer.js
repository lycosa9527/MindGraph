/**
 * Bubble Map Renderer for MindGraph
 * 
 * This module contains the bubble map, double bubble map, and circle map rendering functions.
 * Requires: shared-utilities.js, style-manager.js
 * 
 * Performance Impact: Loads only ~50KB instead of full 213KB
 */

// Check if shared utilities are available
if (typeof window.MindGraphUtils === 'undefined') {
    console.error('MindGraphUtils not found. Please load shared-utilities.js first.');
}

// Note: getTextRadius and addWatermark are available globally from shared-utilities.js

function renderBubbleMap(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    if (!spec || !spec.topic || !Array.isArray(spec.attributes)) {
        console.error('Invalid spec for bubble_map');
        return;
    }
    
    // Use provided theme and dimensions or defaults
    const baseWidth = dimensions?.baseWidth || 700;
    const baseHeight = dimensions?.baseHeight || 500;
    const padding = dimensions?.padding || 40;
    
    // Load theme from style manager - FIXED: No more hardcoded overrides
    let THEME;
    try {
        if (typeof styleManager !== 'undefined' && styleManager.getTheme) {
            THEME = styleManager.getTheme('bubble_map', theme, theme);
            console.log('Bubble Map: Using centralized theme from style manager');
        } else {
            console.error('Style manager not available - this should not happen');
            throw new Error('Style manager not available for bubble map rendering');
        }
    } catch (error) {
        console.error('Error getting theme from style manager:', error);
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
    const uniformAttributeR = Math.max(...attributeRadii, 30); // Use the largest required radius for all
    
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
    console.log(`Bubble Map SVG dimensions: ${width} x ${height}, bounds: [${minX}, ${minY}] to [${maxX}, ${maxY}]`);
    
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
        .attr('stroke-width', THEME.topicStrokeWidth);
    
    svg.append('text')
        .attr('x', centerX)
        .attr('y', centerY)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('fill', THEME.topicText)
        .attr('font-size', THEME.fontTopic)
        .attr('font-weight', 'bold')
        .text(spec.topic);
    
    // Draw attribute circles
    nodes.forEach(node => {
        svg.append('circle')
            .attr('cx', node.x)
            .attr('cy', node.y)
            .attr('r', node.radius)
            .attr('fill', THEME.attributeFill)
            .attr('stroke', THEME.attributeStroke)
            .attr('stroke-width', THEME.attributeStrokeWidth);
        
        svg.append('text')
            .attr('x', node.x)
            .attr('y', node.y)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.attributeText)
            .attr('font-size', THEME.fontAttribute)
            .text(node.text);
    });
    
    // Add watermark in lower right corner - matching original d3-renderers.js
    const watermarkText = 'MindGraph';
    
    // Calculate dynamic padding and font size like original
    const watermarkPadding = Math.max(5, Math.min(15, Math.min(width, height) * 0.01));
    const watermarkFontSize = Math.max(8, Math.min(16, Math.min(width, height) * 0.02));
    
    const watermarkX = maxX - watermarkPadding;
    const watermarkY = maxY - watermarkPadding;
    
    svg.append('text')
        .attr('x', watermarkX)
        .attr('y', watermarkY)
        .attr('text-anchor', 'end')
        .attr('dominant-baseline', 'alphabetic')
        .attr('fill', '#2c3e50')  // Original dark blue-grey color
        .attr('font-size', watermarkFontSize)
        .attr('font-family', 'Inter, Segoe UI, sans-serif')
        .attr('font-weight', '500')
        .attr('opacity', 0.8)     // Original 80% opacity
        .attr('pointer-events', 'none')
        .text(watermarkText);
}

function renderCircleMap(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    if (!spec || !spec.topic || !Array.isArray(spec.context)) {
        console.error('Invalid spec for circle_map');
        return;
    }
    
    // Use provided theme and dimensions or defaults
    const baseWidth = dimensions?.baseWidth || 700;
    const baseHeight = dimensions?.baseHeight || 500;
    const padding = dimensions?.padding || 40;
    
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
    
    // Draw outer circle first (background boundary)
    svg.append('circle')
        .attr('cx', centerX)
        .attr('cy', centerY)
        .attr('r', outerCircleR)
        .attr('fill', THEME.outerCircleFill)
        .attr('stroke', THEME.outerCircleStroke)
        .attr('stroke-width', THEME.outerCircleStrokeWidth);
    
    // Draw context circles around the perimeter
    nodes.forEach(node => {
        svg.append('circle')
            .attr('cx', node.x)
            .attr('cy', node.y)
            .attr('r', node.radius)
            .attr('fill', THEME.contextFill)
            .attr('stroke', THEME.contextStroke)
            .attr('stroke-width', THEME.contextStrokeWidth);
        
        svg.append('text')
            .attr('x', node.x)
            .attr('y', node.y)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.contextText)
            .attr('font-size', THEME.fontContext)
            .text(node.text);
    });
    
    // Draw topic circle at center
    svg.append('circle')
        .attr('cx', centerX)
        .attr('cy', centerY)
        .attr('r', topicR)
        .attr('fill', THEME.topicFill)
        .attr('stroke', THEME.topicStroke)
        .attr('stroke-width', THEME.topicStrokeWidth);
    
    // Draw topic text on top
    svg.append('text')
        .attr('x', centerX)
        .attr('y', centerY)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('fill', THEME.topicText)
        .attr('font-size', THEME.fontTopic)
        .attr('font-weight', 'bold')
        .text(spec.topic);
    
    // Add watermark in lower right corner - matching original d3-renderers.js
    const watermarkText = 'MindGraph';
    
    // Calculate dynamic padding and font size like original
    const watermarkPadding = Math.max(5, Math.min(15, Math.min(width, height) * 0.01));
    const watermarkFontSize = Math.max(8, Math.min(16, Math.min(width, height) * 0.02));
    
    const watermarkX = maxX - watermarkPadding;
    const watermarkY = maxY - watermarkPadding;
    
    svg.append('text')
        .attr('x', watermarkX)
        .attr('y', watermarkY)
        .attr('text-anchor', 'end')
        .attr('dominant-baseline', 'alphabetic')
        .attr('fill', '#2c3e50')  // Original dark blue-grey color
        .attr('font-size', watermarkFontSize)
        .attr('font-family', 'Inter, Segoe UI, sans-serif')
        .attr('font-weight', '500')
        .attr('opacity', 0.8)     // Original 80% opacity
        .attr('pointer-events', 'none')
        .text(watermarkText);
}

function renderDoubleBubbleMap(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    
    // Enhanced validation with detailed error messages
    if (!spec) {
        console.error('renderDoubleBubbleMap: spec is null or undefined');

        return;
    }
    
    if (!spec.left || !spec.right) {
        console.error('renderDoubleBubbleMap: missing left or right topic', { left: spec.left, right: spec.right });

        return;
    }
    
    if (!Array.isArray(spec.similarities)) {
        console.error('renderDoubleBubbleMap: similarities is not an array', spec.similarities);

        return;
    }
    
    if (!Array.isArray(spec.left_differences)) {
        console.error('renderDoubleBubbleMap: left_differences is not an array', spec.left_differences);

        return;
    }
    
    if (!Array.isArray(spec.right_differences)) {
        console.error('renderDoubleBubbleMap: right_differences is not an array', spec.right_differences);

        return;
    }
    
    // Validation passed, proceeding with rendering
    
    const baseWidth = dimensions?.baseWidth || 800;
    
    // Apply background if specified (like bubble map)
    if (theme && theme.background) {
        // Setting container background to theme background
        d3.select('#d3-container').style('background-color', theme.background);
    }
    const baseHeight = dimensions?.baseHeight || 600;
    const padding = dimensions?.padding || 40;
    
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
    
    const simR = Math.max(...spec.similarities.map(t => getTextRadius(t, THEME.fontAttribute, 10)), 28);
    const leftDiffR = Math.max(...spec.left_differences.map(t => getTextRadius(t, THEME.fontAttribute, 8)), 24);
    const rightDiffR = Math.max(...spec.right_differences.map(t => getTextRadius(t, THEME.fontAttribute, 8)), 24);
    
    // Calculate counts
    const simCount = spec.similarities.length;
    const leftDiffCount = spec.left_differences.length;
    const rightDiffCount = spec.right_differences.length;
    
    // Calculate column heights
    const simColHeight = simCount > 0 ? (simCount - 1) * (simR * 2 + 12) + simR * 2 : 0;
    const leftColHeight = leftDiffCount > 0 ? (leftDiffCount - 1) * (leftDiffR * 2 + 10) + leftDiffR * 2 : 0;
    const rightColHeight = rightDiffCount > 0 ? (rightDiffCount - 1) * (rightDiffR * 2 + 10) + rightDiffR * 2 : 0;
    const maxColHeight = Math.max(simColHeight, leftColHeight, rightColHeight, topicR * 2);
    const height = Math.max(baseHeight, maxColHeight + padding * 2);
    
    // Position columns with 50px spacing between them (matching original)
    const columnSpacing = 50;
    const leftDiffX = padding + leftDiffR;
    const leftTopicX = leftDiffX + leftDiffR + columnSpacing + topicR;
    const simX = leftTopicX + topicR + columnSpacing + simR;
    const rightTopicX = simX + simR + columnSpacing + topicR;
    const rightDiffX = rightTopicX + topicR + columnSpacing + rightDiffR;
    
    // Calculate width to accommodate all columns
    const requiredWidth = rightDiffX + rightDiffR + padding * 2;
    const width = Math.max(baseWidth, requiredWidth);
    const topicY = height / 2;
    
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
        .attr('opacity', 0.9)
        .attr('stroke', THEME.topicStroke)
        .attr('stroke-width', THEME.topicStrokeWidth);
    
    svg.append('text')
        .attr('x', leftTopicX)
        .attr('y', topicY)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('fill', THEME.topicText)
        .attr('font-size', THEME.fontTopic)
        .attr('font-weight', 600)
        .text(spec.left);
    
    // Draw right topic
    svg.append('circle')
        .attr('cx', rightTopicX)
        .attr('cy', topicY)
        .attr('r', topicR)
        .attr('fill', THEME.topicFill)
        .attr('opacity', 0.9)
        .attr('stroke', THEME.topicStroke)
        .attr('stroke-width', THEME.topicStrokeWidth);
    
    svg.append('text')
        .attr('x', rightTopicX)
        .attr('y', topicY)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('fill', THEME.topicText)
        .attr('font-size', THEME.fontTopic)
        .attr('font-weight', 600)
        .text(spec.right);
    
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
                .attr('stroke-width', THEME.simStrokeWidth);
            
            svg.append('text')
                .attr('x', simX)
                .attr('y', y)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', THEME.simText)
                .attr('font-size', THEME.fontSim)
                .text(item);
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
                .attr('stroke-width', THEME.diffStrokeWidth);
            
            svg.append('text')
                .attr('x', leftDiffX)
                .attr('y', y)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', THEME.diffText)
                .attr('font-size', THEME.fontDiff)
                .text(item);
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
                .attr('stroke-width', THEME.diffStrokeWidth);
            
            svg.append('text')
                .attr('x', rightDiffX)
                .attr('y', y)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', THEME.diffText)
                .attr('font-size', THEME.fontDiff)
                .text(item);
        });
    }
    
    // Add watermark in lower right corner - using smaller size like circle map
    const watermarkText = 'MindGraph';
    
    // Calculate dynamic padding and font size (smaller like circle map for better proportion)
    const watermarkPadding = Math.max(5, Math.min(15, Math.min(width, height) * 0.01));
    const watermarkFontSize = Math.max(8, Math.min(16, Math.min(width, height) * 0.02));
    
    const watermarkX = width - watermarkPadding;
    const watermarkY = height - watermarkPadding;
    
    svg.append('text')
        .attr('x', watermarkX)
        .attr('y', watermarkY)
        .attr('text-anchor', 'end')
        .attr('dominant-baseline', 'alphabetic')
        .attr('fill', '#2c3e50')  // Original dark blue-grey color
        .attr('font-size', watermarkFontSize)
        .attr('font-family', 'Inter, Segoe UI, sans-serif')
        .attr('font-weight', '500')
        .attr('opacity', 0.8)     // Original 80% opacity
        .attr('pointer-events', 'none')
        .text(watermarkText);
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
