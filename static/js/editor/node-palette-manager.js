/**
 * Node Palette Manager
 * ====================
 * 
 * Manages the Node Palette feature for all diagram types.
 * Handles multi-LLM node generation, selection, and diagram integration.
 * 
 * Features:
 * - SSE streaming from 4 LLMs (qwen, deepseek, hunyuan, kimi)
 * - Infinite scroll with smart stopping (200 nodes or 12 batches)
 * - Real-time node selection with animations
 * - Support for multiple diagram types with appropriate terminology
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 */

class NodePaletteManager {
    constructor() {
        this.nodes = [];
        this.selectedNodes = new Set();
        this.currentBatch = 0;
        this.sessionId = null;
        this.centerTopic = null;
        this.diagramData = null;
        this.diagramType = null;  // Track diagram type
        this.isLoadingBatch = false;  // Prevent duplicate batch requests
        
        // Tab management for double bubble map
        this.currentTab = 'similarities';  // 'similarities' | 'differences'
        this.tabNodes = {
            'similarities': [],
            'differences': []
        };
        this.tabSelectedNodes = {
            'similarities': new Set(),
            'differences': new Set()
        };
        
        // Diagram type metadata - node types and array names
        this.diagramMetadata = {
            'circle_map': {
                arrayName: 'context',
                nodeName: 'context node',
                nodeNamePlural: 'context nodes',
                nodeType: 'context'
            },
            'bubble_map': {
                arrayName: 'attributes',
                nodeName: 'attribute',
                nodeNamePlural: 'attributes',
                nodeType: 'attribute'
            },
            'double_bubble_map': {
                // Multi-array support with tabs
                arrays: {
                    'similarities': {
                        nodeName: 'similarity',
                        nodeNamePlural: 'similarities',
                        nodeType: 'similarity'
                    },
                    'left_differences': {
                        nodeName: 'left difference',
                        nodeNamePlural: 'left differences',
                        nodeType: 'left_difference'
                    },
                    'right_differences': {
                        nodeName: 'right difference',
                        nodeNamePlural: 'right differences',
                        nodeType: 'right_difference'
                    }
                },
                // Default array for backward compatibility
                arrayName: 'similarities',
                nodeName: 'similarity',
                nodeNamePlural: 'similarities',
                nodeType: 'similarity',
                useTabs: true  // Enable tab UI
            },
            'tree_map': {
                arrayName: 'items',
                nodeName: 'item',
                nodeNamePlural: 'items',
                nodeType: 'leaf'
            },
            'mindmap': {
                arrayName: 'branches',
                nodeName: 'branch',
                nodeNamePlural: 'branches',
                nodeType: 'branch'
            },
            'flow_map': {
                arrayName: 'steps',
                nodeName: 'step',
                nodeNamePlural: 'steps',
                nodeType: 'step'
            },
            'multi_flow_map': {
                arrayName: 'effects',  // or causes depending on context
                nodeName: 'effect',
                nodeNamePlural: 'effects',
                nodeType: 'effect'
            },
            'brace_map': {
                arrayName: 'parts',
                nodeName: 'part',
                nodeNamePlural: 'parts',
                nodeType: 'part'
            },
            'bridge_map': {
                arrayName: 'analogies',
                nodeName: 'analogy',
                nodeNamePlural: 'analogies',
                nodeType: 'analogy'
            },
            'concept_map': {
                arrayName: 'concepts',
                nodeName: 'concept',
                nodeNamePlural: 'concepts',
                nodeType: 'concept'
            }
        };
        
        console.log('[NodePalette] Initialized with support for:', Object.keys(this.diagramMetadata).join(', '));
    }
    
    /**
     * Get diagram-specific metadata (node terminology, array names, etc.)
     */
    getMetadata(diagramType = null) {
        const type = diagramType || this.diagramType || 'circle_map';
        return this.diagramMetadata[type] || this.diagramMetadata['circle_map'];
    }
    
    /**
     * Check if a node text is a template placeholder.
     * Uses centralized DiagramValidator for comprehensive pattern matching.
     * 
     * @param {string} text - Node text to check
     * @returns {boolean} True if text matches placeholder pattern
     */
    isPlaceholder(text) {
        if (!text || typeof text !== 'string') {
            return false;
        }
        
        // Use DiagramValidator's centralized placeholder detection
        // Access validator through editor's toolbar manager
        const validator = window.currentEditor?.toolbarManager?.validator;
        if (!validator) {
            console.warn('[NodePalette] DiagramValidator not found, using fallback placeholder detection');
            // Fallback: basic pattern matching that covers common placeholders
            return /^(Context|背景|New|新|属性|Attribute)\s*\d*$/i.test(text.trim());
        }
        
        return validator.isPlaceholderText(text);
    }
    
    /**
     * Check if current diagram uses tabs (double bubble map)
     */
    usesTabs() {
        const metadata = this.getMetadata();
        return metadata.useTabs === true;
    }
    
    /**
     * Switch between tabs with elegant transition (double bubble only)
     */
    switchTab(tabName) {
        if (!this.usesTabs()) return;
        
        // Don't switch if already on this tab
        if (this.currentTab === tabName) {
            console.log(`[NodePalette] Already on ${tabName} tab, ignoring`);
            return;
        }
        
        console.log('[NodePalette] ========================================');
        console.log(`[NodePalette] TAB SWITCH: ${this.currentTab} → ${tabName}`);
        console.log('[NodePalette] ========================================');
        
        // Save current tab state (preserve user progress)
        console.log(`[NodePalette] Saving ${this.currentTab} state:`);
        console.log(`  - Nodes: ${this.nodes.length}`);
        console.log(`  - Selected: ${this.selectedNodes.size}`);
        
        this.tabNodes[this.currentTab] = [...this.nodes];
        this.tabSelectedNodes[this.currentTab] = new Set(this.selectedNodes);
        
        // Fade out current grid
        const grid = document.getElementById('node-palette-grid');
        if (grid) {
            grid.style.opacity = '0';
            grid.style.transform = 'translateY(10px)';
        }
        
        // Wait for fade out, then switch
        setTimeout(() => {
            // Switch to new tab
            this.currentTab = tabName;
            
            // Restore new tab state
            this.nodes = [...(this.tabNodes[tabName] || [])];
            this.selectedNodes = new Set(this.tabSelectedNodes[tabName] || new Set());
            
            console.log(`[NodePalette] Restored ${tabName} state:`);
            console.log(`  - Nodes: ${this.nodes.length}`);
            console.log(`  - Selected: ${this.selectedNodes.size}`);
            
            // Update UI
            this.renderTabNodes();
            this.updateTabButtons();
            this.updateSelectionCounter();
            
            // If the new tab has no nodes yet, CATAPULT!
            if (this.nodes.length === 0) {
                console.log(`[NodePalette] New tab empty, CATAPULT for ${tabName}...`);
                this.currentBatch = 0; // Reset batch counter for this tab
                this.loadNextBatch();
            }
            
            // Fade in new grid
            if (grid) {
                setTimeout(() => {
                    grid.style.transition = 'opacity 0.3s, transform 0.3s';
                    grid.style.opacity = '1';
                    grid.style.transform = 'translateY(0)';
                }, 10);
            }
            
            console.log(`[NodePalette] ✓ Tab switch complete: ${tabName}`);
        }, 300);
    }
    
    /**
     * Render nodes for current tab
     */
    renderTabNodes() {
        const grid = document.getElementById('node-palette-grid');
        if (!grid) return;
        
        // Clear grid
        grid.innerHTML = '';
        
        // Render nodes based on current tab
        if (this.currentTab === 'similarities') {
            // Render as single nodes
            this.nodes.forEach(node => this.renderNodeCardOnly(node));
        } else {
            // Render as paired nodes
            this.nodes.forEach(pairNode => this.renderPairCardOnly(pairNode));
        }
    }
    
