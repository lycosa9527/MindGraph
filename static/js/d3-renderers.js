// D3.js Renderers for D3.js_Dify Application
// This file contains all the D3.js rendering functions for different graph types

// --- Safe, memory-leak-free text radius measurement ---
const measurementContainer = d3.select('body')
    .append('div')
    .attr('id', 'measurement-container')
    .style('position', 'absolute')
    .style('visibility', 'hidden')
    .style('pointer-events', 'none');

function getTextRadius(text, fontSize, padding) {
    let textElement = null;
    try {
        textElement = measurementContainer
            .append('svg')
            .append('text')
            .attr('font-size', fontSize)
            .text(text);
        const bbox = textElement.node().getBBox();
        const radius = Math.ceil(Math.sqrt(bbox.width * bbox.width + bbox.height * bbox.height) / 2 + (padding || 12));
        return Math.max(radius, 30); // Minimum radius
    } catch (error) {
        console.error('Error calculating text radius:', error);
        return 30; // Default fallback
    } finally {
        if (textElement) {
            textElement.remove();
        }
    }
}

window.addEventListener('beforeunload', () => {
    measurementContainer.remove();
});

// --- End safe text radius ---

// Helper function to get watermark text from theme or use default
function getWatermarkText(theme = null) {
    return theme?.watermarkText || 'MindSpring';
}

// Helper function to add watermark with proper positioning and styling
function addWatermark(svg, theme = null) {
    const watermarkText = getWatermarkText(theme);
    const w = +svg.attr('width');
    const h = +svg.attr('height');
    
    // Check if SVG uses viewBox
    const viewBox = svg.attr('viewBox');
    let watermarkX, watermarkY, watermarkFontSize;
    
    if (viewBox) {
        // SVG uses viewBox - position within viewBox coordinate system
        const viewBoxParts = viewBox.split(' ').map(Number);
        const viewBoxWidth = viewBoxParts[2];
        const viewBoxHeight = viewBoxParts[3];
        
        // Calculate font size based on viewBox dimensions
        watermarkFontSize = Math.max(8, Math.min(16, Math.min(viewBoxWidth, viewBoxHeight) * 0.02));
        
        // Calculate padding based on viewBox size
        const padding = Math.max(5, Math.min(15, Math.min(viewBoxWidth, viewBoxHeight) * 0.01));
        
        // Position in lower right corner of viewBox
        watermarkX = viewBoxParts[0] + viewBoxWidth - padding;
        watermarkY = viewBoxParts[1] + viewBoxHeight - padding;
    } else {
        // SVG uses standard coordinate system
        watermarkFontSize = Math.max(12, Math.min(20, Math.min(w, h) * 0.025));
        const padding = Math.max(10, Math.min(20, Math.min(w, h) * 0.02));
        watermarkX = w - padding;
        watermarkY = h - padding;
    }
    
    // Add watermark with proper styling
    svg.append('text')
        .attr('x', watermarkX)
        .attr('y', watermarkY)
        .attr('text-anchor', 'end')
        .attr('dominant-baseline', 'alphabetic')
        .attr('fill', '#2c3e50')
        .attr('font-size', watermarkFontSize)
        .attr('font-family', 'Inter, Segoe UI, sans-serif')
        .attr('font-weight', '500')
        .attr('opacity', 0.8)
        .attr('pointer-events', 'none')
        .text(watermarkText);
}

