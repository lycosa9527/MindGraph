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
    
    const THEME = theme || {
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
        fontDiff: 13
    };
    
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
    const w = +svg.attr('width'), h = +svg.attr('height');
    svg.append('text').attr('x', w - 18).attr('y', h - 18)
        .attr('text-anchor', 'end').attr('fill', '#888').attr('font-size', 18)
        .attr('font-family', 'Inter, Segoe UI, sans-serif').attr('opacity', 0.35)
        .attr('pointer-events', 'none').text('D3.js_Dify');
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
    
    const THEME = theme || {
        topicFill: '#4e79a7',
        topicText: '#fff',
        topicStroke: '#35506b',
        topicStrokeWidth: 3,
        attributeFill: '#a7c7e7',
        attributeText: '#333',
        attributeStroke: '#4e79a7',
        attributeStrokeWidth: 2,
        fontTopic: 20,
        fontAttribute: 14
    };
    
    // Calculate sizes
    const topicR = getTextRadius(spec.topic, THEME.fontTopic, 20);
    const attributeR = Math.max(...spec.attributes.map(t => getTextRadius(t, THEME.fontAttribute, 10)), 30);
    
    // Calculate layout - topic in the center, attributes around it
    const centerX = baseWidth / 2;
    const centerY = baseHeight / 2;
    
    // Arrange attributes in a circle around the topic
    const attributeCount = spec.attributes.length;
    const radius = Math.max(topicR + attributeR + 40, 120);
    const angleStep = (2 * Math.PI) / attributeCount;
    
    // Calculate total dimensions
    const minX = centerX - radius - attributeR - padding;
    const maxX = centerX + radius + attributeR + padding;
    const minY = centerY - radius - attributeR - padding;
    const maxY = centerY + radius + attributeR + padding;
    const width = maxX - minX;
    const height = maxY - minY;
    
    const svg = d3.select('#d3-container').append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `${minX} ${minY} ${width} ${height}`)
        .attr('preserveAspectRatio', 'xMinYMin meet');
    
    // Draw connecting lines from topic to attributes
    for (let i = 0; i < attributeCount; i++) {
        const angle = i * angleStep;
        const attrX = centerX + radius * Math.cos(angle);
        const attrY = centerY + radius * Math.sin(angle);
        
        // Calculate line endpoints
        const dx = attrX - centerX;
        const dy = attrY - centerY;
        const dist = Math.sqrt(dx * dx + dy * dy);
        
        const lineStartX = centerX + (dx / dist) * topicR;
        const lineStartY = centerY + (dy / dist) * topicR;
        const lineEndX = attrX - (dx / dist) * attributeR;
        const lineEndY = attrY - (dy / dist) * attributeR;
        
        svg.append('line')
            .attr('x1', lineStartX)
            .attr('y1', lineStartY)
            .attr('x2', lineEndX)
            .attr('y2', lineEndY)
            .attr('stroke', '#888')
            .attr('stroke-width', 2);
    }
    
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
    for (let i = 0; i < attributeCount; i++) {
        const angle = i * angleStep;
        const x = centerX + radius * Math.cos(angle);
        const y = centerY + radius * Math.sin(angle);
        
        svg.append('circle')
            .attr('cx', x)
            .attr('cy', y)
            .attr('r', attributeR)
            .attr('fill', THEME.attributeFill)
            .attr('stroke', THEME.attributeStroke)
            .attr('stroke-width', THEME.attributeStrokeWidth);
        
        svg.append('text')
            .attr('x', x)
            .attr('y', y)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.attributeText)
            .attr('font-size', THEME.fontAttribute)
            .text(spec.attributes[i]);
    }
    
    // Watermark
    const w = +svg.attr('width'), h = +svg.attr('height');
    svg.append('text')
        .attr('x', w - 18)
        .attr('y', h - 18)
        .attr('text-anchor', 'end')
        .attr('fill', '#888')
        .attr('font-size', 18)
        .attr('font-family', 'Inter, Segoe UI, sans-serif')
        .attr('opacity', 0.35)
        .attr('pointer-events', 'none')
        .text('D3.js_Dify');
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
    
    const THEME = theme || {
        topicFill: '#4e79a7',
        topicText: '#fff',
        topicStroke: '#35506b',
        topicStrokeWidth: 3,
        contextFill: '#a7c7e7',
        contextText: '#333',
        contextStroke: '#4e79a7',
        contextStrokeWidth: 2,
        fontTopic: 20,
        fontContext: 14
    };
    
    // Calculate sizes
    const topicR = getTextRadius(spec.topic, THEME.fontTopic, 20);
    const contextR = Math.max(...spec.context.map(t => getTextRadius(t, THEME.fontContext, 10)), 30);
    
    // Calculate layout - circle map has topic in center, context around it
    const centerX = baseWidth / 2;
    const centerY = baseHeight / 2;
    
    // Arrange context items in a circle around the topic
    const contextCount = spec.context.length;
    const radius = Math.max(topicR + contextR + 40, 120);
    const angleStep = (2 * Math.PI) / contextCount;
    
    // Calculate total dimensions
    const minX = centerX - radius - contextR - padding;
    const maxX = centerX + radius + contextR + padding;
    const minY = centerY - radius - contextR - padding;
    const maxY = centerY + radius + contextR + padding;
    const width = maxX - minX;
    const height = maxY - minY;
    
    const svg = d3.select('#d3-container').append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `${minX} ${minY} ${width} ${height}`)
        .attr('preserveAspectRatio', 'xMinYMin meet');
    
    // Draw connecting lines from topic to context
    for (let i = 0; i < contextCount; i++) {
        const angle = i * angleStep;
        const contextX = centerX + radius * Math.cos(angle);
        const contextY = centerY + radius * Math.sin(angle);
        
        // Calculate line endpoints
        const dx = contextX - centerX;
        const dy = contextY - centerY;
        const dist = Math.sqrt(dx * dx + dy * dy);
        
        const lineStartX = centerX + (dx / dist) * topicR;
        const lineStartY = centerY + (dy / dist) * topicR;
        const lineEndX = contextX - (dx / dist) * contextR;
        const lineEndY = contextY - (dy / dist) * contextR;
        
        svg.append('line')
            .attr('x1', lineStartX)
            .attr('y1', lineStartY)
            .attr('x2', lineEndX)
            .attr('y2', lineEndY)
            .attr('stroke', '#888')
            .attr('stroke-width', 2);
    }
    
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
    
    // Draw context circles
    for (let i = 0; i < contextCount; i++) {
        const angle = i * angleStep;
        const x = centerX + radius * Math.cos(angle);
        const y = centerY + radius * Math.sin(angle);
        
        svg.append('circle')
            .attr('cx', x)
            .attr('cy', y)
            .attr('r', contextR)
            .attr('fill', THEME.contextFill)
            .attr('stroke', THEME.contextStroke)
            .attr('stroke-width', THEME.contextStrokeWidth);
        
        svg.append('text')
            .attr('x', x)
            .attr('y', y)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.contextText)
            .attr('font-size', THEME.fontContext)
            .text(spec.context[i]);
    }
    
    // Watermark
    const w = +svg.attr('width'), h = +svg.attr('height');
    svg.append('text')
        .attr('x', w - 18)
        .attr('y', h - 18)
        .attr('text-anchor', 'end')
        .attr('fill', '#888')
        .attr('font-size', 18)
        .attr('font-family', 'Inter, Segoe UI, sans-serif')
        .attr('opacity', 0.35)
        .attr('pointer-events', 'none')
        .text('D3.js_Dify');
}

