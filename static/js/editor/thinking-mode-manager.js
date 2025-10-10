/**
 * ThinkGuide Mode Manager
 * =======================
 * 
 * Manages Socratic guided thinking workflow for diagrams.
 * Provides SSE streaming, state management, and UI updates.
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 */

class ThinkingModeManager {
    constructor() {
        this.panel = null;
        this.messagesContainer = null;
        this.inputArea = null;
        this.sendBtn = null;
        this.progressFill = null;
        this.progressLabel = null;
        this.closeBtn = null;
        
        // State management
        this.sessionId = null;
        this.currentState = 'CONTEXT_GATHERING';
        this.isStreaming = false;
        this.diagramType = null;
        this.language = 'en'; // Detected language (en/zh)
        
        // Initialize Markdown renderer
        if (window.markdownit) {
            this.md = window.markdownit({
                html: false,
                linkify: true,
                breaks: false  // Don't convert single line breaks to <br> - prevents text fragmentation
            });
        } else {
            console.warn('[ThinkGuide] markdownit not loaded, using plain text');
            this.md = null;
        }
        
        // Language-aware labels
        this.labels = {
            en: {
                starting: 'Starting...',
                contextGathering: 'Gathering Context...',
                educationalAnalysis: 'Analyzing Nodes...',
                analysis: 'Socratic Analysis...',
                refinement1: 'First Refinement...',
                refinement2: 'Second Refinement...',
                finalRefinement: 'Final Refinement...',
                complete: 'Complete!'
            },
            zh: {
                starting: '启动中...',
                contextGathering: '收集背景信息...',
                educationalAnalysis: '分析节点...',
                analysis: '苏格拉底式分析...',
                refinement1: '第一次优化...',
                refinement2: '第二次优化...',
                finalRefinement: '最后优化...',
                complete: '完成！'
            }
        };
        
        // Logger reference
        this.logger = window.logger || console;
    }
    
