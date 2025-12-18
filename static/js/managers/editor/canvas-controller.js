/**
 * Canvas Controller
 * =================
 * 
 * Manages canvas sizing, responsive layout, and viewport fitting.
 * Handles window resize, panel space adjustments, and zoom/pan.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class CanvasController {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        
        // NEW: Add owner identifier for Event Bus Listener Registry
        this.ownerId = 'CanvasController';
        
        // Canvas state
        this.isSizedForPanel = false;
        this.lastKnownWidth = null;
        this.lastKnownHeight = null;
        this.isDestroyed = false;
        
        // Panel dimensions (from CSS)
        this.propertyPanelWidth = 320;
        this.aiPanelWidth = 420;
        
        // Mobile detection
        this.isMobile = this.detectMobileDevice();
        
        // Subscribe to events
        this.subscribeToEvents();
        
        // Bind window resize handler
        this.bindWindowResize();
        
        this.logger.info('CanvasController', 'Canvas Controller initialized', {
            isMobile: this.isMobile
        });
    }
    
    /**
     * Subscribe to Event Bus events
     */
    subscribeToEvents() {
        // Listen for panel open/close
        this.eventBus.onWithOwner('panel:opened', (data) => {
            this.handlePanelChange(data.panel, true);
        }, this.ownerId);
        
        this.eventBus.onWithOwner('panel:closed', (data) => {
            this.handlePanelChange(data.panel, false);
        }, this.ownerId);
        
        // Listen for fit requests
        this.eventBus.onWithOwner('canvas:fit_requested', (data) => {
            this.fitDiagramToWindow(data?.animate);
        }, this.ownerId);
        
        // Listen for diagram rendered
        this.eventBus.onWithOwner('diagram:rendered', () => {
            this.checkAutoFitNeeded();
        }, this.ownerId);
        
        this.logger.debug('CanvasController', 'Subscribed to events');
    }
    
    /**
     * Bind window resize handler
     */
    bindWindowResize() {
        let resizeTimeout;
        
        window.addEventListener('resize', () => {
            // Debounce resize events
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                this.handleWindowResize();
            }, 150);
        });
        
        // Also handle orientation change on mobile
        if (this.isMobile) {
            window.addEventListener('orientationchange', () => {
                setTimeout(() => {
                    this.handleWindowResize();
                }, 200);
            });
        }
    }
    
    /**
     * Handle panel open/close
     * @param {string} panelName - Panel name (property, mindmate, etc.)
     * @param {boolean} isOpen - Whether panel is open
     */
    handlePanelChange(panelName, isOpen) {
        // Ignore events if already destroyed
        if (this.isDestroyed) {
            return;
        }
        
        this.logger.debug('CanvasController', 'Panel state changed', {
            panel: panelName,
            isOpen,
            currentState: this.isSizedForPanel
        });
        
        if (panelName === 'property' || panelName === 'mindmate') {
            if (isOpen) {
                // When property panel opens (e.g., node clicked), fit with panel space
                // Use ViewManager via Event Bus to ensure proper fit with panel space
                // CRITICAL: Use animate: false to prevent jarring "jump" on first node selection
                // The ViewManager's smart check will skip if already sized for panel
                this.logger.debug('CanvasController', 'Panel opened - requesting fit to canvas with panel');
                this.eventBus.emit('view:fit_to_canvas_requested', { animate: false });
            } else {
                // When panel closes, fit to full canvas
                // Use animation here since panel closing is a deliberate user action
                this.logger.debug('CanvasController', 'Panel closed - requesting fit to full canvas');
                this.eventBus.emit('view:fit_to_window_requested', { animate: true });
            }
        }
    }
    
    /**
     * Fit diagram to canvas with panel space reserved
     * @param {boolean} animate - Whether to animate the transition
     */
    fitToCanvasWithPanel(animate = false) {
        this.logger.debug('CanvasController', 'Fitting to canvas with panel');
        
        this.isSizedForPanel = true;
        this.fitDiagramToWindow(animate);
        
        this.eventBus.emit('canvas:fitted_with_panel', {
            panelWidth: this.getActivePanelWidth()
        });
    }
    
    /**
     * Fit diagram to full canvas (no panel space)
     * @param {boolean} animate - Whether to animate the transition
     */
    fitToFullCanvas(animate = false) {
        this.logger.debug('CanvasController', 'Fitting to full canvas');
        
        this.isSizedForPanel = false;
        this.fitDiagramToWindow(animate);
        
        this.eventBus.emit('canvas:fitted_full', {});
    }
    
    /**
     * Get width of currently active panel
     * @returns {number} Panel width in pixels
     */
    getActivePanelWidth() {
        const panelState = this.stateManager.getState().panels;
        
        if (panelState.property?.open) {
            return this.propertyPanelWidth;
        }
        
        if (panelState.mindmate?.open) {
            return this.aiPanelWidth;
        }
        
        return 0;
    }
    
    /**
     * Fit diagram to window
     * @param {boolean} animate - Whether to animate
     */
    fitDiagramToWindow(animate = false) {
        try {
            // Skip if Node Palette is active (d3-container is hidden)
            // Use PanelManager instead of direct DOM check
            if (window.panelManager?.isPanelOpen('nodePalette')) {
                const d3Container = document.getElementById('d3-container');
                if (d3Container && d3Container.style.display === 'none') {
                    this.logger.debug('CanvasController', 'Skipping fit: Node Palette is active');
                    return;
                }
            }
            
            this.logger.debug('CanvasController', 'Fitting diagram to window');
            
            const container = d3.select('#d3-container');
            const svg = container.select('svg');
            
            if (svg.empty()) {
                this.logger.warn('CanvasController', 'No SVG found, cannot fit');
                return;
            }
            
            // Calculate content bounds
            const contentBounds = this.calculateContentBounds(svg);
            
            if (!contentBounds) {
                this.logger.warn('CanvasController', 'No valid content bounds');
                return;
            }
            
            // Get container dimensions
            const containerNode = container.node();
            const containerWidth = containerNode.clientWidth;
            const containerHeight = containerNode.clientHeight;
            
            // Calculate available width (accounting for panels)
            const availableWidth = this.calculateAvailableWidth(containerWidth);
            
            this.logger.debug('CanvasController', 'Canvas dimensions', {
                containerWidth,
                containerHeight,
                availableWidth,
                panelWidth: containerWidth - availableWidth,
                contentBounds
            });
            
            // Apply transform
            this.applyViewBoxTransform(
                svg, 
                contentBounds, 
                availableWidth, 
                containerHeight, 
                animate
            );
            
            // Emit resize event
            this.eventBus.emit('canvas:resized', {
                availableWidth,
                containerHeight,
                contentBounds
            });
            
        } catch (error) {
            this.logger.error('CanvasController', 'Error fitting diagram:', error);
        }
    }
    
    /**
     * Calculate content bounds of SVG
     * @param {Object} svg - D3 selection of SVG
     * @returns {Object|null} Content bounds {x, y, width, height}
     */
    calculateContentBounds(svg) {
        // Get all visual elements
        const allElements = svg.selectAll('g, circle, rect, ellipse, path, line, text, polygon, polyline');
        
        if (allElements.empty()) {
            this.logger.warn('CanvasController', 'No content found in SVG');
            return null;
        }
        
        this.logger.debug('CanvasController', `Found ${allElements.size()} elements in SVG`);
        
        // Calculate the bounding box of all SVG content
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        let hasContent = false;
        
        allElements.each(function() {
            try {
                const bbox = this.getBBox();
                if (bbox.width > 0 && bbox.height > 0) {
                    minX = Math.min(minX, bbox.x);
                    minY = Math.min(minY, bbox.y);
                    maxX = Math.max(maxX, bbox.x + bbox.width);
                    maxY = Math.max(maxY, bbox.y + bbox.height);
                    hasContent = true;
                }
            } catch (e) {
                // Some elements might not have getBBox, skip them
            }
        });
        
        if (!hasContent || minX === Infinity) {
            this.logger.warn('CanvasController', 'No valid content bounds found');
            return null;
        }
        
        return {
            x: minX,
            y: minY,
            width: maxX - minX,
            height: maxY - minY
        };
    }
    
    /**
     * Calculate available canvas width
     * @param {number} containerWidth - Container width
     * @returns {number} Available width
     */
    calculateAvailableWidth(containerWidth) {
        if (!this.isSizedForPanel) {
            return containerWidth;
        }
        
        const panelWidth = this.getActivePanelWidth();
        return containerWidth - panelWidth;
    }
    
    /**
     * Apply viewBox transform to fit content
     * @param {Object} svg - D3 selection of SVG
     * @param {Object} contentBounds - Content bounds
     * @param {number} availableWidth - Available width
     * @param {number} containerHeight - Container height
     * @param {boolean} animate - Whether to animate
     */
    applyViewBoxTransform(svg, contentBounds, availableWidth, containerHeight, animate) {
        try {
            // Calculate scale to fit with padding (85% to add margins)
            const scale = Math.min(
                availableWidth / contentBounds.width,
                containerHeight / contentBounds.height
            ) * 0.85;
            
            // Calculate translation to center the content in available space
            const translateX = (availableWidth - contentBounds.width * scale) / 2 - contentBounds.x * scale;
            const translateY = (containerHeight - contentBounds.height * scale) / 2 - contentBounds.y * scale;
            
            this.logger.debug('CanvasController', 'Applying transform:', { scale, translateX, translateY });
            
            // Make SVG responsive to fill container
            svg.attr('width', '100%')
               .attr('height', '100%');
            
            // Get the current viewBox
            const viewBox = svg.attr('viewBox');
            
            // Calculate optimal viewBox with padding
            const padding = Math.min(contentBounds.width, contentBounds.height) * 0.1; // 10% padding
            const newViewBox = `${contentBounds.x - padding} ${contentBounds.y - padding} ${contentBounds.width + padding * 2} ${contentBounds.height + padding * 2}`;
            
            if (viewBox) {
                this.logger.debug('CanvasController', 'Old viewBox:', viewBox);
                this.logger.debug('CanvasController', 'New viewBox:', newViewBox);
                
                if (animate) {
                    svg.transition()
                        .duration(750)
                        .attr('viewBox', newViewBox);
                } else {
                    svg.attr('viewBox', newViewBox);
                }
            } else {
                // No existing viewBox, create one
                svg.attr('viewBox', newViewBox);
                this.logger.debug('CanvasController', 'Created viewBox:', newViewBox);
            }
            
            this.logger.debug('CanvasController', 'ViewBox transform applied successfully');
            
        } catch (error) {
            this.logger.error('CanvasController', 'Error applying viewBox transform:', error);
        }
    }
    
    /**
     * Check if auto-fit is needed
     */
    checkAutoFitNeeded() {
        try {
            // Skip if Node Palette is active (d3-container is hidden)
            // Use PanelManager instead of direct DOM check
            if (window.panelManager?.isPanelOpen('nodePalette')) {
                const d3Container = document.getElementById('d3-container');
                if (d3Container && d3Container.style.display === 'none') {
                    this.logger.debug('CanvasController', 'Skipping auto-fit check: Node Palette is active');
                    return;
                }
            }
            
            const container = d3.select('#d3-container');
            const svg = container.select('svg');
            
            if (svg.empty()) {
                return;
            }
            
            // Calculate content bounds
            const contentBounds = this.calculateContentBounds(svg);
            
            if (!contentBounds) {
                return;
            }
            
            // Get container dimensions
            const containerNode = container.node();
            const containerWidth = containerNode.clientWidth;
            const containerHeight = containerNode.clientHeight;
            
            // Get SVG dimensions
            const svgWidth = parseFloat(svg.attr('width')) || containerWidth;
            const svgHeight = parseFloat(svg.attr('height')) || containerHeight;
            
            // Check if content exceeds the visible area (with 10% tolerance)
            const exceedsWidth = contentBounds.width > containerWidth * 0.9;
            const exceedsHeight = contentBounds.height > containerHeight * 0.9;
            const exceedsSvgBounds = (contentBounds.x + contentBounds.width > svgWidth * 0.9) || 
                                     (contentBounds.y + contentBounds.height > svgHeight * 0.9);
            
            if (exceedsWidth || exceedsHeight || exceedsSvgBounds) {
                this.logger.debug('CanvasController', 'Diagram exceeds window bounds - auto-fitting to view', {
                    contentBounds,
                    containerSize: { width: containerWidth, height: containerHeight },
                    exceedsWidth,
                    exceedsHeight,
                    exceedsSvgBounds
                });
                
                // Auto-fit with a slight delay to ensure rendering is complete
                setTimeout(() => {
                    this.fitDiagramToWindow();
                }, 100);
            } else {
                this.logger.debug('CanvasController', 'Diagram fits within window - no auto-fit needed');
            }
            
        } catch (error) {
            if (this.logger && this.logger.error) {
                this.logger.error('CanvasController', 'Error in auto-fit check:', error || 'Unknown error');
            }
        }
    }
    
    /**
     * Handle window resize
     */
    handleWindowResize() {
        // Ignore events if already destroyed
        if (this.isDestroyed) {
            return;
        }
        
        this.logger.debug('CanvasController', 'Window resized');
        
        // Emit resize event
        this.eventBus.emit('window:resized', {
            width: window.innerWidth,
            height: window.innerHeight
        });
        
        // Re-fit diagram
        this.fitDiagramToWindow(false);
    }
    
    /**
     * Detect if running on mobile device
     * @returns {boolean}
     */
    detectMobileDevice() {
        return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    }
    
    /**
     * Destroy canvas controller
     */
    destroy() {
        // Set destroyed flag FIRST to prevent any method execution
        this.isDestroyed = true;
        
        this.logger.info('CanvasController', 'Destroying Canvas Controller');
        
        // Remove all Event Bus listeners (using Listener Registry)
        if (this.eventBus && this.ownerId) {
            const removedCount = this.eventBus.removeAllListenersForOwner(this.ownerId);
            if (removedCount > 0) {
                this.logger.debug('CanvasController', `Removed ${removedCount} Event Bus listeners`);
            }
        }
        
        // Nullify references
        this.eventBus = null;
        this.stateManager = null;
        this.logger = null;
    }
}

// Make available globally
window.CanvasController = CanvasController;

