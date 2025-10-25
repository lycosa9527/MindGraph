/**
 * Panel Manager
 * =============
 * 
 * Centralized panel management system to ensure only one panel is open at a time.
 * Handles: Properties Panel, ThinkGuide Panel, MindMate AI Panel, and future panels.
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 */

class PanelManager {
    constructor() {
        this.panels = {};
        this.currentPanel = null;
        this.logger = window.logger || console;
        
        this.init();
    }
    
    init() {
        // Register all panels in the system
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
        
        this.registerPanel('property', {
            element: propertyPanel,
            type: 'style', // Uses style.display
            closeCallback: () => {
                // Also clear property panel content
                if (window.currentEditor?.toolbarManager) {
                    window.currentEditor.toolbarManager.clearPropertyPanel();
                }
            }
        });
        
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
        
        this.logger.info('PanelManager', 'Initialized successfully with panels:', Object.keys(this.panels));
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
            return false;
        }
        
        if (!panel.element) {
            this.logger.warn('PanelManager', `Panel "${name}" element not found in DOM`);
            return false;
        }
        
        // Verify we're targeting the right element
        const elementId = panel.element.id;
        this.logger.info('PanelManager', `Opening panel: ${name} (element: ${elementId})`);
        
        // Log current state before changes
        this.logger.debug('PanelManager', `Panel state before open:`, {
            requestedPanel: name,
            currentPanel: this.currentPanel,
            allPanels: Object.keys(this.panels).map(n => ({
                name: n,
                elementId: this.panels[n].element?.id || 'N/A',
                isOpen: this.isPanelOpen(n)
            }))
        });
        
        // Close all other panels first
        this.closeAllExcept(name);
        
        // Open the requested panel
        if (panel.type === 'class') {
            const hadCollapsed = panel.element.classList.contains('collapsed');
            panel.element.classList.remove('collapsed');
            const nowOpen = !panel.element.classList.contains('collapsed');
            this.logger.debug('PanelManager', `Removed 'collapsed' from ${name}`, {
                elementId,
                hadCollapsed,
                nowOpen
            });
        } else if (panel.type === 'style') {
            panel.element.style.display = 'block';
        }
        
        this.currentPanel = name;
        
        // Run open callback if defined
        if (panel.openCallback) {
            try {
                this.logger.debug('PanelManager', `Running openCallback for ${name}`);
                panel.openCallback();
            } catch (error) {
                this.logger.error('PanelManager', `Error in open callback for ${name}:`, error);
            }
        } else {
            this.logger.warn('PanelManager', `No openCallback defined for ${name}`);
        }
        
        // Final verification
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
        
        // Log state BEFORE closing
        const wasClosed = panel.type === 'class' 
            ? panel.element.classList.contains('collapsed')
            : panel.element.style.display === 'none';
        
        const elementId = panel.element.id;
        this.logger.debug('PanelManager', `Closing panel: ${name} (element: ${elementId})`, {
            wasClosed,
            willClose: !wasClosed
        });
        
        if (panel.type === 'class') {
            panel.element.classList.add('collapsed');
            // Verify it was added
            const nowClosed = panel.element.classList.contains('collapsed');
            this.logger.debug('PanelManager', `Panel ${name} collapsed class added:`, {
                elementId,
                nowClosed,
                success: nowClosed
            });
        } else if (panel.type === 'style') {
            panel.element.style.display = 'none';
        }
        
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
}

// Create global instance
window.panelManager = new PanelManager();

// Expose helper functions for backward compatibility
window.closePanels = () => window.panelManager.closeAll();
window.closeOtherPanels = (exceptName) => window.panelManager.closeAllExcept(exceptName);