function renderDoubleBubbleMap(spec, theme = null, dimensions = null) {
    console.log('renderDoubleBubbleMap called with:', { spec, theme, dimensions });
    
    d3.select('#d3-container').html('');
    
    // Enhanced validation with detailed error messages
    if (!spec) {
        console.error('renderDoubleBubbleMap: spec is null or undefined');
        d3.select('#d3-container').append('div').style('color', 'red').text('Error: No specification provided');
        return;
    }
    
    if (!spec.left || !spec.right) {
        console.error('renderDoubleBubbleMap: missing left or right topic', { left: spec.left, right: spec.right });
        d3.select('#d3-container').append('div').style('color', 'red').text('Error: Missing left or right topic');
        return;
    }
    
    if (!Array.isArray(spec.similarities)) {
        console.error('renderDoubleBubbleMap: similarities is not an array', spec.similarities);
        d3.select('#d3-container').append('div').style('color', 'red').text('Error: Similarities must be an array');
        return;
    }
    
    if (!Array.isArray(spec.left_differences)) {
        console.error('renderDoubleBubbleMap: left_differences is not an array', spec.left_differences);
        d3.select('#d3-container').append('div').style('color', 'red').text('Error: Left differences must be an array');
        return;
    }
    
    if (!Array.isArray(spec.right_differences)) {
        console.error('renderDoubleBubbleMap: right_differences is not an array', spec.right_differences);
        d3.select('#d3-container').append('div').style('color', 'red').text('Error: Right differences must be an array');
        return;
    }
    
    console.log('renderDoubleBubbleMap: validation passed, proceeding with rendering');
    
    // Use provided theme and dimensions or defaults
    const baseWidth = dimensions?.baseWidth || 700;
    const baseHeight = dimensions?.baseHeight || 500;
    const padding = dimensions?.padding || 40;
    
    // Map integrated styles to theme structure
    const THEME = {
        topicFill: '#4e79a7',
        topicText: '#fff',
        topicStroke: '#35506b',
        topicStrokeWidth: 3,
        simFill: '#a7c7e7',
        simText: '#333',
        simStroke: '#4e79a7',
        simStrokeWidth: 2,
        diffFill: '#f4f6fb',
        diffText: '#4e79a7',
        diffStroke: '#4e79a7',
        diffStrokeWidth: 2,
        fontTopic: 18,
        fontSim: 14,
        fontDiff: 13,
        ...theme
    };
    
    // Apply integrated styles if available
    if (theme) {
        // Map style properties to theme structure
        if (theme.leftTopicColor) THEME.topicFill = theme.leftTopicColor;
        if (theme.topicTextColor) THEME.topicText = theme.topicTextColor;
        if (theme.stroke) THEME.topicStroke = theme.stroke;
        if (theme.strokeWidth) THEME.topicStrokeWidth = theme.strokeWidth;
        if (theme.similarityColor) THEME.simFill = theme.similarityColor;
        if (theme.similarityTextColor) THEME.simText = theme.similarityTextColor;
        if (theme.leftDiffColor) THEME.diffFill = theme.leftDiffColor;
        if (theme.diffTextColor) THEME.diffText = theme.diffTextColor;
        if (theme.topicFontSize) THEME.fontTopic = theme.topicFontSize;
        if (theme.similarityFontSize) THEME.fontSim = theme.similarityFontSize;
        if (theme.diffFontSize) THEME.fontDiff = theme.diffFontSize;
        
        // Apply background if specified
        if (theme.background) {
            d3.select('#d3-container').style('background-color', theme.background);
        }
    }
    
    console.log('renderDoubleBubbleMap: using theme:', THEME);
    
    const leftTopicR = getTextRadius(spec.left, THEME.fontTopic, 18);
    const rightTopicR = getTextRadius(spec.right, THEME.fontTopic, 18);
    const topicR = Math.max(leftTopicR, rightTopicR, 60);
    
    const simFontSize = THEME.fontSim, diffFontSize = THEME.fontDiff;
    const simR = Math.max(...spec.similarities.map(t => getTextRadius(t, simFontSize, 10)), 28);
    const leftDiffR = Math.max(...spec.left_differences.map(t => getTextRadius(t, diffFontSize, 8)), 24);
    const rightDiffR = Math.max(...spec.right_differences.map(t => getTextRadius(t, diffFontSize, 8)), 24);
    
    console.log('renderDoubleBubbleMap: calculated radii:', { leftTopicR, rightTopicR, topicR, simR, leftDiffR, rightDiffR });
    
    const simCount = spec.similarities.length;
    const leftDiffCount = spec.left_differences.length;
    const rightDiffCount = spec.right_differences.length;
    
    console.log('renderDoubleBubbleMap: counts:', { simCount, leftDiffCount, rightDiffCount });
    
    const simColHeight = simCount > 0 ? (simCount - 1) * (simR * 2 + 12) + simR * 2 : 0;
    const leftColHeight = leftDiffCount > 0 ? (leftDiffCount - 1) * (leftDiffR * 2 + 10) + leftDiffR * 2 : 0;
    const rightColHeight = rightDiffCount > 0 ? (rightDiffCount - 1) * (rightDiffR * 2 + 10) + rightDiffR * 2 : 0;
    const maxColHeight = Math.max(simColHeight, leftColHeight, rightColHeight, topicR * 2);
    const height = Math.max(baseHeight, maxColHeight + padding * 2);
    
    const leftX = padding + topicR;
    const rightX = baseWidth - padding - topicR;
    const simX = (leftX + rightX) / 2;
    const leftDiffX = leftX - topicR - 90;
    const rightDiffX = rightX + topicR + 90;
    
    const minX = Math.min(leftDiffX - leftDiffR, leftX - topicR, simX - simR, rightX - topicR, rightDiffX - rightDiffR) - padding;
    const maxX = Math.max(leftDiffX + leftDiffR, leftX + topicR, simX + simR, rightX + topicR, rightDiffX + rightDiffR) + padding;
    const width = Math.max(baseWidth, maxX - minX);
    const topicY = height / 2;
    
    console.log('renderDoubleBubbleMap: layout calculated:', { width, height, leftX, rightX, simX, leftDiffX, rightDiffX, topicY });
    
    const svg = d3.select('#d3-container').append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `${minX} 0 ${width} ${height}`)
        .attr('preserveAspectRatio', 'xMinYMin meet');
    
    console.log('renderDoubleBubbleMap: SVG created');
    
    // Draw all lines first
    const simStartY = topicY - ((simCount - 1) * (simR * 2 + 12)) / 2;
    for (let i = 0; i < simCount; i++) {
        const y = simStartY + i * (simR * 2 + 12);
        let dxL = leftX - simX, dyL = topicY - y, distL = Math.sqrt(dxL * dxL + dyL * dyL);
        let x1L = simX + (dxL / distL) * simR, y1L = y + (dyL / distL) * simR;
        let x2L = leftX - (dxL / distL) * topicR, y2L = topicY - (dyL / distL) * topicR;
        svg.append('line').attr('x1', x1L).attr('y1', y1L).attr('x2', x2L).attr('y2', y2L)
            .attr('stroke', '#888').attr('stroke-width', 2);
        
        let dxR = rightX - simX, dyR = topicY - y, distR = Math.sqrt(dxR * dxR + dyR * dyR);
        let x1R = simX + (dxR / distR) * simR, y1R = y + (dyR / distR) * simR;
        let x2R = rightX - (dxR / distR) * topicR, y2R = topicY - (dyR / distR) * topicR;
        svg.append('line').attr('x1', x1R).attr('y1', y1R).attr('x2', x2R).attr('y2', y2R)
            .attr('stroke', '#888').attr('stroke-width', 2);
    }
    
    const leftDiffStartY = topicY - ((leftDiffCount - 1) * (leftDiffR * 2 + 10)) / 2;
    for (let i = 0; i < leftDiffCount; i++) {
        const y = leftDiffStartY + i * (leftDiffR * 2 + 10);
        let dx = leftX - leftDiffX, dy = topicY - y, dist = Math.sqrt(dx * dx + dy * dy);
        let x1 = leftDiffX + (dx / dist) * leftDiffR, y1 = y + (dy / dist) * leftDiffR;
        let x2 = leftX - (dx / dist) * topicR, y2 = topicY - (dy / dist) * topicR;
        svg.append('line').attr('x1', x1).attr('y1', y1).attr('x2', x2).attr('y2', y2)
            .attr('stroke', '#bbb').attr('stroke-width', 2);
    }
    
    const rightDiffStartY = topicY - ((rightDiffCount - 1) * (rightDiffR * 2 + 10)) / 2;
    for (let i = 0; i < rightDiffCount; i++) {
        const y = rightDiffStartY + i * (rightDiffR * 2 + 10);
        let dx = rightX - rightDiffX, dy = topicY - y, dist = Math.sqrt(dx * dx + dy * dy);
        let x1 = rightDiffX + (dx / dist) * rightDiffR, y1 = y + (dy / dist) * rightDiffR;
        let x2 = rightX - (dx / dist) * topicR, y2 = topicY - (dy / dist) * topicR;
        svg.append('line').attr('x1', x1).attr('y1', y1).attr('x2', x2).attr('y2', y2)
            .attr('stroke', '#bbb').attr('stroke-width', 2);
    }
    
    // Draw all circles next
    svg.append('circle').attr('cx', leftX).attr('cy', topicY).attr('r', topicR)
        .attr('fill', THEME.topicFill).attr('opacity', 0.9)
        .attr('stroke', THEME.topicStroke).attr('stroke-width', THEME.topicStrokeWidth);
    svg.append('circle').attr('cx', rightX).attr('cy', topicY).attr('r', topicR)
        .attr('fill', THEME.topicFill).attr('opacity', 0.9)
        .attr('stroke', THEME.topicStroke).attr('stroke-width', THEME.topicStrokeWidth);
    
    for (let i = 0; i < simCount; i++) {
        const y = simStartY + i * (simR * 2 + 12);
        svg.append('circle').attr('cx', simX).attr('cy', y).attr('r', simR)
            .attr('fill', THEME.simFill).attr('stroke', THEME.simStroke).attr('stroke-width', THEME.simStrokeWidth);
    }
    
    for (let i = 0; i < leftDiffCount; i++) {
        const y = leftDiffStartY + i * (leftDiffR * 2 + 10);
        svg.append('circle').attr('cx', leftDiffX).attr('cy', y).attr('r', leftDiffR)
            .attr('fill', THEME.diffFill).attr('stroke', THEME.diffStroke).attr('stroke-width', THEME.diffStrokeWidth);
    }
    
    for (let i = 0; i < rightDiffCount; i++) {
        const y = rightDiffStartY + i * (rightDiffR * 2 + 10);
        svg.append('circle').attr('cx', rightDiffX).attr('cy', y).attr('r', rightDiffR)
            .attr('fill', THEME.diffFill).attr('stroke', THEME.diffStroke).attr('stroke-width', THEME.diffStrokeWidth);
    }
    
    // Draw all text last
    svg.append('text').attr('x', leftX).attr('y', topicY)
        .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
        .attr('fill', THEME.topicText).attr('font-size', THEME.fontTopic).attr('font-weight', 600)
        .text(spec.left);
    svg.append('text').attr('x', rightX).attr('y', topicY)
        .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
        .attr('fill', THEME.topicText).attr('font-size', THEME.fontTopic).attr('font-weight', 600)
        .text(spec.right);
    
    for (let i = 0; i < simCount; i++) {
        const y = simStartY + i * (simR * 2 + 12);
        svg.append('text').attr('x', simX).attr('y', y)
            .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
            .attr('fill', THEME.simText).attr('font-size', THEME.fontSim)
            .text(spec.similarities[i]);
    }
    
    for (let i = 0; i < leftDiffCount; i++) {
        const y = leftDiffStartY + i * (leftDiffR * 2 + 10);
        svg.append('text').attr('x', leftDiffX).attr('y', y)
            .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
            .attr('fill', THEME.diffText).attr('font-size', THEME.fontDiff)
            .text(spec.left_differences[i]);
    }
    
    for (let i = 0; i < rightDiffCount; i++) {
        const y = rightDiffStartY + i * (rightDiffR * 2 + 10);
        svg.append('text').attr('x', rightDiffX).attr('y', y)
            .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
            .attr('fill', THEME.diffText).attr('font-size', THEME.fontDiff)
            .text(spec.right_differences[i]);
    }
    
    // Watermark
    addWatermark(svg, theme);
}

