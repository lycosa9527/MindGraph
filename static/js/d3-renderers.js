// D3.js Renderers for MindGraph Application
// This file contains all the D3.js rendering functions for different graph types

// --- Safe, memory-leak-free text radius measurement ---
let measurementContainer = null;

function getMeasurementContainer() {
    if (!measurementContainer) {
        const body = d3.select('body');
        if (body.empty()) {
            console.warn('Body element not found, creating measurement container in document');
            measurementContainer = d3.select(document.documentElement)
                .append('div')
                .attr('id', 'measurement-container')
                .style('position', 'absolute')
                .style('visibility', 'hidden')
                .style('pointer-events', 'none');
        } else {
            measurementContainer = body
                .append('div')
                .attr('id', 'measurement-container')
                .style('position', 'absolute')
                .style('visibility', 'hidden')
                .style('pointer-events', 'none');
        }
    }
    return measurementContainer;
}

function getTextRadius(text, fontSize, padding) {
    let textElement = null;
    try {
        const container = getMeasurementContainer();
        textElement = container
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

// Cleanup function for measurement container
function cleanupMeasurementContainer() {
    if (measurementContainer) {
        measurementContainer.remove();
        measurementContainer = null;
    }
}

// Add cleanup on page unload if window is available
if (typeof window !== 'undefined') {
    window.addEventListener('beforeunload', cleanupMeasurementContainer);
}

// --- End safe text radius ---

// Helper function to get watermark text from theme or use default
function getWatermarkText(theme = null) {
    return theme?.watermarkText || 'MindGraph';
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
    
    // Get complete theme using centralized configuration
    let THEME;
    try {
        // Use centralized theme configuration if available
        if (typeof getD3Theme === 'function') {
            THEME = getD3Theme('double_bubble_map');
            console.log('Using centralized theme configuration for double bubble map');
        } else if (typeof styleManager !== 'undefined' && styleManager.getTheme) {
            THEME = styleManager.getTheme('double_bubble_map', theme, theme);
            console.log('Using style manager theme (fallback)');
        } else {
            console.warn('Using fallback theme');
            THEME = {
                centralTopicFill: '#1976d2',  // Deeper blue
                centralTopicText: '#ffffff',   // White text for contrast
                centralTopicStroke: '#000000', // Black border for central topic
                leftTopicFill: '#1976d2',      // Deeper blue
                leftTopicText: '#ffffff',       // White text for contrast
                leftTopicStroke: '#000000',    // Black border for left topic
                rightTopicFill: '#1976d2',     // Deeper blue
                rightTopicText: '#ffffff',      // White text for contrast
                rightTopicStroke: '#000000',   // Black border for right topic
                attributeFill: '#e3f2fd', // Light blue for feature nodes
                attributeText: '#333333',
                attributeStroke: '#000000',  // Black border
                fontTopic: '18px Inter, sans-serif',
                fontAttribute: '14px Inter, sans-serif',
                background: '#ffffff'
            };
        }
    } catch (error) {
        console.error('Error getting theme:', error);
        THEME = {
            centralTopicFill: '#1976d2',  // Deeper blue
            centralTopicText: '#ffffff',   // White text for contrast
            centralTopicStroke: '#000000', // Black border for central topic
            leftTopicFill: '#1976d2',      // Deeper blue
            leftTopicText: '#ffffff',       // White text for contrast
            leftTopicStroke: '#000000',    // Black border for left topic
            rightTopicFill: '#1976d2',     // Deeper blue
            rightTopicText: '#ffffff',      // White text for contrast
            rightTopicStroke: '#000000',   // Black border for right topic
            attributeFill: '#e3f2fd', // Light blue for feature nodes
            attributeText: '#333333',
            attributeStroke: '#000000',  // Black border
            fontTopic: '18px Inter, sans-serif',
            fontAttribute: '14px Inter, sans-serif',
            background: '#ffffff'
        };
    }
    
    // Apply background if specified
    if (theme && theme.background) {
        d3.select('#d3-container').style('background-color', theme.background);
    }
    
    console.log('renderDoubleBubbleMap: using theme:', THEME);
    console.log('attributeFill value:', THEME.attributeFill);
    console.log('attributeText value:', THEME.attributeText);
    console.log('attributeStroke value:', THEME.attributeStroke);
    
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
    
    // Position topic nodes in the middle between left differences and similarities
    const leftDiffX = padding + leftDiffR;
    const simX = baseWidth / 2;
    const rightDiffX = baseWidth - padding - rightDiffR;
    
    // Position all columns with 50px spacing between columns
    const columnSpacing = 50; // Fixed 50 pixel spacing between columns
    
    // Calculate column positions (center of each column)
    const leftDiffColumnX = leftDiffX; // Left differences column center
    const leftTopicColumnX = leftDiffX + leftDiffR + columnSpacing + topicR; // Left topic column center
    const similaritiesColumnX = leftTopicColumnX + topicR + columnSpacing + simR; // Similarities column center
    const rightTopicColumnX = similaritiesColumnX + simR + columnSpacing + topicR; // Right topic column center
    const rightDiffColumnX = rightTopicColumnX + topicR + columnSpacing + rightDiffR; // Right differences column center
    
    // Position individual elements within their columns
    const leftTopicX = leftTopicColumnX;
    const leftSimX = similaritiesColumnX;
    const rightTopicX = rightTopicColumnX;
    const calculatedRightDiffX = rightDiffColumnX;
    
    // Calculate width to accommodate all elements with proper spacing
    const minX = Math.min(leftDiffX - leftDiffR, leftTopicX - topicR, leftSimX - simR, rightTopicX - topicR, calculatedRightDiffX - rightDiffR) - padding;
    const maxX = Math.max(leftDiffX + leftDiffR, leftTopicX + topicR, leftSimX + simR, rightTopicX + topicR, calculatedRightDiffX + rightDiffR) + padding;
    const width = Math.max(baseWidth, maxX - minX);
    
    // Calculate required width based on new positioning
    const requiredWidth = calculatedRightDiffX + rightDiffR + padding * 2;
    const finalWidth = Math.max(width, requiredWidth);
    const topicY = height / 2;
    
    console.log('renderDoubleBubbleMap: layout calculated:', { 
        width: finalWidth, 
        height, 
        leftTopicX, 
        leftSimX, 
        rightTopicX, 
        calculatedRightDiffX, 
        leftDiffX, 
        rightDiffX, 
        topicY,
        columnSpacing,
        leftDiffColumnX,
        leftTopicColumnX,
        similaritiesColumnX,
        rightTopicColumnX,
        rightDiffColumnX
    });
    
    const svg = d3.select('#d3-container').append('svg')
        .attr('width', finalWidth)
        .attr('height', height)
        .attr('viewBox', `${minX} 0 ${finalWidth} ${height}`)
        .attr('preserveAspectRatio', 'xMinYMin meet');
    
    console.log('renderDoubleBubbleMap: SVG created');
    
    // Draw all lines first
    const simStartY = topicY - ((simCount - 1) * (simR * 2 + 12)) / 2;
    for (let i = 0; i < simCount; i++) {
        const y = simStartY + i * (simR * 2 + 12);
        let dxL = leftTopicX - leftSimX, dyL = topicY - y, distL = Math.sqrt(dxL * dxL + dyL * dyL);
        let x1L = leftSimX + (dxL / distL) * simR, y1L = y + (dyL / distL) * simR;
        let x2L = leftTopicX - (dxL / distL) * topicR, y2L = topicY - (dyL / distL) * topicR;
        svg.append('line').attr('x1', x1L).attr('y1', y1L).attr('x2', x2L).attr('y2', y2L)
            .attr('stroke', '#888').attr('stroke-width', 2);
        
        let dxR = rightTopicX - leftSimX, dyR = topicY - y, distR = Math.sqrt(dxR * dxR + dyR * dyR);
        let x1R = leftSimX + (dxR / distR) * simR, y1R = y + (dyR / distR) * simR;
        let x2R = rightTopicX - (dxR / distR) * topicR, y2R = topicY - (dyR / distR) * topicR;
        svg.append('line').attr('x1', x1R).attr('y1', y1R).attr('x2', x2R).attr('y2', y2R)
            .attr('stroke', '#888').attr('stroke-width', 2);
    }
    
    const leftDiffStartY = topicY - ((leftDiffCount - 1) * (leftDiffR * 2 + 10)) / 2;
    for (let i = 0; i < leftDiffCount; i++) {
        const y = leftDiffStartY + i * (leftDiffR * 2 + 10);
        let dx = leftTopicX - leftDiffX, dy = topicY - y, dist = Math.sqrt(dx * dx + dy * dy);
        let x1 = leftDiffX + (dx / dist) * leftDiffR, y1 = y + (dy / dist) * leftDiffR;
        let x2 = leftTopicX - (dx / dist) * topicR, y2 = topicY - (dy / dist) * topicR;
        svg.append('line').attr('x1', x1).attr('y1', y1).attr('x2', x2).attr('y2', y2)
            .attr('stroke', '#bbb').attr('stroke-width', 2);
    }
    
    const rightDiffStartY = topicY - ((rightDiffCount - 1) * (rightDiffR * 2 + 10)) / 2;
    for (let i = 0; i < rightDiffCount; i++) {
        const y = rightDiffStartY + i * (rightDiffR * 2 + 10);
        let dx = rightTopicX - calculatedRightDiffX, dy = topicY - y, dist = Math.sqrt(dx * dx + dy * dy);
        let x1 = calculatedRightDiffX + (dx / dist) * rightDiffR, y1 = y + (dy / dist) * rightDiffR;
        let x2 = rightTopicX - (dx / dist) * topicR, y2 = topicY - (dy / dist) * topicR;
        svg.append('line').attr('x1', x1).attr('y1', y1).attr('x2', x2).attr('y2', y2)
            .attr('stroke', '#bbb').attr('stroke-width', 2);
    }
    
    // Draw all circles next
    svg.append('circle').attr('cx', leftTopicX).attr('cy', topicY).attr('r', topicR)
        .attr('fill', THEME.topicFill).attr('opacity', 0.9)
        .attr('stroke', THEME.topicStroke).attr('stroke-width', THEME.topicStrokeWidth);
    svg.append('circle').attr('cx', rightTopicX).attr('cy', topicY).attr('r', topicR)
        .attr('fill', THEME.topicFill).attr('opacity', 0.9)
        .attr('stroke', THEME.topicStroke).attr('stroke-width', THEME.topicStrokeWidth);
    
    for (let i = 0; i < simCount; i++) {
        const y = simStartY + i * (simR * 2 + 12);
        svg.append('circle').attr('cx', leftSimX).attr('cy', y).attr('r', simR)
            .attr('fill', THEME.simFill).attr('stroke', THEME.simStroke).attr('stroke-width', THEME.simStrokeWidth);
    }
    
    for (let i = 0; i < leftDiffCount; i++) {
        const y = leftDiffStartY + i * (leftDiffR * 2 + 10);
        svg.append('circle').attr('cx', leftDiffX).attr('cy', y).attr('r', leftDiffR)
            .attr('fill', THEME.diffFill).attr('stroke', THEME.diffStroke).attr('stroke-width', THEME.diffStrokeWidth);
    }
    
    for (let i = 0; i < rightDiffCount; i++) {
        const y = rightDiffStartY + i * (rightDiffR * 2 + 10);
        svg.append('circle').attr('cx', calculatedRightDiffX).attr('cy', y).attr('r', rightDiffR)
            .attr('fill', THEME.diffFill).attr('stroke', THEME.diffStroke).attr('stroke-width', THEME.diffStrokeWidth);
    }
    
    // Draw all text last
    svg.append('text').attr('x', leftTopicX).attr('y', topicY)
        .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
        .attr('fill', THEME.topicText).attr('font-size', THEME.fontTopic).attr('font-weight', 600)
        .text(spec.left);
    svg.append('text').attr('x', rightTopicX).attr('y', topicY)
        .attr('text-anchor', 'middle').attr('dominant-baseline', 'middle')
        .attr('fill', THEME.topicText).attr('font-size', THEME.fontTopic).attr('font-weight', 600)
        .text(spec.right);
    
    for (let i = 0; i < simCount; i++) {
        const y = simStartY + i * (simR * 2 + 12);
        svg.append('text').attr('x', leftSimX).attr('y', y)
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
        svg.append('text').attr('x', calculatedRightDiffX).attr('y', y)
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
    
    // Get complete theme using centralized configuration
    let THEME;
    try {
        // Use centralized theme configuration if available
        if (typeof getD3Theme === 'function') {
            THEME = getD3Theme('bubble_map');
            console.log('Using centralized theme configuration');
            console.log('Converted theme:', THEME);
            console.log('attributeFill:', THEME.attributeFill);
        } else if (typeof styleManager !== 'undefined' && styleManager.getTheme) {
            THEME = styleManager.getTheme('bubble_map', theme, theme);
            console.log('Using style manager theme');
        } else {
            console.warn('Using fallback theme');
            console.log('getD3Theme available:', typeof getD3Theme === 'function');
            console.log('styleManager available:', typeof styleManager !== 'undefined');
            THEME = {
                topicFill: '#1976d2',  // Deep blue background
                topicText: '#ffffff',   // White text for contrast
                topicStroke: '#000000', // Black border for topic nodes
                topicStrokeWidth: 3,
                attributeFill: '#e3f2fd',  // Light blue for attributes
                attributeText: '#333333', // Dark text for readability
                attributeStroke: '#000000',  // Black border
                attributeStrokeWidth: 2,
                fontTopic: 20,
                fontAttribute: 14,
                background: '#ffffff'
            };
        }
    } catch (error) {
        console.error('Error getting theme:', error);
        THEME = {
            topicFill: '#1976d2',  // Deep blue background
            topicText: '#ffffff',   // White text for contrast
            topicStroke: '#000000', // Black border for topic nodes
            topicStrokeWidth: 3,
            attributeFill: '#e3f2fd',  // Light blue for attributes
            attributeText: '#333333', // Dark text for readability
            attributeStroke: '#000000',  // Black border
            attributeStrokeWidth: 2,
            fontTopic: 20,
            fontAttribute: 14,
            background: '#ffffff'
        };
    }
    
    // Apply background if specified
    if (theme && theme.background) {
        d3.select('#d3-container').style('background-color', theme.background);
    }
    
    console.log('Bubble map final theme:', THEME);
    console.log('attributeFill value:', THEME.attributeFill);
    console.log('attributeText value:', THEME.attributeText);
    console.log('attributeStroke value:', THEME.attributeStroke);
    
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
    centerY = baseHeight / 2;
    
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
    
    // Validate spec
    if (!spec || !spec.topic || !Array.isArray(spec.children)) {
        d3.select('#d3-container').append('div').style('color', 'red').text('Invalid spec for tree map');
        return;
    }
    
    // Use provided theme and dimensions or defaults
    const baseWidth = dimensions?.baseWidth || 800;
    const baseHeight = dimensions?.baseHeight || 600;
    const padding = dimensions?.padding || 40;
    
    // Get theme using style manager
    let THEME;
    try {
        if (typeof styleManager !== 'undefined' && styleManager.getTheme) {
            THEME = styleManager.getTheme('tree_map', theme, theme);
        } else {
            console.warn('Style manager not available, using fallback theme');
            THEME = {
                rootFill: '#1976d2',  // Deeper blue
                rootText: '#ffffff',   // White text for contrast
                rootStroke: '#0d47a1', // Darker blue border
                rootStrokeWidth: 3,
                branchFill: '#e3f2fd', // Light blue for branches
                branchText: '#333333',  // Dark text
                branchStroke: '#1976d2', // Blue border
                branchStrokeWidth: 2,
                leafFill: '#f8f9fa',   // Very light blue for leaves
                leafText: '#333333',    // Dark text
                leafStroke: '#1976d2',  // Blue border
                leafStrokeWidth: 1,
                fontRoot: 20,
                fontBranch: 16,
                fontLeaf: 14
            };
        }
    } catch (error) {
        console.error('Error getting theme from style manager:', error);
        THEME = {
            rootFill: '#1976d2',  // Deeper blue
            rootText: '#ffffff',   // White text for contrast
            rootStroke: '#0d47a1', // Darker blue border
            rootStrokeWidth: 3,
            branchFill: '#e3f2fd', // Light blue for branches
            branchText: '#333333',  // Dark text
            branchStroke: '#1976d2', // Blue border
            branchStrokeWidth: 2,
            leafFill: '#f8f9fa',   // Very light blue for leaves
            leafText: '#333333',    // Dark text
            leafStroke: '#1976d2',  // Blue border
            leafStrokeWidth: 1,
            fontRoot: 20,
            fontBranch: 16,
            fontLeaf: 14
        };
    }
    
    const width = baseWidth;
    const height = baseHeight;
    var svg = d3.select('#d3-container').append('svg').attr('width', width).attr('height', height);

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
                .attr('font-family', 'Inter, sans-serif')
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
        .attr('stroke-width', THEME.rootStrokeWidth);
    svg.append('text')
        .attr('x', rootX)
        .attr('y', rootY)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('fill', THEME.rootText)
        .attr('font-size', rootFont)
        .attr('font-weight', 'bold')
        .text(spec.topic);
    
    // Draw branches
    const branchY = rootY + rootBox.h / 2 + 60;
    let requiredBottomY = branchY + 40;

    // First pass: measure branches and leaves, compute per-column width
    const branchLayouts = spec.children.map((child) => {
        const branchFont = THEME.fontBranch || 16;
        const branchBox = measureSvgTextBox(svg, child.label, branchFont, 14, 10);
        const leafFont = THEME.fontLeaf || 14;
        let maxLeafW = 0;
        const leafBoxes = (Array.isArray(child.children) ? child.children : []).map(leaf => {
            const b = measureSvgTextBox(svg, leaf.label, leafFont, 12, 8);
            if (b.w > maxLeafW) maxLeafW = b.w;
            return b;
        });
        const columnContentW = Math.max(branchBox.w, maxLeafW);
        const columnWidth = columnContentW + 60; // padding within column to avoid overlap
        return { child, branchFont, branchBox, leafFont, leafBoxes, maxLeafW, columnWidth };
    });

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
    branchLayouts.forEach(layout => {
        const { child, branchFont, branchBox, leafFont, leafBoxes, maxLeafW } = layout;
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
            .attr('stroke-width', THEME.branchStrokeWidth);

        svg.append('text')
            .attr('x', branchX)
            .attr('y', branchY)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.branchText)
            .attr('font-size', branchFont)
            .text(child.label);

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
                const box = leafBoxes[j] || measureSvgTextBox(svg, leaf.label, leafFont, 12, 8);
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
                    .attr('stroke-width', THEME.leafStrokeWidth != null ? THEME.leafStrokeWidth : 1);

                svg.append('text')
                    .attr('x', branchX)
                    .attr('y', leafY)
                    .attr('text-anchor', 'middle')
                    .attr('dominant-baseline', 'middle')
                    .attr('fill', THEME.leafText)
                    .attr('font-size', leafFont)
                    .text(leaf.label);
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
    
    // Watermark
    addWatermark(svg, theme);
}

function renderConceptMap(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    
    // Validate spec
    if (!spec || !spec.topic || !Array.isArray(spec.concepts) || !Array.isArray(spec.relationships)) {
        d3.select('#d3-container').append('div').style('color', 'red').text('Invalid spec for concept map');
        return;
    }
    
    // Use provided theme and dimensions or defaults
    const baseWidth = dimensions?.baseWidth || 800;
    const baseHeight = dimensions?.baseHeight || 600;
    const padding = dimensions?.padding || 40;
    
    // Get complete theme using robust style manager
    let THEME;
    try {
        if (typeof styleManager !== 'undefined' && styleManager.getTheme) {
            THEME = styleManager.getTheme('concept_map', theme, theme);
        } else {
            console.warn('Style manager not available, using fallback theme');
            THEME = {
                nodeFill: '#e3f2fd',
                nodeText: '#000000',
                nodeStroke: '#35506b',
                linkStroke: '#cccccc',
                fontNode: '16px Inter, sans-serif',
                background: '#ffffff'
            };
        }
    } catch (error) {
        console.error('Error getting theme from style manager:', error);
        THEME = {
            nodeFill: '#e3f2fd',
            nodeText: '#000000',
            nodeStroke: '#35506b',
            linkStroke: '#cccccc',
            fontNode: '16px Inter, sans-serif',
            background: '#ffffff'
        };
    }
    
    // Apply background if specified
    if (theme && theme.background) {
        d3.select('#d3-container').style('background-color', theme.background);
    }
    
    const width = baseWidth;
    const height = baseHeight;
    var svg = d3.select('#d3-container').append('svg').attr('width', width).attr('height', height);
    
    // Calculate layout - arrange concepts in a circle around the topic
    const centerX = width / 2;
    const centerY = height / 2;
    const topicRadius = getTextRadius(spec.topic, THEME.fontTopic, 20);
    const conceptRadius = 60; // Distance from center for concepts
    
    // Draw central topic
    svg.append('circle')
        .attr('cx', centerX)
        .attr('cy', centerY)
        .attr('r', topicRadius)
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
    
    // Position concepts in a circle
    const conceptPositions = [];
    const angleStep = (2 * Math.PI) / spec.concepts.length;
    
    spec.concepts.forEach((concept, i) => {
        const angle = i * angleStep;
        const x = centerX + conceptRadius * Math.cos(angle);
        const y = centerY + conceptRadius * Math.sin(angle);
        conceptPositions.push({ concept, x, y });
        
        const nodeRadius = getTextRadius(concept, THEME.fontConcept, 15);
        
        // Draw concept node
        svg.append('circle')
            .attr('cx', x)
            .attr('cy', y)
            .attr('r', nodeRadius)
            .attr('fill', THEME.conceptFill)
            .attr('stroke', THEME.conceptStroke)
            .attr('stroke-width', THEME.conceptStrokeWidth);
        
        svg.append('text')
            .attr('x', x)
            .attr('y', y)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.conceptText)
            .attr('font-size', THEME.fontConcept)
            .text(concept);
    });
    
    // Draw relationships
    spec.relationships.forEach(rel => {
        const fromNode = conceptPositions.find(p => p.concept === rel.from);
        const toNode = conceptPositions.find(p => p.concept === rel.to);
        
        if (fromNode && toNode) {
            // Calculate line positions
            const dx = toNode.x - fromNode.x;
            const dy = toNode.y - fromNode.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            
            const fromRadius = getTextRadius(rel.from, THEME.fontConcept, 15);
            const toRadius = getTextRadius(rel.to, THEME.fontConcept, 15);
            
            const lineStartX = fromNode.x + (dx / dist) * fromRadius;
            const lineStartY = fromNode.y + (dy / dist) * fromRadius;
            const lineEndX = toNode.x - (dx / dist) * toRadius;
            const lineEndY = toNode.y - (dy / dist) * toRadius;
            
            // Draw relationship line
            svg.append('line')
                .attr('x1', lineStartX)
                .attr('y1', lineStartY)
                .attr('x2', lineEndX)
                .attr('y2', lineEndY)
                .attr('stroke', THEME.relationshipColor)
                .attr('stroke-width', THEME.relationshipStrokeWidth);
            
            // Draw relationship label
            const midX = (lineStartX + lineEndX) / 2;
            const midY = (lineStartY + lineEndY) / 2;
            
            svg.append('text')
                .attr('x', midX)
                .attr('y', midY - 5)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', THEME.relationshipColor)
                .attr('font-size', THEME.fontRelationship)
                .attr('font-style', 'italic')
                .text(rel.label);
        }
    });
    
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
    
    // Get complete theme using robust style manager
    let THEME;
    try {
        if (typeof styleManager !== 'undefined' && styleManager.getTheme) {
            THEME = styleManager.getTheme('mindmap', theme, theme);
        } else {
            console.warn('Style manager not available, using fallback theme');
            THEME = {
                centralNodeFill: '#e3f2fd',
                centralNodeText: '#000000',
                centralNodeStroke: '#35506b',
                childNodeFill: '#f5f5f5',
                childNodeText: '#333333',
                childNodeStroke: '#cccccc',
                linkStroke: '#cccccc',
                fontCentral: '18px Inter, sans-serif',
                fontChild: '14px Inter, sans-serif',
                background: '#ffffff'
            };
        }
    } catch (error) {
        console.error('Error getting theme from style manager:', error);
        THEME = {
            centralNodeFill: '#e3f2fd',
            centralNodeText: '#000000',
            centralNodeStroke: '#35506b',
            childNodeFill: '#f5f5f5',
            childNodeText: '#333333',
            childNodeStroke: '#cccccc',
            linkStroke: '#cccccc',
            fontCentral: '18px Inter, sans-serif',
            fontChild: '14px Inter, sans-serif',
            background: '#ffffff'
        };
    }
    
    // Apply background if specified
    if (theme && theme.background) {
        d3.select('#d3-container').style('background-color', theme.background);
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
    
    // Validate spec
    if (!spec || !spec.topic || !Array.isArray(spec.branches)) {
        d3.select('#d3-container').append('div').style('color', 'red').text('Invalid spec for radial mind map');
        return;
    }
    
    // Use provided theme and dimensions or defaults
    const baseWidth = dimensions?.baseWidth || 800;
    const baseHeight = dimensions?.baseHeight || 600;
    const padding = dimensions?.padding || 40;
    
    const THEME = {
        topicFill: '#4e79a7',
        topicText: '#fff',
        topicStroke: '#35506b',
        topicStrokeWidth: 3,
        branchFill: '#a7c7e7',
        branchText: '#333',
        branchStroke: '#4e79a7',
        branchStrokeWidth: 2,
        subBranchFill: '#f4f6fb',
        subBranchText: '#333',
        subBranchStroke: '#4e79a7',
        subBranchStrokeWidth: 1,
        fontTopic: 20,
        fontBranch: 16,
        fontSubBranch: 14,
        ...theme
    };
    
    // Apply integrated styles if available
    if (theme) {
        if (theme.topicColor) THEME.topicFill = theme.topicColor;
        if (theme.topicTextColor) THEME.topicText = theme.topicTextColor;
        if (theme.stroke) THEME.topicStroke = theme.stroke;
        if (theme.strokeWidth) THEME.topicStrokeWidth = theme.strokeWidth;
        if (theme.branchColor) THEME.branchFill = theme.branchColor;
        if (theme.branchTextColor) THEME.branchText = theme.branchTextColor;
        if (theme.subBranchColor) THEME.subBranchFill = theme.subBranchColor;
        if (theme.subBranchTextColor) THEME.subBranchText = theme.subBranchTextColor;
        if (theme.topicFontSize) THEME.fontTopic = theme.topicFontSize;
        if (theme.branchFontSize) THEME.fontBranch = theme.branchFontSize;
        if (theme.subBranchFontSize) THEME.fontSubBranch = theme.subBranchFontSize;
        
        if (theme.background) {
            d3.select('#d3-container').style('background-color', theme.background);
        }
    }
    
    const width = baseWidth;
    const height = baseHeight;
    var svg = d3.select('#d3-container').append('svg').attr('width', width).attr('height', height);
    
    // Calculate layout
    const centerX = width / 2;
    const centerY = height / 2;
    const topicRadius = getTextRadius(spec.topic, THEME.fontTopic, 20);
    
    // Draw central topic
    svg.append('circle')
        .attr('cx', centerX)
        .attr('cy', centerY)
        .attr('r', topicRadius)
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
    
    // Draw branches in a radial pattern
    const branchCount = spec.branches.length;
    const angleStep = (2 * Math.PI) / branchCount;
    const branchRadius = 120;
    
    spec.branches.forEach((branch, i) => {
        const angle = i * angleStep;
        const branchX = centerX + branchRadius * Math.cos(angle);
        const branchY = centerY + branchRadius * Math.sin(angle);
        const branchNodeRadius = getTextRadius(branch.name, THEME.fontBranch, 15);
        
        // Draw branch node
        svg.append('circle')
            .attr('cx', branchX)
            .attr('cy', branchY)
            .attr('r', branchNodeRadius)
            .attr('fill', THEME.branchFill)
            .attr('stroke', THEME.branchStroke)
            .attr('stroke-width', THEME.branchStrokeWidth);
        
        svg.append('text')
            .attr('x', branchX)
            .attr('y', branchY)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.branchText)
            .attr('font-size', THEME.fontBranch)
            .text(branch.name);
        
        // Draw connecting line from topic to branch
        const dx = branchX - centerX;
        const dy = branchY - centerY;
        const dist = Math.sqrt(dx * dx + dy * dy);
        
        const lineStartX = centerX + (dx / dist) * topicRadius;
        const lineStartY = centerY + (dy / dist) * topicRadius;
        const lineEndX = branchX - (dx / dist) * branchNodeRadius;
        const lineEndY = branchY - (dy / dist) * branchNodeRadius;
        
        svg.append('line')
            .attr('x1', lineStartX)
            .attr('y1', lineStartY)
            .attr('x2', lineEndX)
            .attr('y2', lineEndY)
            .attr('stroke', '#bbb')
            .attr('stroke-width', 2);
        
        // Draw sub-branches
        if (branch.children && branch.children.length > 0) {
            const subBranchCount = branch.children.length;
            const subAngleStep = Math.PI / (subBranchCount + 1);
            const subBranchRadius = 60;
            
            branch.children.forEach((subBranch, j) => {
                const subAngle = angle - Math.PI/2 + (j + 1) * subAngleStep;
                const subBranchX = branchX + subBranchRadius * Math.cos(subAngle);
                const subBranchY = branchY + subBranchRadius * Math.sin(subAngle);
                const subBranchNodeRadius = getTextRadius(subBranch.name, THEME.fontSubBranch, 10);
                
                // Draw sub-branch node
                svg.append('circle')
                    .attr('cx', subBranchX)
                    .attr('cy', subBranchY)
                    .attr('r', subBranchNodeRadius)
                    .attr('fill', THEME.subBranchFill)
                    .attr('stroke', THEME.subBranchStroke)
                    .attr('stroke-width', THEME.subBranchStrokeWidth);
                
                svg.append('text')
                    .attr('x', subBranchX)
                    .attr('y', subBranchY)
                    .attr('text-anchor', 'middle')
                    .attr('dominant-baseline', 'middle')
                    .attr('fill', THEME.subBranchText)
                    .attr('font-size', THEME.fontSubBranch)
                    .text(subBranch.name);
                
                // Draw connecting line from branch to sub-branch
                const subDx = subBranchX - branchX;
                const subDy = subBranchY - branchY;
                const subDist = Math.sqrt(subDx * subDx + subDy * subDy);
                
                const subLineStartX = branchX + (subDx / subDist) * branchNodeRadius;
                const subLineStartY = branchY + (subDy / subDist) * branchNodeRadius;
                const subLineEndX = subBranchX - (subDx / subDist) * subBranchNodeRadius;
                const subLineEndY = subBranchY - (subDy / subDist) * subBranchNodeRadius;
                
                svg.append('line')
                    .attr('x1', subLineStartX)
                    .attr('y1', subLineStartY)
                    .attr('x2', subLineEndX)
                    .attr('y2', subLineEndY)
                    .attr('stroke', '#ddd')
                    .attr('stroke-width', 1);
            });
        }
    });
    
    // Watermark
    addWatermark(svg, theme);
}

function renderVennDiagram(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    
    // Validate spec
    if (!spec || !Array.isArray(spec.sets) || spec.sets.length < 2) {
        d3.select('#d3-container').append('div').style('color', 'red').text('Invalid spec for venn diagram - need at least 2 sets');
        return;
    }
    
    // Use provided theme and dimensions or defaults
    const baseWidth = dimensions?.baseWidth || 800;
    const baseHeight = dimensions?.baseHeight || 600;
    const padding = dimensions?.padding || 40;
    
    // Get theme using style manager
    let THEME;
    try {
        if (typeof styleManager !== 'undefined' && styleManager.getTheme) {
            THEME = styleManager.getTheme('venn_diagram', theme, theme);
        } else {
            console.warn('Style manager not available, using fallback theme');
            THEME = {
                set1Fill: '#ff6b6b',   // Red for first set
                set1Text: '#ffffff',    // White text
                set1Stroke: '#c44569',  // Darker red border
                set1StrokeWidth: 2,
                set2Fill: '#4ecdc4',   // Teal for second set
                set2Text: '#ffffff',    // White text
                set2Stroke: '#26a69a',  // Darker teal border
                set2StrokeWidth: 2,
                set3Fill: '#45b7d1',   // Blue for third set
                set3Text: '#ffffff',    // White text
                set3Stroke: '#2c3e50',  // Darker blue border
                set3StrokeWidth: 2,
                intersectionFill: '#a8e6cf', // Light green for intersections
                intersectionText: '#333333',  // Dark text
                fontSet: 16,
                fontIntersection: 14
            };
        }
    } catch (error) {
        console.error('Error getting theme from style manager:', error);
        THEME = {
            set1Fill: '#ff6b6b',   // Red for first set
            set1Text: '#ffffff',    // White text
            set1Stroke: '#c44569',  // Darker red border
            set1StrokeWidth: 2,
            set2Fill: '#4ecdc4',   // Teal for second set
            set2Text: '#ffffff',    // White text
            set2Stroke: '#26a69a',  // Darker teal border
            set2StrokeWidth: 2,
            set3Fill: '#45b7d1',   // Blue for third set
            set3Text: '#ffffff',    // White text
            set3Stroke: '#2c3e50',  // Darker blue border
            set3StrokeWidth: 2,
            intersectionFill: '#a8e6cf', // Light green for intersections
            intersectionText: '#333333',  // Dark text
            fontSet: 16,
            fontIntersection: 14
        };
    }
    
    const width = baseWidth;
    const height = baseHeight;
    var svg = d3.select('#d3-container').append('svg').attr('width', width).attr('height', height);
    
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = 120;
    
    if (spec.sets.length === 2) {
        // Two-set Venn diagram
        const set1X = centerX - radius * 0.6;
        const set1Y = centerY;
        const set2X = centerX + radius * 0.6;
        const set2Y = centerY;
        
        // Draw circles with transparency for overlap
        svg.append('circle')
            .attr('cx', set1X)
            .attr('cy', set1Y)
            .attr('r', radius)
            .attr('fill', THEME.set1Fill)
            .attr('stroke', THEME.set1Stroke)
            .attr('stroke-width', THEME.set1StrokeWidth)
            .attr('opacity', 0.7);
        
        svg.append('circle')
            .attr('cx', set2X)
            .attr('cy', set2Y)
            .attr('r', radius)
            .attr('fill', THEME.set2Fill)
            .attr('stroke', THEME.set2Stroke)
            .attr('stroke-width', THEME.set2StrokeWidth)
            .attr('opacity', 0.7);
        
        // Draw set labels
        svg.append('text')
            .attr('x', set1X - radius * 0.8)
            .attr('y', set1Y)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.set1Text)
            .attr('font-size', THEME.fontSet)
            .attr('font-weight', 'bold')
            .text(spec.sets[0].name);
        
        svg.append('text')
            .attr('x', set2X + radius * 0.8)
            .attr('y', set2Y)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.set2Text)
            .attr('font-size', THEME.fontSet)
            .attr('font-weight', 'bold')
            .text(spec.sets[1].name);
        
        // Draw intersection label
        svg.append('text')
            .attr('x', centerX)
            .attr('y', centerY)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.intersectionText)
            .attr('font-size', THEME.fontIntersection)
            .text(spec.sets[0].intersection || 'A ∩ B');
        
    } else if (spec.sets.length === 3) {
        // Three-set Venn diagram
        const set1X = centerX - radius * 0.8;
        const set1Y = centerY - radius * 0.4;
        const set2X = centerX + radius * 0.8;
        const set2Y = centerY - radius * 0.4;
        const set3X = centerX;
        const set3Y = centerY + radius * 0.6;
        
        // Draw circles with transparency
        svg.append('circle')
            .attr('cx', set1X)
            .attr('cy', set1Y)
            .attr('r', radius)
            .attr('fill', THEME.set1Fill)
            .attr('stroke', THEME.set1Stroke)
            .attr('stroke-width', THEME.set1StrokeWidth)
            .attr('opacity', 0.6);
        
        svg.append('circle')
            .attr('cx', set2X)
            .attr('cy', set2Y)
            .attr('r', radius)
            .attr('fill', THEME.set2Fill)
            .attr('stroke', THEME.set2Stroke)
            .attr('stroke-width', THEME.set2StrokeWidth)
            .attr('opacity', 0.6);
        
        svg.append('circle')
            .attr('cx', set3X)
            .attr('cy', set3Y)
            .attr('r', radius)
            .attr('fill', THEME.set3Fill)
            .attr('stroke', THEME.set3Stroke)
            .attr('stroke-width', THEME.set3StrokeWidth)
            .attr('opacity', 0.6);
        
        // Draw set labels
        svg.append('text')
            .attr('x', set1X - radius * 0.8)
            .attr('y', set1Y)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.set1Text)
            .attr('font-size', THEME.fontSet)
            .attr('font-weight', 'bold')
            .text(spec.sets[0].name);
        
        svg.append('text')
            .attr('x', set2X + radius * 0.8)
            .attr('y', set2Y)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.set2Text)
            .attr('font-size', THEME.fontSet)
            .attr('font-weight', 'bold')
            .text(spec.sets[1].name);
        
        svg.append('text')
            .attr('x', set3X)
            .attr('y', set3Y + radius * 0.8)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.set3Text)
            .attr('font-size', THEME.fontSet)
            .attr('font-weight', 'bold')
            .text(spec.sets[2].name);
        
        // Draw intersection labels
        svg.append('text')
            .attr('x', centerX)
            .attr('y', centerY - radius * 0.2)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.intersectionText)
            .attr('font-size', THEME.fontIntersection)
            .text(spec.sets[0].intersection || 'A ∩ B ∩ C');
    }
    
    // Watermark
    addWatermark(svg, theme);
}