function renderTreeMap(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    const width = dimensions?.baseWidth || 400;
    const height = dimensions?.baseHeight || 300;
    var svg = d3.select('#d3-container').append('svg').attr('width', width).attr('height', height);
    svg.append('text').attr('x', width/2).attr('y', height/2).attr('text-anchor', 'middle')
        .attr('fill', '#333').attr('font-size', 24).text('Tree Map: ' + spec.topic);
    const w = +svg.attr('width'), h = +svg.attr('height');
    svg.append('text').attr('x', w - 18).attr('y', h - 18).attr('text-anchor', 'end')
        .attr('fill', '#000').attr('font-size', 18).attr('font-family', 'Inter, Segoe UI, sans-serif')
        .attr('opacity', 1).attr('pointer-events', 'none').text('D3.js_Dify');
}

function renderConceptMap(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    const width = dimensions?.baseWidth || 400;
    const height = dimensions?.baseHeight || 300;
    var svg = d3.select('#d3-container').append('svg').attr('width', width).attr('height', height);
    svg.append('text').attr('x', width/2).attr('y', height/2).attr('text-anchor', 'middle')
        .attr('fill', '#333').attr('font-size', 24).text('Concept Map: ' + spec.topic);
    const w = +svg.attr('width'), h = +svg.attr('height');
    svg.append('text').attr('x', w - 18).attr('y', h - 18).attr('text-anchor', 'end')
        .attr('fill', '#000').attr('font-size', 18).attr('font-family', 'Inter, Segoe UI, sans-serif')
        .attr('opacity', 1).attr('pointer-events', 'none').text('D3.js_Dify');
}

function renderMindMap(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    const width = dimensions?.baseWidth || 400;
    const height = dimensions?.baseHeight || 300;
    var svg = d3.select('#d3-container').append('svg').attr('width', width).attr('height', height);
    svg.append('text').attr('x', width/2).attr('y', height/2).attr('text-anchor', 'middle')
        .attr('fill', '#333').attr('font-size', 24).text('Mind Map: ' + spec.topic);
    const w = +svg.attr('width'), h = +svg.attr('height');
    svg.append('text').attr('x', w - 18).attr('y', h - 18).attr('text-anchor', 'end')
        .attr('fill', '#000').attr('font-size', 18).attr('font-family', 'Inter, Segoe UI, sans-serif')
        .attr('opacity', 1).attr('pointer-events', 'none').text('D3.js_Dify');
}

function renderGraph(type, spec, theme = null, dimensions = null) {
    console.log('renderGraph called with:', { type, spec, theme, dimensions });
    
    if (type === 'double_bubble_map') {
        console.log('Calling renderDoubleBubbleMap');
        renderDoubleBubbleMap(spec, theme, dimensions);
    }
    else if (type === 'bubble_map') {
        console.log('Calling renderBubbleMap');
        renderBubbleMap(spec, theme, dimensions);
    }
    else if (type === 'circle_map') {
        console.log('Calling renderCircleMap');
        renderCircleMap(spec, theme, dimensions);
    }
    else if (type === 'tree_map') {
        console.log('Calling renderTreeMap');
        renderTreeMap(spec, theme, dimensions);
    }
    else if (type === 'concept_map') {
        console.log('Calling renderConceptMap');
        renderConceptMap(spec, theme, dimensions);
    }
    else if (type === 'mindmap') {
        console.log('Calling renderMindMap');
        renderMindMap(spec, theme, dimensions);
    }
    else {
        console.error('Unknown graph type:', type);
        d3.select('#d3-container').html('<div style="color: red;">Unknown graph type: ' + type + '</div>');
    }
} 