function renderBubbleMap(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    if (!spec || !spec.topic || !Array.isArray(spec.attributes)) {
        d3.select('#d3-container').append('div').style('color', 'red').text('Invalid spec for bubble_map');
        return;
    }
    
    // Use provided theme and dimensions or defaults
    const baseWidth = dimensions?.baseWidth || 700;
    const baseHeight = dimensions?.baseHeight || 500;
    const padding = dimensions?.padding || 40;
    
    const THEME = {
        topicFill: '#4e79a7',
        topicText: '#fff',
        topicStroke: '#35506b',
        topicStrokeWidth: 3,
        attributeFill: '#a7c7e7',
        attributeText: '#333',
        attributeStroke: '#4e79a7',
        attributeStrokeWidth: 2,
        fontTopic: 20,
        fontAttribute: 14,
        ...theme
    };
    
    // Apply integrated styles if available
    if (theme) {
        // Map style properties to theme structure
        if (theme.topicColor) THEME.topicFill = theme.topicColor;
        if (theme.topicTextColor) THEME.topicText = theme.topicTextColor;
        if (theme.stroke) THEME.topicStroke = theme.stroke;
        if (theme.strokeWidth) THEME.topicStrokeWidth = theme.strokeWidth;
        if (theme.charColor) THEME.attributeFill = theme.charColor;
        if (theme.charTextColor) THEME.attributeText = theme.charTextColor;
        if (theme.topicFontSize) THEME.fontTopic = theme.topicFontSize;
        if (theme.charFontSize) THEME.fontAttribute = theme.charFontSize;
        
        // Apply background if specified
        if (theme.background) {
            d3.select('#d3-container').style('background-color', theme.background);
        }
    }
    
    // Calculate sizes
    const topicR = getTextRadius(spec.topic, THEME.fontTopic, 20);
    
    // Calculate uniform radius for all attribute nodes
    const attributeRadii = spec.attributes.map(t => getTextRadius(t, THEME.fontAttribute, 10));
    const uniformAttributeR = Math.max(...attributeRadii, 30); // Use the largest required radius for all
    
    // Calculate layout with collision detection
    const centerX = baseWidth / 2;
    const centerY = baseHeight / 2;
    
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
    
    // Watermark
    addWatermark(svg, theme);
}