    /**
     * Update tab button states with elegant animations
     */
    updateTabButtons() {
        const similaritiesBtn = document.getElementById('tab-similarities');
        const differencesBtn = document.getElementById('tab-differences');
        const tabsContainer = document.querySelector('.palette-tabs');
        
        // Update active state
        if (similaritiesBtn) {
            if (this.currentTab === 'similarities') {
                similaritiesBtn.classList.add('active');
            } else {
                similaritiesBtn.classList.remove('active');
            }
        }
        
        if (differencesBtn) {
            if (this.currentTab === 'differences') {
                differencesBtn.classList.add('active');
            } else {
                differencesBtn.classList.remove('active');
            }
        }
        
        // Update sliding indicator via data attribute
        if (tabsContainer) {
            tabsContainer.setAttribute('data-active', this.currentTab);
            
            // Dynamically calculate indicator width and position
            if (similaritiesBtn && differencesBtn) {
                const simWidth = similaritiesBtn.offsetWidth;
                const diffWidth = differencesBtn.offsetWidth;
                const gap = 8; // Must match CSS gap
                
                // Set CSS variables for dynamic positioning
                if (this.currentTab === 'similarities') {
                    tabsContainer.style.setProperty('--tab-indicator-width', `${simWidth}px`);
                } else {
                    tabsContainer.style.setProperty('--tab-indicator-width', `${diffWidth}px`);
                    tabsContainer.style.setProperty('--tab-indicator-offset', `${simWidth + gap}px`);
                }
            }
        }
        
        // Update tab counters
        this.updateTabCounters();
    }
    
    /**
     * Update node counters in tab badges
     */
    updateTabCounters() {
        const simCount = document.getElementById('count-similarities');
        const diffCount = document.getElementById('count-differences');
        
        if (simCount) {
            const count = this.tabNodes['similarities']?.length || 0;
            simCount.textContent = count > 0 ? count : '0';
        }
        
        if (diffCount) {
            const count = this.tabNodes['differences']?.length || 0;
            diffCount.textContent = count > 0 ? `${count} pairs` : '0 pairs';
        }
    }
    
    /**
     * Attach tab button click listeners
     */
    attachTabButtonListeners() {
        const similaritiesBtn = document.getElementById('tab-similarities');
        const differencesBtn = document.getElementById('tab-differences');
        
        if (similaritiesBtn) {
            similaritiesBtn.addEventListener('click', () => {
                console.log('[NodePalette] User clicked Similarities tab');
                this.switchTab('similarities');
            });
        }
        
        if (differencesBtn) {
            differencesBtn.addEventListener('click', () => {
                console.log('[NodePalette] User clicked Differences tab');
                this.switchTab('differences');
            });
        }
    }
    
    /**
     * Show tabs UI (for double bubble map only)
     */
    showTabsUI() {
        const tabsContainer = document.getElementById('node-palette-tabs');
        if (tabsContainer) {
            tabsContainer.style.display = 'flex';
            console.log('[NodePalette] Tab switcher UI shown');
        }
    }
    
    /**
     * Hide tabs UI (for other diagram types)
     */
    hideTabsUI() {
        const tabsContainer = document.getElementById('node-palette-tabs');
        if (tabsContainer) {
            tabsContainer.style.display = 'none';
        }
    }
    
