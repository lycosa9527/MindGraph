/**
 * Flow Renderer for MindGraph
 * 
 * This module contains the flowchart, flow map, multi-flow map, and bridge map rendering functions.
 * Requires: shared-utilities.js, style-manager.js
 * 
 * Performance Impact: Loads only ~45KB instead of full 213KB
 */

// Check if shared utilities are available
if (typeof window.MindGraphUtils === 'undefined') {
    logger.error('FlowRenderer', 'MindGraphUtils not found! Please load shared-utilities.js first');
}

// Helper: round to 1 decimal to reduce floating-point precision noise in canvas calcs
function __round1(n) { return Math.round(n * 10) / 10; }

function renderFlowchart(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');

    // Validate spec
    if (!spec || !spec.title || !Array.isArray(spec.steps)) {
        logger.error('FlowRenderer', 'Invalid spec for flowchart');
        return;
    }

    // Use adaptive dimensions if provided, otherwise use fallback dimensions
    let padding;
    
    if (spec._recommended_dimensions) {
        // Adaptive dimensions from template (calculated based on window size)
        padding = spec._recommended_dimensions.padding;
    } else if (dimensions) {
        // Provided dimensions (fallback)
        padding = dimensions.padding || 40;
    } else {
        // Default padding
        padding = 40;
    }

    // Get theme from style manager - FIXED: No more hardcoded overrides
    let THEME;
    try {
        if (typeof styleManager !== 'undefined' && styleManager.getTheme) {
            THEME = styleManager.getTheme('flowchart', theme, theme);
        } else {
            logger.error('FlowRenderer', 'Style manager not available');
            throw new Error('Style manager not available for flow map rendering');
        }
    } catch (error) {
        logger.error('FlowRenderer', 'Error getting theme from style manager', error);
        throw new Error('Failed to load theme from style manager');
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

    // Apply dimensions (rounded)
    const rw = __round1(requiredWidth);
    const rh = __round1(requiredHeight);
    
    // DON'T set explicit width/height on container - let CSS handle it (100% fill)
    // This allows the canvas to fill the viewport and auto-fit to work properly

    // Create visible SVG with viewBox for proper scaling
    const svg = d3.select('#d3-container').append('svg')
        .attr('viewBox', `0 0 ${rw} ${rh}`)
        .attr('preserveAspectRatio', 'xMidYMid meet');

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

    // RENDERING ORDER: Define arrow marker FIRST, draw arrows, THEN draw nodes on top
    // Arrow marker definition
    svg.append('defs').append('marker')
        .attr('id', 'arrowhead')
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 8)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('fill', '#666');

    // Vertical layout - calculate positions first
    const centerX = rw / 2;
    let yCursor = titleY + 40;
    
    // Calculate all node positions
    const nodePositions = nodes.map((n, i) => {
        const x = centerX;
        const y = yCursor + n.h / 2;
        const pos = { ...n, x, y, index: i };
        yCursor += n.h + stepSpacing;
        return pos;
    });

    // Draw arrows FIRST (underneath nodes)
    nodePositions.forEach((n, i) => {
        if (i < nodePositions.length - 1) {
            const nextTopY = n.y + n.h / 2 + 6;
            const nextBottomY = nextTopY + stepSpacing - 12;
            svg.append('line')
                .attr('x1', n.x)
                .attr('y1', nextTopY)
                .attr('x2', n.x)
                .attr('y2', nextBottomY)
                .attr('stroke', '#666')
                .attr('stroke-width', 2)
                .attr('marker-end', 'url(#arrowhead)');
        }
    });

    // Draw nodes and text ON TOP of arrows
    nodePositions.forEach((n) => {
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
                `${n.x},${n.y - n.h/2}`,
                `${n.x + n.w/2},${n.y}`,
                `${n.x},${n.y + n.h/2}`,
                `${n.x - n.w/2},${n.y}`
            ].join(' ');
            svg.append('polygon')
                .attr('points', points)
                .attr('fill', fill)
                .attr('stroke', stroke)
                .attr('stroke-width', strokeWidth);
        } else {
            svg.append('rect')
                .attr('x', n.x - n.w/2)
                .attr('y', n.y - n.h/2)
                .attr('width', n.w)
                .attr('height', n.h)
                .attr('rx', nodeRadius)
                .attr('fill', fill)
                .attr('stroke', stroke)
                .attr('stroke-width', strokeWidth);
        }

        svg.append('text')
            .attr('x', n.x)
            .attr('y', n.y)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', textColor || '#fff')
            .attr('font-size', THEME.fontNode)
            .text(n.text);
    });

    // Watermark removed from canvas display - will be added during PNG export only
}

