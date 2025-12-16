/**
 * Flow Renderer for MindGraph
 * 
 * This module contains the flowchart, flow map, multi-flow map, and bridge map rendering functions.
 * Requires: shared-utilities.js, style-manager.js
 * 
 * Performance Impact: Loads only ~45KB instead of full 213KB
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
    logger.error('FlowRenderer', 'MindGraphUtils not found! Please load shared-utilities.js first');
}

// Helper: round to 1 decimal to reduce floating-point precision noise in canvas calcs
function __round1(n) { return Math.round(n * 10) / 10; }

function renderFlowchart(spec, theme = null, dimensions = null) {
    // Validate BEFORE clearing container - defensive programming
    // Use typeof check to allow empty string (for empty button functionality)
    if (!spec || typeof spec.title !== 'string' || !Array.isArray(spec.steps)) {
        logger.error('FlowRenderer', 'Invalid spec for flowchart');
        return;
    }

    d3.select('#d3-container').html('');

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
    const maxTextWidth = 280; // Max width before wrapping
    const lineHeight = Math.round(THEME.fontNode * 1.2);

    const nodes = spec.steps.map(step => {
        // Handle both string steps and object steps (for backward compatibility)
        const txt = typeof step === 'string' ? step : (step.text || '');
        // Split by newlines and wrap each line
        const lines = window.splitAndWrapText(txt, THEME.fontNode, maxTextWidth, measureLineWidth);
        // Calculate dimensions based on wrapped lines
        const textWidth = Math.max(...lines.map(l => measureLineWidth(l, THEME.fontNode)), 20);
        const textHeight = lines.length * lineHeight;
        const w = Math.max(100, textWidth + hPad * 2);
        const h = Math.max(40, textHeight + vPad * 2);
        return { step, text: txt, lines, w, h };
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
        .attr('fill', '#666')
        .attr('stroke', '#666')
        .attr('stroke-width', '1')
        .attr('class', 'arrowhead-marker');

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

        // Render multi-line text using multiple text elements (tspan doesn't render)
        const textStartY = n.y - (n.lines.length - 1) * lineHeight / 2;
        n.lines.forEach((line, i) => {
            svg.append('text')
                .attr('x', n.x)
                .attr('y', textStartY + i * lineHeight)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', textColor || '#fff')
                .attr('font-size', THEME.fontNode)
                .attr('data-line-index', i)
                .text(line);
        });
    });

}

function renderFlowMap(spec, theme = null, dimensions = null) {
    // Validate BEFORE clearing container - defensive programming
    // Use typeof check to allow empty string (for empty button functionality)
    if (!spec || typeof spec.title !== 'string' || !Array.isArray(spec.steps)) {
        logger.error('FlowRenderer', 'Invalid spec for flow map');
        return;
    }

    d3.select('#d3-container').html('');
    
    // Get orientation (default to 'vertical' for backward compatibility)
    const orientation = spec.orientation || 'vertical';

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

    function measureLineWidth(text, fontSize) {
        const t = tempSvg.append('text')
            .attr('x', -9999)
            .attr('y', -9999)
            .attr('font-size', fontSize)
            .text(text || '');
        const w = t.node().getBBox().width;
        t.remove();
        return w;
    }

    // Measure title and steps to compute adaptive sizes (vertical layout)
    // Check for preserved dimensions first
    const nodeDimensions = spec._node_dimensions || {};
    
    // Title size - use preserved if available
    let titleSize;
    if (nodeDimensions.title && nodeDimensions.title.w && nodeDimensions.title.h) {
        titleSize = { w: nodeDimensions.title.w, h: nodeDimensions.title.h };
    } else {
        titleSize = measureTextSize(spec.title, THEME.fontTitle);
    }
    
    const stepSizes = spec.steps.map((s, idx) => {
        // Handle both string steps and object steps (for backward compatibility)
        const text = typeof s === 'string' ? s : (s.text || '');
        
        // Check for preserved dimensions first
        const nodeKey = `step-${idx}`;
        const preservedDims = nodeDimensions[nodeKey];
        
        if (preservedDims && preservedDims.w && preservedDims.h) {
            // Use preserved dimensions for empty nodes
            return { text, w: preservedDims.w, h: preservedDims.h };
        }
        
        // Calculate dimensions based on text
        // Split by newlines to handle multi-line text (Ctrl+Enter)
        const lines = (typeof window.splitTextLines === 'function') 
            ? window.splitTextLines(text) 
            : (text || '').split(/\n/);
        const lineHeight = Math.round(THEME.fontStep * 1.2);
        // Calculate width based on longest line
        const textWidth = Math.max(...lines.map(line => measureLineWidth(line, THEME.fontStep)), 20);
        // Calculate height based on number of lines
        const textHeight = lines.length * lineHeight;
        return {
            text: text,
            w: Math.max(100, textWidth + THEME.hPadStep * 2),
            h: Math.max(42, textHeight + THEME.vPadStep * 2)
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
    const substepFontSize = Math.max(12, THEME.fontStep - 1);
    const substepLineHeight = Math.round(substepFontSize * 1.2);
    const subNodesPerStep = stepSizes.map((stepObj, stepIdx) => {
        const subs = stepToSubsteps[stepObj.text] || [];
        return subs.map((txt, substepIdx) => {
            const text = txt || '';
            
            // Check for preserved dimensions first
            const nodeKey = `substep-${stepIdx}-${substepIdx}`;
            const preservedDims = nodeDimensions[nodeKey];
            
            if (preservedDims && preservedDims.w && preservedDims.h) {
                // Use preserved dimensions for empty nodes
                return { text, w: preservedDims.w, h: preservedDims.h };
            }
            
            // Calculate dimensions based on text
            // Split by newlines to handle multi-line text (Ctrl+Enter)
            const lines = (typeof window.splitTextLines === 'function') 
                ? window.splitTextLines(text) 
                : text.split(/\n/);
            // Calculate max line width
            let maxLineWidth = 20;
            lines.forEach(line => {
                const w = measureLineWidth(line, substepFontSize);
                if (w > maxLineWidth) maxLineWidth = w;
            });
            // Calculate height based on number of lines
            const textHeight = lines.length * substepLineHeight;
            return {
                text: text,
                w: Math.max(80, maxLineWidth + THEME.hPadStep * 2),
                h: Math.max(28, textHeight + THEME.vPadStep * 2)
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

    const maxStepBoxWidth = stepSizes.reduce((mw, s) => Math.max(mw, s.w), 0);
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
    const initialWidth = Math.max(titleSize.w, maxStepBoxWidth + rightSideWidth) + padding * 2 + extraPadding;
    
    // Use agent recommendations as minimum for initial sizing
    let baseWidth, baseHeight;
    if (dimensions && dimensions.baseWidth && dimensions.baseHeight) {
        baseWidth = Math.max(dimensions.baseWidth, initialWidth);
        baseHeight = dimensions.baseHeight; // Will be updated after substep positioning
    } else {
        baseWidth = initialWidth;
        baseHeight = 600; // Initial estimate, will be updated
    }

    // NOTE: Keep tempSvg until after rendering for text measurement during drawing
    // It will be removed after all elements are drawn

    // DON'T set explicit width/height on container - let CSS handle it (100% fill)
    // This allows the canvas to fill the viewport and auto-fit to work properly

    // Create actual SVG with viewBox for proper scaling
    const svg = d3.select('#d3-container').append('svg')
        .attr('viewBox', `0 0 ${baseWidth} ${baseHeight}`)
        .attr('preserveAspectRatio', 'xMidYMid meet');

    // Render based on orientation (title will be drawn after step positions are calculated)
    if (orientation === 'vertical') {
        // VERTICAL LAYOUT (existing code)
        const centerX = baseWidth / 2;
        const startY = padding + 40; // Starting position for content (title will be positioned above step 1)
        
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
    
    // Draw title above step 1's first substep (if exists) or above step 1 (before drawing connectors and steps)
    let titleY = padding;
    if (stepCenters.length > 0) {
        let referenceY;
        
        // Check if step 1 has substeps - if yes, position title above first substep
        const step1Substeps = allSubstepPositions[0];
        if (step1Substeps && step1Substeps.length > 0) {
            // Position above first substep of step 1
            const firstSubstepTop = step1Substeps[0].y;
            referenceY = firstSubstepTop;
        } else {
            // No substeps - position above step 1
            const step1YCenter = stepCenters[0];
            const step1Top = step1YCenter - stepSizes[0].h / 2;
            referenceY = step1Top;
        }
        
        titleY = Math.max(padding, referenceY - titleSize.h - 15); // 15px gap above reference
        
        svg.append('text')
            .attr('x', centerX)  // Aligned with step 1 (centerX)
            .attr('y', titleY)
            .attr('text-anchor', 'middle')
            .attr('fill', THEME.titleText)
            .attr('font-size', THEME.fontTitle)
            .attr('font-family', THEME.fontFamily)
            .attr('font-weight', 'bold')
            .attr('data-node-id', 'flow-title')
            .attr('data-node-type', 'title')
            .attr('cursor', 'pointer')
            .text(spec.title);
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
                    .attr('fill', '#666')
                    .attr('stroke', '#666')
                    .attr('stroke-width', '1')
                    .attr('class', 'arrowhead-triangle');
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

        // Render step text with automatic wrapping and tspan (always use tspan)
        const stepText = s.text || '';
        const stepMaxWidth = s.w * 0.9; // Max width based on box width
        const stepLineHeight = Math.round(THEME.fontStep * 1.2);
        
        // Use splitAndWrapText for automatic word wrapping
        const stepLines = (typeof window.splitAndWrapText === 'function')
            ? window.splitAndWrapText(stepText, THEME.fontStep, stepMaxWidth, measureLineWidth)
            : (stepText ? [stepText] : ['']);
        
        // Ensure at least one line for placeholder
        const finalStepLines = stepLines.length > 0 ? stepLines : [''];
        
        // WORKAROUND: Use multiple text elements instead of tspan
        const stepStartY = stepYCenter - (finalStepLines.length - 1) * stepLineHeight / 2;
        finalStepLines.forEach((line, i) => {
            svg.append('text')
                .attr('x', stepXCenter)
                .attr('y', stepStartY + i * stepLineHeight)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', THEME.stepText)        // White text
                .attr('font-size', THEME.fontStep)
                .attr('font-family', THEME.fontFamily)  // Add font family to match bubble map
                .attr('data-node-id', `flow-step-${index}`)
                .attr('data-node-type', 'step')
                .attr('data-step-index', index)
                .attr('cursor', 'pointer')
                .attr('data-line-index', i)
                .text(line);
        });
    });

    // Calculate accurate canvas dimensions based on actual content positions
    // Track ALL bounds: top, bottom, left, right
    let contentTop = Infinity;
    let contentBottom = 0;
    let contentLeft = Infinity;
    let contentRight = 0;
    
    // Account for stroke width - half extends beyond the rect dimensions
    const stepStrokeOffset = Math.ceil(THEME.stepStrokeWidth / 2);
    
    // Include title in bounds calculation (title was drawn with titleY as baseline)
    // Text baseline is at titleY, so actual top is approximately titleY - titleSize.h
    if (titleY !== undefined) {
        const titleTop = titleY - titleSize.h;
        const titleBottom = titleY + 5; // Small descent allowance
        const titleLeft = centerX - titleSize.w / 2;
        const titleRight = centerX + titleSize.w / 2;
        contentTop = Math.min(contentTop, titleTop);
        contentBottom = Math.max(contentBottom, titleBottom);
        contentLeft = Math.min(contentLeft, titleLeft);
        contentRight = Math.max(contentRight, titleRight);
    }
    
    // Find bounds of main steps
    if (stepCenters.length > 0) {
        for (let i = 0; i < stepCenters.length; i++) {
            const stepTop = stepCenters[i] - stepSizes[i].h / 2 - stepStrokeOffset;
            const stepBottom = stepCenters[i] + stepSizes[i].h / 2 + stepStrokeOffset;
            const stepLeft = centerX - stepSizes[i].w / 2 - stepStrokeOffset;
            const stepRight = centerX + stepSizes[i].w / 2 + stepStrokeOffset;
            contentTop = Math.min(contentTop, stepTop);
            contentBottom = Math.max(contentBottom, stepBottom);
            contentLeft = Math.min(contentLeft, stepLeft);
            contentRight = Math.max(contentRight, stepRight);
        }
    }
    
    // Find bounds of substeps (which now control the layout)
    // Account for stroke width - half extends beyond the rect dimensions
    const substepStrokeWidth = Math.max(1, THEME.stepStrokeWidth - 1);
    const strokeOffset = Math.ceil(substepStrokeWidth / 2);
    
    for (let stepIdx = 0; stepIdx < allSubstepPositions.length; stepIdx++) {
        const stepPositions = allSubstepPositions[stepIdx];
        for (let nodeIdx = 0; nodeIdx < stepPositions.length; nodeIdx++) {
            const substep = stepPositions[nodeIdx];
            const substepTop = substep.y - strokeOffset;
            const substepBottom = substep.y + substep.h + strokeOffset;
            const substepLeft = substep.x - strokeOffset;
            const substepRight = substep.x + substep.w + strokeOffset;
            contentTop = Math.min(contentTop, substepTop);
            contentBottom = Math.max(contentBottom, substepBottom);
            contentLeft = Math.min(contentLeft, substepLeft);
            contentRight = Math.max(contentRight, substepRight);
        }
    }
    
    // Calculate final dimensions with padding on ALL sides
    // Ensure minimum padding from content to edge
    const minPaddingFromEdge = padding;
    const calculatedWidth = Math.max(baseWidth, contentRight + minPaddingFromEdge, (contentRight - contentLeft) + minPaddingFromEdge * 2);
    const calculatedHeight = Math.max(baseHeight, contentBottom + minPaddingFromEdge, (contentBottom - contentTop) + minPaddingFromEdge * 2);
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
            
            // Render substep text with automatic wrapping and tspan (always use tspan)
            const substepText = substep.text || '';
            const substepMaxWidth = substep.w * 0.9; // Max width based on box width
            const substepFontSize = Math.max(12, THEME.fontStep - 1);
            const substepLineHeight = Math.round(substepFontSize * 1.2);
            
            // Use splitAndWrapText for automatic word wrapping
            const substepLines = (typeof window.splitAndWrapText === 'function')
                ? window.splitAndWrapText(substepText, substepFontSize, substepMaxWidth, measureLineWidth)
                : (substepText ? [substepText] : ['']);
            
            // Ensure at least one line for placeholder
            const finalSubstepLines = substepLines.length > 0 ? substepLines : [''];
            
            // WORKAROUND: Use multiple text elements instead of tspan
            const substepStartY = substep.y + substep.h / 2 - (finalSubstepLines.length - 1) * substepLineHeight / 2;
            finalSubstepLines.forEach((line, i) => {
                svg.append('text')
                    .attr('x', substep.x + substep.w / 2)
                    .attr('y', substepStartY + i * substepLineHeight)
                    .attr('text-anchor', 'middle')
                    .attr('dominant-baseline', 'middle')
                    .attr('fill', THEME.substepText)        // Dark text for readability
                    .attr('font-size', substepFontSize)
                    .attr('font-family', THEME.fontFamily)  // Add font family to match bubble map
                    .attr('data-node-id', `flow-substep-${stepIdx}-${nodeIdx}`)
                    .attr('data-node-type', 'substep')
                    .attr('data-step-index', stepIdx)
                    .attr('data-substep-index', nodeIdx)
                    .attr('cursor', 'pointer')
                    .attr('data-line-index', i)
                    .text(line);
            });
            
            // L-shaped connectors already drawn earlier (Step 3b) for proper z-order
        });
    });
    
        // Always update SVG dimensions to match calculated content
        // This ensures the viewBox captures ALL content, not just initial estimates
        svg.attr('viewBox', `0 0 ${cw} ${ch}`)
           .attr('preserveAspectRatio', 'xMidYMid meet');
        
        // Clean up temp svg now that all rendering is complete
        tempSvg.remove();
        
    } else {
        // HORIZONTAL LAYOUT (new code)
        const centerY = baseHeight / 2;
        const startX = padding + 60; // Start from left with padding
        
        const subOffsetY = 40; // Gap between step and substeps (below)
        // Reuse subSpacing from above (30) for consistency
        
        // Calculate horizontal step spacing
        const stepSpacing = 100; // Horizontal spacing between steps
        const totalStepsWidth = stepSizes.reduce((sum, s) => sum + s.w, 0) + (stepSizes.length - 1) * stepSpacing;
        
        // Adjust baseWidth if needed for horizontal layout
        const maxSubGroupHeight = subGroupHeights.reduce((mx, h) => Math.max(mx, h), 0);
        const requiredHeight = Math.max(
            baseHeight,
            maxSubGroupHeight + subOffsetY + maxStepBoxWidth + padding * 2
        );
        
        if (requiredHeight > baseHeight) {
            baseHeight = requiredHeight;
            svg.attr('viewBox', `0 0 ${baseWidth} ${baseHeight}`)
               .attr('preserveAspectRatio', 'xMidYMid meet');
        }
        
        // Calculate step X positions (horizontal row)
        const stepCentersX = [];
        let currentStepX = startX;
        
        for (let stepIdx = 0; stepIdx < stepSizes.length; stepIdx++) {
            const stepWidth = stepSizes[stepIdx].w;
            stepCentersX.push(currentStepX + stepWidth / 2);
            currentStepX += stepWidth + stepSpacing;
        }
        
        // Draw title above step 1
        let titleY = padding;
        if (stepCentersX.length > 0) {
            const step1XCenter = stepCentersX[0];
            const step1Top = centerY - stepSizes[0].h / 2;
            titleY = Math.max(padding, step1Top - titleSize.h - 15); // 15px gap above step 1
            
            svg.append('text')
                .attr('x', step1XCenter)  // Aligned with step 1 X center
                .attr('y', titleY)
                .attr('text-anchor', 'middle')
                .attr('fill', THEME.titleText)
                .attr('font-size', THEME.fontTitle)
                .attr('font-family', THEME.fontFamily)
                .attr('font-weight', 'bold')
                .attr('data-node-id', 'flow-title')
                .attr('data-node-type', 'title')
                .attr('cursor', 'pointer')
                .text(spec.title);
        }
        
        // Adjust centerY to account for substeps below
        const maxSubHeight = maxSubGroupHeight;
        const adjustedCenterY = centerY;
        
        // Calculate substep positions (below each step)
        const allSubstepPositions = [];
        for (let stepIdx = 0; stepIdx < stepSizes.length; stepIdx++) {
            const nodes = subNodesPerStep[stepIdx];
            const stepPositions = [];
            const stepXCenter = stepCentersX[stepIdx];
            const stepBottomY = adjustedCenterY + stepSizes[stepIdx].h / 2;
            
            if (nodes.length > 0) {
                let currentSubY = stepBottomY + subOffsetY;
                for (let nodeIdx = 0; nodeIdx < nodes.length; nodeIdx++) {
                    const node = nodes[nodeIdx];
                    stepPositions.push({
                        x: stepXCenter - node.w / 2, // Center substep under step
                        y: currentSubY,
                        w: node.w,
                        h: node.h,
                        text: node.text
                    });
                    currentSubY += node.h + subSpacing;
                }
            }
            allSubstepPositions.push(stepPositions);
        }
        
        // Draw arrows between steps (horizontal, pointing right)
        stepSizes.forEach((s, index) => {
            const stepXCenter = stepCentersX[index];
            const stepYCenter = adjustedCenterY;
            
            if (index < stepSizes.length - 1) {
                const nextStepXCenter = stepCentersX[index + 1];
                const currentRight = stepXCenter + s.w / 2 + 6;
                const nextLeft = nextStepXCenter - stepSizes[index + 1].w / 2 - 6;
                
                if (nextLeft > currentRight) {
                    svg.append('line')
                        .attr('x1', currentRight)
                        .attr('y1', stepYCenter)
                        .attr('x2', nextLeft)
                        .attr('y2', stepYCenter)
                        .attr('stroke', '#666')
                        .attr('stroke-width', 2);
                    svg.append('polygon')
                        .attr('points', `${nextLeft},${stepYCenter} ${nextLeft - 10},${stepYCenter - 5} ${nextLeft - 10},${stepYCenter + 5}`)
                        .attr('fill', '#666')
                        .attr('stroke', '#666')
                        .attr('stroke-width', '1')
                        .attr('class', 'arrowhead-triangle');
                }
            }
        });
        
        // Draw connectors from steps to substeps (edge-to-edge, no lines through nodes)
        allSubstepPositions.forEach((stepPositions, stepIdx) => {
            const stepXCenter = stepCentersX[stepIdx];
            const stepYCenter = adjustedCenterY;
            const stepBottomY = stepYCenter + stepSizes[stepIdx].h / 2;
            
            if (stepPositions.length === 0) return;
            
            // Draw vertical line from step bottom to first substep top
            const firstSubstep = stepPositions[0];
            const firstSubstepTopY = firstSubstep.y;
            
            svg.append('line')
                .attr('x1', stepXCenter)
                .attr('y1', stepBottomY)
                .attr('x2', stepXCenter)
                .attr('y2', firstSubstepTopY)
                .attr('stroke', '#888')
                .attr('stroke-width', 1.5);
            
            // For subsequent substeps, draw vertical lines from previous substep bottom to current top
            for (let nodeIdx = 1; nodeIdx < stepPositions.length; nodeIdx++) {
                const prevSubstep = stepPositions[nodeIdx - 1];
                const currSubstep = stepPositions[nodeIdx];
                const prevBottomY = prevSubstep.y + prevSubstep.h;
                const currTopY = currSubstep.y;
                
                svg.append('line')
                    .attr('x1', stepXCenter)
                    .attr('y1', prevBottomY)
                    .attr('x2', stepXCenter)
                    .attr('y2', currTopY)
                    .attr('stroke', '#888')
                    .attr('stroke-width', 1.5);
            }
        });
        
        // Draw main step nodes
        stepSizes.forEach((s, index) => {
            const stepXCenter = stepCentersX[index];
            const stepYCenter = adjustedCenterY;
            
            // Rect
            svg.append('rect')
                .attr('x', stepXCenter - s.w / 2)
                .attr('y', stepYCenter - s.h / 2)
                .attr('width', s.w)
                .attr('height', s.h)
                .attr('rx', THEME.rectRadius)
                .attr('fill', THEME.stepFill)
                .attr('stroke', THEME.stepStroke)
                .attr('stroke-width', THEME.stepStrokeWidth)
                .attr('data-node-id', `flow-step-${index}`)
                .attr('data-node-type', 'step')
                .attr('data-step-index', index)
                .attr('cursor', 'pointer');
            
            // Render step text with automatic wrapping and tspan (always use tspan)
            const hStepText = s.text || '';
            const hStepMaxWidth = s.w * 0.9; // Max width based on box width
            const hStepLineHeight = Math.round(THEME.fontStep * 1.2);
            
            // Use splitAndWrapText for automatic word wrapping
            const hStepLines = (typeof window.splitAndWrapText === 'function')
                ? window.splitAndWrapText(hStepText, THEME.fontStep, hStepMaxWidth, measureLineWidth)
                : (hStepText ? [hStepText] : ['']);
            
            // Ensure at least one line for placeholder
            const finalHStepLines = hStepLines.length > 0 ? hStepLines : [''];
            
            // WORKAROUND: Use multiple text elements instead of tspan
            const hStepStartY = stepYCenter - (finalHStepLines.length - 1) * hStepLineHeight / 2;
            finalHStepLines.forEach((line, i) => {
                svg.append('text')
                    .attr('x', stepXCenter)
                    .attr('y', hStepStartY + i * hStepLineHeight)
                    .attr('text-anchor', 'middle')
                    .attr('dominant-baseline', 'middle')
                    .attr('fill', THEME.stepText)
                    .attr('font-size', THEME.fontStep)
                    .attr('font-family', THEME.fontFamily)
                    .attr('data-node-id', `flow-step-${index}`)
                    .attr('data-node-type', 'step')
                    .attr('data-step-index', index)
                    .attr('cursor', 'pointer')
                    .attr('data-line-index', i)
                    .text(line);
            });
        });
        
        // Draw substeps
        allSubstepPositions.forEach((stepPositions, stepIdx) => {
            stepPositions.forEach((substep, nodeIdx) => {
                // Draw substep rectangle
                svg.append('rect')
                    .attr('x', substep.x)
                    .attr('y', substep.y)
                    .attr('width', substep.w)
                    .attr('height', substep.h)
                    .attr('rx', Math.max(4, THEME.rectRadius - 2))
                    .attr('fill', THEME.substepFill)
                    .attr('stroke', THEME.substepStroke)
                    .attr('stroke-width', Math.max(1, THEME.stepStrokeWidth - 1))
                    .attr('data-node-id', `flow-substep-${stepIdx}-${nodeIdx}`)
                    .attr('data-node-type', 'substep')
                    .attr('data-step-index', stepIdx)
                    .attr('data-substep-index', nodeIdx)
                    .attr('cursor', 'pointer');
                
                // Render substep text with automatic wrapping and tspan (always use tspan)
                const hSubstepText = substep.text || '';
                const hSubstepMaxWidth = substep.w * 0.9; // Max width based on box width
                const hSubstepFontSize = Math.max(12, THEME.fontStep - 1);
                const hSubstepLineHeight = Math.round(hSubstepFontSize * 1.2);
                
                // Use splitAndWrapText for automatic word wrapping
                const hSubstepLines = (typeof window.splitAndWrapText === 'function')
                    ? window.splitAndWrapText(hSubstepText, hSubstepFontSize, hSubstepMaxWidth, measureLineWidth)
                    : (hSubstepText ? [hSubstepText] : ['']);
                
                // Ensure at least one line for placeholder
                const finalHSubstepLines = hSubstepLines.length > 0 ? hSubstepLines : [''];
                
                // WORKAROUND: Use multiple text elements instead of tspan
                const hSubstepStartY = substep.y + substep.h / 2 - (finalHSubstepLines.length - 1) * hSubstepLineHeight / 2;
                finalHSubstepLines.forEach((line, i) => {
                    svg.append('text')
                        .attr('x', substep.x + substep.w / 2)
                        .attr('y', hSubstepStartY + i * hSubstepLineHeight)
                        .attr('text-anchor', 'middle')
                        .attr('dominant-baseline', 'middle')
                        .attr('fill', THEME.substepText)
                        .attr('font-size', hSubstepFontSize)
                        .attr('font-family', THEME.fontFamily)
                        .attr('data-node-id', `flow-substep-${stepIdx}-${nodeIdx}`)
                        .attr('data-node-type', 'substep')
                        .attr('data-step-index', stepIdx)
                        .attr('data-substep-index', nodeIdx)
                        .attr('cursor', 'pointer')
                        .attr('data-line-index', i)
                        .text(line);
                });
            });
        });
        
        // Calculate canvas dimensions for horizontal layout
        let contentBottom = 0;
        let contentRight = 0;
        const stepStrokeOffset = Math.ceil(THEME.stepStrokeWidth / 2);
        
        // Find right edge of steps
        if (stepCentersX.length > 0) {
            const lastStepIndex = stepCentersX.length - 1;
            const lastStepRight = stepCentersX[lastStepIndex] + stepSizes[lastStepIndex].w / 2 + stepStrokeOffset;
            contentRight = Math.max(contentRight, lastStepRight);
        }
        
        // Find bottom of substeps
        const substepStrokeWidth = Math.max(1, THEME.stepStrokeWidth - 1);
        const strokeOffset = Math.ceil(substepStrokeWidth / 2);
        
        for (let stepIdx = 0; stepIdx < allSubstepPositions.length; stepIdx++) {
            const stepPositions = allSubstepPositions[stepIdx];
            for (let nodeIdx = 0; nodeIdx < stepPositions.length; nodeIdx++) {
                const substep = stepPositions[nodeIdx];
                const substepBottom = substep.y + substep.h + strokeOffset;
                const substepRight = substep.x + substep.w + strokeOffset;
                contentBottom = Math.max(contentBottom, substepBottom);
                contentRight = Math.max(contentRight, substepRight);
            }
        }
        
        // Update SVG dimensions
        const calculatedHeight = Math.max(baseHeight, contentBottom + padding);
        const calculatedWidth = Math.max(baseWidth, contentRight + padding, totalStepsWidth + padding * 2);
        const ch = __round1(calculatedHeight);
        const cw = __round1(calculatedWidth);
        
        // Always update viewBox to ensure all content is captured
        svg.attr('viewBox', `0 0 ${cw} ${ch}`)
           .attr('preserveAspectRatio', 'xMidYMid meet');
        
        // Clean up temp svg now that all rendering is complete
        tempSvg.remove();
    }
    
    // Apply learning sheet text knockout if needed
    if (spec.is_learning_sheet && spec.hidden_node_percentage > 0) {
        knockoutTextForLearningSheet(svg, spec.hidden_node_percentage);
    }
}

function renderBridgeMap(spec, theme = null, dimensions = null, containerId = 'd3-container') {

    logger.debug('FlowRenderer', 'Rendering bridge map', {
        analogiesCount: spec?.analogies?.length || 0,
        dimension: spec?.dimension,
        alternativeDimensions: spec?.alternative_dimensions?.length || 0
    });
    
    // Validate BEFORE clearing container - defensive programming
    // Use typeof check to allow empty string (for empty button functionality)
    if (!spec || !Array.isArray(spec.analogies) || spec.analogies.length === 0) {
        logger.error('FlowRenderer', 'Invalid spec for bridge map');
        return;
    }
    
    // Validate that analogies have the correct structure (allow empty strings)
    if (!spec.analogies.every(analogy => typeof analogy.left === 'string' && typeof analogy.right === 'string')) {
        logger.error('FlowRenderer', 'Invalid analogy structure');
        return;
    }
    
    d3.select(`#${containerId}`).html('');
    
    // Apply theme first (needed for text measurement)
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
    
    // Create temporary SVG for text measurement FIRST (needed to calculate optimal dimensions)
    const tempSvg = d3.select('body').append('svg')
        .attr('width', 0)
        .attr('height', 0)
        .style('position', 'absolute')
        .style('left', '-9999px')
        .style('top', '-9999px');
    
    // Measure single line width for adaptive node sizing
    function measureLineWidth(text, fontSize) {
        const t = tempSvg.append('text')
            .attr('x', -9999)
            .attr('y', -9999)
            .attr('font-size', fontSize)
            .attr('font-family', THEME.fontFamily)
            .text(text || '');
        const w = t.node().getBBox().width;
        t.remove();
        return w;
    }
    
    // PHASE 1: Measure all text to calculate actual node widths
    const maxTextWidthLimit = 200; // Max width before text wraps
    const nodePadding = 24; // Padding inside each node
    const nodeGap = 60; // Minimum gap between nodes
    
    // Check for preserved dimensions from empty button operation
    const nodeDimensions = spec._node_dimensions || {};
    
    const nodeWidths = spec.analogies.map((analogy, pairIndex) => {
        // Measure left text - use preserved dimensions if available
        const leftText = analogy.left || '';
        const leftNodeKey = `left-${pairIndex}`;
        const leftPreserved = nodeDimensions[leftNodeKey];
        
        let leftWidth;
        if (leftPreserved && leftPreserved.w && leftText === '') {
            leftWidth = leftPreserved.w - nodePadding; // Subtract padding since we add it back
            logger.debug('BridgeMapRenderer', 'Using preserved left width', { pairIndex, width: leftPreserved.w });
        } else {
            const leftLines = (typeof window.splitAndWrapText === 'function')
                ? window.splitAndWrapText(leftText, parseFloat(THEME.analogyFontSize), maxTextWidthLimit, measureLineWidth)
                : (leftText ? [leftText] : ['']);
            leftWidth = Math.max(...leftLines.map(l => measureLineWidth(l, parseFloat(THEME.analogyFontSize))), 20);
        }
        
        // Measure right text - use preserved dimensions if available
        const rightText = analogy.right || '';
        const rightNodeKey = `right-${pairIndex}`;
        const rightPreserved = nodeDimensions[rightNodeKey];
        
        let rightWidth;
        if (rightPreserved && rightPreserved.w && rightText === '') {
            rightWidth = rightPreserved.w - nodePadding; // Subtract padding since we add it back
            logger.debug('BridgeMapRenderer', 'Using preserved right width', { pairIndex, width: rightPreserved.w });
        } else {
            const rightLines = (typeof window.splitAndWrapText === 'function')
                ? window.splitAndWrapText(rightText, parseFloat(THEME.analogyFontSize), maxTextWidthLimit, measureLineWidth)
                : (rightText ? [rightText] : ['']);
            rightWidth = Math.max(...rightLines.map(l => measureLineWidth(l, parseFloat(THEME.analogyFontSize))), 20);
        }
        
        // Node width is the max of left/right text widths + padding
        const nodeWidth = Math.max(leftWidth, rightWidth) + nodePadding;
        return Math.max(60, nodeWidth); // Minimum 60px
    });
    
    // PHASE 2: Calculate optimal dimensions based on actual content
    const numAnalogies = spec.analogies.length;
    const leftPadding = 110; // Extra left padding for dimension label
    const rightPadding = 40; // Right padding
    const topBottomPadding = 40; // Top and bottom padding
    
    // Calculate section width based on the widest node
    // Each node should fit within its section with margin for separators
    const maxNodeWidth = Math.max(...nodeWidths);
    const separatorMargin = 30; // Margin on each side of separator
    const sectionWidth = maxNodeWidth + separatorMargin * 2; // Space for one node + margins
    
    // Calculate required width: all sections + padding
    const requiredWidth = numAnalogies * sectionWidth + leftPadding + rightPadding;
    
    // Use the larger of required width or provided dimensions
    const width = Math.max(requiredWidth, dimensions?.baseWidth || 600);
    
    // Recalculate section width based on actual available width (might be larger than required)
    const availableWidth = width - leftPadding - rightPadding;
    const actualSectionWidth = availableWidth / numAnalogies;
    
    // Calculate optimal height
    const lineHeight = 50;
    const altDimensionsHeight = 80;
    const baseTextHeight = 40;
    const height = Math.max(baseTextHeight + lineHeight + (2 * topBottomPadding) + altDimensionsHeight, dimensions?.baseHeight || 200);
    
    // Create SVG with calculated dimensions
    const svg = d3.select(`#${containerId}`)
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', `0 0 ${width} ${height}`)
        .attr('preserveAspectRatio', 'xMidYMid meet')
        .style('background-color', '#f8f8f8');
    
    // 1. Create horizontal main line
    svg.append("line")
        .attr("x1", leftPadding)
        .attr("y1", height/2)
        .attr("x2", width - rightPadding)
        .attr("y2", height/2)
        .attr("stroke", "#666666")
        .attr("stroke-width", 4);
    
    // 2. Calculate separator positions (at section boundaries)
    // Separators are between sections, so at positions: leftPadding + sectionWidth, leftPadding + 2*sectionWidth, etc.
    const separatorPositions = [];
    for (let i = 1; i < numAnalogies; i++) {
        separatorPositions.push(leftPadding + i * actualSectionWidth);
    }
    
    // 3. Calculate node positions (centered in each section)
    // Node i is centered in section i, so at: leftPadding + (i + 0.5) * sectionWidth
    const nodePositions = [];
    for (let i = 0; i < numAnalogies; i++) {
        nodePositions.push(leftPadding + (i + 0.5) * actualSectionWidth);
    }
    
    // Check for custom positions
    const customPositions = spec._customPositions || {};
    const hasCustomPositions = Object.keys(customPositions).length > 0;
    
    // Position analogy pairs
    // If custom positions exist but some pairs don't have positions (new pairs added),
    // recalculate all positions evenly to maintain proper spacing
    const pairCount = spec.analogies.length;
    
    // Count how many pairs have custom positions (both left and right must exist)
    let pairsWithCustomPositions = 0;
    if (hasCustomPositions) {
        for (let i = 0; i < pairCount; i++) {
            const leftNodeId = `bridge-left-${i}`;
            const rightNodeId = `bridge-right-${i}`;
            const hasLeft = customPositions.hasOwnProperty(leftNodeId) && customPositions[leftNodeId] !== null && customPositions[leftNodeId] !== undefined;
            const hasRight = customPositions.hasOwnProperty(rightNodeId) && customPositions[rightNodeId] !== null && customPositions[rightNodeId] !== undefined;
            if (hasLeft && hasRight) {
                pairsWithCustomPositions++;
            }
        }
    }
    
    const hasNewPairsWithoutPositions = hasCustomPositions && pairsWithCustomPositions < pairCount;
    const shouldRecalculateEvenly = hasNewPairsWithoutPositions;
    
    logger.info('[BridgeMap-Renderer] Position detection check', {
        hasCustomPositions,
        pairCount,
        pairsWithCustomPositions,
        hasNewPairsWithoutPositions,
        shouldRecalculateEvenly
    });
    console.log('[BridgeMap-Renderer] 🔍 Position detection check:', {
        hasCustomPositions,
        pairCount,
        pairsWithCustomPositions,
        hasNewPairsWithoutPositions,
        shouldRecalculateEvenly
    });
    
    // Store node references globally for drag operations
    const bridgeMapNodes = [];
    
    // Use the max text width limit for wrapping (same as measurement phase)
    const adaptiveMaxTextWidth = maxTextWidthLimit;
    
    // 3. Draw analogy pairs with calculated positions
    spec.analogies.forEach((analogy, i) => {
        
        const leftNodeId = `bridge-left-${i}`;
        const rightNodeId = `bridge-right-${i}`;
        
        // Check if custom positions exist and we're not recalculating
        let leftX, leftY, rightX, rightY;
        if (hasCustomPositions && customPositions[leftNodeId] && customPositions[rightNodeId] && !shouldRecalculateEvenly) {
            leftX = customPositions[leftNodeId].x;
            leftY = customPositions[leftNodeId].y;
            rightX = customPositions[rightNodeId].x;
            rightY = customPositions[rightNodeId].y;
        } else {
            const xPos = nodePositions[i]; // Use pre-calculated position based on actual node widths
            leftX = xPos;
            leftY = height/2 - 30;
            rightX = xPos;
            rightY = height/2 + 40;
        }
        
        const isFirstPair = i === 0; // Check if this is the first pair
        
        // 3.1 Add upstream item (left) - above the main line
        if (isFirstPair) {
            // First pair gets rectangle borders with deep blue background and white text
            // Calculate adaptive height based on text lines
            const leftText = analogy.left || '';
            const leftMaxWidth = adaptiveMaxTextWidth; // Adaptive width based on available space
            const leftLineHeight = Math.round(parseFloat(THEME.analogyFontSize) * 1.2);
            
            // Check for preserved dimensions
            const leftNodeKey = `left-${i}`;
            const leftPreserved = nodeDimensions[leftNodeKey];
            
            // Use splitAndWrapText for automatic word wrapping
            const leftLines = (typeof window.splitAndWrapText === 'function')
                ? window.splitAndWrapText(leftText, parseFloat(THEME.analogyFontSize), leftMaxWidth, measureLineWidth)
                : (leftText ? [leftText] : ['']);
            
            // Ensure at least one line for placeholder
            const finalLeftLines = leftLines.length > 0 ? leftLines : [''];
            
            // Calculate adaptive dimensions - use preserved dimensions if available for empty node
            let rectWidth, rectHeight;
            if (leftPreserved && leftPreserved.w && leftPreserved.h && leftText === '') {
                rectWidth = leftPreserved.w;
                rectHeight = leftPreserved.h;
                logger.debug('BridgeMapRenderer', 'Using preserved left rect dimensions', { i, rectWidth, rectHeight });
            } else {
                const leftTextWidth = Math.max(...finalLeftLines.map(l => measureLineWidth(l, parseFloat(THEME.analogyFontSize))), 20);
                rectWidth = Math.max(60, leftTextWidth + 20); // Min 60px, add 20px padding
                rectHeight = Math.max(30, finalLeftLines.length * leftLineHeight + 10); // Adaptive height
            }
            
            // Store node reference
            bridgeMapNodes.push({
                id: i,
                nodeId: leftNodeId,
                type: 'left',
                x: leftX,
                y: leftY,
                width: rectWidth,
                height: rectHeight
            });
            
            // Draw rectangle background
            svg.append("rect")
                .attr("x", leftX - rectWidth/2)
                .attr("y", leftY - rectHeight/2)
                .attr("width", rectWidth)
                .attr("height", rectHeight)
                .attr("rx", 4)
                .attr("fill", "#1976d2") // Deep blue from mind map
                .attr("stroke", "#0d47a1")
                .attr("stroke-width", 2)
                .attr("data-node-id", leftNodeId)
                .attr("data-node-type", "left")
                .attr("data-pair-index", i)
                .attr("cursor", "pointer");
            
            // WORKAROUND: Use multiple text elements instead of tspan
            const leftStartY = leftY - (finalLeftLines.length - 1) * leftLineHeight / 2;
            finalLeftLines.forEach((line, idx) => {
                svg.append("text")
                    .attr("x", leftX)
                    .attr("y", leftStartY + idx * leftLineHeight)
                    .attr("text-anchor", "middle")
                    .attr("dominant-baseline", "middle")
                    .style("font-size", THEME.analogyFontSize)
                    .style("fill", "#ffffff") // White text
                    .style("font-weight", "bold")
                    .attr("data-text-for", leftNodeId)
                    .attr("data-node-id", leftNodeId)
                    .attr("data-node-type", "left")
                    .attr("data-pair-index", i)
                    .attr("cursor", "pointer")
                    .attr("data-line-index", idx)
                    .text(line);
            });
        } else {
            // Store node reference for regular pairs
            bridgeMapNodes.push({
                id: i,
                nodeId: leftNodeId,
                type: 'left',
                x: leftX,
                y: leftY,
                width: 0, // Text nodes don't have explicit width
                height: 0
            });
            
            // Render left analogy text - regular pairs - use multiple text elements
            const regLeftText = analogy.left || '';
            const regLeftMaxWidth = adaptiveMaxTextWidth; // Adaptive width based on available space
            const regLeftLineHeight = Math.round(parseFloat(THEME.analogyFontSize) * 1.2);
            
            // Use splitAndWrapText for automatic word wrapping
            const regLeftLines = (typeof window.splitAndWrapText === 'function')
                ? window.splitAndWrapText(regLeftText, parseFloat(THEME.analogyFontSize), regLeftMaxWidth, measureLineWidth)
                : (regLeftText ? [regLeftText] : ['']);
            
            // Ensure at least one line for placeholder
            const finalRegLeftLines = regLeftLines.length > 0 ? regLeftLines : [''];
            
            // WORKAROUND: Use multiple text elements instead of tspan
            const regLeftStartY = leftY - (finalRegLeftLines.length - 1) * regLeftLineHeight / 2;
            finalRegLeftLines.forEach((line, idx) => {
                svg.append("text")
                    .attr("x", leftX)
                    .attr("y", regLeftStartY + idx * regLeftLineHeight)
                    .attr("text-anchor", "middle")
                    .attr("dominant-baseline", "middle")
                    .style("font-size", THEME.analogyFontSize)
                    .style("fill", THEME.analogyTextColor)
                    .style("font-weight", "bold")
                    .attr("data-node-id", leftNodeId)
                    .attr("data-node-type", "left")
                    .attr("data-pair-index", i)
                    .attr("cursor", "pointer")
                    .attr("data-line-index", idx)
                    .text(line);
            });
        }
        
        // 3.2 Add downstream item (right) - below the main line
        if (isFirstPair) {
            // First pair gets rectangle borders with deep blue background and white text
            // Calculate adaptive rectangle height based on text content
            const rightText = analogy.right || '';
            const rightMaxWidth = adaptiveMaxTextWidth; // Adaptive width based on available space
            const rightLineHeight = Math.round(parseFloat(THEME.analogyFontSize) * 1.2);
            
            // Check for preserved dimensions
            const rightNodeKey = `right-${i}`;
            const rightPreserved = nodeDimensions[rightNodeKey];
            
            // Use splitAndWrapText for automatic word wrapping
            const rightLines = (typeof window.splitAndWrapText === 'function')
                ? window.splitAndWrapText(rightText, parseFloat(THEME.analogyFontSize), rightMaxWidth, measureLineWidth)
                : (rightText ? [rightText] : ['']);
            
            // Ensure at least one line for placeholder
            const finalRightLines = rightLines.length > 0 ? rightLines : [''];
            
            // Calculate adaptive dimensions - use preserved dimensions if available for empty node
            let rightRectWidth, rightRectHeight;
            if (rightPreserved && rightPreserved.w && rightPreserved.h && rightText === '') {
                rightRectWidth = rightPreserved.w;
                rightRectHeight = rightPreserved.h;
                logger.debug('BridgeMapRenderer', 'Using preserved right rect dimensions', { i, rightRectWidth, rightRectHeight });
            } else {
                const rightTextWidth = Math.max(...finalRightLines.map(l => measureLineWidth(l, parseFloat(THEME.analogyFontSize))), 20);
                rightRectWidth = Math.max(60, rightTextWidth + 20); // Min 60px, add 20px padding
                rightRectHeight = Math.max(30, finalRightLines.length * rightLineHeight + 10); // Adaptive height
            }
            const rectHeight = rightRectHeight; // For backward compatibility with subsequent code
            
            // Store node reference
            bridgeMapNodes.push({
                id: i,
                nodeId: rightNodeId,
                type: 'right',
                x: rightX,
                y: rightY,
                width: rightRectWidth,
                height: rectHeight
            });
            
            // Draw rectangle background
            svg.append("rect")
                .attr("x", rightX - rightRectWidth/2)
                .attr("y", rightY - rectHeight/2)
                .attr("width", rightRectWidth)
                .attr("height", rectHeight)
                .attr("rx", 4)
                .attr("fill", "#1976d2") // Deep blue from mind map
                .attr("stroke", "#0d47a1")
                .attr("stroke-width", 2)
                .attr("data-node-id", rightNodeId)
                .attr("data-node-type", "right")
                .attr("data-pair-index", i)
                .attr("cursor", "pointer");
            
            // Render right analogy text - first pair (white) - use multiple text elements
            const rightStartY = rightY - (finalRightLines.length - 1) * rightLineHeight / 2;
            finalRightLines.forEach((line, idx) => {
                svg.append("text")
                    .attr("x", rightX)
                    .attr("y", rightStartY + idx * rightLineHeight)
                    .attr("text-anchor", "middle")
                    .attr("dominant-baseline", "middle")
                    .style("font-size", THEME.analogyFontSize)
                    .style("fill", "#ffffff") // White text
                    .style("font-weight", "bold")
                    .attr("data-text-for", `bridge-right-${i}`)
                    .attr("data-node-id", `bridge-right-${i}`)
                    .attr("data-node-type", "right")
                    .attr("data-pair-index", i)
                    .attr("cursor", "pointer")
                    .attr("data-line-index", idx)
                    .text(line);
            });
        } else {
            // Render right analogy text - regular pairs - use multiple text elements
            const regRightText = analogy.right || '';
            const regRightMaxWidth = adaptiveMaxTextWidth; // Adaptive width based on available space
            const regRightLineHeight = Math.round(parseFloat(THEME.analogyFontSize) * 1.2);
            
            // Use splitAndWrapText for automatic word wrapping
            const regRightLines = (typeof window.splitAndWrapText === 'function')
                ? window.splitAndWrapText(regRightText, parseFloat(THEME.analogyFontSize), regRightMaxWidth, measureLineWidth)
                : (regRightText ? [regRightText] : ['']);
            
            // Ensure at least one line for placeholder
            const finalRegRightLines = regRightLines.length > 0 ? regRightLines : [''];
            
            // WORKAROUND: Use multiple text elements instead of tspan
            const regRightStartY = rightY - (finalRegRightLines.length - 1) * regRightLineHeight / 2;
            finalRegRightLines.forEach((line, idx) => {
                svg.append("text")
                    .attr("x", rightX)
                    .attr("y", regRightStartY + idx * regRightLineHeight)
                    .attr("text-anchor", "middle")
                    .attr("dominant-baseline", "middle")
                    .style("font-size", THEME.analogyFontSize)
                    .style("fill", THEME.analogyTextColor)
                    .style("font-weight", "bold")
                    .attr("data-node-id", rightNodeId)
                    .attr("data-node-type", "right")
                    .attr("data-pair-index", i)
                    .attr("cursor", "pointer")
                    .attr("data-line-index", idx)
                    .text(line);
            });
        }
        
        // 3.3 Add vertical connection line (made invisible) - EXACTLY as in old renderer
        // These lines are for interaction purposes only and should never be visible
        // Use average X position for the line
        const lineX = (leftX + rightX) / 2;
        svg.append("line")
            .attr("x1", lineX)
            .attr("y1", leftY + 10) // Connect to upstream item
            .attr("x2", lineX)
            .attr("y2", rightY - 10) // Connect to downstream item
            .attr("stroke", "transparent") // Make vertical lines invisible
            .attr("stroke-width", 3) // Use attr instead of style
            .attr("class", "invisible-connection") // Mark as invisible connection
            .style("stroke", "transparent") // Also set via style to override line mode
            .style("opacity", "0"); // Ensure completely invisible
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
    
    // 4. Draw "as" separators (one less than analogy pairs) - at section boundaries
    for (let i = 0; i < spec.analogies.length - 1; i++) {
        // Position separator at section boundary (nodes are contained within their sections)
        const xPos = separatorPositions[i];
        
        // 4.1 Add little triangle separator on the main line - pointing UPWARD
        const triangleSize = 8; // Back to normal size
        const trianglePath = `M ${xPos - triangleSize} ${height/2} L ${xPos} ${height/2 - triangleSize} L ${xPos + triangleSize} ${height/2} Z`;
        
        svg.append("path")
            .attr("d", trianglePath)
            .attr("fill", "#666666") // Solid fill
            .attr("stroke", "#666666") // Solid stroke
            .attr("stroke-width", 2)
            .attr("class", "bridge-separator-triangle") // Mark as separator triangle
            .style("fill", "#666666") // Ensure solid fill via style
            .style("stroke", "#666666"); // Ensure solid stroke via style
        
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
    
    // Draw dotted separator line spanning actual content width (adaptive to diagram width)
    // The actual content spans from leftPadding to width - rightPadding (where the main line is drawn)
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
    
    // Store node references globally for drag operations
    window.bridgeMapNodes = bridgeMapNodes;
    
    // If we recalculated evenly (new pairs added), update custom positions silently
    // This ensures positions are saved for future renders without triggering re-render loop
    if (shouldRecalculateEvenly) {
        console.log('[BridgeMap-Renderer] 🔄 UPDATING CUSTOM POSITIONS - Recalculated evenly for', pairCount, 'pairs');
        if (!spec._customPositions) {
            spec._customPositions = {};
        }
        // Clear old custom positions for bridge pairs
        Object.keys(spec._customPositions).forEach(key => {
            if (key.startsWith('bridge-left-') || key.startsWith('bridge-right-')) {
                delete spec._customPositions[key];
            }
        });
        
        // Save all recalculated positions
        bridgeMapNodes.forEach(node => {
            spec._customPositions[node.nodeId] = { x: node.x, y: node.y };
        });
        
        logger.info('[BridgeMap-Renderer] Updated custom positions with evenly-spaced layout', {
            updatedPositions: bridgeMapNodes.length
        });
        console.log('[BridgeMap-Renderer] ✅ Custom positions updated:', Object.keys(spec._customPositions).filter(k => k.startsWith('bridge-')).sort());
    }
    
    // Clean up temporary SVG used for text measurement
    tempSvg.remove();
    
    // Watermark removed from canvas display - will be added during PNG export only
    
    
    // Apply learning sheet text knockout if needed
    if (spec.is_learning_sheet && spec.hidden_node_percentage > 0) {
        knockoutTextForLearningSheet(svg, spec.hidden_node_percentage);
    }
}

function renderMultiFlowMap(spec, theme = null, dimensions = null) {
    // Validate BEFORE clearing container - defensive programming
    // Use typeof check to allow empty string (for empty button functionality)
    if (!spec || typeof spec.event !== 'string' || !Array.isArray(spec.causes) || !Array.isArray(spec.effects)) {
        logger.error('FlowRenderer', 'Invalid spec for multi-flow map');
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

    // Measure single line width
    function measureLineWidth(text, fontSize) {
        const t = tempSvg.append('text')
            .attr('x', -9999)
            .attr('y', -9999)
            .attr('font-size', fontSize)
            .text(text || '');
        const w = t.node().getBBox().width;
        t.remove();
        return w;
    }
    
    // Measure text size with multi-line support
    function measureTextSize(text, fontSize) {
        // Split by newlines to handle multi-line text (Ctrl+Enter)
        const lines = (typeof window.splitTextLines === 'function') 
            ? window.splitTextLines(text || '') 
            : (text || '').split(/\n/);
        const lineHeight = Math.round(fontSize * 1.2);
        
        // Calculate max width across all lines
        let maxWidth = 0;
        lines.forEach(line => {
            const w = measureLineWidth(line, fontSize);
            if (w > maxWidth) maxWidth = w;
        });
        
        // Height is number of lines * line height
        const totalHeight = lines.length * lineHeight;
        
        return { 
            w: Math.ceil(maxWidth), 
            h: Math.ceil(totalHeight || fontSize),
            lines: lines,
            lineHeight: lineHeight
        };
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
            .attr('fill', color)
            .attr('stroke', color)
            .attr('stroke-width', '1')
            .attr('class', 'arrowhead-triangle');
    }
    
    // STEP 1: Measure all content to calculate optimal canvas dimensions
    
    // Check for preserved dimensions from empty button operation
    const nodeDimensions = spec._node_dimensions || {};
    
    // Measure central event size - check for preserved dimensions first
    let eventW, eventH;
    const eventPreservedDims = nodeDimensions['event'];
    if (eventPreservedDims && eventPreservedDims.w && eventPreservedDims.h && spec.event === '') {
        // Use preserved dimensions for empty event node
        eventW = eventPreservedDims.w;
        eventH = eventPreservedDims.h;
        logger.debug('MultiFlowMapRenderer', 'Using preserved event dimensions', { eventW, eventH });
    } else {
        const evSize = measureTextSize(spec.event, THEME.fontEvent);
        eventW = evSize.w + THEME.hPadEvent * 2;
        eventH = evSize.h + THEME.vPadEvent * 2;
    }
    
    // Measure causes and effects
    // CRITICAL: Maintain minimum dimensions for empty nodes to prevent shrinking
    // Also preserve dimensions if they were stored when node was emptied
    const minNodeWidth = 100;  // Minimum width for cause/effect nodes
    const minNodeHeight = 42;  // Minimum height for cause/effect nodes
    
    const causes = (spec.causes || []).map((text, idx) => {
        const nodeKey = `cause-${idx}`;
        const preservedDims = nodeDimensions[nodeKey];
        
        if (preservedDims && preservedDims.w && preservedDims.h) {
            // Use preserved dimensions for empty nodes
            return { text, w: preservedDims.w, h: preservedDims.h };
        }
        
        // Calculate dimensions based on text
        const s = measureTextSize(text, THEME.fontCause);
        // Ensure minimum dimensions even for empty text
        const w = Math.max(s.w + THEME.hPadNode * 2, minNodeWidth);
        const h = Math.max(s.h + THEME.vPadNode * 2, minNodeHeight);
        return { text, w, h };
    });
    const effects = (spec.effects || []).map((text, idx) => {
        const nodeKey = `effect-${idx}`;
        const preservedDims = nodeDimensions[nodeKey];
        
        if (preservedDims && preservedDims.w && preservedDims.h) {
            // Use preserved dimensions for empty nodes
            return { text, w: preservedDims.w, h: preservedDims.h };
        }
        
        // Calculate dimensions based on text
        const s = measureTextSize(text, THEME.fontEffect);
        // Ensure minimum dimensions even for empty text
        const w = Math.max(s.w + THEME.hPadNode * 2, minNodeWidth);
        const h = Math.max(s.h + THEME.vPadNode * 2, minNodeHeight);
        return { text, w, h };
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
        .attr('preserveAspectRatio', 'xMidYMid meet');
    
    // STEP 3: Calculate layout positions
    const centerX = fW / 2;
    const centerY = fH / 2;
    
    // Check for custom positions
    const customPositions = spec._customPositions || {};
    const hasCustomPositions = Object.keys(customPositions).length > 0;
    
    // Position side nodes with proper spacing
    // If custom positions exist but some nodes don't have positions (new nodes added),
    // recalculate all positions evenly to maintain proper spacing
    const causeCount = causes.length;
    const effectCount = effects.length;
    
    // Count how many causes have custom positions
    let causesWithCustomPositions = 0;
    if (hasCustomPositions) {
        for (let i = 0; i < causeCount; i++) {
            const nodeId = `multi-flow-cause-${i}`;
            if (customPositions.hasOwnProperty(nodeId) && customPositions[nodeId] !== null && customPositions[nodeId] !== undefined) {
                causesWithCustomPositions++;
            }
        }
    }
    
    // Count how many effects have custom positions
    let effectsWithCustomPositions = 0;
    if (hasCustomPositions) {
        for (let i = 0; i < effectCount; i++) {
            const nodeId = `multi-flow-effect-${i}`;
            if (customPositions.hasOwnProperty(nodeId) && customPositions[nodeId] !== null && customPositions[nodeId] !== undefined) {
                effectsWithCustomPositions++;
            }
        }
    }
    
    const hasNewCausesWithoutPositions = hasCustomPositions && causesWithCustomPositions < causeCount;
    const hasNewEffectsWithoutPositions = hasCustomPositions && effectsWithCustomPositions < effectCount;
    const shouldRecalculateCauses = hasNewCausesWithoutPositions;
    const shouldRecalculateEffects = hasNewEffectsWithoutPositions;
    
    logger.info('[MultiFlowMap-Renderer] Position detection check', {
        hasCustomPositions,
        causeCount,
        causesWithCustomPositions,
        effectCount,
        effectsWithCustomPositions,
        shouldRecalculateCauses,
        shouldRecalculateEffects
    });
    console.log('[MultiFlowMap-Renderer] 🔍 Position detection check:', {
        hasCustomPositions,
        causeCount,
        causesWithCustomPositions,
        effectCount,
        effectsWithCustomPositions,
        shouldRecalculateCauses,
        shouldRecalculateEffects
    });
    
    // Store node references globally for drag operations
    const multiFlowNodes = [];
    
    // Position side nodes with proper spacing
    const causeCX = sideMargin + maxCauseW / 2;
    const effectCX = finalWidth - sideMargin - maxEffectW / 2;

    // Position causes and effects vertically (or use custom positions)
    let cy = centerY - totalCauseH / 2;
    causes.forEach((n, idx) => {
        const nodeId = `multi-flow-cause-${idx}`;
        
        // Check if custom position exists and we're not recalculating
        if (hasCustomPositions && customPositions[nodeId] && !shouldRecalculateCauses) {
            n.cx = customPositions[nodeId].x;
            n.cy = customPositions[nodeId].y;
        } else {
            n.cx = causeCX;
            n.cy = cy + n.h / 2;
            cy += n.h + vSpacing;
        }
        
        // Store node reference
        multiFlowNodes.push({
            id: idx,
            nodeId: nodeId,
            type: 'cause',
            x: n.cx,
            y: n.cy,
            width: n.w,
            height: n.h
        });
    });
    
    let ey = centerY - totalEffectH / 2;
    effects.forEach((n, idx) => {
        const nodeId = `multi-flow-effect-${idx}`;
        
        // Check if custom position exists and we're not recalculating
        if (hasCustomPositions && customPositions[nodeId] && !shouldRecalculateEffects) {
            n.cx = customPositions[nodeId].x;
            n.cy = customPositions[nodeId].y;
        } else {
            n.cx = effectCX;
            n.cy = ey + n.h / 2;
            ey += n.h + vSpacing;
        }
        
        // Store node reference
        multiFlowNodes.push({
            id: idx,
            nodeId: nodeId,
            type: 'effect',
            x: n.cx,
            y: n.cy,
            width: n.w,
            height: n.h
        });
    });
    
    // Store node references globally for drag operations
    window.multiFlowMapNodes = multiFlowNodes;
    
    // If we recalculated evenly (new nodes added), update custom positions silently
    // This ensures positions are saved for future renders without triggering re-render loop
    if (shouldRecalculateCauses || shouldRecalculateEffects) {
        console.log('[MultiFlowMap-Renderer] 🔄 UPDATING CUSTOM POSITIONS - Recalculated evenly');
        if (!spec._customPositions) {
            spec._customPositions = {};
        }
        // Clear old custom positions for causes/effects
        Object.keys(spec._customPositions).forEach(key => {
            if (key.startsWith('multi-flow-cause-') || key.startsWith('multi-flow-effect-')) {
                delete spec._customPositions[key];
            }
        });
        
        // Save all recalculated positions
        multiFlowNodes.forEach(node => {
            spec._customPositions[node.nodeId] = { x: node.x, y: node.y };
        });
        
        logger.info('[MultiFlowMap-Renderer] Updated custom positions with evenly-spaced layout', {
            updatedPositions: multiFlowNodes.length
        });
        console.log('[MultiFlowMap-Renderer] ✅ Custom positions updated:', Object.keys(spec._customPositions).filter(k => k.startsWith('multi-flow-')).sort());
    }

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
        
        // Render cause text - use multiple text elements (tspan doesn't render)
        const causeLines = (typeof window.splitTextLines === 'function') 
            ? window.splitTextLines(n.text) 
            : (n.text || '').split(/\n/);
        const causeLineHeight = Math.round(THEME.fontCause * 1.2);
        
        // WORKAROUND: Use multiple text elements instead of tspan
        const causeStartY = n.cy - (causeLines.length - 1) * causeLineHeight / 2;
        causeLines.forEach((line, i) => {
            svg.append('text')
                .attr('x', n.cx)
                .attr('y', causeStartY + i * causeLineHeight)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', THEME.causeText)
                .attr('font-size', THEME.fontCause)
                .attr('data-node-id', `multi-flow-cause-${idx}`)
                .attr('data-node-type', 'cause')
                .attr('data-cause-index', idx)
                .attr('data-text-for', `multi-flow-cause-${idx}`)
                .attr('cursor', 'pointer')
                .attr('data-line-index', i)
                .text(line);
        });
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
        
        // Render effect text - use multiple text elements (tspan doesn't render)
        const effectLines = (typeof window.splitTextLines === 'function') 
            ? window.splitTextLines(n.text) 
            : (n.text || '').split(/\n/);
        const effectLineHeight = Math.round(THEME.fontEffect * 1.2);
        
        // WORKAROUND: Use multiple text elements instead of tspan
        const effectStartY = n.cy - (effectLines.length - 1) * effectLineHeight / 2;
        effectLines.forEach((line, i) => {
            svg.append('text')
                .attr('x', n.cx)
                .attr('y', effectStartY + i * effectLineHeight)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', THEME.effectText)
                .attr('font-size', THEME.fontEffect)
                .attr('data-node-id', `multi-flow-effect-${idx}`)
                .attr('data-node-type', 'effect')
                .attr('data-effect-index', idx)
                .attr('data-text-for', `multi-flow-effect-${idx}`)
                .attr('cursor', 'pointer')
                .attr('data-line-index', i)
                .text(line);
        });
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
    
    // Render event text - use multiple text elements (tspan doesn't render)
    const eventLines = (typeof window.splitTextLines === 'function') 
        ? window.splitTextLines(spec.event) 
        : (spec.event || '').split(/\n/);
    const eventLineHeight = Math.round(THEME.fontEvent * 1.2);
    
    // WORKAROUND: Use multiple text elements instead of tspan
    const eventStartY = centerY - (eventLines.length - 1) * eventLineHeight / 2;
    eventLines.forEach((line, i) => {
        svg.append('text')
            .attr('x', centerX)
            .attr('y', eventStartY + i * eventLineHeight)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.eventText)
            .attr('font-size', THEME.fontEvent)
            .attr('font-weight', 'bold')
            .attr('data-node-id', 'multi-flow-event')
            .attr('data-node-type', 'event')
            .attr('data-text-for', 'multi-flow-event')
            .attr('cursor', 'pointer')
            .attr('data-line-index', i)
            .text(line || '\u00A0');
    });
    
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