function renderCircleMap(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    if (!spec || !spec.topic || !Array.isArray(spec.context)) {
        d3.select('#d3-container').append('div').style('color', 'red').text('Invalid spec for circle_map');
        return;
    }
    
    // Use provided theme and dimensions or defaults
    const baseWidth = dimensions?.baseWidth || 700;
    const baseHeight = dimensions?.baseHeight || 500;
    const padding = dimensions?.padding || 40;
    
    const THEME = {
        outerCircleFill: 'none',
        outerCircleStroke: '#2c3e50',
        outerCircleStrokeWidth: 2,
        topicFill: '#4e79a7',
        topicText: '#fff',
        topicStroke: '#35506b',
        topicStrokeWidth: 3,
        contextFill: '#a7c7e7',
        contextText: '#333',
        contextStroke: '#2c3e50',
        contextStrokeWidth: 2,
        fontTopic: 20,
        fontContext: 14,
        ...theme
    };
    
    // Calculate uniform radius for all context nodes
    const contextRadii = spec.context.map(t => getTextRadius(t, THEME.fontContext, 10));
    const uniformContextR = Math.max(...contextRadii, 30); // Use the largest required radius for all
    
    // Calculate topic circle size (made smaller)
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
    
    // Watermark
    addWatermark(svg, theme);
}

