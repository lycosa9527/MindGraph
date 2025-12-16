/**
 * Tab Mode Manager
 * ================
 * 
 * Manages Tab Mode feature: autocomplete suggestions and node expansion.
 * 
 * Features:
 * - Editing Mode: Autocomplete suggestions when typing in inputs
 * - Viewing Mode: Node expansion when pressing Tab on selected nodes
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * @author MindGraph Team
 */

class TabModeManager {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger || console;
        
        // Owner ID for Event Bus Listener Registry
        this.ownerId = 'TabModeManager';
        
        // Tab Mode state
        this.enabled = false;
        this.currentRequest = null; // AbortController for request cancellation
        this.debounceTimer = null;
        this.debounceDelay = 300; // ms
        
        // UI elements
        this.tabModeButton = null;
        this.suggestionOverlay = null;
        this.suggestions = [];
        this.selectedIndex = 0;
        
        // Current editing context
        this.currentInput = null;
        this.currentNodeId = null;
        this.currentDiagramType = null;
        
        // Initialize
        this.initializeElements();
        this.attachEventListeners();
        this.subscribeToEvents();
        
        this.logger.info('TabModeManager', 'Tab Mode Manager initialized');
    }
    
    /**
     * Initialize DOM elements
     */
    initializeElements() {
        // Tab Mode button (will be added to editor.html)
        this.tabModeButton = document.getElementById('tab-mode-btn');
        
        // Suggestion overlay (created dynamically)
        this.suggestionOverlay = null;
        
        if (!this.tabModeButton) {
            this.logger.warn('TabModeManager', 'Tab Mode button not found');
        }
    }
    
    /**
     * Attach event listeners
     */
    attachEventListeners() {
        // Tab Mode button toggle
        if (this.tabModeButton) {
            this.tabModeButton.addEventListener('click', () => {
                this.toggleTabMode();
            });
        }
        
        // Global keyboard handler for viewing mode expansion
        document.addEventListener('keydown', (e) => {
            this.handleGlobalKeydown(e);
        }, true); // Use capture phase to intercept before other handlers
    }
    
    /**
     * Subscribe to Event Bus events
     */
    subscribeToEvents() {
        // Listen for node selection changes (for viewing mode expansion)
        this.eventBus.onWithOwner('node:selected', (data) => {
            this.handleNodeSelection(data);
        }, this.ownerId);
        
        // Listen for diagram type changes
        this.eventBus.onWithOwner('diagram:type_changed', (data) => {
            this.currentDiagramType = data.type;
        }, this.ownerId);
        
        // Listen for diagram spec updates
        this.eventBus.onWithOwner('diagram:spec_updated', (data) => {
            // Context may have changed, clear suggestions if needed
            if (this.suggestions.length > 0) {
                this.hideSuggestions();
            }
        }, this.ownerId);
    }
    
    /**
     * Toggle Tab Mode on/off
     */
    toggleTabMode() {
        this.enabled = !this.enabled;
        
        if (this.tabModeButton) {
            // Toggle active class for visual feedback
            if (this.enabled) {
                this.tabModeButton.classList.add('active');
                this.tabModeButton.title = 'Disable Tab Mode (Click to turn off)';
            } else {
                this.tabModeButton.classList.remove('active');
                this.tabModeButton.title = 'Enable Tab Mode (Click to turn on)';
            }
        }
        
        this.logger.info('TabModeManager', `Tab Mode ${this.enabled ? 'enabled' : 'disabled'}`);
        
        // Emit event
        this.eventBus.emit('tab_mode:toggled', {
            enabled: this.enabled
        });
        
        // If disabling, hide suggestions
        if (!this.enabled) {
            this.hideSuggestions();
        }
    }
    
    /**
     * Handle global keydown events (for viewing mode expansion)
     */
    handleGlobalKeydown(event) {
        // Only handle Tab key when Tab Mode is enabled
        if (!this.enabled) return;
        
        // Ignore if user is typing in an input/textarea
        const activeElement = document.activeElement;
        const isTyping = activeElement && (
            activeElement.tagName === 'INPUT' ||
            activeElement.tagName === 'TEXTAREA' ||
            activeElement.isContentEditable
        );
        
        // Viewing Mode: Tab key on selected node → Expand
        if (event.key === 'Tab' && !isTyping && !event.shiftKey) {
            const selectedNodes = this.stateManager.getDiagramState()?.selectedNodes || [];
            if (selectedNodes.length === 1) {
                event.preventDefault();
                event.stopPropagation(); // Prevent Tab from triggering other handlers (e.g., MindMate panel)
                this.handleNodeExpansion(selectedNodes[0]);
                return; // Exit early to prevent further processing
            }
        }
    }
    
    /**
     * Handle node selection (for viewing mode expansion context)
     */
    handleNodeSelection(data) {
        // Store current selection for expansion
        // Expansion happens on Tab key press
    }
    
    /**
     * Handle node expansion (Viewing Mode)
     */
    async handleNodeExpansion(nodeId) {
        if (!this.enabled) return;
        
        this.logger.debug('TabModeManager', 'Handling node expansion', { nodeId });
        
        try {
            // Get editor instance
            const editor = window.currentEditor;
            if (!editor) {
                this.logger.warn('TabModeManager', 'No editor instance found');
                return;
            }
            
            // Extract expansion context
            const context = this.extractExpansionContext(editor, nodeId);
            if (!context) {
                this.logger.warn('TabModeManager', 'Failed to extract expansion context');
                return;
            }
            
            this.logger.debug('TabModeManager', 'Expansion context extracted', {
                nodeId: context.nodeId,
                nodeText: context.nodeText,
                nodeType: context.nodeType,
                mainTopic: context.mainTopic,
                existingChildrenCount: context.existingChildren?.length || 0,
                diagramType: context.diagramType
            });
            
            // Check if node is expandable
            if (!this.isNodeExpandable(context.diagramType, context.nodeType)) {
                this.logger.debug('TabModeManager', 'Node is not expandable', { 
                    diagramType: context.diagramType,
                    nodeType: context.nodeType 
                });
                return;
            }
            
            // Show loading indicator
            this.showExpansionLoading(nodeId);
            
            // Call API
            this.logger.info('TabModeManager', 'Requesting expansion from API', {
                nodeText: context.nodeText,
                mainTopic: context.mainTopic
            });
            const response = await this.requestExpansion(context);
            
            this.logger.debug('TabModeManager', 'Expansion API response', {
                success: response.success,
                childrenCount: response.children?.length || 0,
                error: response.error
            });
            
            if (response.success && response.children && response.children.length > 0) {
                // Apply expansion to diagram
                this.applyExpansion(editor, nodeId, response.children, context);
                
                // Emit event
                this.eventBus.emit('tab_mode:node_expanded', {
                    nodeId,
                    children: response.children
                });
                
                this.logger.info('TabModeManager', 'Expansion completed successfully', {
                    nodeId,
                    childrenAdded: response.children.length
                });
            } else {
                this.logger.warn('TabModeManager', 'Expansion failed or empty', response);
            }
            
        } catch (error) {
            this.logger.error('TabModeManager', 'Error handling node expansion', error);
        } finally {
            this.hideExpansionLoading();
        }
    }
    
    /**
     * Extract expansion context from editor and node
     */
    extractExpansionContext(editor, nodeId) {
        if (!editor || !nodeId) {
            this.logger.warn('TabModeManager', 'Missing editor or nodeId for expansion context');
            return null;
        }
        
        const spec = editor.currentSpec;
        const diagramType = editor.diagramType;
        
        // Get node element from DOM
        const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);
        if (nodeElement.empty()) {
            this.logger.warn('TabModeManager', `Node element not found: ${nodeId}`);
            return null;
        }
        
        const nodeType = nodeElement.attr('data-node-type') || 'branch';
        
        // Extract node text using the same pattern as PropertyPanelManager
        let nodeText = '';
        let textElement = null;
        
        // Check if this is a dimension node - special handling needed
        if (nodeType === 'dimension') {
            // For dimension nodes, get the actual value from data-dimension-value attribute
            nodeText = nodeElement.attr('data-dimension-value') || '';
            // Still find the text element for potential future use
            textElement = d3.select(`[data-text-for="${nodeId}"]`);
            if (textElement.empty()) {
                textElement = nodeElement.select('text');
            }
        } else {
            // Regular node handling - get display text
            // Method 1: Try finding text elements by data-node-id (for multi-line text)
            let textElements = d3.selectAll(`text[data-node-id="${nodeId}"]`);
            if (!textElements.empty()) {
                textElement = d3.select(textElements.node()); // Get first for attributes
                // Use extractTextFromSVG to handle multi-line text
                nodeText = (typeof window.extractTextFromSVG === 'function') 
                    ? window.extractTextFromSVG(textElement) 
                    : (textElement.text() || '');
            } else {
                // Method 2: Try as child
                textElement = nodeElement.select('text');
                if (!textElement.empty()) {
                    nodeText = (typeof window.extractTextFromSVG === 'function') 
                        ? window.extractTextFromSVG(textElement) 
                        : (textElement.text() || '');
                } else {
                    // Method 3: Try data-text-for attribute
                    textElement = d3.select(`[data-text-for="${nodeId}"]`);
                    if (!textElement.empty()) {
                        nodeText = (typeof window.extractTextFromSVG === 'function') 
                            ? window.extractTextFromSVG(textElement) 
                            : (textElement.text() || '');
                    } else {
                        // Method 4: Try nextElementSibling
                        const node = nodeElement.node();
                        if (node) {
                            const nextSibling = node.nextElementSibling;
                            if (nextSibling && nextSibling.tagName === 'text') {
                                textElement = d3.select(nextSibling);
                                nodeText = (typeof window.extractTextFromSVG === 'function') 
                                    ? window.extractTextFromSVG(textElement) 
                                    : (textElement.text() || '');
                            }
                        }
                    }
                }
            }
        }
        
        // Fallback: if still no text, try to get from spec
        if (!nodeText && spec) {
            // Try to extract from spec based on nodeId pattern
            if (diagramType === 'mindmap') {
                const branchMatch = nodeId.match(/branch_(\d+)/);
                if (branchMatch) {
                    const branchIndex = parseInt(branchMatch[1]);
                    const branch = spec.children?.[branchIndex];
                    if (branch) {
                        nodeText = branch.label || branch.text || '';
                    }
                }
            }
        }
        
        // Extract main topic and existing children based on diagram type
        let mainTopic = '';
        let existingChildren = [];
        
        if (diagramType === 'mindmap') {
            mainTopic = spec.topic || '';
            // Extract branch index from node ID
            const branchMatch = nodeId.match(/branch_(\d+)/);
            if (branchMatch) {
                const branchIndex = parseInt(branchMatch[1]);
                const branch = spec.children?.[branchIndex];
                if (branch && branch.children) {
                    existingChildren = branch.children.map(c => c.label || c.text || c);
                }
            }
        } else if (diagramType === 'tree_map') {
            mainTopic = spec.topic || '';
            const categoryMatch = nodeId.match(/tree-category-(\d+)/);
            if (categoryMatch) {
                const categoryIndex = parseInt(categoryMatch[1]);
                const category = spec.children?.[categoryIndex];
                if (category && category.children) {
                    existingChildren = category.children.map(item => item.text || item);
                }
            }
        } else if (diagramType === 'flow_map') {
            mainTopic = spec.title || '';
            const stepMatch = nodeId.match(/step_(\d+)/);
            if (stepMatch) {
                const stepIndex = parseInt(stepMatch[1]);
                const step = spec.steps?.[stepIndex];
                if (step && step.substeps) {
                    existingChildren = step.substeps.map(s => s.text || s);
                }
            }
        } else if (diagramType === 'brace_map') {
            mainTopic = spec.whole || '';
            const partMatch = nodeId.match(/part_(\d+)/);
            if (partMatch) {
                const partIndex = parseInt(partMatch[1]);
                const part = spec.parts?.[partIndex];
                if (part && part.subparts) {
                    existingChildren = part.subparts.map(p => p.text || p);
                }
            }
        }
        
        return {
            diagramType,
            nodeId,
            nodeType,
            nodeText,
            mainTopic,
            existingChildren
        };
    }
    
    /**
     * Check if node type is expandable for given diagram type
     */
    isNodeExpandable(diagramType, nodeType) {
        const expandableTypes = {
            'mindmap': ['branch'],
            'tree_map': ['category'],
            'flow_map': ['step'],
            'brace_map': ['part']
        };
        
        const types = expandableTypes[diagramType] || [];
        return types.includes(nodeType);
    }
    
    /**
     * Request expansion from API
     */
    async requestExpansion(context) {
        // Cancel previous request if any
        if (this.currentRequest) {
            this.currentRequest.abort();
        }
        
        this.currentRequest = new AbortController();
        
        // Get session ID from editor
        const sessionId = window.currentEditor?.sessionId || 
                          window.diagramSelector?.currentSession?.id || 
                          window.sessionLifecycle?.currentSessionId || 
                          null;
        
        const requestBody = {
            mode: 'expansion',
            diagram_type: context.diagramType,
            node_id: context.nodeId,
            node_text: context.nodeText,
            node_type: context.nodeType,
            main_topic: context.mainTopic,
            existing_children: context.existingChildren,
            num_children: 4,
            language: window.languageManager?.getCurrentLanguage() || this.stateManager.getState()?.ui?.language || 'en',
            llm: 'qwen',
            session_id: sessionId
        };
        
        this.logger.debug('TabModeManager', 'Sending expansion request', requestBody);
        
        try {
            const response = await fetch('/api/tab_expand', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestBody),
                signal: this.currentRequest.signal
            });
            
            if (!response.ok) {
                const errorText = await response.text();
                this.logger.error('TabModeManager', 'API error response', {
                    status: response.status,
                    statusText: response.statusText,
                    body: errorText
                });
                throw new Error(`API error: ${response.status} - ${errorText}`);
            }
            
            const data = await response.json();
            this.logger.debug('TabModeManager', 'Expansion API response received', {
                success: data.success,
                childrenCount: data.children?.length || 0
            });
            return data;
            
        } catch (error) {
            if (error.name === 'AbortError') {
                this.logger.debug('TabModeManager', 'Expansion request cancelled');
            } else {
                this.logger.error('TabModeManager', 'Expansion request failed', error);
            }
            return { success: false, error: error.message };
        } finally {
            this.currentRequest = null;
        }
    }
    
    /**
     * Apply expansion to diagram
     */
    applyExpansion(editor, nodeId, children, context) {
        this.logger.debug('TabModeManager', 'Applying expansion', {
            nodeId,
            childrenCount: children.length,
            diagramType: context.diagramType
        });
        
        // Update spec based on diagram type
        const spec = editor.currentSpec;
        
        if (context.diagramType === 'mindmap') {
            const branchMatch = nodeId.match(/branch_(\d+)/);
            if (branchMatch) {
                const branchIndex = parseInt(branchMatch[1]);
                this.logger.debug('TabModeManager', 'Adding children to mindmap branch', {
                    branchIndex,
                    branchLabel: spec.children[branchIndex]?.label,
                    existingChildrenCount: spec.children[branchIndex]?.children?.length || 0,
                    newChildrenCount: children.length
                });
                
                if (!spec.children[branchIndex]) {
                    this.logger.error('TabModeManager', 'Branch not found', { branchIndex, totalBranches: spec.children.length });
                    return;
                }
                
                if (!spec.children[branchIndex].children) {
                    spec.children[branchIndex].children = [];
                }
                
                // Helper function to detect placeholder text
                const isPlaceholder = (text) => {
                    if (!text || typeof text !== 'string') return false;
                    const trimmed = text.trim();
                    // Check for common placeholder patterns
                    const placeholderPatterns = [
                        // Chinese patterns
                        /^子项\d+\.\d+$/,  // 子项1.1, 子项1.2, etc.
                        /^Sub-item \d+\.\d+$/i,  // Sub-item 1.1, Sub-item 1.2, etc.
                        /^Subitem \d+\.\d+$/i,   // Subitem 1.1, etc.
                        /^Child \d+\.\d+$/i,     // Child 1.1, etc.
                        /^Item \d+\.\d+$/i,      // Item 1.1, etc.
                        // Generic "New" patterns
                        /^New (Subitem|Child|Item)/i,
                        /^新(子项|项目|节点)/i
                    ];
                    return placeholderPatterns.some(pattern => pattern.test(trimmed));
                };
                
                // Find placeholder children to replace
                const existingChildren = spec.children[branchIndex].children;
                const placeholderIndices = [];
                existingChildren.forEach((child, index) => {
                    const childText = child.label || child.text || '';
                    if (isPlaceholder(childText)) {
                        placeholderIndices.push(index);
                    }
                });
                
                this.logger.debug('TabModeManager', 'Placeholder detection', {
                    branchIndex,
                    totalExistingChildren: existingChildren.length,
                    placeholderCount: placeholderIndices.length,
                    placeholderIndices
                });
                
                // Replace placeholders first, then append remaining
                let childIndex = 0;
                const numToReplace = Math.min(placeholderIndices.length, children.length);
                
                // Replace placeholders
                for (let i = 0; i < numToReplace; i++) {
                    const placeholderIdx = placeholderIndices[i];
                    const child = children[childIndex];
                    const childId = child.id || existingChildren[placeholderIdx].id || `sub_${branchIndex}_${placeholderIdx}`;
                    
                    // Replace the placeholder child
                    spec.children[branchIndex].children[placeholderIdx] = {
                        id: childId,
                        label: child.text,
                        text: child.text,
                        children: existingChildren[placeholderIdx].children || [] // Preserve nested children if any
                    };
                    childIndex++;
                }
                
                // Append remaining generated children if we have more than placeholders
                if (childIndex < children.length) {
                    for (let i = childIndex; i < children.length; i++) {
                        const child = children[i];
                        const existingCount = spec.children[branchIndex].children.length;
                        const childId = child.id || `sub_${branchIndex}_${existingCount}`;
                        spec.children[branchIndex].children.push({
                            id: childId,
                            label: child.text,
                            text: child.text,
                            children: []
                        });
                    }
                }
                
                this.logger.info('TabModeManager', 'Children added to mindmap branch', {
                    branchIndex,
                    totalChildren: spec.children[branchIndex].children.length,
                    addedChildren: children.map(c => c.text)
                });
            } else {
                this.logger.warn('TabModeManager', 'Invalid nodeId format for mindmap', { nodeId });
            }
        } else if (context.diagramType === 'tree_map') {
            const categoryMatch = nodeId.match(/tree-category-(\d+)/);
            if (categoryMatch) {
                const categoryIndex = parseInt(categoryMatch[1]);
                if (!spec.children[categoryIndex].children) {
                    spec.children[categoryIndex].children = [];
                }
                children.forEach(child => {
                    spec.children[categoryIndex].children.push({
                        text: child.text,
                        id: child.id
                    });
                });
            }
        }
        // Similar logic for flow_map and brace_map...
        
        // Update state manager first
        if (this.stateManager && typeof this.stateManager.updateDiagram === 'function') {
            this.stateManager.updateDiagram({
                data: spec
            });
            this.logger.debug('TabModeManager', 'State manager updated');
        } else {
            this.logger.warn('TabModeManager', 'State manager updateDiagram method not available');
        }
        
        // For mindmap, trigger layout recalculation to update positions for new children
        if (context.diagramType === 'mindmap') {
            this.logger.debug('TabModeManager', 'Triggering mindmap layout recalculation');
            this.eventBus.emit('mindmap:layout_recalculation_requested', {
                spec: spec,
                source: 'tab_mode_expansion'
            });
        } else {
            // For other diagram types, just trigger re-render
            this.logger.debug('TabModeManager', 'Triggering editor re-render via event');
            this.eventBus.emit('diagram:spec_updated', {
                spec: spec,
                source: 'tab_mode_expansion'
            });
        }
    }
    
    /**
     * Show expansion loading indicator
     */
    showExpansionLoading(nodeId) {
        const nodeElement = d3.select(`[data-node-id="${nodeId}"]`);
        if (!nodeElement.empty()) {
            nodeElement.append('circle')
                .attr('class', 'tab-mode-loading')
                .attr('r', 8)
                .attr('fill', '#4CAF50')
                .attr('opacity', 0.7)
                .style('animation', 'pulse 1s infinite');
        }
    }
    
    /**
     * Hide expansion loading indicator
     */
    hideExpansionLoading() {
        d3.selectAll('.tab-mode-loading').remove();
    }
    
    /**
     * Setup autocomplete for input element (Editing Mode)
     */
    setupAutocomplete(inputElement, nodeId, diagramType) {
        if (!this.enabled) return;
        
        this.currentInput = inputElement;
        this.currentNodeId = nodeId;
        this.currentDiagramType = diagramType;
        
        // Debounced input handler
        inputElement.addEventListener('input', (e) => {
            this.handleInputChange(e);
        });
        
        // Tab key handler for accepting suggestions
        inputElement.addEventListener('keydown', (e) => {
            this.handleInputKeydown(e);
        });
        
        // Focus/blur handlers
        inputElement.addEventListener('focus', () => {
            // Show suggestions if there's partial input
            if (inputElement.value.trim().length >= 2) {
                this.handleInputChange({ target: inputElement });
            }
        });
        
        inputElement.addEventListener('blur', () => {
            // Delay hiding to allow clicking on suggestions
            setTimeout(() => {
                this.hideSuggestions();
            }, 200);
        });
    }
    
    /**
     * Handle input change (debounced)
     */
    handleInputChange(event) {
        const inputElement = event.target;
        const partialInput = inputElement.value;
        
        // Clear previous debounce timer
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }
        
        // Debounce API calls
        this.debounceTimer = setTimeout(() => {
            if (partialInput.trim().length >= 2) {
                this.requestSuggestions(inputElement, partialInput);
            } else {
                this.hideSuggestions();
            }
        }, this.debounceDelay);
    }
    
    /**
     * Handle input keydown (Tab to accept, Arrow keys to navigate)
     */
    handleInputKeydown(event) {
        if (!this.enabled) return;
        
        // Tab key: Accept selected suggestion
        if (event.key === 'Tab' && this.suggestions.length > 0) {
            event.preventDefault();
            this.acceptSuggestion(this.selectedIndex);
            return;
        }
        
        // Arrow keys: Navigate suggestions
        if (event.key === 'ArrowDown') {
            event.preventDefault();
            this.selectedIndex = Math.min(this.selectedIndex + 1, this.suggestions.length - 1);
            this.updateSuggestionHighlight();
            return;
        }
        
        if (event.key === 'ArrowUp') {
            event.preventDefault();
            this.selectedIndex = Math.max(this.selectedIndex - 1, 0);
            this.updateSuggestionHighlight();
            return;
        }
        
        // Escape: Hide suggestions
        if (event.key === 'Escape') {
            this.hideSuggestions();
            return;
        }
    }
    
    /**
     * Request suggestions from API
     */
    async requestSuggestions(inputElement, partialInput) {
        // Cancel previous request
        if (this.currentRequest) {
            this.currentRequest.abort();
        }
        
        this.currentRequest = new AbortController();
        
        try {
            // Extract context
            const context = this.extractAutocompleteContext(inputElement, partialInput);
            if (!context) {
                return;
            }
            
            const response = await fetch('/api/tab_suggestions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    mode: 'autocomplete',
                    diagram_type: context.diagramType,
                    main_topics: context.mainTopics,
                    node_category: context.nodeCategory,
                    partial_input: partialInput,
                    existing_nodes: context.existingNodes,
                    language: window.languageManager?.getCurrentLanguage() || this.stateManager.getState()?.ui?.language || 'en',
                    llm: 'qwen',
                    cursor_position: inputElement.selectionStart
                }),
                signal: this.currentRequest.signal
            });
            
            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.success && data.suggestions.length > 0) {
                this.suggestions = data.suggestions.map(s => s.text);
                this.selectedIndex = 0;
                this.showSuggestions(inputElement);
            } else {
                this.hideSuggestions();
            }
            
        } catch (error) {
            if (error.name === 'AbortError') {
                this.logger.debug('TabModeManager', 'Suggestion request cancelled');
            } else {
                this.logger.error('TabModeManager', 'Suggestion request failed', error);
            }
            this.hideSuggestions();
        } finally {
            this.currentRequest = null;
        }
    }
    
    /**
     * Extract autocomplete context from input element
     */
    extractAutocompleteContext(inputElement, partialInput) {
        const editor = window.currentEditor;
        if (!editor) {
            this.logger.warn('TabModeManager', 'No editor instance found');
            return null;
        }
        
        const spec = editor.currentSpec;
        const diagramType = editor.diagramType || this.currentDiagramType;
        
        // Extract main topics based on diagram type
        let mainTopics = [];
        let nodeCategory = null;
        let existingNodes = [];
        
        if (diagramType === 'double_bubble_map') {
            mainTopics = [spec.left || '', spec.right || ''];
            // Determine category from node ID
            if (this.currentNodeId) {
                if (this.currentNodeId.startsWith('similarity_')) {
                    nodeCategory = 'similarities';
                    existingNodes = (spec.similarities || []).map(n => typeof n === 'string' ? n : n.text || n);
                } else if (this.currentNodeId.startsWith('left_diff_')) {
                    nodeCategory = 'left_differences';
                    existingNodes = (spec.left_differences || []).map(n => typeof n === 'string' ? n : n.text || n);
                } else if (this.currentNodeId.startsWith('right_diff_')) {
                    nodeCategory = 'right_differences';
                    existingNodes = (spec.right_differences || []).map(n => typeof n === 'string' ? n : n.text || n);
                }
            }
        } else if (diagramType === 'mindmap') {
            mainTopics = [spec.topic || ''];
            // For child nodes, need parent branch
            if (this.currentNodeId) {
                const childMatch = this.currentNodeId.match(/child_(\d+)_(\d+)/);
                if (childMatch) {
                    const branchIndex = parseInt(childMatch[1]);
                    const branch = spec.children?.[branchIndex];
                    if (branch) {
                        mainTopics.push(branch.label || branch.text || '');
                        nodeCategory = 'children';
                        existingNodes = (branch.children || []).map(c => c.label || c.text || c);
                    }
                }
            }
        } else {
            // Generic diagram
            mainTopics = [spec.topic || spec.title || ''];
        }
        
        return {
            diagramType,
            mainTopics,
            nodeCategory,
            existingNodes
        };
    }
    
    /**
     * Show suggestions overlay
     */
    showSuggestions(inputElement) {
        if (!this.suggestions.length) return;
        
        // Remove existing overlay
        this.hideSuggestions();
        
        // Get input position
        const rect = inputElement.getBoundingClientRect();
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;
        
        // Create overlay
        this.suggestionOverlay = d3.select('body')
            .append('div')
            .attr('class', 'tab-mode-suggestions')
            .style('position', 'absolute')
            .style('top', `${rect.bottom + scrollTop + 4}px`)
            .style('left', `${rect.left + scrollLeft}px`)
            .style('background', 'white')
            .style('border', '1px solid #ddd')
            .style('border-radius', '4px')
            .style('box-shadow', '0 4px 12px rgba(0,0,0,0.15)')
            .style('z-index', 10001)
            .style('max-height', '200px')
            .style('overflow-y', 'auto')
            .style('min-width', `${rect.width}px`);
        
        // Add suggestions
        const suggestionList = this.suggestionOverlay
            .append('ul')
            .style('list-style', 'none')
            .style('margin', 0)
            .style('padding', '4px 0');
        
        this.suggestions.forEach((suggestion, index) => {
            const item = suggestionList
                .append('li')
                .attr('class', 'tab-mode-suggestion-item')
                .attr('data-index', index)
                .style('padding', '8px 12px')
                .style('cursor', 'pointer')
                .text(suggestion);
            
            // Highlight selected
            if (index === this.selectedIndex) {
                item.style('background', '#f0f0f0');
            }
            
            // Click handler
            item.on('click', () => {
                this.acceptSuggestion(index);
            });
            
            // Hover handler
            item.on('mouseenter', function() {
                d3.select(this).style('background', '#f0f0f0');
            }).on('mouseleave', function() {
                if (d3.select(this).attr('data-index') != this.selectedIndex) {
                    d3.select(this).style('background', 'transparent');
                }
            });
        });
        
        this.updateSuggestionHighlight();
    }
    
    /**
     * Update suggestion highlight
     */
    updateSuggestionHighlight() {
        if (!this.suggestionOverlay) return;
        
        this.suggestionOverlay.selectAll('.tab-mode-suggestion-item')
            .style('background', (d, i) => i === this.selectedIndex ? '#f0f0f0' : 'transparent');
    }
    
    /**
     * Accept suggestion
     */
    acceptSuggestion(index) {
        if (index < 0 || index >= this.suggestions.length) return;
        if (!this.currentInput) return;
        
        const suggestion = this.suggestions[index];
        const inputElement = this.currentInput;
        
        // Insert suggestion at cursor position
        const start = inputElement.selectionStart;
        const end = inputElement.selectionEnd;
        const value = inputElement.value;
        const before = value.substring(0, start);
        const after = value.substring(end);
        
        // Find where partial input starts (for replacement)
        const partialInput = value.substring(0, start);
        const lastSpace = partialInput.lastIndexOf(' ');
        const replaceStart = lastSpace + 1;
        
        const newValue = value.substring(0, replaceStart) + suggestion + after;
        inputElement.value = newValue;
        
        // Set cursor after inserted text
        const newCursorPos = replaceStart + suggestion.length;
        inputElement.setSelectionRange(newCursorPos, newCursorPos);
        
        // Hide suggestions
        this.hideSuggestions();
        
        // Trigger input event for other listeners
        inputElement.dispatchEvent(new Event('input', { bubbles: true }));
        
        // Focus back on input
        inputElement.focus();
    }
    
    /**
     * Hide suggestions overlay
     */
    hideSuggestions() {
        if (this.suggestionOverlay) {
            this.suggestionOverlay.remove();
            this.suggestionOverlay = null;
        }
        this.suggestions = [];
        this.selectedIndex = 0;
    }
    
    /**
     * Cleanup on destroy
     */
    destroy() {
        // Cancel any pending requests
        if (this.currentRequest) {
            this.currentRequest.abort();
        }
        
        // Clear timers
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }
        
        // Hide suggestions
        this.hideSuggestions();
        
        // Remove event listeners
        this.eventBus.offAny((event, callback) => {
            // Remove all listeners owned by this manager
            // EventBus will handle cleanup via ownerId
        });
        
        this.logger.info('TabModeManager', 'Tab Mode Manager destroyed');
    }
}