function renderFlowMap(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');

    // Validate spec
    if (!spec || !spec.title || !Array.isArray(spec.steps)) {
        logger.error('FlowRenderer', 'Invalid spec for flow map');
        return;
    }

    // Use adaptive dimensions if provided, otherwise use fallback dimensions
    let padding;
    
    if (spec._recommended_dimensions) {
        // Adaptive dimensions from template (calculated based on window size)
        padding = spec._recommended_dimensions.padding;
    } else if (dimensions) {
        // Provided dimensions (fallback)
        padding = dimensions.padding || 40;
    } else {
        // Default padding
        padding = 40;
    }

    const THEME = {
        titleFill: '#1976d2',
        titleText: '#333',  // Changed from white to dark gray/black for better readability
        titleStroke: '#0d47a1',
        titleStrokeWidth: 3,
        stepFill: '#1976d2',      // Deep blue for step nodes (matching bubble map)
        stepText: '#ffffff',      // White text for step nodes
        stepStroke: '#0d47a1',    // Darker blue border for step nodes
        stepStrokeWidth: 2,
        substepFill: '#e3f2fd',   // Light blue for substep nodes (matching bubble map)
        substepText: '#333333',   // Dark text for substep nodes
        substepStroke: '#1976d2', // Blue border for substep nodes
        fontTitle: 20,            // Match bubble map's fontTopic size
        fontStep: 14,             // Match bubble map's fontAttribute size
        fontFamily: 'Inter, Segoe UI, sans-serif', // Match bubble map font family
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
    const subSpacing = 30; // Increased further to prevent overlap
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
    
    // Calculate adaptive spacing based on substep heights (simplified)
    let totalVerticalSpacing = 0;
    if (stepSizes.length > 1) {
        for (let i = 0; i < stepSizes.length - 1; i++) {
            const currentStepSubHeight = subGroupHeights[i] || 0;
            const nextStepSubHeight = subGroupHeights[i + 1] || 0;
            
            // Use more efficient spacing calculation
            const maxSubHeight = Math.max(currentStepSubHeight, nextStepSubHeight);
            const minBaseSpacing = 45; // Reduced from 60
            const adaptiveSpacing = maxSubHeight > 0 ? Math.max(minBaseSpacing, maxSubHeight * 0.4 + 20) : minBaseSpacing;
            
            totalVerticalSpacing += adaptiveSpacing;
        }
    }

    // Calculate initial width estimate (will be refined after substep positioning)
    const rightSideWidth = maxSubGroupWidth > 0 ? (subOffsetX + maxSubGroupWidth) : 0;
    const extraPadding = 20; // Additional safety margin for text rendering
    const initialWidth = Math.max(titleSize.w, maxStepWidth + rightSideWidth) + padding * 2 + extraPadding;
    
    // Use agent recommendations as minimum for initial sizing
    let baseWidth, baseHeight;
    if (dimensions && dimensions.baseWidth && dimensions.baseHeight) {
        baseWidth = Math.max(dimensions.baseWidth, initialWidth);
        baseHeight = dimensions.baseHeight; // Will be updated after substep positioning
    } else {
        baseWidth = initialWidth;
        baseHeight = 600; // Initial estimate, will be updated
    }

    // Clean up temp svg (measurement SVG)
    tempSvg.remove();

    const centerX = baseWidth / 2;
    const startY = padding + titleSize.h + THEME.vPadTitle + 10; // Further reduced from 20 to 10

    // DON'T set explicit width/height on container - let CSS handle it (100% fill)
    // This allows the canvas to fill the viewport and auto-fit to work properly

    // Create actual SVG with viewBox for proper scaling
    const svg = d3.select('#d3-container').append('svg')
        .attr('viewBox', `0 0 ${baseWidth} ${baseHeight}`)
        .attr('preserveAspectRatio', 'xMidYMid meet');

    // Draw title at the top - centered to the canvas width, not the step nodes
    const titleY = padding + titleSize.h; // baseline roughly below top padding
    svg.append('text')
        .attr('x', baseWidth / 2)  // Center to canvas width
        .attr('y', titleY)
        .attr('text-anchor', 'middle')
        .attr('fill', THEME.titleText)
        .attr('font-size', THEME.fontTitle)
        .attr('font-family', THEME.fontFamily)  // Add font family to match bubble map
        .attr('font-weight', 'bold')
        .attr('data-node-id', 'flow-title')
        .attr('data-node-type', 'title')
        .attr('cursor', 'pointer')
        .text(spec.title);

    // NEW APPROACH: Calculate all substep positions first, then position steps accordingly
    
    // Step 1: Calculate all substep node positions with perfect spacing
    const allSubstepPositions = [];
    let currentSubY = startY + 15; // Further reduced from 30 to 15
    
    for (let stepIdx = 0; stepIdx < stepSizes.length; stepIdx++) {
        const nodes = subNodesPerStep[stepIdx];
        const stepPositions = [];
        
        if (nodes.length > 0) {
            // Position each substep with proper spacing
            for (let nodeIdx = 0; nodeIdx < nodes.length; nodeIdx++) {
                const node = nodes[nodeIdx];
                stepPositions.push({
                    x: centerX + stepSizes[stepIdx].w / 2 + subOffsetX,
                    y: currentSubY,
                    w: node.w,
                    h: node.h,
                    text: node.text
                });
                currentSubY += node.h + subSpacing; // Perfect spacing, no overlap
            }
            // Add gap between substep groups (reduced)
            currentSubY += 10; // Reduced from 20 to 10
        }
        allSubstepPositions.push(stepPositions);
    }
    
    // Step 2: Position main steps to align with their substep groups
    const stepCenters = [];
    for (let stepIdx = 0; stepIdx < stepSizes.length; stepIdx++) {
        const substepGroup = allSubstepPositions[stepIdx];
        let stepYCenter;
        
        if (substepGroup.length > 0) {
            // Center step on its substep group
            const firstSubstepY = substepGroup[0].y;
            const lastSubstepY = substepGroup[substepGroup.length - 1].y + substepGroup[substepGroup.length - 1].h;
            stepYCenter = (firstSubstepY + lastSubstepY) / 2;
        } else {
            // No substeps - use sequential positioning with minimal spacing
            if (stepIdx === 0) {
                stepYCenter = startY + 15; // Further reduced from 30 to 15
            } else {
                // Position below previous step with minimum spacing
                const prevStepBottom = stepCenters[stepIdx - 1] + stepSizes[stepIdx - 1].h / 2;
                stepYCenter = prevStepBottom + 40 + stepSizes[stepIdx].h / 2; // Reduced from 60 to 40
            }
        }
        
        stepCenters.push(stepYCenter);
    }
    
    // RENDERING ORDER: Draw all connectors FIRST, then nodes on top
    // Step 3a: Draw arrows between main steps (underneath)
    stepSizes.forEach((s, index) => {
        const stepXCenter = centerX;
        const stepYCenter = stepCenters[index];

        // Arrow to next step (if there is one)
        if (index < stepSizes.length - 1) {
            const nextStepYCenter = stepCenters[index + 1];
            const currentBottom = stepYCenter + s.h / 2 + 6;
            const nextTop = nextStepYCenter - stepSizes[index + 1].h / 2 - 6;
            
            if (nextTop > currentBottom) {
                svg.append('line')
                    .attr('x1', stepXCenter)
                    .attr('y1', currentBottom)
                    .attr('x2', stepXCenter)
                    .attr('y2', nextTop)
                    .attr('stroke', '#666')
                    .attr('stroke-width', 2);
                svg.append('polygon')
                    .attr('points', `${stepXCenter},${nextTop} ${stepXCenter - 5},${nextTop - 10} ${stepXCenter + 5},${nextTop - 10}`)
                    .attr('fill', '#666');
            }
        }
    });

    // Step 3b: Draw L-shaped connectors from steps to substeps (still underneath)
    allSubstepPositions.forEach((stepPositions, stepIdx) => {
        const stepYCenter = stepCenters[stepIdx];
        const stepRightX = centerX + stepSizes[stepIdx].w / 2;
        
        stepPositions.forEach((substep, nodeIdx) => {
            // Draw L-shaped connector from step to substep
            const substepCenterY = substep.y + substep.h / 2;
            const midX = stepRightX + Math.max(8, subOffsetX / 2);
            
            // Horizontal line from step
            svg.append('line')
                .attr('x1', stepRightX)
                .attr('y1', stepYCenter)
                .attr('x2', midX)
                .attr('y2', stepYCenter)
                .attr('stroke', '#888')
                .attr('stroke-width', 1.5);
            
            // Vertical line to substep level
            svg.append('line')
                .attr('x1', midX)
                .attr('y1', stepYCenter)
                .attr('x2', midX)
                .attr('y2', substepCenterY)
                .attr('stroke', '#888')
                .attr('stroke-width', 1.5);
            
            // Horizontal line to substep
            svg.append('line')
                .attr('x1', midX)
                .attr('y1', substepCenterY)
                .attr('x2', substep.x)
                .attr('y2', substepCenterY)
                .attr('stroke', '#888')
                .attr('stroke-width', 1.5);
        });
    });

    // Step 3c: NOW draw main step nodes ON TOP of connectors
    stepSizes.forEach((s, index) => {
        const stepXCenter = centerX;
        const stepYCenter = stepCenters[index];

        // Rect
        svg.append('rect')
            .attr('x', stepXCenter - s.w / 2)
            .attr('y', stepYCenter - s.h / 2)
            .attr('width', s.w)
            .attr('height', s.h)
            .attr('rx', THEME.rectRadius)
            .attr('fill', THEME.stepFill)        // Deep blue fill
            .attr('stroke', THEME.stepStroke)    // Darker blue border
            .attr('stroke-width', THEME.stepStrokeWidth)
            .attr('data-node-id', `flow-step-${index}`)
            .attr('data-node-type', 'step')
            .attr('data-step-index', index)
            .attr('cursor', 'pointer');

        // Text
        svg.append('text')
            .attr('x', stepXCenter)
            .attr('y', stepYCenter)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.stepText)        // White text
            .attr('font-size', THEME.fontStep)
            .attr('font-family', THEME.fontFamily)  // Add font family to match bubble map
            .attr('data-node-id', `flow-step-${index}`)
            .attr('data-node-type', 'step')
            .attr('data-step-index', index)
            .attr('cursor', 'pointer')
            .text(s.text);
    });

    // Calculate accurate canvas dimensions based on actual content positions
    let contentBottom = 0;
    let contentRight = 0;
    
    // Account for stroke width - half extends beyond the rect dimensions
    const stepStrokeOffset = Math.ceil(THEME.stepStrokeWidth / 2);
    
    // Find the bottom of main steps
    if (stepCenters.length > 0) {
        for (let i = 0; i < stepCenters.length; i++) {
            const stepBottom = stepCenters[i] + stepSizes[i].h / 2 + stepStrokeOffset;
            const stepRight = centerX + stepSizes[i].w / 2 + stepStrokeOffset;
            contentBottom = Math.max(contentBottom, stepBottom);
            contentRight = Math.max(contentRight, stepRight);
        }
    }
    
    // Find the bottom and right edge of substeps (which now control the layout)
    // Account for stroke width - half extends beyond the rect dimensions
    const substepStrokeWidth = Math.max(1, THEME.stepStrokeWidth - 1);
    const strokeOffset = Math.ceil(substepStrokeWidth / 2);
    
    for (let stepIdx = 0; stepIdx < allSubstepPositions.length; stepIdx++) {
        const stepPositions = allSubstepPositions[stepIdx];
        for (let nodeIdx = 0; nodeIdx < stepPositions.length; nodeIdx++) {
            const substep = stepPositions[nodeIdx];
            const substepBottom = substep.y + substep.h + strokeOffset; // Add stroke offset
            const substepRight = substep.x + substep.w + strokeOffset;   // Add stroke offset
            contentBottom = Math.max(contentBottom, substepBottom);
            contentRight = Math.max(contentRight, substepRight);
        }
    }
    
    // Calculate final dimensions with padding
    const calculatedHeight = contentBottom + padding;
    const calculatedWidth = contentRight + padding;
    const ch = __round1(calculatedHeight);
    const cw = __round1(calculatedWidth);
    
    // Step 4: Draw substeps using pre-calculated positions (no overlap possible!)
    allSubstepPositions.forEach((stepPositions, stepIdx) => {
        const stepYCenter = stepCenters[stepIdx];
        const stepRightX = centerX + stepSizes[stepIdx].w / 2;
        
        stepPositions.forEach((substep, nodeIdx) => {
            // Draw substep rectangle
            svg.append('rect')
                .attr('x', substep.x)
                .attr('y', substep.y)
                .attr('width', substep.w)
                .attr('height', substep.h)
                .attr('rx', Math.max(4, THEME.rectRadius - 2))
                .attr('fill', THEME.substepFill)        // Light blue fill
                .attr('stroke', THEME.substepStroke)    // Blue border
                .attr('stroke-width', Math.max(1, THEME.stepStrokeWidth - 1))
                .attr('data-node-id', `flow-substep-${stepIdx}-${nodeIdx}`)
                .attr('data-node-type', 'substep')
                .attr('data-step-index', stepIdx)
                .attr('data-substep-index', nodeIdx)
                .attr('cursor', 'pointer');
            
            // Draw substep text
            svg.append('text')
                .attr('x', substep.x + substep.w / 2)
                .attr('y', substep.y + substep.h / 2)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', THEME.substepText)        // Dark text for readability
                .attr('font-size', Math.max(12, THEME.fontStep - 1))
                .attr('font-family', THEME.fontFamily)  // Add font family to match bubble map
                .attr('data-node-id', `flow-substep-${stepIdx}-${nodeIdx}`)
                .attr('data-node-type', 'substep')
                .attr('data-step-index', stepIdx)
                .attr('data-substep-index', nodeIdx)
                .attr('cursor', 'pointer')
                .text(substep.text);
            
            // L-shaped connectors already drawn earlier (Step 3b) for proper z-order
        });
    });
    
    // Update SVG dimensions to match calculated content
    if (cw > baseWidth || ch > baseHeight) {
        svg.attr('width', cw)
           .attr('viewBox', `0 0 ${cw} ${ch}`)
           .attr('preserveAspectRatio', 'xMidYMid meet');
        
        // DON'T set explicit width/height on container - let CSS handle it (100% fill)
    }
    
    // Watermark removed from canvas display - will be added during PNG export only
    // Apply learning sheet text knockout if needed
    if (spec.is_learning_sheet && spec.hidden_node_percentage > 0) {
        knockoutTextForLearningSheet(svg, spec.hidden_node_percentage);
    }
}