    async start(centerTopic, diagramData, sessionId, educationalContext, diagramType = 'circle_map') {
        /**
         * Initialize Node Palette and load first batch.
         * 
         * @param {string} centerTopic - Center node text from diagram
         * @param {Object} diagramData - Current diagram data
         * @param {string} sessionId - Session ID from ThinkGuide
         * @param {Object} educationalContext - Educational context from ThinkGuide (grade, subject, etc.)
         * @param {string} diagramType - Type of diagram (circle_map, bubble_map, etc.)
         */
        this.diagramType = diagramType || window.currentEditor?.diagramType || 'circle_map';
        
        // Check if this is the same session (user coming back) or a new session
        const isSameSession = this.sessionId === sessionId;
        const previousSessionId = this.sessionId;
        
        this.sessionId = sessionId || `palette_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        this.centerTopic = centerTopic;
        this.diagramData = diagramData;
        this.educationalContext = educationalContext || {}; // Store ThinkGuide context
        
        // Only clear state if it's a NEW session (different sessionId)
        if (!isSameSession) {
            console.log('[NodePalette] NEW session detected - clearing previous state');
            console.log(`[NodePalette]   Previous session: ${previousSessionId || 'none'}`);
            console.log(`[NodePalette]   New session: ${this.sessionId}`);
            this.resetState();
        } else {
            console.log('[NodePalette] SAME session detected - preserving nodes and selections');
            console.log(`[NodePalette]   Session: ${this.sessionId}`);
            console.log(`[NodePalette]   Existing nodes: ${this.nodes.length}`);
            console.log(`[NodePalette]   Selected nodes: ${this.selectedNodes.size}`);
            // Keep existing nodes, selections, and batch count
            // This allows user to return and continue selecting
        }
        
        const metadata = this.getMetadata();
        const existingNodes = diagramData?.children?.length || diagramData?.[metadata.arrayName]?.length || 0;
        
        console.log('[NodePalette] ========================================');
        console.log('[NodePalette] STARTING NODE PALETTE');
        console.log('[NodePalette] ========================================');
        console.log(`[NodePalette] Diagram type: ${this.diagramType}`);
        console.log(`[NodePalette] Node type: ${metadata.nodeNamePlural}`);
        console.log(`[NodePalette] Target array: spec.${metadata.arrayName}`);
        console.log(`[NodePalette] Center topic: "${centerTopic}"`);
        console.log(`[NodePalette] Existing ${metadata.nodeNamePlural}: ${existingNodes}`);
        console.log(`[NodePalette] Educational context:`, educationalContext);
        
        // Show Node Palette panel, hide diagram
        console.log(`[NodePalette] Hiding ${this.diagramType}, showing Palette UI`);
        this.showPalettePanel();
        
        // Setup scroll listener
        this.setupScrollListener();
        
        // Initialize tabs for double bubble map
        if (this.usesTabs()) {
            this.currentTab = 'similarities';
            this.tabNodes = {
                'similarities': [],
                'differences': []
            };
            this.tabSelectedNodes = {
                'similarities': new Set(),
                'differences': new Set()
            };
            
            // Show tabs UI
            this.showTabsUI();
            
            // Attach tab button listeners
            this.attachTabButtonListeners();
            
            console.log('[NodePalette] Tabs initialized for double bubble map');
        } else {
            // Hide tabs for other diagram types
            this.hideTabsUI();
        }
        
        if (isSameSession && this.nodes.length > 0) {
            // Returning to same session - restore existing nodes in UI
            this.restoreUI();
        } else {
            // New session - load first batch
            if (this.usesTabs()) {
                // For double bubble map: load BOTH similarities and differences
                console.log('[NodePalette] Loading first batch for BOTH tabs (similarities + differences)...');
                await this.loadBothTabsInitial();
            } else {
                // For other diagrams: load single batch
                console.log('[NodePalette] Loading first batch for new session...');
                await this.loadNextBatch();
            }
        }
    }
    
    resetState() {
        /**
         * Reset Node Palette batch and node data.
         * Does NOT reset session properties (sessionId, diagramType, etc.) 
         * as those are set at the start of each session.
         */
        this.nodes = [];
        this.selectedNodes.clear();
        this.currentBatch = 0;
        this.isLoadingBatch = false;
        
        // Clear tab data for double bubble maps (CRITICAL for proper cleanup)
        this.currentTab = null;
        this.tabNodes = null;
        this.tabSelectedNodes = null;
        
        // Clear the UI grid to remove old nodes from previous session
        const grid = document.getElementById('node-palette-grid');
        if (grid) {
            grid.innerHTML = '';
            console.log('[NodePalette] UI grid cleared for new session');
        }
        
        // Hide tab UI (will be re-shown if needed in start())
        this.hideTabsUI();
        
        // Clear any active loading animations
        this.hideBatchTransition();
        this.hideCatapultLoading();
        
        console.log('[NodePalette] State reset complete (nodes, selections, tabs, animations cleared)');
    }
    
    clearAll() {
        /**
         * Complete cleanup - reset everything including session properties.
         * Called when cancelling or completely exiting Node Palette.
         */
        this.resetState();
        this.sessionId = null;
        this.centerTopic = null;
        this.diagramData = null;
        this.diagramType = null;
    }
    
    restoreUI() {
        /**
         * Restore Node Palette UI from existing session data.
         * Re-renders all node cards and updates button state.
         */
        console.log(`[NodePalette] Restoring ${this.nodes.length} existing nodes to grid`);
        
        const grid = document.getElementById('node-palette-grid');
        if (grid) {
            grid.innerHTML = '';
            this.nodes.forEach(node => this.renderNodeCardOnly(node));
            console.log(`[NodePalette] ✓ Restored ${this.nodes.length} nodes with ${this.selectedNodes.size} selected`);
        }
        
        this.updateFinishButtonState();
    }
    
    showPalettePanel() {
        /**
         * Show Node Palette panel and hide Circle Map.
         * Respects ThinkGuide panel if it's visible (leaves space for it).
         */
        const d3Container = document.getElementById('d3-container');
        const palettePanel = document.getElementById('node-palette-panel');
        const thinkingPanel = document.getElementById('thinking-panel');
        
        if (d3Container) d3Container.style.display = 'none';
        if (palettePanel) {
            palettePanel.style.display = 'flex';
            palettePanel.style.opacity = '0';
            
            // Check if ThinkGuide panel is visible
            const isThinkGuideVisible = thinkingPanel && !thinkingPanel.classList.contains('collapsed');
            if (isThinkGuideVisible) {
                palettePanel.classList.add('thinkguide-visible');
                console.log('[NodePalette] ThinkGuide is visible, leaving space for it');
            } else {
                palettePanel.classList.remove('thinkguide-visible');
                console.log('[NodePalette] ThinkGuide is hidden, using full width');
            }
            
            // Fade in
            setTimeout(() => {
                palettePanel.style.transition = 'opacity 0.3s';
                palettePanel.style.opacity = '1';
            }, 10);
        }
        
        // Attach button listeners when panel opens
        this.attachFinishButtonListener();
        this.attachCancelButtonListener();
    }
    
    attachFinishButtonListener() {
        /**
         * Attach click listener to Finish button.
         * Called when panel opens to ensure listener is active.
         */
        const finishBtn = document.getElementById('finish-selection-btn');
        if (finishBtn) {
            // Remove old listener if exists (prevent duplicates)
            finishBtn.replaceWith(finishBtn.cloneNode(true));
            const newBtn = document.getElementById('finish-selection-btn');
            
            newBtn.addEventListener('click', () => {
                console.log('[NodePalette] Finish button clicked!');
                this.finishSelection();
            });
            console.log('[NodePalette] Finish button listener attached');
        } else {
            console.error('[NodePalette] Finish button not found in DOM!');
        }
    }
    
    attachCancelButtonListener() {
        /**
         * Attach click listener to Cancel button.
         * Called when panel opens to ensure listener is active.
         */
        const cancelBtn = document.getElementById('cancel-palette-btn');
        if (cancelBtn) {
            // Remove old listener if exists (prevent duplicates)
            cancelBtn.replaceWith(cancelBtn.cloneNode(true));
            const newBtn = document.getElementById('cancel-palette-btn');
            
            newBtn.addEventListener('click', () => {
                console.log('[NodePalette] Cancel button clicked!');
                this.cancelPalette();
            });
            console.log('[NodePalette] Cancel button listener attached');
        } else {
            console.error('[NodePalette] Cancel button not found in DOM!');
        }
    }
    
    hidePalettePanel() {
        /**
         * Hide Node Palette panel and show Circle Map.
         */
        const d3Container = document.getElementById('d3-container');
        const palettePanel = document.getElementById('node-palette-panel');
        
        if (palettePanel) {
            palettePanel.style.opacity = '0';
            setTimeout(() => {
                palettePanel.style.display = 'none';
                // Clean up ThinkGuide visibility class
                palettePanel.classList.remove('thinkguide-visible');
            }, 300);
        }
        if (d3Container) {
            d3Container.style.display = 'block';
            d3Container.style.opacity = '0';
            setTimeout(() => {
                d3Container.style.transition = 'opacity 0.3s';
                d3Container.style.opacity = '1';
            }, 10);
        }
    }
    
    async cancelPalette() {
        /**
         * Cancel Node Palette and return to canvas without adding nodes.
         * Clears all state and logs the cancellation event.
         */
        const metadata = this.getMetadata();
        
        console.log('[NodePalette-Cancel] ========================================');
        console.log('[NodePalette-Cancel] USER CLICKED CANCEL BUTTON');
        console.log('[NodePalette-Cancel] ========================================');
        console.log(`[NodePalette-Cancel] Diagram: ${this.diagramType} | Node type: ${metadata.nodeNamePlural}`);
        console.log(`[NodePalette-Cancel] Selected: ${this.selectedNodes.size}/${this.nodes.length} | Batches: ${this.currentBatch}`);
        console.log(`[NodePalette-Cancel] Session ID: ${this.sessionId}`);
        console.log('[NodePalette-Cancel] Action: Returning to canvas WITHOUT adding nodes');
        
        // Log cancel event to backend
        console.log('[NodePalette-Cancel] Sending cancel event to backend...');
        try {
            const response = await auth.fetch('/thinking_mode/node_palette/cancel', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    diagram_type: this.diagramType,  // CRITICAL: Backend needs this to clean up generator
                    selected_node_count: this.selectedNodes.size,
                    total_nodes_generated: this.nodes.length,
                    batches_loaded: this.currentBatch
                })
            });
            console.log('[NodePalette-Cancel] Backend response:', response.status, response.statusText);
        } catch (e) {
            console.error('[NodePalette-Cancel] Failed to log cancel event:', e);
        }
        
        // Hide Node Palette panel
        console.log('[NodePalette-Cancel] Hiding Node Palette panel...');
        this.hideBatchTransition(); // Clean up any active transition
        this.hidePalettePanel();
        
        // Clear all state including session properties
        console.log('[NodePalette-Cancel] Clearing Node Palette state...');
        this.clearAll();
        
        // Clear grid
        const grid = document.getElementById('node-palette-grid');
        if (grid) {
            grid.innerHTML = '';
            console.log('[NodePalette-Cancel] Cleared node grid');
        }
        
        console.log('[NodePalette-Cancel] ========================================');
        console.log('[NodePalette-Cancel] ✓ CANCELLED: Returned to canvas');
        console.log('[NodePalette-Cancel] ========================================');
    }
    
    setupScrollListener() {
        /**
         * Setup infinite scroll listener - triggers at 2/3 scroll position.
         */
        const container = document.getElementById('node-palette-container');
        if (!container) return;
        
        // Throttle scroll events
        let scrollTimeout;
        container.addEventListener('scroll', () => {
            if (scrollTimeout) clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => {
                this.onScroll();
            }, 150);
        });
    }
    
    onScroll() {
        /**
         * INFINITE SCROLL - Keep CATAPULT firing forever!
         * 
         * Every time user scrolls to 2/3 down the page, we CATAPULT again.
         * This fires 4 LLMs concurrently for batch 2, 3, 4, 5... no limits!
         * 
         * Each scroll trigger = 1 CATAPULT = 4 LLMs = ~60 new nodes
         */
        const container = document.getElementById('node-palette-container');
        if (!container) return;
        
        const scrollHeight = container.scrollHeight;
        const scrollTop = container.scrollTop;
        const clientHeight = container.clientHeight;
        
        // Calculate scroll progress (0 to 1)
        const scrollProgress = (scrollTop + clientHeight) / scrollHeight;
        
        // Trigger at 2/3 (0.67) - CATAPULT again! Infinite batches!
        if (scrollProgress >= 0.67 && !this.isLoadingBatch) {
            console.log('[NodePalette] 2/3 scroll reached! CATAPULT batch #' + (this.currentBatch + 1) + ' launching...');
            this.loadNextBatch();  // This calls catapult() -> 4 LLMs fire -> ~60 new nodes
        }
    }
    
    async loadBothTabsInitial() {
        /**
         * Load BOTH similarities and differences tabs simultaneously (double bubble map only)
         * Each tab fires 4 LLMs concurrently = 8 LLMs total!
         */
        console.log('[NodePalette] Loading BOTH tabs in parallel (8 LLMs total)');
        
        this.isLoadingBatch = true;
        this.currentBatch = 1;
        
        try {
            // CATAPULT! Fire 8 LLMs total (4 per tab) - both tabs load in parallel
            await Promise.all([
                this.loadTabBatch('similarities'),
                this.loadTabBatch('differences')
            ]);
            
            console.log('[NodePalette] Both tabs loaded successfully');
            console.log(`  - Similarities: ${this.tabNodes['similarities'].length} nodes`);
            console.log(`  - Differences: ${this.tabNodes['differences'].length} nodes`);
            
            // Update tab counters
            this.updateTabCounters();
            
        } catch (error) {
            console.error('[NodePalette] Error loading both tabs:', error);
        } finally {
            this.isLoadingBatch = false;
        }
    }
    
    async loadTabBatch(mode) {
        /**
         * Load a single tab's batch (used by loadBothTabsInitial)
         * @param {string} mode - 'similarities' or 'differences'
         */
        console.log(`[NodePalette] CATAPULT for ${mode} tab (4 LLMs launching)...`);
        
        const url = '/thinking_mode/node_palette/start';
        const payload = {
            session_id: this.sessionId,
            diagram_type: this.diagramType,
            diagram_data: this.diagramData,
            educational_context: this.educationalContext,
            mode: mode  // Specify which mode to generate
        };
        
        try {
            // CATAPULT! Fire 4 LLMs concurrently for this tab
            const nodeCount = await this.catapult(url, payload, mode);
            
            console.log(`[NodePalette] ${mode} tab loaded: ${nodeCount} nodes`);
            
        } catch (error) {
            console.error(`[NodePalette] Error loading ${mode} tab:`, error);
        }
    }
    
    async catapult(url, payload, targetMode = null) {
        /**
         * CATAPULT - Fire all 4 LLMs concurrently!
         * 
         * This is the core function that launches 4 LLM requests simultaneously
         * via Server-Sent Events (SSE) and streams nodes back in real-time.
         * 
         * Think of it as a catapult launching 4 projectiles at once - each LLM
         * generates nodes in parallel, and we catch them as they stream in.
         * 
         * @param {string} url - API endpoint (/start or /next_batch)
         * @param {Object} payload - Request payload with session_id, diagram_data, etc.
         * @param {string|null} targetMode - For double bubble: 'similarities' or 'differences'
         * @returns {Promise<number>} - Number of nodes generated
         */
        // Show loading animation while catapult is firing
        this.showCatapultLoading();
        
        const response = await auth.fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        let nodeCount = 0;
        let llmsComplete = 0;
        const batchStartTime = Date.now();
        
        // STREAMING LOOP - Catch nodes as they fly in from all 4 LLMs
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = JSON.parse(line.substring(6));
                    
                    if (data.event === 'batch_start') {
                        // CATAPULT LAUNCHED! All 4 LLMs are now firing
                        console.log(`[NodePalette] CATAPULT LAUNCHED: ${data.llm_count} LLMs firing concurrently`);
                        this.updateCatapultLoading(`Launching ${data.llm_count} LLMs...`, 0, data.llm_count);
                        
                    } else if (data.event === 'node_generated') {
                        nodeCount++;
                        const node = data.node;
                        
                        // Update loading animation with live count
                        this.updateCatapultLoading(`Generating ideas... ${nodeCount} nodes received`, llmsComplete, 4);
                        
                        // Add node to appropriate target (tab-specific or main array)
                        if (targetMode && this.tabNodes) {
                            // For double bubble: add to specific tab's storage
                            this.tabNodes[targetMode].push(node);
                            
                            // If this is the CURRENT tab, also render it
                            if (targetMode === this.currentTab) {
                                this.nodes.push(node);
                                this.renderNodeCard(node);
                            }
                        } else {
                            // For other diagrams: add directly and render
                            this.appendNode(node);
                        }
                        
                    } else if (data.event === 'llm_complete') {
                        // One of the 4 LLMs has finished
                        llmsComplete++;
                        console.log(`[NodePalette] ${data.llm} complete: ${data.unique_nodes} unique, ${data.duplicates} duplicates (${data.duration}s)`);
                        this.updateCatapultLoading(`${data.llm} complete (${llmsComplete}/4)`, llmsComplete, 4);
                        
                    } else if (data.event === 'batch_complete') {
                        // All 4 LLMs have completed - catapult mission success!
                        const elapsed = ((Date.now() - batchStartTime) / 1000).toFixed(2);
                        console.log(`[NodePalette] CATAPULT COMPLETE (${elapsed}s) | New: ${data.new_unique_nodes} | Total: ${data.total_nodes}`);
                        this.updateCatapultLoading(`Complete! ${data.new_unique_nodes} new ideas`, 4, 4);
                        
                        // Hide catapult loading animation after brief delay
                        setTimeout(() => this.hideCatapultLoading(), 800);
                        
                    } else if (data.event === 'error') {
                        console.error(`[NodePalette] CATAPULT ERROR:`, data.message);
                        this.hideCatapultLoading();
                    }
                }
            }
        }
        
        return nodeCount;
    }
    
    async loadNextBatch() {
        /**
         * CATAPULT - Fire 4 LLMs concurrently for next batch!
         * 
         * INFINITE SCROLL: This gets called repeatedly as user scrolls down.
         * - Batch 1: Initial load
         * - Batch 2, 3, 4, 5...: Triggered at 2/3 scroll position, NO LIMIT!
         * 
         * Each batch = 1 CATAPULT = 4 LLMs fire concurrently = ~60 new nodes
         */
        if (this.isLoadingBatch) {
            console.warn('[NodePalette] Batch load already in progress, skipping');
            return;
        }
        
        this.isLoadingBatch = true;
        this.currentBatch++;
        
        // Hide transition animation as new batch starts
        this.hideBatchTransition();
        
        console.log(`[NodePalette] CATAPULT batch #${this.currentBatch} (4 LLMs launching)...`);
        
        // Determine URL based on batch number
        const url = this.currentBatch === 1
            ? '/thinking_mode/node_palette/start'
            : `/thinking_mode/node_palette/next_batch`;
        
        const payload = this.currentBatch === 1
            ? {
                session_id: this.sessionId,
                diagram_type: this.diagramType,  // Use actual diagram type
                diagram_data: this.diagramData,
                educational_context: this.educationalContext,  // Use ThinkGuide context
                mode: this.currentTab  // Pass current tab as mode for double bubble
            }
            : {
                session_id: this.sessionId,
                diagram_type: this.diagramType,  // Include diagram type for next batch
                center_topic: this.centerTopic,
                educational_context: this.educationalContext,  // Use ThinkGuide context
                mode: this.currentTab  // Pass current tab as mode for double bubble
            };
        
        try {
            // CATAPULT! Fire 4 LLMs concurrently (works for infinite batches)
            // For double bubble: targetMode determines which tab's nodes to update
            const targetMode = this.usesTabs() ? this.currentTab : null;
            await this.catapult(url, payload, targetMode);
            
            // Show elegant loading animation - ready for next batch when user scrolls!
            this.showBatchTransition();
            
        } catch (error) {
            console.error(`[NodePalette] CATAPULT batch ${this.currentBatch} error:`, error);
        } finally {
            this.isLoadingBatch = false;  // Allow next CATAPULT when user scrolls more
        }
    }
    
