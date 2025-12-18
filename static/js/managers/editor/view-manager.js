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
        
        // ===========================================
        // FIT EVENTS - Simple, consistent behavior
        // All fit events: reset zoom transform + apply viewBox fit
        // NO smart checks - always perform the fit
        // ===========================================
        
        // Fit to full canvas (no panel space reserved)
        this.eventBus.onWithOwner('view:fit_to_window_requested', (data) => {
            const animate = data?.animate !== false;
            this.fitToFullCanvas(animate);
        }, this.ownerId);
        
        // Fit to canvas with panel space reserved
        this.eventBus.onWithOwner('view:fit_to_canvas_requested', (data) => {
            const animate = data?.animate !== false;
            this.fitToCanvasWithPanel(animate);
        }, this.ownerId);
        
        // Reset View button - smart fit based on panel visibility
        this.eventBus.onWithOwner('view:fit_diagram_requested', () => {
            const isPanelVisible = this._isPanelVisible();
            this.logger.debug('ViewManager', 'Reset View - panel visible:', isPanelVisible);
            if (isPanelVisible) {
                this.fitToCanvasWithPanel(true);
            } else {
                this.fitToFullCanvas(true);
            }
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
        
        // CRITICAL: Remove existing zoom behavior before re-attaching
        // This prevents duplicate event handlers and ensures clean state
        if (this.zoomBehavior) {
            svg.on('.zoom', null);
        }
        
        // Get or create zoom-group
        let contentGroup = svg.select('g.zoom-group');
        if (contentGroup.empty()) {
            // Move all existing SVG children into a group
            const existingChildren = svg.selectAll('*:not(defs)').nodes();
            contentGroup = svg.insert('g', ':first-child')
                .attr('class', 'zoom-group');
            
            existingChildren.forEach(child => {
                // Skip if child is already a zoom-group (shouldn't happen, but safety check)
                if (child !== contentGroup.node() && child.getAttribute('class') !== 'zoom-group') {
                    contentGroup.node().appendChild(child);
                }
            });
        }
        
        // Get current transform from existing zoom-group if it exists
        // This preserves zoom/pan state across re-renders
        let currentTransform = d3.zoomIdentity;
        if (!contentGroup.empty()) {
            const existingTransform = contentGroup.attr('transform');
            if (existingTransform && existingTransform !== 'none') {
                try {
                    // D3 stores transform as: translate(x,y) scale(k) or matrix(a,b,c,d,e,f)
                    // Try to parse translate/scale format first
                    const translateMatch = existingTransform.match(/translate\(([^)]+)\)/);
                    const scaleMatch = existingTransform.match(/scale\(([^)]+)\)/);
                    
                    if (translateMatch && scaleMatch) {
                        const [tx, ty] = translateMatch[1].split(',').map(s => parseFloat(s.trim()));
                        const k = parseFloat(scaleMatch[1]);
                        if (!isNaN(tx) && !isNaN(ty) && !isNaN(k)) {
                            currentTransform = d3.zoomIdentity.translate(tx, ty).scale(k);
                        }
                    } else {
                        // Try matrix format: matrix(a,b,c,d,e,f)
                        const matrixMatch = existingTransform.match(/matrix\(([^)]+)\)/);
                        if (matrixMatch) {
                            const values = matrixMatch[1].split(',').map(s => parseFloat(s.trim()));
                            if (values.length === 6 && values.every(v => !isNaN(v))) {
                                // matrix(a,b,c,d,e,f) where e=tx, f=ty, and scale k = sqrt(a²+b²)
                                const k = Math.sqrt(values[0] * values[0] + values[1] * values[1]);
                                const tx = values[4];
                                const ty = values[5];
                                currentTransform = d3.zoomIdentity.translate(tx, ty).scale(k);
                            }
                        }
                    }
                } catch (e) {
                    // If parsing fails, use identity transform
                    this.logger.debug('ViewManager', 'Could not parse existing transform, using identity', e);
                }
            }
        }
        
        // Configure zoom behavior
        // Zoom: mouse wheel + pinch-to-zoom on touch devices
        // Pan: middle mouse button drag + two-finger drag on touch devices
        const zoom = d3.zoom()
            .scaleExtent([0.1, 10]) // Allow 10x zoom in, 0.1x zoom out
            .filter((event) => {
                // Allow wheel events for zooming (desktop)
                if (event.type === 'wheel') {
                    return true;
                }
                
                // Allow middle mouse button (button === 1) for panning (desktop)
                // This enables drag-to-pan when holding middle mouse button
                if (event.type === 'mousedown' && event.button === 1) {
                    event.preventDefault(); // Prevent default middle-click behavior (auto-scroll)
                    return true;
                }
                
                // TOUCH SUPPORT: Allow multi-touch for pinch-to-zoom on all touch-enabled devices
                // Works on mobile devices, tablets, and large touch displays (interactive whiteboards, etc.)
                // For touchstart/touchmove: check event.touches.length
                // For touchend: check event.changedTouches.length (touches array is empty on touchend)
                if (event.type === 'touchstart' || event.type === 'touchmove') {
                    // Allow touch events with 2+ fingers (pinch-to-zoom / two-finger pan)
                    // Block single-finger touch (reserved for node selection/tapping)
                    const touchCount = event.touches ? event.touches.length : 0;
                    if (touchCount >= 2) {
                        return true;
                    }
                    // Single finger touch - block for node selection
                    return false;
                }
                
                if (event.type === 'touchend') {
                    // For touchend, check changedTouches to see if this was part of a multi-touch gesture
                    // If 2+ fingers were lifted, allow the event (completes pinch gesture)
                    const changedTouchCount = event.changedTouches ? event.changedTouches.length : 0;
                    const remainingTouchCount = event.touches ? event.touches.length : 0;
                    // Allow if 2+ touches were involved (either lifted or remaining)
                    if (changedTouchCount >= 2 || remainingTouchCount >= 2) {
                        return true;
                    }
                    return false;
                }
                
                // Block everything else: left click, right click, double-click
                // Left click is reserved for node selection/interaction
                // Double-click opens edit modal
                return false;
            })
            .on('zoom', (event) => {
                // CRITICAL: Always get fresh reference to zoom-group in case it was recreated
                const zoomGroup = svg.select('g.zoom-group');
                if (!zoomGroup.empty()) {
                    zoomGroup.attr('transform', event.transform);
                }
                
                // Update zoom level display if needed
                if (this.currentZoomLevel) {
                    this.currentZoomLevel.textContent = `${Math.round(event.transform.k * 100)}%`;
                }
                
                // CRITICAL: When user manually zooms/pans, invalidate the "sized for panel" flag
                // This ensures the next node selection will trigger a proper fit
                // Check if this is a user-initiated zoom (not identity transform)
                const isIdentity = event.transform.k === 1 && event.transform.x === 0 && event.transform.y === 0;
                if (!isIdentity) {
                    this.isSizedForPanel = false;
                }
                
                // Store current transform for programmatic access
                this.zoomTransform = event.transform;
                
                // Update state (use updateUI method for view state)
                if (this.stateManager && typeof this.stateManager.updateUI === 'function') {
                    this.stateManager.updateUI({
                        zoomLevel: event.transform.k,
                        panX: event.transform.x,
                        panY: event.transform.y
                    });
                }
            });
        
        // Apply zoom behavior to SVG with current transform preserved
        svg.call(zoom);
        
        // Restore previous transform if it existed
        if (currentTransform.k !== 1 || currentTransform.x !== 0 || currentTransform.y !== 0) {
            svg.call(zoom.transform, currentTransform);
        }
        
        // CRITICAL: Disable default double-click zoom behavior
        // This allows custom double-click handlers (e.g., edit modal) to work properly
        // Per D3.js documentation: https://d3js.org/d3-zoom#zoom
        svg.on('dblclick.zoom', null);
        
        // Store zoom behavior for programmatic control
        this.zoomBehavior = zoom;
        this.zoomTransform = currentTransform;
        
        this.logger.debug('ViewManager', 'Zoom enabled (mouse wheel + middle mouse pan, touch support, double-click disabled)');
    }
    
    /**
     * Reset D3 zoom transform to identity (no zoom/pan)
     * @private
     * @param {boolean} animate - Whether to animate the transition
     */
    _resetZoomTransform(animate = true) {
        const svg = d3.select('#d3-container svg');
        if (svg.empty() || !this.zoomBehavior) {
            this.logger.warn('ViewManager', 'Cannot reset zoom - no SVG or zoom behavior');
            return;
        }
        
        // Reset to identity transform (scale=1, translate=0,0)
        // CRITICAL: Use named transition 'zoom-reset' to prevent interference with viewBox transition
        // Without named transitions, calling .transition() twice on the same element cancels the first
        if (animate) {
            svg.transition('zoom-reset')
                .duration(750)
                .call(this.zoomBehavior.transform, d3.zoomIdentity);
        } else {
            svg.call(this.zoomBehavior.transform, d3.zoomIdentity);
        }
        
        this.zoomTransform = d3.zoomIdentity;
        this.logger.debug('ViewManager', 'Zoom transform reset to identity');
    }
    
    /**
     * Add zoom control buttons for mobile
     */
    addMobileZoomControls() {
        // Check if controls already exist
        if (document.getElementById('mobile-zoom-controls')) {
            return;
        }
        
        // Get current language for button labels
        const isZh = window.languageManager?.currentLanguage === 'zh';
        const zoomInLabel = isZh ? '放大' : '+';
        const zoomOutLabel = isZh ? '缩小' : '−';
        const resetLabel = isZh ? '重置' : '⊙';
        const zoomInTitle = isZh ? '放大' : 'Zoom In';
        const zoomOutTitle = isZh ? '缩小' : 'Zoom Out';
        const resetTitle = isZh ? '重置视图' : 'Reset Zoom';
        
        const controlsHtml = `
            <div id="mobile-zoom-controls" class="mobile-zoom-controls">
                <button id="zoom-in-btn" class="zoom-control-btn" title="${zoomInTitle}">
                    <span>${zoomInLabel}</span>
                </button>
                <button id="zoom-out-btn" class="zoom-control-btn" title="${zoomOutTitle}">
                    <span>${zoomOutLabel}</span>
                </button>
                <button id="zoom-reset-btn" class="zoom-control-btn" title="${resetTitle}">
                    <span>${resetLabel}</span>
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
        
        return isPropertyPanelVisible || isAIPanelVisible;
    }
    
    /**
     * Fit diagram to full canvas area (entire window width)
     * @param {boolean} animate - Whether to animate the transition (default: true)
     */
    fitToFullCanvas(animate = true) {
        this.logger.debug('ViewManager', 'Fit to full canvas', { animate });
        this._resetZoomTransform(animate);
        this._fitToCanvas(animate, false);
        this.isSizedForPanel = false;
    }

    /**
     * Fit diagram to canvas with properties panel space reserved
     * @param {boolean} animate - Whether to animate the transition (default: true)
     */
    fitToCanvasWithPanel(animate = true) {
        this.logger.debug('ViewManager', 'Fit to canvas with panel', { animate });
        this._resetZoomTransform(animate);
        this._fitToCanvas(animate, true);
        this.isSizedForPanel = true;
    }

    /**
     * Internal method: Fit diagram to canvas area
     * @private
     * @param {boolean} animate - Whether to animate the transition
     * @param {boolean} reserveForPanel - Whether to reserve space for properties panel (320px)
     */
    _fitToCanvas(animate, reserveForPanel) {
        // Skip if Node Palette is active (d3-container is hidden)
        // Use PanelManager instead of direct DOM check
        if (window.panelManager?.isPanelOpen('nodePalette')) {
            const d3Container = document.getElementById('d3-container');
            if (d3Container && d3Container.style.display === 'none') {
                this.logger.debug('ViewManager', 'Skipping fit: Node Palette is active');
                return;
            }
        }
        
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
        
        // Get container dimensions
        const containerNode = container.node();
        const containerWidth = containerNode.clientWidth;
        const containerHeight = containerNode.clientHeight;
        const windowWidth = window.innerWidth;
        
        // Check panel visibility for CSS class updates
        const propertyPanel = document.getElementById('property-panel');
        const isPropertyPanelVisible = propertyPanel && propertyPanel.style.display !== 'none';
        
        const aiPanel = document.getElementById('ai-assistant-panel');
        const isAIPanelVisible = aiPanel && !aiPanel.classList.contains('collapsed');
        
        // Update canvas panel classes for dynamic width adjustment
        const canvasPanel = document.querySelector('.canvas-panel');
        if (canvasPanel) {
            canvasPanel.classList.toggle('property-panel-visible', isPropertyPanelVisible);
            canvasPanel.classList.toggle('ai-panel-visible', isAIPanelVisible && !isPropertyPanelVisible);
        }
        
        // Calculate available canvas width based on reserveForPanel parameter and active panels
        // CRITICAL: Always use windowWidth as reference, not containerWidth (which may be CSS-constrained)
        const propertyPanelWidth = 320;
        const aiPanelWidth = 450;        // AI Assistant panel width
        
        let reservedWidth = 0;
        if (reserveForPanel && isPropertyPanelVisible) {
            reservedWidth = propertyPanelWidth;
        } else if (isAIPanelVisible) {
            reservedWidth = aiPanelWidth;
        }
        
        const availableCanvasWidth = windowWidth - reservedWidth;
        
        this.logger.debug('ViewManager', 'Canvas fit calculation:', {
            mode: reservedWidth > 0 ? `WITH ${reservedWidth}px panel reserved` : 'FULL width',
            windowWidth,
            containerSize: { width: containerWidth, height: containerHeight },
            isPropertyPanelVisible,
            isAIPanelVisible,
            reservedWidth,
            availableCanvasWidth,
            contentBounds,
            animate
        });
        
        // Calculate viewBox with equal padding on all sides
        // This approach creates a viewBox around the content with uniform padding,
        // then relies on preserveAspectRatio='xMidYMid meet' to center it in the viewport
        const paddingPercent = 0.10; // 10% padding around content
        const padding = Math.min(contentBounds.width, contentBounds.height) * paddingPercent;
        
        // Create viewBox that's content bounds plus equal padding on all sides
        const viewBoxX = contentBounds.x - padding;
        const viewBoxY = contentBounds.y - padding;
        const viewBoxWidth = contentBounds.width + padding * 2;
        const viewBoxHeight = contentBounds.height + padding * 2;
        
        const newViewBox = `${viewBoxX} ${viewBoxY} ${viewBoxWidth} ${viewBoxHeight}`;
        
        this.logger.debug('ViewManager', 'Fit calculation result:', {
            availableCanvasWidth,
            contentBounds,
            padding,
            viewBox: newViewBox
        });
        
        // Apply viewBox with or without animation
        // CRITICAL: Use named transition 'viewbox-fit' to prevent interference with zoom-reset transition
        // Without named transitions, calling .transition() twice on the same element cancels the first
        if (animate) {
            svg.transition('viewbox-fit')
                .duration(750)
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
            // Skip if Node Palette is active (d3-container is hidden)
            // Use PanelManager instead of direct DOM check
            if (window.panelManager?.isPanelOpen('nodePalette')) {
                const d3Container = document.getElementById('d3-container');
                if (d3Container && d3Container.style.display === 'none') {
                    this.logger.debug('ViewManager', 'Skipping fit: Node Palette is active');
                    return;
                }
            }
            
            this.logger.debug('ViewManager', 'Reset View clicked - fitting diagram to window');
            
            const container = d3.select('#d3-container');
            const svg = container.select('svg');
            
            if (svg.empty()) {
                this.logger.warn('ViewManager', 'No SVG found, cannot reset view');
                return;
            }
            
            // Get all visual elements (groups, circles, rects, paths, text, etc.)
            const allElements = svg.selectAll('g, circle, rect, ellipse, path, line, text, polygon, polyline');
            
            if (allElements.empty()) {
                this.logger.warn('ViewManager', 'No content found in SVG');
                return;
            }
            
            this.logger.debug('ViewManager', `Found ${allElements.size()} elements in SVG`);
            
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
                this.logger.warn('ViewManager', 'No valid content bounds found');
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
            this.logger.error('ViewManager', 'Error fitting diagram to window:', error);
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
            svg.attr('width', '100%')
               .attr('height', '100%');
            
            // Get the current viewBox or create one
            const viewBox = svg.attr('viewBox');
            
            // Calculate optimal viewBox with padding
            const padding = Math.min(contentBounds.width, contentBounds.height) * 0.1; // 10% padding
            const newViewBox = `${contentBounds.x - padding} ${contentBounds.y - padding} ${contentBounds.width + padding * 2} ${contentBounds.height + padding * 2}`;
            
            if (viewBox) {
                this.logger.debug('ViewManager', 'Old viewBox:', viewBox);
                this.logger.debug('ViewManager', 'New viewBox:', newViewBox);
                
                // CRITICAL: Always set preserveAspectRatio to ensure consistent centering
                // Some renderers use xMinYMin which causes top-left alignment
                // Use named transition 'viewbox-fit' to prevent interference with zoom-reset transition
                svg.transition('viewbox-fit')
                    .duration(750)
                    .attr('viewBox', newViewBox)
                    .attr('preserveAspectRatio', 'xMidYMid meet');
                    
                this.logger.debug('ViewManager', 'Diagram fitted to window (existing viewBox)', {
                    bounds: contentBounds,
                    oldViewBox: viewBox,
                    newViewBox: newViewBox
                });
            } else {
                // No viewBox exists - create one
                this.logger.debug('ViewManager', 'No viewBox found, creating one:', newViewBox);
                
                // Use named transition 'viewbox-fit' to prevent interference with zoom-reset transition
                svg.transition('viewbox-fit')
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
            // Refit diagram to new window size (no animation for snappy response)
            const isPanelVisible = this._isPanelVisible();
            if (isPanelVisible) {
                this.fitToCanvasWithPanel(false);
            } else {
                this.fitToFullCanvas(false);
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

