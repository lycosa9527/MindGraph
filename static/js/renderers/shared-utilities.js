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

// --- Safe, memory-leak-free text radius measurement ---
let measurementContainer = null;

function getMeasurementContainer() {
    if (!measurementContainer) {
        const body = d3.select('body');
        if (body.empty()) {
            logger.warn('SharedUtilities', 'Body element not found, creating measurement container in document');
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
        logger.error('SharedUtilities', 'Error calculating text radius', error);
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
    
    // Get SVG dimensions AND viewBox offsets (critical for bubble/circle maps)
    const svgNode = svg.node();
    let width, height, offsetX = 0, offsetY = 0;
    
    // Try to get viewBox first (most reliable and handles offsets)
    const viewBox = svgNode.getAttribute('viewBox');
    if (viewBox) {
        const parts = viewBox.split(' ').map(Number);
        offsetX = parts[0];  // minX offset (can be negative for bubble/circle maps)
        offsetY = parts[1];  // minY offset (can be negative for bubble/circle maps)
        width = parts[2];    // viewBox width
        height = parts[3];   // viewBox height
    } else {
        // Fallback to width/height attributes if no viewBox
        width = parseFloat(svgNode.getAttribute('width')) || 800;
        height = parseFloat(svgNode.getAttribute('height')) || 600;
        // offsetX and offsetY remain 0
    }
    
    // Calculate position based on configuration, accounting for viewBox offset
    let x, y, textAnchor;
    
    switch (config.position) {
        case 'top-left':
            x = offsetX + config.padding;
            y = offsetY + config.padding + 12;
            textAnchor = 'start';
            break;
        case 'top-right':
            x = offsetX + width - config.padding;
            y = offsetY + config.padding + 12;
            textAnchor = 'end';
            break;
        case 'bottom-left':
            x = offsetX + config.padding;
            y = offsetY + height - config.padding;
            textAnchor = 'start';
            break;
        case 'bottom-right':
        default:
            x = offsetX + width - config.padding;
            y = offsetY + height - config.padding;
            textAnchor = 'end';
            break;
    }
    
    // Add watermark text - EXACTLY as in original d3-renderers.js
    svg.append('text')
        .attr('class', 'watermark')
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
        logger.warn('SharedUtilities', 'Could not center content', error);
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

/**
 * Hide random text elements for learning sheet mode
 * @param {Object} svg - D3 SVG selection
 * @param {number} hiddenPercentage - Percentage of text elements to hide (0-1)
 */
function knockoutTextForLearningSheet(svg, hiddenPercentage) {
    if (!svg || hiddenPercentage <= 0) return;
    
    try {
        // Get all text elements, excluding watermarks, titles, and critical structural elements
        const allTextElements = svg.selectAll('text');
        
        const textElements = allTextElements
            .filter(function() {
                const text = d3.select(this).text();
                const fontSize = parseFloat(d3.select(this).attr('font-size')) || 16;
                const fontWeight = d3.select(this).attr('font-weight');
                const fillColor = d3.select(this).attr('fill');
                
                // Exclude watermarks
                const isWatermark = text === 'MindGraph';
                
                // Exclude main topic nodes (bold or semi-bold text - central topics, main concepts)
                // Note: concept maps use font-weight 600, other maps use 'bold'
                const isMainTopic = fontWeight === 'bold' || fontWeight === '600' || parseInt(fontWeight) >= 600;
                
                // Exclude empty text
                const isEmpty = text.length === 0;
                
                // For flow maps and bridge maps: Exclude main step/example text (white text on blue background)
                // Flow map main steps and bridge map first pair use white text (#ffffff)
                const isMainStep = fillColor && fillColor.toLowerCase() === '#ffffff' && fontSize >= 14;
                
                // Debug logging for each text element
                if (!isWatermark && !isMainTopic && !isEmpty) {
                }
                
                return !isWatermark && !isMainTopic && !isEmpty && !isMainStep;
            });
        
        const totalTexts = textElements.size();
        if (totalTexts === 0) {
            return;
        }
        
        // Ensure at least 2 elements are hidden (20% rate)
        const hideCount = Math.max(2, Math.floor(totalTexts * hiddenPercentage));
        if (hideCount === 0) {
            return;
        }
        
        // Create array of indices to hide
        const indicesToHide = [];
        while (indicesToHide.length < hideCount) {
            const randomIndex = Math.floor(Math.random() * totalTexts);
            if (!indicesToHide.includes(randomIndex)) {
                indicesToHide.push(randomIndex);
            }
        }
        
        // Collect hidden texts for answer key
        const hiddenTexts = [];
        
        // Hide selected texts and collect their values
        textElements.each(function(d, i) {
            if (indicesToHide.includes(i)) {
                const text = d3.select(this).text();
                hiddenTexts.push(text);
                
                d3.select(this)
                    .attr('opacity', 0)
                    .attr('fill', 'transparent');
            }
        });
        
        
        // Add answer key below the diagram
        if (hiddenTexts.length > 0) {
            // Create answer key text
            const answerText = '参考答案: ' + hiddenTexts.join(', ');
            const answerKeyHeight = 50; // Space needed for answer key
            
            // Get viewBox or use regular coordinates
            const viewBox = svg.attr('viewBox');
            let answerX, answerY;
            let currentWidth, currentHeight;
            
            if (viewBox) {
                // Parse viewBox: "minX minY width height"
                const [minX, minY, width, height] = viewBox.split(' ').map(Number);
                currentWidth = width;
                currentHeight = height;
                
                // Expand viewBox to make room for answer key
                const newHeight = height + answerKeyHeight;
                svg.attr('viewBox', `${minX} ${minY} ${width} ${newHeight}`);
                
                // Update SVG height attribute
                const svgHeight = parseFloat(svg.attr('height')) || height;
                svg.attr('height', svgHeight + answerKeyHeight);
                
                // Position answer key at new bottom
                answerX = minX + 20;
                answerY = minY + newHeight - 20; // 20px from new bottom
                
            } else {
                // Use regular coordinates
                const bbox = svg.node().getBBox();
                currentWidth = parseFloat(svg.attr('width')) || bbox.width;
                currentHeight = parseFloat(svg.attr('height')) || bbox.height;
                
                // Expand SVG height to make room for answer key
                const newHeight = currentHeight + answerKeyHeight;
                svg.attr('height', newHeight);
                
                // Position answer key at new bottom
                answerX = 20;
                answerY = newHeight - 20; // 20px from new bottom
                
            }
            
            // Add answer key at the bottom
            svg.append('text')
                .attr('x', answerX)
                .attr('y', answerY)
                .attr('font-family', 'Inter, Arial, sans-serif')
                .attr('font-size', '14')
                .attr('font-weight', '500')
                .attr('fill', '#374151')
                .text(answerText);
            
        }
        
    } catch (error) {
        logger.error('SharedUtilities', 'Error in knockoutTextForLearningSheet', error);
    }
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
        wrapText,
        knockoutTextForLearningSheet
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
    if (typeof window.knockoutTextForLearningSheet === 'undefined') {
        window.knockoutTextForLearningSheet = knockoutTextForLearningSheet;
    }
    
    // Shared utilities exported to global scope
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
        wrapText,
        knockoutTextForLearningSheet
    };
} else {
    logger.error('SharedUtilities', 'Module failed to load in any environment');
}
