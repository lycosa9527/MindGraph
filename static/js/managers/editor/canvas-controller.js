/**
 * Canvas Controller
 * =================
 * 
 * Manages canvas sizing, responsive layout, and viewport fitting.
 * Handles window resize, panel space adjustments, and zoom/pan.
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 * @size_target ~500-600 lines
 */

class CanvasController {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        
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
        this.eventBus.on('panel:opened', (data) => {
            this.handlePanelChange(data.panel, true);
        });
        
        this.eventBus.on('panel:closed', (data) => {
            this.handlePanelChange(data.panel, false);
        });
        
        // Listen for fit requests
        this.eventBus.on('canvas:fit_requested', (data) => {
            this.fitDiagramToWindow(data?.animate);
        });
        
        // Listen for diagram rendered
        this.eventBus.on('diagram:rendered', () => {
            this.checkAutoFitNeeded();
        });
        
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
            isOpen
        });
        
        if (panelName === 'property' || panelName === 'mindmate') {
            // Adjust canvas for panel
            if (isOpen) {
                this.fitToCanvasWithPanel(true);
            } else {
                this.fitToFullCanvas(true);
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
            this.logger.error('CanvasController', 'Error in auto-fit check:', error);
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
        
        // Unsubscribe from all events
        this.eventBus.off('panel:opened');
        this.eventBus.off('panel:closed');
        this.eventBus.off('canvas:fit_requested');
        this.eventBus.off('diagram:rendered');
        
        // Nullify references
        this.eventBus = null;
        this.stateManager = null;
        this.logger = null;
    }
}

// Make available globally
window.CanvasController = CanvasController;

