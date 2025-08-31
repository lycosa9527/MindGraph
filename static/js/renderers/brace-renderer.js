/**
 * Brace Map Renderer for MindGraph
 * Renders hierarchical brace maps with professional styling
 * 
 * @version 2.4.0
 * @author MindGraph Team
 */

// CRITICAL DEBUG: Add comprehensive logging
console.log('🔍 Brace renderer: Module loading started');

// Verify MindGraphUtils availability
if (typeof window.MindGraphUtils === 'undefined') {
    console.warn('⚠️ Brace renderer: MindGraphUtils not found! Please load shared-utilities.js first.');
} else {
    console.log('✅ Brace renderer: MindGraphUtils found');
}

// getThemeDefaults is optional - create fallback if needed
if (window.MindGraphUtils && typeof window.MindGraphUtils.getThemeDefaults === 'function') {
    console.log('✅ Brace renderer: MindGraphUtils.getThemeDefaults available');
} else {
    console.log('⚠️ Brace renderer: Creating fallback getThemeDefaults');
    // Create a fallback function
    window.getThemeDefaults = () => ({});
}

console.log('🔍 Brace renderer: Module initialization completed');

function renderBraceMap(spec, theme = null, dimensions = null) {
    console.log('🚀 Brace renderer: renderBraceMap called with:', { spec, theme, dimensions });
    
    try {
        // CRITICAL FIX: Move function validation inside the render function to prevent race conditions
        // Verify required functions are available when actually needed
        console.log('🔍 Brace renderer: Checking required functions...');
        
        if (typeof window.getTextRadius !== 'function') {
            console.error('❌ Brace renderer: getTextRadius function not available globally');
            console.log('🔍 Available functions on window:', Object.keys(window).filter(k => k.includes('Text') || k.includes('Radius')));
            throw new Error('getTextRadius function not available globally');
        } else {
            console.log('✅ Brace renderer: getTextRadius function available');
        }

        if (typeof window.addWatermark !== 'function') {
            console.error('❌ Brace renderer: addWatermark function not available globally');
            console.log('🔍 Available functions on window:', Object.keys(window).filter(k => k.includes('Watermark') || k.includes('watermark')));
            throw new Error('addWatermark function not available globally');
        } else {
            console.log('✅ Brace renderer: addWatermark function available');
        }

        // Check D3 availability
        if (typeof d3 === 'undefined') {
            console.error('❌ Brace renderer: D3.js not available');
            throw new Error('D3.js not available');
        } else {
            console.log('✅ Brace renderer: D3.js available, version:', d3.version);
        }

        // Function called with spec, theme, and dimensions
        console.log('🔍 Brace renderer: Starting rendering process...');
    
    // Clear container and ensure it exists
    console.log('🔍 Brace renderer: Looking for d3-container...');
    const container = d3.select('#d3-container');
    if (container.empty()) {
        console.error('❌ Brace renderer: d3-container not found');
        console.log('🔍 Available elements with id:', document.querySelectorAll('[id]'));
        return;
    }
    console.log('✅ Brace renderer: d3-container found');
    container.html('');
    console.log('✅ Brace renderer: Container cleared');
    
    // Validate spec with comprehensive error handling
    console.log('🔍 Brace renderer: Validating spec...');
    
    if (!spec) {
        console.error('Brace renderer: Spec is null or undefined');
        d3.select('#d3-container').append('div').style('color', 'red').text('Error: No specification provided for brace map');
        return;
    }
    
    // Handle different spec structures - check if data is nested
    let actualSpec = spec;
    console.log('🔍 Brace renderer: Processing spec structure...');
    
    // Check for enhanced spec format (with agent data preserved)
    if (spec.topic && Array.isArray(spec.parts) && spec._agent_result) {
        console.log('✅ Brace renderer: Using enhanced spec format with agent data');
        actualSpec = spec; // Use the original spec directly
    }
    // Check if we have the original spec structure directly
    else if (spec.topic && Array.isArray(spec.parts)) {
        console.log('✅ Brace renderer: Using direct spec format');
        actualSpec = spec;
    }
    // Legacy format handling for backward compatibility
    else if (spec.success && spec.data) {
        console.log('✅ Brace renderer: Using legacy success.data format');
        actualSpec = spec.data;
    } else if (spec.success && spec.svg_data && spec.svg_data.elements) {
        console.log('✅ Brace renderer: Using legacy svg_data format');
        actualSpec = spec.svg_data;
    } else if (spec.success && spec.layout_data && spec.layout_data.nodes) {
        console.log('✅ Brace renderer: Using layout_data format, extracting spec...');
        // Extract the original spec from layout data if available
        actualSpec = {
            topic: spec.layout_data.nodes.find(n => n.node_type === 'topic')?.text || 'Topic',
            parts: spec.layout_data.nodes.filter(n => n.node_type === 'part').map(n => ({
                name: n.text,
                subparts: spec.layout_data.nodes.filter(sn => sn.node_type === 'subpart' && sn.part_index === n.part_index).map(sn => ({
                    name: sn.text
                }))
            }))
        };
        console.log('✅ Brace renderer: Extracted spec:', actualSpec);
    } else {
        console.warn('⚠️ Brace renderer: Unknown spec format:', spec);
    }
    
    // Using actual spec for rendering
    console.log('🔍 Brace renderer: Final spec to render:', actualSpec);
    
    if (!actualSpec.topic) {
        console.error('❌ Brace renderer: Spec missing topic:', actualSpec);
        d3.select('#d3-container').append('div').style('color', 'red').text('Error: Brace map specification missing topic');
        return;
    }
    
    if (!Array.isArray(actualSpec.parts)) {
        console.error('❌ Brace renderer: Spec parts is not an array:', actualSpec.parts);
        d3.select('#d3-container').append('div').style('color', 'red').text('Error: Brace map specification missing parts array');
        return;
    }
    
    // Spec validation passed, starting rendering
    console.log('✅ Brace renderer: Spec validation passed, starting rendering');
    
    // Use provided dimensions only - no hardcoded defaults
    const padding = dimensions?.padding || 40;
    console.log('🔍 Brace renderer: Using padding:', padding);
    
    // Load theme from style manager - FIXED: No more hardcoded overrides
    let THEME;
    try {
        if (typeof styleManager !== 'undefined' && styleManager.getTheme) {
            THEME = styleManager.getTheme('brace_map', theme, theme);
            console.log('Brace: Using centralized theme from style manager');
        } else {
            console.warn('Style manager not available, using minimal fallback');
            THEME = {
                topicFill: '#1976d2',
                topicText: '#ffffff',
                topicStroke: '#0d47a1',
                partFill: '#e3f2fd',
                partText: '#333333',
                partStroke: '#4e79a7',
                subpartFill: '#bbdefb',
                subpartText: '#333333',
                subpartStroke: '#90caf9',
                fontTopic: '24px Inter, Segoe UI, sans-serif',
                fontPart: '18px Inter, Segoe UI, sans-serif',
                fontSubpart: '14px Inter, Segoe UI, sans-serif',
                background: '#ffffff',
                braceColor: '#666666',
                braceWidth: 3
            };
        }
    } catch (error) {
        console.error('Error getting theme from style manager:', error);
        // Minimal emergency fallback only if style manager completely fails
        THEME = {
            topicFill: '#1976d2',
            topicText: '#ffffff',
            topicStroke: '#0d47a1',
            partFill: '#e3f2fd',
            partText: '#333333',
            partStroke: '#4e79a7',
            subpartFill: '#bbdefb',
            subpartText: '#333333',
            subpartStroke: '#90caf9',
            fontTopic: '24px Inter, Segoe UI, sans-serif',
            fontPart: '18px Inter, Segoe UI, sans-serif',
            fontSubpart: '14px Inter, Segoe UI, sans-serif',
            background: '#ffffff',
            braceColor: '#666666',
            braceWidth: 3
        };
    }
    
    // Apply background if specified
    if (theme && theme.background) {
        d3.select('#d3-container').style('background-color', theme.background);
    }
    
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
    const topicWidth = measureTextWidth(actualSpec.topic, THEME.fontTopic, 'bold');
    const partWidths = (actualSpec.parts || []).map(p => measureTextWidth(p?.name || '', THEME.fontPart, 'bold'));
    const maxPartWidth = Math.max(100, ...(partWidths.length ? partWidths : [0]));
    const subpartWidths = [];
    (actualSpec.parts || []).forEach(p => {
        (p.subparts || []).forEach(sp => {
            subpartWidths.push(measureTextWidth(sp?.name || '', THEME.fontSubpart));
        });
    });
    const maxSubpartWidth = Math.max(100, ...(subpartWidths.length ? subpartWidths : [0]));

    // Define spacing and dimensions
    const topicPadding = 16;
    const partPadding = 12;
    const subpartPadding = 8;
    const braceWidth = 3;
    const braceSpacing = 30;
    const columnSpacing = 45;
    
    // Calculate dimensions
    const topicBoxWidth = topicWidth + topicPadding * 2;
    const topicBoxHeight = parseFontSpec(THEME.fontTopic).size + topicPadding * 2;
    const partBoxHeight = parseFontSpec(THEME.fontPart).size + partPadding * 2;
    const subpartBoxHeight = parseFontSpec(THEME.fontSubpart).size + subpartPadding * 2;
    
    // Calculate total height needed
    let totalHeight = topicBoxHeight + 40; // Topic + spacing
    (actualSpec.parts || []).forEach(part => {
        totalHeight += partBoxHeight + 20; // Part height + spacing
        if (part.subparts && part.subparts.length > 0) {
            totalHeight += (part.subparts.length * (subpartBoxHeight + 10)) + 20; // Subparts + spacing
        }
    });
    totalHeight += 40; // Bottom padding
    
    // Calculate the actual content area (excluding top/bottom padding)
    const contentStartY = 30; // Parts start at this Y position
    const contentEndY = totalHeight - 40; // Bottom padding
    const contentCenterY = contentStartY + (contentEndY - contentStartY) / 2;
    
    // Calculate total width needed - FIXED: Ensure adequate width for all elements
    const topicSectionWidth = topicBoxWidth + 30; // Topic + padding
    const partsSectionWidth = maxPartWidth + 30; // Parts + padding
    const subpartsSectionWidth = maxSubpartWidth + 30; // Subparts + padding
    const totalWidth = Math.max(
        topicSectionWidth + columnSpacing + partsSectionWidth + columnSpacing + subpartsSectionWidth + 60, // Content width
        750 // Minimum width for readability
    );
    
    // Create SVG with calculated dimensions
    
    const svg = d3.select('#d3-container').append('svg')
        .attr('width', totalWidth)
        .attr('height', totalHeight)
        .attr('viewBox', `0 0 ${totalWidth} ${totalHeight}`)
        .attr('preserveAspectRatio', 'xMinYMin meet');
    
    // SVG created successfully

    // Add grey background - FIXED: Add background rectangle
    svg.append('rect')
        .attr('x', 0)
        .attr('y', 0)
        .attr('width', totalWidth)
        .attr('height', totalHeight)
        .attr('fill', THEME.background || '#f8f9fa')
        .attr('stroke', 'none');

    // Position topic in center-left, centered relative to actual content
    const topicX = 30;
    const topicY = contentCenterY;
    
    // Draw topic
    svg.append('rect')
        .attr('x', topicX)
        .attr('y', topicY - topicBoxHeight / 2)
        .attr('width', topicBoxWidth)
        .attr('height', topicBoxHeight)
        .attr('rx', 8)
        .attr('fill', THEME.topicFill)
        .attr('stroke', THEME.topicStroke)
        .attr('stroke-width', 2);
    
    svg.append('text')
        .attr('x', topicX + topicBoxWidth / 2)
        .attr('y', topicY)
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('fill', THEME.topicText)
        .attr('font-size', parseFontSpec(THEME.fontTopic).size)
        .attr('font-family', parseFontSpec(THEME.fontTopic).family)
        .attr('font-weight', 'bold')
        .text(actualSpec.topic);

    // Position parts to the right of topic - FIXED: Better positioning
    const partsStartX = topicX + topicBoxWidth + columnSpacing;
    const partsStartY = 30;
    let currentY = partsStartY;
    let partsEndY = currentY;

    (actualSpec.parts || []).forEach((part, partIndex) => {
        // Calculate the starting Y position for this part's section
        const partSectionStartY = currentY;
        
        // First, calculate the total height needed for this part's section (including subparts)
        let partSectionHeight = partBoxHeight + 20; // Part height + spacing
        
        if (part.subparts && part.subparts.length > 0) {
            partSectionHeight += (part.subparts.length * (subpartBoxHeight + 10)) + 20; // Subparts + spacing
        }
        
        // Calculate the center Y position for this part's entire section
        const partSectionCenterY = partSectionStartY + partSectionHeight / 2;
        
        // Position the part at the center of its section
        const partY = partSectionCenterY;
        const partBoxWidth = Math.max(maxPartWidth, measureTextWidth(part?.name || '', THEME.fontPart, 'bold')) + partPadding * 2;
        
        // Draw part
        svg.append('rect')
            .attr('x', partsStartX)
            .attr('y', partY - partBoxHeight / 2)
            .attr('width', partBoxWidth)
            .attr('height', partBoxHeight)
            .attr('rx', 5)
            .attr('fill', THEME.partFill)
            .attr('stroke', THEME.partStroke)
            .attr('stroke-width', 1);
        
        svg.append('text')
            .attr('x', partsStartX + partBoxWidth / 2)
            .attr('y', partY)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .attr('fill', THEME.partText)
            .attr('font-size', parseFontSpec(THEME.fontPart).size)
            .attr('font-family', parseFontSpec(THEME.fontPart).family)
            .attr('font-weight', 'bold')
            .text(part.name || '');

        // Move to next position for subparts
        currentY += partBoxHeight + 20;

        // Draw subparts if they exist
        if (part.subparts && part.subparts.length > 0) {
            const subpartsStartX = partsStartX + partBoxWidth + columnSpacing;
            const subpartsStartY = currentY;
            
            part.subparts.forEach((subpart, subpartIndex) => {
                const subpartY = currentY + subpartBoxHeight / 2;
                const subpartBoxWidth = Math.max(maxSubpartWidth, measureTextWidth(subpart?.name || '', THEME.fontSubpart)) + subpartPadding * 2;
                
                svg.append('rect')
                    .attr('x', subpartsStartX)
                    .attr('y', subpartY - subpartBoxHeight / 2)
                    .attr('width', subpartBoxWidth)
                    .attr('height', subpartBoxHeight)
                    .attr('rx', 3)
                    .attr('fill', THEME.subpartFill)
                    .attr('stroke', THEME.subpartStroke)
                    .attr('stroke-width', 1);
                
                svg.append('text')
                    .attr('x', subpartsStartX + subpartBoxWidth / 2)
                    .attr('y', subpartY)
                    .attr('text-anchor', 'middle')
                    .attr('dominant-baseline', 'middle')
                    .attr('fill', THEME.subpartText)
                    .attr('font-size', parseFontSpec(THEME.fontSubpart).size)
                    .attr('font-family', parseFontSpec(THEME.fontSubpart).family)
                    .text(subpart.name || '');

                currentY += subpartBoxHeight + 10;
            });

            // Draw small brace connecting part to subparts - FIXED: Better positioning
            const subpartsEndY = currentY - 10;
            if (subpartsEndY > subpartsStartY) {
                const braceX = partsStartX + partBoxWidth + (columnSpacing - braceSpacing) / 2;
                // Drawing small brace connecting part to subparts
                
                const bracePath = buildCurlyBracePath(
                    braceX,
                    subpartsStartY,
                    subpartsEndY,
                    braceSpacing / 2
                );
                
                svg.append('path')
                    .attr('d', bracePath)
                    .attr('fill', 'none')
                    .attr('stroke', THEME.braceColor || '#666666')
                    .attr('stroke-width', braceWidth / 2);
            }
        }
        
        currentY += 20; // Extra spacing between parts
        partsEndY = currentY - 20;
    });

    // Draw main brace connecting topic to parts - FIXED: Better positioning and visibility
    if (partsEndY > partsStartY) {
        const mainBraceX = topicX + topicBoxWidth + (columnSpacing - braceSpacing) / 2;
        // Drawing main brace connecting topic to parts
        
        const bracePath = buildCurlyBracePath(
            mainBraceX,
            partsStartY,
            partsEndY,
            braceSpacing / 2
        );
        
        svg.append('path')
            .attr('d', bracePath)
            .attr('fill', 'none')
            .attr('stroke', THEME.braceColor || '#666666')
            .attr('stroke-width', braceWidth);
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
    
    // Rendering completed successfully
    console.log('✅ Brace renderer: Rendering completed successfully');
    } catch (error) {
        console.error('❌ Brace renderer: Error during rendering:', error);
        console.error('❌ Brace renderer: Error stack:', error.stack);
        d3.select('#d3-container').append('div').style('color', 'red').text('Error: ' + error.message);
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
    console.log('✅ Brace renderer: Module loaded successfully in browser environment.');
} else if (typeof module !== 'undefined' && module.exports) {
    // Node.js environment
    module.exports = {
        renderBraceMap
    };
    console.log('✅ Brace renderer: Module loaded successfully in Node.js environment.');
} else {
    console.error('❌ Brace renderer: Module failed to load in any environment.');
}
