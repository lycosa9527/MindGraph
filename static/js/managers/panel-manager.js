/**
 * Panel Manager
 * ==============
 * 
 * Centralized panel management system integrated with Event Bus.
 * Ensures only one panel is open at a time.
 * Manages: Properties Panel, ThinkGuide Panel, MindMate AI Panel, Node Palette, and future panels.
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 */

class PanelManager {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger;
        
        this.panels = {};
        this.currentPanel = null;
        
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
        
        // Register ThinkGuide Panel
        this.registerPanel('thinkguide', {
            element: thinkingPanel,
            type: 'class', // Uses collapsed class
            button: thinkingBtn,
            manager: () => window.thinkingModeManager,
            closeCallback: () => {
                if (thinkingBtn) thinkingBtn.classList.remove('active');
            },
            openCallback: () => {
                if (thinkingBtn) thinkingBtn.classList.add('active');
            }
        });
        
        // Register MindMate Panel
        this.registerPanel('mindmate', {
            element: aiPanel,
            type: 'class', // Uses collapsed class
            button: mindmateBtn,
            manager: () => window.aiAssistantManager,
            closeCallback: () => {
                if (mindmateBtn) mindmateBtn.classList.remove('active');
            },
            openCallback: () => {
                if (mindmateBtn) mindmateBtn.classList.add('active');
            }
        });
        
        // Register Node Palette Panel
        const nodePalettePanel = document.getElementById('node-palette-panel');
        this.registerPanel('nodePalette', {
            element: nodePalettePanel,
            type: 'style', // Uses style.display
            manager: () => window.nodePaletteManager,
            closeCallback: () => {
                // Hide panel and clean up
                if (nodePalettePanel) {
                    nodePalettePanel.style.display = 'none';
                    nodePalettePanel.classList.remove('thinkguide-visible');
                }
            },
            openCallback: () => {
                // Show panel using NodePaletteManager's method
                if (window.nodePaletteManager) {
                    window.nodePaletteManager.showPalettePanel();
                }
            }
        });
        
        this.logger.info('PanelManager', 'Initialized with panels:', Object.keys(this.panels));
    }
    
    /**
     * Subscribe to Event Bus events
     */
    subscribeToEvents() {
        // Listen for panel open requests
        this.eventBus.on('panel:open_requested', (data) => {
            if (data.panel) {
                this.openPanel(data.panel, data.options);
            }
        });
        
        // Listen for panel close requests
        this.eventBus.on('panel:close_requested', (data) => {
            if (data.panel) {
                this.closePanel(data.panel);
            }
        });
        
        // Listen for panel toggle requests
        this.eventBus.on('panel:toggle_requested', (data) => {
            if (data.panel) {
                this.togglePanel(data.panel);
            }
        });
        
        // Listen for close all requests
        this.eventBus.on('panel:close_all_requested', () => {
            this.closeAll();
        });
        
        this.logger.debug('PanelManager', 'Subscribed to events');
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
            panel.element.style.display = 'block';
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
     */
    closePanel(name) {
        const panel = this.panels[name];
        if (!panel || !panel.element) {
            this.logger.warn('PanelManager', `Cannot close panel "${name}" - not found`);
            return false;
        }
        
        const elementId = panel.element.id;
        this.logger.debug('PanelManager', `Closing panel: ${name} (element: ${elementId})`);
        
        // Close the panel
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
        
        // Emit event
        this.eventBus.emit('panel:closed', {
            panel: name,
            isOpen: false
        });
        
        this.logger.debug('PanelManager', `✅ Panel closed: ${name}`, {
            elementId,
            isActuallyClosed: !this.isPanelOpen(name)
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
     */
    closeAllExcept(exceptName) {
        const toClose = Object.keys(this.panels).filter(name => name !== exceptName);
        this.logger.debug('PanelManager', `Closing all panels except: ${exceptName}`, {
            closingPanels: toClose
        });
        
        toClose.forEach(name => {
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