    /**
     * Initialize the thinking mode manager
     */
    init() {
        // Get DOM elements
        this.panel = document.getElementById('thinking-panel');
        this.messagesContainer = document.getElementById('thinking-messages');
        this.inputArea = document.getElementById('thinking-input');
        this.sendBtn = document.getElementById('thinking-send-btn');
        this.progressFill = document.getElementById('thinking-progress-fill');
        this.progressLabel = document.getElementById('thinking-progress-label');
        this.closeBtn = document.getElementById('thinking-close-btn');
        
        if (!this.panel) {
            this.logger.warn('[ThinkGuide] Panel not found');
            return;
        }
        
        // Event listeners
        this.sendBtn.addEventListener('click', () => this.handleSendMessage());
        this.inputArea.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.handleSendMessage();
            }
        });
        this.closeBtn.addEventListener('click', () => this.closePanel());
        
        this.logger.info('[ThinkGuide] Initialized successfully');
    }
    
    /**
     * Start thinking mode for current diagram
     */
    async startThinkingMode(diagramType, diagramData) {
        this.logger.info(`[ThinkGuide] Starting for diagram: ${diagramType}`);
        
        // Detect language from diagram
        this.detectLanguage(diagramData);
        
        // Reset state
        this.diagramType = diagramType;
        this.sessionId = `thinking_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        this.currentState = 'CONTEXT_GATHERING';
        this.isStreaming = false;
        
        // Clear UI
        this.messagesContainer.innerHTML = '';
        this.inputArea.value = '';
        const lang = this.labels[this.language] || this.labels.en;
        this.updateProgress(0, lang.starting);
        
        // Open panel
        this.openPanel();
        
        // Start first message stream (empty message to trigger context gathering)
        await this.sendMessage('', diagramData);
    }
    
    /**
     * Send message to backend
     */
    async sendMessage(message, diagramData) {
        if (this.isStreaming) {
            this.logger.warn('[ThinkGuide] Already streaming, ignoring request');
            return;
        }
        
        this.isStreaming = true;
        this.sendBtn.disabled = true;
        this.inputArea.disabled = true;
        
        // If user sent a message, display it
        if (message.trim()) {
            this.addUserMessage(message);
            this.inputArea.value = '';
        }
        
        try {
            // Extract current diagram data (fresh with every message)
            const currentDiagramData = diagramData || this.extractDiagramData();
            
            // Prepare request
            const requestData = {
                message: message,
                user_id: 'user_' + Date.now(),
                session_id: this.sessionId,
                diagram_type: this.diagramType,
                diagram_data: currentDiagramData,
                current_state: this.currentState,
                selected_node: null // TODO: Get from selection manager
            };
            
            this.logger.info('[ThinkGuide] 📊 Sending with current diagram:', {
                message: message.substring(0, 50) + '...',
                center: currentDiagramData.center?.text || 'empty',
                nodeCount: currentDiagramData.children?.length || 0,
                diagramType: this.diagramType
            });
            
            // Stream response
            await this.streamResponse(requestData);
            
        } catch (error) {
            this.logger.error('[ThinkGuide] Error sending message:', error);
            this.addSystemMessage('Error: ' + error.message);
        } finally {
            this.isStreaming = false;
            this.sendBtn.disabled = false;
            this.inputArea.disabled = false;
            this.inputArea.focus();
        }
    }
    
    /**
     * Stream SSE response from backend
     */
    async streamResponse(requestData) {
        // Show typing indicator
        const typingIndicator = this.showTypingIndicator();
        
        try {
            const response = await fetch('/thinking_mode/stream', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            // Remove typing indicator before showing actual message
            if (typingIndicator && typingIndicator.parentNode) {
                typingIndicator.parentNode.removeChild(typingIndicator);
            }
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let currentMessageDiv = this.createAssistantMessageDiv();
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop(); // Keep incomplete line in buffer
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = JSON.parse(line.slice(6));
                        this.handleSSEEvent(data, currentMessageDiv);
                    }
                }
            }
        } catch (error) {
            // Remove typing indicator on error
            if (typingIndicator && typingIndicator.parentNode) {
                typingIndicator.parentNode.removeChild(typingIndicator);
            }
            throw error;
        }
    }
    
    /**
     * Handle incoming SSE events
     */
    handleSSEEvent(data, contentDiv) {
        const { event, content, new_state, progress, message } = data;
        
        switch (event) {
            case 'message_chunk':
                // Accumulate text in buffer
                if (!contentDiv.dataset.rawText) {
                    contentDiv.dataset.rawText = '';
                }
                contentDiv.dataset.rawText += content;
                
                // Render markdown continuously (like MindMate)
                // breaks: false prevents Chinese text fragmentation
                if (this.md && window.DOMPurify) {
                    const html = this.md.render(contentDiv.dataset.rawText);
                    contentDiv.innerHTML = DOMPurify.sanitize(html);
                } else {
                    contentDiv.textContent = contentDiv.dataset.rawText;
                }
                
                this.scrollToBottom();
                break;
            
            case 'message_complete':
                // Message finished - clean up
                this.logger.debug('[ThinkGuide] Message complete');
                if (contentDiv.dataset.rawText) {
                    delete contentDiv.dataset.rawText;
                }
                break;
            
            case 'state_transition':
                // Update state and progress
                if (new_state) {
                    this.currentState = new_state;
                    this.logger.info(`[ThinkGuide] State: ${new_state}`);
                }
                if (progress !== undefined) {
                    this.updateProgress(progress, this.getStateLabel(new_state));
                }
                break;
            
            case 'diagram_update':
                // Backend wants to modify the diagram
                this.logger.info('[ThinkGuide] 🔄 Received diagram update:', data);
                this.applyDiagramUpdate(data);
                break;
            
            case 'complete':
                // Workflow complete
                const lang = this.labels[this.language] || this.labels.en;
                this.updateProgress(100, lang.complete);
                const completeMsg = this.language === 'zh' ? '思维训练完成！' : 'Thinking session complete!';
                this.addSystemMessage(completeMsg);
                break;
            
            case 'error':
                // Error occurred
                this.logger.error('[ThinkGuide] Server error:', message);
                this.addSystemMessage('Error: ' + message);
                break;
        }
    }
    
    /**
     * Extract current diagram data
     */
    extractDiagramData() {
        // Get from current editor instance
        const editor = window.currentEditor;
        if (!editor || !editor.currentSpec) {
            this.logger.info('[ThinkGuide] No diagram data - starting from scratch');
            // Return empty structure - ThinkGuide can help build from ground up!
            return { 
                center: { text: '' }, 
                children: [],
                isEmpty: true  // Flag to indicate empty diagram
            };
        }
        
        return this.normalizeDiagramData(editor.currentSpec, editor.diagramType);
    }
    
    /**
     * Normalize diagram spec to ThinkGuide format
     * Converts diagram-specific structure to {center: {text: ...}, children: [...]}
     */
    normalizeDiagramData(spec, diagramType) {
        this.logger.debug('[ThinkGuide] Normalizing diagram data:', { diagramType, spec });
        
        switch (diagramType) {
            case 'circle_map':
                return {
                    center: { text: spec.topic || spec.center?.text || '' },
                    children: (spec.items || spec.children || []).map((item, index) => ({
                        id: item.id || String(index + 1),
                        text: item.text || item.content || item
                    }))
                };
            
            case 'bubble_map':
                return {
                    center: { text: spec.topic || spec.center?.text || '' },
                    children: (spec.adjectives || spec.items || spec.children || []).map((item, index) => ({
                        id: item.id || String(index + 1),
                        text: item.text || item.content || item
                    }))
                };
            
            case 'tree_map':
                // Tree map has categories with items
                const treeChildren = [];
                if (spec.categories) {
                    spec.categories.forEach((category, catIndex) => {
                        if (category.items) {
                            category.items.forEach((item, itemIndex) => {
                                treeChildren.push({
                                    id: `${catIndex}-${itemIndex}`,
                                    text: item.text || item.content || item,
                                    category: category.name
                                });
                            });
                        }
                    });
                }
                return {
                    center: { text: spec.topic || spec.title || '' },
                    children: treeChildren
                };
            
            default:
                // Generic fallback - allow empty text for building from scratch
                return {
                    center: { text: spec.topic || spec.title || spec.center?.text || '' },
                    children: (spec.items || spec.children || spec.nodes || []).map((item, index) => ({
                        id: item.id || String(index + 1),
                        text: item.text || item.content || item.label || String(item)
                    }))
                };
        }
    }
    
    /**
     * Create assistant message div
     */
    createAssistantMessageDiv() {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'thinking-message assistant';
        
        // Create content wrapper (like MindMate structure)
        const contentDiv = document.createElement('div');
        contentDiv.className = 'thinking-message-content';
        contentDiv.textContent = ''; // Initialize empty for accumulation
        
        messageDiv.appendChild(contentDiv);
        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
        
        return contentDiv; // Return content div for direct text manipulation
    }
    
    /**
     * Add user message to chat
     */
    addUserMessage(text) {
        const div = document.createElement('div');
        div.className = 'thinking-message user';
        // Render user message as plain text (no markdown)
        div.textContent = text;
        this.messagesContainer.appendChild(div);
        this.scrollToBottom();
    }
    
    /**
     * Add system message (info/error)
     */
    addSystemMessage(text) {
        const div = document.createElement('div');
        div.className = 'thinking-message assistant';
        div.style.fontStyle = 'italic';
        div.style.opacity = '0.8';
        div.textContent = text;
        this.messagesContainer.appendChild(div);
        this.scrollToBottom();
    }
    
    /**
     * Show typing indicator (three dots animation)
     */
    showTypingIndicator() {
        const indicator = document.createElement('div');
        indicator.className = 'thinking-typing-indicator';
        indicator.innerHTML = `
            <div class="thinking-typing-dots">
                <span></span><span></span><span></span>
            </div>
        `;
        this.messagesContainer.appendChild(indicator);
        this.scrollToBottom();
        return indicator;
    }
    
    /**
     * Update progress bar
     */
    updateProgress(percent, label) {
        if (this.progressFill) {
            this.progressFill.style.width = `${percent}%`;
        }
        if (this.progressLabel) {
            this.progressLabel.textContent = label || `${percent}%`;
        }
    }
    
    /**
     * Get human-readable label for state (language-aware)
     */
    getStateLabel(state) {
        const lang = this.labels[this.language] || this.labels.en;
        const labelMap = {
            'CONTEXT_GATHERING': lang.contextGathering,
            'EDUCATIONAL_ANALYSIS': lang.educationalAnalysis,
            'ANALYSIS': lang.analysis,
            'REFINEMENT_1': lang.refinement1,
            'REFINEMENT_2': lang.refinement2,
            'FINAL_REFINEMENT': lang.finalRefinement,
            'COMPLETE': lang.complete
        };
        return labelMap[state] || state;
    }
    
    /**
     * Detect language from diagram data
     */
    detectLanguage(diagramData) {
        // For empty diagrams, check browser language or default to 'en'
        if (diagramData?.isEmpty || !diagramData?.center?.text) {
            const browserLang = navigator.language || navigator.userLanguage || 'en';
            this.language = browserLang.startsWith('zh') ? 'zh' : 'en';
            this.logger.debug(`[ThinkGuide] Empty diagram - using browser language: ${this.language}`);
            return this.language;
        }
        
        const centerText = diagramData.center.text || '';
        const chineseChars = (centerText.match(/[\u4e00-\u9fff]/g) || []).length;
        this.language = chineseChars > centerText.length * 0.3 ? 'zh' : 'en';
        this.logger.debug(`[ThinkGuide] Detected language from diagram: ${this.language}`);
        return this.language;
    }
    
    /**
     * Scroll messages to bottom
     */
    scrollToBottom() {
        if (this.messagesContainer) {
            this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
        }
    }
    
    /**
     * Handle send button click
     */
    handleSendMessage() {
        const message = this.inputArea.value.trim();
        if (!message || this.isStreaming) return;
        
        this.sendMessage(message);
    }
    
    /**
     * Open thinking panel
     */
    openPanel() {
        this.logger.info('[ThinkGuide] 🔵 openPanel() called - STARTING PANEL OPEN');
        
        if (!this.panel) {
            this.logger.error('[ThinkGuide] ❌ Panel element not found!');
            return;
        }
        
        // Log current state of BOTH panels before opening
        const thinkPanel = document.getElementById('thinking-panel');
        const aiPanel = document.getElementById('ai-assistant-panel');
        
        this.logger.info('[ThinkGuide] Panel state BEFORE open:', {
            thinkPanelId: thinkPanel?.id || 'NOT_FOUND',
            thinkPanelCollapsed: thinkPanel?.classList.contains('collapsed'),
            aiPanelId: aiPanel?.id || 'NOT_FOUND',
            aiPanelCollapsed: aiPanel?.classList.contains('collapsed'),
            currentPanelManager: window.panelManager?.getCurrentPanel()
        });
        
        // Use centralized panel manager with EXPLICIT method
        if (window.panelManager) {
            this.logger.info('[ThinkGuide] 🎯 Calling panelManager.openThinkGuidePanel() - EXPLICIT METHOD');
            const success = window.panelManager.openThinkGuidePanel();
            this.logger.info('[ThinkGuide] openThinkGuidePanel result:', success);
        } else {
            // Fallback if panel manager not available
            this.logger.warn('[ThinkGuide] ⚠️ PanelManager not available, using fallback');
            this.panel.classList.remove('collapsed');
        }
        
        // Brief delay to let DOM update
        setTimeout(() => {
            // Log state AFTER opening
            this.logger.info('[ThinkGuide] Panel state AFTER open:', {
                thinkPanelId: thinkPanel?.id || 'NOT_FOUND',
                thinkPanelCollapsed: thinkPanel?.classList.contains('collapsed'),
                thinkPanelClasses: thinkPanel?.className || 'N/A',
                aiPanelId: aiPanel?.id || 'NOT_FOUND',
                aiPanelCollapsed: aiPanel?.classList.contains('collapsed'),
                aiPanelClasses: aiPanel?.className || 'N/A',
                currentPanelManager: window.panelManager?.getCurrentPanel()
            });
            
            this.inputArea?.focus();
            this.logger.info('[ThinkGuide] ✅ Panel open sequence completed');
        }, 100);
    }
    
    /**
     * Apply diagram updates from ThinkGuide
     * Syncs backend suggestions with the visual diagram
     */
    applyDiagramUpdate(data) {
        const { action, updates } = data;
        
        this.logger.info('[ThinkGuide] Applying diagram update:', { action, updates });
        
        // Get the current editor instance
        const editor = window.currentEditor;
        if (!editor) {
            this.logger.error('[ThinkGuide] No editor instance found, cannot update diagram');
            return;
        }
        
        try {
            switch (action) {
                case 'update_nodes':
                    // Update existing nodes
                    updates.forEach(update => {
                        this.updateDiagramNode(update.node_id, update.new_text);
                    });
                    break;
                
                case 'add_nodes':
                    // Add new nodes
                    updates.forEach(nodeData => {
                        this.addDiagramNode(nodeData.text, nodeData.position);
                    });
                    break;
                
                case 'remove_nodes':
                    // Remove nodes
                    updates.forEach(nodeId => {
                        this.removeDiagramNode(nodeId);
                    });
                    break;
                
                case 'update_center':
                    // Update center/main topic
                    this.updateCenterTopic(updates.new_text);
                    break;
                
                case 'update_properties':
                    // Update node visual properties (color, bold, italic, etc.)
                    updates.forEach(update => {
                        this.updateNodeProperties(update.node_id, update.properties);
                    });
                    break;
                
                case 'update_position':
                    // Update node position (angle, rotation)
                    updates.forEach(update => {
                        this.updateNodePosition(update.node_id, update.node_index, update.position);
                    });
                    break;
                
                case 'swap_positions':
                    // Swap positions of two nodes
                    this.swapNodePositions(updates.node1_id, updates.node2_id);
                    break;
                
                case 'replace_all':
                    // Replace entire diagram structure
                    this.replaceDiagram(updates);
                    break;
                
                default:
                    this.logger.warn('[ThinkGuide] Unknown diagram update action:', action);
            }
            
            // Show feedback to user
            const msg = this.language === 'zh' ? '✅ 图表已更新' : '✅ Diagram updated';
            this.addSystemMessage(msg);
            
        } catch (error) {
            this.logger.error('[ThinkGuide] Error applying diagram update:', error);
            const errorMsg = this.language === 'zh' ? 
                '❌ 更新图表失败' : '❌ Failed to update diagram';
            this.addSystemMessage(errorMsg);
        }
    }
    
    /**
     * Update a specific node's text in the diagram
     */
    updateDiagramNode(nodeId, newText) {
        this.logger.info('[ThinkGuide] Updating node:', { nodeId, newText });
        
        // Find the text element in SVG
        const textElement = d3.select(`text[data-node-id="${nodeId}"]`);
        
        if (!textElement.empty()) {
            textElement.text(newText);
            
            // Update the underlying data model if editor has updateNode method
            const editor = window.currentEditor;
            if (editor && typeof editor.updateNodeText === 'function') {
                editor.updateNodeText(nodeId, newText);
            }
            
            this.logger.info('[ThinkGuide] ✅ Node updated successfully');
        } else {
            this.logger.warn('[ThinkGuide] Node not found:', nodeId);
        }
    }
    
    /**
     * Add a new node to the diagram
     */
    addDiagramNode(text, position) {
        this.logger.info('[ThinkGuide] Adding node:', { text, position });
        
        const editor = window.currentEditor;
        if (editor && typeof editor.addNode === 'function') {
            editor.addNode({ text, position });
            this.logger.info('[ThinkGuide] ✅ Node added successfully');
        } else {
            this.logger.warn('[ThinkGuide] Editor does not support addNode');
        }
    }
    
    /**
     * Remove a node from the diagram
     */
    removeDiagramNode(nodeId) {
        this.logger.info('[ThinkGuide] Removing node:', nodeId);
        
        const editor = window.currentEditor;
        if (editor && typeof editor.removeNode === 'function') {
            editor.removeNode(nodeId);
            this.logger.info('[ThinkGuide] ✅ Node removed successfully');
        } else {
            this.logger.warn('[ThinkGuide] Editor does not support removeNode');
        }
    }
    
    /**
     * Update center/main topic
     */
    updateCenterTopic(newText) {
        this.logger.info('[ThinkGuide] Updating center topic:', newText);
        
        // Find center text element
        const centerText = d3.select('text[data-node-type="center"]');
        
        if (!centerText.empty()) {
            centerText.text(newText);
            
            // Update data model
            const editor = window.currentEditor;
            if (editor && editor.currentSpec) {
                if (editor.currentSpec.topic !== undefined) {
                    editor.currentSpec.topic = newText;
                } else if (editor.currentSpec.center) {
                    editor.currentSpec.center.text = newText;
                }
            }
            
            this.logger.info('[ThinkGuide] ✅ Center topic updated');
        } else {
            this.logger.warn('[ThinkGuide] Center topic element not found');
        }
    }
    
    /**
     * Update node visual properties (color, bold, italic, etc.)
     */
    updateNodeProperties(nodeId, properties) {
        this.logger.info('[ThinkGuide] Updating node properties:', { nodeId, properties });
        
        // Find the shape element (circle, rect, etc.)
        const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
        
        // Find the text element
        let textElement = d3.select(`text[data-node-id="${nodeId}"]`);
        if (textElement.empty()) {
            textElement = d3.select(`text[data-text-for="${nodeId}"]`);
        }
        
        if (!shapeElement.empty()) {
            // Apply shape properties
            if (properties.fillColor) {
                shapeElement.attr('fill', properties.fillColor);
            }
            if (properties.strokeColor) {
                shapeElement.attr('stroke', properties.strokeColor);
            }
            if (properties.strokeWidth) {
                shapeElement.attr('stroke-width', properties.strokeWidth);
            }
            if (properties.opacity !== undefined) {
                shapeElement.attr('opacity', properties.opacity);
            }
        }
        
        if (!textElement.empty()) {
            // Apply text properties
            if (properties.textColor) {
                textElement.attr('fill', properties.textColor);
            }
            if (properties.fontSize) {
                textElement.attr('font-size', properties.fontSize);
            }
            if (properties.fontFamily) {
                textElement.attr('font-family', properties.fontFamily);
            }
            if (properties.bold !== undefined) {
                textElement.attr('font-weight', properties.bold ? 'bold' : 'normal');
            }
            if (properties.italic !== undefined) {
                textElement.attr('font-style', properties.italic ? 'italic' : 'normal');
            }
            if (properties.underline !== undefined) {
                textElement.attr('text-decoration', properties.underline ? 'underline' : 'none');
            }
        }
        
        // Update the data model if editor has updateNodeProperties method
        const editor = window.currentEditor;
        if (editor && typeof editor.updateNodeProperties === 'function') {
            editor.updateNodeProperties(nodeId, properties);
        }
        
        this.logger.info('[ThinkGuide] ✅ Properties updated successfully');
    }
    
    /**
     * Update node position (angle-based for Circle Maps)
     */
    updateNodePosition(nodeId, nodeIndex, position) {
        this.logger.info('[ThinkGuide] Updating node position:', { nodeId, nodeIndex, position });
        
        const editor = window.currentEditor;
        if (!editor || !editor.currentSpec) {
            this.logger.warn('[ThinkGuide] No editor or spec found');
            return;
        }
        
        // For Circle Maps, we need to recalculate the position based on angle
        const spec = editor.currentSpec;
        
        // Find SVG dimensions
        const svg = d3.select('#d3-container svg');
        const width = parseInt(svg.attr('width')) || 800;
        const height = parseInt(svg.attr('height')) || 600;
        const centerX = width / 2;
        const centerY = height / 2;
        
        // Calculate distance from center (typical for circle maps)
        const radius = 150; // Standard distance for circle map nodes
        
        let newAngle;
        
        if (position.angle !== undefined) {
            // Absolute angle
            newAngle = position.angle;
        } else if (position.rotate !== undefined) {
            // Relative rotation - need to find current angle
            const children = spec.children || spec.attributes || [];
            const totalNodes = children.length;
            const currentAngle = (nodeIndex * 360 / totalNodes) - 90; // Current position
            newAngle = currentAngle + position.rotate;
        } else {
            this.logger.warn('[ThinkGuide] No angle or rotate specified');
            return;
        }
        
        // Normalize angle to 0-360
        newAngle = ((newAngle % 360) + 360) % 360;
        
        // Convert to radians and calculate new position
        const angleRad = (newAngle - 90) * Math.PI / 180; // -90 to start from top
        const newX = centerX + radius * Math.cos(angleRad);
        const newY = centerY + radius * Math.sin(angleRad);
        
        // Find and move the node elements
        const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
        const textElement = d3.select(`text[data-node-id="${nodeId}"]`).empty() ? 
            d3.select(`text[data-text-for="${nodeId}"]`) : 
            d3.select(`text[data-node-id="${nodeId}"]`);
        
        if (!shapeElement.empty()) {
            shapeElement
                .transition()
                .duration(500)
                .attr('cx', newX)
                .attr('cy', newY);
        }
        
        if (!textElement.empty()) {
            textElement
                .transition()
                .duration(500)
                .attr('x', newX)
                .attr('y', newY);
        }
        
        this.logger.info('[ThinkGuide] ✅ Position updated successfully');
    }
    
    /**
     * Swap positions of two nodes
     */
    swapNodePositions(nodeId1, nodeId2) {
        this.logger.info('[ThinkGuide] Swapping positions:', { nodeId1, nodeId2 });
        
        // Find both nodes
        const shape1 = d3.select(`[data-node-id="${nodeId1}"]`);
        const shape2 = d3.select(`[data-node-id="${nodeId2}"]`);
        const text1 = d3.select(`text[data-node-id="${nodeId1}"]`).empty() ? 
            d3.select(`text[data-text-for="${nodeId1}"]`) : 
            d3.select(`text[data-node-id="${nodeId1}"]`);
        const text2 = d3.select(`text[data-node-id="${nodeId2}"]`).empty() ? 
            d3.select(`text[data-text-for="${nodeId2}"]`) : 
            d3.select(`text[data-node-id="${nodeId2}"]`);
        
        if (shape1.empty() || shape2.empty()) {
            this.logger.warn('[ThinkGuide] One or both nodes not found');
            return;
        }
        
        // Get current positions
        const x1 = parseFloat(shape1.attr('cx'));
        const y1 = parseFloat(shape1.attr('cy'));
        const x2 = parseFloat(shape2.attr('cx'));
        const y2 = parseFloat(shape2.attr('cy'));
        
        // Swap with animation
        shape1.transition().duration(500).attr('cx', x2).attr('cy', y2);
        shape2.transition().duration(500).attr('cx', x1).attr('cy', y1);
        
        if (!text1.empty()) {
            text1.transition().duration(500).attr('x', x2).attr('y', y2);
        }
        if (!text2.empty()) {
            text2.transition().duration(500).attr('x', x1).attr('y', y1);
        }
        
        this.logger.info('[ThinkGuide] ✅ Positions swapped successfully');
    }
    
    /**
     * Replace entire diagram with new structure
     */
    replaceDiagram(newDiagramData) {
        this.logger.info('[ThinkGuide] Replacing entire diagram');
        
        const editor = window.currentEditor;
        if (editor && typeof editor.loadDiagram === 'function') {
            editor.loadDiagram(newDiagramData);
            this.logger.info('[ThinkGuide] ✅ Diagram replaced successfully');
        } else {
            this.logger.warn('[ThinkGuide] Editor does not support loadDiagram');
        }
    }
    
    /**
     * Close thinking panel
     */
    closePanel() {
        if (this.panel) {
            if (window.panelManager) {
                this.logger.info('[ThinkGuide] 🎯 Calling panelManager.closeThinkGuidePanel() - EXPLICIT METHOD');
                window.panelManager.closeThinkGuidePanel();
            } else {
                // Fallback
                this.logger.warn('[ThinkGuide] ⚠️ PanelManager not available, using fallback');
                this.panel.classList.add('collapsed');
            }
            this.logger.info('[ThinkGuide] Panel closed');
        }
    }
    
    /**
     * Check if panel is open
     */
    isPanelOpen() {
        return this.panel && !this.panel.classList.contains('collapsed');
    }
}

// Create global instance with error handling
try {
    window.thinkingModeManager = new ThinkingModeManager();
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            try {
                window.thinkingModeManager.init();
                console.log('[ThinkGuide] Initialized successfully');
            } catch (error) {
                console.error('[ThinkGuide] Initialization error:', error);
            }
        });
    } else {
        try {
            window.thinkingModeManager.init();
            console.log('[ThinkGuide] Initialized successfully');
        } catch (error) {
            console.error('[ThinkGuide] Initialization error:', error);
        }
    }
} catch (error) {
    console.error('[ThinkGuide] Failed to create ThinkingModeManager:', error);
    window.thinkingModeManager = null;
}

// Panel control is now handled by centralized PanelManager (panel-manager.js)

