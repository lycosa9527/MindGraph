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
                arrayName: 'similarities',  // Could also be left_differences or right_differences
                nodeName: 'similarity',
                nodeNamePlural: 'similarities',
                nodeType: 'similarity'
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
        
        if (isSameSession && this.nodes.length > 0) {
            // Returning to same session - restore existing nodes in UI
            this.restoreUI();
        } else {
            // New session - load first batch
            console.log('[NodePalette] Loading first batch for new session...');
        await this.loadNextBatch();
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
        
        // Clear the UI grid to remove old nodes from previous session
        const grid = document.getElementById('node-palette-grid');
        if (grid) {
            grid.innerHTML = '';
            console.log('[NodePalette] UI grid cleared for new session');
        }
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
         * Handle scroll event - load next batch at 2/3 position.
         * Infinite scroll - no limits!
         */
        const container = document.getElementById('node-palette-container');
        if (!container) return;
        
        const scrollHeight = container.scrollHeight;
        const scrollTop = container.scrollTop;
        const clientHeight = container.clientHeight;
        
        // Calculate scroll progress (0 to 1)
        const scrollProgress = (scrollTop + clientHeight) / scrollHeight;
        
        // Trigger at 2/3 (0.67) - fire all 4 LLMs concurrently again!
        if (scrollProgress >= 0.67 && !this.isLoadingBatch) {
            console.log('[NodePalette] 🚀 2/3 scroll reached! Firing 4 LLMs concurrently...');
            this.loadNextBatch();
        }
    }
    
    async loadNextBatch() {
        /**
         * Load next batch - fires 4 LLMs concurrently!
         * Infinite scroll - no limits.
         */
        if (this.isLoadingBatch) {
            console.warn('[NodePalette] Batch load already in progress, skipping');
            return;
        }
        
        this.isLoadingBatch = true;
        this.currentBatch++;
        
        // Hide transition animation as new batch starts
        this.hideBatchTransition();
        
        console.log(`[NodePalette] 🚀 Loading batch #${this.currentBatch} (4 LLMs concurrent)`);
        
        // Determine URL based on batch number
        const url = this.currentBatch === 1
            ? '/thinking_mode/node_palette/start'
            : `/thinking_mode/node_palette/next_batch`;
        
            const payload = this.currentBatch === 1
            ? {
                session_id: this.sessionId,
                diagram_type: this.diagramType,  // Use actual diagram type
                diagram_data: this.diagramData,
                educational_context: this.educationalContext  // Use ThinkGuide context
            }
            : {
                session_id: this.sessionId,
                diagram_type: this.diagramType,  // Include diagram type for next batch
                center_topic: this.centerTopic,
                educational_context: this.educationalContext  // Use ThinkGuide context
            };
        
        try {
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
            let duplicateCount = 0;
            let currentLLM = null;
            const batchStartTime = Date.now();
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = JSON.parse(line.substring(6));
                        
                        if (data.event === 'batch_start') {
                            console.log(`[NodePalette] Batch ${this.currentBatch} starting: ${data.llm_count} LLMs firing concurrently`);
                            
                        } else if (data.event === 'node_generated') {
                            nodeCount++;
                            const metadata = this.getMetadata();
                            
                            // Verbose logging for streaming nodes - FULL TRACKING
                            console.log(`[NodePalette-Stream] ${metadata.nodeName.charAt(0).toUpperCase() + metadata.nodeName.slice(1)} #${nodeCount} received:`, {
                                // Node Identity
                                id: data.node.id,
                                text: data.node.text,
                                
                                // Node Metadata
                                source_llm: data.node.source_llm,
                                batch_number: data.node.batch_number,
                                relevance_score: data.node.relevance_score,
                                
                                // Diagram Context
                                node_type: metadata.nodeType,
                                diagram_type: this.diagramType,
                                target_array: metadata.arrayName,
                                
                                // Selection Status - TRACKED
                                selected: data.node.selected,
                                added_to_diagram: false,  // Not added yet, just received
                                
                                // Object Structure
                                type: typeof data.node,
                                keys: Object.keys(data.node),
                                
                                // Tracking Info
                                total_nodes_received: nodeCount,
                                current_selections: this.selectedNodes.size
                            });
                            
                            this.appendNode(data.node);
                            
                        } else if (data.event === 'llm_complete') {
                            console.log(`[NodePalette] ${data.llm} complete: ${data.unique_nodes} unique, ${data.duplicates} duplicates (${data.duration}s)`);
                            
                        } else if (data.event === 'batch_complete') {
                            const elapsed = ((Date.now() - batchStartTime) / 1000).toFixed(2);
                            
                            console.log(`[NodePalette] Batch ${this.currentBatch} complete (${elapsed}s) | New: ${data.new_unique_nodes} | Total: ${data.total_nodes}`);
                            
                            this.isLoadingBatch = false;
                            
                            // Show elegant loading animation for next batch
                            this.showBatchTransition();
                            
                        } else if (data.event === 'error') {
                            console.error(`[NodePalette] Batch ${this.currentBatch} error:`, data.message);
                            this.isLoadingBatch = false;
                        }
                    }
                }
            }
            
        } catch (error) {
            console.error(`[NodePalette] Batch ${this.currentBatch} load error:`, error);
            this.isLoadingBatch = false;
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
        const card = document.querySelector(`.node-card[data-node-id="${nodeId}"]`);
        
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
                    batches_loaded: this.currentBatch
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
            console.log(`  [${idx}] "${nodeText}" → ${isPlaceholder ? '🏷️ PLACEHOLDER' : '✅ USER NODE'}`);
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

