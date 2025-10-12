/**
 * Node Palette Manager
 * ====================
 * 
 * Manages the Node Palette feature for Circle Maps.
 * Handles multi-LLM node generation, selection, and Circle Map integration.
 * 
 * Features:
 * - SSE streaming from 4 LLMs (qwen, deepseek, hunyuan, kimi)
 * - Infinite scroll with smart stopping (200 nodes or 12 batches)
 * - Real-time node selection with animations
 * - Integration with Circle Map for selected nodes
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 */

class NodePaletteManager {
    constructor() {
        this.nodes = [];
        this.selectedNodes = new Set();
        this.currentBatch = 0;
        this.isLoading = false;
        this.sessionId = null;
        this.centerTopic = null;
        this.diagramData = null;
        
        // Constants from design doc
        this.MAX_NODES = 200;
        this.MAX_BATCHES = 12;
        this.hasReachedLimit = false;
        
        console.log('[NodePalette] Initialized');
    }
    
    async start(centerTopic, diagramData, sessionId) {
        /**
         * Initialize Node Palette and load first batch.
         * 
         * @param {string} centerTopic - Center node text from Circle Map
         * @param {Object} diagramData - Current Circle Map data
         * @param {string} sessionId - Session ID from ThinkGuide
         */
        const existingNodes = diagramData?.children?.length || 0;
        console.log(`[NodePalette] Starting | Topic: "${centerTopic}" | Existing nodes: ${existingNodes}`);
        
        this.sessionId = sessionId || `palette_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        this.centerTopic = centerTopic;
        this.diagramData = diagramData;
        this.currentBatch = 0;
        this.nodes = [];
        this.selectedNodes.clear();
        this.hasReachedLimit = false;
        
        // Show Node Palette panel, hide Circle Map
        console.log('[NodePalette] Hiding Circle Map, showing Palette UI');
        this.showPalettePanel();
        
        // Setup scroll listener
        this.setupScrollListener();
        
        // Load first batch
        await this.loadNextBatch();
    }
    
    showPalettePanel() {
        /**
         * Show Node Palette panel and hide Circle Map.
         */
        const d3Container = document.getElementById('d3-container');
        const palettePanel = document.getElementById('node-palette-panel');
        
        if (d3Container) d3Container.style.display = 'none';
        if (palettePanel) {
            palettePanel.style.display = 'flex';
            palettePanel.style.opacity = '0';
            // Fade in
            setTimeout(() => {
                palettePanel.style.transition = 'opacity 0.3s';
                palettePanel.style.opacity = '1';
            }, 10);
        }
        
        // Attach finish button listener when panel opens
        this.attachFinishButtonListener();
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
    
    setupScrollListener() {
        /**
         * Setup infinite scroll listener (200px from bottom triggers next batch).
         */
        const container = document.getElementById('node-palette-container');
        if (!container) return;
        
        // Throttle scroll events
        let scrollTimeout;
        container.addEventListener('scroll', () => {
            if (scrollTimeout) clearTimeout(scrollTimeout);
            scrollTimeout = setTimeout(() => {
                this.onScroll();
            }, 100);
        });
    }
    
    onScroll() {
        /**
         * Handle scroll event - load next batch if near bottom.
         */
        const container = document.getElementById('node-palette-container');
        if (!container) return;
        
        const scrollHeight = container.scrollHeight;
        const scrollTop = container.scrollTop;
        const clientHeight = container.clientHeight;
        
        // Check if near bottom (200px threshold)
        const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
        
        if (distanceFromBottom < 200 && !this.isLoading && !this.hasReachedLimit) {
            console.log('[NodePalette] User scrolled near bottom, loading next batch');
            this.loadNextBatch();
        }
    }
    
    async loadNextBatch() {
        /**
         * Load next batch of nodes from backend SSE stream.
         */
        if (this.isLoading) {
            console.warn('[NodePalette] Batch load already in progress, skipping');
            return;
        }
        
        // Check limits
        if (this.nodes.length >= this.MAX_NODES || this.currentBatch >= this.MAX_BATCHES) {
            console.log('[NodePalette] Reached limit: nodes=%d, batches=%d', this.nodes.length, this.currentBatch);
            this.hasReachedLimit = true;
            this.showEndMessage();
            return;
        }
        
        this.isLoading = true;
        this.currentBatch++;
        
        console.log(`[NodePalette] Loading batch #${this.currentBatch}`);
        
        // Determine URL based on batch number
        const url = this.currentBatch === 1
            ? '/thinking_mode/node_palette/start'
            : `/thinking_mode/node_palette/next_batch`;
        
            const payload = this.currentBatch === 1
            ? {
                session_id: this.sessionId,
                diagram_type: 'circle_map',
                diagram_data: this.diagramData,
                educational_context: {
                    grade_level: '5th grade',
                    subject: 'Science'
                },
                batch_size: 50
            }
            : {
                session_id: this.sessionId,
                center_topic: this.centerTopic,
                educational_context: {
                    grade_level: '5th grade',
                    subject: 'Science'
                },
                batch_size: 50
            };
        
        try {
            const response = await fetch(url, {
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
                            currentLLM = data.llm;
                            console.log(`[NodePalette] Batch ${this.currentBatch}: ${currentLLM} generating...`);
                            
                        } else if (data.event === 'node_generated') {
                            nodeCount++;
                            this.appendNode(data.node);
                            
                            // Only log every 5th node to avoid console spam
                            if (nodeCount % 5 === 0 || nodeCount === 1) {
                                console.log(`[NodePalette] Node #${nodeCount}: "${data.node.text}" (${data.node.source_llm})`);
                            }
                            
                        } else if (data.event === 'batch_complete') {
                            const elapsed = ((Date.now() - batchStartTime) / 1000).toFixed(2);
                            duplicateCount = data.duplicates_filtered;
                            
                            console.log(`[NodePalette] Batch ${this.currentBatch} complete (${elapsed}s) | LLM: ${currentLLM} | Unique: ${data.unique_nodes} | Duplicates: ${duplicateCount} | Total: ${this.nodes.length}`);
                            
                            this.isLoading = false;
                            
                        } else if (data.event === 'error') {
                            console.error(`[NodePalette] Batch ${this.currentBatch} error:`, data.message, data.fallback);
                            this.isLoading = false;
                        }
                    }
                }
            }
            
        } catch (error) {
            console.error(`[NodePalette] Batch ${this.currentBatch} load error:`, error);
            this.isLoading = false;
        }
    }
    
    appendNode(node) {
        /**
         * Append a new node card to the masonry layout.
         * 
         * @param {Object} node - Node data from backend
         */
        this.nodes.push(node);
        
        const container = document.getElementById('node-palette-grid');
        if (!container) return;
        
        const card = this.createNodeCard(node);
        container.appendChild(card);
        
        // Fade in animation
        setTimeout(() => {
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, 10);
        
        // Update selection counter
        this.updateSelectionCounter();
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
        
        if (wasSelected) {
            this.selectedNodes.delete(nodeId);
            card.classList.remove('selected');
            console.log(`[NodePalette-Selection] Deselected: "${node.text}" | Total selected: ${this.selectedNodes.size}/${this.nodes.length}`);
        } else {
            this.selectedNodes.add(nodeId);
            card.classList.add('selected');
            console.log(`[NodePalette-Selection] Selected: "${node.text}" | Total selected: ${this.selectedNodes.size}/${this.nodes.length}`);
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
                ? `Finish (${this.selectedNodes.size} selected)` 
                : 'Select nodes to continue';
            
            // Log button state change
            if (wasDisabled && !finishBtn.disabled) {
                console.log('[NodePalette] Button enabled: "Finish (%d selected)"', this.selectedNodes.size);
            } else if (!wasDisabled && finishBtn.disabled) {
                console.log('[NodePalette] Button disabled: "Select nodes to continue"');
            }
        } else {
            console.error('[NodePalette] Finish button not found when updating counter!');
        }
    }
    
    async logSelection(nodeId, selected, nodeText) {
        /**
         * Send selection event to backend for logging.
         */
        try {
            await fetch('/thinking_mode/node_palette/select_node', {
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
    
    showEndMessage() {
        /**
         * Show message when node generation limits are reached.
         */
        const container = document.getElementById('node-palette-grid');
        if (!container) return;
        
        const endMessage = document.createElement('div');
        endMessage.className = 'end-message';
        endMessage.innerHTML = `
            <p>✓ Generated ${this.nodes.length} nodes from ${this.currentBatch} batches</p>
            <p>Select your favorites and click "Finish"</p>
        `;
        container.appendChild(endMessage);
    }
    
    async finishSelection() {
        /**
         * Finish Node Palette, add selected nodes to Circle Map.
         */
        const selectedCount = this.selectedNodes.size;
        
        console.log('[NodePalette-Finish] ========================================');
        console.log('[NodePalette-Finish] USER CLICKED FINISH BUTTON');
        console.log('[NodePalette-Finish] ========================================');
        console.log(`[NodePalette-Finish] Selected: ${selectedCount}/${this.nodes.length} | Batches: ${this.currentBatch} | Rate: ${((selectedCount/this.nodes.length)*100).toFixed(1)}%`);
        console.log('[NodePalette-Finish] selectedNodes Set:', Array.from(this.selectedNodes));
        
        if (selectedCount === 0) {
            console.warn('[NodePalette-Finish] ⚠ No nodes selected, showing alert');
            alert('Please select at least one node');
            return;
        }
        
        // Filter selected nodes
        const selectedNodesData = this.nodes.filter(n => this.selectedNodes.has(n.id));
        console.log('[NodePalette-Finish] Filtered %d nodes from %d total', selectedNodesData.length, this.nodes.length);
        console.log('[NodePalette-Finish] Selected node texts:', selectedNodesData.map(n => n.text));
        
        // Log finish event to backend
        console.log('[NodePalette-Finish] Sending finish event to backend...');
        try {
            const response = await fetch('/thinking_mode/node_palette/finish', {
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
        this.hidePalettePanel();
        
        // Wait for panel to hide
        await new Promise(resolve => setTimeout(resolve, 350));
        
        // Add selected nodes to Circle Map
        console.log('[NodePalette-Finish] Starting node assembly...');
        await this.assembleNodesToCircleMap(selectedNodesData);
        
        console.log('[NodePalette-Finish] ========================================');
        console.log('[NodePalette-Finish] ✓ FINISH COMPLETE');
        console.log('[NodePalette-Finish] ========================================');
    }
    
    async assembleNodesToCircleMap(selectedNodes) {
        /**
         * Add selected nodes to the Circle Map diagram.
         * Uses InteractiveEditor API for robust integration.
         * 
         * @param {Array} selectedNodes - Array of selected node objects
         */
        console.log('[NodePalette] ========================================');
        console.log('[NodePalette] ASSEMBLING NODES TO CIRCLE MAP');
        console.log('[NodePalette] ========================================');
        console.log('[NodePalette] Selected nodes count: %d', selectedNodes.length);
        console.log('[NodePalette] Selected nodes:', selectedNodes.map(n => n.text));
        
        // Step 1: Verify editor exists
        const editor = window.currentEditor;
        console.log('[NodePalette] Editor check: %s', editor ? '✓ Found' : '✗ Not found');
        
        if (!editor) {
            console.error('[NodePalette] ERROR: No active editor found');
            alert('Error: No active editor found. Please try refreshing the page.');
            return;
        }
        
        console.log('[NodePalette] Editor type: %s', editor.diagramType);
        console.log('[NodePalette] Editor has currentSpec: %s', !!editor.currentSpec);
        console.log('[NodePalette] Editor has render method: %s', typeof editor.render === 'function');
        
        // Step 2: Verify spec exists
        const currentSpec = editor.currentSpec;
        if (!currentSpec) {
            console.error('[NodePalette] ERROR: No current spec found');
            alert('Error: No diagram specification found. Please try refreshing the page.');
            return;
        }
        
        console.log('[NodePalette] Current spec keys: %s', Object.keys(currentSpec).join(', '));
        console.log('[NodePalette] Current context nodes: %d', currentSpec.context ? currentSpec.context.length : 0);
        
        // Step 3: Initialize context array if needed
        if (!currentSpec.context) {
            console.log('[NodePalette] Creating new context array');
            currentSpec.context = [];
        }
        
        const beforeCount = currentSpec.context.length;
        
        // Step 4: Add selected nodes
        console.log('[NodePalette] Adding nodes to context array...');
        for (let i = 0; i < selectedNodes.length; i++) {
            const node = selectedNodes[i];
            const newNode = {
                text: node.text,
                id: `context_${currentSpec.context.length}`
            };
            currentSpec.context.push(newNode);
            console.log('[NodePalette]   [%d/%d] Added: "%s" (id: %s)', 
                       i+1, selectedNodes.length, node.text, newNode.id);
        }
        
        const afterCount = currentSpec.context.length;
        console.log('[NodePalette] Context array updated: %d → %d nodes (+%d)', 
                   beforeCount, afterCount, afterCount - beforeCount);
        
        // Step 5: Re-render the diagram
        console.log('[NodePalette] Calling editor.render()...');
        try {
            // Try different render methods based on editor type
            if (typeof editor.render === 'function') {
                const renderResult = await editor.render();
                console.log('[NodePalette] ✓ editor.render() completed:', renderResult);
            } else if (typeof editor.renderDiagram === 'function') {
                await editor.renderDiagram(currentSpec);
                console.log('[NodePalette] ✓ editor.renderDiagram() completed');
            } else if (typeof editor.update === 'function') {
                await editor.update();
                console.log('[NodePalette] ✓ editor.update() completed');
            } else {
                console.error('[NodePalette] ERROR: No render method found on editor');
                console.error('[NodePalette] Available methods:', Object.keys(editor).filter(k => typeof editor[k] === 'function'));
                alert('Error: Cannot render diagram. Please try refreshing the page.');
                return;
            }
            
            // Step 6: Save to history
            console.log('[NodePalette] Checking history save...');
            if (typeof editor.saveHistoryState === 'function') {
                editor.saveHistoryState('node_palette_add');
                console.log('[NodePalette] ✓ History saved');
            } else if (typeof editor.saveHistory === 'function') {
                editor.saveHistory('node_palette_add');
                console.log('[NodePalette] ✓ History saved (alternative method)');
            } else {
                console.warn('[NodePalette] ⚠ No history save method found (this is OK)');
            }
            
            console.log('[NodePalette] ========================================');
            console.log('[NodePalette] ✓ SUCCESS: Nodes added to Circle Map');
            console.log('[NodePalette] ========================================');
            
        } catch (error) {
            console.error('[NodePalette] ========================================');
            console.error('[NodePalette] ✗ ERROR: Failed to render Circle Map');
            console.error('[NodePalette] Error message:', error.message);
            console.error('[NodePalette] Error stack:', error.stack);
            console.error('[NodePalette] ========================================');
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

