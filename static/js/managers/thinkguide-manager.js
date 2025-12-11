/**
 * ThinkGuide Manager (Event Bus Version)
 * =======================================
 * 
 * Manages Socratic guided thinking workflow with Event Bus architecture.
 * Uses SSEClient for proper incremental rendering (no blocking while loop).
 * Integrates with State Manager for centralized state.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class ThinkGuideManager {
    constructor(eventBus, stateManager, sseClient, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.sseClient = sseClient;
        // Ensure logger is always valid - check multiple fallbacks
        this.logger = logger || window.logger || window.frontendLogger || console;
        
        // Add owner identifier for Event Bus Listener Registry
        this.ownerId = 'ThinkGuideManager';
        
        // DOM elements
        this.panel = null;
        this.messagesContainer = null;
        this.inputArea = null;
        this.sendBtn = null;
        this.stopBtn = null;
        this.progressFill = null;
        this.progressLabel = null;
        this.closeBtn = null;
        this.nodePaletteBtn = null;
        
        // Session and state
        this.sessionId = null;
        this.diagramSessionId = null;
        this.currentAbortController = null;
        // Initialize language from languageManager if available
        this.language = window.languageManager?.getCurrentLanguage() || 'en';
        
        // Markdown renderer
        this.md = window.markdownit ? window.markdownit({
            html: false,
            linkify: true,
            breaks: false,
            // Disable typographer to prevent automatic character replacement
            // This prevents ":)" from being converted to "：）" etc.
            typographer: false
        }) : null;
        
        // Labels (i18n)
        this.labels = this._getLabels();
        
        // Store callback references for proper cleanup
        this.callbacks = {
            panelOpen: (data) => {
                if (data.panel === 'thinkguide') {
                    this.openPanel();
                }
            },
            panelClose: (data) => {
                if (data.panel === 'thinkguide') {
                    this.closePanel();
                }
            },
            sendMessage: (data) => {
                if (data.message) {
                    this.inputArea.value = data.message;
                    this.sendMessage();
                }
            },
            explainRequested: (data) => {
                this.explainConflict(data.conflictId);
            }
        };
        
        // Initialize
        this.init();
        this.subscribeToEvents();
        
        this.logger.info('ThinkGuideManager', 'Initialized with Event Bus');
    }
    
    /**
     * Initialize DOM and event listeners
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
            this.logger.warn('ThinkGuideManager', 'Panel not found - feature may be disabled');
            return;
        }
        
        // Bind UI events
        this.bindUIEvents();
        
        // Listen for language changes
        window.addEventListener('languageChanged', (event) => {
            this.language = event.detail.language;
            this.updateNodePaletteButtonText();
        });
    }
    
    /**
     * Subscribe to Event Bus events
     */
    subscribeToEvents() {
        // Listen for panel open requests - use stored callback with owner tracking
        this.eventBus.onWithOwner('panel:open_requested', this.callbacks.panelOpen, this.ownerId);
        
        // Listen for panel close requests - use stored callback with owner tracking
        this.eventBus.onWithOwner('panel:close_requested', this.callbacks.panelClose, this.ownerId);
        
        // Listen for message send requests (from voice agent) - use stored callback with owner tracking
        this.eventBus.onWithOwner('thinkguide:send_message', this.callbacks.sendMessage, this.ownerId);
        
        // Listen for explain requests (from voice agent) - use stored callback with owner tracking
        this.eventBus.onWithOwner('thinkguide:explain_requested', this.callbacks.explainRequested, this.ownerId);
        
        this.logger.debug('ThinkGuideManager', 'Event listeners registered with owner tracking');
    }
    
    /**
     * Bind UI event listeners
     */
    bindUIEvents() {
        // Send button
        if (this.sendBtn) {
            this.sendBtn.addEventListener('click', () => this.sendMessage());
        }
        
        // Stop button
        if (this.stopBtn) {
            this.stopBtn.addEventListener('click', () => this.stopStreaming());
        }
        
        // Close button
        if (this.closeBtn) {
            this.closeBtn.addEventListener('click', () => this.closePanel());
        }
        
        // Node palette button
        if (this.nodePaletteBtn) {
            this.nodePaletteBtn.addEventListener('click', () => this.openNodePalette());
        }
        
        // Input area - Enter to send
        if (this.inputArea) {
            this.inputArea.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
        }
    }
    
    /**
     * Open ThinkGuide panel
     */
    async openPanel() {
        if (!this.panel) return;
        
        // Mobile: Lock body scroll to prevent page shift
        if (window.innerWidth <= 768) {
            document.body.style.overflow = 'hidden';
            document.body.style.position = 'fixed';
            document.body.style.width = '100%';
            document.body.style.top = `-${window.scrollY}px`;
        }
        
        // Generate session ID if not already set
        if (!this.sessionId) {
            this.sessionId = this.generateSessionId();
        }
        
        // Update state
        this.stateManager.openPanel('thinkguide', {
            sessionId: this.sessionId,
            isStreaming: false,
            currentState: 'CONTEXT_GATHERING'
        });
        
        // Show panel via panel manager
        if (window.panelManager) {
            window.panelManager.openThinkGuidePanel();
        }
        
        // CATAPULT PRE-LOADING: Pre-load Node Palette data as soon as panel opens
        // This ensures data is ready when user clicks Node Palette button
        const rawDiagramData = window.currentEditor?.getCurrentDiagramData();
        if (rawDiagramData && this.diagramType) {
            this.preloadNodePalette(rawDiagramData).catch(err => {
                this.logger.error('ThinkGuideManager', 'Catapult pre-load failed (non-critical)', err);
            });
        }
        
        this.logger.info('ThinkGuideManager', 'Panel opened');
    }
    
    /**
     * Close ThinkGuide panel
     * 
     * @param {Object} options - Options for closing
     * @param {boolean} options._internal - If true, called from PanelManager (skip PanelManager call)
     */
    closePanel(options = {}) {
        if (!this.panel) return;
        
        // Check if already closed (prevent duplicate operations)
        if (this.panel.classList.contains('collapsed')) {
            this.logger.debug('ThinkGuideManager', 'Panel already closed, skipping');
            return;
        }
        
        const source = options._internal ? 'panel_manager' : 'user';
        this.logger.info('ThinkGuideManager', 'Closing panel', { source });
        
        // Mobile: Unlock body scroll
        if (window.innerWidth <= 768) {
            const scrollY = document.body.style.top;
            document.body.style.overflow = '';
            document.body.style.position = '';
            document.body.style.width = '';
            document.body.style.top = '';
            window.scrollTo(0, parseInt(scrollY || '0') * -1);
        }
        
        // Stop any active streaming (always do this, regardless of source)
        if (this.currentAbortController) {
            this.stopStreaming();
        }
        
        // If called from PanelManager, just do internal cleanup
        // Otherwise, ask PanelManager to close (which will call us back with _internal flag)
        if (options._internal) {
            // Internal call from PanelManager - do internal cleanup
            // PanelManager will handle DOM and state updates
            // Update our own state
            this.stateManager.closePanel('thinkguide');
            this.logger.info('ThinkGuideManager', 'Panel closed', { source });
            
        } else {
            // User-initiated close - delegate to PanelManager
            // PanelManager will call this method again with _internal: true
            // to allow us to do cleanup (stop streaming, update state)
            // Don't do cleanup here - wait for PanelManager's callback
            if (window.panelManager) {
                window.panelManager.closeThinkGuidePanel();
            } else {
                // Fallback if PanelManager not available
                this.stateManager.closePanel('thinkguide');
                if (this.panel) {
                    this.panel.classList.add('collapsed');
                }
            }
            // Note: PanelManager will call this method again with _internal: true,
            // which will handle the actual cleanup (stop streaming, update state)
        }
    }
    
    /**
     * Start thinking mode for current diagram
     */
    async startThinkingMode(diagramType, diagramData) {
        this.diagramType = diagramType;
        
        // Sync language when starting (user may have changed it)
        this.language = window.languageManager?.getCurrentLanguage() || this.language;
        
        // Check if we're opening for a new diagram session (following MindMate pattern)
        const currentDiagramSessionId = window.currentEditor?.sessionId;
        const isNewDiagramSession = !this.diagramSessionId || this.diagramSessionId !== currentDiagramSessionId;
        
        // Check if conversation already exists (has messages)
        const hasExistingMessages = this.messagesContainer && 
                                    this.messagesContainer.children.length > 0;
        
        // Open panel first (this will trigger catapult pre-loading automatically)
        await this.openPanel();
        
        // Only clear messages and start stream if NEW diagram session OR no existing messages
        if (isNewDiagramSession || !hasExistingMessages) {
            // New diagram or first time - start fresh
            if (isNewDiagramSession) {
                this.logger.info('ThinkGuideManager', 'New diagram session detected', {
                    oldSession: this.diagramSessionId,
                    newSession: currentDiagramSessionId
                });
                this.diagramSessionId = currentDiagramSessionId;
            }
            
            // Clear messages
            if (this.messagesContainer) {
                this.messagesContainer.innerHTML = '';
            }
            
            // Start streaming analysis (backend will send greeting)
            await this.streamAnalysis(diagramData, true);
            
            this.logger.info('ThinkGuideManager', 'Thinking mode started', {
                diagramType,
                language: this.language,
                isNewSession: isNewDiagramSession
            });
        } else {
            // Same diagram session with existing conversation - keep it alive
            this.logger.info('ThinkGuideManager', 'Resuming existing conversation', {
                diagramType,
                messageCount: this.messagesContainer.children.length,
                diagramSessionId: this.diagramSessionId
            });
            // Panel already opened above - conversation preserved ✅
        }
    }
    
    /**
     * Send user message
     */
    async sendMessage() {
        const message = this.inputArea?.value.trim();
        if (!message) return;
        
        // Add user message to UI
        this.addUserMessage(message);
        
        // Clear input
        this.inputArea.value = '';
        
        // Get current diagram data
        const diagramData = window.currentEditor?.getCurrentDiagramData();
        
        // Stream response
        await this.streamAnalysis(diagramData, false, message);
    }
    
    /**
     * Stream analysis from backend using SSE Client
     */
    async streamAnalysis(diagramData, isInitialGreeting, userMessage = null) {
        // Update state
        this.stateManager.updatePanelState('thinkguide', { isStreaming: true });
        
        // Disable input
        if (this.sendBtn) this.sendBtn.disabled = true;
        if (this.inputArea) this.inputArea.disabled = true;
        if (this.stopBtn) this.stopBtn.style.display = 'inline-block';
        
        // Show typing indicator
        const typingIndicator = this.showTypingIndicator();
        
        // Create abort controller
        this.currentAbortController = new AbortController();
        
        // Prepare request data
        const requestData = {
            message: userMessage || '',
            user_id: auth?.getUser()?.phone || 'anonymous',
            session_id: this.sessionId,
            diagram_type: this.diagramType || diagramData?.type || 'unknown',
            diagram_data: diagramData,
            current_state: this.stateManager.getPanelState('thinkguide').currentState,
            is_initial_greeting: isInitialGreeting,
            language: this.language
        };
        
        // Create message div for streaming content
        const messageDiv = this.createAssistantMessageDiv();
        
        try {
            // Use SSE Client (no blocking while loop!)
            await this.sseClient.start(
                '/thinking_mode/stream',
                requestData,
                {
                    onChunk: (data) => {
                        // Remove typing indicator on first chunk (with delay to show animation)
                        if (typingIndicator && typingIndicator.parentNode) {
                            setTimeout(() => {
                                if (typingIndicator && typingIndicator.parentNode) {
                                    typingIndicator.parentNode.removeChild(typingIndicator);
                                }
                            }, 500); // Keep cute animation visible for 500ms
                            typingIndicator = null; // Prevent multiple removals
                        }
                        
                        // Handle SSE event
                        this.handleSSEEvent(data, messageDiv);
                    },
                    onComplete: () => {
                        this.logger.info('ThinkGuideManager', 'Stream completed');
                        this.onStreamComplete();
                    },
                    onError: (error) => {
                        if (error.name !== 'AbortError') {
                            this.logger.error('ThinkGuideManager', 'Stream error', error);
                            this.addSystemMessage('Error: ' + error.message);
                        }
                        this.onStreamComplete();
                    }
                },
                this.currentAbortController
            );
            
        } catch (error) {
            if (error.name !== 'AbortError') {
                this.logger.error('ThinkGuideManager', 'Stream error', error);
            }
        } finally {
            this.currentAbortController = null;
        }
    }
    
    /**
     * Handle SSE event
     */
    handleSSEEvent(data, messageDiv) {
        const { event, content, new_state, progress, message } = data;
        
        // Get the content div from the message div
        const contentDiv = messageDiv.querySelector('.thinking-message-content');
        if (!contentDiv) return;
        
        switch (event) {
            case 'message_chunk':
                // Accumulate text
                if (!contentDiv.dataset.rawText) {
                    contentDiv.dataset.rawText = '';
                }
                contentDiv.dataset.rawText += content;
                
                // Render markdown with sanitization
                if (this.md) {
                    const html = this.md.render(contentDiv.dataset.rawText);
                    contentDiv.innerHTML = window.DOMPurify ? window.DOMPurify.sanitize(html) : html;
                } else {
                    contentDiv.textContent = contentDiv.dataset.rawText;
                }
                
                // Scroll to bottom
                this.scrollToBottom();
                break;
                
            case 'state_change':
                // Update state
                this.stateManager.updatePanelState('thinkguide', {
                    currentState: new_state
                });
                
                // Update progress bar
                if (progress !== undefined) {
                    this.updateProgress(progress, message);
                }
                break;
                
            case 'complete':
                // Stream complete
                this.onStreamComplete();
                break;
                
            case 'error':
                this.addSystemMessage('Error: ' + (message || 'Unknown error'));
                this.onStreamComplete();
                break;
        }
    }
    
    /**
     * Stream complete handler
     */
    onStreamComplete() {
        // Remove streaming class from the last message
        const streamingMessages = this.messagesContainer.querySelectorAll('.thinking-message.streaming');
        streamingMessages.forEach(msg => msg.classList.remove('streaming'));
        
        // Update state
        this.stateManager.updatePanelState('thinkguide', { isStreaming: false });
        
        // Re-enable input
        if (this.sendBtn) this.sendBtn.disabled = false;
        if (this.inputArea) {
            this.inputArea.disabled = false;
            this.inputArea.focus();
        }
        if (this.stopBtn) this.stopBtn.style.display = 'none';
        
        // Emit completion event
        this.eventBus.emit('thinkguide:stream_completed', {
            sessionId: this.sessionId
        });
    }
    
    /**
     * Stop streaming
     */
    stopStreaming() {
        if (this.currentAbortController) {
            this.currentAbortController.abort();
            this.currentAbortController = null;
            
            const stopMsg = this.language === 'zh' ? 
                '⏹ 已停止生成' : 
                '⏹ Generation stopped';
            this.addSystemMessage(stopMsg);
            
            this.logger.info('ThinkGuideManager', 'Stream stopped by user');
        }
    }
    
    /**
     * UI Helper Methods
     */
    
    createAssistantMessageDiv() {
        const div = document.createElement('div');
        div.className = 'thinking-message assistant streaming';
        
        // Create content wrapper for markdown rendering
        const contentDiv = document.createElement('div');
        contentDiv.className = 'thinking-message-content';
        contentDiv.dataset.rawText = '';
        div.appendChild(contentDiv);
        
        this.messagesContainer.appendChild(div);
        this.scrollToBottom();
        return div;
    }
    
    addUserMessage(text) {
        const div = document.createElement('div');
        div.className = 'thinking-message user';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'thinking-message-content';
        contentDiv.textContent = text;
        div.appendChild(contentDiv);
        
        this.messagesContainer.appendChild(div);
        this.scrollToBottom();
    }
    
    addSystemMessage(text) {
        const div = document.createElement('div');
        div.className = 'thinking-message assistant';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'thinking-message-content';
        
        // Render markdown for system messages too
        if (this.md) {
            const html = this.md.render(text);
            contentDiv.innerHTML = window.DOMPurify ? window.DOMPurify.sanitize(html) : html;
        } else {
            contentDiv.textContent = text;
        }
        
        div.appendChild(contentDiv);
        this.messagesContainer.appendChild(div);
        this.scrollToBottom();
    }
    
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
    
    updateProgress(progress, label) {
        if (this.progressFill) {
            this.progressFill.style.width = `${progress}%`;
        }
        if (this.progressLabel && label) {
            this.progressLabel.textContent = label;
        }
    }
    
    scrollToBottom() {
        if (this.messagesContainer) {
            this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
        }
    }
    
    /**
     * Pre-load Node Palette data in background (Catapult system)
     * This caches data so opening is instant
     */
    async preloadNodePalette(diagramData) {
        try {
            // Get current diagram data from editor
            const rawDiagramData = diagramData || window.currentEditor?.getCurrentDiagramData();
            
            if (!rawDiagramData) {
                this.logger.debug('ThinkGuideManager', 'No diagram data for preload');
                return;
            }
            
            // Extract spec from diagram data structure
            const diagramSpec = rawDiagramData.spec || rawDiagramData;
            
            // Extract center topic
            let centerTopic;
            if (['tree_map', 'mindmap'].includes(this.diagramType)) {
                centerTopic = diagramSpec.topic || '';
            } else if (this.diagramType === 'flow_map') {
                centerTopic = diagramSpec.title || '';
            } else if (this.diagramType === 'brace_map') {
                centerTopic = diagramSpec.whole || '';
            } else if (this.diagramType === 'double_bubble_map') {
                centerTopic = `${diagramSpec.left || ''} vs ${diagramSpec.right || ''}`;
            } else if (this.diagramType === 'multi_flow_map') {
                centerTopic = diagramSpec.event || '';
            } else if (this.diagramType === 'bridge_map') {
                centerTopic = diagramSpec.dimension || '';
            } else if (this.diagramType === 'circle_map') {
                centerTopic = diagramSpec.topic || '';
            } else if (this.diagramType === 'bubble_map') {
                centerTopic = diagramSpec.topic || '';
            } else {
                centerTopic = diagramSpec.center?.text || diagramSpec.topic || '';
            }
            
            if (!centerTopic) {
                this.logger.debug('ThinkGuideManager', 'No center topic for preload');
                return;
            }
            
            this.logger.info('ThinkGuideManager', 'Catapult pre-loading Node Palette', {
                centerTopic,
                diagramType: this.diagramType
            });
            
            // Call Node Palette Manager's preload method
            if (window.currentEditor?.nodePalette && window.currentEditor.nodePalette.preload) {
                await window.currentEditor.nodePalette.preload(
                    centerTopic,
                    diagramSpec,
                    this.sessionId,
                    this.extractEducationalContext(),
                    this.diagramType
                );
                this.logger.info('ThinkGuideManager', 'Catapult pre-load complete');
            } else {
                this.logger.warn('ThinkGuideManager', 'NodePaletteManager.preload not available');
            }
        } catch (error) {
            this.logger.error('ThinkGuideManager', 'Preload error', {
                error: error.message,
                stack: error.stack
            });
        }
    }
    
    async openNodePalette() {
        this.logger.info('ThinkGuideManager', 'Opening Node Palette');
        
        // Get current diagram data from editor
        const rawDiagramData = window.currentEditor?.getCurrentDiagramData();
        if (!rawDiagramData) {
            this.logger.error('ThinkGuideManager', 'No diagram data available');
            return;
        }
        
        // Extract spec from editor data structure (Node Palette expects raw spec format)
        const diagramSpec = rawDiagramData.spec || rawDiagramData;
        
        // Extract center topic based on diagram type from spec
        let centerTopic;
        if (['tree_map', 'mindmap'].includes(this.diagramType)) {
            centerTopic = diagramSpec.topic || '';
        } else if (this.diagramType === 'flow_map') {
            centerTopic = diagramSpec.title || '';
        } else if (this.diagramType === 'brace_map') {
            centerTopic = diagramSpec.whole || '';
        } else if (this.diagramType === 'double_bubble_map') {
            centerTopic = `${diagramSpec.left || ''} vs ${diagramSpec.right || ''}`;
        } else if (this.diagramType === 'multi_flow_map') {
            centerTopic = diagramSpec.event || '';
        } else if (this.diagramType === 'bridge_map') {
            centerTopic = diagramSpec.dimension || '';
        } else if (this.diagramType === 'circle_map') {
            centerTopic = diagramSpec.topic || '';
        } else if (this.diagramType === 'bubble_map') {
            centerTopic = diagramSpec.topic || '';
        } else {
            // Generic fallback
            centerTopic = diagramSpec.center?.text || diagramSpec.topic || '';
        }
        
        this.logger.debug('ThinkGuideManager', 'Starting Node Palette', {
            diagramType: this.diagramType,
            centerTopic,
            sessionId: this.sessionId,
            specKeys: Object.keys(diagramSpec)
        });
        
        // Open panel first
        this.eventBus.emit('panel:open_requested', { panel: 'nodePalette' });
        
        // Start Node Palette Manager with raw spec (backend expects raw format)
        if (window.currentEditor?.nodePalette) {
            const nodePalette = window.currentEditor.nodePalette;
            
            // Check if Node Palette already has nodes for this session (user returning)
            // Check BEFORE calling start() because start() may modify sessionId
            const isReturningSession = nodePalette.sessionId === this.sessionId && 
                                       nodePalette.nodes && 
                                       nodePalette.nodes.length > 0;
            
            // Call start() - this will preserve nodes if same session, or clear if new session
            await nodePalette.start(
                centerTopic,
                diagramSpec,  // Send raw spec format, not normalized
                this.sessionId,
                this.extractEducationalContext(),
                this.diagramType
            );
            
            // Only show message if it's a NEW session (first time opening)
            // If returning to existing session with nodes, don't spam the message
            if (!isReturningSession) {
                const msg = this.language === 'zh' ? 
                    '正在打开节点选择板，AI将为您头脑风暴更多想法...' : 
                    'Opening Node Palette, AI will brainstorm more ideas for you...';
                this.addSystemMessage(msg);
            } else {
                this.logger.debug('ThinkGuideManager', 'Node Palette returning session - skipping opening message', {
                    sessionId: this.sessionId,
                    existingNodes: nodePalette.nodes.length
                });
            }
        } else {
            this.logger.error('ThinkGuideManager', 'NodePaletteManager not found');
        }
    }
    
    updateNodePaletteButtonText() {
        if (this.nodePaletteBtn) {
            const label = this.labels[this.language] || this.labels.en;
            this.nodePaletteBtn.textContent = label.nodePalette;
            this.nodePaletteBtn.title = label.nodePaletteTooltip;
        }
    }
    
    explainConflict(conflictId) {
        const conflicts = this.stateManager.getPanelState('thinkguide').cognitiveConflicts;
        if (conflicts && conflicts[conflictId - 1]) {
            const conflict = conflicts[conflictId - 1];
            const message = `Please elaborate on example ${conflictId}: ${conflict.text}`;
            this.inputArea.value = message;
            this.sendMessage();
        }
    }
    
    generateSessionId() {
        return `thinkguide_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
    
    /**
     * Normalize diagram spec to ThinkGuide format
     * Converts diagram-specific structure to standard format
     */
    normalizeDiagramData(spec, diagramType) {
        this.logger.debug('ThinkGuideManager', 'Normalizing diagram data:', { diagramType, spec });
        
        switch (diagramType) {
            case 'circle_map':
                return {
                    center: { text: spec.topic || spec.center?.text || '' },
                    children: (spec.context || spec.items || spec.children || []).map((item, index) => ({
                        id: item.id || `context_${index}`,
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
                // Generic fallback
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
     * Extract educational context for Node Palette
     */
    extractEducationalContext() {
        const panelState = this.stateManager.getPanelState('thinkguide');
        
        const context = {
            session_id: this.sessionId,
            diagram_type: panelState.diagramType || 'circle_map',
            language: this.language,
            raw_message: 'K12 teaching context from ThinkGuide session'
        };
        
        // Include last user message if available
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
        
        this.logger.debug('ThinkGuideManager', 'Extracted educational context:', context);
        return context;
    }
    
    _getLabels() {
        return {
            en: {
                starting: 'Starting...',
                contextGathering: 'Gathering Context...',
                analysis: 'Socratic Analysis...',
                complete: 'Complete!',
                nodePalette: 'Node Palette',
                nodePaletteTooltip: 'Open Node Palette to brainstorm nodes with AI'
            },
            zh: {
                starting: '启动中...',
                contextGathering: '收集背景信息...',
                analysis: '苏格拉底式分析...',
                complete: '完成！',
                nodePalette: '瀑布流',
                nodePaletteTooltip: '打开瀑布流，AI为您头脑风暴更多节点'
            }
        };
    }
    
    /**
     * Clean up resources
     */
    destroy() {
        this.logger.debug('ThinkGuideManager', 'Destroying');
        
        // Stop any active streaming
        if (this.currentAbortController) {
            this.currentAbortController.abort();
            this.currentAbortController = null;
        }
        
        // Remove all Event Bus listeners using Listener Registry
        if (this.eventBus && this.ownerId) {
            this.eventBus.removeAllListenersForOwner(this.ownerId);
            this.logger.debug('ThinkGuideManager', 'Event listeners successfully removed');
        }
        
        // Clear session data
        this.sessionId = null;
        this.diagramSessionId = null;
        
        // Nullify references
        this.callbacks = null;
        this.eventBus = null;
        this.stateManager = null;
        this.sseClient = null;
        this.panel = null;
        this.messagesContainer = null;
        this.inputArea = null;
        this.sendBtn = null;
        this.stopBtn = null;
        this.progressFill = null;
        this.progressLabel = null;
        this.closeBtn = null;
        this.nodePaletteBtn = null;
        this.md = null;
        this.logger = null;
    }
}

// NOTE: No longer auto-initialized globally.
// Now created per-session in DiagramSelector and managed by SessionLifecycleManager.