    appendNode(node) {
        /**
         * Append a new node card to the masonry layout.
         * 
         * @param {Object} node - Node data from backend
         */
        const metadata = this.getMetadata();
        
        console.log(`[NodePalette-Append] Appending ${metadata.nodeName} to this.nodes array:`, {
            diagram_type: this.diagramType,
            target_array: metadata.arrayName,
            node_type: metadata.nodeType,
            objectType: typeof node,
            nodeKeys: Object.keys(node),
            id: node.id,
            text: node.text,
            llm: node.source_llm,
            currentArrayLength: this.nodes.length
        });
        
        this.nodes.push(node);
        
        console.log(`[NodePalette-Append] After push: this.nodes.length = ${this.nodes.length} ${metadata.nodeNamePlural}`);
        
        const container = document.getElementById('node-palette-grid');
        if (!container) {
            console.error('[NodePalette-Append] ERROR: node-palette-grid container not found!');
            return;
        }
        
        const card = this.createNodeCard(node);
        container.appendChild(card);
        
        console.log(`[NodePalette-Append] Card appended to DOM | Card ID: ${card.dataset.nodeId}`);
        
        // Fade in animation
        setTimeout(() => {
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, 10);
        
        // Update selection counter
        this.updateSelectionCounter();
    }
    
    renderNodeCardOnly(node) {
        /**
         * Render a node card to the DOM WITHOUT adding to this.nodes array.
         * Used when restoring existing nodes from a previous session.
         * 
         * @param {Object} node - Node data (already in this.nodes)
         */
        const container = document.getElementById('node-palette-grid');
        if (!container) {
            console.error('[NodePalette-RenderOnly] ERROR: node-palette-grid container not found!');
            return;
        }
        
        const card = this.createNodeCard(node);
        container.appendChild(card);
        
        // Fade in animation
        setTimeout(() => {
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, 10);
    }
    
    createNodeCard(node) {
        /**
         * Create HTML element for a node card.
         * 
         * @param {Object} node - Node data
         * @returns {HTMLElement} Node card element
         */
        const card = document.createElement('div');
        card.className = `node-card llm-${node.source_llm}`;
        card.dataset.nodeId = node.id;
        card.dataset.llm = node.source_llm;
        
        // Check if this node is already selected (important for session restoration)
        const isSelected = this.selectedNodes.has(node.id);
        if (isSelected) {
            card.classList.add('selected');
            console.log(`[NodePalette-CreateCard] Node already selected, applying 'selected' class:`, node.id);
        }
        
        // Truncate text if too long (max 60 chars for 220px circular nodes)
        const displayText = this.truncateText(node.text, 60);
        
        card.innerHTML = `
            <div class="node-card-content">
                <div class="node-text">${displayText}</div>
                <div class="node-source">${node.source_llm}</div>
            </div>
            <div class="node-checkmark">✓</div>
        `;
        
        // Click handler for selection
        card.addEventListener('click', () => {
            this.toggleNodeSelection(node.id);
        });
        
        return card;
    }
    
    /**
     * Create a pair card for differences tab (using circular nodes with connection)
     */
    createPairCard(pairNode) {
        const card = document.createElement('div');
        card.className = `node-pair-container llm-${pairNode.source_llm}`;
        card.dataset.nodeId = pairNode.id;
        card.dataset.llm = pairNode.source_llm;
        
        // Check if pair is selected
        const isSelected = this.selectedNodes.has(pairNode.id);
        if (isSelected) {
            card.classList.add('selected');
        }
        
        // Get topics
        const leftTopic = this.diagramData?.left || 'Left';
        const rightTopic = this.diagramData?.right || 'Right';
        
        // Truncate text for circular nodes
        const leftText = this.truncateText(pairNode.left, 50);
        const rightText = this.truncateText(pairNode.right, 50);
        
        card.innerHTML = `
            <!-- Left circular node -->
            <div class="pair-node pair-node-left">
                <div class="pair-node-content">
                    <div class="pair-node-label">${leftTopic}</div>
                    <div class="pair-node-text">${leftText}</div>
                </div>
            </div>
            
            <!-- Animated connection line -->
            <div class="pair-connection">
                <div class="connection-line"></div>
                <div class="connection-icon">⚖️</div>
            </div>
            
            <!-- Right circular node -->
            <div class="pair-node pair-node-right">
                <div class="pair-node-content">
                    <div class="pair-node-label">${rightTopic}</div>
                    <div class="pair-node-text">${rightText}</div>
                </div>
            </div>
            
            <!-- Source badge & checkmark -->
            <div class="pair-source">${pairNode.source_llm}</div>
            <div class="pair-checkmark">✓</div>
        `;
        
        // Click handler - select/deselect entire pair
        card.addEventListener('click', () => {
            this.toggleNodeSelection(pairNode.id);
        });
        
        return card;
    }
    
    /**
     * Render a pair card to DOM (without adding to this.nodes)
     */
    renderPairCardOnly(pairNode) {
        const container = document.getElementById('node-palette-grid');
        if (!container) {
            console.error('[NodePalette-RenderPair] ERROR: node-palette-grid not found!');
            return;
        }
        
        const card = this.createPairCard(pairNode);
        container.appendChild(card);
        
        // Fade in animation
        setTimeout(() => {
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, 10);
    }
    
    truncateText(text, maxLength) {
        /**
         * Truncate text to max length with ellipsis.
         * 
         * @param {string} text - Text to truncate
         * @param {number} maxLength - Maximum length
         * @returns {string} Truncated text
         */
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength - 3) + '...';
    }
    
    toggleNodeSelection(nodeId) {
        /**
         * Toggle selection state of a node.
         * 
         * @param {string} nodeId - Node ID to toggle
         */
        const node = this.nodes.find(n => n.id === nodeId);
        // Handle both regular cards and pair containers
        const card = document.querySelector(`.node-card[data-node-id="${nodeId}"]`) || 
                     document.querySelector(`.node-pair-container[data-node-id="${nodeId}"]`);
        
        if (!node || !card) return;
        
        const wasSelected = this.selectedNodes.has(nodeId);
        
        const metadata = this.getMetadata();
        
        if (wasSelected) {
            this.selectedNodes.delete(nodeId);
            card.classList.remove('selected');
            
            // Mark node as deselected
            node.selected = false;
            
            console.log(`[NodePalette-Selection] ✗ Deselected ${metadata.nodeName}:`, {
                id: node.id,
                text: node.text,
                source_llm: node.source_llm,
                
                // STATUS CHANGE TRACKED
                selected: false,  // Changed from true → false
                added_to_diagram: false,
                
                totalSelected: this.selectedNodes.size,
                totalNodes: this.nodes.length
            });
        } else {
            this.selectedNodes.add(nodeId);
            card.classList.add('selected');
            
            // Mark node as selected - TRACK STATUS CHANGE
            node.selected = true;
            
            console.log(`[NodePalette-Selection] ✓ Selected ${metadata.nodeName}:`, {
                // Node Identity
                id: node.id,
                text: node.text,
                source_llm: node.source_llm,
                batch: node.batch_number,
                
                // Diagram Context
                diagram_type: this.diagramType,
                node_type: metadata.nodeType,
                target_array: metadata.arrayName,
                
                // STATUS TRACKED - Changed from false → true
                selected: true,  // Just changed!
                added_to_diagram: false,  // Not added yet
                
                // Aggregate Info
                totalSelected: this.selectedNodes.size,
                totalNodes: this.nodes.length,
                selectionRate: `${((this.selectedNodes.size / this.nodes.length) * 100).toFixed(1)}%`,
                
                // Object Structure
                type: typeof node,
                keys: Object.keys(node)
            });
        }
        
        this.updateSelectionCounter();
        
        // Log to backend every 5 selections
        if (this.selectedNodes.size % 5 === 0) {
            this.logSelection(nodeId, !wasSelected, node.text);
        }
    }
    
    updateSelectionCounter() {
        /**
         * Update the selection counter display.
         */
        const counter = document.getElementById('selection-counter');
        const finishBtn = document.getElementById('finish-selection-btn');
        
        if (counter) {
            counter.textContent = `Selected: ${this.selectedNodes.size}/${this.nodes.length}`;
        }
        
        if (finishBtn) {
            const wasDisabled = finishBtn.disabled;
            finishBtn.disabled = this.selectedNodes.size === 0;
            finishBtn.textContent = this.selectedNodes.size > 0 
                ? `Next (${this.selectedNodes.size} selected)` 
                : 'Next';
            
            // Log button state change
            if (wasDisabled && !finishBtn.disabled) {
                console.log('[NodePalette] Button enabled: "Next (%d selected)"', this.selectedNodes.size);
            } else if (!wasDisabled && finishBtn.disabled) {
                console.log('[NodePalette] Button disabled: "Next"');
            }
        } else {
            console.error('[NodePalette] Finish button not found when updating counter!');
        }
    }
    
    updateFinishButtonState() {
        /**
         * Alias for updateSelectionCounter() - updates the finish button state.
         * Called when restoring a session to sync button state with selections.
         */
        this.updateSelectionCounter();
    }
    
    async logSelection(nodeId, selected, nodeText) {
        /**
         * Send selection event to backend for logging.
         */
        try {
            await auth.fetch('/thinking_mode/node_palette/select_node', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    node_id: nodeId,
                    selected: selected,
                    node_text: nodeText
                })
            });
        } catch (e) {
            console.error('[NodePalette-Selection] Failed to log selection:', e);
        }
    }
    
    
    showBatchTransition() {
        /**
         * Show elegant loading animation between batches
         */
        const container = document.getElementById('node-palette-grid');
        if (!container) return;
        
        // Check if transition element already exists
        let transition = document.getElementById('batch-transition');
        if (!transition) {
            transition = document.createElement('div');
            transition.id = 'batch-transition';
            transition.className = 'batch-transition';
            transition.innerHTML = `
                <div class="transition-content">
                    <div class="transition-spinner">
                        <div class="spinner-ring"></div>
                        <div class="spinner-ring"></div>
                        <div class="spinner-ring"></div>
                    </div>
                    <div class="transition-text">Preparing next batch...</div>
                    <div class="transition-subtext">Scroll down for more ideas</div>
                </div>
            `;
            container.appendChild(transition);
        }
        
        // Fade in
        setTimeout(() => {
            transition.style.opacity = '1';
            transition.style.transform = 'translateY(0)';
        }, 10);
    }
    
    hideBatchTransition() {
        /**
         * Hide batch transition animation
         */
        const transition = document.getElementById('batch-transition');
        if (transition) {
            transition.style.opacity = '0';
            transition.style.transform = 'translateY(20px)';
            setTimeout(() => {
                transition.remove();
            }, 400);
        }
    }
    
    showCatapultLoading() {
        /**
         * Show CATAPULT loading animation - live updates while LLMs fire!
         */
        const header = document.getElementById('node-palette-header');
        if (!header) return;
        
        // Check if catapult loader already exists
        let loader = document.getElementById('catapult-loader');
        if (!loader) {
            loader = document.createElement('div');
            loader.id = 'catapult-loader';
            loader.className = 'catapult-loader';
            loader.innerHTML = `
                <div class="catapult-spinner">
                    <div class="spinner-circle"></div>
                    <div class="spinner-circle"></div>
                    <div class="spinner-circle"></div>
                    <div class="spinner-circle"></div>
                </div>
                <div class="catapult-status">Launching CATAPULT...</div>
                <div class="catapult-progress">
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: 0%"></div>
                    </div>
                </div>
            `;
            header.appendChild(loader);
        }
        
        // Fade in
        setTimeout(() => {
            loader.style.opacity = '1';
        }, 10);
    }
    
    updateCatapultLoading(status, completedLLMs, totalLLMs) {
        /**
         * Update CATAPULT loading animation with live progress
         */
        const loader = document.getElementById('catapult-loader');
        if (!loader) return;
        
        const statusEl = loader.querySelector('.catapult-status');
        const progressFill = loader.querySelector('.progress-fill');
        
        if (statusEl) {
            statusEl.textContent = status;
        }
        
        if (progressFill) {
            const percentage = (completedLLMs / totalLLMs) * 100;
            progressFill.style.width = `${percentage}%`;
        }
    }
    
    hideCatapultLoading() {
        /**
         * Hide CATAPULT loading animation
         */
        const loader = document.getElementById('catapult-loader');
        if (loader) {
            loader.style.opacity = '0';
            setTimeout(() => {
                loader.remove();
            }, 300);
        }
    }
    
    async finishSelection() {
        /**
         * Finish Node Palette, add selected nodes to Circle Map.
         */
        const selectedCount = this.selectedNodes.size;
        
        const metadata = this.getMetadata();
        
        console.log('[NodePalette-Finish] ========================================');
        console.log('[NodePalette-Finish] USER CLICKED FINISH BUTTON');
        console.log('[NodePalette-Finish] ========================================');
        console.log(`[NodePalette-Finish] Diagram: ${this.diagramType} | Node type: ${metadata.nodeNamePlural}`);
        console.log(`[NodePalette-Finish] Selected: ${selectedCount}/${this.nodes.length} | Batches: ${this.currentBatch} | Rate: ${((selectedCount/this.nodes.length)*100).toFixed(1)}%`);
        console.log('[NodePalette-Finish] selectedNodes Set (IDs):', Array.from(this.selectedNodes));
        
        if (selectedCount === 0) {
            console.warn(`[NodePalette-Finish] ⚠ No ${metadata.nodeNamePlural} selected, showing alert`);
            alert(`Please select at least one ${metadata.nodeName}`);
            return;
        }
        
        // Filter selected nodes - ONLY get NEW selections (not already added)
        const selectedNodesData = this.nodes.filter(n => 
            this.selectedNodes.has(n.id) && !n.added_to_diagram  // Only nodes that haven't been added yet
        );
        
        const alreadyAddedCount = this.nodes.filter(n => 
            this.selectedNodes.has(n.id) && n.added_to_diagram  // Count previously added nodes
        ).length;
        
        console.log(`[NodePalette-Finish] Filtered ${selectedNodesData.length} NEW ${metadata.nodeNamePlural} (${alreadyAddedCount} already added, skipping)`);
        
        // Check if there are any NEW nodes to add
        if (selectedNodesData.length === 0) {
            console.warn(`[NodePalette-Finish] ⚠ All selected ${metadata.nodeNamePlural} were already added. Nothing to do.`);
            const msg = metadata.language === 'zh' ? 
                '所有选中的节点都已添加到图中。' : 
                'All selected nodes have already been added to the diagram.';
            alert(msg);
            return;
        }
        
        console.log(`[NodePalette-Finish] Selected ${metadata.nodeName} details (NEW only):`);
        selectedNodesData.forEach((node, idx) => {
            console.log(`  [${idx + 1}/${selectedNodesData.length}] ID: ${node.id} | LLM: ${node.source_llm} | Batch: ${node.batch_number} | Text: "${node.text}"`);
        });
        
        // Log finish event to backend
        console.log('[NodePalette-Finish] Sending finish event to backend...');
        try {
            const response = await auth.fetch('/thinking_mode/node_palette/finish', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    selected_node_ids: Array.from(this.selectedNodes),
                    total_nodes_generated: this.nodes.length,
                    batches_loaded: this.currentBatch,
                    diagram_type: this.diagramType  // Add diagram type for cleanup
                })
            });
            console.log('[NodePalette-Finish] Backend response:', response.status, response.statusText);
        } catch (e) {
            console.error('[NodePalette-Finish] Failed to log finish event:', e);
        }
        
        // Hide Node Palette BEFORE adding nodes (so user sees the result)
        console.log('[NodePalette-Finish] Hiding Node Palette panel...');
        this.hideBatchTransition(); // Clean up any active transition
        this.hidePalettePanel();
        
        // Wait for panel to hide
        await new Promise(resolve => setTimeout(resolve, 350));
        
        // Add selected nodes to diagram (method name kept for backward compatibility)
        console.log(`[NodePalette-Finish] Starting ${metadata.nodeName} assembly to ${this.diagramType}...`);
        await this.assembleNodesToCircleMap(selectedNodesData);
        
        console.log('[NodePalette-Finish] ========================================');
        console.log('[NodePalette-Finish] ✓ FINISH COMPLETE');
        console.log('[NodePalette-Finish] ========================================');
    }
    
    async assembleNodesToCircleMap(selectedNodes) {
        /**
         * Add selected nodes to the diagram.
         * Uses InteractiveEditor API for robust integration.
         * Works for Circle Map, Bubble Map, and other diagram types.
         * 
         * @param {Array} selectedNodes - Array of selected node objects
         */
        const metadata = this.getMetadata();
        
        console.log('[NodePalette-Assemble] ========================================');
        console.log(`[NodePalette-Assemble] ASSEMBLING ${metadata.nodeNamePlural.toUpperCase()} TO ${this.diagramType.toUpperCase()}`);
        console.log('[NodePalette-Assemble] ========================================');
        console.log(`[NodePalette-Assemble] Diagram: ${this.diagramType}`);
        console.log(`[NodePalette-Assemble] Target array: spec.${metadata.arrayName}`);
        console.log(`[NodePalette-Assemble] Node type: ${metadata.nodeType}`);
        console.log(`[NodePalette-Assemble] Input: Received ${selectedNodes.length} selected ${metadata.nodeNamePlural}`);
        console.log(`[NodePalette-Assemble] ${metadata.nodeName.charAt(0).toUpperCase() + metadata.nodeName.slice(1)} objects structure:`);
        selectedNodes.forEach((node, idx) => {
            console.log(`  [${idx + 1}] Type: ${typeof node} | Keys: ${Object.keys(node).join(', ')}`);
            console.log(`       ID: ${node.id} | Text: "${node.text}" | LLM: ${node.source_llm}`);
        });
        
        // Step 1: Verify editor exists
        const editor = window.currentEditor;
        console.log('[NodePalette-Assemble] Editor: %s', editor ? '✓ Found' : '✗ Not found');
        
        if (!editor) {
            console.error('[NodePalette-Assemble] ERROR: No active editor found');
            alert('Error: No active editor found. Please try refreshing the page.');
            return;
        }
        
        console.log('[NodePalette-Assemble] Editor type: %s', editor.diagramType);
        console.log('[NodePalette-Assemble] Editor currentSpec: %s', !!editor.currentSpec);
        
        // Step 2: Verify spec exists
        const currentSpec = editor.currentSpec;
        if (!currentSpec) {
            console.error('[NodePalette-Assemble] ERROR: No current spec found');
            alert('Error: No diagram specification found. Please try refreshing the page.');
            return;
        }
        
        const arrayName = metadata.arrayName;
        
        console.log('[NodePalette-Assemble] Spec keys: %s', Object.keys(currentSpec).join(', '));
        console.log(`[NodePalette-Assemble] Current spec.${arrayName}: %s`, Array.isArray(currentSpec[arrayName]) ? `Array[${currentSpec[arrayName].length}]` : typeof currentSpec[arrayName]);
        
        // Step 3: Initialize array if needed
        if (!currentSpec[arrayName]) {
            console.log(`[NodePalette-Assemble] Initializing new spec.${arrayName} array`);
            currentSpec[arrayName] = [];
        }
        
        const beforeCount = currentSpec[arrayName].length;
        console.log(`[NodePalette-Assemble] BEFORE: spec.${arrayName} has ${beforeCount} items`);
        if (beforeCount > 0) {
            console.log(`[NodePalette-Assemble] Existing ${metadata.nodeNamePlural}:`);
            currentSpec[arrayName].forEach((item, idx) => {
                console.log(`  [${idx}] Type: ${typeof item} | Value: ${typeof item === 'object' ? JSON.stringify(item) : item}`);
            });
        }
        
        // ========================================
        // STEP 4: SMART REPLACE LOGIC
        // ========================================
        // Analyze existing nodes and choose strategy:
        // - REPLACE: All placeholders → clear all, add selected
        // - SMART_REPLACE: Mix of placeholders + user nodes → keep user nodes, add selected
        // - APPEND: All user nodes → append selected (current behavior)
        
        console.log('[NodePalette-Assemble] ========================================');
        console.log('[NodePalette-Assemble] DETECTION PHASE: Analyzing existing nodes');
        console.log('[NodePalette-Assemble] ========================================');
        
        // Analyze existing nodes
        const existingNodes = currentSpec[arrayName] || [];
        const placeholders = [];
        const userNodes = [];
        
        existingNodes.forEach((nodeText, idx) => {
            const isPlaceholder = this.isPlaceholder(nodeText);
            if (isPlaceholder) {
                placeholders.push({ index: idx, text: nodeText });
            } else {
                userNodes.push({ index: idx, text: nodeText });
            }
            console.log(`  [${idx}] "${nodeText}" -> ${isPlaceholder ? 'PLACEHOLDER' : 'USER NODE'}`);
        });
        
        console.log(`[NodePalette-Assemble] Analysis complete:`);
        console.log(`[NodePalette-Assemble]   Total existing: ${existingNodes.length}`);
        console.log(`[NodePalette-Assemble]   Placeholders: ${placeholders.length}`);
        console.log(`[NodePalette-Assemble]   User nodes: ${userNodes.length}`);
        console.log(`[NodePalette-Assemble]   Selected to add: ${selectedNodes.length}`);
        
        // ========================================
        // UNIFIED EXECUTION - Elegant Approach
        // ========================================
        // This single approach handles all cases:
        // - Empty array: userNodes=[], result=[selected]
        // - All placeholders: userNodes=[] (filtered out), result=[selected]
        // - Mix: userNodes=[kept], result=[kept, selected]
        // - All user nodes: userNodes=[all], result=[all, selected]
        
        console.log('[NodePalette-Assemble] ========================================');
        console.log('[NodePalette-Assemble] EXECUTION: Building new array');
        console.log('[NodePalette-Assemble] ========================================');
        console.log(`[NodePalette-Assemble] Keeping ${userNodes.length} user nodes`);
        console.log(`[NodePalette-Assemble] Adding ${selectedNodes.length} selected ${metadata.nodeNamePlural}`);
        
        // Build new array: keep user nodes + add selected nodes
        const newArray = [];
        const addedNodeIds = [];
        
        // Keep user nodes (placeholders automatically excluded)
        userNodes.forEach(userNode => {
            newArray.push(userNode.text);
            console.log(`  KEEPING user node: "${userNode.text}"`);
        });
        
        // Add selected nodes
        selectedNodes.forEach((node, idx) => {
            newArray.push(node.text);
            node.added_to_diagram = true;
            addedNodeIds.push(node.id);
            console.log(`  [${idx + 1}/${selectedNodes.length}] ADDED: "${node.text}" | LLM: ${node.source_llm} | ID: ${node.id}`);
        });
        
        // Update spec
        currentSpec[arrayName] = newArray;
        
        console.log(`[NodePalette-Assemble] ✓ Complete: ${userNodes.length} kept + ${selectedNodes.length} added = ${newArray.length} total`);
        
        console.log(`[NodePalette-Assemble] Successfully processed ${addedNodeIds.length} ${metadata.nodeNamePlural}`);
        console.log(`[NodePalette-Assemble] Added node IDs:`, addedNodeIds);
        
        const afterCount = currentSpec[arrayName].length;
        const diff = afterCount - beforeCount;
        console.log('[NodePalette-Assemble] ========================================');
        console.log('[NodePalette-Assemble] BEFORE/AFTER SUMMARY');
        console.log('[NodePalette-Assemble] ========================================');
        console.log(`[NodePalette-Assemble] BEFORE: ${beforeCount} ${metadata.nodeNamePlural}`);
        console.log(`[NodePalette-Assemble]   - Placeholders: ${placeholders.length} (auto-excluded)`);
        console.log(`[NodePalette-Assemble]   - User nodes: ${userNodes.length} (kept)`);
        console.log(`[NodePalette-Assemble] AFTER: ${afterCount} ${metadata.nodeNamePlural} (${diff >= 0 ? '+' : ''}${diff})`);
        console.log(`[NodePalette-Assemble] Final spec.${arrayName} array:`);
        currentSpec[arrayName].forEach((item, idx) => {
            console.log(`  [${idx}] Type: ${typeof item} | Value: ${typeof item === 'object' ? JSON.stringify(item) : item}`);
        });
        
        // Step 5: Re-render the diagram
        console.log('[NodePalette-Assemble] Rendering diagram...');
        try {
            // Try different render methods based on editor type
            if (typeof editor.render === 'function') {
                console.log('[NodePalette-Assemble] Calling editor.render()...');
                const renderResult = await editor.render();
                console.log('[NodePalette-Assemble] ✓ editor.render() completed:', renderResult);
            } else if (typeof editor.renderDiagram === 'function') {
                console.log('[NodePalette-Assemble] Calling editor.renderDiagram()...');
                await editor.renderDiagram(currentSpec);
                console.log('[NodePalette-Assemble] ✓ editor.renderDiagram() completed');
            } else if (typeof editor.update === 'function') {
                console.log('[NodePalette-Assemble] Calling editor.update()...');
                await editor.update();
                console.log('[NodePalette-Assemble] ✓ editor.update() completed');
            } else {
                console.error('[NodePalette-Assemble] ERROR: No render method found on editor');
                console.error('[NodePalette-Assemble] Available methods:', Object.keys(editor).filter(k => typeof editor[k] === 'function'));
                alert('Error: Cannot render diagram. Please try refreshing the page.');
                return;
            }
            
            // Step 6: Verify the rendered nodes
            console.log('[NodePalette-Assemble] Verifying rendered nodes in DOM...');
            const nodeElements = document.querySelectorAll(`[data-node-type="${metadata.nodeType}"]`);
            console.log(`[NodePalette-Assemble] Found ${nodeElements.length} ${metadata.nodeNamePlural} in DOM with [data-node-type="${metadata.nodeType}"]`);
            nodeElements.forEach((elem, idx) => {
                const nodeId = elem.getAttribute('data-node-id');
                const arrayIndex = elem.getAttribute('data-array-index');
                const textElement = elem.querySelector('text');
                const textContent = textElement ? textElement.textContent : 'NO TEXT ELEMENT';
                console.log(`  [${idx}] ID: ${nodeId} | Index: ${arrayIndex} | Type: ${metadata.nodeType} | Text: "${textContent}"`);
            });
            
            // Step 7: Save to history
            console.log('[NodePalette-Assemble] Saving to history...');
            if (typeof editor.saveHistoryState === 'function') {
                editor.saveHistoryState('node_palette_add');
                console.log('[NodePalette-Assemble] ✓ History saved via saveHistoryState');
            } else if (typeof editor.saveHistory === 'function') {
                editor.saveHistory('node_palette_add');
                console.log('[NodePalette-Assemble] ✓ History saved via saveHistory');
            } else {
                console.warn('[NodePalette-Assemble] ⚠ No history save method found (skipping)');
            }
            
            console.log('[NodePalette-Assemble] ========================================');
            console.log(`[NodePalette-Assemble] ✓ SUCCESS: ${selectedNodes.length} ${metadata.nodeNamePlural} added to ${this.diagramType}`);
            console.log('[NodePalette-Assemble] ========================================');
            
            // FINAL STATUS SUMMARY - Complete tracking report
            console.log(`[NodePalette-Assemble] FINAL STATUS SUMMARY:`);
            console.log(`[NodePalette-Assemble]   Total nodes generated: ${this.nodes.length}`);
            console.log(`[NodePalette-Assemble]   Total nodes selected: ${this.selectedNodes.size}`);
            console.log(`[NodePalette-Assemble]   Total nodes added to ${this.diagramType}: ${selectedNodes.length}`);
            console.log(`[NodePalette-Assemble]   Selection rate: ${((this.selectedNodes.size / this.nodes.length) * 100).toFixed(1)}%`);
            console.log(`[NodePalette-Assemble] All added nodes now have: selected=true, added_to_diagram=true`);
            
        } catch (error) {
            console.error('[NodePalette-Assemble] ========================================');
            console.error('[NodePalette-Assemble] ✗ ERROR: Failed to render Circle Map');
            console.error('[NodePalette-Assemble] Error type:', error.constructor.name);
            console.error('[NodePalette-Assemble] Error message:', error.message);
            console.error('[NodePalette-Assemble] Error stack:', error.stack);
            console.error('[NodePalette-Assemble] Current spec at error:', JSON.stringify(currentSpec, null, 2));
            console.error('[NodePalette-Assemble] ========================================');
            alert(`Error rendering diagram: ${error.message}\n\nPlease check console for details.`);
        }
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = NodePaletteManager;
}

// Global instance
window.nodePaletteManager = new NodePaletteManager();

// Note: Button listener is now attached when panel opens (see showPalettePanel)
// This ensures the listener is active even if panel opens after DOMContentLoaded

