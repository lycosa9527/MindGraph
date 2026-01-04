/**
 * CanvasManager - Manages canvas setup and viewport
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class CanvasManager {
    constructor() {
        this.container = null;
        this.svg = null;
        this.zoom = null;
        this.currentZoom = 1;
        this.currentPan = { x: 0, y: 0 };
    }
    
    /**
     * Setup canvas and container
     * @param {string} containerId - Container element ID
     * @param {Object} options - Configuration options
     */
    setupCanvas(containerId, options = {}) {
        this.container = d3.select(containerId);
        
        if (this.container.empty()) {
            logger.error('CanvasManager', `Container ${containerId} not found`);
            return;
        }
        
        // Clear existing content
        this.container.html('');
        
        // Set container styles
        this.container
            .style('width', '100%')
            .style('height', '100%')
            .style('min-height', options.minHeight || '600px')
            .style('overflow', 'hidden')
            .style('position', 'relative')
            .style('background-color', options.backgroundColor || '#f5f5f5');
        
        return this.container;
    }
    
    /**
     * Create SVG element
     * @param {number} width - SVG width
     * @param {number} height - SVG height
     * @returns {Object} D3 SVG selection
     */
    createSVG(width, height) {
        this.svg = this.container.append('svg')
            .attr('width', '100%')
            .attr('height', '100%')
            .attr('viewBox', `0 0 ${width} ${height}`)
            .attr('preserveAspectRatio', 'xMidYMid meet');
        
        return this.svg;
    }
    
    /**
     * Enable pan and zoom
     * @param {Object} options - Zoom options
     */
    enablePanZoom(options = {}) {
        if (!this.svg) {
            logger.error('CanvasManager', 'SVG not created yet');
            return;
        }
        
        const minZoom = options.minZoom || 0.1;
        const maxZoom = options.maxZoom || 10;
        
        this.zoom = d3.zoom()
            .scaleExtent([minZoom, maxZoom])
            // Zoom: mouse wheel only
            // Pan: middle mouse button drag only
            .filter((event) => {
                // Allow wheel events for zooming
                if (event.type === 'wheel') {
                    return true;
                }
                // Allow middle mouse button (button === 1) for panning
                // This enables drag-to-pan when holding middle mouse button
                if (event.type === 'mousedown' && event.button === 1) {
                    event.preventDefault(); // Prevent default middle-click behavior (auto-scroll)
                    return true;
                }
                // Block everything else: left click, right click, double-click, touch
                return false;
            })
            .on('zoom', (event) => {
                this.currentZoom = event.transform.k;
                this.currentPan = { x: event.transform.x, y: event.transform.y };
                
                this.svg.select('g.canvas-content')
                    .attr('transform', event.transform);
                
                if (options.onZoom) {
                    options.onZoom(event.transform);
                }
            });
        
        this.svg.call(this.zoom);
        
        // CRITICAL: Remove dblclick.zoom handler as extra safety
        // The filter above already blocks dblclick, but this ensures it's completely gone
        this.svg.on('dblclick.zoom', null);
        
        // Create content group
        const contentGroup = this.svg.append('g')
            .attr('class', 'canvas-content');
        
        return contentGroup;
    }
    
    /**
     * Reset zoom to default
     */
    resetZoom() {
        if (this.svg && this.zoom) {
            this.svg.transition()
                .duration(750)
                .call(this.zoom.transform, d3.zoomIdentity);
        }
    }
    
    /**
     * Zoom to specific level
     * @param {number} level - Zoom level
     */
    zoomTo(level) {
        if (this.svg && this.zoom) {
            this.svg.transition()
                .duration(750)
                .call(this.zoom.scaleTo, level);
        }
    }
    
    /**
     * Fit content to view
     * @param {Object} bounds - Content bounds
     */
    fitToView(bounds) {
        if (!this.svg || !this.zoom) return;
        
        const containerNode = this.container.node();
        const width = containerNode.clientWidth;
        const height = containerNode.clientHeight;
        
        const scale = Math.min(
            width / bounds.width,
            height / bounds.height
        ) * 0.9; // 90% to add padding
        
        const translate = [
            (width - bounds.width * scale) / 2 - bounds.x * scale,
            (height - bounds.height * scale) / 2 - bounds.y * scale
        ];
        
        this.svg.transition()
            .duration(750)
            .call(
                this.zoom.transform,
                d3.zoomIdentity.translate(translate[0], translate[1]).scale(scale)
            );
    }
    
    /**
     * Get current transform
     * @returns {Object} Current transform
     */
    getCurrentTransform() {
        return {
            zoom: this.currentZoom,
            pan: this.currentPan
        };
    }
    
    /**
     * Disable pan and zoom
     */
    disablePanZoom() {
        if (this.svg && this.zoom) {
            this.svg.on('.zoom', null);
        }
    }
    
    /**
     * Clear canvas
     */
    clear() {
        if (this.container) {
            this.container.html('');
        }
    }
}

// Make available globally
if (typeof window !== 'undefined') {
    window.CanvasManager = CanvasManager;
}

