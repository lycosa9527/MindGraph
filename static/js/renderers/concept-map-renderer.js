/**
 * Concept Map Renderer for MindGraph
 * 
 * This module contains the concept map rendering functions.
 * Requires: shared-utilities.js, style-manager.js
 * 
 * Performance Impact: Loads only ~95KB instead of full 213KB
 */

// CRITICAL DEBUG: Add comprehensive logging
console.log('🔍 Concept map renderer: Module loading started');

function renderConceptMap(spec, theme = null, dimensions = null) {
    console.log('🚀 Concept map renderer: renderConceptMap called with:', { spec, theme, dimensions });
    
    // Check dependencies when function is called
    if (typeof window.MindGraphUtils === 'undefined') {
        console.error('❌ Concept map renderer: MindGraphUtils not found! Please load shared-utilities.js first.');
        d3.select('#d3-container').append('div').style('color', 'red').text('Error: MindGraphUtils not available');
        return;
    }
    
    // Resolve dependencies - CRITICAL FIX: Use const inside function scope to avoid redeclaration errors
    console.log('🔍 Concept map renderer: Resolving dependencies...');
    try {
        const getMeasurementContainer = window.MindGraphUtils.getMeasurementContainer;
        const addWatermark = window.MindGraphUtils.addWatermark;
        
        if (typeof getMeasurementContainer !== 'function' || typeof addWatermark !== 'function') {
            throw new Error('Required functions not available from shared-utilities.js');
        }
        console.log('✅ Concept map renderer: Dependencies resolved successfully');
    } catch (error) {
        console.error('❌ Concept map renderer: Failed to import required functions:', error);
        d3.select('#d3-container').append('div').style('color', 'red').text('Error: Failed to load required functions');
        return;
    }
    
    d3.select('#d3-container').html('');
    console.log('✅ Concept map renderer: Container cleared');
    
    console.log('🔍 Concept map renderer: Validating spec...');
    if (!spec || !spec.topic || !Array.isArray(spec.concepts) || !Array.isArray(spec.relationships)) {
        console.error('❌ Concept map renderer: Invalid spec for concept map:', { spec, topic: spec?.topic, concepts: spec?.concepts, relationships: spec?.relationships });
        d3.select('#d3-container').append('div').style('color', 'red').text('Invalid spec for concept map');
        return;
    }
    console.log('✅ Concept map renderer: Spec validation passed');
    
    const baseWidth = dimensions?.baseWidth || 1600;
    const baseHeight = dimensions?.baseHeight || 1000;
    const padding = dimensions?.padding || 80;
    
    // Starting concept map rendering with specified dimensions
    
    // Check for configurable padding from spec
    const earlyConfig = spec._config || {};
    const configPadding = earlyConfig.canvasPadding || padding;

    let THEME;
    try {
        if (typeof styleManager !== 'undefined' && styleManager.getTheme) {
            THEME = styleManager.getTheme('concept_map', theme, theme);
        } else {
            THEME = {
                topicFill: '#e3f2fd',
                topicText: '#000',
                topicStroke: '#35506b',
                topicStrokeWidth: 2,
                conceptFill: '#e3f2fd',
                conceptText: '#333',
                conceptStroke: '#4e79a7',
                conceptStrokeWidth: 2,
                relationshipColor: '#666',
                relationshipStrokeWidth: 2,
                fontTopic: 26,
                fontConcept: 22,
                background: '#ffffff'
            };
        }
    } catch (e) {
        THEME = {
            topicFill: '#e3f2fd',
            topicText: '#000',
            topicStroke: '#35506b',
            topicStrokeWidth: 2,
            conceptFill: '#e3f2fd',
            conceptText: '#333',
            conceptStroke: '#4e79a7',
            conceptStrokeWidth: 2,
            relationshipColor: '#666',
            relationshipStrokeWidth: 2,
            fontTopic: 18,
            fontConcept: 14,
            background: '#ffffff'
        };
    }
    
    if (theme && theme.background) {
        d3.select('#d3-container').style('background-color', theme.background);
    }
    
    // If layout positions are normalized and include extents, we'll size after computing positions.
    let width = baseWidth;
    let height = baseHeight;
    
    // Use backend adaptive sizing - disable conflicting D3.js expansion
    // The backend already calculates optimal canvas size based on SVG elements
    // This old logic was creating oversized canvases that override backend calculations
    
    const svg = d3.select('#d3-container').append('svg').attr('width', width).attr('height', height);

    // Arrowhead marker for directed relationships
    const defs = svg.append('defs');
    defs.append('marker')
        .attr('id', 'arrowhead')
        .attr('viewBox', '0 0 10 8')
        .attr('refX', 9)
        .attr('refY', 4)
        .attr('markerWidth', 10)
        .attr('markerHeight', 8)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M 0 0 L 10 4 L 0 8 z')
        .attr('fill', THEME.relationshipColor);

    // Helpers for text wrapping and box measurement
    function measureLineWidth(text, fontSize) {
        const container = getMeasurementContainer();
        const t = container.append('svg').append('text').attr('font-size', fontSize).text(text);
        const w = t.node().getBBox().width;
        t.remove();
        return w;
    }

    function wrapIntoLines(text, fontSize, maxWidth) {
        const words = String(text).split(/\s+/);
        const lines = [];
        let current = '';
        for (const w of words) {
            const candidate = current ? current + ' ' + w : w;
            if (measureLineWidth(candidate, fontSize) <= maxWidth || current === '') {
                current = candidate;
            } else {
                lines.push(current);
                current = w;
            }
        }
        if (current) lines.push(current);
        return lines;
    }

    function drawBox(x, y, text, isTopic = false) {
        const fontSize = isTopic ? THEME.fontTopic : THEME.fontConcept;
        const maxTextWidth = isTopic ? 350 : 300;
        const lines = wrapIntoLines(text, fontSize, maxTextWidth);
        const lineHeight = Math.round(fontSize * 1.2);
        const textWidth = Math.max(...lines.map(l => measureLineWidth(l, fontSize)), 20);
        const paddingX = 16;
        const paddingY = 10;
        const boxW = Math.ceil(textWidth + paddingX * 2);
        const boxH = Math.ceil(lines.length * lineHeight + paddingY * 2);

        const group = svg.append('g');
        group.append('rect')
            .attr('x', x - boxW / 2)
            .attr('y', y - boxH / 2)
            .attr('rx', 8)
            .attr('ry', 8)
            .attr('width', boxW)
            .attr('height', boxH)
            .attr('fill', isTopic ? THEME.topicFill : THEME.conceptFill)
            .attr('stroke', isTopic ? THEME.topicStroke : THEME.conceptStroke)
            .attr('stroke-width', isTopic ? THEME.topicStrokeWidth : THEME.conceptStrokeWidth);

        const textEl = group.append('text')
            .attr('x', x)
            .attr('y', y - (lines.length - 1) * lineHeight / 2)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
            .attr('fill', isTopic ? THEME.topicText : THEME.conceptText)
            .attr('font-size', fontSize)
            .attr('font-weight', isTopic ? '600' : '400');
        lines.forEach((ln, i) => {
            textEl.append('tspan').attr('x', x).attr('dy', i === 0 ? 0 : lineHeight).text(ln);
        });

        return { x, y, width: boxW, height: boxH, group };
    }

    // Check if we have pre-computed positions from the backend
    if (spec._layout && spec._layout.positions) {
        // Using backend-calculated positions
        const positions = spec._layout.positions;
        const extents = spec._layout.extents;
        
        // If we have extents, use them to set canvas size
        if (extents) {
            const margin = configPadding;
            width = Math.ceil(extents.maxX - extents.minX + 2 * margin);
            height = Math.ceil(extents.maxY - extents.minY + 2 * margin);
            svg.attr('width', width).attr('height', height);
            // Updated canvas size based on backend extents
        }
        
        const boxes = {};
        
        // Draw topic first
        if (positions.topic) {
            const pos = positions.topic;
            boxes.topic = drawBox(pos.x, pos.y, spec.topic, true);
        }
        
        // Draw concepts
        spec.concepts.forEach((concept, i) => {
            const pos = positions.concepts && positions.concepts[i];
            if (pos) {
                boxes[`concept_${i}`] = drawBox(pos.x, pos.y, concept, false);
            }
        });
        
        // Draw relationships
        spec.relationships.forEach((rel, i) => {
            const pos = positions.relationships && positions.relationships[i];
            if (pos) {
                const from = boxes[rel.from] || boxes.topic;
                const to = boxes[rel.to] || boxes[`concept_${spec.concepts.indexOf(rel.to.replace('concept_', ''))}`];
                
                if (from && to) {
                    // Draw connecting line
                    svg.append('line')
                        .attr('x1', from.x)
                        .attr('y1', from.y)
                        .attr('x2', to.x)
                        .attr('y2', to.y)
                        .attr('stroke', THEME.relationshipColor)
                        .attr('stroke-width', THEME.relationshipStrokeWidth)
                        .attr('marker-end', 'url(#arrowhead)');
                    
                    // Draw relationship label at midpoint
                    const midX = (from.x + to.x) / 2;
                    const midY = (from.y + to.y) / 2;
                    
                    svg.append('text')
                        .attr('x', midX)
                        .attr('y', midY)
                        .attr('text-anchor', 'middle')
                        .attr('dominant-baseline', 'middle')
                        .attr('fill', THEME.relationshipColor)
                        .attr('font-size', 12)
                        .attr('font-weight', 'bold')
                        .style('background', 'white')
                        .text(rel.label || '');
                }
            }
        });
    } else {
        // Fallback to D3 force layout
        // Falling back to D3 force layout
        renderConceptMapWithForceLayout(spec, svg, THEME, width, height);
    }
    
    // Watermark - matching mindmap style
    const watermarkText = 'MindGraph';
    
    // Get SVG dimensions
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
    
    // Add watermark with proper styling - matching mindmap
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

function renderConceptMapWithForceLayout(spec, svg, THEME, width, height) {
    // Create nodes for topic and concepts
    const nodes = [
        { id: 'topic', text: spec.topic, isTopic: true, x: width / 2, y: height / 2 }
    ];
    
    spec.concepts.forEach((concept, i) => {
        nodes.push({
            id: `concept_${i}`,
            text: concept,
            isTopic: false,
            x: Math.random() * width,
            y: Math.random() * height
        });
    });
    
    // Create links from relationships
    const links = [];
    spec.relationships.forEach(rel => {
        const sourceId = rel.from === 'topic' ? 'topic' : `concept_${spec.concepts.indexOf(rel.from)}`;
        const targetId = rel.to === 'topic' ? 'topic' : `concept_${spec.concepts.indexOf(rel.to)}`;
        
        if (sourceId !== targetId) {
            links.push({
                source: sourceId,
                target: targetId,
                label: rel.label || ''
            });
        }
    });
    
    // Create force simulation
    const simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(links).id(d => d.id).distance(200))
        .force('charge', d3.forceManyBody().strength(-1000))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(60));
    
    // Draw links
    const linkGroup = svg.append('g').attr('class', 'links');
    const link = linkGroup.selectAll('line')
        .data(links)
        .enter().append('line')
        .attr('stroke', THEME.relationshipColor)
        .attr('stroke-width', THEME.relationshipStrokeWidth)
        .attr('marker-end', 'url(#arrowhead)');
    
    // Draw nodes
    const nodeGroup = svg.append('g').attr('class', 'nodes');
    const node = nodeGroup.selectAll('g')
        .data(nodes)
        .enter().append('g');
    
    // Add circles to nodes
    node.append('circle')
        .attr('r', d => d.isTopic ? 40 : 30)
        .attr('fill', d => d.isTopic ? THEME.topicFill : THEME.conceptFill)
        .attr('stroke', d => d.isTopic ? THEME.topicStroke : THEME.conceptStroke)
        .attr('stroke-width', d => d.isTopic ? THEME.topicStrokeWidth : THEME.conceptStrokeWidth);
    
    // Add text to nodes
    node.append('text')
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('fill', d => d.isTopic ? THEME.topicText : THEME.conceptText)
        .attr('font-size', d => d.isTopic ? THEME.fontTopic : THEME.fontConcept)
        .attr('font-weight', d => d.isTopic ? '600' : '400')
        .text(d => d.text.length > 15 ? d.text.substring(0, 15) + '...' : d.text);
    
    // Update positions on simulation tick
    simulation.on('tick', () => {
        link
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);
        
        node
            .attr('transform', d => `translate(${d.x},${d.y})`);
    });
    
    // Add drag behavior
    node.call(d3.drag()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended));
    
    function dragstarted(event, d) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    }
    
    function dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
    }
    
    function dragended(event, d) {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
    }
    
    console.log('✅ Concept map renderer: Rendering completed successfully');
}

// Export functions for module system
if (typeof window !== 'undefined') {
    // Browser environment - attach to window
    window.ConceptMapRenderer = {
        renderConceptMap,
        renderConceptMapWithForceLayout
    };
    
    // CRITICAL FIX: Also expose renderConceptMap globally for backward compatibility
    // This prevents the "renderConceptMap is not defined" error
    if (typeof window.renderConceptMap === 'undefined') {
        window.renderConceptMap = renderConceptMap;
    }
    
    // ConceptMapRenderer exported to window.ConceptMapRenderer
    console.log('✅ Concept map renderer: Module loaded successfully in browser environment');
} else if (typeof module !== 'undefined' && module.exports) {
    // Node.js environment
    module.exports = {
        renderConceptMap,
        renderConceptMapWithForceLayout
    };
    console.log('✅ Concept map renderer: Module loaded successfully in Node.js environment');
} else {
    console.error('❌ Concept map renderer: Module failed to load in any environment');
}
