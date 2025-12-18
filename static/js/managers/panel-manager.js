/**
 * Panel Manager
 * ==============
 * 
 * Centralized panel management system integrated with Event Bus.
 * Ensures only one panel is open at a time.
 * Manages: Properties Panel, ThinkGuide Panel, MindMate AI Panel, Node Palette, and future panels.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class PanelManager {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger;
        
        // Add owner identifier for Event Bus Listener Registry
        this.ownerId = 'PanelManager';
        
        this.panels = {};
        this.currentPanel = null;
        
        // Store callback references for proper cleanup
        this.callbacks = {
            panelOpen: (data) => {
                if (data.panel) {
                    this.openPanel(data.panel, data.options);
                }
            },
            panelClose: (data) => {
                if (data.panel) {
                    this.closePanel(data.panel);
                }
            },
            panelToggle: (data) => {
                if (data.panel) {
                    this.togglePanel(data.panel);
                }
            },
            closeAll: () => {
                this.closeAll();
            }
        };
        
        this.init();
        this.subscribeToEvents();
        
        this.logger.info('PanelManager', 'Initialized with Event Bus');
    }
    
    /**
     * Initialize and register all panels
     */
    init() {
        // Get DOM elements
        const propertyPanel = document.getElementById('property-panel');
        const thinkingPanel = document.getElementById('thinking-panel');
        const aiPanel = document.getElementById('ai-assistant-panel');
        const thinkingBtn = document.getElementById('thinking-btn');
        const mindmateBtn = document.getElementById('mindmate-ai-btn');
        
        this.logger.debug('PanelManager', 'Initializing panels', {
            hasPropertyPanel: !!propertyPanel,
            hasThinkingPanel: !!thinkingPanel,
            hasAIPanel: !!aiPanel,
            hasThinkingBtn: !!thinkingBtn,
            hasMindmateBtn: !!mindmateBtn
        });
        
        // Register Property Panel
        this.registerPanel('property', {
            element: propertyPanel,
            type: 'style', // Uses style.display
            closeCallback: () => {
                // Clear property panel content
                if (window.currentEditor?.toolbarManager) {
                    window.currentEditor.toolbarManager.clearPropertyPanel();
                }
            }
        });
        
        // Register ThinkGuide Panel (still exists, but button now opens Node Palette)
        this.registerPanel('thinkguide', {
            element: thinkingPanel,
            type: 'class', // Uses collapsed class
            manager: () => window.currentEditor?.thinkGuide,
            // No button - thinking-btn now opens Node Palette instead
        });
        
        // Register MindMate Panel
        this.registerPanel('mindmate', {
            element: aiPanel,
            type: 'class', // Uses collapsed class
            button: mindmateBtn,
            manager: () => window.currentEditor?.mindMate,
            closeCallback: () => {
                if (mindmateBtn) mindmateBtn.classList.remove('active');
            },
            openCallback: () => {
                if (mindmateBtn) mindmateBtn.classList.add('active');
            }
        });
        
        // Register Node Palette Panel (thinking-btn now opens this)
        const nodePalettePanel = document.getElementById('node-palette-panel');
        this.registerPanel('nodePalette', {
            element: nodePalettePanel,
            type: 'style', // Uses style.display
            button: thinkingBtn, // thinking-btn now controls Node Palette
            manager: () => window.currentEditor?.nodePalette,
            closeCallback: () => {
                // Panel-specific cleanup (PanelManager handles display)
                // NodePaletteManager.closePanel() will be called by PanelManager
                if (thinkingBtn) thinkingBtn.classList.remove('active');
            },
            openCallback: () => {
                // Panel-specific setup (PanelManager handles display)
                // NodePaletteManager.showPalettePanel() handles watermark, listeners, etc.
                if (window.currentEditor?.nodePalette) {
                    window.currentEditor.nodePalette.showPalettePanel();
                }
                if (thinkingBtn) thinkingBtn.classList.add('active');
            }
        });
        
        this.logger.info('PanelManager', 'Initialized with panels:', Object.keys(this.panels));
    }
    
    /**
     * Subscribe to Event Bus events
     */
    subscribeToEvents() {
        // Listen for panel open requests - use stored callback with owner tracking
        this.eventBus.onWithOwner('panel:open_requested', this.callbacks.panelOpen, this.ownerId);
        
        // Listen for panel close requests - use stored callback with owner tracking
        this.eventBus.onWithOwner('panel:close_requested', this.callbacks.panelClose, this.ownerId);
        
        // Listen for panel toggle requests - use stored callback with owner tracking
        this.eventBus.onWithOwner('panel:toggle_requested', this.callbacks.panelToggle, this.ownerId);
        
        // Listen for close all requests - use stored callback with owner tracking
        this.eventBus.onWithOwner('panel:close_all_requested', this.callbacks.closeAll, this.ownerId);
        
        this.logger.debug('PanelManager', 'Event listeners registered with owner tracking');
    }
    
    /**
     * Register a panel in the system
     */
    registerPanel(name, config) {
        this.panels[name] = {
            name,
            element: config.element,
            type: config.type || 'class',
            button: config.button,
            manager: config.manager,
            closeCallback: config.closeCallback,
            openCallback: config.openCallback
        };
        
        this.logger.debug('PanelManager', `Registered panel: ${name}`, {
            hasElement: !!config.element,
            hasButton: !!config.button,
            hasOpenCallback: !!config.openCallback,
            hasCloseCallback: !!config.closeCallback
        });
    }
    
    /**
     * Check if a panel is currently open
     */
    isPanelOpen(name) {
        const panel = this.panels[name];
        if (!panel || !panel.element) return false;
        
        if (panel.type === 'class') {
            return !panel.element.classList.contains('collapsed');
        } else if (panel.type === 'style') {
            return panel.element.style.display !== 'none';
        }
        return false;
    }
    
    /**
     * Open a panel (closes all others)
     */
    openPanel(name, options = {}) {
        const panel = this.panels[name];
        if (!panel) {
            this.logger.warn('PanelManager', `Panel "${name}" not found`);
            this.eventBus.emit('panel:error', { 
                panel: name, 
                error: 'Panel not found' 
            });
            return false;
        }
        
        if (!panel.element) {
            this.logger.warn('PanelManager', `Panel "${name}" element not found in DOM`);
            this.eventBus.emit('panel:error', { 
                panel: name, 
                error: 'Panel element not found' 
            });
            return false;
        }
        
        const elementId = panel.element.id;
        this.logger.info('PanelManager', `Opening panel: ${name} (element: ${elementId})`);
        
        // Close all other panels first
        this.closeAllExcept(name);
        
        // Open the requested panel
        if (panel.type === 'class') {
            panel.element.classList.remove('collapsed');
        } else if (panel.type === 'style') {
            // Node palette uses flex layout, others use block
            const displayValue = name === 'nodePalette' ? 'flex' : 'block';
            panel.element.style.display = displayValue;
        }
        
        this.currentPanel = name;
        
        // Update State Manager
        this.stateManager.openPanel(name, options);
        
        // Run open callback if defined
        if (panel.openCallback) {
            try {
                this.logger.debug('PanelManager', `Running openCallback for ${name}`);
                panel.openCallback();
            } catch (error) {
                this.logger.error('PanelManager', `Error in open callback for ${name}:`, error);
            }
        }
        
        // Emit event
        this.eventBus.emit('panel:opened', {
            panel: name,
            isOpen: true,
            options
        });
        
        this.logger.info('PanelManager', `✅ Panel opened: ${name}`, {
            elementId,
            isActuallyOpen: this.isPanelOpen(name),
            currentPanel: this.currentPanel
        });
        
        return true;
    }
    
    /**
     * Close a specific panel
     * 
     * @param {string} name - Panel name to close
     * @param {Object} options - Options for closing
     * @param {boolean} options._internal - If true, skips manager notification (prevents loops)
     * @returns {boolean} True if panel was closed, false otherwise
     */
    closePanel(name, options = {}) {
        const panel = this.panels[name];
        if (!panel || !panel.element) {
            this.logger.warn('PanelManager', `Cannot close panel "${name}" - not found`);
            return false;
        }
        
        // Check if already closed (prevent unnecessary operations)
        if (!this.isPanelOpen(name)) {
            this.logger.debug('PanelManager', `Panel "${name}" already closed, skipping`);
            return false;
        }
        
        const elementId = panel.element.id;
        const source = options._internal ? 'manager' : 'panel_manager';
        this.logger.debug('PanelManager', `Closing panel: ${name} (element: ${elementId}, source: ${source})`);
        
        // Notify manager BEFORE DOM manipulation
        // This allows manager to cleanup state (stop streams, etc.)
        // The _internal flag in options means this call originated from a manager,
        // so we skip manager notification to prevent circular calls
        if (!options._internal) {
            const manager = panel.manager?.();
            if (manager && typeof manager.closePanel === 'function') {
                try {
                    this.logger.debug('PanelManager', `Notifying manager for panel: ${name}`);
                    // Pass internal flag to prevent manager from calling PanelManager back
                    // Manager will do internal cleanup only, not call PanelManager again
                    manager.closePanel({ _internal: true });
                } catch (error) {
                    this.logger.error('PanelManager', `Error notifying manager for ${name}:`, error);
                    // Continue with close even if manager notification fails
                }
            } else {
                this.logger.debug('PanelManager', `No manager found for panel: ${name}`);
            }
        } else {
            this.logger.debug('PanelManager', `Skipping manager notification (internal call from manager)`);
        }
        
        // Close the panel (DOM manipulation)
        if (panel.type === 'class') {
            panel.element.classList.add('collapsed');
        } else if (panel.type === 'style') {
            panel.element.style.display = 'none';
        }
        
        // Update State Manager
        this.stateManager.closePanel(name);
        
        // Run close callback if defined
        if (panel.closeCallback) {
            try {
                this.logger.debug('PanelManager', `Running closeCallback for ${name}`);
                panel.closeCallback();
            } catch (error) {
                this.logger.error('PanelManager', `Error in close callback for ${name}:`, error);
            }
        }
        
        if (this.currentPanel === name) {
            this.currentPanel = null;
        }
        
        // Emit event (notification that closing is complete)
        this.eventBus.emit('panel:closed', {
            panel: name,
            isOpen: false,
            source: source
        });
        
        this.logger.debug('PanelManager', `✅ Panel closed: ${name}`, {
            elementId,
            isActuallyClosed: !this.isPanelOpen(name),
            source: source
        });
        
        return true;
    }
    
    /**
     * Close all panels
     */
    closeAll() {
        Object.keys(this.panels).forEach(name => {
            this.closePanel(name);
        });
        this.currentPanel = null;
        this.logger.debug('PanelManager', 'Closed all panels');
        
        this.eventBus.emit('panel:all_closed', {});
    }
    
    /**
     * Close all panels except the specified one
     * 
     * This is called automatically when opening a panel to ensure only one is open.
     * Managers will be notified via their closePanel() method with _internal flag.
     * 
     * @param {string} exceptName - Panel name to keep open
     */
    closeAllExcept(exceptName) {
        const toClose = Object.keys(this.panels).filter(name => name !== exceptName);
        this.logger.debug('PanelManager', `Closing all panels except: ${exceptName}`, {
            closingPanels: toClose
        });
        
        toClose.forEach(name => {
            // Call with no options (not _internal) so managers get notified
            // This is PanelManager-initiated, not user-initiated, but we want managers to know
            this.closePanel(name);
        });
    }
    
    /**
     * Get current open panel name
     */
    getCurrentPanel() {
        return this.currentPanel;
    }
    
    /**
     * Toggle a panel (open if closed, close if open)
     */
    togglePanel(name) {
        if (this.isPanelOpen(name)) {
            this.closePanel(name);
        } else {
            this.openPanel(name);
        }
    }
    
    // ============================================================================
    // EXPLICIT PANEL METHODS - Type-safe, precise control for each panel
    // ============================================================================
    
    /**
     * Open MindMate AI Panel (right side)
     */
    openMindMatePanel() {
        this.logger.info('PanelManager', '📱 openMindMatePanel() called - EXPLICIT');
        return this.openPanel('mindmate');
    }
    
    /**
     * Close MindMate AI Panel
     */
    closeMindMatePanel() {
        this.logger.info('PanelManager', '📱 closeMindMatePanel() called - EXPLICIT');
        return this.closePanel('mindmate');
    }
    
    /**
     * Toggle MindMate AI Panel
     */
    toggleMindMatePanel() {
        this.logger.info('PanelManager', '📱 toggleMindMatePanel() called - EXPLICIT');
        return this.togglePanel('mindmate');
    }
    
    /**
     * Check if MindMate AI Panel is open
     */
    isMindMatePanelOpen() {
        return this.isPanelOpen('mindmate');
    }
    
    /**
     * Open ThinkGuide Panel (left side)
     */
    openThinkGuidePanel() {
        this.logger.info('PanelManager', '🧠 openThinkGuidePanel() called - EXPLICIT');
        return this.openPanel('thinkguide');
    }
    
    /**
     * Close ThinkGuide Panel
     */
    closeThinkGuidePanel() {
        this.logger.info('PanelManager', '🧠 closeThinkGuidePanel() called - EXPLICIT');
        return this.closePanel('thinkguide');
    }
    
    /**
     * Toggle ThinkGuide Panel
     */
    toggleThinkGuidePanel() {
        this.logger.info('PanelManager', '🧠 toggleThinkGuidePanel() called - EXPLICIT');
        return this.togglePanel('thinkguide');
    }
    
    /**
     * Check if ThinkGuide Panel is open
     */
    isThinkGuidePanelOpen() {
        return this.isPanelOpen('thinkguide');
    }
    
    /**
     * Open Property Panel
     */
    openPropertyPanel() {
        this.logger.info('PanelManager', '⚙️ openPropertyPanel() called - EXPLICIT');
        return this.openPanel('property');
    }
    
    /**
     * Close Property Panel
     */
    closePropertyPanel() {
        this.logger.info('PanelManager', '⚙️ closePropertyPanel() called - EXPLICIT');
        return this.closePanel('property');
    }
    
    /**
     * Toggle Property Panel
     */
    togglePropertyPanel() {
        this.logger.info('PanelManager', '⚙️ togglePropertyPanel() called - EXPLICIT');
        return this.togglePanel('property');
    }
    
    /**
     * Check if Property Panel is open
     */
    isPropertyPanelOpen() {
        return this.isPanelOpen('property');
    }
    
    /**
     * Convenience method: Open Node Palette panel
     */
    openNodePalettePanel() {
        this.logger.info('PanelManager', '🎨 openNodePalettePanel() called - EXPLICIT');
        return this.openPanel('nodePalette');
    }
    
    /**
     * Convenience method: Close Node Palette panel
     */
    closeNodePalettePanel() {
        this.logger.info('PanelManager', '🎨 closeNodePalettePanel() called - EXPLICIT');
        return this.closePanel('nodePalette');
    }
    
    /**
     * Clean up resources
     */
    destroy() {
        this.logger.debug('PanelManager', 'Destroying');
        
        // Remove all Event Bus listeners using Listener Registry
        if (this.eventBus && this.ownerId) {
            this.eventBus.removeAllListenersForOwner(this.ownerId);
            this.logger.debug('PanelManager', 'Event listeners successfully removed');
        }
        
        // Clear panel registry
        this.panels = {};
        this.currentPanel = null;
        
        // Nullify references
        this.callbacks = null;
        this.eventBus = null;
        this.stateManager = null;
        this.logger = null;
    }
}

// Initialize when dependencies are ready
if (typeof window !== 'undefined') {
    const initPanelManager = () => {
        if (window.eventBus && window.stateManager && window.logger) {
            window.panelManager = new PanelManager(
                window.eventBus,
                window.stateManager,
                window.logger
            );
            
            // Expose helper functions for backward compatibility
            window.closePanels = () => window.panelManager.closeAll();
            window.closeOtherPanels = (exceptName) => window.panelManager.closeAllExcept(exceptName);
            
            if (window.logger.debugMode) {
                console.log('%c[PanelManager] Initialized with Event Bus', 'color: #00bcd4; font-weight: bold;');
            }
        } else {
            setTimeout(initPanelManager, 50);
        }
    };
    
    initPanelManager();
}