function renderFlowchart(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');

    // Validate spec
    if (!spec || !spec.title || !Array.isArray(spec.steps)) {
        d3.select('#d3-container').append('div').style('color', 'red').text('Invalid spec for flowchart');
        return;
    }

    // Use provided padding; width/height will be derived from content
    const padding = dimensions?.padding || 40;

    // Get theme using style manager
    let THEME;
    try {
        if (typeof styleManager !== 'undefined' && styleManager.getTheme) {
            THEME = styleManager.getTheme('flowchart', theme, theme);
        } else {
            console.warn('Style manager not available, using fallback theme');
            THEME = {
                startFill: '#4caf50',
                startText: '#ffffff',
                startStroke: '#388e3c',
                startStrokeWidth: 2,
                processFill: '#2196f3',
                processText: '#ffffff',
                processStroke: '#1976d2',
                processStrokeWidth: 2,
                decisionFill: '#ff9800',
                decisionText: '#ffffff',
                decisionStroke: '#f57c00',
                decisionStrokeWidth: 2,
                endFill: '#f44336',
                endText: '#ffffff',
                endStroke: '#d32f2f',
                endStrokeWidth: 2,
                fontNode: 14,
                fontEdge: 12
            };
        }
    } catch (error) {
        console.error('Error getting theme from style manager:', error);
        THEME = {
            startFill: '#4caf50',
            startText: '#ffffff',
            startStroke: '#388e3c',
            startStrokeWidth: 2,
            processFill: '#2196f3',
            processText: '#ffffff',
            processStroke: '#1976d2',
            processStrokeWidth: 2,
            decisionFill: '#ff9800',
            decisionText: '#ffffff',
            decisionStroke: '#f57c00',
            decisionStrokeWidth: 2,
            endFill: '#f44336',
            endText: '#ffffff',
            endStroke: '#d32f2f',
            endStrokeWidth: 2,
            fontNode: 14,
            fontEdge: 12
        };
    }

    // Measurement SVG (off-screen)
    const tempSvg = d3.select('body').append('svg')
        .attr('width', 0)
        .attr('height', 0)
        .style('position', 'absolute')
        .style('left', '-9999px')
        .style('top', '-9999px');

    function measureTextSize(text, fontSize) {
        const t = tempSvg.append('text')
            .attr('x', -9999)
            .attr('y', -9999)
            .attr('font-size', fontSize)
            .attr('dominant-baseline', 'hanging')
            .text(text || '');
        const bbox = t.node().getBBox();
        t.remove();
        return { w: Math.ceil(bbox.width), h: Math.ceil(bbox.height || fontSize) };
    }

    // Measure title
    const titleFont = 20;
    const titleSize = measureTextSize(spec.title, titleFont);

    // Measure each step's text and compute adaptive node sizes
    const hPad = 14;
    const vPad = 10;
    const stepSpacing = 40;
    const nodeRadius = 5;

    const nodes = spec.steps.map(step => {
        const txt = step.text || '';
        const m = measureTextSize(txt, THEME.fontNode);
        const w = Math.max(100, m.w + hPad * 2);
        const h = Math.max(40, m.h + vPad * 2);
        return { step, text: txt, w, h };
    });

    // Compute required canvas from content
    const maxNodeWidth = nodes.reduce((acc, n) => Math.max(acc, n.w), 0);
    const requiredWidth = Math.max(titleSize.w, maxNodeWidth) + padding * 2;
    const totalNodesHeight = nodes.reduce((sum, n) => sum + n.h, 0);
    const totalSpacing = Math.max(0, nodes.length - 1) * stepSpacing;
    const requiredHeight = padding + (titleSize.h + 30) + totalNodesHeight + totalSpacing + padding;

    // Apply dimensions by sizing container explicitly
    d3.select('#d3-container')
        .style('width', requiredWidth + 'px')
        .style('height', requiredHeight + 'px');

    // Create visible SVG
    const svg = d3.select('#d3-container').append('svg')
        .attr('width', requiredWidth)
        .attr('height', requiredHeight)
        .attr('viewBox', `0 0 ${requiredWidth} ${requiredHeight}`)
        .attr('preserveAspectRatio', 'xMinYMin meet');

    // Remove temp svg
    tempSvg.remove();

    // Draw title
    const titleY = padding + titleSize.h;
    svg.append('text')
        .attr('x', requiredWidth / 2)
        .attr('y', titleY)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('fill', '#333')
        .attr('font-size', titleFont)
        .attr('font-weight', 'bold')
        .text(spec.title);

    // Vertical layout
    const centerX = requiredWidth / 2;
    let yCursor = titleY + 40;

    nodes.forEach((n, i) => {
        const x = centerX;
        const y = yCursor + n.h / 2;

        let fill, stroke, strokeWidth, textColor;
        switch (n.step.type) {
            case 'start':
                fill = THEME.startFill; stroke = THEME.startStroke; strokeWidth = THEME.startStrokeWidth; textColor = THEME.startText; break;
            case 'decision':
                fill = THEME.decisionFill; stroke = THEME.decisionStroke; strokeWidth = THEME.decisionStrokeWidth; textColor = THEME.decisionText; break;
            case 'end':
                fill = THEME.endFill; stroke = THEME.endStroke; strokeWidth = THEME.endStrokeWidth; textColor = THEME.endText; break;
            default:
                fill = THEME.processFill; stroke = THEME.processStroke; strokeWidth = THEME.processStrokeWidth; textColor = THEME.processText; break;
        }

        if (n.step.type === 'decision') {
            // Diamond using adaptive width/height
            const points = [
                `${x},${y - n.h/2}`,
                `${x + n.w/2},${y}`,
                `${x},${y + n.h/2}`,
                `${x - n.w/2},${y}`
            ].join(' ');
            svg.append('polygon')
                .attr('points', points)
                .attr('fill', fill)
                .attr('stroke', stroke)
                .attr('stroke-width', strokeWidth);
        } else {
            svg.append('rect')
                .attr('x', x - n.w/2)
                .attr('y', y - n.h/2)
                .attr('width', n.w)
                .attr('height', n.h)
                .attr('rx', nodeRadius)
                .attr('fill', fill)
                .attr('stroke', stroke)
                .attr('stroke-width', strokeWidth);
        }

        svg.append('text')
            .attr('x', x)
            .attr('y', y)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', textColor || '#fff')
            .attr('font-size', THEME.fontNode)
            .text(n.text);

        // Arrow to next node
        if (i < nodes.length - 1) {
            const nextTopY = y + n.h / 2 + 6;
            const nextBottomY = nextTopY + stepSpacing - 12;
            svg.append('line')
                .attr('x1', x)
                .attr('y1', nextTopY)
                .attr('x2', x)
                .attr('y2', nextBottomY)
                .attr('stroke', '#666')
                .attr('stroke-width', 2);
            svg.append('polygon')
                .attr('points', `${x},${nextBottomY} ${x - 5},${nextBottomY - 10} ${x + 5},${nextBottomY - 10}`)
                .attr('fill', '#666');
        }

        yCursor += n.h + stepSpacing;
    });

    // Watermark
    addWatermark(svg, theme);
}

