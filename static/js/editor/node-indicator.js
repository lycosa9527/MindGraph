/**
 * Node Indicator System
 * =====================
 * 
 * Reusable module for highlighting and indicating nodes in diagrams.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class NodeIndicator {
    constructor() {
        this.logger = window.logger || console;
        this.activeIndicators = new Map(); // Track active animations
        this.filterCounter = 0; // Unique filter IDs
    }
    
    /**
     * Initialize the indicator system
     */
    init() {
        this.logger.info('[NodeIndicator] Initialized');
    }
    
    /**
     * Main entry point: Highlight a node with various effects
     * 
     * @param {string|Element} target - Node ID, Element, or D3 selection
     * @param {Object} options - Configuration options
     * @param {string} options.type - 'glow', 'pulse', 'flash', 'shake', 'ping'
     * @param {string} options.color - Highlight color (default: auto-detect)
     * @param {number} options.duration - Animation duration in ms (default: 2400)
     * @param {number} options.intensity - Effect intensity 1-10 (default: 5)
     * @param {boolean} options.repeat - Repeat animation (default: false)
     * @param {Function} options.onComplete - Callback when animation completes
     */
    highlight(target, options = {}) {
        this.logger.info('[NodeIndicator] ✨ highlight() called with target:', target, 'options:', options);
        
        const element = this.resolveTarget(target);
        if (!element) {
            this.logger.error('[NodeIndicator] ❌ Target not found:', target);
            this.logger.info('[NodeIndicator] Available elements with data-node-type:', 
                document.querySelectorAll('[data-node-type]').length);
            this.logger.info('[NodeIndicator] Available elements with data-node-id:', 
                document.querySelectorAll('[data-node-id]').length);
            return null;
        }
        
        this.logger.info('[NodeIndicator] ✅ Element resolved:', element.tagName, {
            id: element.id,
            'data-node-type': element.getAttribute('data-node-type'),
            'data-node-id': element.getAttribute('data-node-id')
        });
        
        const config = {
            type: options.type || 'glow',
            color: options.color || this.detectColor(element),
            duration: options.duration || 2400,
            intensity: Math.max(1, Math.min(10, options.intensity || 5)),
            repeat: options.repeat || false,
            onComplete: options.onComplete
        };
        
        this.logger.info('[NodeIndicator] 🎨 Animation config:', {
            type: config.type,
            color: config.color,
            duration: config.duration,
            intensity: config.intensity
        });
        
        // Stop any existing animation on this element
        this.stopHighlight(element);
        
        // Apply the effect
        this.logger.info('[NodeIndicator] 🚀 Applying effect:', config.type);
        let result;
        switch (config.type) {
            case 'glow':
                result = this.applyGlow(element, config);
                break;
            case 'pulse':
                result = this.applyPulse(element, config);
                break;
            case 'flash':
                result = this.applyFlash(element, config);
                break;
            case 'shake':
                result = this.applyShake(element, config);
                break;
            case 'ping':
                result = this.applyPing(element, config);
                break;
            default:
                this.logger.warn('[NodeIndicator] Unknown effect type:', config.type);
                result = this.applyGlow(element, config);
        }
        
        this.logger.info('[NodeIndicator] ✅ Effect applied, animation ID:', result);
        return result;
    }
    
    /**
     * Glow Effect: Soft glowing border with pulsing stroke width
     */
    applyGlow(element, config) {
        this.logger.info('[NodeIndicator] 🌟 applyGlow() starting');
        
        const d3Element = d3.select(element);
        const elementType = this.getElementType(element);
        
        this.logger.info('[NodeIndicator] Element type:', elementType);
        
        // Store original styles
        const original = {
            stroke: d3Element.attr('stroke'),
            strokeWidth: d3Element.attr('stroke-width') || 2,
            filter: d3Element.attr('filter')
        };
        
        this.logger.info('[NodeIndicator] Original styles:', original);
        
        // Create glow filter
        const filterId = this.createGlowFilter(config.color, config.intensity);
        this.logger.info('[NodeIndicator] Created filter:', filterId);
        
        // Calculate stroke widths based on intensity
        const baseStroke = parseFloat(original.strokeWidth);
        const maxStroke = baseStroke + (config.intensity * 0.5);
        
        // Apply glow animation
        d3Element
            .attr('stroke', config.color)
            .attr('stroke-width', baseStroke)
            .attr('filter', `url(#${filterId})`);
        
        this.logger.info('[NodeIndicator] 🎬 Animation attributes applied to element');
        this.logger.info('[NodeIndicator] Filter attr now:', element.getAttribute('filter'));
        this.logger.info('[NodeIndicator] Stroke attr now:', element.getAttribute('stroke'));
        this.logger.info('[NodeIndicator] Stroke-width attr now:', element.getAttribute('stroke-width'));
        
        // 🔬 DEBUG: Check if attributes persist after a short delay
        setTimeout(() => {
            this.logger.info('[NodeIndicator] ⏱️ CHECK (after 100ms):');
            this.logger.info('[NodeIndicator]   - Filter:', element.getAttribute('filter'));
            this.logger.info('[NodeIndicator]   - Stroke:', element.getAttribute('stroke'));
            this.logger.info('[NodeIndicator]   - Stroke-width:', element.getAttribute('stroke-width'));
        }, 100);
        
        setTimeout(() => {
            this.logger.info('[NodeIndicator] ⏱️ CHECK (after 500ms):');
            this.logger.info('[NodeIndicator]   - Filter:', element.getAttribute('filter'));
            this.logger.info('[NodeIndicator]   - Stroke:', element.getAttribute('stroke'));
            this.logger.info('[NodeIndicator]   - Stroke-width:', element.getAttribute('stroke-width'));
        }, 500);
        
        this.logger.info('[NodeIndicator] Starting transition animation...');
        
        d3Element
            .transition()
            .duration(config.duration / 4)
            .attr('stroke-width', maxStroke)
            .on('start', () => this.logger.info('[NodeIndicator] 🎬 Transition 1 started'))
            .on('end', () => this.logger.info('[NodeIndicator] ✅ Transition 1 ended'))
            .transition()
            .duration(config.duration / 4)
            .attr('stroke-width', baseStroke)
            .on('start', () => this.logger.info('[NodeIndicator] 🎬 Transition 2 started'))
            .on('end', () => this.logger.info('[NodeIndicator] ✅ Transition 2 ended'))
            .transition()
            .duration(config.duration / 4)
            .attr('stroke-width', maxStroke)
            .on('start', () => this.logger.info('[NodeIndicator] 🎬 Transition 3 started'))
            .on('end', () => this.logger.info('[NodeIndicator] ✅ Transition 3 ended'))
            .transition()
            .duration(config.duration / 4)
            .attr('stroke-width', baseStroke)
            .attr('stroke', original.stroke || config.color)
            .on('start', () => this.logger.info('[NodeIndicator] 🎬 Transition 4 started (final)'))
            .on('end', () => {
                this.logger.info('[NodeIndicator] ✅ Transition 4 ended (final) - Starting cleanup');
                // Clean up
                d3Element.attr('filter', original.filter || null);
                this.removeFilter(filterId);
                this.logger.info('[NodeIndicator] 🧹 Cleanup complete');
                
                if (config.repeat) {
                    setTimeout(() => this.applyGlow(element, config), 100);
                } else if (config.onComplete) {
                    config.onComplete();
                }
            });
        
        // Track this animation
        const animationId = this.trackAnimation(element, 'glow', () => {
            d3Element.interrupt();
            d3Element
                .attr('stroke', original.stroke)
                .attr('stroke-width', original.strokeWidth)
                .attr('filter', original.filter || null);
            this.removeFilter(filterId);
        });
        
        return animationId;
    }
    
    /**
     * Pulse Effect: Scale animation (expand and contract)
     */
    applyPulse(element, config) {
        const d3Element = d3.select(element);
        const elementType = this.getElementType(element);
        
        // Get current transform
        const transform = d3Element.attr('transform') || '';
        
        // Calculate scale factor based on intensity
        const scaleFactor = 1 + (config.intensity * 0.05);
        
        // Get bounding box for transform origin
        const bbox = element.getBBox();
        const cx = bbox.x + bbox.width / 2;
        const cy = bbox.y + bbox.height / 2;
        
        // Store original stroke color
        const originalStroke = d3Element.attr('stroke');
        
        // Apply pulse with color change
        d3Element
            .attr('stroke', config.color)
            .transition()
            .duration(config.duration / 3)
            .attr('transform', `${transform} translate(${cx}, ${cy}) scale(${scaleFactor}) translate(${-cx}, ${-cy})`)
            .transition()
            .duration(config.duration / 3)
            .attr('transform', transform)
            .transition()
            .duration(config.duration / 3)
            .attr('transform', `${transform} translate(${cx}, ${cy}) scale(${scaleFactor}) translate(${-cx}, ${-cy})`)
            .transition()
            .duration(config.duration / 6)
            .attr('transform', transform)
            .attr('stroke', originalStroke)
            .on('end', () => {
                if (config.repeat) {
                    setTimeout(() => this.applyPulse(element, config), 100);
                } else if (config.onComplete) {
                    config.onComplete();
                }
            });
        
        return this.trackAnimation(element, 'pulse', () => {
            d3Element.interrupt();
            d3Element.attr('transform', transform).attr('stroke', originalStroke);
        });
    }
    
    /**
     * Flash Effect: Quick opacity blinks
     */
    applyFlash(element, config) {
        const d3Element = d3.select(element);
        const originalOpacity = d3Element.attr('opacity') || 1;
        const originalStroke = d3Element.attr('stroke');
        
        let flashCount = 0;
        const maxFlashes = Math.ceil(config.intensity / 2);
        const flashDuration = config.duration / (maxFlashes * 2);
        
        const flash = () => {
            if (flashCount >= maxFlashes) {
                d3Element
                    .attr('opacity', originalOpacity)
                    .attr('stroke', originalStroke);
                if (config.onComplete) config.onComplete();
                return;
            }
            
            d3Element
                .attr('stroke', config.color)
                .transition()
                .duration(flashDuration)
                .attr('opacity', 0.3)
                .transition()
                .duration(flashDuration)
                .attr('opacity', 1)
                .on('end', () => {
                    flashCount++;
                    if (config.repeat || flashCount < maxFlashes) {
                        flash();
                    } else {
                        d3Element.attr('stroke', originalStroke);
                        if (config.onComplete) config.onComplete();
                    }
                });
        };
        
        flash();
        
        return this.trackAnimation(element, 'flash', () => {
            d3Element.interrupt();
            d3Element.attr('opacity', originalOpacity).attr('stroke', originalStroke);
        });
    }
    
    /**
     * Shake Effect: Horizontal wiggle
     */
    applyShake(element, config) {
        const d3Element = d3.select(element);
        const transform = d3Element.attr('transform') || '';
        const shakeDistance = config.intensity * 2;
        
        d3Element
            .transition().duration(config.duration / 8).attr('transform', `${transform} translate(${shakeDistance}, 0)`)
            .transition().duration(config.duration / 8).attr('transform', `${transform} translate(${-shakeDistance}, 0)`)
            .transition().duration(config.duration / 8).attr('transform', `${transform} translate(${shakeDistance}, 0)`)
            .transition().duration(config.duration / 8).attr('transform', `${transform} translate(${-shakeDistance}, 0)`)
            .transition().duration(config.duration / 8).attr('transform', `${transform} translate(${shakeDistance / 2}, 0)`)
            .transition().duration(config.duration / 8).attr('transform', `${transform} translate(${-shakeDistance / 2}, 0)`)
            .transition().duration(config.duration / 4).attr('transform', transform)
            .on('end', () => {
                if (config.repeat) {
                    setTimeout(() => this.applyShake(element, config), 100);
                } else if (config.onComplete) {
                    config.onComplete();
                }
            });
        
        return this.trackAnimation(element, 'shake', () => {
            d3Element.interrupt();
            d3Element.attr('transform', transform);
        });
    }
    
    /**
     * Ping Effect: Expanding rings (like radar ping)
     */
    applyPing(element, config) {
        const svg = d3.select('#d3-container svg');
        const bbox = element.getBBox();
        const cx = bbox.x + bbox.width / 2;
        const cy = bbox.y + bbox.height / 2;
        const maxRadius = Math.max(bbox.width, bbox.height) * 2;
        
        // Create ping circle
        const ping = svg.append('circle')
            .attr('cx', cx)
            .attr('cy', cy)
            .attr('r', 0)
            .attr('fill', 'none')
            .attr('stroke', config.color)
            .attr('stroke-width', 3)
            .attr('opacity', 0.8);
        
        ping.transition()
            .duration(config.duration)
            .attr('r', maxRadius)
            .attr('opacity', 0)
            .on('end', () => {
                ping.remove();
                if (config.repeat) {
                    setTimeout(() => this.applyPing(element, config), 100);
                } else if (config.onComplete) {
                    config.onComplete();
                }
            });
        
        return this.trackAnimation(element, 'ping', () => {
            ping.interrupt();
            ping.remove();
        });
    }
    
    /**
     * Stop highlighting for an element
     */
    stopHighlight(target) {
        const element = this.resolveTarget(target);
        if (!element) return;
        
        const animationId = this.getAnimationId(element);
        if (animationId && this.activeIndicators.has(animationId)) {
            const cleanup = this.activeIndicators.get(animationId);
            cleanup();
            this.activeIndicators.delete(animationId);
        }
    }
    
    /**
     * Stop all active indicators
     */
    stopAll() {
        this.activeIndicators.forEach((cleanup, id) => cleanup());
        this.activeIndicators.clear();
    }
    
    // === Helper Methods ===
    
    /**
     * Resolve target to a DOM element
     */
    resolveTarget(target) {
        if (typeof target === 'string') {
            // IMPORTANT: Search in the ACTIVE editor (#d3-container) first, not the hidden gallery!
            const editorContainer = d3.select('#d3-container');
            
            // Try node ID in active editor first
            if (!editorContainer.empty()) {
                const byId = editorContainer.select(`[data-node-id="${target}"]`);
                if (!byId.empty()) {
                    this.logger.info('[NodeIndicator] ✅ Found in active editor (#d3-container)');
                    return byId.node();
                }
                
            // Try center node in active editor
            if (target === 'center') {
                // Try multiple patterns for center node
                let center = editorContainer.select('[data-node-type="center"]');
                if (!center.empty()) {
                    this.logger.info('[NodeIndicator] ✅ Found center by data-node-type="center"');
                    return center.node();
                }
                
                center = editorContainer.select('[data-node-type="topic"]');
                if (!center.empty()) {
                    this.logger.info('[NodeIndicator] ✅ Found center by data-node-type="topic"');
                    return center.node();
                }
                
                center = editorContainer.select('[data-node-id="topic_center"]');
                if (!center.empty()) {
                    this.logger.info('[NodeIndicator] ✅ Found center by data-node-id="topic_center"');
                    return center.node();
                }
                
                // For older templates: find the largest circle (likely the center)
                const allCircles = Array.from(editorContainer.selectAll('circle').nodes());
                if (allCircles.length > 0) {
                    const largestCircle = allCircles.reduce((max, circle) => {
                        const r = parseFloat(circle.getAttribute('r') || 0);
                        const maxR = parseFloat(max.getAttribute('r') || 0);
                        return r > maxR ? circle : max;
                    });
                    this.logger.info('[NodeIndicator] ✅ Found center as largest circle (fallback)');
                    return largestCircle;
                }
            }
                
                // Try CSS selector in active editor
                const bySelector = editorContainer.select(target);
                if (!bySelector.empty()) {
                    this.logger.info('[NodeIndicator] ✅ Found via selector in active editor (#d3-container)');
                    return bySelector.node();
                }
            }
            
            // FALLBACK: Search entire document (for backward compatibility)
            this.logger.warn('[NodeIndicator] ⚠️ Not found in #d3-container, searching entire document...');
            const byId = d3.select(`[data-node-id="${target}"]`);
            if (!byId.empty()) return byId.node();
            
            if (target === 'center') {
                const center = d3.select('[data-node-type="center"]');
                if (!center.empty()) return center.node();
            }
            
            const bySelector = d3.select(target);
            if (!bySelector.empty()) return bySelector.node();
            
            return null;
        }
        
        if (target && target.node) {
            // D3 selection
            return target.node();
        }
        
        return target; // Assume it's already a DOM element
    }
    
    /**
     * Detect appropriate color for element
     */
    detectColor(element) {
        const elementType = this.getElementType(element);
        
        if (elementType === 'center') {
            return '#9C27B0'; // Purple for center
        }
        
        // Try to get element's fill color
        const d3Element = d3.select(element);
        const fill = d3Element.attr('fill');
        if (fill && fill !== 'none') {
            return fill;
        }
        
        // Default to blue
        return '#2196F3';
    }
    
    /**
     * Get element type (center, node, text, etc.)
     */
    getElementType(element) {
        const d3Element = d3.select(element);
        return d3Element.attr('data-node-type') || 'node';
    }
    
    /**
     * Create a glow filter in SVG defs
     */
    createGlowFilter(color, intensity) {
        this.logger.info('[NodeIndicator] 🎨 createGlowFilter called', { color, intensity });
        
        const svg = d3.select('#d3-container svg');
        this.logger.info('[NodeIndicator] SVG element:', svg.empty() ? 'NOT FOUND' : 'FOUND');
        
        if (svg.empty()) {
            this.logger.error('[NodeIndicator] ❌ No SVG found in #d3-container!');
            return `node-indicator-glow-${++this.filterCounter}`;
        }
        
        let defs = svg.select('defs');
        this.logger.info('[NodeIndicator] Defs element (before):', defs.empty() ? 'NOT FOUND' : 'FOUND');
        
        if (defs.empty()) {
            this.logger.info('[NodeIndicator] Creating new defs element');
            defs = svg.append('defs');
        }
        
        this.logger.info('[NodeIndicator] Defs element (after):', defs.node());
        
        const filterId = `node-indicator-glow-${++this.filterCounter}`;
        const stdDeviation = Math.max(4, Math.min(12, intensity));
        
        this.logger.info('[NodeIndicator] Creating filter:', filterId, 'stdDeviation:', stdDeviation);
        
        const filter = defs.append('filter')
            .attr('id', filterId)
            .attr('x', '-50%')
            .attr('y', '-50%')
            .attr('width', '200%')
            .attr('height', '200%');
        
        filter.append('feGaussianBlur')
            .attr('in', 'SourceGraphic')
            .attr('stdDeviation', stdDeviation)
            .attr('result', 'blur');
        
        filter.append('feFlood')
            .attr('flood-color', color)
            .attr('result', 'color');
        
        filter.append('feComposite')
            .attr('in', 'color')
            .attr('in2', 'blur')
            .attr('operator', 'in')
            .attr('result', 'coloredBlur');
        
        const feMerge = filter.append('feMerge');
        feMerge.append('feMergeNode').attr('in', 'coloredBlur');
        feMerge.append('feMergeNode').attr('in', 'coloredBlur');
        feMerge.append('feMergeNode').attr('in', 'coloredBlur');
        feMerge.append('feMergeNode').attr('in', 'SourceGraphic');
        
        this.logger.info('[NodeIndicator] ✅ Filter created successfully:', filterId);
        this.logger.info('[NodeIndicator] Filter element:', filter.node());
        this.logger.info('[NodeIndicator] Filter in DOM?', document.getElementById(filterId));
        
        return filterId;
    }
    
    /**
     * Remove a filter from SVG defs
     */
    removeFilter(filterId) {
        const svg = d3.select('#d3-container svg');
        svg.select(`#${filterId}`).remove();
    }
    
    /**
     * Track an active animation
     */
    trackAnimation(element, type, cleanup) {
        const animationId = this.getAnimationId(element);
        this.activeIndicators.set(animationId, cleanup);
        return animationId;
    }
    
    /**
     * Get unique animation ID for an element
     */
    getAnimationId(element) {
        if (!element.__nodeIndicatorId) {
            element.__nodeIndicatorId = `indicator-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        }
        return element.__nodeIndicatorId;
    }
    
    /**
     * Test function - highlight all elements on the page
     * Useful for debugging: window.nodeIndicator.testAll()
     */
    testAll() {
        this.logger.info('[NodeIndicator] 🧪 Testing all elements...');
        
        // Search in ACTIVE editor (#d3-container)
        const editorContainer = document.querySelector('#d3-container');
        if (!editorContainer) {
            this.logger.error('[NodeIndicator] ❌ No #d3-container found!');
            return;
        }
        
        // Test center
        const center = editorContainer.querySelector('[data-node-type="center"]');
        if (center) {
            this.logger.info('[NodeIndicator] Found center element in active editor, highlighting...');
            this.highlight('center', { type: 'glow', duration: 3000, intensity: 8 });
        } else {
            this.logger.warn('[NodeIndicator] No center element found in active editor');
        }
        
        // Test all nodes in ACTIVE editor only
        const nodes = editorContainer.querySelectorAll('[data-node-id]');
        this.logger.info(`[NodeIndicator] Found ${nodes.length} nodes in active editor (#d3-container)`);
        nodes.forEach((node, index) => {
            setTimeout(() => {
                const nodeId = node.getAttribute('data-node-id');
                this.logger.info(`[NodeIndicator] Highlighting node ${index + 1}/${nodes.length}: ${nodeId}`);
                this.highlight(nodeId, {
                    type: ['glow', 'pulse', 'flash'][index % 3],
                    duration: 2000,
                    intensity: 6
                });
            }, index * 500);
        });
    }
}

// Global instance
window.nodeIndicator = new NodeIndicator();
window.nodeIndicator.init();

// Also log to console for easy debugging
console.log('✨ NodeIndicator loaded. Test with: window.nodeIndicator.testAll()');

// 🔬 VISUAL DEBUG TEST - Super simple, no filter, just BRIGHT colors
window.testVisualChange = function() {
    // Search in ACTIVE editor first!
    const editorContainer = document.querySelector('#d3-container');
    let node = editorContainer ? editorContainer.querySelector('[data-node-id="node_0"]') : null;
    
    if (!node) {
        console.warn('⚠️ No node_0 found in #d3-container, searching entire document...');
        node = document.querySelector('[data-node-id="node_0"]');
    }
    
    if (!node) {
        console.error('❌ No node found anywhere!');
        console.log('Available nodes in #d3-container:', 
            editorContainer ? editorContainer.querySelectorAll('[data-node-id]').length : 0);
        console.log('Available nodes in document:', document.querySelectorAll('[data-node-id]').length);
        return;
    }
    
    console.log('✅ Found node in:', node.closest('#d3-container') ? '#d3-container (active editor)' : 'other location');
    
    console.log('🔬 VISUAL TEST: Changing to BRIGHT RED, THICK stroke, NO filter');
    console.log('Element:', node);
    
    // Use D3 for consistency
    const d3Node = d3.select(node);
    
    // Store original
    const original = {
        stroke: d3Node.attr('stroke'),
        strokeWidth: d3Node.attr('stroke-width'),
        fill: d3Node.attr('fill')
    };
    
    console.log('Original:', original);
    
    // Apply SUPER OBVIOUS changes
    d3Node
        .attr('stroke', '#FF0000')
        .attr('stroke-width', '10')
        .attr('fill', '#FFFF00');
    
    console.log('Applied: stroke=#FF0000, stroke-width=10, fill=#FFFF00');
    console.log('After application:');
    console.log('  - stroke:', node.getAttribute('stroke'));
    console.log('  - stroke-width:', node.getAttribute('stroke-width'));
    console.log('  - fill:', node.getAttribute('fill'));
    
    // Keep for 5 seconds, then restore
    setTimeout(() => {
        console.log('⏱️ Restoring original...');
        d3Node
            .attr('stroke', original.stroke)
            .attr('stroke-width', original.strokeWidth)
            .attr('fill', original.fill);
    }, 5000);
    
    console.log('🎯 If you don\'t see a BRIGHT RED thick circle with YELLOW fill, there\'s a rendering/CSS issue!');
    
    // Check parent containers for visibility issues
    let parent = node.parentElement;
    let depth = 0;
    console.log('🔍 Checking parent containers for visibility issues:');
    while (parent && depth < 10) {
        const computed = window.getComputedStyle(parent);
        console.log(`  ${depth}: <${parent.tagName}> id="${parent.id}" class="${parent.className}"`);
        console.log(`     display: ${computed.display}, opacity: ${computed.opacity}, visibility: ${computed.visibility}`);
        console.log(`     position: ${computed.position}, z-index: ${computed.zIndex}`);
        if (computed.display === 'none' || computed.opacity === '0' || computed.visibility === 'hidden') {
            console.error(`     ❌ FOUND ISSUE: This container is hidden/invisible!`);
        }
        parent = parent.parentElement;
        depth++;
    }
    
    // Check if element is in viewport
    const rect = node.getBoundingClientRect();
    console.log('📐 Element position:', {
        x: rect.x,
        y: rect.y,
        width: rect.width,
        height: rect.height,
        inViewport: rect.x >= 0 && rect.y >= 0 && rect.x < window.innerWidth && rect.y < window.innerHeight
    });
    
    // Check computed styles on the element itself
    const computedSelf = window.getComputedStyle(node);
    console.log('🎨 Computed styles on circle:');
    console.log(`   stroke: ${computedSelf.stroke}`);
    console.log(`   strokeWidth: ${computedSelf.strokeWidth}`);
    console.log(`   fill: ${computedSelf.fill}`);
    console.log(`   opacity: ${computedSelf.opacity}`);
    console.log(`   display: ${computedSelf.display}`);
};

console.log('🔬 Run window.testVisualChange() to test basic visual changes');

// 🎯 SUPER VISIBLE TEST - Pulse a node (scale + color)
window.testPulse = function(nodeId = 'context_0') {
    console.log('🎯 Testing PULSE animation on:', nodeId);
    window.nodeIndicator.highlight(nodeId, {
        type: 'pulse',
        duration: 2000,
        intensity: 8,
        color: '#00FF00'  // Bright green
    });
};

// 💥 SUPER VISIBLE TEST - Flash a node (blink + color)  
window.testFlash = function(nodeId = 'context_0') {
    console.log('💥 Testing FLASH animation on:', nodeId);
    window.nodeIndicator.highlight(nodeId, {
        type: 'flash',
        duration: 1500,
        intensity: 10,
        color: '#FF0000'  // Bright red
    });
};

console.log('🎯 Quick tests: window.testPulse() or window.testFlash()');