function renderBridgeMap(spec, theme = null, dimensions = null, containerId = 'd3-container') {

    logger.debug('FlowRenderer', 'Rendering bridge map', {
        analogiesCount: spec?.analogies?.length || 0,
        dimension: spec?.dimension
    });
    
    d3.select(`#${containerId}`).html('');
    
    // Validate spec
    if (!spec || !Array.isArray(spec.analogies) || spec.analogies.length === 0) {
        logger.error('FlowRenderer', 'Invalid spec for bridge map');
        return;
    }
    
    // Validate that analogies have the correct structure
    if (!spec.analogies.every(analogy => analogy.left && analogy.right)) {
        logger.error('FlowRenderer', 'Invalid analogy structure');
        return;
    }
    
    // Calculate optimal dimensions based on content (exactly as in old renderer)
    const numAnalogies = spec.analogies.length;
    const minWidthPerAnalogy = 120; // Minimum width needed per analogy pair
    const leftPadding = 110; // Extra left padding for dimension label (text extends leftward with text-anchor: end)
    const rightPadding = 40; // Right padding
    const topBottomPadding = 40; // Top and bottom padding
    
    // Calculate optimal width: enough space for all analogies + separators + padding
    const contentWidth = (numAnalogies * minWidthPerAnalogy) + ((numAnalogies - 1) * 60); // 60px for separator spacing
    const optimalWidth = Math.max(contentWidth + leftPadding + rightPadding, dimensions?.baseWidth || 600);
    
    // Calculate optimal height: enough space for text + vertical lines + padding + alternative dimensions
    const textHeight = 40; // Height for text elements
    const lineHeight = 50; // Height for vertical connection lines
    const altDimensionsHeight = 80; // Always reserve space for alternative dimensions section (even if empty)
    const optimalHeight = Math.max(textHeight + lineHeight + (2 * topBottomPadding) + altDimensionsHeight, dimensions?.baseHeight || 200);
    
    // Use calculated dimensions or fall back to provided dimensions
    const width = optimalWidth;
    const height = optimalHeight;
    
    // Create SVG
    const svg = d3.select(`#${containerId}`)
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `0 0 ${width} ${height}`)
        .style('background-color', '#f8f8f8'); // Light background to see boundaries
    
    // Apply theme (exactly as in old renderer)
    const THEME = {
        backgroundColor: '#ffffff',
        analogyTextColor: '#2c3e50',
        analogyFontSize: 14,
        bridgeColor: '#666666', // Changed to grey for lines and triangles
        bridgeWidth: 3,
        stroke: '#2c3e50',
        strokeWidth: 1,
        fontFamily: 'Inter, Segoe UI, sans-serif' // Changed back to Inter
    };
    
    // 1. Create horizontal main line (ensure it's visible) - EXACTLY as in old renderer
    const mainLine = svg.append("line")
        .attr("x1", leftPadding)
        .attr("y1", height/2)
        .attr("x2", width - rightPadding)
        .attr("y2", height/2)
        .attr("stroke", "#666666") // Changed to grey
        .attr("stroke-width", 4); // Use attr instead of style
    
    // 2. Calculate separator positions with better spacing - EXACTLY as in old renderer
    const availableWidth = width - leftPadding - rightPadding;
    const sectionWidth = availableWidth / (spec.analogies.length + 1);
    
    // 3. Draw analogy pairs first - EXACTLY as in old renderer
    spec.analogies.forEach((analogy, i) => {

        
        const xPos = leftPadding + (sectionWidth * (i + 1));
        const isFirstPair = i === 0; // Check if this is the first pair
        
        // 3.1 Add upstream item (left) - above the main line
        if (isFirstPair) {
            // First pair gets rectangle borders with deep blue background and white text
            const rectWidth = 100;
            const rectHeight = 30;
            
            // Draw rectangle background
            svg.append("rect")
                .attr("x", xPos - rectWidth/2)
                .attr("y", height/2 - 30 - rectHeight/2)
                .attr("width", rectWidth)
                .attr("height", rectHeight)
                .attr("rx", 4)
                .attr("fill", "#1976d2") // Deep blue from mind map
                .attr("stroke", "#0d47a1")
                .attr("stroke-width", 2)
                .attr("data-node-id", `bridge-left-${i}`)
                .attr("data-node-type", "left")
                .attr("data-pair-index", i)
                .attr("cursor", "pointer");
            
            // Draw text in white
            svg.append("text")
                .attr("x", xPos)
                .attr("y", height/2 - 30)
                .attr("text-anchor", "middle")
                .attr("dominant-baseline", "middle")
                .text(analogy.left)
                .style("font-size", THEME.analogyFontSize)
                .style("fill", "#ffffff") // White text
                .style("font-weight", "bold")
                .attr("data-text-for", `bridge-left-${i}`)
                .attr("cursor", "pointer");
        } else {
            // Regular pairs get normal text styling
            svg.append("text")
                .attr("x", xPos)
                .attr("y", height/2 - 30)
                .attr("text-anchor", "middle")
                .text(analogy.left)
                .style("font-size", THEME.analogyFontSize)
                .style("fill", THEME.analogyTextColor)
                .style("font-weight", "bold")
                .attr("data-node-id", `bridge-left-${i}`)
                .attr("data-node-type", "left")
                .attr("data-pair-index", i)
                .attr("cursor", "pointer");
        }
        
        // 3.2 Add downstream item (right) - below the main line
        if (isFirstPair) {
            // First pair gets rectangle borders with deep blue background and white text
            const rectWidth = 100;
            const rectHeight = 30;
            
            // Draw rectangle background
            svg.append("rect")
                .attr("x", xPos - rectWidth/2)
                .attr("y", height/2 + 40 - rectHeight/2)
                .attr("width", rectWidth)
                .attr("height", rectHeight)
                .attr("rx", 4)
                .attr("fill", "#1976d2") // Deep blue from mind map
                .attr("stroke", "#0d47a1")
                .attr("stroke-width", 2)
                .attr("data-node-id", `bridge-right-${i}`)
                .attr("data-node-type", "right")
                .attr("data-pair-index", i)
                .attr("cursor", "pointer");
            
            // Draw text in white
            svg.append("text")
                .attr("x", xPos)
                .attr("y", height/2 + 40)
                .attr("text-anchor", "middle")
                .attr("dominant-baseline", "middle")
                .text(analogy.right)
                .style("font-size", THEME.analogyFontSize)
                .style("fill", "#ffffff") // White text
                .style("font-weight", "bold")
                .attr("data-text-for", `bridge-right-${i}`)
                .attr("cursor", "pointer");
        } else {
            // Regular pairs get normal text styling
            svg.append("text")
                .attr("x", xPos)
                .attr("y", height/2 + 40)
                .attr("text-anchor", "middle")
                .text(analogy.right)
                .style("font-size", THEME.analogyFontSize)
                .style("fill", THEME.analogyTextColor)
                .style("font-weight", "bold")
                .attr("data-node-id", `bridge-right-${i}`)
                .attr("data-node-type", "right")
                .attr("data-pair-index", i)
                .attr("cursor", "pointer");
        }
        
        // 3.3 Add vertical connection line (made invisible) - EXACTLY as in old renderer
        svg.append("line")
            .attr("x1", xPos)
            .attr("y1", height/2 - 20) // Connect to upstream item
            .attr("x2", xPos)
            .attr("y2", height/2 + 30) // Connect to downstream item
            .attr("stroke", "transparent") // Make vertical lines invisible
            .attr("stroke-width", 3); // Use attr instead of style
    });
    
    // 3.5 Add dimension label on the left side (two lines)
    if (spec.analogies.length > 0) {
        const dimensionText = spec.dimension || '';
        
        // Detect language from dimension text or spec content
        const hasChineseContent = dimensionText ? /[\u4e00-\u9fa5]/.test(dimensionText) : 
                                  (spec.analogies[0] && /[\u4e00-\u9fa5]/.test(spec.analogies[0].left + spec.analogies[0].right));
        const isEnglish = !hasChineseContent;
        
        const labelLine1 = isEnglish ? "Analogy Pattern:" : "类比关系:";
        const labelLine2 = dimensionText || (isEnglish ? "[click to specify]" : "[点击设置]");
        
        const leftX = leftPadding - 10; // Position 10px left of the main content area
        
        // Line 1: Label
        svg.append("text")
            .attr("x", leftX)
            .attr("y", height/2 - 8)
            .attr("text-anchor", "end")
            .text(labelLine1)
            .style("font-size", "11px")
            .style("fill", THEME.dimensionLabelColor || '#1976d2')
            .style("font-weight", "bold");
        
        // Line 2: Value (clickable)
        svg.append("text")
            .attr("x", leftX)
            .attr("y", height/2 + 8)
            .attr("text-anchor", "end")
            .text(labelLine2)
            .style("font-size", "12px")
            .style("fill", THEME.dimensionLabelColor || '#1976d2')
            .style("font-style", dimensionText ? "normal" : "italic")
            .style("opacity", dimensionText ? 1 : 0.6)
            .attr("data-node-id", "dimension_label")
            .attr("data-node-type", "dimension")
            .attr("data-dimension-value", dimensionText)
            .attr("cursor", "pointer");
    }
    
    // 4. Draw "as" separators (one less than analogy pairs) - positioned to the right of analogy pairs
    // EXACTLY as in old renderer
    for (let i = 0; i < spec.analogies.length - 1; i++) {
        // Position separator between analogy pairs (to the right of current pair)
        const xPos = leftPadding + (sectionWidth * (i + 1.5)); // Position between pairs
        
        // 4.1 Add little triangle separator on the main line - pointing UPWARD
        const triangleSize = 8; // Back to normal size
        const trianglePath = `M ${xPos - triangleSize} ${height/2} L ${xPos} ${height/2 - triangleSize} L ${xPos + triangleSize} ${height/2} Z`;
        
        svg.append("path")
            .attr("d", trianglePath)
            .attr("fill", "#666666") // Changed to grey
            .attr("stroke", "#666666") // Changed to grey
            .attr("stroke-width", 2); // Use attr instead of style
        
        // 4.2 Add "as" text below the triangle - improved positioning
        svg.append("text")
            .attr("x", xPos)
            .attr("y", height/2 + 20) // Positioned below the line with comfortable spacing
            .attr("text-anchor", "middle")
            .text("as")
            .style("font-weight", "bold")
            .style("font-size", THEME.analogyFontSize + 2)
            .style("fill", "#666666"); // Changed to grey to match triangles
    }
    
    // 5. Add alternative dimensions section at the bottom (matching tree/brace map style)
    const hasAlternatives = spec.alternative_dimensions && Array.isArray(spec.alternative_dimensions) && spec.alternative_dimensions.length > 0;
    if (hasAlternatives) {
    }
    
    // Calculate the actual bottom of all analogy nodes
    // Lower nodes are positioned at height/2 + 40
    // First pair has rectangles with height 30, centered at height/2 + 40
    // So bottom of rectangle is: height/2 + 40 + (30/2) = height/2 + 55
    // Regular text extends ~7px below baseline, so bottom is: height/2 + 40 + 7 = height/2 + 47
    const rectHeight = 30;
    const lastContentBottomY = height / 2 + 40 + (rectHeight / 2); // Bottom of the lower rectangle nodes (height/2 + 55)
    const separatorY = lastContentBottomY + 15;  // Separator line 15px below the bottom edge of last content
    const alternativesY = separatorY + 20;  // Label 20px below separator
    const fontSize = 13;
    
    // Detect language from first alternative dimension or spec
    const hasChineseInSpec = spec.alternative_dimensions && spec.alternative_dimensions.length > 0 ? 
                              /[\u4e00-\u9fa5]/.test(spec.alternative_dimensions[0]) :
                              (spec.dimension ? /[\u4e00-\u9fa5]/.test(spec.dimension) : 
                              (spec.analogies && spec.analogies[0] && /[\u4e00-\u9fa5]/.test(spec.analogies[0].left + spec.analogies[0].right)));
    const isEnglishSpec = !hasChineseInSpec;
    const alternativeLabel = isEnglishSpec ? 'Other possible analogy patterns for this topic:' : '本主题的其他可能类比关系:';
    
    // Calculate center position based on content width
    const contentCenterX = width / 2;
    
    // Draw dotted separator line spanning full diagram width (matching tree/brace map)
    const separatorLeftX = leftPadding;
    const separatorRightX = width - rightPadding;
    
    svg.append('line')
        .attr('x1', separatorLeftX)
        .attr('y1', separatorY)
        .attr('x2', separatorRightX)
        .attr('y2', separatorY)
        .attr('stroke', THEME.dimensionLabelColor || '#1976d2')  // Dark blue for classroom visibility
        .attr('stroke-width', 1)
        .attr('stroke-dasharray', '4,4')  // Dotted line matching tree/brace map
        .style('opacity', 0.4);  // Match tree/brace map opacity
    
    // Add label centered on content
    svg.append('text')
        .attr('x', contentCenterX)
        .attr('y', alternativesY - 5)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('fill', THEME.dimensionLabelColor || '#1976d2')  // Dark blue for classroom visibility
        .attr('font-size', fontSize)
        .attr('font-family', 'Inter, Segoe UI, sans-serif')
        .style('opacity', 0.7)  // Match tree/brace map opacity
        .text(alternativeLabel);
    
    // Display 4-6 alternative dimensions as chips (or placeholder)
    if (hasAlternatives) {
        const altsToShow = spec.alternative_dimensions.slice(0, 6);
        const dimensionChips = altsToShow.map(d => `• ${d}`).join('  ');  // Match tree/brace map format
        svg.append('text')
            .attr('x', contentCenterX)
            .attr('y', alternativesY + 18)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.dimensionLabelColor || '#1976d2')  // Dark blue for classroom visibility
            .attr('font-size', fontSize - 1)  // 12px matching tree/brace map
            .attr('font-family', 'Inter, Segoe UI, sans-serif')
            .attr('font-weight', '600')
            .style('opacity', 0.8)  // Match tree/brace map opacity
            .text(dimensionChips);
    } else {
        // Show placeholder when no alternatives available
        const placeholderText = isEnglishSpec ? '[Alternatives will appear here]' : '[替代关系将在此显示]';
        svg.append('text')
            .attr('x', contentCenterX)
            .attr('y', alternativesY + 18)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.dimensionLabelColor || '#1976d2')
            .attr('font-size', fontSize - 1)
            .attr('font-family', 'Inter, Segoe UI, sans-serif')
            .attr('font-style', 'italic')
            .style('opacity', 0.4)
            .text(placeholderText);
    }
    
    // Watermark removed from canvas display - will be added during PNG export only
    
    
    // Apply learning sheet text knockout if needed
    if (spec.is_learning_sheet && spec.hidden_node_percentage > 0) {
        knockoutTextForLearningSheet(svg, spec.hidden_node_percentage);
    }
}