function renderOrgChart(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    
    // Validate spec
    if (!spec || !spec.title || !spec.structure) {
        d3.select('#d3-container').append('div').style('color', 'red').text('Invalid spec for org chart');
        return;
    }
    
    // Use provided theme and dimensions or defaults
    const baseWidth = dimensions?.baseWidth || 800;
    const baseHeight = dimensions?.baseHeight || 600;
    const padding = dimensions?.padding || 40;
    
    const THEME = {
        rootFill: '#4e79a7',
        rootText: '#fff',
        rootStroke: '#35506b',
        rootStrokeWidth: 3,
        managerFill: '#a7c7e7',
        managerText: '#333',
        managerStroke: '#4e79a7',
        managerStrokeWidth: 2,
        employeeFill: '#f4f6fb',
        employeeText: '#333',
        employeeStroke: '#4e79a7',
        employeeStrokeWidth: 1,
        fontRoot: 18,
        fontManager: 16,
        fontEmployee: 14,
        ...theme
    };
    
    // Apply integrated styles if available
    if (theme) {
        if (theme.rootColor) THEME.rootFill = theme.rootColor;
        if (theme.rootTextColor) THEME.rootText = theme.rootTextColor;
        if (theme.managerColor) THEME.managerFill = theme.managerColor;
        if (theme.managerTextColor) THEME.managerText = theme.managerTextColor;
        if (theme.employeeColor) THEME.employeeFill = theme.employeeColor;
        if (theme.employeeTextColor) THEME.employeeText = theme.employeeTextColor;
        if (theme.rootFontSize) THEME.fontRoot = theme.rootFontSize;
        if (theme.managerFontSize) THEME.fontManager = theme.managerFontSize;
        if (theme.employeeFontSize) THEME.fontEmployee = theme.employeeFontSize;
        
        if (theme.background) {
            d3.select('#d3-container').style('background-color', theme.background);
        }
    }
    
    const width = baseWidth;
    const height = baseHeight;
    var svg = d3.select('#d3-container').append('svg').attr('width', width).attr('height', height);
    
    // Recursive function to draw org chart
    function drawNode(node, x, y, level = 0) {
        const nodeWidth = 120;
        const nodeHeight = 50;
        const levelHeight = 100;
        
        let fill, stroke, strokeWidth, fontSize, textColor;
        
        if (level === 0) {
            fill = THEME.rootFill;
            stroke = THEME.rootStroke;
            strokeWidth = THEME.rootStrokeWidth;
            fontSize = THEME.fontRoot;
            textColor = THEME.rootText;
        } else if (level === 1) {
            fill = THEME.managerFill;
            stroke = THEME.managerStroke;
            strokeWidth = THEME.managerStrokeWidth;
            fontSize = THEME.fontManager;
            textColor = THEME.managerText;
        } else {
            fill = THEME.employeeFill;
            stroke = THEME.employeeStroke;
            strokeWidth = THEME.employeeStrokeWidth;
            fontSize = THEME.fontEmployee;
            textColor = THEME.employeeText;
        }
        
        // Draw node rectangle
        svg.append('rect')
            .attr('x', x - nodeWidth/2)
            .attr('y', y - nodeHeight/2)
            .attr('width', nodeWidth)
            .attr('height', nodeHeight)
            .attr('rx', 5)
            .attr('fill', fill)
            .attr('stroke', stroke)
            .attr('stroke-width', strokeWidth);
        
        // Draw node text
        svg.append('text')
            .attr('x', x)
            .attr('y', y - 5)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', textColor)
            .attr('font-size', fontSize)
            .text(node.name);
        
        svg.append('text')
            .attr('x', x)
            .attr('y', y + 5)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', textColor)
            .attr('font-size', fontSize - 2)
            .text(node.title);
        
        // Draw children
        if (node.children && node.children.length > 0) {
            const childCount = node.children.length;
            const childSpacing = Math.min(200, (width - 2 * padding) / childCount);
            const childStartX = x - (childCount - 1) * childSpacing / 2;
            
            node.children.forEach((child, i) => {
                const childX = childStartX + i * childSpacing;
                const childY = y + levelHeight;
                
                // Draw connecting line
                svg.append('line')
                    .attr('x1', x)
                    .attr('y1', y + nodeHeight/2)
                    .attr('x2', childX)
                    .attr('y2', childY - nodeHeight/2)
                    .attr('stroke', '#bbb')
                    .attr('stroke-width', 2);
                
                // Recursively draw child
                drawNode(child, childX, childY, level + 1);
            });
        }
    }
    
    // Draw title
    svg.append('text')
        .attr('x', width / 2)
        .attr('y', padding + 20)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('fill', '#333')
        .attr('font-size', 20)
        .attr('font-weight', 'bold')
        .text(spec.title);
    
    // Start drawing from root structure
    drawNode(spec.structure, width / 2, padding + 50);
    
    // Watermark
    addWatermark(svg, theme);
}

