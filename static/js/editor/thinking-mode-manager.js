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
        this.stopBtn = null;
        this.progressFill = null;
        this.progressLabel = null;
        this.closeBtn = null;
        this.nodePaletteBtn = null;
        
        // State management
        this.sessionId = null;
        this.diagramSessionId = null; // Track which diagram session this conversation belongs to
        this.currentState = 'CONTEXT_GATHERING';
        this.isStreaming = false;
        this.currentAbortController = null; // For stopping SSE streams
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
                complete: 'Complete!',
                nodePalette: 'Node Palette',
                nodePaletteTooltip: 'Open Node Palette to brainstorm nodes with AI'
            },
            zh: {
                starting: '启动中...',
                contextGathering: '收集背景信息...',
                educationalAnalysis: '分析节点...',
                analysis: '苏格拉底式分析...',
                refinement1: '第一次优化...',
                refinement2: '第二次优化...',
                finalRefinement: '最后优化...',
                complete: '完成！',
                nodePalette: '瀑布流',
                nodePaletteTooltip: '打开瀑布流，AI为您头脑风暴更多节点'
            }
        };
        
        // Logger reference
        this.logger = window.logger || console;
        
        // Listen for language changes
        window.addEventListener('languageChanged', (event) => {
            this.language = event.detail.language;
            this.updateNodePaletteButtonText();
            this.logger.debug('[ThinkGuide]', `Language changed to: ${this.language}`);
        });
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
        this.stopBtn = document.getElementById('thinking-stop-btn');
        this.progressFill = document.getElementById('thinking-progress-fill');
        this.progressLabel = document.getElementById('thinking-progress-label');
        this.closeBtn = document.getElementById('thinking-close-btn');
        this.nodePaletteBtn = document.getElementById('thinking-node-palette-btn');
        
        if (!this.panel) {
            this.logger.warn('[ThinkGuide]', 'Panel not found');
            return;
        }
        
        // Event listeners
        this.sendBtn.addEventListener('click', () => this.handleSendMessage());
        this.stopBtn.addEventListener('click', () => {
            this.logger.info('[ThinkGuide]', '🛑 STOP BUTTON CLICKED');
            this.stopStreaming();
        });
        this.inputArea.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.handleSendMessage();
            }
        });
        this.closeBtn.addEventListener('click', () => this.closePanel());
        
        // Node Palette Button - directly trigger without keyword detection
        if (this.nodePaletteBtn) {
            this.nodePaletteBtn.addEventListener('click', () => this.openNodePalette());
            this.logger.info('[ThinkGuide]', 'Node Palette button listener attached');
        } else {
            this.logger.warn('[ThinkGuide]', 'Node Palette button not found');
        }
        
        this.logger.info('[ThinkGuide]', 'Initialized successfully');
    }
    
    /**
     * Start thinking mode for current diagram
     */
    async startThinkingMode(diagramType, diagramData) {
        this.logger.info('[ThinkGuide]', `Starting for diagram: ${diagramType}`);
        
        // Detect language from diagram
        this.detectLanguage(diagramData);
        
        // Get current diagram session ID
        const currentDiagramSessionId = window.currentEditor?.sessionId;
        
        // Check if this is a new diagram session or same session being reopened
        const isNewDiagramSession = !this.diagramSessionId || this.diagramSessionId !== currentDiagramSessionId;
        
        let needsGreeting = false;
        
        if (isNewDiagramSession) {
            this.logger.info('[ThinkGuide] New diagram session detected - creating new conversation', {
                oldSession: this.diagramSessionId,
                newSession: currentDiagramSessionId
            });
            
            // Reset state for new diagram
            this.diagramType = diagramType;
            this.diagramSessionId = currentDiagramSessionId;
            this.sessionId = `thinking_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
            this.currentState = 'CONTEXT_GATHERING';
            this.isStreaming = false;
            
            // Clear UI
            this.messagesContainer.innerHTML = '';
            this.inputArea.value = '';
            const lang = this.labels[this.language] || this.labels.en;
            this.updateProgress(0, lang.starting);
            
            // New session needs initial greeting
            needsGreeting = true;
        } else {
            this.logger.info('[ThinkGuide] Resuming existing conversation session', {
                diagramSession: this.diagramSessionId,
                thinkingSession: this.sessionId
            });
            // Keep existing session - just reopen panel, no greeting needed
            needsGreeting = false;
        }
        
        // Open panel
        this.openPanel();
        
        // Only send greeting for new sessions
        if (needsGreeting) {
            // Fire greeting and preload in parallel (don't await greeting)
            this.sendMessage('', diagramData, true); // true = request initial greeting (no await!)
            
            // PRELOAD Node Palette data in background IMMEDIATELY (saves 2-5 seconds when user clicks!)
            this.preloadNodePalette(diagramData);
        }
    }
    
    /**
     * Send message to backend
     * @param {string} message - User message
     * @param {object} diagramData - Current diagram data
     * @param {boolean} isInitialGreeting - If true, request initial greeting for new session
     */
    async sendMessage(message, diagramData, isInitialGreeting = false) {
        if (this.isStreaming) {
            this.logger.warn('[ThinkGuide]', 'Already streaming, ignoring request');
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
                selected_node: null, // TODO: Get from selection manager
                is_initial_greeting: isInitialGreeting,  // Explicit flag for greeting
                language: this.language  // Add detected language (zh/en)
            };
            
            // Extract center topic based on diagram type for logging
            let centerTopic;
            if (['tree_map', 'mindmap'].includes(this.diagramType)) {
                centerTopic = currentDiagramData.topic || 'empty';
            } else if (this.diagramType === 'flow_map') {
                centerTopic = currentDiagramData.title || 'empty';
            } else if (this.diagramType === 'brace_map') {
                centerTopic = currentDiagramData.whole || 'empty';
            } else if (this.diagramType === 'double_bubble_map') {
                centerTopic = `${currentDiagramData.left || ''} vs ${currentDiagramData.right || ''}`;
            } else if (this.diagramType === 'multi_flow_map') {
                centerTopic = currentDiagramData.event || 'empty';
            } else if (this.diagramType === 'bridge_map') {
                centerTopic = currentDiagramData.dimension || 'empty';
            } else {
                centerTopic = currentDiagramData.center?.text || 'empty';
            }
            
            this.logger.info('[ThinkGuide] 📊 Sending with current diagram:', {
                message: message.substring(0, 50) + '...',
                center: centerTopic,
                nodeCount: currentDiagramData.children?.length || 0,
                diagramType: this.diagramType,
                language: this.language  // Log detected language
            });
            
            // Stream response
            await this.streamResponse(requestData);
            
        } catch (error) {
            this.logger.error('[ThinkGuide]', 'Error sending message:', error);
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
        
        // Create NEW AbortController for this stream (must be fresh each time)
        if (this.currentAbortController) {
            this.logger.warn('[ThinkGuide]', 'Cleaning up old AbortController');
        }
        this.currentAbortController = new AbortController();
        this.logger.info('[ThinkGuide]', 'Created new AbortController');
        
        // Show stop button, hide send button
        this.showStopButton();
        this.logger.info('[ThinkGuide]', 'Stop button shown');
        
        try {
            this.logger.info('[ThinkGuide]', 'Starting fetch with AbortController signal');
            const response = await auth.fetch('/thinking_mode/stream', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData),
                signal: this.currentAbortController.signal
            });
            
            this.logger.info('[ThinkGuide]', 'Fetch response received, status:', response.status);
            
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
            
            // Stream complete - hide stop button
            this.hideStopButton();
            
        } catch (error) {
            // Remove typing indicator on error
            if (typingIndicator && typingIndicator.parentNode) {
                typingIndicator.parentNode.removeChild(typingIndicator);
            }
            
            // Hide stop button
            this.hideStopButton();
            
            // Don't throw if it was intentionally aborted
            if (error.name === 'AbortError') {
                const stopMsg = this.language === 'zh' ? '⏹ 已停止生成' : '⏹ Generation stopped';
                this.addSystemMessage(stopMsg);
                this.logger.info('[ThinkGuide]', 'Stream stopped by user');
                return; // Don't re-throw
            }
            
            throw error;
        } finally {
            this.logger.info('[ThinkGuide]', 'streamResponse finally block - cleaning up AbortController');
            this.currentAbortController = null;
            this.logger.info('[ThinkGuide]', 'AbortController set to null');
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
                    const sanitized = DOMPurify.sanitize(html, {
                        ALLOWED_TAGS: ['p', 'strong', 'em', 'code', 'pre', 'ul', 'ol', 'li', 'br', 'a', 'blockquote', 'span'],
                        ALLOWED_ATTR: ['href', 'target', 'class']
                    });
                    // Convert 【】markers to purple bold highlights
                    const highlighted = this.applyThinkGuideHighlights(sanitized);
                    contentDiv.innerHTML = highlighted;
                } else {
                    contentDiv.textContent = contentDiv.dataset.rawText;
                }
                
                this.scrollToBottom();
                break;
            
            case 'message_complete':
                // Message finished - clean up
                // Check if this is a silent resume (panel reopened, no new message)
                if (data.silent_resume) {
                    this.logger.info('[ThinkGuide]', 'Silent resume - conversation continued without greeting');
                    // No UI updates needed, conversation history is preserved
                    break;
                }
                
                this.logger.debug('[ThinkGuide]', 'Message complete');
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
                this.logger.info('[ThinkGuide]', '🔄 Received diagram update:', data);
                this.applyDiagramUpdate(data);
                break;
            
            case 'action':
                // Backend wants to trigger an action (e.g., open Node Palette)
                this.logger.info('[ThinkGuide]', 'Action triggered:', data.action);
                this.handleAction(data);
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
                this.logger.error('[ThinkGuide]', 'Server error:', message);
                this.addSystemMessage('Error: ' + message);
                break;
        }
    }
    
    /**
     * Handle action events from backend
     */
    handleAction(data) {
        const { action, data: actionData } = data;
        
        switch (action) {
            case 'open_node_palette':
                // Open Node Palette for brainstorming more nodes
                this.logger.info('[ThinkGuide]', 'Opening Node Palette | Topic:', actionData.center_topic);
                this.logger.debug('[ThinkGuide]', 'Educational context:', actionData.educational_context);
                
                if (window.nodePaletteManager) {
                    // For tree maps, set stage information before opening
                    if (this.diagramType === 'tree_map' && actionData.stage) {
                        window.nodePaletteManager.currentStage = actionData.stage;
                        window.nodePaletteManager.stageData = actionData.stage_data || {};
                        this.logger.info('[ThinkGuide-TreeMap]', `Stage: ${actionData.stage} | Data:`, actionData.stage_data);
                    }
                    
                    window.nodePaletteManager.start(
                        actionData.center_topic,
                        actionData.diagram_data,
                        actionData.session_id,
                        actionData.educational_context,  // Pass ThinkGuide context for focused generation
                        this.diagramType  // Pass diagram type for proper terminology
                    );
                } else {
                    this.logger.error('[ThinkGuide]', 'NodePaletteManager not found');
                }
                break;
            
            default:
                this.logger.warn('[ThinkGuide]', 'Unknown action:', action);
        }
    }
    
    /**
     * Extract current diagram data
     */
    extractDiagramData() {
        // Get from current editor instance
        const editor = window.currentEditor;
        if (!editor || !editor.currentSpec) {
            this.logger.info('[ThinkGuide]', 'No diagram data - starting from scratch');
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
        this.logger.debug('[ThinkGuide]', 'Normalizing diagram data:', { diagramType, spec });
        
        switch (diagramType) {
            case 'circle_map':
                return {
                    center: { text: spec.topic || spec.center?.text || '' },
                    children: (spec.context || spec.items || spec.children || []).map((item, index) => ({
                        id: item.id || `context_${index}`,  // Match renderer's ID format
                        text: item.text || item.content || item
                    }))
                };
            
            case 'bubble_map':
                return {
                    center: { text: spec.topic || spec.center?.text || '' },
                    children: (spec.attributes || spec.adjectives || spec.items || spec.children || []).map((item, index) => ({
                        id: item.id || String(index + 1),
                        text: item.text || item.content || item
                    }))
                };
            
            case 'double_bubble_map':
                return {
                    left: spec.left || '',
                    right: spec.right || '',
                    similarities: spec.similarities || [],
                    left_differences: spec.left_differences || [],
                    right_differences: spec.right_differences || []
                };
            
            case 'tree_map':
                return {
                    topic: spec.topic || '',
                    children: spec.children || []
                };
            
            case 'flow_map':
                return {
                    title: spec.title || '',
                    steps: spec.steps || []
                };
            
            case 'multi_flow_map':
                return {
                    event: spec.event || '',
                    causes: spec.causes || [],
                    effects: spec.effects || []
                };
            
            case 'brace_map':
                return {
                    whole: spec.whole || '',
                    parts: spec.parts || []
                };
            
            case 'bridge_map':
                return {
                    dimension: spec.dimension || '',
                    analogies: spec.analogies || []
                };
            
            case 'mindmap':
                return {
                    topic: spec.topic || '',
                    children: spec.children || []
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
     * Extract educational context for Node Palette.
     * Builds context from current ThinkGuide session state.
     * 
     * @returns {Object} Educational context object
     */
    extractEducationalContext() {
        // Build educational context from current session
        const context = {
            session_id: this.sessionId,
            diagram_type: this.diagramType,
            language: this.language,
            // Add any user messages from the conversation as context
            raw_message: 'K12 teaching context from ThinkGuide session'
        };
        
        // If there's conversation history, include the last user message
        if (this.messagesContainer) {
            const userMessages = this.messagesContainer.querySelectorAll('.thinking-user-message');
            if (userMessages.length > 0) {
                const lastMessage = userMessages[userMessages.length - 1];
                const messageText = lastMessage.textContent || lastMessage.innerText;
                if (messageText && messageText.trim()) {
                    context.raw_message = messageText.trim();
                }
            }
        }
        
        this.logger.debug('[ThinkGuide]', 'Extracted educational context:', context);
        return context;
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
        // Collect text for language detection based on diagram type
        let textToAnalyze = '';
        
        if (this.diagramType === 'double_bubble_map') {
            // Double bubble map has left and right topics
            const leftTopic = diagramData?.left_topic || diagramData?.left || '';
            const rightTopic = diagramData?.right_topic || diagramData?.right || '';
            textToAnalyze = leftTopic + ' ' + rightTopic;
            this.logger.debug('[ThinkGuide]', `Double bubble map topics: left="${leftTopic}", right="${rightTopic}"`);
        } else if (this.diagramType === 'multi_flow_map') {
            // Multi flow map has event
            textToAnalyze = diagramData?.event || '';
            this.logger.debug('[ThinkGuide]', `Multi flow map event: "${textToAnalyze}"`);
        } else if (this.diagramType === 'flow_map') {
            // Flow map has title
            textToAnalyze = diagramData?.title || '';
            this.logger.debug('[ThinkGuide]', `Flow map title: "${textToAnalyze}"`);
        } else if (this.diagramType === 'brace_map') {
            // Brace map has whole
            textToAnalyze = diagramData?.whole || '';
            this.logger.debug('[ThinkGuide]', `Brace map whole: "${textToAnalyze}"`);
        } else if (this.diagramType === 'bridge_map') {
            // Bridge map has dimension
            textToAnalyze = diagramData?.dimension || '';
            this.logger.debug('[ThinkGuide]', `Bridge map dimension: "${textToAnalyze}"`);
        } else if (this.diagramType === 'tree_map' || this.diagramType === 'mindmap') {
            // Tree map and mindmap have topic
            textToAnalyze = diagramData?.topic || '';
            this.logger.debug('[ThinkGuide]', `${this.diagramType} topic: "${textToAnalyze}"`);
        } else {
            // Other diagrams have center.text or similar
            textToAnalyze = diagramData?.center?.text || diagramData?.topic || diagramData?.title || '';
            this.logger.debug('[ThinkGuide]', `Other diagram text: "${textToAnalyze}"`);
        }
        
        // For empty diagrams, use UI language toggle state
        if (diagramData?.isEmpty || !textToAnalyze || textToAnalyze.trim() === '') {
            // Use language from UI toggle (via LanguageManager)
            this.language = window.languageManager?.getCurrentLanguage() || 'en';
            this.logger.debug(`[ThinkGuide] Empty diagram - using UI language toggle: ${this.language}`);
            this.updateNodePaletteButtonText();
            return this.language;
        }
        
        // Detect Chinese characters in the text
        const chineseChars = (textToAnalyze.match(/[\u4e00-\u9fff]/g) || []).length;
        const totalChars = textToAnalyze.length;
        const chineseRatio = totalChars > 0 ? (chineseChars / totalChars) : 0;
        this.language = chineseRatio > 0.3 ? 'zh' : 'en';
        
        this.logger.info('[ThinkGuide]', `✓ Language detected: ${this.language} (${this.diagramType})`);
        this.logger.info('[ThinkGuide]', `  Chinese chars: ${chineseChars}/${totalChars} (${(chineseRatio * 100).toFixed(1)}%)`);
        this.logger.info('[ThinkGuide]', `  Text analyzed: "${textToAnalyze.substring(0, 50)}${textToAnalyze.length > 50 ? '...' : ''}"`);
        
        this.updateNodePaletteButtonText();
        return this.language;
    }
    
    /**
     * Update Node Palette button text based on current language
     */
    updateNodePaletteButtonText() {
        if (!this.nodePaletteBtn) return;
        
        const lang = this.labels[this.language] || this.labels.en;
        const textElement = document.getElementById('node-palette-btn-text');
        const tooltipElement = document.getElementById('node-palette-tooltip');
        
        if (textElement) {
            textElement.textContent = lang.nodePalette;
        }
        
        // Update tooltip text
        if (tooltipElement) {
            tooltipElement.textContent = lang.nodePaletteTooltip;
        }
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
     * Apply ThinkGuide purple bold highlights to 【】markers
     * Converts 【text】to <span class="thinkguide-highlight">text</span>
     */
    applyThinkGuideHighlights(html) {
        // Replace 【text】with styled spans
        return html.replace(/【([^】]+)】/g, '<span class="thinkguide-highlight">$1</span>');
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
     * Open Node Palette directly (button-triggered, not keyword detection)
     */
    /**
     * Preload Node Palette data in background (called when ThinkGuide opens)
     * This fires the catapult silently so data is ready when user clicks!
     */
    async preloadNodePalette(diagramData) {
        this.logger.info('[ThinkGuide]', 'Preloading Node Palette data in background...');
        
        // Use same validation logic as openNodePalette
        let centerTopic;
        
        if (this.diagramType === 'double_bubble_map') {
            const leftTopic = diagramData?.left;
            const rightTopic = diagramData?.right;
            if (!leftTopic || !rightTopic || leftTopic.trim() === '' || rightTopic.trim() === '') {
                this.logger.info('[ThinkGuide]', 'Skipping preload - missing topics');
                return;
            }
            centerTopic = `${leftTopic} vs ${rightTopic}`;
        } else if (this.diagramType === 'multi_flow_map') {
            centerTopic = diagramData?.event;
        } else if (this.diagramType === 'flow_map') {
            centerTopic = diagramData?.title;
        } else if (this.diagramType === 'brace_map') {
            centerTopic = diagramData?.whole;
        } else if (this.diagramType === 'bridge_map') {
            centerTopic = diagramData?.dimension;
        } else if (this.diagramType === 'tree_map' || this.diagramType === 'mindmap') {
            centerTopic = diagramData?.topic;
        } else {
            centerTopic = diagramData?.center?.text || diagramData?.topic || diagramData?.title;
        }
        
        if (!centerTopic || centerTopic.trim() === '') {
            this.logger.info('[ThinkGuide]', 'Skipping preload - no topic');
            return;
        }
        
        this.logger.info('[ThinkGuide]', `Preloading for topic: "${centerTopic}"`);
        
        // Trigger Node Palette Manager to preload (but don't show panel)
        if (window.nodePaletteManager) {
            await window.nodePaletteManager.preload(
                centerTopic,
                diagramData,
                this.sessionId,
                this.extractEducationalContext(),
                this.diagramType
            );
            this.logger.info('[ThinkGuide]', 'Preload complete! Data cached and ready.');
        }
    }
    
    openNodePalette() {
        this.logger.info('[ThinkGuide]', 'Node Palette button clicked');
        
        // Extract current diagram data
        const diagramData = this.extractDiagramData();
        
        // Validate diagram has required data and extract topic
        let centerTopic;
        
        if (this.diagramType === 'double_bubble_map') {
            // Double bubble map uses left and right topics
            const leftTopic = diagramData?.left;
            const rightTopic = diagramData?.right;
            
            if (!leftTopic || !rightTopic || leftTopic.trim() === '' || rightTopic.trim() === '') {
                const msg = this.language === 'zh' ? 
                    '请先为双气泡图添加左右两个主题。' : 
                    'Please add both left and right topics to your Double Bubble Map first.';
                this.addSystemMessage(msg);
                this.logger.warn('[ThinkGuide]', 'Cannot open Node Palette - missing topics');
                return;
            }
            centerTopic = `${leftTopic} vs ${rightTopic}`;
        } else if (this.diagramType === 'multi_flow_map') {
            centerTopic = diagramData?.event;
        } else if (this.diagramType === 'flow_map') {
            centerTopic = diagramData?.title;
        } else if (this.diagramType === 'brace_map') {
            centerTopic = diagramData?.whole;
        } else if (this.diagramType === 'bridge_map') {
            // Bridge Map: dimension field (can be empty for diverse relationships)
            centerTopic = diagramData?.dimension || '';
        } else if (this.diagramType === 'tree_map' || this.diagramType === 'mindmap') {
            centerTopic = diagramData?.topic;
        } else {
            // Most diagrams use center/topic field
            centerTopic = diagramData?.center?.text || diagramData?.topic || diagramData?.title;
        }
        
        // For bridge_map, empty dimension is OK (means diverse relationships mode)
        if (this.diagramType !== 'bridge_map') {
            if (!centerTopic || centerTopic.trim() === '') {
                const msg = this.language === 'zh' ? 
                    '请先为图表添加主题。' : 
                    'Please add a topic to your diagram first.';
                this.addSystemMessage(msg);
                this.logger.warn('[ThinkGuide]', 'Cannot open Node Palette - no topic');
                return;
            }
        }
        
        // Log with special message for bridge map
        if (this.diagramType === 'bridge_map') {
            if (centerTopic && centerTopic.trim()) {
                this.logger.info('[ThinkGuide] Opening Node Palette (Bridge Map - SPECIFIC):', {
                    dimension: centerTopic,
                    sessionId: this.sessionId
                });
            } else {
                this.logger.info('[ThinkGuide] Opening Node Palette (Bridge Map - DIVERSE mode):', {
                    dimension: '(empty - will generate multiple relationship types)',
                    sessionId: this.sessionId
                });
            }
        } else {
            this.logger.info('[ThinkGuide] Opening Node Palette:', {
                centerTopic,
                sessionId: this.sessionId,
                nodeCount: diagramData?.children?.length || 0
            });
        }
        
        // Debug: Log normalized diagram data being sent
        this.logger.debug('[ThinkGuide] Normalized diagram data being sent:', diagramData);
        this.logger.debug('[ThinkGuide] Diagram data keys:', Object.keys(diagramData));
        
        // Call Node Palette Manager
        if (window.nodePaletteManager) {
            window.nodePaletteManager.start(
                centerTopic,
                diagramData,
                this.sessionId,
                this.extractEducationalContext(),  // Pass context
                this.diagramType  // Pass diagram type for proper terminology
            );
            
            // Add confirmation message to chat
            const msg = this.language === 'zh' ? 
                '正在打开节点选择板，AI将为您头脑风暴更多想法...' : 
                'Opening Node Palette, AI will brainstorm more ideas for you...';
            this.addSystemMessage(msg);
        } else {
            this.logger.error('[ThinkGuide]', 'NodePaletteManager not found!');
            const msg = this.language === 'zh' ? 
                '错误：节点选择板未加载。' : 
                'Error: Node Palette not loaded.';
            this.addSystemMessage(msg);
        }
    }
    
    /**
     * Open thinking panel
     */
    openPanel() {
        this.logger.info('[ThinkGuide]', '🔵 openPanel() called - STARTING PANEL OPEN');
        
        if (!this.panel) {
            this.logger.error('[ThinkGuide]', '❌ Panel element not found!');
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
            this.logger.info('[ThinkGuide]', '🎯 Calling panelManager.openThinkGuidePanel() - EXPLICIT METHOD');
            const success = window.panelManager.openThinkGuidePanel();
            this.logger.info('[ThinkGuide]', 'openThinkGuidePanel result:', success);
        } else {
            // Fallback if panel manager not available
            this.logger.warn('[ThinkGuide]', '⚠️ PanelManager not available, using fallback');
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
            
            // Adjust diagram to make room for panel
            this.fitDiagramToCanvas();
            
            this.logger.info('[ThinkGuide]', '✅ Panel open sequence completed');
        }, 100);
    }
    
    /**
     * Apply diagram updates from ThinkGuide
     * Syncs backend suggestions with the visual diagram
     */
    applyDiagramUpdate(data) {
        const { action, updates } = data;
        
        this.logger.info('[ThinkGuide]', '🔄 applyDiagramUpdate called!');
        this.logger.info('[ThinkGuide]', 'Action:', action);
        this.logger.info('[ThinkGuide]', 'Updates:', updates);
        
        // Get the current editor instance
        const editor = window.currentEditor;
        if (!editor) {
            this.logger.error('[ThinkGuide]', '❌ No editor instance found, cannot update diagram');
            return;
        }
        
        this.logger.info('[ThinkGuide]', '✅ Editor instance found');
        
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
                    this.logger.warn('[ThinkGuide]', 'Unknown diagram update action:', action);
            }
            
            // Show feedback to user
            const msg = this.language === 'zh' ? '✅ 图表已更新' : '✅ Diagram updated';
            this.addSystemMessage(msg);
            
        } catch (error) {
            this.logger.error('[ThinkGuide]', 'Error applying diagram update:', error);
            const errorMsg = this.language === 'zh' ? 
                '❌ 更新图表失败' : '❌ Failed to update diagram';
            this.addSystemMessage(errorMsg);
        }
    }
    
    /**
     * Update a specific node's text in the diagram
     */
    updateDiagramNode(nodeId, newText) {
        this.logger.info('[ThinkGuide]', 'Updating node:', { nodeId, newText });
        
        const editor = window.currentEditor;
        if (editor && editor.currentSpec) {
            // Update in data model
            // Support different spec structures: circle_map uses 'context', bubble_map uses 'adjectives', etc.
            const children = editor.currentSpec.children || editor.currentSpec.items || editor.currentSpec.adjectives || editor.currentSpec.context || [];
            
            // For circle maps with simple string arrays, extract index from nodeId (e.g., "context_0" -> 0)
            if (Array.isArray(children) && children.length > 0 && typeof children[0] === 'string') {
                // Simple array format (e.g., circle map: ["item1", "item2", ...])
                const match = nodeId.match(/context_(\d+)/);
                if (match) {
                    const index = parseInt(match[1]);
                    if (index >= 0 && index < children.length) {
                        children[index] = newText;
                        this.logger.info('[ThinkGuide] ✅ Updated context array at index', index);
                    }
                }
            } else {
                // Object format with IDs
                for (let node of children) {
                    if (node.id === nodeId || String(node.id) === String(nodeId)) {
                        node.text = newText;
                        this.logger.info('[ThinkGuide]', '✅ Updated node object:', nodeId);
                        break;
                    }
                }
            }
            
            // Re-render diagram
            if (typeof editor.renderDiagram === 'function') {
                editor.renderDiagram();
            }
            
            // Highlight the updated node
            setTimeout(() => {
                this.logger.info('[ThinkGuide]', '🎯 Attempting to highlight node:', nodeId);
                this.logger.info('[ThinkGuide]', 'window.nodeIndicator exists?', !!window.nodeIndicator);
                
                if (window.nodeIndicator) {
                    this.logger.info('[ThinkGuide]', '✅ Calling nodeIndicator.highlight for node:', nodeId);
                    // Use 'pulse' instead of 'glow' - simpler, more visible, no SVG filters
                    const result = window.nodeIndicator.highlight(nodeId, {
                        type: 'pulse',
                        duration: 2000,
                        intensity: 6,
                        color: '#4CAF50'  // Green for updates
                    });
                    this.logger.info('[ThinkGuide]', 'Highlight result:', result);
                } else {
                    this.logger.error('[ThinkGuide] ❌ window.nodeIndicator not available!');
                }
            }, 100);
            
            this.logger.info('[ThinkGuide]', '✅ Node updated and highlighted');
        } else {
            this.logger.warn('[ThinkGuide] No editor or spec found');
        }
    }
    
    /**
     * Add a new node to the diagram
     */
    addDiagramNode(text, position) {
        this.logger.info('[ThinkGuide]', 'Adding node:', { text, position });
        
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
        this.logger.info('[ThinkGuide]', 'Removing node:', nodeId);
        
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
        this.logger.info('[ThinkGuide]', 'Updating center topic:', newText);
        
        // Update data model FIRST
        const editor = window.currentEditor;
        if (editor && editor.currentSpec) {
            if (editor.currentSpec.topic !== undefined) {
                editor.currentSpec.topic = newText;
            } else if (editor.currentSpec.center) {
                editor.currentSpec.center.text = newText;
            }
            
            // Re-render the entire diagram to reflect changes
            if (typeof editor.renderDiagram === 'function') {
                editor.renderDiagram();
                this.logger.info('[ThinkGuide]', 'Diagram re-rendered');
            }
            
            // After re-render, find and highlight the center element
            setTimeout(() => {
                this.logger.info('[ThinkGuide]', '🎯 Attempting to highlight center element');
                this.logger.info('[ThinkGuide]', 'window.nodeIndicator exists?', !!window.nodeIndicator);
                
                if (window.nodeIndicator) {
                    this.logger.info('[ThinkGuide]', '✅ Calling nodeIndicator.highlight("center")');
                    // Use 'flash' for center - very visible, no SVG filters
                    const result = window.nodeIndicator.highlight('center', {
                        type: 'flash',
                        duration: 1500,
                        intensity: 8,
                        color: '#FF9800'  // Orange for center changes
                    });
                    this.logger.info('[ThinkGuide]', 'Highlight result:', result);
                } else {
                    this.logger.error('[ThinkGuide] ❌ window.nodeIndicator not available!');
                }
            }, 100); // Small delay to ensure re-render is complete
            
            this.logger.info('[ThinkGuide] ✅ Center topic updated and highlighted');
        } else {
            this.logger.warn('[ThinkGuide] No editor or spec found');
        }
    }
    
    /**
     * Update node visual properties (color, bold, italic, etc.)
     */
    updateNodeProperties(nodeId, properties) {
        this.logger.info('[ThinkGuide]', 'Updating node properties:', { nodeId, properties });
        
        // Find the shape element (circle, rect, etc.)
        const shapeElement = d3.select(`[data-node-id="${nodeId}"]`);
        
        // Find the text element
        let textElement = d3.select(`text[data-node-id="${nodeId}"]`);
        if (textElement.empty()) {
            textElement = d3.select(`text[data-text-for="${nodeId}"]`);
        }
        
        if (!shapeElement.empty()) {
            // Apply shape properties with smooth transitions
            if (properties.fillColor) {
                shapeElement.transition().duration(400).attr('fill', properties.fillColor);
            }
            if (properties.strokeColor) {
                shapeElement.transition().duration(400).attr('stroke', properties.strokeColor);
            }
            if (properties.strokeWidth) {
                shapeElement.transition().duration(400).attr('stroke-width', properties.strokeWidth);
            }
            if (properties.opacity !== undefined) {
                shapeElement.transition().duration(400).attr('opacity', properties.opacity);
            }
            
            // Highlight the node after property changes
            setTimeout(() => {
                if (window.nodeIndicator) {
                    window.nodeIndicator.highlight(shapeElement.node(), {
                        type: 'pulse',
                        duration: 1500,
                        intensity: 5
                    });
                }
            }, 450);
        }
        
        if (!textElement.empty()) {
            // Apply text properties
            if (properties.textColor) {
                textElement.transition().duration(400).attr('fill', properties.textColor);
            }
            if (properties.fontSize) {
                textElement.transition().duration(400).attr('font-size', properties.fontSize);
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
        
        this.logger.info('[ThinkGuide] ✅ Properties updated with animation');
    }
    
    /**
     * Update node position (angle-based for Circle Maps)
     */
    updateNodePosition(nodeId, nodeIndex, position) {
        this.logger.info('[ThinkGuide]', 'Updating node position:', { nodeId, nodeIndex, position });
        
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
                .attr('cy', newY)
                .on('end', () => {
                    // Highlight after movement completes
                    if (window.nodeIndicator) {
                        window.nodeIndicator.highlight(shapeElement.node(), {
                            type: 'ping',
                            duration: 1500,
                            intensity: 7
                        });
                    }
                });
        }
        
        if (!textElement.empty()) {
            textElement
                .transition()
                .duration(500)
                .attr('x', newX)
                .attr('y', newY);
        }
        
        this.logger.info('[ThinkGuide] ✅ Position updated with animation');
    }
    
    /**
     * Swap positions of two nodes
     */
    swapNodePositions(nodeId1, nodeId2) {
        this.logger.info('[ThinkGuide]', 'Swapping positions:', { nodeId1, nodeId2 });
        
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
        shape1.transition().duration(500).attr('cx', x2).attr('cy', y2)
            .on('end', () => {
                if (window.nodeIndicator) {
                    window.nodeIndicator.highlight(shape1.node(), {
                        type: 'flash',
                        duration: 1200,
                        intensity: 6
                    });
                }
            });
        shape2.transition().duration(500).attr('cx', x1).attr('cy', y1)
            .on('end', () => {
                setTimeout(() => {
                    if (window.nodeIndicator) {
                        window.nodeIndicator.highlight(shape2.node(), {
                            type: 'flash',
                            duration: 1200,
                            intensity: 6
                        });
                    }
                }, 100); // Slight delay for second highlight
            });
        
        if (!text1.empty()) {
            text1.transition().duration(500).attr('x', x2).attr('y', y2);
        }
        if (!text2.empty()) {
            text2.transition().duration(500).attr('x', x1).attr('y', y1);
        }
        
        this.logger.info('[ThinkGuide] ✅ Positions swapped with animation');
    }
    
    /**
     * Replace entire diagram with new structure
     */
    replaceDiagram(newDiagramData) {
        this.logger.info('[ThinkGuide]', 'Replacing entire diagram');
        
        const editor = window.currentEditor;
        if (editor && typeof editor.loadDiagram === 'function') {
            editor.loadDiagram(newDiagramData);
            this.logger.info('[ThinkGuide]', '✅ Diagram replaced successfully');
        } else {
            this.logger.warn('[ThinkGuide]', 'Editor does not support loadDiagram');
        }
    }
    
    /**
     * Close thinking panel
     */
    closePanel() {
        if (this.panel) {
            if (window.panelManager) {
                this.logger.info('[ThinkGuide]', '🎯 Calling panelManager.closeThinkGuidePanel() - EXPLICIT METHOD');
                window.panelManager.closeThinkGuidePanel();
            } else {
                // Fallback
                this.logger.warn('[ThinkGuide]', '⚠️ PanelManager not available, using fallback');
                this.panel.classList.add('collapsed');
            }
            
            // Restore diagram to full canvas width after panel closes
            setTimeout(() => {
                const editor = window.currentEditor;
                if (editor && typeof editor.fitToCanvasFullWidth === 'function') {
                    editor.fitToCanvasFullWidth(true); // Expand to full width
                    this.logger.info('[ThinkGuide]', 'Diagram expanded to full canvas width');
                }
            }, 400); // Wait for panel close animation
            
            this.logger.info('[ThinkGuide]', 'Panel closed');
        }
    }
    
    /**
     * Fit diagram to canvas, accounting for panel space
     */
    fitDiagramToCanvas() {
        const editor = window.currentEditor;
        if (!editor) {
            this.logger.warn('[ThinkGuide]', 'No editor instance for fitToCanvas');
            return;
        }
        
        // Use the editor's fitToCanvasWithPanel method to reserve space for the ThinkGuide panel
        if (typeof editor.fitToCanvasWithPanel === 'function') {
            editor.fitToCanvasWithPanel(true); // Animated, reserves space for panel
            this.logger.info('[ThinkGuide]', 'Diagram fitted to canvas with panel space reserved');
        } else {
            this.logger.warn('[ThinkGuide]', 'Editor does not support fitToCanvasWithPanel');
        }
    }
    
    /**
     * Stop streaming (abort current request)
     */
    stopStreaming() {
        this.logger.info('[ThinkGuide]', 'stopStreaming called');
        if (this.currentAbortController) {
            this.logger.info('[ThinkGuide]', 'Aborting current stream');
            this.currentAbortController.abort();
            // Don't call hideStopButton here - let streamResponse handle cleanup
        } else {
            this.logger.warn('[ThinkGuide]', 'No active AbortController to stop');
        }
    }
    
    /**
     * Show stop button, hide send button
     */
    showStopButton() {
        this.logger.info('[ThinkGuide]', 'showStopButton called');
        if (this.stopBtn && this.sendBtn) {
            this.logger.info('[ThinkGuide]', 'Setting stop button display to flex');
            this.stopBtn.style.display = 'flex';
            this.sendBtn.style.display = 'none';
            this.inputArea.disabled = true;
        } else {
            this.logger.error('[ThinkGuide] Stop or Send button not found!', {
                stopBtn: !!this.stopBtn,
                sendBtn: !!this.sendBtn
            });
        }
    }
    
    /**
     * Hide stop button, show send button
     */
    hideStopButton() {
        this.logger.info('[ThinkGuide]', 'hideStopButton called');
        if (this.stopBtn && this.sendBtn) {
            this.logger.info('[ThinkGuide]', 'Setting stop button display to none');
            this.stopBtn.style.display = 'none';
            this.sendBtn.style.display = 'flex';
            this.inputArea.disabled = false;
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