function renderTreeMap(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    const width = dimensions?.baseWidth || 400;
    const height = dimensions?.baseHeight || 300;
    var svg = d3.select('#d3-container').append('svg').attr('width', width).attr('height', height);
    svg.append('text').attr('x', width/2).attr('y', height/2).attr('text-anchor', 'middle')
        .attr('fill', '#333').attr('font-size', 24).text('Tree Map: ' + spec.topic);
    
    // Watermark
    addWatermark(svg, theme);
}

function renderConceptMap(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    const width = dimensions?.baseWidth || 400;
    const height = dimensions?.baseHeight || 300;
    var svg = d3.select('#d3-container').append('svg').attr('width', width).attr('height', height);
    svg.append('text').attr('x', width/2).attr('y', height/2).attr('text-anchor', 'middle')
        .attr('fill', '#333').attr('font-size', 24).text('Concept Map: ' + spec.topic);
    
    // Watermark
    addWatermark(svg, theme);
}

function renderMindMap(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    if (!spec || !spec.topic || !Array.isArray(spec.children)) {
        d3.select('#d3-container').append('div').style('color', 'red').text('Invalid spec for mindmap');
        return;
    }
    
    // Use provided theme and dimensions or defaults
    const baseWidth = dimensions?.baseWidth || 700;
    const baseHeight = dimensions?.baseHeight || 500;
    const padding = dimensions?.padding || 40;
    
    const THEME = {
        centralTopicFill: '#4e79a7',
        centralTopicText: '#fff',
        centralTopicStroke: '#35506b',
        centralTopicStrokeWidth: 3,
        mainBranchFill: '#a7c7e7',
        mainBranchText: '#333',
        mainBranchStroke: '#4e79a7',
        mainBranchStrokeWidth: 2,
        subBranchFill: '#f4f6fb',
        subBranchText: '#333',
        subBranchStroke: '#4e79a7',
        subBranchStrokeWidth: 1,
        fontCentralTopic: 20,
        fontMainBranch: 16,
        fontSubBranch: 14,
        ...theme
    };
    
    // Apply integrated styles if available
    if (theme) {
        // Map style properties to theme structure
        if (theme.centralTopicColor) THEME.centralTopicFill = theme.centralTopicColor;
        if (theme.centralTopicTextColor) THEME.centralTopicText = theme.centralTopicTextColor;
        if (theme.stroke) THEME.centralTopicStroke = theme.stroke;
        if (theme.strokeWidth) THEME.centralTopicStrokeWidth = theme.strokeWidth;
        if (theme.mainBranchColor) THEME.mainBranchFill = theme.mainBranchColor;
        if (theme.mainBranchTextColor) THEME.mainBranchText = theme.mainBranchTextColor;
        if (theme.subBranchColor) THEME.subBranchFill = theme.subBranchColor;
        if (theme.subBranchTextColor) THEME.subBranchText = theme.subBranchTextColor;
        if (theme.centralTopicFontSize) THEME.fontCentralTopic = theme.centralTopicFontSize;
        if (theme.mainBranchFontSize) THEME.fontMainBranch = theme.mainBranchFontSize;
        if (theme.subBranchFontSize) THEME.fontSubBranch = theme.subBranchFontSize;
        
        // Apply background if specified
        if (theme.background) {
            d3.select('#d3-container').style('background-color', theme.background);
        }
    }
    
    const width = baseWidth;
    const height = baseHeight;
    var svg = d3.select('#d3-container').append('svg').attr('width', width).attr('height', height);
    
    // Draw central topic
    const centerX = width / 2;
    const centerY = height / 2;
    const centralRadius = getTextRadius(spec.topic, THEME.fontCentralTopic, 20);
    
    svg.append('circle')
        .attr('cx', centerX)
        .attr('cy', centerY)
        .attr('r', centralRadius)
        .attr('fill', THEME.centralTopicFill)
        .attr('stroke', THEME.centralTopicStroke)
        .attr('stroke-width', THEME.centralTopicStrokeWidth);
    
    svg.append('text')
        .attr('x', centerX)
        .attr('y', centerY)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('fill', THEME.centralTopicText)
        .attr('font-size', THEME.fontCentralTopic)
        .attr('font-weight', 'bold')
        .text(spec.topic);
    
    // Draw branches (simplified implementation)
    const branchCount = spec.children.length;
    const angleStep = (2 * Math.PI) / branchCount;
    const branchRadius = 80;
    
    spec.children.forEach((child, i) => {
        const angle = i * angleStep;
        const branchX = centerX + branchRadius * Math.cos(angle);
        const branchY = centerY + branchRadius * Math.sin(angle);
        const branchNodeRadius = getTextRadius(child.label, THEME.fontMainBranch, 15);
        
        // Draw branch node
        svg.append('circle')
            .attr('cx', branchX)
            .attr('cy', branchY)
            .attr('r', branchNodeRadius)
            .attr('fill', THEME.mainBranchFill)
            .attr('stroke', THEME.mainBranchStroke)
            .attr('stroke-width', THEME.mainBranchStrokeWidth);
        
        svg.append('text')
            .attr('x', branchX)
            .attr('y', branchY)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.mainBranchText)
            .attr('font-size', THEME.fontMainBranch)
            .text(child.label);
        
        // Draw connecting line
        const dx = branchX - centerX;
        const dy = branchY - centerY;
        const dist = Math.sqrt(dx * dx + dy * dy);
        
        const lineStartX = centerX + (dx / dist) * centralRadius;
        const lineStartY = centerY + (dy / dist) * centralRadius;
        const lineEndX = branchX - (dx / dist) * branchNodeRadius;
        const lineEndY = branchY - (dy / dist) * branchNodeRadius;
        
        svg.append('line')
            .attr('x1', lineStartX)
            .attr('y1', lineStartY)
            .attr('x2', lineEndX)
            .attr('y2', lineEndY)
            .attr('stroke', '#888')
            .attr('stroke-width', 2);
    });
    
    // Watermark
    addWatermark(svg, theme);
}