function renderTimeline(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    
    // Validate spec
    if (!spec || !spec.title || !Array.isArray(spec.events)) {
        d3.select('#d3-container').append('div').style('color', 'red').text('Invalid spec for timeline');
        return;
    }
    
    // Use provided theme and dimensions or defaults
    const baseWidth = dimensions?.baseWidth || 900;
    const baseHeight = dimensions?.baseHeight || 400;
    const padding = dimensions?.padding || 40;
    
    const THEME = {
        titleFill: '#4e79a7',
        titleText: '#fff',
        titleStroke: '#35506b',
        titleStrokeWidth: 3,
        eventFill: '#a7c7e7',
        eventText: '#333',
        eventStroke: '#4e79a7',
        eventStrokeWidth: 2,
        lineColor: '#666',
        lineWidth: 3,
        fontTitle: 20,
        fontEvent: 14,
        fontDate: 12,
        ...theme
    };
    
    // Apply integrated styles if available
    if (theme) {
        if (theme.titleColor) THEME.titleFill = theme.titleColor;
        if (theme.titleTextColor) THEME.titleText = theme.titleTextColor;
        if (theme.eventColor) THEME.eventFill = theme.eventColor;
        if (theme.eventTextColor) THEME.eventText = theme.eventTextColor;
        if (theme.lineColor) THEME.lineColor = theme.lineColor;
        if (theme.titleFontSize) THEME.fontTitle = theme.titleFontSize;
        if (theme.eventFontSize) THEME.fontEvent = theme.eventFontSize;
        
        if (theme.background) {
            d3.select('#d3-container').style('background-color', theme.background);
        }
    }
    
    const width = baseWidth;
    const height = baseHeight;
    var svg = d3.select('#d3-container').append('svg').attr('width', width).attr('height', height);
    
    // Draw title
    const titleY = padding + 30;
    const titleRadius = getTextRadius(spec.title, THEME.fontTitle, 20);
    
    svg.append('circle')
        .attr('cx', width / 2)
        .attr('cy', titleY)
        .attr('r', titleRadius)
        .attr('fill', THEME.titleFill)
        .attr('stroke', THEME.titleStroke)
        .attr('stroke-width', THEME.titleStrokeWidth);
    
    svg.append('text')
        .attr('x', width / 2)
        .attr('y', titleY)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('fill', THEME.titleText)
        .attr('font-size', THEME.fontTitle)
        .attr('font-weight', 'bold')
        .text(spec.title);
    
    // Draw timeline line
    const lineY = titleY + titleRadius + 60;
    const lineStartX = padding + 50;
    const lineEndX = width - padding - 50;
    
    svg.append('line')
        .attr('x1', lineStartX)
        .attr('y1', lineY)
        .attr('x2', lineEndX)
        .attr('y2', lineY)
        .attr('stroke', THEME.lineColor)
        .attr('stroke-width', THEME.lineWidth);
    
    // Draw events
    const eventCount = spec.events.length;
    const eventSpacing = (lineEndX - lineStartX) / (eventCount + 1);
    
    spec.events.forEach((event, i) => {
        const eventX = lineStartX + (i + 1) * eventSpacing;
        const eventY = lineY;
        const eventRadius = 8;
        
        // Draw event circle
        svg.append('circle')
            .attr('cx', eventX)
            .attr('cy', eventY)
            .attr('r', eventRadius)
            .attr('fill', THEME.eventFill)
            .attr('stroke', THEME.eventStroke)
            .attr('stroke-width', THEME.eventStrokeWidth);
        
        // Draw event label
        svg.append('text')
            .attr('x', eventX)
            .attr('y', eventY + 30)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.eventText)
            .attr('font-size', THEME.fontEvent)
            .attr('font-weight', 'bold')
            .text(event.title);
        
        // Draw event date
        if (event.date) {
            svg.append('text')
                .attr('x', eventX)
                .attr('y', eventY + 50)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', '#666')
                .attr('font-size', THEME.fontDate)
                .text(event.date);
        }
        
        // Draw event description
        if (event.description) {
            svg.append('text')
                .attr('x', eventX)
                .attr('y', eventY + 70)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', '#666')
                .attr('font-size', THEME.fontDate)
                .text(event.description);
        }
    });
    
    // Watermark
    addWatermark(svg, theme);
}

