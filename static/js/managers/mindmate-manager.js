/**
 * MindMate Manager (Event Bus Version)
 * =====================================
 * 
 * Manages MindMate AI assistant with Event Bus architecture.
 * Already uses correct SSE pattern (recursive promise chain) ✅
 * This version adds Event Bus integration for decoupled communication.
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 */

class MindMateManager {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        this.logger = logger;
        
        // User and session management
        this.userId = this.generateUserId();
        this.conversationId = null;
        this.diagramSessionId = null;
        this.hasGreeted = false;
        
        // Streaming state
        this.currentStreamingMessage = null;
        this.messageBuffer = '';
        
        // Markdown renderer
        this.md = window.markdownit ? window.markdownit({
            html: false,
            linkify: true,
            breaks: true
        }) : null;
        
        // DOM elements
        this.panel = null;
        this.chatMessages = null;
        this.chatInput = null;
        this.sendBtn = null;
        this.toggleBtn = null;
        this.mindmateBtn = null;
        
        // Initialize
        this.initializeElements();
        this.bindEvents();
        this.subscribeToEvents();
        
        this.logger.info('MindMateManager', 'Initialized with Event Bus', { userId: this.userId });
    }
    
    /**
     * Initialize DOM elements
     */
    initializeElements() {
        this.panel = document.getElementById('ai-assistant-panel');
        this.toggleBtn = document.getElementById('toggle-ai-assistant');
        this.mindmateBtn = document.getElementById('mindmate-ai-btn');
        this.chatMessages = document.getElementById('ai-chat-messages');
        this.chatInput = document.getElementById('ai-chat-input');
        this.sendBtn = document.getElementById('ai-chat-send');
        
        if (this.panel && !this.mindmateBtn) {
            this.logger.error('MindMateManager', 'MindMate button not found in DOM');
        }
    }
    
    /**
     * Bind UI event listeners
     */
    bindEvents() {
        // Close button in panel
        if (this.toggleBtn) {
            this.toggleBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.togglePanel();
            });
        }
        
        // MindMate AI button in toolbar
        if (this.mindmateBtn) {
            this.mindmateBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.togglePanel();
            });
        }
        
        // Send message button
        if (this.sendBtn) {
            this.sendBtn.addEventListener('click', () => this.sendMessage());
        }
        
        // Send on Enter (Shift+Enter for newline)
        if (this.chatInput) {
            this.chatInput.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
            
            // Auto-resize textarea
            this.chatInput.addEventListener('input', () => this.autoResizeTextarea());
        }
    }
    
    /**
     * Subscribe to Event Bus events
     */
    subscribeToEvents() {
        // Listen for panel open requests
        this.eventBus.on('panel:open_requested', (data) => {
            if (data.panel === 'mindmate') {
                this.openPanel();
            }
        });
        
        // Listen for panel close requests
        this.eventBus.on('panel:close_requested', (data) => {
            if (data.panel === 'mindmate') {
                this.closePanel();
            }
        });
        
        // Listen for message send requests (from voice agent)
        this.eventBus.on('mindmate:send_message', (data) => {
            if (data.message) {
                this.chatInput.value = data.message;
                this.sendMessage();
            }
        });
        
        this.logger.debug('MindMateManager', 'Subscribed to events');
    }
    
    /**
     * Toggle MindMate panel
     */
    togglePanel() {
        if (!this.panel) {
            this.logger.error('MindMateManager', 'Panel not found');
            alert('AI Assistant panel not found. Please reload the page.');
            return;
        }
        
        const isCurrentlyClosed = this.panel.classList.contains('collapsed');
        
        if (isCurrentlyClosed) {
            this.openPanel();
        } else {
            this.closePanel();
        }
    }
    
    /**
     * Open MindMate panel
     */
    openPanel() {
        if (!this.panel) return;
        
        this.logger.info('MindMateManager', 'Opening panel');
        
        // Check if we're opening for a new diagram session
        const currentDiagramSessionId = window.currentEditor?.sessionId;
        const isNewDiagramSession = !this.diagramSessionId || this.diagramSessionId !== currentDiagramSessionId;
        
        if (isNewDiagramSession) {
            this.logger.info('MindMateManager', 'New diagram session detected', {
                oldSession: this.diagramSessionId,
                newSession: currentDiagramSessionId
            });
            
            // Reset conversation for new diagram
            this.diagramSessionId = currentDiagramSessionId;
            this.conversationId = null;
            this.hasGreeted = false;
            if (this.chatMessages) {
                this.chatMessages.innerHTML = ''; // Clear old messages
            }
        }
        
        // Open via Panel Manager (Event Bus)
        if (window.panelManager) {
            window.panelManager.openMindMatePanel();
        } else {
            // Fallback
            this.panel.classList.remove('collapsed');
            if (this.mindmateBtn) {
                this.mindmateBtn.classList.add('active');
            }
        }
        
        // Send conversation opener for new sessions
        if (!this.hasGreeted) {
            this.hasGreeted = true;
            setTimeout(() => {
                this.sendConversationOpener();
            }, 300);
        }
        
        // Focus input
        if (this.chatInput) {
            setTimeout(() => this.chatInput.focus(), 800);
        }
        
        // Trigger canvas resize
        setTimeout(() => {
            if (window.currentEditor && typeof window.currentEditor.fitDiagramToWindow === 'function') {
                window.currentEditor.fitDiagramToWindow();
            }
        }, 450);
        
        // Emit event
        this.eventBus.emit('mindmate:opened', { diagramSessionId: this.diagramSessionId });
    }
    
    /**
     * Close MindMate panel
     */
    closePanel() {
        if (!this.panel) return;
        
        this.logger.info('MindMateManager', 'Closing panel');
        
        // Close via Panel Manager (Event Bus)
        if (window.panelManager) {
            window.panelManager.closeMindMatePanel();
        } else {
            // Fallback
            this.panel.classList.add('collapsed');
            if (this.mindmateBtn) {
                this.mindmateBtn.classList.remove('active');
            }
        }
        
        // Emit event
        this.eventBus.emit('mindmate:closed', {});
    }
    
    /**
     * Send user message
     */
    async sendMessage() {
        const message = this.chatInput?.value.trim();
        if (!message) return;
        
        // Clear input
        this.chatInput.value = '';
        this.autoResizeTextarea();
        
        // Send message
        await this.sendMessageToDify(message, true);
    }
    
    /**
     * Send conversation opener (greeting)
     */
    async sendConversationOpener() {
        if (!this.chatMessages) return;
        
        this.logger.debug('MindMateManager', 'Triggering conversation opener');
        
        try {
            const DIFY_OPENER_TRIGGER = 'start';
            await this.sendMessageToDify(DIFY_OPENER_TRIGGER, false);
            this.logger.info('MindMateManager', 'Conversation opener triggered');
        } catch (error) {
            this.logger.error('MindMateManager', 'Failed to trigger conversation opener', {
                error: error.message || String(error),
                stack: error.stack
            });
            this.showFallbackWelcome();
        }
    }
    
    /**
     * Send message to Dify API with SSE streaming
     */
    async sendMessageToDify(message, showUserMessage = true) {
        if (!this.chatMessages) return;
        
        // Show user message
        if (showUserMessage) {
            this.addMessage('user', message);
        }
        
        // Show typing indicator
        const typingIndicator = this.showTypingIndicator();
        
        // Disable input
        this.setInputEnabled(false);
        
        // Emit event
        this.eventBus.emit('mindmate:message_sending', { message });
        
        // Track if we've removed the typing indicator
        let typingIndicatorRemoved = false;
        
        return new Promise((resolve, reject) => {
            const payload = {
                message: message,
                user_id: this.userId,
                conversation_id: this.conversationId
            };
            
            // Use authenticated fetch with SSE streaming
            // Note: 'auth' is global from auth-helper.js, not window.auth
            auth.fetch('/api/ai_assistant/stream', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                
                // ✅ CORRECT SSE PATTERN: Recursive promise chain (non-blocking)
                const readChunk = () => {
                    reader.read().then(({ done, value }) => {
                        if (done) {
                            // Stream ended
                            if (this.currentStreamingMessage) {
                                this.currentStreamingMessage.classList.remove('streaming');
                            }
                            
                            // Re-enable input
                            this.setInputEnabled(true);
                            
                            // Emit completion event
                            this.eventBus.emit('mindmate:message_completed', {
                                conversationId: this.conversationId
                            });
                            
                            resolve();
                            return;
                        }
                        
                        // Decode chunk
                        const chunk = decoder.decode(value, { stream: true });
                        const lines = chunk.split('\n');
                        
                        for (const line of lines) {
                            if (line.startsWith('data: ')) {
                                try {
                                    const data = JSON.parse(line.slice(6));
                                    this.handleStreamEvent(data);
                                    
                                    // Remove typing indicator on first content chunk (with delay to show animation)
                                    if (!typingIndicatorRemoved && data.event === 'message' && data.answer) {
                                        typingIndicatorRemoved = true;
                                        setTimeout(() => {
                                            if (typingIndicator && typingIndicator.parentNode) {
                                                typingIndicator.parentNode.removeChild(typingIndicator);
                                            }
                                        }, 500); // Keep cute animation visible for 500ms
                                    }
                                } catch (e) {
                                    this.logger.debug('MindMateManager', 'Skipping malformed JSON');
                                }
                            }
                        }
                        
                        // Continue reading - RETURNS TO EVENT LOOP ✅
                        readChunk();
                    }).catch(error => {
                        this.logger.error('MindMateManager', 'Stream error', {
                            error: error.message || String(error),
                            stack: error.stack
                        });
                        
                        // Remove typing indicator (immediately on error)
                        typingIndicatorRemoved = true;
                        if (typingIndicator && typingIndicator.parentNode) {
                            typingIndicator.parentNode.removeChild(typingIndicator);
                        }
                        
                        // Re-enable input
                        this.setInputEnabled(true);
                        
                        // Emit error event
                        this.eventBus.emit('mindmate:error', { error: error.message });
                        
                        reject(error);
                    });
                };
                
                readChunk(); // Start recursive chain
            })
            .catch(error => {
                this.logger.error('MindMateManager', 'Fetch error', {
                    error: error.message || String(error),
                    stack: error.stack,
                    status: error.status
                });
                
                // Remove typing indicator (immediately on error)
                typingIndicatorRemoved = true;
                if (typingIndicator && typingIndicator.parentNode) {
                    typingIndicator.parentNode.removeChild(typingIndicator);
                }
                
                // Re-enable input
                this.setInputEnabled(true);
                
                // Emit error event
                this.eventBus.emit('mindmate:error', { error: error.message });
                
                reject(error);
            });
        });
    }
    
    /**
     * Handle stream event from SSE
     */
    handleStreamEvent(data) {
        const event = data.event;
        
        if (event === 'message') {
            // Append message chunk
            const content = data.answer || '';
            if (content) {
                this.messageBuffer += content;
                this.updateStreamingMessage(this.messageBuffer);
                
                // Emit chunk event
                this.eventBus.emit('mindmate:message_chunk', { chunk: content });
            }
            
            // Save conversation ID
            if (data.conversation_id && !this.conversationId) {
                this.conversationId = data.conversation_id;
            }
            
        } else if (event === 'message_end') {
            // Stream complete
            if (this.currentStreamingMessage) {
                this.currentStreamingMessage.classList.remove('streaming');
            }
            
            // Save conversation ID
            if (data.conversation_id) {
                this.conversationId = data.conversation_id;
            }
            
            this.messageBuffer = '';
            this.currentStreamingMessage = null;
            
        } else if (event === 'error') {
            // Handle error
            this.logger.error('MindMateManager', 'Stream error', { error: data.error });
            
            if (this.currentStreamingMessage && this.currentStreamingMessage.parentNode) {
                this.currentStreamingMessage.parentNode.removeChild(this.currentStreamingMessage);
            }
            
            this.addMessage('assistant', `Error: ${data.error}`);
            this.messageBuffer = '';
            this.currentStreamingMessage = null;
            
            // Emit error event
            this.eventBus.emit('mindmate:stream_error', { error: data.error });
        }
    }
    
    /**
     * Update streaming message content
     */
    updateStreamingMessage(text) {
        if (!this.currentStreamingMessage) {
            // Create new streaming message
            this.currentStreamingMessage = this.createMessageElement('assistant', '');
            this.currentStreamingMessage.classList.add('streaming');
            this.chatMessages.appendChild(this.currentStreamingMessage);
        }
        
        const contentDiv = this.currentStreamingMessage.querySelector('.ai-message-content');
        if (contentDiv && this.md) {
            // Render markdown and sanitize
            const html = this.md.render(text);
            contentDiv.innerHTML = window.DOMPurify ? window.DOMPurify.sanitize(html) : html;
            
            // Scroll to bottom
            this.scrollToBottom();
        }
    }
    
    /**
     * Add message to chat
     */
    addMessage(type, content) {
        const messageEl = this.createMessageElement(type, content);
        this.chatMessages.appendChild(messageEl);
        this.scrollToBottom();
        return messageEl;
    }
    
    /**
     * Create message element
     */
    createMessageElement(type, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `ai-message ${type}`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'ai-message-content';
        
        if (content && this.md) {
            // Render markdown and sanitize
            const html = this.md.render(content);
            contentDiv.innerHTML = window.DOMPurify ? window.DOMPurify.sanitize(html) : html;
        } else {
            contentDiv.textContent = content;
        }
        
        messageDiv.appendChild(contentDiv);
        return messageDiv;
    }
    
    /**
     * Show typing indicator
     */
    showTypingIndicator() {
        const indicator = document.createElement('div');
        indicator.className = 'ai-typing-indicator';
        indicator.innerHTML = `
            <div class="ai-typing-dots">
                <span></span><span></span><span></span>
            </div>
        `;
        this.chatMessages.appendChild(indicator);
        this.scrollToBottom();
        return indicator;
    }
    
    /**
     * Show fallback welcome message
     */
    showFallbackWelcome() {
        if (!this.chatMessages) return;
        
        const language = this.detectLanguage();
        const aiName = window.AI_ASSISTANT_NAME || 'MindMate AI';
        
        const welcomeDiv = document.createElement('div');
        welcomeDiv.className = 'ai-welcome-message';
        
        if (language === 'zh') {
            welcomeDiv.innerHTML = `
                <div class="welcome-icon">✨</div>
                <div class="welcome-text">
                    <strong>${aiName}</strong> 已就绪<br>
                    有什么可以帮助您的吗？
                </div>
            `;
        } else {
            welcomeDiv.innerHTML = `
                <div class="welcome-icon">✨</div>
                <div class="welcome-text">
                    <strong>${aiName}</strong> is ready<br>
                    How can I help you today?
                </div>
            `;
        }
        
        this.chatMessages.appendChild(welcomeDiv);
        this.scrollToBottom();
    }
    
    /**
     * Auto-resize textarea
     */
    autoResizeTextarea() {
        if (!this.chatInput) return;
        
        this.chatInput.style.height = 'auto';
        this.chatInput.style.height = Math.min(this.chatInput.scrollHeight, 120) + 'px';
    }
    
    /**
     * Enable/disable input
     */
    setInputEnabled(enabled) {
        if (this.chatInput) {
            this.chatInput.disabled = !enabled;
        }
        if (this.sendBtn) {
            this.sendBtn.disabled = !enabled;
        }
    }
    
    /**
     * Scroll chat to bottom
     */
    scrollToBottom() {
        if (this.chatMessages) {
            this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        }
    }
    
    /**
     * Detect language
     */
    detectLanguage() {
        return window.currentLanguage || navigator.language.startsWith('zh') ? 'zh' : 'en';
    }
    
    /**
     * Generate unique user ID
     */
    generateUserId() {
        let userId = localStorage.getItem('mindgraph_user_id');
        if (!userId) {
            userId = 'user_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('mindgraph_user_id', userId);
        }
        return userId;
    }
}

// Initialize when dependencies are ready
if (typeof window !== 'undefined') {
    const initMindMateManager = () => {
        // Check if MindMate feature is enabled (button exists)
        const mindmateBtn = document.getElementById('mindmate-ai-btn');
        if (!mindmateBtn) {
            window.logger?.debug('MindMateManager', 'Feature disabled, skipping initialization');
            return;
        }
        
        if (window.eventBus && window.stateManager && window.logger) {
            window.aiAssistantManager = new MindMateManager(
                window.eventBus,
                window.stateManager,
                window.logger
            );
            
            // Backward compatibility
            window.aiAssistant = window.aiAssistantManager;
            
            if (window.logger.debugMode) {
                console.log('%c[MindMateManager] Initialized with Event Bus', 'color: #4caf50; font-weight: bold;');
            }
        } else {
            setTimeout(initMindMateManager, 50);
        }
    };
    
    // Wait for DOM
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initMindMateManager);
    } else {
        initMindMateManager();
    }
}

