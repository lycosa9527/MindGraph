/**
 * Brace Map Renderer for MindGraph
 * Renders hierarchical brace maps with professional styling
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

// Verify MindGraphUtils availability
if (typeof window.MindGraphUtils === 'undefined') {
    logger.warn('BraceRenderer', 'MindGraphUtils not found! Please load shared-utilities.js first');
}

// getThemeDefaults is optional - create fallback if needed
if (!window.MindGraphUtils || typeof window.MindGraphUtils.getThemeDefaults !== 'function') {
    // Create a fallback function
    window.getThemeDefaults = () => ({});
}

function renderBraceMap(spec, theme = null, dimensions = null) {
    logger.debug('BraceRenderer', 'Rendering brace map');
    
    try {
        // Verify required functions are available when actually needed
        if (typeof window.getTextRadius !== 'function') {
            logger.error('BraceRenderer', 'getTextRadius function not available');
            throw new Error('getTextRadius function not available globally');
        }

        if (typeof window.addWatermark !== 'function') {
            logger.error('BraceRenderer', 'addWatermark function not available');
            throw new Error('addWatermark function not available globally');
        }

        // Check D3 availability
        if (typeof d3 === 'undefined') {
            logger.error('BraceRenderer', 'D3.js not available');
            throw new Error('D3.js not available');
        }
    
    // Validate BEFORE clearing container - defensive programming
    const container = d3.select('#d3-container');
    if (container.empty()) {
        logger.error('BraceRenderer', 'd3-container not found');
        return;
    }
    
    // Validate spec with comprehensive error handling
    if (!spec) {
        logger.error('BraceRenderer', 'Spec is null or undefined');
        return;
    }
    
    // Handle different spec structures - check if data is nested
    let actualSpec = spec;
    
    // Check for enhanced spec format (with agent data preserved)
    // Use typeof check to allow empty string (for empty button functionality)
    if (typeof spec.whole === 'string' && Array.isArray(spec.parts) && spec._agent_result) {
        actualSpec = spec; // Use the original spec directly
    }
    // Check if we have the original spec structure directly
    else if (typeof spec.whole === 'string' && Array.isArray(spec.parts)) {
        actualSpec = spec;
    }
    // Legacy format handling for backward compatibility
    else if (spec.success && spec.data) {
        actualSpec = spec.data;
    } else if (spec.success && spec.svg_data && spec.svg_data.elements) {
        actualSpec = spec.svg_data;
    } else if (spec.success && spec.layout_data && spec.layout_data.nodes) {
        // Extract the original spec from layout data if available
        actualSpec = {
            whole: spec.layout_data.nodes.find(n => n.node_type === 'topic')?.text || 'Main Topic',
            parts: spec.layout_data.nodes.filter(n => n.node_type === 'part').map(n => ({
                name: n.text,
                subparts: spec.layout_data.nodes.filter(sn => sn.node_type === 'subpart' && sn.part_index === n.part_index).map(sn => ({
                    name: sn.text
                }))
            }))
        };
    } else {
        logger.warn('BraceRenderer', 'Unknown spec format');
    }
    
    // Use typeof check to allow empty string (for empty button functionality)
    if (typeof actualSpec.whole !== 'string') {
        logger.error('BraceRenderer', 'Spec missing whole');
        return;
    }
    
    if (!Array.isArray(actualSpec.parts)) {
        logger.error('BraceRenderer', 'Spec parts is not an array');
        return;
    }
    
    // Validation passed, clear container and proceed with rendering
    container.html('');
    
    // Use provided adaptive dimensions - this ensures templates fit the window properly
    const padding = dimensions?.padding || 40;
    const adaptiveWidth = dimensions?.width;
    const adaptiveHeight = dimensions?.height;
    
    // Load theme from style manager
    let THEME;
    try {
        if (typeof styleManager !== 'undefined' && styleManager.getTheme) {
            THEME = styleManager.getTheme('brace_map', theme, theme);
        } else {
            logger.error('BraceRenderer', 'Style manager not available');
            throw new Error('Style manager not available for brace map rendering');
        }
    } catch (error) {
        logger.error('BraceRenderer', 'Error getting theme from style manager', error);
        throw new Error('Failed to load theme from style manager');
    }
    
    // Background is set directly on SVG, not on container
    // This ensures no white padding around the SVG
    
    // Helpers to measure text width using a temporary hidden SVG text node
    function parseFontSpec(fontSpec) {
        // Expect formats like "24px Inter, sans-serif"
        const match = typeof fontSpec === 'string' ? fontSpec.match(/^(\\d+)px\\s+(.+)$/) : null;
        if (match) {
            return { size: parseInt(match[1], 10), family: match[2] };
        }
        // Fallbacks
        return { size: 16, family: 'Inter, Segoe UI, sans-serif' };
    }
    
    function measureTextWidth(text, fontSpec, fontWeight = 'normal') {
        const { size, family } = parseFontSpec(fontSpec);
        // Create a temporary hidden SVG for measurement - use body instead of container
        const tempSvg = d3.select('body').append('svg')
            .attr('width', 0)
            .attr('height', 0)
            .style('position', 'absolute')
            .style('left', '-9999px')
            .style('top', '-9999px')
            .style('visibility', 'hidden');
        const tempText = tempSvg.append('text')
            .text(text || '')
            .attr('font-size', size)
            .attr('font-family', family)
            .style('font-weight', fontWeight);
        let width = 0;
        try {
            const bbox = tempText.node().getBBox();
            width = Math.max(0, bbox?.width || 0);
        } catch (error) {
            logger.error('BraceRenderer', 'Error getting bbox for text measurement:', error);
            // Fallback: estimate width based on character count
            width = (text || '').length * size * 0.6;
        }
        tempSvg.remove();
        return width;
    }

    function measureLineWidth(text, fontSpec, fontWeight = 'normal') {
        return measureTextWidth(text, fontSpec, fontWeight);
    }
    
    // Helper for splitAndWrapText compatibility (takes text, fontSize, returns width)
    function measureLineWidthForWrap(text, fontSize) {
        return measureTextWidth(text, fontSize, 'normal');
    }

    // Helper to build a curly brace path opening to the left
    // Based on HTML reference file kh4.html - sharp tip with decorative arcs
    function buildCurlyBracePath(braceX, yTop, yBottom, depth) {
        const height = Math.max(0, yBottom - yTop);
        if (height <= 0 || depth <= 0) {
            return {
                main: '',
                topArc: '',
                bottomArc: ''
            };
        }
        
        const yMid = (yTop + yBottom) / 2;
        
        // Tip parameters - matching kh4.html design (precise proportions based on height)
        const tipDepth = height * 0.05;      // Tip protrudes to the left (5% of height)
        const tipWidth = height * 0.01;      // Sharp tip width (1% of height for sharpness)
        const cornerArc = height * 0.005;    // Smooth transition at tip (0.5% of height)
        
        // Control points for upper half (from top to mid-point tip) - LEFT direction
        const cpTopX = braceX - cornerArc;
        const cpTopY = yMid - tipWidth;
        
        // Control points for lower half (from mid-point tip to bottom) - symmetric - LEFT direction
        const cpBottomX = braceX - cornerArc;
        const cpBottomY = yMid + tipWidth;
        
        const tipX = braceX - tipDepth;  // Tip vertex horizontal position (LEFT)
        
        // Main brace path with sharp mid-point tip - exactly like kh4.html
        const mainPath = `M ${braceX} ${yTop}
                         C ${cpTopX} ${yTop + (yMid - yTop - tipWidth)/2} ${cpTopX} ${cpTopY} ${tipX} ${yMid}
                         C ${cpBottomX} ${cpBottomY} ${cpBottomX} ${yMid + (yBottom - yMid - tipWidth)/2} ${braceX} ${yBottom}`;
        
        // Decorative arcs at top and bottom ends (only if height is sufficient)
        const arcRadius = height * 0.04;  // Arc radius 4% of height
        let topArcPath = '';
        let bottomArcPath = '';
        
        if (height > 50) {  // Only add arcs if brace is tall enough
            // Top arc - corrected position
            const upperCx = braceX + arcRadius;
            const upperStartX = upperCx - arcRadius;
            const upperEndX = upperCx;
            const upperEndY = yTop - arcRadius;
            topArcPath = `M ${upperStartX} ${yTop} A ${arcRadius} ${arcRadius} 0 0 1 ${upperEndX} ${upperEndY}`;
            
            // Bottom arc - corrected position
            const lowerCx = braceX + arcRadius;
            const lowerStartX = lowerCx - arcRadius;
            const lowerEndX = lowerCx;
            const lowerEndY = yBottom + arcRadius;
            bottomArcPath = `M ${lowerStartX} ${yBottom} A ${arcRadius} ${arcRadius} 0 0 0 ${lowerEndX} ${lowerEndY}`;
        }
        
        // Return object with all path components
        return {
            main: mainPath,
            topArc: topArcPath,
            bottomArc: bottomArcPath
        };
    }

    // Define spacing and dimensions
    const topicPadding = 16;
    const partPadding = 12;
    const subpartPadding = 8;
    const braceWidth = 3;
    const braceSpacing = 30;
    const columnSpacing = 38;  // Further reduced from 52 to 38 for tighter horizontal spacing
    
    // Font sizes
    const topicFontSize = parseFontSpec(THEME.fontTopic).size;
    const partFontSize = parseFontSpec(THEME.fontPart).size;
    const subpartFontSize = parseFontSpec(THEME.fontSubpart).size;
    
    // Check for preserved dimensions from empty button operation
    const nodeDimensions = actualSpec._node_dimensions || {};
    
    // Measure topic text (with line break support) - use preserved dimensions if available
    const topicText = actualSpec.whole || '';
    const topicLines = (typeof window.splitTextLines === 'function') 
        ? window.splitTextLines(topicText) 
        : (topicText || '').split(/\n/);
    const topicLineHeight = Math.round(topicFontSize * 1.2);
    
    let topicBoxWidth, topicBoxHeight;
    if (nodeDimensions.topic && nodeDimensions.topic.w && nodeDimensions.topic.h) {
        // Use preserved dimensions for empty node
        topicBoxWidth = nodeDimensions.topic.w;
        topicBoxHeight = nodeDimensions.topic.h;
        logger.debug('BraceRenderer', 'Using preserved topic dimensions', { topicBoxWidth, topicBoxHeight });
    } else {
        // Calculate from text
        const topicTextWidth = Math.max(...topicLines.map(line => measureLineWidth(line, THEME.fontTopic, 'bold')), 20);
        topicBoxWidth = topicTextWidth + topicPadding * 2;
        topicBoxHeight = topicLines.length * topicLineHeight + topicPadding * 2;
    }
    
    // Measure part texts (with line break support) - use preserved dimensions if available
    const partData = (actualSpec.parts || []).map((p, partIndex) => {
        const text = p?.name || '';
        const nodeKey = `part-${partIndex}`;
        const preservedDims = nodeDimensions[nodeKey];
        
        let boxWidth, boxHeight;
        if (preservedDims && preservedDims.w && preservedDims.h && text === '') {
            // Use preserved dimensions for empty node
            boxWidth = preservedDims.w;
            boxHeight = preservedDims.h;
            logger.debug('BraceRenderer', 'Using preserved part dimensions', { partIndex, boxWidth, boxHeight });
        } else {
            // Calculate from text
            const partLines = (typeof window.splitTextLines === 'function') 
                ? window.splitTextLines(text) 
                : (text || '').split(/\n/);
            const partLineHeight = Math.round(partFontSize * 1.2);
            const textWidth = Math.max(...partLines.map(line => measureLineWidth(line, THEME.fontPart, 'bold')), 20);
            boxWidth = textWidth + partPadding * 2;
            boxHeight = partLines.length * partLineHeight + partPadding * 2;
        }
        return { part: p, text, boxWidth, boxHeight };
    });
    const maxPartBoxWidth = Math.max(100, ...partData.map(p => p.boxWidth));
    
    // Measure subpart texts (with line break support) - use preserved dimensions if available
    const subpartData = [];
    (actualSpec.parts || []).forEach((p, partIndex) => {
        (p.subparts || []).forEach((sp, subpartIndex) => {
            const text = sp?.name || '';
            const nodeKey = `subpart-${partIndex}-${subpartIndex}`;
            const preservedDims = nodeDimensions[nodeKey];
            
            let boxWidth, boxHeight;
            if (preservedDims && preservedDims.w && preservedDims.h && text === '') {
                // Use preserved dimensions for empty node
                boxWidth = preservedDims.w;
                boxHeight = preservedDims.h;
                logger.debug('BraceRenderer', 'Using preserved subpart dimensions', { partIndex, subpartIndex, boxWidth, boxHeight });
            } else {
                // Calculate from text
                const subpartLines = (typeof window.splitTextLines === 'function') 
                    ? window.splitTextLines(text) 
                    : (text || '').split(/\n/);
                const subpartLineHeight = Math.round(subpartFontSize * 1.2);
                const textWidth = Math.max(...subpartLines.map(line => measureLineWidth(line, THEME.fontSubpart)), 20);
                boxWidth = textWidth + subpartPadding * 2;
                boxHeight = subpartLines.length * subpartLineHeight + subpartPadding * 2;
            }
            subpartData.push({ subpart: sp, text, boxWidth, boxHeight });
        });
    });
    const maxSubpartBoxWidth = Math.max(100, ...subpartData.map(sp => sp.boxWidth));
    
    // Calculate dimensions (using wrapped heights)
    const partBoxHeight = Math.max(...partData.map(p => p.boxHeight), partFontSize + partPadding * 2);
    const subpartBoxHeight = Math.max(...subpartData.map(sp => sp.boxHeight), subpartFontSize + subpartPadding * 2);
    
    // Calculate total height needed
    const topPadding = 42; // Reduced from 60 for tighter spacing
    let totalHeight = topPadding + topicBoxHeight; // Topic + top padding
    
    // Add space for dimension label if it exists (25px below topic box + font size + small padding)
    if ('dimension' in actualSpec) {
        totalHeight += 25 + 14 + 15; // 25px gap + 14px font + 15px padding before parts
    }
    
    // Calculate parts/subparts height - tightened spacing
    (actualSpec.parts || []).forEach(part => {
        totalHeight += partBoxHeight + 12; // Reduced from 20 for tighter spacing
        if (part.subparts && part.subparts.length > 0) {
            totalHeight += (part.subparts.length * (subpartBoxHeight + 7)) + 12; // Reduced spacing: 10->7, 20->12
        }
    });
    
    // Bottom padding - tighter spacing
    const hasAlternatives = actualSpec.alternative_dimensions && Array.isArray(actualSpec.alternative_dimensions) && actualSpec.alternative_dimensions.length > 0;
    if (hasAlternatives) {
        totalHeight += 70; // 15px gap + 55px for alternative dimensions content
    } else {
        totalHeight += 30; // Minimal bottom padding when no alternatives
    }
    
    // Use adaptive height if provided, otherwise use calculated content height
    const finalHeight = adaptiveHeight ? adaptiveHeight : totalHeight;
    
    // Calculate the actual content area (excluding top/bottom padding)
    const contentStartY = topPadding; // Parts start at this Y position
    const bottomPadding = hasAlternatives ? 70 : 30;  // Match the totalHeight calculation
    const contentEndY = totalHeight - bottomPadding;
    const contentCenterY = contentStartY + (contentEndY - contentStartY) / 2;
    
    // Calculate total width needed - use adaptive dimensions if provided
    const topicSectionWidth = topicBoxWidth + 20; // Reduced from 30 for tighter spacing
    const partsSectionWidth = maxPartBoxWidth + 20; // Reduced from 30 for tighter spacing
    const subpartsSectionWidth = maxSubpartBoxWidth + 20; // Reduced from 30 for tighter spacing
    const braceTipSpace = 70; // Reduced from 100 for tighter horizontal spacing
    const contentWidth = topicSectionWidth + columnSpacing + partsSectionWidth + columnSpacing + subpartsSectionWidth + braceTipSpace;
    
    // Use adaptive width if provided, otherwise use calculated content width
    const totalWidth = adaptiveWidth ? adaptiveWidth : Math.max(contentWidth, 900);
    
    // Create SVG with adaptive dimensions - fits window size properly
    const svg = d3.select('#d3-container').append('svg')
        .attr('width', totalWidth)
        .attr('height', finalHeight)
        .attr('viewBox', `0 0 ${totalWidth} ${finalHeight}`)
        .attr('preserveAspectRatio', 'xMidYMid meet')
        .style('display', 'block')
        .style('background-color', THEME.background || '#f8f9fa');

    // Position topic with adequate left margin to prevent dimension label cutoff
    const topicX = 35;  // Reduced from 50 for tighter horizontal spacing
    // Topic will be drawn AFTER brace center is calculated to ensure correct position

    // Position parts to the right of topic with spacing for brace - further tightened
    const partsStartX = topicX + topicBoxWidth + columnSpacing + 18;  // Reduced from 28 to move parts closer to brace
    const partsStartY = topPadding;  // Start at top padding (consistent with contentStartY)
    let currentY = partsStartY;
    
    // Track the rightmost content position for proper centering
    let maxContentRightX = topicX + topicBoxWidth;
    
    // Track the actual bottom position of rendered children
    let lastChildBottomY = partsStartY;
    
    // Store part center Y positions for brace boundary calculation
    const partCenterYs = [];

    (actualSpec.parts || []).forEach((part, partIndex) => {
        const partInfo = partData[partIndex];
        // Calculate the starting Y position for this part's section
        const partSectionStartY = currentY;
        
        // First, calculate the total height needed for this part's section (including subparts)
        let partSectionHeight = partInfo.boxHeight + 12; // Reduced from 20 for tighter spacing
        
        // Get subparts for this part
        const thisPartSubparts = subpartData.filter((sp, idx) => {
            let subpartIdx = 0;
            for (let i = 0; i < partIndex; i++) {
                subpartIdx += (actualSpec.parts[i].subparts || []).length;
            }
            return idx >= subpartIdx && idx < subpartIdx + (part.subparts || []).length;
        });
        
        if (thisPartSubparts.length > 0) {
            const subpartHeights = thisPartSubparts.map(sp => sp.boxHeight);
            const maxSubpartH = Math.max(...subpartHeights, subpartBoxHeight);
            partSectionHeight += (thisPartSubparts.length * (maxSubpartH + 7)) + 12; // Reduced spacing: 10->7, 20->12
        }
        
        // Calculate subparts range center for part positioning
        let subpartsRangeCenterY = partSectionStartY + partSectionHeight / 2; // Default to section center
        if (thisPartSubparts.length > 0) {
            const subpartsStartY = currentY + partInfo.boxHeight + 12;  // Reduced from 20 for tighter spacing
            const maxSubpartH = Math.max(...thisPartSubparts.map(sp => sp.boxHeight), subpartBoxHeight);
            const subpartsEndY = subpartsStartY + (thisPartSubparts.length * (maxSubpartH + 7)) - 7;  // Reduced from 10 for tighter spacing
            subpartsRangeCenterY = (subpartsStartY + subpartsEndY) / 2;
        }
        
        // Position the part at subparts range center
        const partY = subpartsRangeCenterY;
        const partBoxWidth = partInfo.boxWidth;
        
        // Track rightmost content
        maxContentRightX = Math.max(maxContentRightX, partsStartX + partBoxWidth);
        
        // Track the actual bottom edge of this part
        lastChildBottomY = Math.max(lastChildBottomY, partY + partBoxHeight / 2);
        
        // Store the part center Y for brace boundary calculation
        partCenterYs.push(partY);
        
        // Draw part
        svg.append('rect')
            .attr('x', partsStartX)
            .attr('y', partY - partBoxHeight / 2)
            .attr('width', partBoxWidth)
            .attr('height', partBoxHeight)
            .attr('rx', 5)
            .attr('fill', THEME.partFill)
            .attr('stroke', THEME.partStroke)
            .attr('stroke-width', 1)
            .attr('data-node-id', `brace-part-${partIndex}`)
            .attr('data-node-type', 'part')
            .attr('data-part-index', partIndex);
        
        // Render part text - use multiple text elements (tspan doesn't render)
        const partText = partInfo.text || '';
        const partMaxWidth = partBoxWidth * 0.9; // Max width based on box width
        const partLineHeight = Math.round(partFontSize * 1.2);
        
        // Use splitAndWrapText for automatic word wrapping
        const partLines = (typeof window.splitAndWrapText === 'function')
            ? window.splitAndWrapText(partText, partFontSize, partMaxWidth, measureLineWidthForWrap)
            : (partText ? [partText] : ['']);
        
        // Ensure at least one line for placeholder
        const finalPartLines = partLines.length > 0 ? partLines : [''];
        
        // WORKAROUND: Use multiple text elements instead of tspan
        const partStartY = partY - (finalPartLines.length - 1) * partLineHeight / 2;
        finalPartLines.forEach((line, i) => {
            svg.append('text')
                .attr('x', partsStartX + partBoxWidth / 2)
                .attr('y', partStartY + i * partLineHeight)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', THEME.partText)
                .attr('font-size', partFontSize)
                .attr('font-family', parseFontSpec(THEME.fontPart).family)
                .attr('font-weight', 'bold')
                .attr('data-node-id', `brace-part-${partIndex}`)
                .attr('data-node-type', 'part')
                .attr('data-part-index', partIndex)
                .attr('data-text-for', `part_${partIndex}`)
                .attr('data-line-index', i)
                .text(line);
        });

        // Move to next position for subparts
        currentY += partBoxHeight + 12;  // Reduced from 20 for tighter spacing

        // Draw subparts if they exist
        if (part.subparts && part.subparts.length > 0) {
            const subpartsStartX = partsStartX + partBoxWidth + columnSpacing;
            const subpartsStartY = currentY;
            
            // Get subpart data for this part
            let subpartDataIdx = 0;
            for (let i = 0; i < partIndex; i++) {
                subpartDataIdx += (actualSpec.parts[i].subparts || []).length;
            }
            
            part.subparts.forEach((subpart, subpartIndex) => {
                const subpartInfo = subpartData[subpartDataIdx + subpartIndex];
                const subpartY = currentY + subpartInfo.boxHeight / 2;
                const subpartBoxWidth = subpartInfo.boxWidth;
                
                // Track rightmost content
                maxContentRightX = Math.max(maxContentRightX, subpartsStartX + subpartBoxWidth);
                
                svg.append('rect')
                    .attr('x', subpartsStartX)
                    .attr('y', subpartY - subpartInfo.boxHeight / 2)
                    .attr('width', subpartBoxWidth)
                    .attr('height', subpartInfo.boxHeight)
                    .attr('rx', 3)
                    .attr('fill', THEME.subpartFill)
                    .attr('stroke', THEME.subpartStroke)
                    .attr('stroke-width', 1)
                    .attr('data-node-id', `brace-subpart-${partIndex}-${subpartIndex}`)
                    .attr('data-node-type', 'subpart')
                    .attr('data-part-index', partIndex)
                    .attr('data-subpart-index', subpartIndex);
                
                // Render subpart text - use multiple text elements (tspan doesn't render)
                const subpartText = subpartInfo.text || '';
                const subpartMaxWidth = subpartBoxWidth * 0.9; // Max width based on box width
                const subpartLineHeight = Math.round(subpartFontSize * 1.2);
                
                // Use splitAndWrapText for automatic word wrapping
                const subpartLines = (typeof window.splitAndWrapText === 'function')
                    ? window.splitAndWrapText(subpartText, subpartFontSize, subpartMaxWidth, measureLineWidthForWrap)
                    : (subpartText ? [subpartText] : ['']);
                
                // Ensure at least one line for placeholder
                const finalSubpartLines = subpartLines.length > 0 ? subpartLines : [''];
                
                // WORKAROUND: Use multiple text elements instead of tspan
                const subpartStartY = subpartY - (finalSubpartLines.length - 1) * subpartLineHeight / 2;
                finalSubpartLines.forEach((line, i) => {
                    svg.append('text')
                        .attr('x', subpartsStartX + subpartBoxWidth / 2)
                        .attr('y', subpartStartY + i * subpartLineHeight)
                        .attr('text-anchor', 'middle')
                        .attr('dominant-baseline', 'middle')
                        .attr('fill', THEME.subpartText)
                        .attr('font-size', subpartFontSize)
                        .attr('font-family', parseFontSpec(THEME.fontSubpart).family)
                        .attr('data-text-for', `subpart_${partIndex}_${subpartIndex}`)
                        .attr('data-node-id', `brace-subpart-${partIndex}-${subpartIndex}`)
                        .attr('data-node-type', 'subpart')
                        .attr('data-part-index', partIndex)
                        .attr('data-subpart-index', subpartIndex)
                        .attr('data-line-index', i)
                        .text(line);
                });

                currentY += subpartInfo.boxHeight + 7;  // Reduced from 10 for tighter spacing
                
                // Track the actual bottom edge of this subpart
                lastChildBottomY = Math.max(lastChildBottomY, subpartY + subpartInfo.boxHeight / 2);
            });

            // Draw small brace connecting part to subparts - with safety gap check
            const subpartsEndY = currentY - 10;
            if (subpartsEndY > subpartsStartY) {
                // Calculate safe brace position to avoid overlap
                const partRight = partsStartX + partBoxWidth;
                const subpartsLeft = subpartsStartX;
                const safetyGap = 9;  // Reduced from 12 to move small brace closer to parts and subparts
                
                // Calculate small brace boundaries based on subpart centers
                const subpartCenterYs = [];
                part.subparts.forEach((subpart, subpartIndex) => {
                    const subpartY = subpartsStartY + (subpartIndex + 0.5) * (subpartBoxHeight + 10);
                    subpartCenterYs.push(subpartY);
                });
                
                // Apply same logic as main brace: calculate true height and arc radius
                const totalSubpartRangeA = Math.max(...subpartCenterYs) - Math.min(...subpartCenterYs);
                const trueSmallBraceHeightB = totalSubpartRangeA / 1.08;  // Remove arc radius contribution
                const sArcRadius = trueSmallBraceHeightB * 0.04;     // Arc radius based on true height
                const sTipDepth = trueSmallBraceHeightB * 0.05;      // Tip depth based on true height
                
                // Calculate boundaries: subpart centers ± arc radius (arcs extend inward)
                const smallBraceStartY = Math.min(...subpartCenterYs) + sArcRadius;  // Include top arc (inward)
                const smallBraceEndY = Math.max(...subpartCenterYs) - sArcRadius;    // Include bottom arc (inward)
                const smallBraceHeight = smallBraceEndY - smallBraceStartY;
                
                // CRITICAL: Calculate safe positioning
                // 1. Tip (braceX - tipDepth) doesn't overlap part
                // 2. Right edge (braceX + arcRadius) doesn't overlap subparts
                
                const minBraceX = partRight + safetyGap + sTipDepth;
                const maxBraceX = subpartsLeft - safetyGap - sArcRadius;
                
                // Position brace closer to both parts and subparts (slightly toward center but tighter)
                const braceX = minBraceX + (maxBraceX - minBraceX) * 0.2;  // Reduced from 0.5 (middle) to 0.2 to move closer to nodes
                
                // Calculate safe depth - reduced for tighter horizontal spacing
                const availableSpace = subpartsLeft - partRight - (safetyGap * 2) - sTipDepth - sArcRadius;
                const braceDepth = Math.max(6, Math.min(availableSpace * 0.25, 24));  // Reduced from 0.3 to 0.25 and max from 30 to 24
                
                const bracePaths = buildCurlyBracePath(
                    braceX,
                    smallBraceStartY,
                    smallBraceEndY,
                    braceDepth
                );
                
                // Draw main brace path
                if (bracePaths.main) {
                    svg.append('path')
                        .attr('d', bracePaths.main)
                        .attr('fill', 'none')
                        .attr('stroke', THEME.braceColor || '#666666')
                        .attr('stroke-width', braceWidth / 2)
                        .attr('stroke-linecap', 'round')
                        .attr('stroke-linejoin', 'round');
                }
                
                // Draw top arc (if exists)
                if (bracePaths.topArc) {
                    svg.append('path')
                        .attr('d', bracePaths.topArc)
                        .attr('fill', 'none')
                        .attr('stroke', THEME.braceColor || '#666666')
                        .attr('stroke-width', braceWidth / 2)
                        .attr('stroke-linecap', 'round')
                        .attr('stroke-linejoin', 'round');
                }
                
                // Draw bottom arc (if exists)
                if (bracePaths.bottomArc) {
                svg.append('path')
                        .attr('d', bracePaths.bottomArc)
                    .attr('fill', 'none')
                    .attr('stroke', THEME.braceColor || '#666666')
                        .attr('stroke-width', braceWidth / 2)
                        .attr('stroke-linecap', 'round')
                        .attr('stroke-linejoin', 'round');
                }
            }
        }
        
        currentY += 12; // Reduced from 20 for tighter spacing between parts
    });

    // Calculate brace boundaries based on first and last part centers
    let braceStartY, braceEndY;
    if (partCenterYs.length > 0) {
        // Current calculation gives us total range (A) = true brace height (B) + 2 * arc radius
        // We need to solve: A = B + 2 * (B * 0.04) = B + 0.08 * B = B * (1 + 0.08) = B * 1.08
        // So: B = A / 1.08
        const totalRangeA = Math.max(...partCenterYs) - Math.min(...partCenterYs);
        const trueBraceHeightB = totalRangeA / 1.08;  // Remove arc radius contribution
        const arcRadius = trueBraceHeightB * 0.04;     // Arc radius based on true height
        
        // Calculate boundaries: part centers ± arc radius (arcs extend inward)
        braceStartY = Math.min(...partCenterYs) + arcRadius;  // Include top arc (inward)
        braceEndY = Math.max(...partCenterYs) - arcRadius;    // Include bottom arc (inward)
    } else {
        // Fallback if no parts
        braceStartY = partsStartY;
        braceEndY = partsStartY;
    }

    // Draw main brace connecting topic to parts - with safety gap check
    if (braceEndY > braceStartY) {
        // Calculate safe brace position to avoid overlap
        const topicRight = topicX + topicBoxWidth;
        const partsLeft = partsStartX;
        const safetyGap = 10;  // Reduced from 14 to move brace closer to nodes on both sides
        
        // Calculate main brace height and tip depth based on corrected boundaries
        const mainBraceHeight = braceEndY - braceStartY;
        const tipDepth = mainBraceHeight * 0.05;  // Tip extends LEFT by 5% of height
        const arcRadius = mainBraceHeight * 0.04;  // Arc radius is 4% of height
        
        // CRITICAL: Position brace to the RIGHT of topic text box
        // Brace should be positioned after topic with sufficient gap
        // The brace's leftmost point (braceX - tipDepth) should be after topic's right edge
        const minBraceX = topicRight + safetyGap + tipDepth;  // Minimum X to avoid overlap with topic
        
        // Calculate maximum X position (before parts start)
        const maxBraceX = partsLeft - safetyGap - arcRadius;  // Maximum X to avoid overlap with parts
        
        // Position brace closer to both topic and parts
        let mainBraceX;
        if (minBraceX >= maxBraceX) {
            // Not enough space - position as close to topic as possible
            mainBraceX = topicRight + safetyGap + tipDepth + 3;  // Reduced from 6px to move brace closer to topic
        } else {
            // Position brace closer to center (equidistant from both sides) for tighter spacing
            mainBraceX = minBraceX + (maxBraceX - minBraceX) * 0.15;  // Reduced from 25% to 15% to move brace closer to both nodes
        }
        
        // CRITICAL: Brace boundaries align with first and last part centers
        // braceStartY and braceEndY are already calculated above based on part centers
        const braceCenterY = (braceStartY + braceEndY) / 2; // Center between first and last part centers
        
        // CRITICAL: Adjust topic position to align with brace tip (left tip horizontal line)
        // The brace tip is at the vertical center of the brace, which is braceCenterY
        // Topic center line should align with braceCenterY
        topicY = braceCenterY;  // Topic center line = brace center line
        topicCenterY = braceCenterY;
        
        // RENDERING ORDER: Draw brace paths FIRST (underneath), then topic node on top
        // Calculate safe depth - reduced for tighter horizontal spacing
        const availableSpace = partsLeft - topicRight - (safetyGap * 2) - tipDepth - arcRadius;
        const braceDepth = Math.max(8, Math.min(availableSpace * 0.25, 32));  // Reduced from 0.3 to 0.25 and max from 40 to 32
        
        const bracePaths = buildCurlyBracePath(
            mainBraceX,
            braceStartY,
            braceEndY,
            braceDepth
        );
        
        // Draw main brace path (FIRST for proper z-order)
        if (bracePaths.main) {
            svg.append('path')
                .attr('d', bracePaths.main)
                .attr('fill', 'none')
                .attr('stroke', THEME.braceColor || '#666666')
                .attr('stroke-width', braceWidth)
                .attr('stroke-linecap', 'round')
                .attr('stroke-linejoin', 'round');
        }
        
        // Draw top arc (if exists)
        if (bracePaths.topArc) {
            svg.append('path')
                .attr('d', bracePaths.topArc)
                .attr('fill', 'none')
                .attr('stroke', THEME.braceColor || '#666666')
                .attr('stroke-width', braceWidth)
                .attr('stroke-linecap', 'round')
                .attr('stroke-linejoin', 'round');
        }
        
        // Draw bottom arc (if exists)
        if (bracePaths.bottomArc) {
            svg.append('path')
                .attr('d', bracePaths.bottomArc)
                .attr('fill', 'none')
                .attr('stroke', THEME.braceColor || '#666666')
                .attr('stroke-width', braceWidth)
                .attr('stroke-linecap', 'round')
                .attr('stroke-linejoin', 'round');
        }
        
        // CRITICAL: Draw topic NOW with correct position (AFTER braces for proper z-order)
        const topicRect = svg.append('rect')
            .attr('x', topicX)
            .attr('y', topicY - topicBoxHeight / 2)  // Rectangle top = center - height/2
            .attr('width', topicBoxWidth)
            .attr('height', topicBoxHeight)
            .attr('rx', 8)
            .attr('fill', THEME.topicFill)
            .attr('stroke', THEME.topicStroke)
            .attr('stroke-width', 2)
            .attr('data-node-id', 'topic_center')
            .attr('data-node-type', 'topic');
        
        // Render topic text - use multiple text elements (tspan doesn't render)
        const topicMaxWidth = topicBoxWidth * 0.9; // Max width based on box width
        const topicLineHeight = Math.round(topicFontSize * 1.2);
        
        // Use splitAndWrapText for automatic word wrapping
        const topicLines = (typeof window.splitAndWrapText === 'function')
            ? window.splitAndWrapText(topicText, topicFontSize, topicMaxWidth, measureLineWidthForWrap)
            : (topicText ? [topicText] : ['']);
        
        // Ensure at least one line for placeholder
        const finalTopicLines = topicLines.length > 0 ? topicLines : [''];
        
        // WORKAROUND: Use multiple text elements instead of tspan
        const topicStartY = topicY - (finalTopicLines.length - 1) * topicLineHeight / 2;
        finalTopicLines.forEach((line, i) => {
            svg.append('text')
                .attr('x', topicX + topicBoxWidth / 2)
                .attr('y', topicStartY + i * topicLineHeight)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', THEME.topicText)
                .attr('font-size', topicFontSize)
                .attr('font-family', parseFontSpec(THEME.fontTopic).family)
                .attr('font-weight', 'bold')
                .attr('data-text-for', 'topic_center')
                .attr('data-node-id', 'topic_center')
                .attr('data-node-type', 'topic')
                .attr('data-line-index', i)
                .text(line);
        });
        
        // ALWAYS show dimension field (even if empty) so users can edit it
        // Only show if dimension field exists in spec (even if empty string)
        if ('dimension' in actualSpec) {
            const dimensionY = topicY + topicBoxHeight / 2 + 25;  // 25px below topic box
            const dimensionFontSize = 14;
            
            let dimensionText;
            let textOpacity;
            
            if (actualSpec.dimension && actualSpec.dimension.trim() !== '') {
                // Dimension has value - show it with label
                const hasChinese = /[\u4e00-\u9fa5]/.test(actualSpec.dimension);
                const dimensionLabel = hasChinese ? '拆解维度' : 'Decomposition by';
                dimensionText = `[${dimensionLabel}: ${actualSpec.dimension}]`;
                textOpacity = 0.8;
            } else {
                // Dimension is empty - show placeholder
                // Detect language from whole to show appropriate placeholder
                const hasChinese = /[\u4e00-\u9fa5]/.test(actualSpec.whole);
                dimensionText = hasChinese ? '[拆解维度: 点击填写...]' : '[Decomposition by: click to specify...]';
                textOpacity = 0.4;  // Lower opacity for placeholder
            }
            
            // Make dimension text EDITABLE - users can click to change/fill decomposition standard
            svg.append('text')
                .attr('x', topicX + topicBoxWidth / 2)
                .attr('y', dimensionY)
                .attr('text-anchor', 'middle')
                .attr('dominant-baseline', 'middle')
                .attr('fill', THEME.dimensionLabelColor || '#1976d2')  // Dark blue for classroom visibility
                .attr('font-size', dimensionFontSize)
                .attr('font-family', parseFontSpec(THEME.fontSubpart).family)
                .attr('font-style', 'italic')
                .style('opacity', textOpacity)
                .style('cursor', 'pointer')  // Show it's clickable
                .attr('data-node-id', 'dimension_label')  // Make it editable
                .attr('data-node-type', 'dimension')  // Identify as dimension node
                .attr('data-dimension-value', actualSpec.dimension || '')  // Store actual dimension value (or empty)
                .text(dimensionText);
        }
    }

    // Add alternative dimensions at the bottom (if alternative_dimensions field exists)
    if (actualSpec.alternative_dimensions && Array.isArray(actualSpec.alternative_dimensions) && actualSpec.alternative_dimensions.length > 0) {
        // Position exactly 15px below the last child node (using actual rendered position)
        const separatorY = lastChildBottomY + 15;  // Separator line 15px below the bottom edge of last child
        const alternativesY = separatorY + 20;  // Label 20px below separator
        const fontSize = 13;
        
        // Detect language from first alternative dimension (if contains Chinese characters, use Chinese)
        const hasChinese = /[\u4e00-\u9fa5]/.test(actualSpec.alternative_dimensions[0]);
        const alternativeLabel = hasChinese ? '本主题的其他可能拆解维度：' : 'Other possible dimensions for this topic:';
        
        // Calculate center of actual content (not canvas) for proper alignment
        const contentCenterX = (topicX + maxContentRightX) / 2;
        
        // Draw separator line spanning the actual content width (adaptive to diagram width)
        // Use actual content bounds: from topicX (left edge) to maxContentRightX (right edge)
        const separatorLeftX = topicX;
        const separatorRightX = maxContentRightX;
        
        svg.append('line')
            .attr('x1', separatorLeftX)
            .attr('y1', separatorY)
            .attr('x2', separatorRightX)
            .attr('y2', separatorY)
            .attr('stroke', THEME.dimensionLabelColor || '#1976d2')  // Dark blue for classroom visibility
            .attr('stroke-width', 1)
            .attr('stroke-dasharray', '4,4')
            .style('opacity', 0.4);
        
        // Add label centered on content (not canvas)
        svg.append('text')
            .attr('x', contentCenterX)
            .attr('y', alternativesY - 5)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.dimensionLabelColor || '#1976d2')  // Dark blue for classroom visibility
            .attr('font-size', fontSize)
            .attr('font-family', parseFontSpec(THEME.fontSubpart).family)
            .style('opacity', 0.7)
            .text(alternativeLabel);
        
        // Add dimension chips/badges centered on content
        const dimensionChips = actualSpec.alternative_dimensions.map(d => `• ${d}`).join('  ');
        svg.append('text')
            .attr('x', contentCenterX)
            .attr('y', alternativesY + 18)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.dimensionLabelColor || '#1976d2')  // Dark blue for classroom visibility
            .attr('font-size', fontSize - 1)
            .attr('font-family', parseFontSpec(THEME.fontSubpart).family)
            .attr('font-weight', '600')
            .style('opacity', 0.8)
            .text(dimensionChips);
    }
    
    // Apply learning sheet text knockout if needed
    if (spec.is_learning_sheet && spec.hidden_node_percentage > 0) {
        knockoutTextForLearningSheet(svg, spec.hidden_node_percentage);
    }
    
    // Recalculate viewBox to tightly fit actual content and center it
    recalculateTightViewBoxBrace(svg, 40);
    
    } catch (error) {
        logger.error('BraceRenderer', 'Error during rendering', error);

    }
}

/**
 * Recalculate SVG viewBox to tightly fit actual content bounds.
 * Eliminates excessive white padding and ensures proper centering with xMidYMid meet.
 * 
 * @param {d3.Selection} svg - D3 selection of the SVG element
 * @param {number} padding - Desired padding around content (default: 40)
 */