function renderBridgeMap(spec, theme = null, dimensions = null, containerId = 'd3-container') {
    d3.select(`#${containerId}`).html('');
    
    // Validate spec
    if (!spec || !Array.isArray(spec.analogies) || spec.analogies.length === 0) {
        d3.select(`#${containerId}`).append('div').style('color', 'red').text('Invalid spec for bridge map');
        return;
    }
    
    // Calculate optimal dimensions based on content
    const numAnalogies = spec.analogies.length;
    const minWidthPerAnalogy = 120; // Minimum width needed per analogy pair
    const minPadding = 40; // Minimum padding on sides
    
    // Calculate optimal width: enough space for all analogies + separators + padding
    const contentWidth = (numAnalogies * minWidthPerAnalogy) + ((numAnalogies - 1) * 60); // 60px for separator spacing
    const optimalWidth = Math.max(contentWidth + (2 * minPadding), dimensions?.baseWidth || 600);
    
    // Calculate optimal height: enough space for text + vertical lines + padding
    const textHeight = 40; // Height for text elements
    const lineHeight = 50; // Height for vertical connection lines
    const optimalHeight = Math.max(textHeight + lineHeight + (2 * minPadding), dimensions?.baseHeight || 200);
    
    // Use calculated dimensions or fall back to provided dimensions
    const width = optimalWidth;
    const height = optimalHeight;
    const padding = minPadding; // Use minimal padding to reduce empty space
    
    // Create SVG
    const svg = d3.select(`#${containerId}`)
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `0 0 ${width} ${height}`)
        .style('background-color', '#f8f8f8'); // Light background to see boundaries
    
    // Apply theme
    const THEME = theme || {
        backgroundColor: '#ffffff',
        analogyTextColor: '#2c3e50',
        analogyFontSize: 14,
        bridgeColor: '#000000', // Use black for better visibility
        bridgeWidth: 3,
        stroke: '#2c3e50',
        strokeWidth: 1
    };
    
    // 1. Create horizontal main line (ensure it's visible)
    const mainLine = svg.append("line")
        .attr("x1", padding)
        .attr("y1", height/2)
        .attr("x2", width - padding)
        .attr("y2", height/2)
        .attr("stroke", "#000000") // Use attr instead of style
        .attr("stroke-width", 4); // Use attr instead of style
    
    // 2. Calculate separator positions with better spacing
    const availableWidth = width - (2 * padding);
    const sectionWidth = availableWidth / (spec.analogies.length + 1);
    
    // 3. Draw analogy pairs first
    spec.analogies.forEach((analogy, i) => {
        const xPos = padding + (sectionWidth * (i + 1));
        
        // 3.1 Add upstream item (left)
        svg.append("text")
            .attr("x", xPos)
            .attr("y", height/2 - 30)
            .attr("text-anchor", "middle")
            .text(analogy.left)
            .style("font-size", THEME.analogyFontSize)
            .style("fill", THEME.analogyTextColor)
            .style("font-weight", "bold");
        
        // 3.2 Add downstream item (right)
        svg.append("text")
            .attr("x", xPos)
            .attr("y", height/2 + 40)
            .attr("text-anchor", "middle")
            .text(analogy.right)
            .style("font-size", THEME.analogyFontSize)
            .style("fill", THEME.analogyTextColor)
            .style("font-weight", "bold");
        
                   // 3.3 Add vertical connection line (made invisible)
           svg.append("line")
               .attr("x1", xPos)
               .attr("y1", height/2 - 20) // Connect to upstream item
               .attr("x2", xPos)
               .attr("y2", height/2 + 30) // Connect to downstream item
               .attr("stroke", "transparent") // Make vertical lines invisible
               .attr("stroke-width", 3); // Use attr instead of style
    });
    
    // 4. Draw "as" separators (one less than analogy pairs) - positioned to the right of analogy pairs
    for (let i = 0; i < spec.analogies.length - 1; i++) {
        // Position separator between analogy pairs (to the right of current pair)
        const xPos = padding + (sectionWidth * (i + 1.5)); // Position between pairs
        
        // 4.1 Add little triangle separator on the main line
        const triangleSize = 8; // Back to normal size
        const trianglePath = `M ${xPos - triangleSize} ${height/2} L ${xPos} ${height/2 - triangleSize} L ${xPos + triangleSize} ${height/2} Z`;
        
        svg.append("path")
            .attr("d", trianglePath)
            .attr("fill", "#000000") // Use attr instead of style
            .attr("stroke", "#000000") // Use attr instead of style
            .attr("stroke-width", 2); // Use attr instead of style
        
        // 4.2 Add "as" text above the triangle
        svg.append("text")
            .attr("x", xPos)
            .attr("y", height/2 - triangleSize - 8) // Closer to triangle
            .attr("text-anchor", "middle")
            .text("as")
            .style("font-weight", "bold")
            .style("font-size", THEME.analogyFontSize + 2)
            .style("fill", THEME.analogyTextColor);
    }
    
    // Watermark
    addWatermark(svg, theme);
}

function renderFlowMap(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');

    // Validate spec
    if (!spec || !spec.title || !Array.isArray(spec.steps)) {
        d3.select('#d3-container').append('div').style('color', 'red').text('Invalid spec for flow map');
        return;
    }

    // Use provided padding from dimensions; width/height will be computed from content
    const padding = dimensions?.padding || 40;

    const THEME = {
        titleFill: '#4e79a7',
        titleText: '#fff',
        titleStroke: '#35506b',
        titleStrokeWidth: 3,
        stepFill: '#a7c7e7',
        stepText: '#333',
        stepStroke: '#4e79a7',
        stepStrokeWidth: 2,
        fontTitle: 18,
        fontStep: 14,
        hPadTitle: 12,
        vPadTitle: 8,
        hPadStep: 14,
        vPadStep: 10,
        stepSpacing: 80,
        rectRadius: 8,
        ...theme
    };

    // Apply integrated styles if available
    if (theme) {
        if (theme.titleColor) THEME.titleFill = theme.titleColor;
        if (theme.titleTextColor) THEME.titleText = theme.titleTextColor;
        if (theme.stroke) THEME.titleStroke = theme.stroke;
        if (theme.strokeWidth) THEME.titleStrokeWidth = theme.strokeWidth;
        if (theme.stepColor) THEME.stepFill = theme.stepColor;
        if (theme.stepTextColor) THEME.stepText = theme.stepTextColor;
        if (theme.titleFontSize) THEME.fontTitle = theme.titleFontSize;
        if (theme.stepFontSize) THEME.fontStep = theme.stepFontSize;

        if (theme.background) {
            d3.select('#d3-container').style('background-color', theme.background);
        }
    }

    // Create a temporary SVG for measuring text
    const tempSvg = d3.select('body').append('svg')
        .attr('width', 0)
        .attr('height', 0)
        .style('position', 'absolute')
        .style('left', '-9999px')
        .style('top', '-9999px');

    function measureTextSize(text, fontSize) {
        const t = tempSvg.append('text')
            .attr('x', -9999)
            .attr('y', -9999)
            .attr('font-size', fontSize)
            .attr('dominant-baseline', 'hanging')
            .text(text || '');
        const bbox = t.node().getBBox();
        t.remove();
        return { w: Math.ceil(bbox.width), h: Math.ceil(bbox.height || fontSize) };
    }

    // Measure title and steps to compute adaptive sizes (vertical layout)
    const titleSize = measureTextSize(spec.title, THEME.fontTitle);
    const stepSizes = spec.steps.map(s => {
        const m = measureTextSize(s, THEME.fontStep);
        return {
            text: s,
            w: Math.max(100, m.w + THEME.hPadStep * 2),
            h: Math.max(42, m.h + THEME.vPadStep * 2)
        };
    });

    // Build substeps mapping and measurements per step
    const stepToSubsteps = {};
    if (Array.isArray(spec.substeps)) {
        spec.substeps.forEach(entry => {
            if (!entry || typeof entry !== 'object') return;
            const stepName = entry.step;
            const subs = Array.isArray(entry.substeps) ? entry.substeps : [];
            if (typeof stepName === 'string' && subs.length) {
                stepToSubsteps[stepName] = subs;
            }
        });
    }
    const subSpacing = 12;
    const subOffsetX = 40; // gap between step rect and substeps group
    const subNodesPerStep = stepSizes.map(stepObj => {
        const subs = stepToSubsteps[stepObj.text] || [];
        return subs.map(txt => {
            const m = measureTextSize(txt, THEME.fontStep);
            return {
                text: txt,
                w: Math.max(80, m.w + THEME.hPadStep * 2),
                h: Math.max(28, m.h + THEME.vPadStep * 2)
            };
        });
    });
    const subGroupWidths = subNodesPerStep.map(nodes => nodes.length ? nodes.reduce((mx, n) => Math.max(mx, n.w), 0) : 0);
    const subGroupHeights = subNodesPerStep.map(nodes => {
        if (!nodes.length) return 0;
        const totalH = nodes.reduce((sum, n) => sum + n.h, 0);
        const spacing = Math.max(0, nodes.length - 1) * subSpacing;
        return totalH + spacing;
    });

    const maxStepWidth = stepSizes.reduce((mw, s) => Math.max(mw, s.w), 0);
    const maxSubGroupWidth = subGroupWidths.reduce((mw, w) => Math.max(mw, w), 0);
    const totalStepsHeight = stepSizes.reduce((sum, s) => sum + s.h, 0);
    const totalVerticalSpacing = Math.max(0, stepSizes.length - 1) * THEME.stepSpacing;

    // Required canvas based on content (include right-side substeps if present)
    const rightSideWidth = maxSubGroupWidth > 0 ? (subOffsetX + maxSubGroupWidth) : 0;
    let requiredWidth = Math.max(titleSize.w, maxStepWidth + rightSideWidth) + padding * 2;
    let requiredHeight = padding + (titleSize.h + THEME.vPadTitle) + 30 + totalStepsHeight + totalVerticalSpacing + padding;

    const baseWidth = requiredWidth;
    const baseHeight = requiredHeight;

    // Clean up temp svg (measurement SVG)
    tempSvg.remove();

    const centerX = baseWidth / 2;
    const startY = padding + titleSize.h + THEME.vPadTitle + 40;

    // Size container to content to avoid external CSS constraining the SVG
    d3.select('#d3-container')
        .style('width', baseWidth + 'px')
        .style('height', baseHeight + 'px');

    // Create actual SVG
    const svg = d3.select('#d3-container').append('svg')
        .attr('width', baseWidth)
        .attr('height', baseHeight)
        .attr('viewBox', `0 0 ${baseWidth} ${baseHeight}`)
        .attr('preserveAspectRatio', 'xMinYMin meet');

    // Draw title at the top
    const titleY = padding + titleSize.h; // baseline roughly below top padding
    svg.append('text')
        .attr('x', baseWidth / 2)
        .attr('y', titleY)
        .attr('text-anchor', 'middle')
        .attr('fill', THEME.titleText)
        .attr('font-size', THEME.fontTitle)
        .attr('font-weight', 'bold')
        .text(spec.title);

    // Draw steps vertically with adaptive block sizes and record centers
    let yCursor = startY;
    const stepCenters = [];
    stepSizes.forEach((s, index) => {
        const stepXCenter = centerX;
        const stepYCenter = yCursor + s.h / 2;
        stepCenters.push(stepYCenter);

        // Rect
        svg.append('rect')
            .attr('x', stepXCenter - s.w / 2)
            .attr('y', stepYCenter - s.h / 2)
            .attr('width', s.w)
            .attr('height', s.h)
            .attr('rx', THEME.rectRadius)
            .attr('fill', THEME.stepFill)
            .attr('stroke', THEME.stepStroke)
            .attr('stroke-width', THEME.stepStrokeWidth);

        // Text
        svg.append('text')
            .attr('x', stepXCenter)
            .attr('y', stepYCenter)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.stepText)
            .attr('font-size', THEME.fontStep)
            .text(s.text);

        // Arrow to next step (vertical)
        if (index < stepSizes.length - 1) {
            const lineStartY = stepYCenter + s.h / 2 + 6;
            const lineEndY = lineStartY + THEME.stepSpacing - 12;

            svg.append('line')
                .attr('x1', stepXCenter)
                .attr('y1', lineStartY)
                .attr('x2', stepXCenter)
                .attr('y2', lineEndY)
                .attr('stroke', '#888')
                .attr('stroke-width', 2);

            svg.append('polygon')
                .attr('points', `${stepXCenter - 4},${lineEndY - 8} ${stepXCenter},${lineEndY} ${stepXCenter + 4},${lineEndY - 8}`)
                .attr('fill', '#888');
        }

        yCursor += s.h + THEME.stepSpacing;
    });

    // If substep groups extend beyond current bounds, increase height and resize SVG
    if (stepCenters.length > 0) {
        const firstTop = stepCenters[0] - stepSizes[0].h / 2;
        const lastBottom = stepCenters[stepCenters.length - 1] + stepSizes[stepSizes.length - 1].h / 2;
        let minTopSub = Infinity;
        let maxBottomSub = -Infinity;
        subNodesPerStep.forEach((nodes, idx) => {
            if (!nodes.length) return;
            const groupH = subGroupHeights[idx];
            const top = stepCenters[idx] - groupH / 2;
            const bottom = stepCenters[idx] + groupH / 2;
            if (top < minTopSub) minTopSub = top;
            if (bottom > maxBottomSub) maxBottomSub = bottom;
        });
        if (minTopSub !== Infinity && maxBottomSub !== -Infinity) {
            const extraTop = Math.max(0, (startY - minTopSub));
            const extraBottom = Math.max(0, (maxBottomSub - lastBottom));
            const newHeight = baseHeight + extraTop + extraBottom;
            if (newHeight > baseHeight) {
                requiredHeight = newHeight;
                d3.select('#d3-container').style('height', requiredHeight + 'px');
                svg.attr('height', requiredHeight).attr('viewBox', `0 0 ${baseWidth} ${requiredHeight}`);
            }
        }
    }

    // Draw substeps to the right of each step
    stepSizes.forEach((s, idx) => {
        const nodes = subNodesPerStep[idx];
        if (!nodes.length) return;
        const stepYCenter = stepCenters[idx];
        const groupW = subGroupWidths[idx];
        const groupH = subGroupHeights[idx];
        const stepRightX = centerX + s.w / 2;
        const groupLeftX = stepRightX + subOffsetX;
        let y = stepYCenter - groupH / 2;

        nodes.forEach(n => {
            const cy = y + n.h / 2;
            // Rect
            svg.append('rect')
                .attr('x', groupLeftX)
                .attr('y', cy - n.h / 2)
                .attr('width', n.w)
                .attr('height', n.h)
                .attr('rx', Math.max(4, THEME.rectRadius - 2))
                .attr('fill', d3.color(THEME.stepFill).brighter(0.5))
                .attr('stroke', THEME.stepStroke)
                .attr('stroke-width', Math.max(1, THEME.stepStrokeWidth - 1));
            // Text
            svg.append('text')
                .attr('x', groupLeftX + n.w / 2)
                .attr('y', cy)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', THEME.stepText)
                .attr('font-size', Math.max(12, THEME.fontStep - 1))
                .text(n.text);
            // L-shaped connector
            const startX = stepRightX;
            const startYLine = stepYCenter;
            const midX = startX + Math.max(8, subOffsetX / 2);
            svg.append('line')
                .attr('x1', startX)
                .attr('y1', startYLine)
                .attr('x2', midX)
                .attr('y2', startYLine)
                .attr('stroke', '#888')
                .attr('stroke-width', 1.5);
            svg.append('line')
                .attr('x1', midX)
                .attr('y1', startYLine)
                .attr('x2', midX)
                .attr('y2', cy)
                .attr('stroke', '#888')
                .attr('stroke-width', 1.5);
            svg.append('line')
                .attr('x1', midX)
                .attr('y1', cy)
                .attr('x2', groupLeftX)
                .attr('y2', cy)
                .attr('stroke', '#888')
                .attr('stroke-width', 1.5);

            y += n.h + subSpacing;
        });
    });
    // Watermark
    addWatermark(svg, theme);
}

