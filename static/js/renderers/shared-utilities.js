/**
 * Shared D3 Utilities for MindGraph Renderers
 * 
 * This module contains common utility functions used across all graph type renderers.
 * By extracting these shared utilities, we eliminate code duplication and reduce
 * the size of individual renderer modules.
 * 
 * Performance Impact: ~15-20KB reduction per renderer module
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
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
    // Try to get school name from user's organization
    try {
        // Try multiple ways to access auth (global, window.auth, window.AuthHelper)
        const authHelper = window.auth || window.AuthHelper || (typeof auth !== 'undefined' ? auth : null);
        
        if (authHelper && typeof authHelper.getUser === 'function') {
            const user = authHelper.getUser();
            if (user && user.organization && user.organization.name) {
                return user.organization.name;
            }
        }
    } catch (error) {
        // Silently fallback if auth is not available
        console.debug('Watermark: Could not get school name', error);
    }
    
    // Fallback to theme watermark or default
    return theme?.watermark?.text || '';
}

function addWatermark(svg, theme = null) {
    if (!svg || !svg.node()) {
        console.debug('Watermark: SVG not valid');
        return;
    }
    
    const watermarkText = getWatermarkText(theme);
    
    // Don't add watermark if there's no school name
    if (!watermarkText || watermarkText.trim() === '') {
        console.debug('Watermark: No school name available, skipping watermark');
        return;
    }
    
    const watermarkConfig = theme?.watermark || {};
    
    // Elegant, professional, clean, and simple watermark configuration
    const config = {
        text: watermarkText,
        fontSize: watermarkConfig.fontSize || '11px',
        fill: watermarkConfig.fill || '#6b7280', // Subtle gray color
        opacity: watermarkConfig.opacity || 0.65, // Subtle opacity for elegant look
        position: watermarkConfig.position || 'bottom-right',
        padding: watermarkConfig.padding || 12
    };
    
    // Get SVG dimensions AND viewBox offsets (critical for bubble/circle maps)
    const svgNode = svg.node();
    if (!svgNode) {
        console.debug('Watermark: SVG node not found');
        return;
    }
    
    let width, height, offsetX = 0, offsetY = 0;
    
    // Try to get viewBox first (most reliable and handles offsets)
    const viewBox = svgNode.getAttribute('viewBox');
    if (viewBox) {
        const parts = viewBox.split(' ').map(Number);
        if (parts.length === 4) {
            offsetX = parts[0];  // minX offset (can be negative for bubble/circle maps)
            offsetY = parts[1];  // minY offset (can be negative for bubble/circle maps)
            width = parts[2];    // viewBox width
            height = parts[3];   // viewBox height
        }
    } else {
        // Fallback to width/height attributes if no viewBox
        width = parseFloat(svgNode.getAttribute('width')) || parseFloat(svgNode.style.width) || 800;
        height = parseFloat(svgNode.getAttribute('height')) || parseFloat(svgNode.style.height) || 600;
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
    
    // Remove existing watermark if any (to avoid duplicates on re-render)
    svg.selectAll('.watermark').remove();
    
    // Add watermark text - elegant, professional, clean, and simple
    svg.append('text')
        .attr('class', 'watermark')
        .attr('x', x)
        .attr('y', y)
        .attr('text-anchor', textAnchor)
        .attr('dominant-baseline', 'alphabetic')
        .attr('font-size', config.fontSize)
        .attr('font-family', 'Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif')
        .attr('font-weight', '400') // Regular weight for clean, simple look
        .attr('letter-spacing', '0.01em') // Subtle letter spacing for elegance
        .attr('fill', config.fill)
        .attr('opacity', config.opacity)
        .attr('pointer-events', 'none')
        .style('user-select', 'none') // Prevent text selection
        .text(config.text);
    
    console.debug('Watermark: Added school name watermark', { text: watermarkText, x, y, width, height });
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
 * Split text by newlines and wrap each line if needed
 * @param {string} text - Text to process
 * @param {number} fontSize - Font size in pixels
 * @param {number} maxWidth - Maximum width before wrapping
 * @param {Function} measureFn - Function to measure text width: (text, fontSize) => number
 * @returns {string[]} Array of lines (already wrapped)
 */
/**
 * Render multi-line text using multiple text elements (workaround for tspan issues)
 * @param {Object} svg - D3 SVG selection
 * @param {string[]} lines - Array of text lines to render
 * @param {number} x - X position (center)
 * @param {number} startY - Starting Y position for first line
 * @param {number} lineHeight - Height between lines
 * @param {Object} attrs - Attributes to apply to each text element
 */
