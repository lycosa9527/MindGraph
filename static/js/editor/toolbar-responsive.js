/**
 * Toolbar Responsive Manager
 * ==========================
 * 
 * Dynamically adjusts toolbar layout when window is resized,
 * ensuring MindMate AI button and other tools fit in one line.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class ToolbarResponsiveManager {
    constructor() {
        this.toolbar = null;
        this.toolbarLeft = null;
        this.toolbarCenter = null;
        this.toolbarRight = null;
        this.resizeTimeout = null;
        this.currentMode = 'full'; // 'full', 'compact', 'minimal', 'mobile'
        this.collapsedSections = new Set(); // Track collapsed sections on mobile
        
        console.log('[ToolbarResponsive] Initialized');
    }
    
    init() {
        /**
         * Initialize responsive manager and attach listeners.
         */
        this.toolbar = document.querySelector('.editor-toolbar');
        this.toolbarLeft = document.querySelector('.toolbar-left');
        this.toolbarCenter = document.querySelector('.toolbar-center');
        this.toolbarRight = document.querySelector('.toolbar-right');
        
        if (!this.toolbar) {
            console.warn('[ToolbarResponsive] Toolbar not found, skipping initialization');
            return;
        }
        
        console.log('[ToolbarResponsive] Starting responsive manager');
        
        // Setup collapsible sections for mobile
        this.setupCollapsibleSections();
        
        // Initial check
        this.checkAndAdjust();
        
        // Attach resize listener with debouncing
        window.addEventListener('resize', () => {
            clearTimeout(this.resizeTimeout);
            this.resizeTimeout = setTimeout(() => {
                this.checkAndAdjust();
            }, 100);
        });
        
        // Also check when buttons are added/removed (for dynamic UI changes)
        this.setupMutationObserver();
        
        // Listen for language changes to update button text
        window.addEventListener('languageChanged', () => {
            this.showFullButtonText(); // Refresh button text with new language
        });
    }
    
    setupMutationObserver() {
        /**
         * Watch for DOM changes in toolbar (buttons added/removed).
         * Only watch for childList changes to avoid infinite loops from our own class/style modifications.
         */
        if (!this.toolbar) return;
        
        this.mutationObserver = new MutationObserver((mutations) => {
            // Only react to childList changes (buttons added/removed), not attribute changes
            const hasChildListChange = mutations.some(mutation => mutation.type === 'childList');
            if (!hasChildListChange) return;
            
            clearTimeout(this.resizeTimeout);
            this.resizeTimeout = setTimeout(() => {
                this.checkAndAdjust();
            }, 150);
        });
        
        this.mutationObserver.observe(this.toolbar, {
            childList: true,
            subtree: true
            // Removed: attributes, attributeFilter - these cause infinite loops
        });
    }
    
    checkAndAdjust() {
        /**
         * Check toolbar width and apply appropriate layout adjustments.
         */
        if (!this.toolbar) return;
        
        const width = window.innerWidth;
        let newMode = this.determineMode(width);
        
        // Only log if mode changed
        if (newMode !== this.currentMode) {
            console.log(`[ToolbarResponsive] Window width: ${width}px | Mode: ${this.currentMode} → ${newMode}`);
            this.currentMode = newMode;
        }
        
        this.applyMode(newMode);
    }
    
    determineMode(width) {
        /**
         * Determine which layout mode to use based on width.
         * 
         * @param {number} width - Window width in pixels
         * @returns {string} Mode name
         */
        if (width >= 1400) {
            return 'full';
        } else if (width >= 1200) {
            return 'large';
        } else if (width >= 900) {
            return 'compact';
        } else if (width >= 769) {
            return 'minimal';
        } else {
            return 'mobile';
        }
    }
    
    applyMode(mode) {
        /**
         * Apply layout adjustments for the given mode.
         * 
         * @param {string} mode - Layout mode
         */
        // Remove all mode classes
        this.toolbar.classList.remove('toolbar-full', 'toolbar-large', 'toolbar-compact', 'toolbar-minimal', 'toolbar-mobile');
        
        // Add current mode class
        this.toolbar.classList.add(`toolbar-${mode}`);
        
        switch (mode) {
            case 'full':
                this.applyFullMode();
                break;
            case 'large':
                this.applyLargeMode();
                break;
            case 'compact':
                this.applyCompactMode();
                break;
            case 'minimal':
                this.applyMinimalMode();
                break;
            case 'mobile':
                this.applyMobileMode();
                break;
        }
    }
    
    applyFullMode() {
        /**
         * Full mode - all elements visible with full text.
         */
        this.showAllLabels();
        this.showFullButtonText();
        this.showFullAIButton();
        this.removeCollapsible();
    }
    
    applyLargeMode() {
        /**
         * Large mode - slightly smaller buttons, labels visible, icon-only AI button.
         * Covers 1200-1399px (includes 1366px budget laptops).
         */
        this.showAllLabels();
        this.showFullButtonText();
        this.showIconOnlyAIButton();
        this.removeCollapsible();
    }
    
    applyCompactMode() {
        /**
         * Compact mode - hide labels, icon-only AI button.
         * Covers 900-1199px.
         */
        this.hideLabels();
        this.showFullButtonText();
        this.showIconOnlyAIButton();
        this.removeCollapsible();
    }
    
    applyMinimalMode() {
        /**
         * Minimal mode - hide labels, show only AI icon for MindMate button.
         */
        this.hideLabels();
        this.showIconOnlyAIButton();
        this.removeCollapsible();
    }
    
    applyMobileMode() {
        /**
         * Mobile mode - collapsible sections, full AI button text.
         */
        this.hideLabels();
        // Don't abbreviate AI button - keep full text on mobile
        this.showFullAIButton();
        this.makeCollapsible();
    }
    
    showAllLabels() {
        /**
         * Show all toolbar group labels.
         */
        const labels = this.toolbar.querySelectorAll('.toolbar-group label');
        labels.forEach(label => {
            label.style.display = '';
        });
    }
    
    hideLabels() {
        /**
         * Hide toolbar group labels to save space.
         */
        const labels = this.toolbar.querySelectorAll('.toolbar-group label');
        labels.forEach(label => {
            label.style.display = 'none';
        });
    }
    
    showFullButtonText() {
        /**
         * Show full text on buttons (restore from abbreviated state).
         */
        const learningBtn = document.getElementById('learning-btn-text');
        const thinkingBtn = document.getElementById('thinking-btn-text');
        const mindmateBtn = document.getElementById('mindmate-btn-text');
        
        // Get current language from LanguageManager
        const currentLang = window.languageManager?.getCurrentLanguage() || 'en';
        
        if (learningBtn) {
            learningBtn.textContent = currentLang === 'zh' ? '学习' : 'Learn';
        }
        if (thinkingBtn) {
            thinkingBtn.textContent = currentLang === 'zh' ? '思维向导' : 'ThinkGuide';
        }
        if (mindmateBtn) {
            const fullName = window.AI_ASSISTANT_NAME || 'MindMate AI';
            mindmateBtn.textContent = fullName;
        }
    }
    
    abbreviateButtonText() {
        /**
         * Abbreviate button text to save space.
         */
        const mindmateBtn = document.getElementById('mindmate-btn-text');
        
        // Only abbreviate MindMate AI button
        if (mindmateBtn) {
            const fullName = window.AI_ASSISTANT_NAME || 'MindMate AI';
            const firstName = fullName.split(' ')[0];
            mindmateBtn.textContent = firstName;
        }
    }
    
    abbreviateAIButton() {
        /**
         * Extra abbreviation for mobile - just "AI".
         */
        const mindmateBtn = document.getElementById('mindmate-btn-text');
        if (mindmateBtn) {
            mindmateBtn.textContent = 'AI';
        }
    }
    
    showIconOnlyAIButton() {
        /**
         * Show only the AI icon, hide the text label completely.
         * Used for narrow desktop screens to save space.
         */
        const mindmateBtn = document.getElementById('mindmate-btn-text');
        const mindmateContainer = document.getElementById('mindmate-ai-btn');
        if (mindmateBtn) {
            mindmateBtn.style.display = 'none';
        }
        if (mindmateContainer) {
            mindmateContainer.classList.add('icon-only');
        }
    }
    
    showFullAIButton() {
        /**
         * Restore full AI button with text.
         */
        const mindmateBtn = document.getElementById('mindmate-btn-text');
        const mindmateContainer = document.getElementById('mindmate-ai-btn');
        if (mindmateBtn) {
            mindmateBtn.style.display = '';
        }
        if (mindmateContainer) {
            mindmateContainer.classList.remove('icon-only');
        }
    }
    
    setupCollapsibleSections() {
        /**
         * Setup collapsible functionality for toolbar groups on mobile.
         */
        const toolbarGroups = this.toolbar.querySelectorAll('.toolbar-group');
        
        toolbarGroups.forEach((group, index) => {
            // Add collapse toggle button
            const label = group.querySelector('label');
            if (label) {
                const toggleBtn = document.createElement('button');
                toggleBtn.className = 'toolbar-group-toggle';
                toggleBtn.innerHTML = '▼';
                toggleBtn.style.display = 'none'; // Hidden by default
                toggleBtn.setAttribute('aria-label', 'Toggle section');
                toggleBtn.dataset.groupIndex = index;
                
                // Insert toggle before label
                group.insertBefore(toggleBtn, label);
                
                // Toggle click handler
                toggleBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.toggleSection(group, toggleBtn);
                });
                
                // Make label clickable too on mobile
                label.addEventListener('click', () => {
                    if (window.innerWidth <= 768) {
                        toggleBtn.click();
                    }
                });
            }
        });
    }
    
    makeCollapsible() {
        /**
         * Enable collapsible sections on mobile (only for sections with many buttons).
         */
        // Select both old .toolbar-group and new specific classes
        const toolbarGroups = this.toolbar.querySelectorAll('.toolbar-group, .nodes-toolbar-group, .tools-toolbar-group');
        
        toolbarGroups.forEach((group) => {
            const toggle = group.querySelector('.toolbar-group-toggle');
            const label = group.querySelector('label');
            const buttons = Array.from(group.children).filter(
                child => child.tagName === 'BUTTON' && !child.classList.contains('toolbar-group-toggle')
            );
            
            // Disable collapsible on mobile - all buttons fit on one row now
            // with adaptive button sizing (padding: 6px 8px, gap: 4px)
            const shouldCollapse = false; // Previously: buttons.length > 3
            
            if (toggle && label) {
                if (shouldCollapse) {
                    // Show toggle button for large sections
                    toggle.style.display = 'inline-flex';
                    label.style.cursor = 'pointer';
                    label.style.userSelect = 'none';
                    
                    // Add collapsible class
                    group.classList.add('collapsible-group');
                    
                    // Collapse by default (except first group)
                    const isFirstGroup = group.parentElement.classList.contains('toolbar-left');
                    if (!isFirstGroup && !group.classList.contains('expanded')) {
                        this.collapseSection(group, toggle);
                    } else {
                        // Keep first group expanded
                        this.expandSection(group, toggle);
                    }
                } else {
                    // Small sections: hide toggle, always show buttons
                    toggle.style.display = 'none';
                    group.classList.remove('collapsible-group', 'collapsed');
                    group.classList.add('always-visible');
                    
                    // Show all buttons (except flow-map-orientation-btn which is controlled by diagram type)
                    buttons.forEach(btn => {
                        // Skip flow map orientation button - it's controlled by diagram type visibility
                        if (btn.id === 'flow-map-orientation-btn') {
                            return;
                        }
                        btn.style.display = '';
                    });
                }
                
                // Always show label
                label.style.display = 'inline';
            }
        });
    }
    
    toggleSection(group, toggle) {
        /**
         * Toggle collapse state of a toolbar group.
         */
        if (group.classList.contains('collapsed')) {
            this.expandSection(group, toggle);
        } else {
            this.collapseSection(group, toggle);
        }
    }
    
    collapseSection(group, toggle) {
        /**
         * Collapse a toolbar group (hide buttons).
         */
        group.classList.add('collapsed');
        group.classList.remove('expanded');
        toggle.innerHTML = '▶';
        
        // Hide all buttons except toggle and label
        const buttons = Array.from(group.children).filter(
            child => child.tagName === 'BUTTON' && !child.classList.contains('toolbar-group-toggle')
        );
        buttons.forEach(btn => {
            btn.style.display = 'none';
        });
        
        console.log('[ToolbarResponsive] Collapsed section');
    }
    
    expandSection(group, toggle) {
        /**
         * Expand a toolbar group (show buttons).
         */
        group.classList.remove('collapsed');
        group.classList.add('expanded');
        toggle.innerHTML = '▼';
        
        // Show all buttons (except flow-map-orientation-btn which is controlled by diagram type)
        const buttons = Array.from(group.children).filter(
            child => child.tagName === 'BUTTON' && !child.classList.contains('toolbar-group-toggle')
        );
        buttons.forEach(btn => {
            // Skip flow map orientation button - it's controlled by diagram type visibility
            if (btn.id === 'flow-map-orientation-btn') {
                return;
            }
            btn.style.display = '';
        });
        
        console.log('[ToolbarResponsive] Expanded section');
    }
    
    removeCollapsible() {
        /**
         * Remove collapsible functionality (restore desktop mode).
         */
        const toolbarGroups = this.toolbar.querySelectorAll('.toolbar-group');
        
        toolbarGroups.forEach((group) => {
            const toggle = group.querySelector('.toolbar-group-toggle');
            const label = group.querySelector('label');
            
            // Hide toggle buttons
            if (toggle) {
                toggle.style.display = 'none';
            }
            
            // Remove collapsible classes
            group.classList.remove('collapsible-group', 'collapsed', 'expanded');
            
            // Show all buttons (except flow-map-orientation-btn which is controlled by diagram type)
            const buttons = Array.from(group.children).filter(
                child => child.tagName === 'BUTTON' && !child.classList.contains('toolbar-group-toggle')
            );
            buttons.forEach(btn => {
                // Skip flow map orientation button - it's controlled by diagram type visibility
                if (btn.id === 'flow-map-orientation-btn') {
                    return;
                }
                btn.style.display = '';
            });
            
            // Reset label style
            if (label) {
                label.style.cursor = '';
                label.style.userSelect = '';
            }
        });
    }
    
    getToolbarWidth() {
        /**
         * Calculate total width needed by toolbar elements.
         * 
         * @returns {number} Total width in pixels
         */
        if (!this.toolbar) return 0;
        
        let totalWidth = 0;
        
        [this.toolbarLeft, this.toolbarCenter, this.toolbarRight].forEach(section => {
            if (section) {
                totalWidth += section.offsetWidth;
            }
        });
        
        return totalWidth;
    }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.toolbarResponsiveManager = new ToolbarResponsiveManager();
        window.toolbarResponsiveManager.init();
    });
} else {
    window.toolbarResponsiveManager = new ToolbarResponsiveManager();
    window.toolbarResponsiveManager.init();
}

