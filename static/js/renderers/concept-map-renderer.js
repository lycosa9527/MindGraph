/**
 * Concept Map Renderer for MindGraph
 * 
 * This module contains the concept map rendering functions.
 * Requires: shared-utilities.js, style-manager.js
 * 
 * Performance Impact: Loads only ~95KB instead of full 213KB
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

function renderConceptMap(spec, theme = null, dimensions = null) {
    logger.debug('ConceptMapRenderer', 'Rendering concept map', { 
        nodesCount: spec?.nodes?.length || 0,
        linksCount: spec?.links?.length || 0
    });
    
    // Self-contained measurement utilities (from reference file)
    let measurementContainer = null;

    function getMeasurementContainer() {
        if (!measurementContainer) {
            const body = d3.select('body');
            if (body.empty()) {
                logger.warn('ConceptMapRenderer', 'Body element not found, creating measurement container in document');
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

    // Try to use shared utilities if available, otherwise use self-contained functions
    let useSharedUtilities = false;
    if (typeof window.MindGraphUtils !== 'undefined' && 
        typeof window.MindGraphUtils.getMeasurementContainer === 'function') {
        useSharedUtilities = true;
    }
    
    // Validate BEFORE clearing container - defensive programming
    // Use typeof check to allow empty string (for empty button functionality)
    if (!spec || typeof spec.topic !== 'string' || !Array.isArray(spec.concepts) || !Array.isArray(spec.relationships)) {
        logger.error('ConceptMapRenderer', 'Invalid spec for concept map');
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
        baseWidth = dimensions.width || dimensions.baseWidth || 1600;
        baseHeight = dimensions.height || dimensions.baseHeight || 1000;
        padding = dimensions.padding || 80;
    } else {
        // Default dimensions
        baseWidth = 1600;
        baseHeight = 1000;
        padding = 80;
    }
    
    // Starting concept map rendering with specified dimensions
    
    // Check for configurable padding from spec
    const earlyConfig = spec._config || {};
    const configPadding = earlyConfig.canvasPadding || padding;

    // Load theme from style manager - FIXED: No more hardcoded overrides
    let THEME;
    try {
        if (typeof styleManager !== 'undefined' && styleManager.getTheme) {
            THEME = styleManager.getTheme('concept_map', theme, theme);
        } else {
            logger.error('ConceptMapRenderer', 'Style manager not available');
            throw new Error('Style manager not available for concept map rendering');
        }
    } catch (e) {
        logger.error('ConceptMapRenderer', 'Error getting theme from style manager', e);
        throw new Error('Failed to load theme from style manager');
    }
    
    // Apply container background (matching reference file)
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
    
    const svg = d3.select('#d3-container').append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `0 0 ${width} ${height}`)
        .attr('preserveAspectRatio', 'xMidYMid meet');

    // Add background rectangle to cover entire canvas (from reference)
    svg.append('rect')
        .attr('width', width)
        .attr('height', height)
        .attr('fill', THEME.background || '#f5f5f5')
        .attr('stroke', 'none')
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

    // Check for preserved dimensions from empty button operation
    const nodeDimensions = spec._node_dimensions || {};

    // Helpers for text wrapping and box measurement
    function measureLineWidth(text, fontSize) {
        const container = getMeasurementContainer();
        const t = container.append('svg').append('text').attr('font-size', fontSize).text(text);
        const w = t.node().getBBox().width;
        t.remove();
        return w;
    }

    function wrapIntoLines(text, fontSize, maxWidth) {
        const textStr = String(text);
        const lines = [];
        
        // First, split by explicit newlines (user-inserted line breaks)
        const explicitLines = textStr.split(/\n/);
        
        // For each explicit line, wrap it if needed
        explicitLines.forEach((line, lineIndex) => {
            // Trim each line but preserve empty lines
            const trimmedLine = line.trim();
            if (trimmedLine === '' && lineIndex < explicitLines.length - 1) {
                // Preserve empty lines (but not trailing ones)
                lines.push('');
                return;
            }
            
            if (trimmedLine === '') {
                return; // Skip trailing empty lines
            }
            
            // Wrap this line if it exceeds maxWidth
            const words = trimmedLine.split(/\s+/);
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
        });
        
        return lines.length > 0 ? lines : [''];
    }

    function drawBox(x, y, text, isTopic = false, nodeKey = null) {
        const fontSize = isTopic ? THEME.fontTopic : THEME.fontConcept;
        const maxTextWidth = isTopic ? 350 : 300;
        const lines = wrapIntoLines(text, fontSize, maxTextWidth);
        const lineHeight = Math.round(fontSize * 1.2);
        const paddingX = 16;
        const paddingY = 10;
        
        // Check for preserved dimensions (from empty button)
        const preservedKey = nodeKey || (isTopic ? 'topic' : `concept-${text}`);
        const preserved = nodeDimensions[preservedKey];
        const textStr = String(text || '').trim();
        
        let boxW, boxH;
        if (preserved && preserved.w && preserved.h && textStr === '') {
            // Use preserved dimensions for empty node
            boxW = preserved.w;
            boxH = preserved.h;
            logger.debug('ConceptMapRenderer', 'Using preserved dimensions', { nodeKey: preservedKey, boxW, boxH });
        } else {
            // Calculate from text
            const textWidth = Math.max(...lines.map(l => measureLineWidth(l, fontSize)), 20);
            boxW = Math.ceil(textWidth + paddingX * 2);
            boxH = Math.ceil(lines.length * lineHeight + paddingY * 2);
        }

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

        // WORKAROUND: Use multiple text elements instead of tspan
        const textStartY = y - (lines.length - 1) * lineHeight / 2;
        lines.forEach((ln, i) => {
            group.append('text')
                .attr('x', x)
                .attr('y', textStartY + i * lineHeight)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', isTopic ? THEME.topicText : THEME.conceptText)
                .attr('font-size', fontSize)
                .attr('font-weight', isTopic ? '600' : '400')
                .attr('data-line-index', i)
                .text(ln);
        });

        return { x, y, width: boxW, height: boxH, group };
    }

    // Configuration constants for coordinate transformation
    const LAYOUT_CONFIG = {
        coordinateRange: 10.0,           // Maximum coordinate range for normalization
        coordinateScaleDivisor: 12.0,    // Divisor for coordinate scaling
        minSpacingScale: 0.8,           // Minimum spacing scale
        maxSpacingScale: 2.0,           // Maximum spacing scale
        defaultSpacingScale: 1.0,       // Default spacing scale
        minValidCoordinate: -1000,       // Minimum valid coordinate value
        maxValidCoordinate: 1000         // Maximum valid coordinate value
    };

    // Coordinate transformation functions from reference file
    function isNormalized(p) {
        if (typeof p.x !== 'number' || typeof p.y !== 'number') return false;
        return p.x <= LAYOUT_CONFIG.coordinateRange && p.x >= -LAYOUT_CONFIG.coordinateRange && 
               p.y <= LAYOUT_CONFIG.coordinateRange && p.y >= -LAYOUT_CONFIG.coordinateRange;
    }

    function transformToCanvas(p) {
        if (!p || typeof p.x !== 'number' || typeof p.y !== 'number') {
            logger.warn('ConceptMapRenderer', 'Invalid position data', p);
            return { x: width / 2, y: height / 2 };
        }
        
        if (isNormalized(p)) {
            const scaleX = (width - 2 * configPadding) / LAYOUT_CONFIG.coordinateScaleDivisor;
            const scaleY = (height - 2 * configPadding) / LAYOUT_CONFIG.coordinateScaleDivisor;
            const px = (width / 2) + (p.x * scaleX);
            const py = (height / 2) + (p.y * scaleY);
            
            // Validate transformed coordinates
            if (px < LAYOUT_CONFIG.minValidCoordinate || px > LAYOUT_CONFIG.maxValidCoordinate ||
                py < LAYOUT_CONFIG.minValidCoordinate || py > LAYOUT_CONFIG.maxValidCoordinate) {
                logger.warn('ConceptMapRenderer', 'Transformed coordinates out of bounds', { input: p, output: { x: px, y: py } });
                return { x: width / 2, y: height / 2 };
            }
            
            return { x: px, y: py };
        }
        
        // If not normalized, validate and return as-is
        if (p.x < LAYOUT_CONFIG.minValidCoordinate || p.x > LAYOUT_CONFIG.maxValidCoordinate ||
            p.y < LAYOUT_CONFIG.minValidCoordinate || p.y > LAYOUT_CONFIG.maxValidCoordinate) {
            logger.warn('ConceptMapRenderer', 'Raw coordinates out of bounds', p);
            return { x: width / 2, y: height / 2 };
        }
        
        return p;
    }

    // Check if we have pre-computed positions from the backend
    if (spec._layout && spec._layout.positions) {
        // Using backend-calculated positions
        const positions = spec._layout.positions;
        const params = spec._layout.params || {};
        const extents = spec._layout.extents;
        
        logger.debug('ConceptMapRenderer', 'Position data debug', {
            positionsKeys: Object.keys(positions),
            topicKey: spec.topic,
            conceptKeys: spec.concepts,
            hasTopicPosition: !!positions[spec.topic],
            samplePosition: positions[Object.keys(positions)[0]]
        });
        
        // Apply spacing scale from agent or config
        const config = spec._config || {};
        let spacingScale = typeof params.nodeSpacing === 'number' ? 
            Math.max(LAYOUT_CONFIG.minSpacingScale, Math.min(LAYOUT_CONFIG.maxSpacingScale, params.nodeSpacing)) : 
            typeof config.nodeSpacing === 'number' ? 
                Math.max(LAYOUT_CONFIG.minSpacingScale, Math.min(LAYOUT_CONFIG.maxSpacingScale, config.nodeSpacing)) : 
                LAYOUT_CONFIG.defaultSpacingScale;
        
        
        const boxes = {};
        
        // Draw topic first - at canvas center
        boxes.topic = drawBox(width / 2, height / 2, spec.topic, true);
        
        // Draw concepts - positions are keyed by concept text with coordinate transformation
        spec.concepts.forEach((concept, i) => {
            const pos = positions[concept];
            if (pos) {
                // Apply spacing scale to normalized coordinates
                const scaled = { x: pos.x * spacingScale, y: pos.y * spacingScale };
                const canvasPos = transformToCanvas(scaled);
                
                logger.debug('ConceptMapRenderer', 'Drawing concept', {
                    concept,
                    original: pos,
                    scaled: scaled,
                    canvas: canvasPos,
                    spacingScale: spacingScale
                });
                
                boxes[concept] = drawBox(canvasPos.x, canvasPos.y, concept, false);
            } else {
                logger.warn('ConceptMapRenderer', 'No position found for concept', concept);
            }
        });
        
        // Add missing functions from old renderer for curved edges and advanced labels
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

        // Prepare node rectangles for label overlap checks
        const nodeRects = [
            { x: boxes.topic.x, y: boxes.topic.y, width: boxes.topic.width, height: boxes.topic.height },
            ...Object.values(boxes).filter(b => b !== boxes.topic).map(b => ({ x: b.x, y: b.y, width: b.width, height: b.height }))
        ];

        // Draw relationships as curved, directed edges with labels (matching old renderer exactly)
        const fontRel = THEME.fontRelationship || Math.max(12, Math.round((THEME.fontConcept || 14) * 0.9));
        const placedLabelRects = [];
        spec.relationships.forEach((rel, idx) => {
            const from = rel.from === spec.topic ? { label: spec.topic, box: boxes.topic } : { label: rel.from, box: boxes[rel.from] };
            const to = rel.to === spec.topic ? { label: spec.topic, box: boxes.topic } : { label: rel.to, box: boxes[rel.to] };
            if (!from || !to || !from.box || !to.box) return;

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
            const curveHint = 0; // No edgeCurvatures in this version
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
            if (rel.label) {
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
            }
        });
    } else {
        // If no positions from agent, generate radial layout (from reference file)
        logger.debug('ConceptMapRenderer', 'No positions from agent, generating radial layout fallback');
        
        // Generate fallback positions using radial layout
        const N = Math.max(1, spec.concepts.length);
        const keys = spec.concepts.slice(0, Math.min(6, N)); // Max 6 primary concepts
        const sectorSpan = (2 * Math.PI) / Math.max(1, keys.length);
        
        const fallbackPositions = { [spec.topic]: { x: 0, y: 0 } };
        
        // Position primary concepts in optimal sectors  
        keys.forEach((k, i) => {
            const ang = -Math.PI / 2 + i * sectorSpan;
            fallbackPositions[k] = { 
                x: 0.35 * Math.cos(ang), 
                y: 0.35 * Math.sin(ang) 
            };
        });
        
        // Position remaining concepts in secondary sectors
        let idx = 0;
        spec.concepts.forEach(c => {
            if (keys.includes(c)) return;
            
            const i = idx % Math.max(1, keys.length);
            const centerAng = -Math.PI / 2 + i * sectorSpan;
            const half = (sectorSpan * 0.8) / 2;
            const t = ((idx / keys.length) % 1);
            const ang = centerAng - half + t * (2 * half);
            
            const radiusTier = Math.floor(idx / keys.length);
            const radiusStep = (0.9 - 0.55) / Math.max(1, radiusTier + 1);
            const rad = 0.55 + (radiusTier * radiusStep);
            
            fallbackPositions[c] = { x: rad * Math.cos(ang), y: rad * Math.sin(ang) };
            idx++;
        });
        
        // Now render using the generated positions
        const boxes = {};
        
        // Draw topic at canvas center
        boxes.topic = drawBox(width / 2, height / 2, spec.topic, true);
        
        // Draw concepts with coordinate transformation
        spec.concepts.forEach((concept) => {
            const pos = fallbackPositions[concept];
            if (pos) {
                const scaleX = (width - 2 * configPadding) / 12.0;
                const scaleY = (height - 2 * configPadding) / 12.0;
                const canvasPos = {
                    x: (width / 2) + (pos.x * scaleX),
                    y: (height / 2) + (pos.y * scaleY)
                };
                
                boxes[concept] = drawBox(canvasPos.x, canvasPos.y, concept, false);
            }
        });
        
        // Draw relationships using same curved style as main renderer
        const nodeRects = [
            { x: boxes.topic.x, y: boxes.topic.y, width: boxes.topic.width, height: boxes.topic.height },
            ...Object.values(boxes).filter(b => b !== boxes.topic).map(b => ({ x: b.x, y: b.y, width: b.width, height: b.height }))
        ];
        
        const fontRel = THEME.fontRelationship || Math.max(12, Math.round((THEME.fontConcept || 14) * 0.9));
        const placedLabelRects = [];
        
        spec.relationships.forEach((rel, idx) => {
            const from = rel.from === spec.topic ? { label: spec.topic, box: boxes.topic } : { label: rel.from, box: boxes[rel.from] };
            const to = rel.to === spec.topic ? { label: spec.topic, box: boxes.topic } : { label: rel.to, box: boxes[rel.to] };
            if (!from || !to || !from.box || !to.box) return;

            const start = rectBorderPoint(from.box, to.box.x, to.box.y);
            const end = rectBorderPoint(to.box, from.box.x, from.box.y);

            const mx = (start.x + end.x) / 2;
            const my = (start.y + end.y) / 2;
            const dx = end.x - start.x;
            const dy = end.y - start.y;
            const dist = Math.max(1, Math.hypot(dx, dy));
            const nx = -dy / dist; // normal vector
            const ny = dx / dist;
            const curve = Math.min(80, 0.18 * dist);
            const cx = mx + nx * curve;
            const cy = my + ny * curve;

            const pathId = `cm_edge_fallback_${idx}`;
            svg.append('path')
                .attr('id', pathId)
                .attr('d', `M ${start.x},${start.y} Q ${cx},${cy} ${end.x},${end.y}`)
                .attr('fill', 'none')
                        .attr('stroke', THEME.relationshipColor)
                        .attr('stroke-width', THEME.relationshipStrokeWidth)
                        .attr('marker-end', 'url(#arrowhead)');
                    
            // Advanced label positioning for fallback too
            if (rel.label) {
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
            }
        });
    }
    
    // Apply learning sheet text knockout if needed
    if (spec.is_learning_sheet && spec.hidden_node_percentage > 0) {
        knockoutTextForLearningSheet(svg, spec.hidden_node_percentage);
    }
}

function renderConceptMapWithForceLayout(spec, svg, THEME, width, height) {
    // This function is kept for compatibility but not actively used
    // The main renderer now uses the radial layout fallback from the reference file
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
} else if (typeof module !== 'undefined' && module.exports) {
    // Node.js environment
    module.exports = {
        renderConceptMap,
        renderConceptMapWithForceLayout
    };
} else {
    logger.error('ConceptMapRenderer', 'Module failed to load in any environment');
}