function renderMultiLineText(svg, lines, x, startY, lineHeight, attrs) {
    const finalLines = (lines && lines.length > 0) ? lines : [''];
    
    finalLines.forEach((line, i) => {
        const textEl = svg.append('text')
            .attr('x', x)
            .attr('y', startY + i * lineHeight)
            .attr('text-anchor', 'middle')
            .attr('dominant-baseline', 'middle')
            .text(line);
        
        // Apply additional attributes
        if (attrs) {
            Object.entries(attrs).forEach(([key, value]) => {
                if (key.startsWith('style-')) {
                    textEl.style(key.substring(6), value);
                } else {
                    textEl.attr(key, value);
                }
            });
        }
    });
}

function splitAndWrapText(text, fontSize, maxWidth, measureFn) {
    const textStr = String(text || '');
    const allLines = [];
    
    // First, split by explicit newlines (user-inserted line breaks)
    const explicitLines = textStr.split(/\n/);
    
    // For each explicit line, wrap it if needed
    explicitLines.forEach((line, lineIndex) => {
        // Trim each line but preserve empty lines
        const trimmedLine = line.trim();
        if (trimmedLine === '' && lineIndex < explicitLines.length - 1) {
            // Preserve empty lines (but not trailing ones)
            allLines.push('');
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
            try {
                const width = measureFn(candidate, fontSize);
                if (width <= maxWidth || current === '') {
                    current = candidate;
                } else {
                    if (current) {
                        allLines.push(current);
                    }
                    current = w;
                }
            } catch (e) {
                // Fallback: just add the candidate
                current = candidate;
            }
        }
        if (current) {
            allLines.push(current);
        }
    });
    
    return allLines.length > 0 ? allLines : [''];
}

/**
 * Split text by newline characters (from Ctrl+Enter in properties panel)
 * Preserves explicit line breaks inserted by users
 * @param {string} text - Text to split (may contain \n from Ctrl+Enter)
 * @returns {string[]} Array of lines
 */
function splitTextLines(text) {
    const textStr = String(text || '');
    if (textStr === '') return ['']; // Return empty string array like wrapIntoLines does
    
    // Split by newlines (invisible \n character inserted via Ctrl+Enter)
    const lines = textStr.split(/\n/);
    
    // Return lines array (empty lines are preserved, matching Concept Map behavior)
    // Note: Can return [''] for empty text, matching wrapIntoLines pattern
    // But ensure we always have at least one element
    if (lines.length === 0) return [''];
    
    // Filter out trailing empty lines (like Concept Map does) but preserve non-trailing empty lines
    const result = [];
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];
        const trimmedLine = line.trim();
        if (trimmedLine === '' && i < lines.length - 1) {
            // Preserve non-trailing empty lines
            result.push('');
        } else if (trimmedLine !== '') {
            // Preserve non-empty lines
            result.push(line);
        }
        // Skip trailing empty lines
    }
    
    // Ensure at least one element (even if empty)
    return result.length > 0 ? result : [''];
}

/**
 * Extract text from SVG text element, handling multiple text elements for multi-line text
 * This function supports three approaches:
 * 1. Legacy tspan-based multi-line text (within single text element)
 * 2. New multi-text approach (multiple text elements with same data-node-id)
 * 3. Single text element with direct text content
 * 
 * @param {d3.Selection} textElement - D3 selection of text element
 * @returns {string} Extracted text with \n for line breaks
 */