function renderMultiFlowMap(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    
    // Validate spec
    if (!spec || !spec.event || !Array.isArray(spec.causes) || !Array.isArray(spec.effects)) {
        d3.select('#d3-container').append('div').style('color', 'red').text('Invalid spec for multi-flow map');
        return;
    }
    
    // Use provided theme and dimensions or defaults
    let baseWidth = dimensions?.baseWidth || 900;
    let baseHeight = dimensions?.baseHeight || 500;
    const padding = dimensions?.padding || 40;
    
    const THEME = {
        eventFill: '#4e79a7',
        eventText: '#fff',
        eventStroke: '#35506b',
        eventStrokeWidth: 3,
        causeFill: '#ff7f0e',
        causeText: '#fff',
        causeStroke: '#cc6600',
        causeStrokeWidth: 2,
        effectFill: '#2ca02c',
        effectText: '#fff',
        effectStroke: '#1f7a1f',
        effectStrokeWidth: 2,
        fontEvent: 18,
        fontCause: 14,
        fontEffect: 14,
        rectRadius: 8,
        hPadEvent: 12,
        vPadEvent: 8,
        hPadNode: 10,
        vPadNode: 6,
        linkColorCause: '#ff7f0e',
        linkColorEffect: '#2ca02c',
        ...theme
    };
    
    // Apply integrated styles if available
    if (theme) {
        if (theme.eventColor) THEME.eventFill = theme.eventColor;
        if (theme.eventTextColor) THEME.eventText = theme.eventTextColor;
        if (theme.stroke) THEME.eventStroke = theme.stroke;
        if (theme.strokeWidth) THEME.eventStrokeWidth = theme.strokeWidth;
        if (theme.causeColor) THEME.causeFill = theme.causeColor;
        if (theme.causeTextColor) THEME.causeText = theme.causeTextColor;
        if (theme.effectColor) THEME.effectFill = theme.effectColor;
        if (theme.effectTextColor) THEME.effectText = theme.effectTextColor;
        if (theme.eventFontSize) THEME.fontEvent = theme.eventFontSize;
        if (theme.causeFontSize) THEME.fontCause = theme.causeFontSize;
        if (theme.effectFontSize) THEME.fontEffect = theme.effectFontSize;
        if (theme.background) d3.select('#d3-container').style('background-color', theme.background);
    }
    
    // Before SVG, measure sizes to adapt canvas height if needed
    const tempSvg2 = d3.select('body').append('svg')
        .attr('width', 0)
        .attr('height', 0)
        .style('position', 'absolute')
        .style('left', '-9999px')
        .style('top', '-9999px');

    function measureTextSize2(text, fontSize) {
        const t = tempSvg2.append('text')
            .attr('x', -9999)
            .attr('y', -9999)
            .attr('font-size', fontSize)
            .attr('dominant-baseline', 'hanging')
            .text(text || '');
        const bbox = t.node().getBBox();
        t.remove();
        return { w: Math.ceil(bbox.width), h: Math.ceil(bbox.height || fontSize) };
    }
    
    // Helpers
    function measureTextSize(text, fontSize) {
        const temp = svg.append('text')
            .attr('x', -9999)
            .attr('y', -9999)
            .attr('font-size', fontSize)
            .attr('dominant-baseline', 'hanging')
            .text(text || '');
        const bbox = temp.node().getBBox();
        temp.remove();
        return { w: Math.ceil(bbox.width), h: Math.ceil(bbox.height || fontSize) };
    }
    function sideCenterPoint(cx, cy, w, h, side) {
        if (side === 'left') return { x: cx - w / 2, y: cy };
        if (side === 'right') return { x: cx + w / 2, y: cy };
        if (side === 'top') return { x: cx, y: cy - h / 2 };
        if (side === 'bottom') return { x: cx, y: cy + h / 2 };
        return { x: cx, y: cy };
    }
    function computeEdgeSlots(cx, cy, w, h, count, side, margin = 8) {
        const slots = [];
        if (count <= 0) return slots;
        const x = side === 'left' ? cx - w / 2 : side === 'right' ? cx + w / 2 : cx;
        let yStart = cy - h / 2 + margin;
        let yEnd = cy + h / 2 - margin;
        if (yEnd < yStart) {
            yStart = cy;
            yEnd = cy;
        }
        if (count === 1) {
            slots.push({ x, y: cy });
            return slots;
        }
        const totalSpan = Math.max(0, yEnd - yStart);
        const step = count > 1 ? (totalSpan / (count - 1)) : 0;
        for (let i = 0; i < count; i++) {
            const y = yStart + step * i;
            slots.push({ x, y });
        }
        return slots;
    }
    function drawArrow(x1, y1, x2, y2, color) {
        svg.append('line')
            .attr('x1', x1)
            .attr('y1', y1)
            .attr('x2', x2)
            .attr('y2', y2)
            .attr('stroke', color)
            .attr('stroke-width', 2);
        const dx = x2 - x1, dy = y2 - y1;
        const len = Math.hypot(dx, dy) || 1;
        const ux = dx / len, uy = dy / len;
        const perpX = -uy, perpY = ux;
        const tipX = x2, tipY = y2;
        const baseX = tipX - ux * 10, baseY = tipY - uy * 10;
        const p1x = baseX + perpX * 4, p1y = baseY + perpY * 4;
        const p2x = baseX - perpX * 4, p2y = baseY - perpY * 4;
        svg.append('polygon')
            .attr('points', `${p1x},${p1y} ${tipX},${tipY} ${p2x},${p2y}`)
            .attr('fill', color);
    }
    
    // Layout centers
    const centerX = baseWidth / 2;
    let centerY = baseHeight / 2;
    
    // Measure sizes
    const evSize = measureTextSize2(spec.event, THEME.fontEvent);
    const eventW = evSize.w + THEME.hPadEvent * 2;
    const eventH = evSize.h + THEME.vPadEvent * 2;
    
    const causes = (spec.causes || []).map(text => {
        const s = measureTextSize2(text, THEME.fontCause);
        return { text, w: s.w + THEME.hPadNode * 2, h: s.h + THEME.vPadNode * 2 };
    });
    const effects = (spec.effects || []).map(text => {
        const s = measureTextSize2(text, THEME.fontEffect);
        return { text, w: s.w + THEME.hPadNode * 2, h: s.h + THEME.vPadNode * 2 };
    });
    
    // Horizontal positions with guaranteed gap from event
    const minSideGap = 120;
    const causeCX = Math.max(padding + 140, centerX - eventW / 2 - minSideGap);
    const effectCX = Math.min(baseWidth - padding - 140, centerX + eventW / 2 + minSideGap);
    
    // Vertical positions (non-overlapping, content-aware)
    const vSpacing = 20;
    const totalCauseH = causes.reduce((sum, n) => sum + n.h, 0) + Math.max(0, causes.length - 1) * vSpacing;
    const totalEffectH = effects.reduce((sum, n) => sum + n.h, 0) + Math.max(0, effects.length - 1) * vSpacing;
    // Adapt baseHeight to fit tallest side if needed
    const requiredHeight = Math.max(totalCauseH, totalEffectH) + 2 * padding + evSize.h + 80;
    baseHeight = Math.max(baseHeight, requiredHeight);

    // Create SVG after adapting height
    const svg = d3.select('#d3-container').append('svg')
        .attr('width', baseWidth)
        .attr('height', baseHeight)
        .attr('viewBox', `0 0 ${baseWidth} ${baseHeight}`)
        .attr('preserveAspectRatio', 'xMinYMin meet');

    // Recompute center after adapting height
    centerY = baseHeight / 2;

    let cy = centerY - totalCauseH / 2;
    causes.forEach(n => { n.cx = causeCX; n.cy = cy + n.h / 2; cy += n.h + vSpacing; });
    let ey = centerY - totalEffectH / 2;
    effects.forEach(n => { n.cx = effectCX; n.cy = ey + n.h / 2; ey += n.h + vSpacing; });

    // Cleanup temp svg
    tempSvg2.remove();
    
    // Draw central event (rectangle)
    svg.append('rect')
        .attr('x', centerX - eventW / 2)
        .attr('y', centerY - eventH / 2)
        .attr('width', eventW)
        .attr('height', eventH)
        .attr('rx', THEME.rectRadius)
        .attr('ry', THEME.rectRadius)
        .attr('fill', THEME.eventFill)
        .attr('stroke', THEME.eventStroke)
        .attr('stroke-width', THEME.eventStrokeWidth);
    svg.append('text')
        .attr('x', centerX)
        .attr('y', centerY)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('fill', THEME.eventText)
        .attr('font-size', THEME.fontEvent)
        .attr('font-weight', 'bold')
        .text(spec.event);
    
    // Pre-compute distinct attachment points on the event rectangle to avoid stacking
    const eventLeftSlots = computeEdgeSlots(centerX, centerY, eventW, eventH, causes.length, 'left', 10);
    const eventRightSlots = computeEdgeSlots(centerX, centerY, eventW, eventH, effects.length, 'right', 10);

    // Draw causes and arrows to event (right center of cause -> distributed left edge of event)
    causes.forEach(n => {
        svg.append('rect')
            .attr('x', n.cx - n.w / 2)
            .attr('y', n.cy - n.h / 2)
            .attr('width', n.w)
            .attr('height', n.h)
            .attr('rx', THEME.rectRadius)
            .attr('ry', THEME.rectRadius)
            .attr('fill', THEME.causeFill)
            .attr('stroke', THEME.causeStroke)
            .attr('stroke-width', THEME.causeStrokeWidth);
        svg.append('text')
            .attr('x', n.cx)
            .attr('y', n.cy)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.causeText)
            .attr('font-size', THEME.fontCause)
            .text(n.text);
        const start = sideCenterPoint(n.cx, n.cy, n.w, n.h, 'right');
        const slotIndex = Math.min(eventLeftSlots.length - 1, Math.max(0, causes.indexOf(n)));
        const end = eventLeftSlots[slotIndex] || sideCenterPoint(centerX, centerY, eventW, eventH, 'left');
        drawArrow(start.x, start.y, end.x, end.y, THEME.linkColorCause);
    });
    
    // Draw effects and arrows from event (distributed right edge of event -> left center of effect)
    effects.forEach(n => {
        svg.append('rect')
            .attr('x', n.cx - n.w / 2)
            .attr('y', n.cy - n.h / 2)
            .attr('width', n.w)
            .attr('height', n.h)
            .attr('rx', THEME.rectRadius)
            .attr('ry', THEME.rectRadius)
            .attr('fill', THEME.effectFill)
            .attr('stroke', THEME.effectStroke)
            .attr('stroke-width', THEME.effectStrokeWidth);
        svg.append('text')
            .attr('x', n.cx)
            .attr('y', n.cy)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.effectText)
            .attr('font-size', THEME.fontEffect)
            .text(n.text);
        const slotIndex = Math.min(eventRightSlots.length - 1, Math.max(0, effects.indexOf(n)));
        const start = eventRightSlots[slotIndex] || sideCenterPoint(centerX, centerY, eventW, eventH, 'right');
        const end = sideCenterPoint(n.cx, n.cy, n.w, n.h, 'left');
        drawArrow(start.x, start.y, end.x, end.y, THEME.linkColorEffect);
    });
    
    // Watermark
    addWatermark(svg, theme);
}