function recalculateTightViewBoxBrace(svg, padding = 40) {
    try {
        const svgNode = svg.node();
        if (!svgNode) {
            logger.warn('BraceRenderer', 'SVG node not found for viewBox recalculation');
            return;
        }
        
        // Get bounding box of all rendered content
        const bbox = svgNode.getBBox();
        
        if (bbox.width <= 0 || bbox.height <= 0) {
            logger.warn('BraceRenderer', 'Invalid content bounds, skipping viewBox recalculation');
            return;
        }
        
        // Calculate new viewBox with padding on all sides
        const newX = bbox.x - padding;
        const newY = bbox.y - padding;
        const newWidth = bbox.width + (padding * 2);
        const newHeight = bbox.height + (padding * 2);
        
        // Update viewBox to tightly fit content - xMidYMid meet will center it
        svg.attr('viewBox', `${newX} ${newY} ${newWidth} ${newHeight}`)
           .attr('preserveAspectRatio', 'xMidYMid meet');
        
        logger.debug('BraceRenderer', 'ViewBox recalculated for proper centering:', {
            viewBox: `${Math.round(newX)} ${Math.round(newY)} ${Math.round(newWidth)} ${Math.round(newHeight)}`
        });
        
    } catch (error) {
        logger.error('BraceRenderer', 'Error recalculating viewBox:', error);
    }
}

// Export functions for module system
if (typeof window !== 'undefined') {
    // Browser environment - attach to window
    window.BraceRenderer = {
        renderBraceMap
    };
    
    // CRITICAL FIX: Also expose renderBraceMap globally for backward compatibility
    // This prevents the "renderBraceMap is not defined" error
    if (typeof window.renderBraceMap === 'undefined') {
        window.renderBraceMap = renderBraceMap;
        // renderBraceMap exported globally for backward compatibility
    }
    
    // BraceRenderer exported to window.BraceRenderer
} else if (typeof module !== 'undefined' && module.exports) {
    // Node.js environment
    module.exports = {
        renderBraceMap
    };
}