function extractTextFromSVG(textElement) {
    if (!textElement || textElement.empty()) return '';
    
    const node = textElement.node();
    if (!node) return '';
    
    // Check for legacy tspan children first (backward compatibility)
    const tspans = textElement.selectAll('tspan');
    if (!tspans.empty() && tspans.size() > 0) {
        // Has tspan children - extract from tspans
        const lines = [];
        tspans.each(function() {
            const tspanText = d3.select(this).text();
            lines.push(tspanText);
        });
        if (lines.length > 0) {
            return lines.join('\n');
        }
        return '';
    }
    
    // Check if this is part of multi-text element approach (data-line-index attribute)
    const lineIndex = textElement.attr('data-line-index');
    const nodeId = textElement.attr('data-node-id');
    
    if (lineIndex !== null && nodeId) {
        // This is part of a multi-text element set - find all text elements with same node ID
        const svg = d3.select(node.ownerSVGElement || node.closest('svg'));
        if (!svg.empty()) {
            const allTextElements = svg.selectAll(`text[data-node-id="${nodeId}"]`);
            if (allTextElements.size() > 1) {
                // Multiple text elements - collect and sort by line index
                const lineEntries = [];
                allTextElements.each(function() {
                    const el = d3.select(this);
                    const idx = parseInt(el.attr('data-line-index') || '0', 10);
                    const text = el.text() || '';
                    lineEntries.push({ idx, text });
                });
                lineEntries.sort((a, b) => a.idx - b.idx);
                return lineEntries.map(e => e.text).join('\n');
            }
        }
    }
    
    // Fallback: direct text content (single-line or no special handling needed)
    return textElement.text() || '';
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
                const textElement = d3.select(this);
                
                // For multi-text approach: only include first line (data-line-index=0 or no index)
                // This prevents counting the same node multiple times
                const lineIndex = textElement.attr('data-line-index');
                if (lineIndex !== null && lineIndex !== '0') {
                    return false; // Skip non-first lines of multi-text nodes
                }
                
                // Use extractTextFromSVG to handle both single-line and multi-line text
                const text = (typeof window.extractTextFromSVG === 'function') 
                    ? window.extractTextFromSVG(textElement) 
                    : textElement.text();
                const fontSize = parseFloat(textElement.attr('font-size')) || 16;
                const fontWeight = textElement.attr('font-weight');
                const fillColor = textElement.attr('fill');
                
                // Exclude watermarks
                const isWatermark = text === 'MindGraph';
                
                // Exclude main topic nodes (bold or semi-bold text - central topics, main concepts)
                // Note: concept maps use font-weight 600, other maps use 'bold'
                const isMainTopic = fontWeight === 'bold' || fontWeight === '600' || parseInt(fontWeight) >= 600;
                
                // Exclude empty text
                const isEmpty = !text || text.length === 0;
                
                // For flow maps and bridge maps: Exclude main step/example text (white text on blue background)
                // Flow map main steps and bridge map first pair use white text (#ffffff)
                const isMainStep = fillColor && fillColor.toLowerCase() === '#ffffff' && fontSize >= 14;
                
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
        // Track already processed node IDs to avoid duplicates in answer key
        const processedNodeIds = new Set();
        
        textElements.each(function(d, i) {
            if (indicesToHide.includes(i)) {
                const textElement = d3.select(this);
                const nodeId = textElement.attr('data-node-id');
                
                // Use extractTextFromSVG to handle both single-line and multi-line text
                const text = (typeof window.extractTextFromSVG === 'function') 
                    ? window.extractTextFromSVG(textElement) 
                    : textElement.text();
                
                // Only add to answer key once per node ID
                if (!nodeId || !processedNodeIds.has(nodeId)) {
                    hiddenTexts.push(text);
                    if (nodeId) processedNodeIds.add(nodeId);
                }
                
                // Hide the text element
                d3.select(this)
                    .attr('opacity', 0)
                    .attr('fill', 'transparent');
                    
                // Also hide any tspan children (legacy support)
                d3.select(this).selectAll('tspan')
                    .attr('opacity', 0)
                    .attr('fill', 'transparent');
                
                // For multi-text approach: hide all other text elements with same node ID
                if (nodeId) {
                    const svgEl = d3.select(this.ownerSVGElement || this.closest('svg'));
                    if (!svgEl.empty()) {
                        svgEl.selectAll(`text[data-node-id="${nodeId}"]`).each(function() {
                            d3.select(this)
                                .attr('opacity', 0)
                                .attr('fill', 'transparent');
                        });
                    }
                }
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
            // Mark with class so it can be filtered out during export
            svg.append('text')
                .attr('class', 'learning-sheet-answer-key')
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
        splitAndWrapText,
        splitTextLines,
        extractTextFromSVG,
        knockoutTextForLearningSheet
    };
    
    // Also expose splitAndWrapText globally for backward compatibility
    if (typeof window.splitAndWrapText === 'undefined') {
        window.splitAndWrapText = splitAndWrapText;
    }
    
    // Expose renderMultiLineText globally
    if (typeof window.renderMultiLineText === 'undefined') {
        window.renderMultiLineText = renderMultiLineText;
    }
    
    // Expose splitTextLines globally for backward compatibility
    if (typeof window.splitTextLines === 'undefined') {
        window.splitTextLines = splitTextLines;
    }
    
    // Expose extractTextFromSVG globally for backward compatibility
    if (typeof window.extractTextFromSVG === 'undefined') {
        window.extractTextFromSVG = extractTextFromSVG;
    }
    
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
        splitAndWrapText,
        splitTextLines,
        extractTextFromSVG,
        knockoutTextForLearningSheet
    };
} else {
    logger.error('SharedUtilities', 'Module failed to load in any environment');
}
