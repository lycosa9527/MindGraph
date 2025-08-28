/**
 * Shared D3 Utilities for MindGraph Renderers
 * 
 * This module contains common utility functions used across all graph type renderers.
 * By extracting these shared utilities, we eliminate code duplication and reduce
 * the size of individual renderer modules.
 * 
 * Performance Impact: ~15-20KB reduction per renderer module
 */

// CRITICAL DEBUG: Add comprehensive logging
console.log('🔍 Shared utilities: Module loading started');

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

function cleanupMeasurementContainer() {
    if (measurementContainer) {
        measurementContainer.remove();
        measurementContainer = null;
    }
}

// --- Watermark utilities ---
function getWatermarkText(theme = null) {
    return theme?.watermark?.text || 'MindGraph';
}

function addWatermark(svg, theme = null) {
    const watermarkText = getWatermarkText(theme);
    const watermarkConfig = theme?.watermark || {};
    
    // Default watermark configuration - EXACTLY as in original d3-renderers.js
    const config = {
        text: watermarkText,
        fontSize: watermarkConfig.fontSize || '12px',
        fill: watermarkConfig.fill || '#2c3e50', // Changed to match original: dark blue-grey
        opacity: watermarkConfig.opacity || 0.8, // Changed to match original: 80% opacity
        position: watermarkConfig.position || 'bottom-right',
        padding: watermarkConfig.padding || 10
    };
    
    // Get SVG dimensions from the SVG element itself, not from content bbox
    const svgNode = svg.node();
    const svgWidth = svgNode.getAttribute('width') || svgNode.getAttribute('viewBox')?.split(' ')[2] || 800;
    const svgHeight = svgNode.getAttribute('height') || svgNode.getAttribute('viewBox')?.split(' ')[3] || 600;
    
    // Parse dimensions if they're strings
    const width = parseFloat(svgWidth);
    const height = parseFloat(svgHeight);
    
    // Calculate position based on configuration
    let x, y, textAnchor;
    
    switch (config.position) {
        case 'top-left':
            x = config.padding;
            y = config.padding + 12;
            textAnchor = 'start';
            break;
        case 'top-right':
            x = width - config.padding;
            y = config.padding + 12;
            textAnchor = 'end';
            break;
        case 'bottom-left':
            x = config.padding;
            y = height - config.padding;
            textAnchor = 'start';
            break;
        case 'bottom-right':
        default:
            x = width - config.padding;
            y = height - config.padding;
            textAnchor = 'end';
            break;
    }
    
    // Add watermark text - EXACTLY as in original d3-renderers.js
    svg.append('text')
        .attr('x', x)
        .attr('y', y)
        .attr('text-anchor', textAnchor)
        .attr('dominant-baseline', 'alphabetic') // Added to match original
        .attr('font-size', config.fontSize)
        .attr('font-family', 'Inter, Segoe UI, sans-serif') // Changed back to Inter
        .attr('font-weight', '500') // Changed to match original
        .attr('fill', config.fill)
        .attr('opacity', config.opacity)
        .attr('pointer-events', 'none') // Changed from style to attr to match original
        .text(config.text);
}

// --- Common color and styling utilities ---
function getColorScale(theme, itemCount) {
    const colors = theme?.colors || ['#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#34495e'];
    return d3.scaleOrdinal()
        .domain(d3.range(itemCount))
        .range(colors);
}

function getThemeDefaults(theme = null) {
    return {
        backgroundColor: theme?.backgroundColor || '#ffffff',
        textColor: theme?.textColor || '#333333',
        fontSize: theme?.fontSize || '14px',
        fontFamily: theme?.fontFamily || 'Arial, sans-serif',
        strokeColor: theme?.strokeColor || '#cccccc',
        strokeWidth: theme?.strokeWidth || 1,
        ...theme
    };
}

// --- Common SVG setup utilities ---
function createSVG(containerId, dimensions) {
    const container = d3.select(`#${containerId}`);
    container.selectAll('*').remove(); // Clean previous content
    
    const svg = container
        .append('svg')
        .attr('width', dimensions.width)
        .attr('height', dimensions.height)
        .style('background-color', 'transparent');
        
    return svg;
}

function centerContent(svg, contentGroup, dimensions) {
    try {
        const bbox = contentGroup.node().getBBox();
        const centerX = dimensions.width / 2;
        const centerY = dimensions.height / 2;
        const contentCenterX = bbox.x + bbox.width / 2;
        const contentCenterY = bbox.y + bbox.height / 2;
        
        const translateX = centerX - contentCenterX;
        const translateY = centerY - contentCenterY;
        
        contentGroup.attr('transform', `translate(${translateX}, ${translateY})`);
    } catch (error) {
        console.warn('Could not center content:', error);
    }
}

// --- Text wrapping utilities ---
function wrapText(text, width) {
    text.each(function() {
        const textElement = d3.select(this);
        const words = textElement.text().split(/\s+/).reverse();
        let word;
        let line = [];
        let lineNumber = 0;
        const lineHeight = 1.1; // ems
        const y = textElement.attr("y");
        const dy = parseFloat(textElement.attr("dy")) || 0;
        
        let tspan = textElement.text(null).append("tspan")
            .attr("x", 0)
            .attr("y", y)
            .attr("dy", dy + "em");
            
        while (word = words.pop()) {
            line.push(word);
            tspan.text(line.join(" "));
            if (tspan.node().getComputedTextLength() > width) {
                line.pop();
                tspan.text(line.join(" "));
                line = [word];
                tspan = textElement.append("tspan")
                    .attr("x", 0)
                    .attr("y", y)
                    .attr("dy", ++lineNumber * lineHeight + dy + "em")
                    .text(word);
            }
        }
    });
}

// Note: renderGraph function has been moved to renderer-dispatcher.js
// to avoid dependency issues with individual renderer modules

// --- Export utilities for module system ---
if (typeof window !== 'undefined') {
    // Browser environment - attach to window
    window.MindGraphUtils = {
        getMeasurementContainer,
        getTextRadius,
        cleanupMeasurementContainer,
        getWatermarkText,
        addWatermark,
        getColorScale,
        getThemeDefaults,
        createSVG,
        centerContent,
        wrapText
    };
    
    // CRITICAL FIX: Also expose functions globally for backward compatibility
    // This prevents the "Identifier 'addWatermark' has already been declared" error
    if (typeof window.addWatermark === 'undefined') {
        window.addWatermark = addWatermark;
    }
    if (typeof window.getWatermarkText === 'undefined') {
        window.getWatermarkText = getWatermarkText;
    }
    if (typeof window.getTextRadius === 'undefined') {
        window.getTextRadius = getTextRadius;
    }
    
    // Shared utilities exported to global scope
    console.log('✅ Shared utilities: Module loaded successfully in browser environment');
    console.log('🔍 Shared utilities: Functions exported to window:', Object.keys(window).filter(k => k.includes('getTextRadius') || k.includes('addWatermark')));
} else if (typeof module !== 'undefined' && module.exports) {
    // Node.js environment
    module.exports = {
        getMeasurementContainer,
        getTextRadius,
        cleanupMeasurementContainer,
        getWatermarkText,
        addWatermark,
        getColorScale,
        getThemeDefaults,
        createSVG,
        centerContent,
        wrapText
    };
    console.log('✅ Shared utilities: Module loaded successfully in Node.js environment');
} else {
    console.error('❌ Shared utilities: Module failed to load in any environment');
}