function renderBraceMap(spec, theme = null, dimensions = null) {
    console.log('renderBraceMap called with:', { spec, theme, dimensions });
    
    // Clear container and ensure it exists
    const container = d3.select('#d3-container');
    if (container.empty()) {
        console.error('d3-container not found');
        return;
    }
    container.html('');
    
    // Validate spec
    if (!spec || !spec.topic || !Array.isArray(spec.parts)) {
        d3.select('#d3-container').append('div').style('color', 'red').text('Invalid spec for brace map');
        return;
    }
    
    // Use provided theme and dimensions or defaults
    const baseWidth = dimensions?.baseWidth || 1000;
    const baseHeight = dimensions?.baseHeight || 600;
    const padding = dimensions?.padding || 40;
    
    // Get complete theme using robust style manager
    let THEME;
    try {
        if (typeof styleManager !== 'undefined' && styleManager.getTheme) {
            THEME = styleManager.getTheme('brace_map', theme, theme);
        } else {
            console.warn('Style manager not available, using fallback theme');
            THEME = {
                topicFill: '#e3f2fd',
                topicText: '#000000',
                topicStroke: '#35506b',
                partFill: '#f5f5f5',
                partText: '#333333',
                partStroke: '#cccccc',
                subpartFill: '#fafafa',
                subpartText: '#666666',
                subpartStroke: '#dddddd',
                fontTopic: '24px Inter, sans-serif',
                fontPart: '18px Inter, sans-serif',
                fontSubpart: '14px Inter, sans-serif',
                background: '#ffffff',
                braceColor: '#666666',
                braceWidth: 3
            };
        }
    } catch (error) {
        console.error('Error getting theme from style manager:', error);
        THEME = {
            topicFill: '#e3f2fd',
            topicText: '#000000',
            topicStroke: '#35506b',
            partFill: '#f5f5f5',
            partText: '#333333',
            partStroke: '#cccccc',
            subpartFill: '#fafafa',
            subpartText: '#666666',
            subpartStroke: '#dddddd',
            fontTopic: '24px Inter, sans-serif',
            fontPart: '18px Inter, sans-serif',
            fontSubpart: '14px Inter, sans-serif',
            background: '#ffffff',
            braceColor: '#666666',
            braceWidth: 3
        };
    }
    
    // Apply background if specified
    if (theme && theme.background) {
        d3.select('#d3-container').style('background-color', theme.background);
    }
    
    // Calculate 5-column layout positions adaptively based on content widths
    // Helpers to measure text width using a temporary hidden SVG text node
    function parseFontSpec(fontSpec) {
        // Expect formats like "24px Inter, sans-serif"
        const match = typeof fontSpec === 'string' ? fontSpec.match(/^(\d+)px\s+(.+)$/) : null;
        if (match) {
            return { size: parseInt(match[1], 10), family: match[2] };
        }
        // Fallbacks
        return { size: 16, family: 'Inter, sans-serif' };
    }
    function measureTextWidth(text, fontSpec, fontWeight = 'normal') {
        const { size, family } = parseFontSpec(fontSpec);
        // Create a temporary hidden SVG for measurement
        const tempSvg = d3.select('#d3-container')
            .append('svg')
            .attr('width', 0)
            .attr('height', 0)
            .style('position', 'absolute')
            .style('visibility', 'hidden');
        const tempText = tempSvg.append('text')
            .text(text || '')
            .attr('font-size', size)
            .attr('font-family', family)
            .style('font-weight', fontWeight);
        const bbox = tempText.node().getBBox();
        tempSvg.remove();
        return Math.max(0, bbox?.width || 0);
    }

    // Helper to build a curly brace path opening to the right
    function buildCurlyBracePath(braceX, yTop, yBottom, depth) {
        const height = Math.max(0, yBottom - yTop);
        if (height <= 0 || depth <= 0) return '';
        const yMid = (yTop + yBottom) / 2;
        const d1 = height * 0.18;
        const d2 = height * 0.12;
        const mid = height * 0.08;
        return `M ${braceX} ${yTop}
                C ${braceX} ${yTop + d2} ${braceX + depth} ${yTop + d1} ${braceX + depth} ${yMid - mid}
                C ${braceX + depth} ${yMid - mid/2} ${braceX} ${yMid} ${braceX} ${yMid}
                C ${braceX} ${yMid} ${braceX + depth} ${yMid + mid/2} ${braceX + depth} ${yBottom - d1}
                C ${braceX + depth} ${yBottom - d2} ${braceX} ${yBottom - d2/2} ${braceX} ${yBottom}`;
    }

    // Measure content widths
    const topicWidth = measureTextWidth(spec.topic, THEME.fontTopic, 'bold');
    const partWidths = (spec.parts || []).map(p => measureTextWidth(p?.name || '', THEME.fontPart, 'bold'));
    const maxPartWidth = Math.max(100, ...(partWidths.length ? partWidths : [0]));
    const subpartWidths = [];
    (spec.parts || []).forEach(p => {
        (p.subparts || []).forEach(sp => {
            subpartWidths.push(measureTextWidth(sp?.name || '', THEME.fontSubpart));
        });
    });
    const maxSubpartWidth = Math.max(100, ...(subpartWidths.length ? subpartWidths : [0]));

    // Define brace corridors and inter-column spacing
    const mainBraceCorridor = 40;  // space allocated for the big brace visuals
    const smallBraceCorridor = 30; // space allocated for small braces
    const columnSpacing = 30;      // spacing between columns

    // Compute X positions by summing column widths and spacing
    let runningX = padding;
    const column1X = runningX + topicWidth / 2; // Topic
    runningX += topicWidth + columnSpacing;
    const column2X = runningX + mainBraceCorridor / 2; // Big brace
    runningX += mainBraceCorridor + columnSpacing;
    const column3X = runningX + maxPartWidth / 2; // Parts
    runningX += maxPartWidth + columnSpacing;
    const column4X = runningX + smallBraceCorridor / 2; // Small brace
    runningX += smallBraceCorridor + columnSpacing;
    const column5X = runningX + maxSubpartWidth / 2; // Subparts
    runningX += maxSubpartWidth;
    
    // Calculate vertical spacing
    const partSpacing = 80;
    const subpartSpacing = 30;
    
    // Calculate total height needed
    let totalHeight = 0;
    spec.parts.forEach(part => {
        totalHeight += partSpacing;
        if (part.subparts && part.subparts.length > 0) {
            totalHeight += part.subparts.length * subpartSpacing;
        }
    });
    
    // Adjust canvas size based on content
    const finalHeight = Math.max(baseHeight, totalHeight + padding * 2);
    const rightPadding = Math.min(padding, 8); // keep right buffer small
    const contentWidth = runningX + rightPadding; // sum of all columns + small right padding
    const finalWidth = contentWidth;
    
    // Create SVG
    const svg = d3.select('#d3-container').append('svg')
        .attr('width', finalWidth)
        .attr('height', finalHeight)
        .attr('viewBox', `0 0 ${finalWidth} ${finalHeight}`)
        .attr('preserveAspectRatio', 'xMinYMin meet')
        .style('display', 'block')
        .style('background-color', '#ffffff');
    
    // Calculate center Y for topic
    const centerY = finalHeight / 2;
    
    // Draw topic (Column 1)
    const topicFontParsed = parseFontSpec(THEME.fontTopic);
    svg.append('text')
        .attr('x', column1X)
        .attr('y', centerY)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('fill', THEME.topicText)
        .attr('font-size', topicFontParsed.size)
        .attr('font-family', topicFontParsed.family)
        .attr('font-weight', 'bold')
        .text(spec.topic);
    
    // Calculate part positions
    const partPositions = [];
    let currentY = padding + 60;
    
    spec.parts.forEach((part, partIndex) => {
        partPositions.push({
            x: column3X,
            y: currentY,
            part: part,
            partIndex: partIndex
        });
        
        // Calculate subpart positions for this part
        if (part.subparts && part.subparts.length > 0) {
            const subpartStartY = currentY - (part.subparts.length - 1) * subpartSpacing / 2;
            part.subparts.forEach((subpart, subpartIndex) => {
                partPositions.push({
                    x: column5X,
                    y: subpartStartY + subpartIndex * subpartSpacing,
                    subpart: subpart,
                    partIndex: partIndex,
                    subpartIndex: subpartIndex
                });
            });
        }
        
        currentY += partSpacing;
    });
    
    // Draw big brace (Column 2) - connects topic to all parts (curly style)
    const partOnlyPositions = partPositions.filter(p => p.part).sort((a, b) => a.y - b.y);
    if (partOnlyPositions.length > 0) {
        const partFontSize = parseFontSpec(THEME.fontPart).size;
        const firstPartY = partOnlyPositions[0].y - partFontSize * 0.6;
        const lastPartY = partOnlyPositions[partOnlyPositions.length - 1].y + partFontSize * 0.6;
        const depth = Math.max(8, mainBraceCorridor * 0.8);
        const braceX = column2X - depth / 2; // Keep within corridor centered at column2X
        const bigBracePath = buildCurlyBracePath(braceX, firstPartY, lastPartY, depth);
        if (bigBracePath) {
            svg.append('path')
                .attr('d', bigBracePath)
                .attr('fill', 'none')
                .attr('stroke', THEME.braceColor)
                .attr('stroke-width', 1.5)
                .attr('stroke-linecap', 'round')
                .attr('stroke-linejoin', 'round');
        }
    }
    
    // Draw parts (Column 3)
    spec.parts.forEach((part, partIndex) => {
        const partPos = partPositions.find(p => p.part && p.partIndex === partIndex);
        if (partPos) {
            const partFontParsed = parseFontSpec(THEME.fontPart);
            svg.append('text')
                .attr('x', partPos.x)
                .attr('y', partPos.y)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', THEME.partText)
                .attr('font-size', partFontParsed.size)
                .attr('font-family', partFontParsed.family)
                .attr('font-weight', 'bold')
                .text(part.name);
        }
    });
    
    // Draw small braces (Column 4) - connect each part to its subparts (curly style)
    spec.parts.forEach((part, partIndex) => {
        if (part.subparts && part.subparts.length > 0) {
            const partPos = partPositions.find(p => p.part && p.partIndex === partIndex);
            const partSubparts = partPositions
                .filter(p => p.subpart && p.partIndex === partIndex)
                .sort((a, b) => a.y - b.y);
            
            if (partPos && partSubparts.length > 0) {
                const subpartFontSize = parseFontSpec(THEME.fontSubpart).size;
                let yTop = partSubparts[0].y - subpartFontSize * 0.6;
                let yBottom = partSubparts[partSubparts.length - 1].y + subpartFontSize * 0.6;
                // Ensure a reasonable minimum height (helps when only one subpart)
                const minBraceHeight = Math.max(12, subpartFontSize * 1.2);
                if ((yBottom - yTop) < minBraceHeight) {
                    const centerY = (yTop + yBottom) / 2;
                    yTop = centerY - minBraceHeight / 2;
                    yBottom = centerY + minBraceHeight / 2;
                }
                const sDepth = Math.max(6, smallBraceCorridor * 0.8);
                const sBraceX = column4X - sDepth / 2; // Center within small brace corridor
                const smallBracePath = buildCurlyBracePath(sBraceX, yTop, yBottom, sDepth);
                if (smallBracePath) {
                    svg.append('path')
                        .attr('d', smallBracePath)
                        .attr('fill', 'none')
                        .attr('stroke', THEME.braceColor)
                        .attr('stroke-width', 1.0)
                        .attr('stroke-linecap', 'round')
                        .attr('stroke-linejoin', 'round');
                }
            }
        }
    });
    
    // Draw subparts (Column 5)
    partPositions.forEach(pos => {
        if (pos.subpart) {
            const subpartFontParsed = parseFontSpec(THEME.fontSubpart);
            svg.append('text')
                .attr('x', pos.x)
                .attr('y', pos.y)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', THEME.subpartText)
                .attr('font-size', subpartFontParsed.size)
                .attr('font-family', subpartFontParsed.family)
                .text(pos.subpart.name);
        }
    });
    
    // Watermark
    addWatermark(svg, theme);
}

function renderFishboneDiagram(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    
    // Validate spec
    if (!spec || !spec.problem || !Array.isArray(spec.categories) || !Array.isArray(spec.causes)) {
        d3.select('#d3-container').append('div').style('color', 'red').text('Invalid spec for fishbone diagram');
        return;
    }
    
    // Use provided theme and dimensions or defaults
    const baseWidth = dimensions?.baseWidth || 900;
    const baseHeight = dimensions?.baseHeight || 600;
    const padding = dimensions?.padding || 40;
    
    const THEME = {
        problemFill: '#e15759',
        problemText: '#fff',
        problemStroke: '#c44569',
        problemStrokeWidth: 3,
        categoryFill: '#4e79a7',
        categoryText: '#fff',
        categoryStroke: '#35506b',
        categoryStrokeWidth: 2,
        causeFill: '#a7c7e7',
        causeText: '#333',
        causeStroke: '#4e79a7',
        causeStrokeWidth: 1,
        fontProblem: 20,
        fontCategory: 16,
        fontCause: 12,
        ...theme
    };
    
    // Apply integrated styles if available
    if (theme) {
        if (theme.problemColor) THEME.problemFill = theme.problemColor;
        if (theme.problemTextColor) THEME.problemText = theme.problemTextColor;
        if (theme.stroke) THEME.problemStroke = theme.stroke;
        if (theme.strokeWidth) THEME.problemStrokeWidth = theme.strokeWidth;
        if (theme.categoryColor) THEME.categoryFill = theme.categoryColor;
        if (theme.categoryTextColor) THEME.categoryText = theme.categoryTextColor;
        if (theme.causeColor) THEME.causeFill = theme.causeColor;
        if (theme.causeTextColor) THEME.causeText = theme.causeTextColor;
        if (theme.problemFontSize) THEME.fontProblem = theme.problemFontSize;
        if (theme.categoryFontSize) THEME.fontCategory = theme.categoryFontSize;
        if (theme.causeFontSize) THEME.fontCause = theme.causeFontSize;
        
        if (theme.background) {
            d3.select('#d3-container').style('background-color', theme.background);
        }
    }
    
    const width = baseWidth;
    const height = baseHeight;
    var svg = d3.select('#d3-container').append('svg').attr('width', width).attr('height', height);
    
    // Calculate layout
    const centerX = width / 2;
    const centerY = height / 2;
    const problemRadius = getTextRadius(spec.problem, THEME.fontProblem, 20);
    
    // Draw central problem
    svg.append('circle')
        .attr('cx', centerX)
        .attr('cy', centerY)
        .attr('r', problemRadius)
        .attr('fill', THEME.problemFill)
        .attr('stroke', THEME.problemStroke)
        .attr('stroke-width', THEME.problemStrokeWidth);
    
    svg.append('text')
        .attr('x', centerX)
        .attr('y', centerY)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('fill', THEME.problemText)
        .attr('font-size', THEME.fontProblem)
        .attr('font-weight', 'bold')
        .text(spec.problem);
    
    // Draw main spine (horizontal line)
    const spineLength = width - 2 * padding;
    const spineY = centerY;
    
    svg.append('line')
        .attr('x1', padding)
        .attr('y1', spineY)
        .attr('x2', width - padding)
        .attr('y2', spineY)
        .attr('stroke', '#333')
        .attr('stroke-width', 3);
    
    // Draw categories and causes
    const categoryCount = spec.categories.length;
    const categorySpacing = (spineLength - 2 * problemRadius) / (categoryCount + 1);
    const categoryStartX = padding + problemRadius + categorySpacing;
    
    spec.categories.forEach((category, i) => {
        const categoryX = categoryStartX + i * categorySpacing;
        const categoryY = centerY - 80; // Above spine
        const categoryRadius = getTextRadius(category, THEME.fontCategory, 15);
        
        // Draw category node
        svg.append('circle')
            .attr('cx', categoryX)
            .attr('cy', categoryY)
            .attr('r', categoryRadius)
            .attr('fill', THEME.categoryFill)
            .attr('stroke', THEME.categoryStroke)
            .attr('stroke-width', THEME.categoryStrokeWidth);
        
        svg.append('text')
            .attr('x', categoryX)
            .attr('y', categoryY)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.categoryText)
            .attr('font-size', THEME.fontCategory)
            .attr('font-weight', 'bold')
            .text(category);
        
        // Draw category branch (diagonal line)
        svg.append('line')
            .attr('x1', categoryX)
            .attr('y1', categoryY + categoryRadius)
            .attr('x2', categoryX)
            .attr('y2', spineY)
            .attr('stroke', '#333')
            .attr('stroke-width', 2);
        
        // Draw causes for this category
        const categoryCauses = spec.causes.filter(cause => cause.category === category);
        if (categoryCauses.length > 0) {
            const causeSpacing = 30;
            const causeStartY = categoryY - categoryRadius - 20;
            
            categoryCauses.forEach((cause, j) => {
                const causeY = causeStartY - j * causeSpacing;
                const causeRadius = getTextRadius(cause.name, THEME.fontCause, 10);
                
                // Draw cause node
                svg.append('circle')
                    .attr('cx', categoryX)
                    .attr('cy', causeY)
                    .attr('r', causeRadius)
                    .attr('fill', THEME.causeFill)
                    .attr('stroke', THEME.causeStroke)
                    .attr('stroke-width', THEME.causeStrokeWidth);
                
                svg.append('text')
                    .attr('x', categoryX)
                    .attr('y', causeY)
                    .attr('text-anchor', 'middle')
                    .attr('dominant-baseline', 'middle')
                    .attr('fill', THEME.causeText)
                    .attr('font-size', THEME.fontCause)
                    .text(cause.name);
                
                // Draw cause branch
                svg.append('line')
                    .attr('x1', categoryX)
                    .attr('y1', causeY + causeRadius)
                    .attr('x2', categoryX)
                    .attr('y2', categoryY - categoryRadius)
                    .attr('stroke', '#666')
                    .attr('stroke-width', 1);
            });
        }
    });
    
    // Watermark
    addWatermark(svg, theme);
}

