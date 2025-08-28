/**
 * Concept Map Renderer - D3.js Implementation
 * 
 * This file contains the dedicated D3.js renderer for concept maps.
 * It renders concept maps using radial layout with concentric circles around the central topic.
 * 
 * Author: lycosa9527
 * Made by MindSpring Team
 */

// --- Safe, memory-leak-free text measurement ---
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

// --- Helper functions ---

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
        
        // Position in lower right corner
        watermarkX = w - padding;
        watermarkY = h - padding;
    }
    
    // Add watermark text
    svg.append('text')
        .attr('x', watermarkX)
        .attr('y', watermarkY)
        .attr('text-anchor', 'end')
        .attr('dominant-baseline', 'hanging')
        .attr('fill', theme?.watermarkColor || '#999')
        .attr('font-size', watermarkFontSize)
        .attr('font-family', 'Arial, sans-serif')
        .attr('opacity', 0.6)
        .text(watermarkText);
}

// --- Main Concept Map Renderer ---

/**
 * Renders a concept map using D3.js with radial layout
 * @param {Object} spec - Concept map specification
 * @param {Object} theme - Theme configuration (optional)
 * @param {Object} dimensions - Canvas dimensions (optional)
 */
function renderConceptMap(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    
    if (!spec || !spec.topic || !Array.isArray(spec.concepts) || !Array.isArray(spec.relationships)) {
        d3.select('#d3-container').append('div').style('color', 'red').text('Invalid spec for concept map');
        return;
    }
    
    const baseWidth = dimensions?.baseWidth || 1600;
    const baseHeight = dimensions?.baseHeight || 1000;
    const padding = dimensions?.padding || 80;
    
    console.log('Concept Map Renderer starting dimensions:', {
        received: dimensions,
        using: {width: baseWidth, height: baseHeight, padding: padding}
    });

    // DEBUG: Log layout information
    console.log('=== CONCEPT MAP LAYOUT DEBUG ===');
    const layout = spec._layout || {};
    console.log('Layout object:', layout);
    console.log('Layout algorithm:', layout.algorithm || 'unknown');
    console.log('Layout keys:', Object.keys(layout));
    if (layout.params) {
        console.log('Layout params:', layout.params);
    }
    if (layout.positions) {
        console.log('Positions count:', Object.keys(layout.positions).length);
        // Log a few sample positions
        const samplePositions = Object.entries(layout.positions).slice(0, 3);
        console.log('Sample positions:', samplePositions);
    }
    console.log('=== END LAYOUT DEBUG ===');
    
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
                background: '#f5f5f5'
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
            background: '#f5f5f5'
        };
    }
    
    // Apply container background (like mind map does)
    const containerBackground = THEME.background || '#f5f5f5';
    d3.select('#d3-container')
        .style('background-color', containerBackground, 'important')
        .style('width', '100%')
        .style('height', '100%');
    
    // Override with custom theme background if provided
    if (theme && theme.background) {
        d3.select('#d3-container').style('background-color', theme.background, 'important');
    }
    
    let width = baseWidth;
    let height = baseHeight;
    
    const svg = d3.select('#d3-container').append('svg').attr('width', width).attr('height', height);

    // Add background rectangle to cover entire canvas
    svg.append('rect')
        .attr('width', width)
        .attr('height', height)
        .attr('fill', THEME.background || '#f5f5f5')
        .attr('x', 0)
        .attr('y', 0)
        .attr('class', 'background-rect');

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

    function rectBorderPoint(rect, targetX, targetY) {
        const halfW = rect.width / 2;
        const halfH = rect.height / 2;
        const dx = targetX - rect.x;
        const dy = targetY - rect.y;
        if (dx === 0 && dy === 0) return { x: rect.x, y: rect.y };
        const absDx = Math.abs(dx);
        const absDy = Math.abs(dy);
        const scaleX = halfW / absDx;
        const scaleY = halfH / absDy;
        if (scaleX < scaleY) {
            const x = rect.x + Math.sign(dx) * halfW;
            const y = rect.y + dy * scaleX;
            return { x, y };
        } else {
            const y = rect.y + Math.sign(dy) * halfH;
            const x = rect.x + dx * scaleY;
            return { x, y };
        }
    }

    function drawEdgeLabel(x, y, text, fontSize, color) {
        const paddingX = 4;
        const paddingY = 2;
        const group = svg.append('g');
        const label = group.append('text')
            .attr('x', x)
            .attr('y', y)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', color)
            .attr('font-size', fontSize)
            .style('font-style', 'italic')
            .text(text || '');
        try {
            const bbox = label.node().getBBox();
            group.insert('rect', 'text')
                .attr('x', bbox.x - paddingX)
                .attr('y', bbox.y - paddingY)
                .attr('width', bbox.width + 2 * paddingX)
                .attr('height', bbox.height + 2 * paddingY)
                .attr('rx', 3)
                .attr('ry', 3)
                .attr('fill', '#ffffff')
                .attr('fill-opacity', 0.9);
        } catch (e) {
            // If bbox fails, fallback to stroke halo
            label
                .style('paint-order', 'stroke')
                .style('stroke', '#ffffff')
                .style('stroke-width', '3px');
        }
    }

    function measureLabelBox(text, fontSize) {
        const paddingX = 4;
        const paddingY = 2;
        const width = measureLineWidth(text || '', fontSize) + 2 * paddingX;
        const height = Math.round(fontSize * 1.2) + 2 * paddingY;
        return { width, height };
    }

    function rectsOverlap(a, b) {
        // a, b: {x, y, width, height} centered at a.x,a.y
        const ax1 = a.x - a.width / 2; const ax2 = a.x + a.width / 2;
        const ay1 = a.y - a.height / 2; const ay2 = a.y + a.height / 2;
        const bx1 = b.x - b.width / 2; const bx2 = b.x + b.width / 2;
        const by1 = b.y - b.height / 2; const by2 = b.y + b.height / 2;
        return !(ax2 < bx1 || ax1 > bx2 || ay2 < by1 || ay1 > by2);
    }

    function findNonOverlappingLabelPosition(midX, midY, nx, ny, tx, ty, labelW, labelH, nodeRects, placedRects) {
        const attempts = [];
        const distances = [0, 10, 20, 30, 40, 50, 60];
        for (const d of distances) {
            attempts.push({ x: midX + nx * d, y: midY + ny * d });  // along normal
            attempts.push({ x: midX - nx * d, y: midY - ny * d });  // opposite normal
            attempts.push({ x: midX + tx * d, y: midY + ty * d });  // along tangent
            attempts.push({ x: midX - tx * d, y: midY - ty * d });  // opposite tangent
            // small diagonal mixes
            attempts.push({ x: midX + (nx + tx) * d * 0.7, y: midY + (ny + ty) * d * 0.7 });
            attempts.push({ x: midX + (nx - tx) * d * 0.7, y: midY + (ny - ty) * d * 0.7 });
        }
        for (const p of attempts) {
            const candidate = { x: p.x, y: p.y, width: labelW, height: labelH };
            let overlaps = false;
            for (const nr of nodeRects) {
                if (rectsOverlap(candidate, nr)) { overlaps = true; break; }
            }
            if (overlaps) continue;
            for (const pr of placedRects) {
                if (rectsOverlap(candidate, pr)) { overlaps = true; break; }
            }
            if (!overlaps) return { x: p.x, y: p.y };
        }
        return { x: midX, y: midY }; // fallback
    }

    const centerX = width / 2;
    const centerY = height / 2;
    
    // Always ensure topic is at canvas center
    let topicBox = drawBox(centerX, centerY, spec.topic, true);

    // Configuration constants - now configurable through theme
    const LAYOUT_CONFIG = {
        // Coordinate system configuration
        coordinateRange: 10.0,           // Maximum coordinate range for normalization
        coordinateScaleDivisor: 12.0,    // Divisor for coordinate scaling (was hardcoded 12)
        
        // Radial layout configuration
        innerRadius: 0.35,               // Inner radius for primary concepts (was hardcoded 0.35)
        minRadius: 0.55,                 // Minimum radius for secondary concepts (was hardcoded 0.55)
        maxRadius: 0.9,                  // Maximum radius for secondary concepts (was hardcoded 0.9)
        sectorGap: 0.8,                  // Gap between sectors (was hardcoded 0.8)
        maxPrimaryConcepts: 6,           // Maximum number of primary concepts to position optimally
        
        // Spacing configuration
        minSpacingScale: 0.8,           // Minimum spacing scale (was hardcoded)
        maxSpacingScale: 2.0,           // Maximum spacing scale (was hardcoded)
        defaultSpacingScale: 1.0,       // Default spacing scale
        
        // Overlap resolution configuration
        overlapMargin: 8,                // Margin for overlap resolution (was hardcoded 8)
        maxOverlapIterations: 16,        // Maximum iterations for overlap resolution (was hardcoded 16)
        
        // Canvas expansion configuration
        canvasMargin: 60,                // Margin around content (was hardcoded 60)
        maxExpansionFactor: 1.1,        // Maximum canvas expansion (was hardcoded 1.1)
        
        // Validation configuration
        minValidCoordinate: -1000,       // Minimum valid coordinate value
        maxValidCoordinate: 1000         // Maximum valid coordinate value
    };

    // Read layout and parameters
    const params = layout.params || {};
    const positions = layout.positions || {};
    const edgeCurvatures = layout.edgeCurvatures || {};

    // Determine whether we have normalized positions from agent
    function isNormalized(p) {
        if (typeof p.x !== 'number' || typeof p.y !== 'number') return false;
        return p.x <= LAYOUT_CONFIG.coordinateRange && p.x >= -LAYOUT_CONFIG.coordinateRange && 
               p.y <= LAYOUT_CONFIG.coordinateRange && p.y >= -LAYOUT_CONFIG.coordinateRange;
    }

    // Consolidated coordinate transformation function
    function transformToCanvas(p) {
        if (!p || typeof p.x !== 'number' || typeof p.y !== 'number') {
            console.warn('Invalid position data:', p);
            return { x: centerX, y: centerY };
        }
        
        if (isNormalized(p)) {
            const scaleX = (width - 2 * configPadding) / LAYOUT_CONFIG.coordinateScaleDivisor;
            const scaleY = (height - 2 * configPadding) / LAYOUT_CONFIG.coordinateScaleDivisor;
            const px = centerX + (p.x * scaleX);
            const py = centerY + (p.y * scaleY);
            
            // Validate transformed coordinates
            if (px < LAYOUT_CONFIG.minValidCoordinate || px > LAYOUT_CONFIG.maxValidCoordinate ||
                py < LAYOUT_CONFIG.minValidCoordinate || py > LAYOUT_CONFIG.maxValidCoordinate) {
                console.warn('Transformed coordinates out of bounds:', { input: p, output: { x: px, y: py } });
                return { x: centerX, y: centerY };
            }
            
            return { x: px, y: py };
        }
        
        // If not normalized, validate and return as-is
        if (p.x < LAYOUT_CONFIG.minValidCoordinate || p.x > LAYOUT_CONFIG.maxValidCoordinate ||
            p.y < LAYOUT_CONFIG.minValidCoordinate || p.y > LAYOUT_CONFIG.maxValidCoordinate) {
            console.warn('Raw coordinates out of bounds:', p);
            return { x: centerX, y: centerY };
        }
        
        return p;
    }

    // Always use positions from agent (radial layout)
    let useSectors = (positions && Object.keys(positions).length > 0);
    
    // DEBUG: Log layout decision logic
    console.log('=== CONCEPT MAP LAYOUT DECISION DEBUG ===');
    console.log('Has positions from agent:', !!positions);
    console.log('Positions count:', positions ? Object.keys(positions).length : 0);
    console.log('Will use sectors:', useSectors);
    console.log('Layout algorithm: radial (forced)');
    console.log('=== END LAYOUT DECISION DEBUG ===');
    
    const nodes = {};

    if (!useSectors) {
        // Compute simple sector positions on the fly if agent did not provide them
        const N = Math.max(1, spec.concepts.length);
        const keys = spec.concepts.slice(0, Math.min(LAYOUT_CONFIG.maxPrimaryConcepts, N));
        const sectorSpan = (2 * Math.PI) / Math.max(1, keys.length);
        
        const pos = { [spec.topic]: { x: 0, y: 0 } };
        
        // Position primary concepts in optimal sectors
        keys.forEach((k, i) => {
            const ang = -Math.PI / 2 + i * sectorSpan;
            pos[k] = { 
                x: LAYOUT_CONFIG.innerRadius * Math.cos(ang), 
                y: LAYOUT_CONFIG.innerRadius * Math.sin(ang) 
            };
        });
        
        // Position remaining concepts in secondary sectors
        let idx = 0;
        spec.concepts.forEach(c => {
            if (keys.includes(c)) return;
            
            const i = idx % Math.max(1, keys.length);
            const centerAng = -Math.PI / 2 + i * sectorSpan;
            const half = (sectorSpan * LAYOUT_CONFIG.sectorGap) / 2;
            const t = ((idx / keys.length) % 1);
            const ang = centerAng - half + t * (2 * half);
            
            // Use more intelligent radius calculation instead of magic number 3
            const radiusTier = Math.floor(idx / keys.length);
            const radiusStep = (LAYOUT_CONFIG.maxRadius - LAYOUT_CONFIG.minRadius) / Math.max(1, radiusTier + 1);
            const rad = LAYOUT_CONFIG.minRadius + (radiusTier * radiusStep);
            
            pos[c] = { x: rad * Math.cos(ang), y: rad * Math.sin(ang) };
            idx++;
        });
        positions = pos;
        useSectors = true;
    }


    
    // Always pin topic at canvas center for radial layout
    const tp = { x: centerX, y: centerY };
    topicBox = drawBox(tp.x, tp.y, spec.topic, true);
    
    // Apply optional node spacing scale from agent or config
    const config = spec._config || {};
    let spacingScale = typeof params.nodeSpacing === 'number' ? 
        Math.max(LAYOUT_CONFIG.minSpacingScale, Math.min(LAYOUT_CONFIG.maxSpacingScale, params.nodeSpacing)) : 
        typeof config.nodeSpacing === 'number' ? 
            Math.max(LAYOUT_CONFIG.minSpacingScale, Math.min(LAYOUT_CONFIG.maxSpacingScale, config.nodeSpacing)) : 
            LAYOUT_CONFIG.defaultSpacingScale;
    
    // DEBUG: Log spacing scale calculation
    console.log('=== SPACING SCALE DEBUG ===');
    console.log('Params nodeSpacing:', params.nodeSpacing);
    console.log('Config nodeSpacing:', config.nodeSpacing);
    console.log('Calculated spacingScale:', spacingScale);
    console.log('=== END SPACING SCALE DEBUG ===');
    
    // Always use radial layout spacing for optimal concept map visualization
    console.log('Using radial layout spacing scale:', spacingScale);
    spec.concepts.forEach(c => {
        const p = positions[c];
        if (!p || typeof p.x !== 'number' || typeof p.y !== 'number') {
            console.warn(`Invalid position for concept "${c}":`, p);
            // Fallback to center position with warning
            const pc = { x: centerX, y: centerY };
            nodes[c] = { label: c, box: drawBox(pc.x, pc.y, c, false) };
            return;
        }
        
        // Scale normalized vector away from center to increase spacing
        const scaled = { x: p.x * spacingScale, y: p.y * spacingScale };
        const pc = transformToCanvas(scaled);
        
        // DEBUG: Log coordinate transformation
        console.log('Coordinate transformation:', {
            input: p,
            scaled: scaled,
            output: pc,
            spacingScale: spacingScale
        });
        
        // DEBUG: Log positioning for each concept
        console.log(`Positioning concept "${c}":`, {
            original: p,
            scaled: scaled,
            canvas: pc,
            spacingScale: spacingScale
        });
        
        nodes[c] = { label: c, box: drawBox(pc.x, pc.y, c, false) };
    });

    // Nudge pass: resolve rectangle overlaps between nodes
    (function nudgeNodeOverlaps() {
        const entries = [
            { key: '__topic__', fixed: true, box: topicBox },
            ...Object.values(nodes).map(n => ({ key: n.label, fixed: false, box: n.box }))
        ];
        
        console.log(`Using radial layout margin (${LAYOUT_CONFIG.overlapMargin}px) for optimal concept map visualization`);
        
        let totalOverlaps = 0;
        let resolvedOverlaps = 0;
        
        for (let iter = 0; iter < LAYOUT_CONFIG.maxOverlapIterations; iter++) {
            let moved = false;
            let iterationOverlaps = 0;
            
            for (let i = 0; i < entries.length; i++) {
                for (let j = i + 1; j < entries.length; j++) {
                    const a = entries[i].box; 
                    const b = entries[j].box;
                    
                    if (!a || !b || !a.width || !a.height || !b.width || !b.height) {
                        console.warn('Invalid box data for overlap resolution:', { a, b });
                        continue;
                    }
                    
                    const halfWsum = (a.width + b.width) / 2 + LAYOUT_CONFIG.overlapMargin;
                    const halfHsum = (a.height + b.height) / 2 + LAYOUT_CONFIG.overlapMargin;
                    const dx = b.x - a.x; 
                    const dy = b.y - a.y;
                    const overlapX = halfWsum - Math.abs(dx);
                    const overlapY = halfHsum - Math.abs(dy);
                    
                    if (overlapX > 0 && overlapY > 0) {
                        iterationOverlaps++;
                        totalOverlaps++;
                        
                        // Minimal translation to separate: along axis with smaller overlap
                        if (overlapX < overlapY) {
                            const push = overlapX / 2 + 0.5;
                            const dir = Math.sign(dx) || (Math.random() < 0.5 ? 1 : -1);
                            
                            if (!entries[i].fixed && !entries[j].fixed) {
                                a.x -= dir * push;
                                b.x += dir * push;
                                moved = true;
                            } else if (entries[i].fixed && !entries[j].fixed) {
                                b.x += dir * (2 * push);
                                moved = true;
                            } else if (!entries[i].fixed && entries[j].fixed) {
                                a.x -= dir * (2 * push);
                                moved = true;
                            }
                        } else {
                            const push = overlapY / 2 + 0.5;
                            const dir = Math.sign(dy) || (Math.random() < 0.5 ? 1 : -1);
                            
                            if (!entries[i].fixed && !entries[j].fixed) {
                                a.y -= dir * push;
                                b.y += dir * push;
                                moved = true;
                            } else if (entries[i].fixed && !entries[j].fixed) {
                                b.y += dir * (2 * push);
                                moved = true;
                            } else if (!entries[i].fixed && entries[j].fixed) {
                                b.y += dir * (2 * push);
                                moved = true;
                            }
                        }
                    }
                }
            }
            
            if (iterationOverlaps === 0) {
                resolvedOverlaps = totalOverlaps;
                break;
            }
            
            if (!moved) {
                console.warn(`Overlap resolution stuck at iteration ${iter + 1} with ${iterationOverlaps} overlaps`);
                break;
            }
        }
        
        console.log(`Overlap resolution completed: ${resolvedOverlaps} overlaps resolved in ${Math.min(LAYOUT_CONFIG.maxOverlapIterations, totalOverlaps)} iterations`);
        
        // Apply visual transforms for moved nodes
        entries.forEach(entry => {
            const b = entry.box;
            if (b && b.group) {
                try {
                    const rect = b.group.select('rect');
                    if (!rect.empty()) {
                        const currentX = +rect.attr('x') + b.width / 2;
                        const currentY = +rect.attr('y') + b.height / 2;
                        const dx = b.x - currentX;
                        const dy = b.y - currentY;
                        
                        if (Math.abs(dx) > 0.1 || Math.abs(dy) > 0.1) {
                            const prev = b.group.attr('transform') || '';
                            b.group.attr('transform', `${prev} translate(${dx},${dy})`);
                        }
                    }
                } catch (e) { 
                    console.warn('Error applying visual transform:', e);
                }
            }
        });
    })();

    // After placing nodes, center the topic in the canvas and size symmetrically around it
    try {
        const allBoxes = [topicBox, ...Object.values(nodes).map(n => n.box)];
        const minX = Math.min(...allBoxes.map(b => b.x - b.width / 2));
        const maxX = Math.max(...allBoxes.map(b => b.x + b.width / 2));
        const minY = Math.min(...allBoxes.map(b => b.y - b.height / 2));
        const maxY = Math.max(...allBoxes.map(b => b.y + b.height / 2));
        const margin = LAYOUT_CONFIG.canvasMargin;
        const leftSpan = topicBox.x - minX;
        const rightSpan = maxX - topicBox.x;
        const topSpan = topicBox.y - minY;
        const bottomSpan = maxY - topicBox.y;
        const maxHoriz = Math.max(leftSpan, rightSpan);
        const maxVert = Math.max(topSpan, bottomSpan);
        const neededW = Math.ceil(maxHoriz * 2 + 2 * margin);
        const neededH = Math.ceil(maxVert * 2 + 2 * margin);
        if (neededW > 0 && neededH > 0) {
            // Respect the adaptive canvas sizing - only expand if absolutely necessary
            const minExpansion = LAYOUT_CONFIG.maxExpansionFactor; // Allow only 10% expansion beyond calculated size
            const maxAllowedW = Math.ceil(width * minExpansion);
            const maxAllowedH = Math.ceil(height * minExpansion);
            
            width = Math.min(Math.max(width, neededW), maxAllowedW);
            height = Math.min(Math.max(height, neededH), maxAllowedH);
            
            console.log('Concept Map expansion control:', {
                original: {w: baseWidth, h: baseHeight},
                needed: {w: neededW, h: neededH},
                maxAllowed: {w: maxAllowedW, h: maxAllowedH},
                final: {w: width, h: height}
            });
            
            svg.attr('width', width).attr('height', height);
            
            // Update background rectangle to cover new dimensions
            svg.select('.background-rect').attr('width', width).attr('height', height);
            
            // Translate so that topic is at the geometric center
            const dx = (width / 2) - topicBox.x;
            const dy = (height / 2) - topicBox.y;
            const g = svg.append('g').attr('class', 'cm-shift').attr('transform', `translate(${dx},${dy})`);
            const existing = svg.selectAll('svg > *:not(defs):not(.cm-shift):not(.background-rect)').nodes();
            existing.forEach(node => { g.node().appendChild(node); });
            topicBox = { ...topicBox, x: topicBox.x + dx, y: topicBox.y + dy };
            Object.keys(nodes).forEach(k => {
                nodes[k].box = { ...nodes[k].box, x: nodes[k].box.x + dx, y: nodes[k].box.y + dy };
            });
        }
    } catch (e) {
        // Safe fallback if bbox sizing fails
    }

    // Prepare node rectangles for label overlap checks
    const nodeRects = [
        { x: topicBox.x, y: topicBox.y, width: topicBox.width, height: topicBox.height },
        ...Object.values(nodes).map(n => ({ x: n.box.x, y: n.box.y, width: n.box.width, height: n.box.height }))
    ];

    // Draw relationships as curved, directed edges with labels
    const fontRel = THEME.fontRelationship || Math.max(12, Math.round((THEME.fontConcept || 14) * 0.9));
    const placedLabelRects = [];
    spec.relationships.forEach((rel, idx) => {
        const from = rel.from === spec.topic ? { label: spec.topic, box: topicBox } : nodes[rel.from];
        const to = rel.to === spec.topic ? { label: spec.topic, box: topicBox } : nodes[rel.to];
        if (!from || !to) return;

        const start = rectBorderPoint(from.box, to.box.x, to.box.y);
        const end = rectBorderPoint(to.box, from.box.x, from.box.y);

        const mx = (start.x + end.x) / 2;
        const my = (start.y + end.y) / 2;
        const dx = end.x - start.x;
        const dy = end.y - start.y;
        const dist = Math.max(1, Math.hypot(dx, dy));
        const nx = -dy / dist; // normal vector
        const ny = dx / dist;
        // Per-edge curvature hint to minimize overlaps
        const curveHint = (edgeCurvatures[rel.from] ?? 0);
        const curve = Math.min(100, Math.max(-100, curveHint)) || Math.min(80, 0.18 * dist);
        const cx = mx + nx * curve;
        const cy = my + ny * curve;

        const pathId = `cm_edge_${idx}`;
        svg.append('path')
            .attr('id', pathId)
            .attr('d', `M ${start.x},${start.y} Q ${cx},${cy} ${end.x},${end.y}`)
            .attr('fill', 'none')
            .attr('stroke', THEME.relationshipColor)
            .attr('stroke-width', THEME.relationshipStrokeWidth)
            .attr('marker-end', 'url(#arrowhead)');

        // Place a horizontal label near the curve midpoint, offset along normal, avoid overlaps
        const labelOffset = 12;
        const midPreferredX = mx + nx * labelOffset;
        const midPreferredY = my + ny * labelOffset;
        const tLen = Math.max(1, Math.hypot(dx, dy));
        const tx = dx / tLen; const ty = dy / tLen; // unit tangent
        const size = measureLabelBox(rel.label || '', fontRel);
        const pos = findNonOverlappingLabelPosition(
            midPreferredX, midPreferredY, nx, ny, tx, ty, size.width, size.height, nodeRects, placedLabelRects
        );
        drawEdgeLabel(pos.x, pos.y, rel.label, fontRel, THEME.relationshipColor);
        placedLabelRects.push({ x: pos.x, y: pos.y, width: size.width, height: size.height });
    });

    // DEBUG: Final layout summary
    console.log('=== CONCEPT MAP RENDERER FINAL SUMMARY ===');
    console.log('Layout algorithm used: radial (forced)');
    console.log('Final canvas dimensions:', { width, height });
    console.log('Nodes rendered:', Object.keys(nodes).length);
    console.log('Relationships rendered:', spec.relationships.length);
    console.log('Spacing scale applied:', spacingScale);
    console.log('=== END CONCEPT MAP RENDERER SUMMARY ===');

    addWatermark(svg, theme);
}

// Export the renderer function
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { renderConceptMap };
} else if (typeof window !== 'undefined') {
    window.renderConceptMap = renderConceptMap;
}