function renderRadialMindMap(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    if (!spec || !spec.central_topic || !Array.isArray(spec.main_branches)) {
        d3.select('#d3-container').append('div').style('color', 'red').text('Invalid spec for radial_mindmap');
        return;
    }
    
    const width = dimensions?.baseWidth || 700;
    const height = dimensions?.baseHeight || 500;
    var svg = d3.select('#d3-container').append('svg').attr('width', width).attr('height', height);
    svg.append('text').attr('x', width/2).attr('y', height/2).attr('text-anchor', 'middle')
        .attr('fill', '#333').attr('font-size', 24).text('Radial Mind Map: ' + spec.central_topic);
    
    // Watermark
    addWatermark(svg, theme);
}

function renderVennDiagram(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    if (!spec || !Array.isArray(spec.sets)) {
        d3.select('#d3-container').append('div').style('color', 'red').text('Invalid spec for venn_diagram');
        return;
    }
    
    const width = dimensions?.baseWidth || 700;
    const height = dimensions?.baseHeight || 500;
    var svg = d3.select('#d3-container').append('svg').attr('width', width).attr('height', height);
    svg.append('text').attr('x', width/2).attr('y', height/2).attr('text-anchor', 'middle')
        .attr('fill', '#333').attr('font-size', 24).text('Venn Diagram: ' + spec.sets.length + ' sets');
    
    // Watermark
    addWatermark(svg, theme);
}

function renderFlowchart(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    if (!spec || !Array.isArray(spec.nodes) || !Array.isArray(spec.edges)) {
        d3.select('#d3-container').append('div').style('color', 'red').text('Invalid spec for flowchart');
        return;
    }
    
    const width = dimensions?.baseWidth || 700;
    const height = dimensions?.baseHeight || 500;
    var svg = d3.select('#d3-container').append('svg').attr('width', width).attr('height', height);
    svg.append('text').attr('x', width/2).attr('y', height/2).attr('text-anchor', 'middle')
        .attr('fill', '#333').attr('font-size', 24).text('Flowchart: ' + spec.nodes.length + ' nodes');
    
    // Watermark
    addWatermark(svg, theme);
}

