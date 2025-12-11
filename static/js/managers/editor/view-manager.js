/**
 * View Manager
 * ============
 * 
 * Manages zoom, pan, and fit-to-canvas operations for diagrams.
 * Handles viewport fitting, zoom controls, and mobile zoom controls.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class ViewManager {
    constructor(eventBus, stateManager, logger, editor) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        this.editor = editor; // Need editor reference for some operations
        
        // NEW: Add owner identifier for Event Bus Listener Registry
        this.ownerId = 'ViewManager';
        
        // Zoom state
        this.zoomBehavior = null;
        this.zoomTransform = null;
        this.currentZoomLevel = null;
        this.isSizedForPanel = false;
        
        // Subscribe to events
        this.subscribeToEvents();
        
        this.logger.info('ViewManager', 'View Manager initialized');
    }
    
    /**
     * Subscribe to Event Bus events
     */
    subscribeToEvents() {
        // Listen for zoom requests
        this.eventBus.onWithOwner('view:zoom_in_requested', () => {
            this.zoomIn();
        }, this.ownerId);
        
        this.eventBus.onWithOwner('view:zoom_out_requested', () => {
            this.zoomOut();
        }, this.ownerId);
        
        // Listen for fit requests
        this.eventBus.onWithOwner('view:fit_to_window_requested', (data) => {
            this.fitToFullCanvas(data?.animate !== false);
        }, this.ownerId);
        
        this.eventBus.onWithOwner('view:fit_to_canvas_requested', (data) => {
            this.fitToCanvasWithPanel(data?.animate !== false);
        }, this.ownerId);
        
        this.eventBus.onWithOwner('view:fit_diagram_requested', () => {
            this.fitDiagramToWindow();
        }, this.ownerId);
        
        // Listen for diagram rendered
        this.eventBus.onWithOwner('diagram:rendered', () => {
            this.autoFitDiagramIfNeeded();
        }, this.ownerId);
        
        // Listen for window resize
        this.eventBus.onWithOwner('window:resized', () => {
            this.handleWindowResize();
        }, this.ownerId);
        
        // Listen for flow map orientation flip
        this.eventBus.onWithOwner('view:flip_orientation_requested', () => {
            this.flipFlowMapOrientation();
        }, this.ownerId);
        
        // Listen for diagram type changes (to update flow map button visibility)
        this.eventBus.onWithOwner('diagram:type_changed', (data) => {
            this.updateFlowMapOrientationButtonVisibility();
        }, this.ownerId);
        
        // Listen for diagram rendered to enable zoom/pan
        this.eventBus.onWithOwner('diagram:rendered', () => {
            // Enable zoom and pan
            this.enableZoomAndPan();
            // Add mobile controls if needed
            if (this.isMobileDevice()) {
                this.addMobileZoomControls();
            }
        }, this.ownerId);
        
        this.logger.debug('ViewManager', 'Subscribed to events');
    }
    
    /**
     * Check if device is mobile
     */
    isMobileDevice() {
        return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
               (window.innerWidth <= 768);
    }
    
    /**
     * Enable zoom and pan on SVG
     */
    enableZoomAndPan() {
        const svg = d3.select('#d3-container svg');
        if (svg.empty()) {
            this.logger.warn('ViewManager', 'No SVG found - zoom/pan disabled');
            return;
        }
        
        // Create a group to hold all content if it doesn't exist
        let contentGroup = svg.select('g.zoom-group');
        if (contentGroup.empty()) {
            // Move all existing SVG children into a group
            const existingChildren = svg.selectAll('*:not(defs)').nodes();
            contentGroup = svg.insert('g', ':first-child')
                .attr('class', 'zoom-group');
            
            existingChildren.forEach(child => {
                contentGroup.node().appendChild(child);
            });
        }
        
        // Configure zoom behavior
        const zoom = d3.zoom()
            .scaleExtent([0.1, 10]) // Allow 10x zoom in, 0.1x zoom out
            .filter((event) => {
                // CRITICAL: Block double-click entirely - should open edit modal, not zoom
                if (event.type === 'dblclick') return false;
                
                // Allow mouse wheel for zooming
                if (event.type === 'wheel') return true;
                
                // For panning: ONLY allow middle mouse button (scroll wheel click)
                // Block left mouse (button 0) and right mouse (button 2)
                if (event.type === 'mousedown') {
                    return event.button === 1; // Only middle mouse button for panning
                }
                
                // Allow other event types (mousemove, mouseup, etc.)
                return true;
            })
            .on('zoom', (event) => {
                contentGroup.attr('transform', event.transform);
                // Update zoom level display if needed
                if (this.currentZoomLevel) {
                    this.currentZoomLevel.textContent = `${Math.round(event.transform.k * 100)}%`;
                }
                
                // Update state (use updateUI method for view state)
                if (this.stateManager && typeof this.stateManager.updateUI === 'function') {
                    this.stateManager.updateUI({
                        zoomLevel: event.transform.k,
                        panX: event.transform.x,
                        panY: event.transform.y
                    });
                }
            });
        
        // Apply zoom behavior to SVG
        svg.call(zoom);
        
        // CRITICAL: Disable default double-click zoom behavior
        // This allows custom double-click handlers (e.g., edit modal) to work properly
        // Per D3.js documentation: https://d3js.org/d3-zoom#zoom
        svg.on('dblclick.zoom', null);
        
        // Store zoom behavior for programmatic control
        this.zoomBehavior = zoom;
        this.zoomTransform = d3.zoomIdentity;
        
        this.logger.debug('ViewManager', 'Zoom and pan enabled (mouse wheel + middle button, double-click disabled)');
    }
    
    /**
     * Add zoom control buttons for mobile
     */
    addMobileZoomControls() {
        // Check if controls already exist
        if (document.getElementById('mobile-zoom-controls')) {
            return;
        }
        
        const controlsHtml = `
            <div id="mobile-zoom-controls" class="mobile-zoom-controls">
                <button id="zoom-in-btn" class="zoom-control-btn" title="Zoom In">
                    <span>+</span>
                </button>
                <button id="zoom-out-btn" class="zoom-control-btn" title="Zoom Out">
                    <span>−</span>
                </button>
                <button id="zoom-reset-btn" class="zoom-control-btn" title="Reset Zoom">
                    <span>⊙</span>
                </button>
            </div>
        `;
        
        // Add to d3-container
        const container = document.getElementById('d3-container');
        if (container) {
            container.insertAdjacentHTML('beforeend', controlsHtml);
            
            // Add event listeners
            document.getElementById('zoom-in-btn').addEventListener('click', () => {
                this.zoomIn();
            });
            
            document.getElementById('zoom-out-btn').addEventListener('click', () => {
                this.zoomOut();
            });
            
            document.getElementById('zoom-reset-btn').addEventListener('click', () => {
                this.fitDiagramToWindow();
            });
            
            this.logger.debug('ViewManager', 'Mobile zoom controls added');
        }
    }
    
    /**
     * Show flow map orientation button in toolbar (only for flow_map diagram type)
     */
    updateFlowMapOrientationButtonVisibility() {
        const btn = document.getElementById('flow-map-orientation-btn');
        if (!btn) {
            return;
        }
        
        // Get diagram type from state or editor
        const diagramType = this.editor?.diagramType || 
                           this.stateManager.getState().diagram?.type;
        
        // CRITICAL: Button should ONLY appear for flow_map diagram type
        // Use setProperty with !important to override any CSS rules that might show it
        if (diagramType === 'flow_map') {
            // Show button (match other toolbar buttons' display style)
            btn.style.setProperty('display', 'inline-flex', 'important');
            this.logger.debug('ViewManager', 'Flow map orientation button shown', {
                diagramType: diagramType
            });
        } else {
            // Explicitly hide for all other diagram types with !important
            btn.style.setProperty('display', 'none', 'important');
        }
    }
    
    /**
     * Flip flow map orientation between vertical and horizontal
     */
    flipFlowMapOrientation() {
        if (!this.editor) {
            this.logger.warn('ViewManager', 'Editor reference not available for orientation flip');
            return;
        }
        
        const currentSpec = this.editor.currentSpec;
        const diagramType = this.editor.diagramType;
        
        if (!currentSpec || diagramType !== 'flow_map') {
            return;
        }
        
        // Toggle orientation
        const currentOrientation = currentSpec.orientation || 'vertical';
        const newOrientation = currentOrientation === 'vertical' ? 'horizontal' : 'vertical';
        currentSpec.orientation = newOrientation;
        
        // Emit event to save to history (via HistoryManager)
        this.eventBus.emit('diagram:operation_completed', {
            operation: 'flip_orientation',
            snapshot: JSON.parse(JSON.stringify(currentSpec)),
            data: { orientation: newOrientation }
        });
        
        // Emit event to re-render diagram
        this.eventBus.emit('diagram:render_requested', {
            spec: currentSpec
        });
        
        this.logger.debug('ViewManager', `Flow map orientation flipped to: ${newOrientation}`);
        
        // Emit completion event
        this.eventBus.emit('view:orientation_flipped', {
            orientation: newOrientation
        });
    }
    
    /**
     * Zoom in programmatically
     */
    zoomIn() {
        const svg = d3.select('#d3-container svg');
        if (svg.empty() || !this.zoomBehavior) return;
        
        svg.transition()
            .duration(300)
            .call(this.zoomBehavior.scaleBy, 1.3);
        
        // Emit zoom event
        this.eventBus.emit('view:zoomed', { 
            direction: 'in',
            level: this.zoomTransform?.k || 1
        });
    }
    
    /**
     * Zoom out programmatically
     */
    zoomOut() {
        const svg = d3.select('#d3-container svg');
        if (svg.empty() || !this.zoomBehavior) return;
        
        svg.transition()
            .duration(300)
            .call(this.zoomBehavior.scaleBy, 0.77);
        
        // Emit zoom event
        this.eventBus.emit('view:zoomed', { 
            direction: 'out',
            level: this.zoomTransform?.k || 1
        });
    }
    
    /**
     * Calculate adaptive dimensions based on current window size
     * This ensures templates are sized appropriately for the user's screen
     * CRITICAL: Always reserves space for properties panel to prevent overlap when clicking nodes
     */
    calculateAdaptiveDimensions() {
        try {
            // Get current window dimensions
            const windowWidth = window.innerWidth;
            const windowHeight = window.innerHeight;
            
            // Calculate available canvas space (accounting for toolbar and status bar)
            // Toolbar height: ~60px, Status bar height: ~40px
            const toolbarHeight = 60;
            const statusBarHeight = 40;
            const availableHeight = windowHeight - toolbarHeight - statusBarHeight;
            
            // CRITICAL: Always reserve space for properties panel to prevent diagram overlap
            // When user clicks a node, the properties panel will appear and should not cover the diagram
            const propertyPanelWidth = 320;
            const availableWidth = windowWidth - propertyPanelWidth;
            
            // Calculate optimal dimensions with appropriate padding for visual comfort
            // Use 85% of available space to ensure good margins and prevent edge clipping
            const widthUsageRatio = 0.85;
            const heightUsageRatio = 0.88;
            
            // Calculate optimal dimensions with padding
            const padding = Math.min(40, Math.max(20, Math.min(availableWidth, availableHeight) * 0.05));
            
            // Ensure minimum dimensions for readability (especially on smaller screens)
            const minWidth = 400;
            const minHeight = 300;
            
            const adaptiveWidth = Math.max(minWidth, availableWidth * widthUsageRatio);
            const adaptiveHeight = Math.max(minHeight, availableHeight * heightUsageRatio);
            
            const dimensions = {
                width: Math.round(adaptiveWidth),
                height: Math.round(adaptiveHeight),
                padding: Math.round(padding)
            };
            
            this.logger.debug('ViewManager', 'Calculated adaptive dimensions (reserved space for properties panel):', {
                windowSize: { width: windowWidth, height: windowHeight },
                reservedForPropertyPanel: propertyPanelWidth,
                availableSpace: { width: availableWidth, height: availableHeight },
                usageRatios: { width: widthUsageRatio, height: heightUsageRatio },
                finalDimensions: dimensions
            });
            
            return dimensions;
            
        } catch (error) {
            this.logger.error('ViewManager', 'Failed to calculate adaptive dimensions', error);
            // Fallback to reasonable defaults
            return {
                width: 800,
                height: 600,
                padding: 40
            };
        }
    }

    /**
     * Check if a panel is currently visible
     * @private
     * @returns {boolean} True if any panel is visible
     */
    _isPanelVisible() {
        const propertyPanel = document.getElementById('property-panel');
        const isPropertyPanelVisible = propertyPanel && propertyPanel.style.display !== 'none';
        
        const aiPanel = document.getElementById('ai-assistant-panel');
        const isAIPanelVisible = aiPanel && !aiPanel.classList.contains('collapsed');
        
        const thinkingPanel = document.getElementById('thinking-panel');
        const isThinkingPanelVisible = thinkingPanel && !thinkingPanel.classList.contains('collapsed');
        
        return isPropertyPanelVisible || isAIPanelVisible || isThinkingPanelVisible;
    }

    /**
     * Fit diagram to full canvas area (entire window width)
     * Used when properties panel is hidden - diagram expands to full width
     * @param {boolean} animate - Whether to animate the transition (default: true)
     */
    fitToFullCanvas(animate = true) {
        try {
            // Smart check: Skip if already fitted to full canvas and no panel is visible
            const isPanelVisible = this._isPanelVisible();
            if (!this.isSizedForPanel && !isPanelVisible) {
                this.logger.debug('ViewManager', 'Already fitted to full canvas with no panels - skipping fit');
                return;
            }
            
            // CRITICAL: Remove canvas panel classes BEFORE fitting to ensure correct width calculation
            // This prevents viewBox from being calculated with constrained width during CSS transition
            const canvasPanel = document.querySelector('.canvas-panel');
            if (canvasPanel) {
                canvasPanel.classList.remove('property-panel-visible', 'ai-panel-visible', 'thinking-panel-visible');
            }
            
            // Force immediate layout recalculation before fitting
            // This ensures container width is updated before viewBox calculation
            // Even with CSS transitions, we need the container to report correct width
            const containerNode = document.querySelector('#d3-container');
            if (containerNode && containerNode.parentElement) {
                // Force reflow by reading offsetHeight of parent
                containerNode.parentElement.offsetHeight;
            }
            
            this.logger.debug('ViewManager', 'Fitting to full canvas width');
            // Calculate immediately - reflow was forced above, container should report correct width
            this._fitToCanvas(animate, false);
            this.isSizedForPanel = false; // Update state
            
            // Update state manager (view state tracking is optional)
            // View state is managed by ViewManager, not StateManager
            
            // Emit event
            this.eventBus.emit('view:fitted', {
                mode: 'full_canvas',
                animate: animate
            });
        } catch (error) {
            this.logger.error('ViewManager', 'Failed to fit to full canvas', error);
        }
    }

    /**
     * Fit diagram to canvas with properties panel space reserved
     * Used when properties panel is visible or will be visible - reserves 320px for panel
     * Always fits when called (e.g., when node is clicked and property panel opens)
     * @param {boolean} animate - Whether to animate the transition (default: true)
     */
    fitToCanvasWithPanel(animate = true) {
        try {
            // Smart check: Skip if already fitted with panel and panel is visible
            // This prevents unnecessary animations when clicking different nodes while panel is already open
            const isPanelVisible = this._isPanelVisible();
            if (this.isSizedForPanel && isPanelVisible) {
                this.logger.debug('ViewManager', 'Already fitted with panel visible - skipping fit');
                return;
            }
            
            this.logger.debug('ViewManager', 'Fitting to canvas (panel space reserved)');
            this._fitToCanvas(animate, true);
            this.isSizedForPanel = true; // Update state
            
            // Update state manager (view state tracking is optional)
            // View state is managed by ViewManager, not StateManager
            
            // Emit event
            this.eventBus.emit('view:fitted', {
                mode: 'canvas_with_panel',
                animate: animate
            });
        } catch (error) {
            this.logger.error('ViewManager', 'Error fitting to canvas with panel:', error);
        }
    }

    /**
     * Internal method: Fit diagram to canvas area
     * @private
     * @param {boolean} animate - Whether to animate the transition
     * @param {boolean} reserveForPanel - Whether to reserve space for properties panel (320px)
     */
    _fitToCanvas(animate, reserveForPanel) {
        const container = d3.select('#d3-container');
        const svg = container.select('svg');
        
        if (svg.empty()) {
            this.logger.warn('ViewManager', 'No SVG found for auto-fit');
            return;
        }
        
        // Get all visual elements to calculate content bounds
        const allElements = svg.selectAll('g, circle, rect, ellipse, path, line, text, polygon, polyline');
        
        if (allElements.empty()) {
            this.logger.warn('ViewManager', 'No content found for auto-fit');
            return;
        }
        
        // Calculate content bounds
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
                // Skip elements without getBBox
            }
        });
        
        if (!hasContent) {
            this.logger.warn('ViewManager', 'No valid content for auto-fit');
            return;
        }
        
        const contentBounds = {
            x: minX,
            y: minY,
            width: maxX - minX,
            height: maxY - minY
        };
        
        // Check panel visibility for CSS class updates
        const propertyPanel = document.getElementById('property-panel');
        const isPropertyPanelVisible = propertyPanel && propertyPanel.style.display !== 'none';
        
        const aiPanel = document.getElementById('ai-assistant-panel');
        const isAIPanelVisible = aiPanel && !aiPanel.classList.contains('collapsed');
        
        const thinkingPanel = document.getElementById('thinking-panel');
        const isThinkingPanelVisible = thinkingPanel && !thinkingPanel.classList.contains('collapsed');
        
        // Update canvas panel classes for dynamic width adjustment
        // Note: Classes are already removed by fitToFullCanvas when reserveForPanel is false
        // Only update classes when reserving panel space
        const canvasPanel = document.querySelector('.canvas-panel');
        if (canvasPanel && reserveForPanel) {
            canvasPanel.classList.toggle('property-panel-visible', isPropertyPanelVisible);
            canvasPanel.classList.toggle('ai-panel-visible', isAIPanelVisible && !isPropertyPanelVisible);
            canvasPanel.classList.toggle('thinking-panel-visible', isThinkingPanelVisible && !isPropertyPanelVisible);
        }
        
        // Force a reflow to ensure CSS changes are applied before measuring container
        // This is critical when transitioning from panel-constrained to full canvas
        if (canvasPanel) {
            canvasPanel.offsetHeight; // Force reflow
        }
        
        // Get container dimensions AFTER CSS classes are updated and reflow is forced
        // This ensures we get the actual current width, not a stale constrained width
        const containerNode = container.node();
        let containerWidth = containerNode.clientWidth;
        const containerHeight = containerNode.clientHeight;
        const windowWidth = window.innerWidth;
        
        // Calculate available canvas width based on reserveForPanel parameter and active panels
        // CRITICAL: When reserveForPanel is false, use actual containerWidth (which should now be full width)
        // When reserveForPanel is true, use windowWidth minus reserved space
        const propertyPanelWidth = 320;
        const thinkingPanelWidth = 400;  // ThinkGuide panel width
        const aiPanelWidth = 450;        // AI Assistant panel width
        
        let reservedWidth = 0;
        if (reserveForPanel && isPropertyPanelVisible) {
            reservedWidth = propertyPanelWidth;
        } else if (isThinkingPanelVisible) {
            reservedWidth = thinkingPanelWidth;
        } else if (isAIPanelVisible) {
            reservedWidth = aiPanelWidth;
        }
        
        // When reserveForPanel is false, use actual containerWidth (should be full width after class removal)
        // When reserveForPanel is true, use windowWidth minus reserved space (panel will constrain via CSS)
        const availableCanvasWidth = reserveForPanel 
            ? (windowWidth - reservedWidth)  // Panel space reserved: use windowWidth minus reserved
            : containerWidth;                // Full canvas: use actual containerWidth after CSS class removal
        
        this.logger.debug('ViewManager', 'Canvas fit calculation:', {
            mode: reservedWidth > 0 ? `WITH ${reservedWidth}px panel reserved` : 'FULL width',
            reserveForPanel: reserveForPanel,
            windowWidth,
            containerSize: { width: containerWidth, height: containerHeight },
            isPropertyPanelVisible,
            isThinkingPanelVisible,
            isAIPanelVisible,
            reservedWidth,
            availableCanvasWidth,
            calculationMethod: reserveForPanel ? 'windowWidth - reserved' : 'containerWidth (after CSS update)',
            contentBounds,
            animate
        });
        
        // Calculate scale to fit available space with padding
        const padding = 0.12; // 12% padding around content for visual comfort
        const scale = Math.min(
            (availableCanvasWidth * (1 - 2 * padding)) / contentBounds.width,
            (containerHeight * (1 - 2 * padding)) / contentBounds.height
        );
        
        // Don't shrink diagrams that are already reasonably sized
        const minScale = Math.min(
            (availableCanvasWidth * 0.6) / contentBounds.width,
            (containerHeight * 0.6) / contentBounds.height
        );
        const finalScale = Math.max(scale, minScale);
        
        // Calculate viewBox to center content in available space
        // First, calculate content center point
        const contentCenterX = contentBounds.x + contentBounds.width / 2;
        const contentCenterY = contentBounds.y + contentBounds.height / 2;
        
        // Calculate viewBox dimensions in SVG coordinate space
        // These dimensions represent how much SVG space is visible in the viewport
        const viewBoxWidth = availableCanvasWidth / finalScale;
        const viewBoxHeight = containerHeight / finalScale;
        
            // Calculate viewBox position to center content within the viewBox
            // The viewBox should be positioned so that the content center aligns with viewBox center
            // This ensures content is centered regardless of its position in SVG coordinate space
            const viewBoxX = contentCenterX - viewBoxWidth / 2;
            const viewBoxY = contentCenterY - viewBoxHeight / 2;
            
            const newViewBox = `${viewBoxX} ${viewBoxY} ${viewBoxWidth} ${viewBoxHeight}`;
            
            this.logger.debug('ViewManager', 'Fit calculation result:', {
                availableCanvasWidth,
                finalScale: finalScale,
                contentCenter: { x: contentCenterX, y: contentCenterY },
                viewBox: newViewBox
            });
            
            // Apply viewBox with or without animation
            // Note: Canvas panel classes are updated by PanelManager when panel opens
            // to trigger CSS width transitions that coordinate with this viewBox animation
        // Coordinate animation duration with CSS transitions:
        // - Panel slide animation: 0.3s
        // - Canvas width transition: 0.4s (cubic-bezier)
        // - ViewBox animation: 0.5s (slightly longer than canvas width for smooth feel)
        if (animate) {
            svg.transition()
                .duration(500) // Reduced from 750ms to coordinate with CSS transitions
                .ease(d3.easeCubicOut) // Match the cubic-bezier easing of canvas width transition
                .attr('viewBox', newViewBox)
                .attr('preserveAspectRatio', 'xMidYMid meet');
        } else {
            svg.attr('viewBox', newViewBox)
                .attr('preserveAspectRatio', 'xMidYMid meet');
        }
        
        this.logger.debug('ViewManager', `Diagram fitted ${animate ? 'with animation' : 'instantly'}`);
    }

    /**
     * Auto-fit diagram to window if it exceeds viewport bounds
     */
    autoFitDiagramIfNeeded() {
        try {
            const container = d3.select('#d3-container');
            const svg = container.select('svg');
            
            if (svg.empty()) {
                return;
            }
            
            // Get all visual elements
            const allElements = svg.selectAll('g, circle, rect, ellipse, path, line, text, polygon, polyline');
            
            if (allElements.empty()) {
                return;
            }
            
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
                    // Skip elements without getBBox
                }
            });
            
            if (!hasContent || minX === Infinity) {
                return;
            }
            
            const contentBounds = {
                x: minX,
                y: minY,
                width: maxX - minX,
                height: maxY - minY
            };
            
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
                this.logger.debug('ViewManager', 'Diagram exceeds window bounds - auto-fitting to view', {
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
                this.logger.debug('ViewManager', 'Diagram fits within window - no auto-fit needed');
            }
            
        } catch (error) {
            this.logger.error('ViewManager', 'Error in auto-fit check:', error);
        }
    }
    
    /**
     * Fit diagram to window - calculates diagram bounds and centers it
     */
    fitDiagramToWindow() {
        try {
            this.logger.debug('ViewManager', 'Reset View clicked - fitting diagram to window');
            
            const container = d3.select('#d3-container');
            const svg = container.select('svg');
            
            if (svg.empty()) {
                this.logger.warn('ViewManager', 'No SVG found, cannot reset view');
                return;
            }
            
            // CRITICAL: Reset zoom transform first before calculating bounds
            // This ensures bounds are calculated correctly regardless of current zoom/pan state
            const zoomGroup = svg.select('g.zoom-group');
            if (!zoomGroup.empty() && this.zoomBehavior) {
                // Reset zoom transform to identity (no zoom, no pan)
                svg.call(this.zoomBehavior.transform, d3.zoomIdentity);
                this.zoomTransform = d3.zoomIdentity;
                this.logger.debug('ViewManager', 'Reset zoom transform to identity');
            }
            
            // Calculate bounds immediately (transform reset is synchronous)
            this._calculateAndFitBounds(svg, container);
            
        } catch (error) {
            this.logger.error('ViewManager', 'Error fitting diagram to window:', error);
        }
    }
    
    /**
     * Calculate bounds and fit diagram (called after zoom reset)
     * @private
     */
    _calculateAndFitBounds(svg, container) {
        try {
            // Get all visual elements - check both zoom-group and direct children
            // For mindmaps, elements are direct children of SVG (no zoom-group)
            const zoomGroup = svg.select('g.zoom-group');
            let allElements;
            
            if (!zoomGroup.empty()) {
                // Elements are in zoom-group (for other diagram types)
                allElements = zoomGroup.selectAll('g, circle, rect, ellipse, path, line, text, polygon, polyline');
            } else {
                // Elements are direct children of SVG (mindmaps)
                // Include all visual elements, excluding background rect
                allElements = svg.selectAll('g, circle, rect:not(.background), ellipse, path, line, text, polygon, polyline');
            }
            
            if (allElements.empty()) {
                this.logger.warn('ViewManager', 'No content found in SVG');
                return;
            }
            
            this.logger.debug('ViewManager', `Found ${allElements.size()} elements in SVG (zoom-group: ${!zoomGroup.empty()})`);
            
            // Calculate the bounding box of all SVG content
            // Use more comprehensive approach to ensure all content is included
            let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
            let hasContent = false;
            
            // First pass: get bounds from all elements
            allElements.each(function() {
                try {
                    const bbox = this.getBBox();
                    if (bbox && bbox.width > 0 && bbox.height > 0 && isFinite(bbox.x) && isFinite(bbox.y)) {
                        minX = Math.min(minX, bbox.x);
                        minY = Math.min(minY, bbox.y);
                        maxX = Math.max(maxX, bbox.x + bbox.width);
                        maxY = Math.max(maxY, bbox.y + bbox.height);
                        hasContent = true;
                    }
                } catch (e) {
                    // Skip elements without getBBox - try alternative methods
                    try {
                        // For elements without getBBox, try to get coordinates from attributes
                        const x = parseFloat(this.getAttribute('x') || this.getAttribute('x1') || 0);
                        const y = parseFloat(this.getAttribute('y') || this.getAttribute('y1') || 0);
                        const width = parseFloat(this.getAttribute('width') || 0);
                        const height = parseFloat(this.getAttribute('height') || 0);
                        const x2 = parseFloat(this.getAttribute('x2') || x);
                        const y2 = parseFloat(this.getAttribute('y2') || y);
                        
                        if (isFinite(x) && isFinite(y)) {
                            minX = Math.min(minX, x, x2);
                            minY = Math.min(minY, y, y2);
                            maxX = Math.max(maxX, x + width, x2);
                            maxY = Math.max(maxY, y + height, y2);
                            hasContent = true;
                        }
                    } catch (e2) {
                        // Skip this element
                    }
                }
            });
            
            // Second pass: also check text elements which might extend beyond their bbox
            const textElements = zoomGroup.empty() 
                ? svg.selectAll('text')
                : zoomGroup.selectAll('text');
            
            textElements.each(function() {
                try {
                    const bbox = this.getBBox();
                    if (bbox && isFinite(bbox.x) && isFinite(bbox.y)) {
                        // Text elements might have negative coordinates or extend beyond
                        minX = Math.min(minX, bbox.x);
                        minY = Math.min(minY, bbox.y);
                        maxX = Math.max(maxX, bbox.x + bbox.width);
                        maxY = Math.max(maxY, bbox.y + bbox.height);
                        hasContent = true;
                    }
                } catch (e) {
                    // Skip text elements without getBBox
                }
            });
            
            if (!hasContent || !isFinite(minX) || !isFinite(minY)) {
                this.logger.warn('ViewManager', 'No valid content bounds found', {
                    hasContent,
                    minX,
                    minY,
                    elementCount: allElements.size()
                });
                return;
            }
            
            const contentBounds = {
                x: minX,
                y: minY,
                width: maxX - minX,
                height: maxY - minY
            };
            
            this.logger.debug('ViewManager', 'Content bounds:', contentBounds);
            
            // Get container dimensions - account for properties panel space
            const containerNode = container.node();
            const containerWidth = containerNode.clientWidth;
            const containerHeight = containerNode.clientHeight;
            
            // Check panel visibility
            const propertyPanel = document.getElementById('property-panel');
            const isPropertyPanelVisible = propertyPanel && propertyPanel.style.display !== 'none';
            this.logger.debug('ViewManager', 'DEBUG: Property panel check:', {
                panelExists: !!propertyPanel,
                displayStyle: propertyPanel?.style.display,
                isVisible: isPropertyPanelVisible
            });
            
            const aiPanel = document.getElementById('ai-assistant-panel');
            const isAIPanelVisible = aiPanel && !aiPanel.classList.contains('collapsed');
            
            // Update canvas panel classes for visual feedback (border, shadow, etc.)
            const canvasPanel = document.querySelector('.canvas-panel');
            if (canvasPanel) {
                canvasPanel.classList.toggle('property-panel-visible', isPropertyPanelVisible);
                canvasPanel.classList.toggle('ai-panel-visible', isAIPanelVisible && !isPropertyPanelVisible);
                this.logger.debug('ViewManager', 'DEBUG: Canvas panel classes updated:', {
                    hasPropertyClass: canvasPanel.classList.contains('property-panel-visible'),
                    hasAIClass: canvasPanel.classList.contains('ai-panel-visible'),
                    allClasses: canvasPanel.className
                });
            }
            
            // Calculate available width manually (don't wait for CSS transition)
            let availableCanvasWidth = containerWidth;
            if (isPropertyPanelVisible) {
                availableCanvasWidth = containerWidth - 320; // Property panel width
            } else if (isAIPanelVisible) {
                availableCanvasWidth = containerWidth - 420; // AI panel width
            }
            
            this.logger.debug('ViewManager', 'Container dimensions:', { 
                containerWidth, 
                containerHeight,
                panelReduction: containerWidth - availableCanvasWidth 
            });
            this.logger.debug('ViewManager', 'Available canvas space:', { 
                availableCanvasWidth, 
                propertyPanelVisible: isPropertyPanelVisible, 
                aiPanelVisible: isAIPanelVisible 
            });
            
            // Continue with the rest of the fitting logic
            this._applyViewBoxTransform(svg, contentBounds, availableCanvasWidth, containerHeight);
            
            // Emit event
            this.eventBus.emit('view:fitted', {
                mode: 'diagram_to_window'
            });
        } catch (error) {
            this.logger.error('ViewManager', 'Error calculating and fitting bounds:', error);
        }
    }
    
    /**
     * Apply viewBox transform to fit content
     * @private
     */
    _applyViewBoxTransform(svg, contentBounds, availableCanvasWidth, containerHeight) {
        try {
            // Calculate scale to fit with padding (85% to add margins)
            // Use available canvas width (accounting for properties panel)
            const scale = Math.min(
                availableCanvasWidth / contentBounds.width,
                containerHeight / contentBounds.height
            ) * 0.85;
            
            // Calculate translation to center the content in available space
            const translateX = (availableCanvasWidth - contentBounds.width * scale) / 2 - contentBounds.x * scale;
            const translateY = (containerHeight - contentBounds.height * scale) / 2 - contentBounds.y * scale;
            
            this.logger.debug('ViewManager', 'Applying transform:', { scale, translateX, translateY });
            
            // Make SVG responsive to fill container
            // But preserve original dimensions for proper bounds calculation
            const originalWidth = parseFloat(svg.attr('width')) || availableCanvasWidth;
            const originalHeight = parseFloat(svg.attr('height')) || containerHeight;
            
            svg.attr('width', '100%')
               .attr('height', '100%');
            
            // Get the current viewBox or create one
            const viewBox = svg.attr('viewBox');
            
            // If content extends beyond original SVG dimensions, expand viewBox accordingly
            const contentRight = contentBounds.x + contentBounds.width;
            const contentBottom = contentBounds.y + contentBounds.height;
            const needsExpansion = contentRight > originalWidth || contentBottom > originalHeight || 
                                  contentBounds.x < 0 || contentBounds.y < 0;
            
            if (needsExpansion) {
                this.logger.debug('ViewManager', 'Content extends beyond SVG bounds, expanding viewBox', {
                    contentBounds,
                    originalWidth,
                    originalHeight,
                    contentRight,
                    contentBottom
                });
            }
            
            // Calculate optimal viewBox with padding
            // Use larger padding for better visibility, especially for larger diagrams
            // Base padding on content size but ensure minimum padding
            const minPadding = 50; // Minimum padding in pixels
            const relativePadding = Math.max(
                contentBounds.width * 0.15,  // 15% of width
                contentBounds.height * 0.15, // 15% of height
                minPadding                    // Minimum padding
            );
            const padding = Math.min(relativePadding, Math.max(contentBounds.width, contentBounds.height) * 0.2); // Cap at 20%
            
            const newViewBox = `${contentBounds.x - padding} ${contentBounds.y - padding} ${contentBounds.width + padding * 2} ${contentBounds.height + padding * 2}`;
            
            this.logger.debug('ViewManager', 'ViewBox calculation:', {
                contentBounds,
                padding,
                newViewBox
            });
            
            if (viewBox) {
                this.logger.debug('ViewManager', 'Old viewBox:', viewBox);
                this.logger.debug('ViewManager', 'New viewBox:', newViewBox);
                
                svg.transition()
                    .duration(750)
                    .attr('viewBox', newViewBox);
                    
                this.logger.debug('ViewManager', 'Diagram fitted to window (existing viewBox)', {
                    bounds: contentBounds,
                    oldViewBox: viewBox,
                    newViewBox: newViewBox
                });
            } else {
                // No viewBox exists - create one
                this.logger.debug('ViewManager', 'No viewBox found, creating one:', newViewBox);
                
                svg.transition()
                    .duration(750)
                    .attr('viewBox', newViewBox)
                    .attr('preserveAspectRatio', 'xMidYMid meet');
                    
                this.logger.debug('ViewManager', 'Diagram fitted to window (created viewBox)', {
                    bounds: contentBounds,
                    newViewBox: newViewBox
                });
            }
            
        } catch (error) {
            this.logger.error('ViewManager', 'Error applying viewBox transform:', error);
        }
    }
    
    /**
     * Fit diagram for export - ensures full diagram is captured, not just visible area
     * Resets zoom/pan and sets viewBox to show all content with minimal padding
     * This method is called synchronously before export, so no animation
     */
    fitDiagramForExport() {
        try {
            this.logger.debug('ViewManager', 'Fitting diagram for export');
            
            const container = d3.select('#d3-container');
            const svg = container.select('svg');
            
            if (svg.empty()) {
                this.logger.warn('ViewManager', 'No SVG found for export fit');
                return;
            }
            
            // CRITICAL: Reset zoom transform first before calculating bounds
            // This works for diagrams with zoom-group (most diagrams) and without (multiflow map, etc.)
            const zoomGroup = svg.select('g.zoom-group');
            if (!zoomGroup.empty() && this.zoomBehavior) {
                // Reset zoom transform to identity (no zoom, no pan)
                svg.call(this.zoomBehavior.transform, d3.zoomIdentity);
                this.zoomTransform = d3.zoomIdentity;
                this.logger.debug('ViewManager', 'Reset zoom transform for export');
            } else if (this.zoomBehavior) {
                // Even without zoom-group, reset the zoom behavior if it exists
                // This handles cases where zoom was applied but zoom-group wasn't created
                try {
                    svg.call(this.zoomBehavior.transform, d3.zoomIdentity);
                    this.zoomTransform = d3.zoomIdentity;
                    this.logger.debug('ViewManager', 'Reset zoom transform (no zoom-group)');
                } catch (e) {
                    this.logger.debug('ViewManager', 'Could not reset zoom transform', e);
                }
            }
            
            // Get all visual elements - check both zoom-group and direct children
            let allElements;
            if (!zoomGroup.empty()) {
                allElements = zoomGroup.selectAll('g, circle, rect, ellipse, path, line, text, polygon, polyline');
            } else {
                allElements = svg.selectAll('g, circle, rect:not(.background), ellipse, path, line, text, polygon, polyline');
            }
            
            if (allElements.empty()) {
                this.logger.warn('ViewManager', 'No content found for export fit');
                return;
            }
            
            // Calculate content bounds
            let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
            let hasContent = false;
            
            allElements.each(function() {
                try {
                    const bbox = this.getBBox();
                    if (bbox && bbox.width > 0 && bbox.height > 0 && isFinite(bbox.x) && isFinite(bbox.y)) {
                        minX = Math.min(minX, bbox.x);
                        minY = Math.min(minY, bbox.y);
                        maxX = Math.max(maxX, bbox.x + bbox.width);
                        maxY = Math.max(maxY, bbox.y + bbox.height);
                        hasContent = true;
                    }
                } catch (e) {
                    // Skip elements without getBBox
                }
            });
            
            // Also check text elements
            const textElements = zoomGroup.empty() 
                ? svg.selectAll('text')
                : zoomGroup.selectAll('text');
            
            textElements.each(function() {
                try {
                    const bbox = this.getBBox();
                    if (bbox && isFinite(bbox.x) && isFinite(bbox.y)) {
                        minX = Math.min(minX, bbox.x);
                        minY = Math.min(minY, bbox.y);
                        maxX = Math.max(maxX, bbox.x + bbox.width);
                        maxY = Math.max(maxY, bbox.y + bbox.height);
                        hasContent = true;
                    }
                } catch (e) {
                    // Skip text elements without getBBox
                }
            });
            
            if (!hasContent || !isFinite(minX) || !isFinite(minY)) {
                this.logger.warn('ViewManager', 'No valid content bounds found for export');
                return;
            }
            
            const contentBounds = {
                x: minX,
                y: minY,
                width: maxX - minX,
                height: maxY - minY
            };
            
            // For export, use minimal padding (just enough to avoid edge clipping)
            const padding = 20;
            const newViewBox = `${contentBounds.x - padding} ${contentBounds.y - padding} ${contentBounds.width + padding * 2} ${contentBounds.height + padding * 2}`;
            
            // Apply viewBox immediately (no animation for export)
            svg.attr('viewBox', newViewBox)
               .attr('preserveAspectRatio', 'xMidYMid meet');
            
            this.logger.debug('ViewManager', 'Diagram fitted for export', {
                contentBounds,
                viewBox: newViewBox
            });
            
        } catch (error) {
            this.logger.error('ViewManager', 'Error fitting diagram for export:', error);
        }
    }
    
    /**
     * Handle window resize
     */
    handleWindowResize() {
        // Debounce resize handling
        if (this.resizeTimeout) {
            clearTimeout(this.resizeTimeout);
        }
        
        this.resizeTimeout = setTimeout(() => {
            // Auto-fit if diagram is currently fitted
            if (this.isSizedForPanel) {
                this.fitToCanvasWithPanel(true);
            } else {
                this.fitToFullCanvas(true);
            }
        }, 150);
    }
    
    /**
     * Cleanup on destroy
     */
    destroy() {
        this.logger.debug('ViewManager', 'Destroying');
        
        // Remove all Event Bus listeners
        if (this.eventBus && this.ownerId) {
            const removedCount = this.eventBus.removeAllListenersForOwner(this.ownerId);
            if (removedCount > 0) {
                this.logger.debug('ViewManager', `Removed ${removedCount} listeners`);
            }
        }
        
        // Clear resize timeout
        if (this.resizeTimeout) {
            clearTimeout(this.resizeTimeout);
        }
        
        // Remove mobile zoom controls if they exist
        const controls = document.getElementById('mobile-zoom-controls');
        if (controls) {
            controls.remove();
        }
        
        // Clear references
        this.zoomBehavior = null;
        this.zoomTransform = null;
        this.currentZoomLevel = null;
        this.editor = null;
    }
}