function renderSemanticWeb(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    
    // Validate spec
    if (!spec || !spec.topic || !Array.isArray(spec.branches)) {
        d3.select('#d3-container').append('div').style('color', 'red').text('Invalid spec for semantic web');
        return;
    }
    
    // Use provided theme and dimensions or defaults
    const baseWidth = dimensions?.baseWidth || 800;
    const baseHeight = dimensions?.baseHeight || 600;
    const padding = dimensions?.padding || 40;
    
    const THEME = {
        topicFill: '#4e79a7',
        topicText: '#fff',
        topicStroke: '#35506b',
        topicStrokeWidth: 3,
        branchFill: '#a7c7e7',
        branchText: '#333',
        branchStroke: '#4e79a7',
        branchStrokeWidth: 2,
        subBranchFill: '#f4f6fb',
        subBranchText: '#333',
        subBranchStroke: '#4e79a7',
        subBranchStrokeWidth: 1,
        fontTopic: 20,
        fontBranch: 16,
        fontSubBranch: 14,
        ...theme
    };
    
    // Apply integrated styles if available
    if (theme) {
        if (theme.topicColor) THEME.topicFill = theme.topicColor;
        if (theme.topicTextColor) THEME.topicText = theme.topicTextColor;
        if (theme.stroke) THEME.topicStroke = theme.stroke;
        if (theme.strokeWidth) THEME.topicStrokeWidth = theme.strokeWidth;
        if (theme.branchColor) THEME.branchFill = theme.branchColor;
        if (theme.branchTextColor) THEME.branchText = theme.branchTextColor;
        if (theme.subBranchColor) THEME.subBranchFill = theme.subBranchColor;
        if (theme.subBranchTextColor) THEME.subBranchText = theme.subBranchTextColor;
        if (theme.topicFontSize) THEME.fontTopic = theme.topicFontSize;
        if (theme.branchFontSize) THEME.fontBranch = theme.branchFontSize;
        if (theme.subBranchFontSize) THEME.fontSubBranch = theme.subBranchFontSize;
        
        if (theme.background) {
            d3.select('#d3-container').style('background-color', theme.background);
        }
    }
    
    const width = baseWidth;
    const height = baseHeight;
    var svg = d3.select('#d3-container').append('svg').attr('width', width).attr('height', height);
    
    // Calculate layout
    const centerX = width / 2;
    const centerY = height / 2;
    const topicRadius = getTextRadius(spec.topic, THEME.fontTopic, 20);
    
    // Draw central topic
    svg.append('circle')
        .attr('cx', centerX)
        .attr('cy', centerY)
        .attr('r', topicRadius)
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
    
    // Draw branches in a radial pattern
    const branchCount = spec.branches.length;
    const angleStep = (2 * Math.PI) / branchCount;
    const branchRadius = 120;
    
    spec.branches.forEach((branch, i) => {
        const angle = i * angleStep;
        const branchX = centerX + branchRadius * Math.cos(angle);
        const branchY = centerY + branchRadius * Math.sin(angle);
        const branchNodeRadius = getTextRadius(branch.name, THEME.fontBranch, 15);
        
        // Draw branch node
        svg.append('circle')
            .attr('cx', branchX)
            .attr('cy', branchY)
            .attr('r', branchNodeRadius)
            .attr('fill', THEME.branchFill)
            .attr('stroke', THEME.branchStroke)
            .attr('stroke-width', THEME.branchStrokeWidth);
        
        svg.append('text')
            .attr('x', branchX)
            .attr('y', branchY)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.branchText)
            .attr('font-size', THEME.fontBranch)
            .text(branch.name);
        
        // Draw connecting line from topic to branch
        const dx = branchX - centerX;
        const dy = branchY - centerY;
        const dist = Math.sqrt(dx * dx + dy * dy);
        
        const lineStartX = centerX + (dx / dist) * topicRadius;
        const lineStartY = centerY + (dy / dist) * topicRadius;
        const lineEndX = branchX - (dx / dist) * branchNodeRadius;
        const lineEndY = branchY - (dy / dist) * branchNodeRadius;
        
        svg.append('line')
            .attr('x1', lineStartX)
            .attr('y1', lineStartY)
            .attr('x2', lineEndX)
            .attr('y2', lineEndY)
            .attr('stroke', '#bbb')
            .attr('stroke-width', 2);
        
        // Draw sub-branches
        if (branch.children && branch.children.length > 0) {
            const subBranchCount = branch.children.length;
            const subAngleStep = Math.PI / (subBranchCount + 1);
            const subBranchRadius = 60;
            
            branch.children.forEach((subBranch, j) => {
                const subAngle = angle - Math.PI/2 + (j + 1) * subAngleStep;
                const subBranchX = branchX + subBranchRadius * Math.cos(subAngle);
                const subBranchY = branchY + subBranchRadius * Math.sin(subAngle);
                const subBranchNodeRadius = getTextRadius(subBranch.name, THEME.fontSubBranch, 10);
                
                // Draw sub-branch node
                svg.append('circle')
                    .attr('cx', subBranchX)
                    .attr('cy', subBranchY)
                    .attr('r', subBranchNodeRadius)
                    .attr('fill', THEME.subBranchFill)
                    .attr('stroke', THEME.subBranchStroke)
                    .attr('stroke-width', THEME.subBranchStrokeWidth);
                
                svg.append('text')
                    .attr('x', subBranchX)
                    .attr('y', subBranchY)
                    .attr('text-anchor', 'middle')
                    .attr('dominant-baseline', 'middle')
                    .attr('fill', THEME.subBranchText)
                    .attr('font-size', THEME.fontSubBranch)
                    .text(subBranch.name);
                
                // Draw connecting line from branch to sub-branch
                const subDx = subBranchX - branchX;
                const subDy = subBranchY - branchY;
                const subDist = Math.sqrt(subDx * subDx + subDy * subDy);
                
                const subLineStartX = branchX + (subDx / subDist) * branchNodeRadius;
                const subLineStartY = branchY + (subDy / subDist) * branchNodeRadius;
                const subLineEndX = subBranchX - (subDx / subDist) * subBranchNodeRadius;
                const subLineEndY = subBranchY - (subDy / subDist) * subBranchNodeRadius;
                
                svg.append('line')
                    .attr('x1', subLineStartX)
                    .attr('y1', subLineStartY)
                    .attr('x2', subLineEndX)
                    .attr('y2', subLineEndY)
                    .attr('stroke', '#ddd')
                    .attr('stroke-width', 1);
            });
        }
    });
    
    // Watermark
    addWatermark(svg, theme);
}

function renderGraph(type, spec, theme = null, dimensions = null) {
    console.log('renderGraph called with:', { type, spec, theme, dimensions });
    
    // Clear the container first
    d3.select('#d3-container').html('');
    
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
            renderBridgeMap(spec, integratedTheme, dimensions, 'd3-container');
            break;
        case 'brace_map':
            console.log('Rendering brace map with spec:', spec);
            try {
                renderBraceMap(spec, integratedTheme, dimensions);
                console.log('Brace map rendering completed');
            } catch (error) {
                console.error('Error rendering brace map:', error);
                d3.select('#d3-container').append('div')
                    .style('color', 'red')
                    .text(`Error rendering brace map: ${error.message}`);
            }
            break;
        case 'flow_map':
            renderFlowMap(spec, integratedTheme, dimensions);
            break;
        case 'multi_flow_map':
            renderMultiFlowMap(spec, integratedTheme, dimensions);
            break;
        case 'fishbone_diagram':
            renderFishboneDiagram(spec, integratedTheme, dimensions);
            break;
        case 'semantic_web':
            renderSemanticWeb(spec, integratedTheme, dimensions);
            break;
        default:
            console.error('Unknown graph type:', type);
            d3.select('#d3-container').append('div')
                .style('color', 'red')
                .text(`Error: Unknown graph type: ${type}`);
    }
}

function renderBraceMapAgent(agent_result, theme = null, dimensions = null) {
    console.log('renderBraceMapAgent called with:', { agent_result, theme, dimensions });
    
    // Clear container and ensure it exists
    const container = d3.select('#d3-container');
    if (container.empty()) {
        console.error('d3-container not found');
        return;
    }
    container.html('');
    
    // Validate agent result
    if (!agent_result || !agent_result.success) {
        const errorMsg = agent_result?.error || 'Invalid agent result';
        d3.select('#d3-container').append('div').style('color', 'red').text(`Agent error: ${errorMsg}`);
        return;
    }
    
    const svg_data = agent_result.svg_data;
    if (!svg_data) {
        d3.select('#d3-container').append('div').style('color', 'red').text('No SVG data from agent');
        return;
    }
    
    // Use provided theme or defaults
    const THEME = {
        topicFill: '#4e79a7',
        topicText: '#fff',
        topicStroke: '#35506b',
        topicStrokeWidth: 3,
        partText: '#333',
        subpartText: '#333',
        fontTopic: 20,
        fontPart: 16,
        fontSubpart: 14,
        braceColor: '#666',
        braceWidth: 3,
        ...theme
    };
    
    // Apply integrated styles if available
    if (theme) {
        if (theme.topicColor) THEME.topicFill = theme.topicColor;
        if (theme.topicTextColor) THEME.topicText = theme.topicTextColor;
        if (theme.stroke) THEME.topicStroke = theme.stroke;
        if (theme.strokeWidth) THEME.topicStrokeWidth = theme.strokeWidth;
        if (theme.partTextColor) THEME.partText = theme.partTextColor;
        if (theme.subpartTextColor) THEME.subpartText = theme.subpartTextColor;
        if (theme.topicFontSize) THEME.fontTopic = theme.topicFontSize;
        if (theme.partFontSize) THEME.fontPart = theme.partFontSize;
        if (theme.subpartFontSize) THEME.fontSubpart = theme.subpartFontSize;
        if (theme.braceColor) THEME.braceColor = theme.braceColor;
        if (theme.braceWidth) THEME.braceWidth = theme.braceWidth;
        
        if (theme.background) {
            d3.select('#d3-container').style('background-color', theme.background);
        }
    }
    
    // Get dimensions from agent result
    const finalWidth = svg_data.width || 800;
    const finalHeight = svg_data.height || 600;
    
    console.log('Agent brace map dimensions:', { finalWidth, finalHeight });
    
    // Create SVG with calculated dimensions
    const svg = d3.select('#d3-container').append('svg')
        .attr('width', finalWidth)
        .attr('height', finalHeight)
        .attr('viewBox', `0 0 ${finalWidth} ${finalHeight}`)
        .attr('preserveAspectRatio', 'xMinYMin meet')
        .style('display', 'block')
        .style('background-color', svg_data.background || '#ffffff');
    
    // Validate SVG was created
    if (svg.empty()) {
        console.error('Failed to create SVG element');
        return;
    }
    
    console.log('SVG created successfully with dimensions:', { width: finalWidth, height: finalHeight });
    
    // Group for all content to compute tight bounding box after rendering
    const contentGroup = svg.append('g').attr('class', 'content-group');
    
    // Render SVG elements from agent data
    svg_data.elements.forEach(element => {
        if (element.type === 'text') {
            const textElement = contentGroup.append('text')
                .attr('x', element.x)
                .attr('y', element.y)
                .attr('text-anchor', element.text_anchor || 'middle')
                .attr('dominant-baseline', element.dominant_baseline || 'middle')
                .attr('fill', element.fill || THEME.partText)
                .attr('font-size', element.font_size || THEME.fontPart)
                .text(element.text);
            
            if (element.font_weight) {
                textElement.attr('font-weight', element.font_weight);
            }
            
            console.log(`Rendered text element: ${element.text} at (${element.x}, ${element.y})`);
            
        } else if (element.type === 'rect') {
            const rectElement = contentGroup.append('rect')
                .attr('x', element.x)
                .attr('y', element.y)
                .attr('width', element.width)
                .attr('height', element.height)
                .attr('fill', element.fill || '#ffffff')
                .attr('stroke', element.stroke || 'none');
            
            if (element.rx) {
                rectElement.attr('rx', element.rx);
            }
            if (element.ry) {
                rectElement.attr('ry', element.ry);
            }
            
            console.log(`Rendered rect element at (${element.x}, ${element.y}) with size (${element.width}, ${element.height})`);
            
        } else if (element.type === 'path') {
            contentGroup.append('path')
                .attr('d', element.d)
                .attr('fill', element.fill || 'none')
                .attr('stroke', element.stroke || THEME.braceColor)
                .attr('stroke-width', element.stroke_width || THEME.braceWidth)
                .attr('stroke-linecap', element.stroke_linecap || 'round')
                .attr('stroke-linejoin', element.stroke_linejoin || 'round');
            
            console.log(`Rendered path element: ${element.d.substring(0, 50)}...`);
        }
    });
    
    // After rendering, tighten SVG width to content bounds
    try {
        const bbox = contentGroup.node().getBBox();
        const rightPadding = 8; // small buffer on the right
        // Keep left padding as-is by including bbox.x
        const tightWidth = Math.ceil(bbox.x + bbox.width + rightPadding);
        if (Number.isFinite(tightWidth) && tightWidth > 0 && tightWidth < finalWidth) {
            svg.attr('width', tightWidth).attr('viewBox', `0 0 ${tightWidth} ${finalHeight}`);
            console.log('Adjusted SVG width to tight content bounds:', { tightWidth });
        }
    } catch (e) {
        console.warn('Could not compute tight content bounds:', e);
    }

    // Add watermark
    addWatermark(svg, theme);
    
    console.log('Agent brace map rendering completed');
} 