function renderOrgChart(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    if (!spec || !spec.root) {
        d3.select('#d3-container').append('div').style('color', 'red').text('Invalid spec for org_chart');
        return;
    }
    
    const width = dimensions?.baseWidth || 700;
    const height = dimensions?.baseHeight || 500;
    var svg = d3.select('#d3-container').append('svg').attr('width', width).attr('height', height);
    svg.append('text').attr('x', width/2).attr('y', height/2).attr('text-anchor', 'middle')
        .attr('fill', '#333').attr('font-size', 24).text('Org Chart: ' + spec.root.label);
    
    // Watermark
    addWatermark(svg, theme);
}

function renderTimeline(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    if (!spec || !spec.title || !Array.isArray(spec.events)) {
        d3.select('#d3-container').append('div').style('color', 'red').text('Invalid spec for timeline');
        return;
    }
    
    const width = dimensions?.baseWidth || 700;
    const height = dimensions?.baseHeight || 500;
    var svg = d3.select('#d3-container').append('svg').attr('width', width).attr('height', height);
    svg.append('text').attr('x', width/2).attr('y', height/2).attr('text-anchor', 'middle')
        .attr('fill', '#333').attr('font-size', 24).text('Timeline: ' + spec.title);
    
    // Watermark
    addWatermark(svg, theme);
}

function renderBridgeMap(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    
    // Validate spec
    if (!spec || !spec.relating_factor || !Array.isArray(spec.analogies) || spec.analogies.length === 0) {
        d3.select('#d3-container').append('div').style('color', 'red').text('Invalid spec for bridge map');
        return;
    }
    
    // Set up dimensions
    const width = dimensions?.baseWidth || 800;
    const height = dimensions?.baseHeight || 600;
    const padding = 50;
    
    // Create SVG
    const svg = d3.select('#d3-container')
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `0 0 ${width} ${height}`);
    
    // Apply theme
    const THEME = theme || {
        backgroundColor: '#ffffff',
        relatingFactorColor: '#4e79a7',
        relatingFactorTextColor: '#ffffff',
        relatingFactorFontSize: 16,
        analogyColor: '#a7c7e7',
        analogyTextColor: '#2c3e50',
        analogyFontSize: 14,
        bridgeColor: '#2c3e50',
        bridgeWidth: 3,
        stroke: '#2c3e50',
        strokeWidth: 2
    };
    
    // Calculate layout
    const centerX = width / 2;
    const centerY = height / 2;
    const bridgeWidth = 200;
    const analogySpacing = 80;
    const totalHeight = (spec.analogies.length - 1) * analogySpacing;
    const startY = centerY - totalHeight / 2;
    
    // Draw bridge structure
    const bridgeGroup = svg.append('g').attr('class', 'bridge');
    
    // Draw horizontal bridge line
    bridgeGroup.append('line')
        .attr('x1', centerX - bridgeWidth / 2)
        .attr('y1', centerY)
        .attr('x2', centerX + bridgeWidth / 2)
        .attr('y2', centerY)
        .attr('stroke', THEME.bridgeColor)
        .attr('stroke-width', THEME.bridgeWidth);
    
    // Draw vertical support lines
    bridgeGroup.append('line')
        .attr('x1', centerX - bridgeWidth / 2)
        .attr('y1', centerY - 20)
        .attr('x2', centerX - bridgeWidth / 2)
        .attr('y2', centerY + 20)
        .attr('stroke', THEME.bridgeColor)
        .attr('stroke-width', THEME.bridgeWidth);
    
    bridgeGroup.append('line')
        .attr('x1', centerX + bridgeWidth / 2)
        .attr('y1', centerY - 20)
        .attr('x2', centerX + bridgeWidth / 2)
        .attr('y2', centerY + 20)
        .attr('stroke', THEME.bridgeColor)
        .attr('stroke-width', THEME.bridgeWidth);
    
    // Draw relating factor
    svg.append('text')
        .attr('x', centerX)
        .attr('y', centerY + 40)
        .attr('text-anchor', 'middle')
        .attr('fill', THEME.relatingFactorTextColor)
        .attr('font-size', THEME.relatingFactorFontSize)
        .attr('font-weight', 'bold')
        .text(spec.relating_factor);
    
    // Draw analogies
    spec.analogies.forEach((analogy, index) => {
        const y = startY + index * analogySpacing;
        
        // Left pair
        const leftGroup = svg.append('g').attr('class', 'left-pair');
        
        // Left top item
        leftGroup.append('circle')
            .attr('cx', centerX - bridgeWidth / 2 - 80)
            .attr('cy', y - 20)
            .attr('r', 30)
            .attr('fill', THEME.analogyColor)
            .attr('stroke', THEME.stroke)
            .attr('stroke-width', THEME.strokeWidth);
        
        leftGroup.append('text')
            .attr('x', centerX - bridgeWidth / 2 - 80)
            .attr('y', y - 20)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.analogyTextColor)
            .attr('font-size', THEME.analogyFontSize)
            .text(analogy.left_pair.top);
        
        // Left bottom item
        leftGroup.append('circle')
            .attr('cx', centerX - bridgeWidth / 2 - 80)
            .attr('cy', y + 20)
            .attr('r', 30)
            .attr('fill', THEME.analogyColor)
            .attr('stroke', THEME.stroke)
            .attr('stroke-width', THEME.strokeWidth);
        
        leftGroup.append('text')
            .attr('x', centerX - bridgeWidth / 2 - 80)
            .attr('y', y + 20)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.analogyTextColor)
            .attr('font-size', THEME.analogyFontSize)
            .text(analogy.left_pair.bottom);
        
        // Right pair
        const rightGroup = svg.append('g').attr('class', 'right-pair');
        
        // Right top item
        rightGroup.append('circle')
            .attr('cx', centerX + bridgeWidth / 2 + 80)
            .attr('cy', y - 20)
            .attr('r', 30)
            .attr('fill', THEME.analogyColor)
            .attr('stroke', THEME.stroke)
            .attr('stroke-width', THEME.strokeWidth);
        
        rightGroup.append('text')
            .attr('x', centerX + bridgeWidth / 2 + 80)
            .attr('y', y - 20)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.analogyTextColor)
            .attr('font-size', THEME.analogyFontSize)
            .text(analogy.right_pair.top);
        
        // Right bottom item
        rightGroup.append('circle')
            .attr('cx', centerX + bridgeWidth / 2 + 80)
            .attr('cy', y + 20)
            .attr('r', 30)
            .attr('fill', THEME.analogyColor)
            .attr('stroke', THEME.stroke)
            .attr('stroke-width', THEME.strokeWidth);
        
        rightGroup.append('text')
            .attr('x', centerX + bridgeWidth / 2 + 80)
            .attr('y', y + 20)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.analogyTextColor)
            .attr('font-size', THEME.analogyFontSize)
            .text(analogy.right_pair.bottom);
    });
    
    // Watermark
    addWatermark(svg, theme);
}