function renderMultiFlowMap(spec, theme = null, dimensions = null) {
    d3.select('#d3-container').html('');
    
    // Validate spec - use the correct format that matches the working spec
    if (!spec || !spec.event || !Array.isArray(spec.causes) || !Array.isArray(spec.effects)) {
        logger.error('FlowRenderer', 'Invalid spec for multi-flow map');
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
        baseWidth = dimensions.width || dimensions.baseWidth || 900;
        baseHeight = dimensions.height || dimensions.baseHeight || 500;
        padding = dimensions.padding || 40;
    } else {
        // Default dimensions
        baseWidth = 900;
        baseHeight = 500;
        padding = 40;
    }
    
    const THEME = {
        eventFill: '#1976d2',      // Deep blue central event (matching double bubble map topic)
        eventText: '#ffffff',      // White text for contrast
        eventStroke: '#0d47a1',    // Darker blue border
        eventStrokeWidth: 3,
        causeFill: '#e3f2fd',      // Light blue causes (matching flow map substeps)
        causeText: '#333333',      // Dark text for readability
        causeStroke: '#1976d2',    // Blue border (matching flow map substeps)
        causeStrokeWidth: 2,
        effectFill: '#e3f2fd',     // Light blue effects (matching flow map substeps)
        effectText: '#333333',     // Dark text for readability
        effectStroke: '#1976d2',   // Blue border (matching flow map substeps)
        effectStrokeWidth: 2,
        fontEvent: 18,
        fontCause: 14,
        fontEffect: 14,
        rectRadius: 8,
        hPadEvent: 12,
        vPadEvent: 8,
        hPadNode: 10,
        vPadNode: 6,
        linkColorCause: '#888888', // Grey links for better visual balance
        linkColorEffect: '#888888', // Grey links for better visual balance
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
    
    // Create temporary SVG for text measurement before finalizing canvas dimensions
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
    
    // STEP 1: Measure all content to calculate optimal canvas dimensions
    
    // Measure central event size
    const evSize = measureTextSize(spec.event, THEME.fontEvent);
    const eventW = evSize.w + THEME.hPadEvent * 2;
    const eventH = evSize.h + THEME.vPadEvent * 2;
    
    // Measure causes and effects
    const causes = (spec.causes || []).map(text => {
        const s = measureTextSize(text, THEME.fontCause);
        return { text, w: s.w + THEME.hPadNode * 2, h: s.h + THEME.vPadNode * 2 };
    });
    const effects = (spec.effects || []).map(text => {
        const s = measureTextSize(text, THEME.fontEffect);
        return { text, w: s.w + THEME.hPadNode * 2, h: s.h + THEME.vPadNode * 2 };
    });
    
    // Calculate required dimensions based on content
    const vSpacing = 20;
    const totalCauseH = causes.reduce((sum, n) => sum + n.h, 0) + Math.max(0, causes.length - 1) * vSpacing;
    const totalEffectH = effects.reduce((sum, n) => sum + n.h, 0) + Math.max(0, effects.length - 1) * vSpacing;
    
    // Calculate optimal width based on side node sizes and minimum gaps
    const maxCauseW = Math.max(...causes.map(c => c.w), 0);
    const maxEffectW = Math.max(...effects.map(e => e.w), 0);
    const minSideGap = 120; // Gap between event and side nodes
    const sideMargin = 40; // Margin for side nodes from canvas edge
    
    const requiredWidth = maxCauseW + sideMargin + minSideGap + eventW + minSideGap + maxEffectW + sideMargin;
    const requiredHeight = Math.max(totalCauseH, totalEffectH, eventH) + 2 * padding + 80;
    
    // Use calculated dimensions or agent recommendations, whichever is larger
    const finalWidth = Math.max(baseWidth, requiredWidth);
    const finalHeight = Math.max(baseHeight, requiredHeight);
    const fW = __round1(finalWidth);
    const fH = __round1(finalHeight);
    
    // STEP 2: Create SVG with proper dimensions
    const svg = d3.select('#d3-container').append('svg')
        .attr('width', fW)
        .attr('height', fH)
        .attr('viewBox', `0 0 ${fW} ${fH}`)
        .attr('preserveAspectRatio', 'xMinYMin meet');
    
    // STEP 3: Calculate layout positions
    const centerX = fW / 2;
    const centerY = fH / 2;
    
    // Position side nodes with proper spacing
    const causeCX = sideMargin + maxCauseW / 2;
    const effectCX = finalWidth - sideMargin - maxEffectW / 2;

    // Position causes and effects vertically
    let cy = centerY - totalCauseH / 2;
    causes.forEach(n => { n.cx = causeCX; n.cy = cy + n.h / 2; cy += n.h + vSpacing; });
    let ey = centerY - totalEffectH / 2;
    effects.forEach(n => { n.cx = effectCX; n.cy = ey + n.h / 2; ey += n.h + vSpacing; });

    // Cleanup temporary SVG
    tempSvg.remove();
    
    // RENDERING ORDER: Draw ALL arrows FIRST, then ALL nodes on top
    // Pre-compute distinct attachment points on the event rectangle to avoid stacking
    const eventLeftSlots = computeEdgeSlots(centerX, centerY, eventW, eventH, causes.length, 'left', 10);
    const eventRightSlots = computeEdgeSlots(centerX, centerY, eventW, eventH, effects.length, 'right', 10);

    // STEP 1: Draw all arrows (underneath nodes)
    // Draw arrows from causes to event
    causes.forEach((n, idx) => {
        const start = sideCenterPoint(n.cx, n.cy, n.w, n.h, 'right');
        const slotIndex = Math.min(eventLeftSlots.length - 1, Math.max(0, causes.indexOf(n)));
        const end = eventLeftSlots[slotIndex] || sideCenterPoint(centerX, centerY, eventW, eventH, 'left');
        drawArrow(start.x, start.y, end.x, end.y, THEME.linkColorCause);
    });
    
    // Draw arrows from event to effects
    effects.forEach((n, idx) => {
        const slotIndex = Math.min(eventRightSlots.length - 1, Math.max(0, effects.indexOf(n)));
        const start = eventRightSlots[slotIndex] || sideCenterPoint(centerX, centerY, eventW, eventH, 'right');
        const end = sideCenterPoint(n.cx, n.cy, n.w, n.h, 'left');
        drawArrow(start.x, start.y, end.x, end.y, THEME.linkColorEffect);
    });

    // STEP 2: Draw all nodes ON TOP of arrows
    // Draw cause nodes
    causes.forEach((n, idx) => {
        svg.append('rect')
            .attr('x', n.cx - n.w / 2)
            .attr('y', n.cy - n.h / 2)
            .attr('width', n.w)
            .attr('height', n.h)
            .attr('rx', THEME.rectRadius)
            .attr('ry', THEME.rectRadius)
            .attr('fill', THEME.causeFill)
            .attr('stroke', THEME.causeStroke)
            .attr('stroke-width', THEME.causeStrokeWidth)
            .attr('data-node-id', `multi-flow-cause-${idx}`)
            .attr('data-node-type', 'cause')
            .attr('data-cause-index', idx)
            .attr('cursor', 'pointer');
        
        svg.append('text')
            .attr('x', n.cx)
            .attr('y', n.cy)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.causeText)
            .attr('font-size', THEME.fontCause)
            .attr('data-node-id', `multi-flow-cause-${idx}`)
            .attr('data-node-type', 'cause')
            .attr('data-cause-index', idx)
            .attr('data-text-for', `multi-flow-cause-${idx}`)
            .attr('cursor', 'pointer')
            .text(n.text);
    });
    
    // Draw effect nodes
    effects.forEach((n, idx) => {
        svg.append('rect')
            .attr('x', n.cx - n.w / 2)
            .attr('y', n.cy - n.h / 2)
            .attr('width', n.w)
            .attr('height', n.h)
            .attr('rx', THEME.rectRadius)
            .attr('ry', THEME.rectRadius)
            .attr('fill', THEME.effectFill)
            .attr('stroke', THEME.effectStroke)
            .attr('stroke-width', THEME.effectStrokeWidth)
            .attr('data-node-id', `multi-flow-effect-${idx}`)
            .attr('data-node-type', 'effect')
            .attr('data-effect-index', idx)
            .attr('cursor', 'pointer');
        
        svg.append('text')
            .attr('x', n.cx)
            .attr('y', n.cy)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.effectText)
            .attr('font-size', THEME.fontEffect)
            .attr('data-node-id', `multi-flow-effect-${idx}`)
            .attr('data-node-type', 'effect')
            .attr('data-effect-index', idx)
            .attr('data-text-for', `multi-flow-effect-${idx}`)
            .attr('cursor', 'pointer')
            .text(n.text);
    });
    
    // Draw central event node (on top of everything)
    svg.append('rect')
        .attr('x', centerX - eventW / 2)
        .attr('y', centerY - eventH / 2)
        .attr('width', eventW)
        .attr('height', eventH)
        .attr('rx', THEME.rectRadius)
        .attr('ry', THEME.rectRadius)
        .attr('fill', THEME.eventFill)
        .attr('stroke', THEME.eventStroke)
        .attr('stroke-width', THEME.eventStrokeWidth)
        .attr('data-node-id', 'multi-flow-event')
        .attr('data-node-type', 'event')
        .attr('cursor', 'pointer');
    
    svg.append('text')
        .attr('x', centerX)
        .attr('y', centerY)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('fill', THEME.eventText)
        .attr('font-size', THEME.fontEvent)
        .attr('font-weight', 'bold')
        .attr('data-node-id', 'multi-flow-event')
        .attr('data-node-type', 'event')
        .attr('data-text-for', 'multi-flow-event')
        .attr('cursor', 'pointer')
        .text(spec.event);
    
    // Watermark removed from canvas display - will be added during PNG export only
    // Apply learning sheet text knockout if needed
    if (spec.is_learning_sheet && spec.hidden_node_percentage > 0) {
        knockoutTextForLearningSheet(svg, spec.hidden_node_percentage);
    }
}

// Export functions for module system
if (typeof window !== 'undefined') {
    // Browser environment - attach to window
    window.FlowRenderer = {
        renderFlowchart,
        renderFlowMap,
        renderBridgeMap,
        renderMultiFlowMap
    };
    
    // Also make these available as global functions for backward compatibility
    // This ensures the HTML can call renderFlowMap() directly
    window.renderFlowchart = renderFlowchart;
    window.renderFlowMap = renderFlowMap;
    window.renderBridgeMap = renderBridgeMap;
    window.renderMultiFlowMap = renderMultiFlowMap;
} else if (typeof module !== 'undefined' && module.exports) {
    // Node.js environment
    module.exports = {
        renderFlowchart,
        renderFlowMap,
        renderBridgeMap,
        renderMultiFlowMap
    };
}