function renderGraph(type, spec, theme = null, dimensions = null) {
    console.log('renderGraph called with:', { type, spec, theme, dimensions });
    
    // Extract style information from spec if available
    let integratedTheme = theme;
    if (spec && spec._style) {
        console.log('Using integrated styles from spec:', spec._style);
        integratedTheme = spec._style;
    }
    
    // Extract style metadata for debugging
    if (spec && spec._style_metadata) {
        console.log('Style metadata:', spec._style_metadata);
    }
    
    switch (type) {
        case 'double_bubble_map':
            renderDoubleBubbleMap(spec, integratedTheme, dimensions);
            break;
        case 'bubble_map':
            renderBubbleMap(spec, integratedTheme, dimensions);
            break;
        case 'circle_map':
            renderCircleMap(spec, integratedTheme, dimensions);
            break;
        case 'tree_map':
            renderTreeMap(spec, integratedTheme, dimensions);
            break;
        case 'concept_map':
            renderConceptMap(spec, integratedTheme, dimensions);
            break;
        case 'mindmap':
            renderMindMap(spec, integratedTheme, dimensions);
            break;
        case 'radial_mindmap':
            renderRadialMindMap(spec, integratedTheme, dimensions);
            break;
        case 'venn_diagram':
            renderVennDiagram(spec, integratedTheme, dimensions);
            break;
        case 'flowchart':
            renderFlowchart(spec, integratedTheme, dimensions);
            break;
        case 'org_chart':
            renderOrgChart(spec, integratedTheme, dimensions);
            break;
        case 'timeline':
            renderTimeline(spec, integratedTheme, dimensions);
            break;
        case 'bridge_map':
            renderBridgeMap(spec, integratedTheme, dimensions);
            break;
        default:
            console.error('Unknown graph type:', type);
            d3.select('#d3-container').append('div')
                .style('color', 'red')
                .text(`Error: Unknown graph type: ${type}`);
    }
} 