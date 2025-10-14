/**
 * AI Assistant Manager - Handles Dify AI integration with SSE and Markdown
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 */

class AIAssistantManager {
    constructor() {
        this.userId = this.generateUserId();
        this.conversationId = null;
        this.diagramSessionId = null; // Track which diagram session this conversation belongs to
        this.currentStreamingMessage = null;
        this.messageBuffer = '';
        this.hasGreeted = false; // Track if we've sent initial greeting
        
        // Initialize Markdown renderer
        this.md = window.markdownit({
            html: false,
            linkify: true,
            breaks: true
        });
        
        this.initializeElements();
        this.bindEvents();
        
        logger.debug('AIAssistant', 'Initialized', { userId: this.userId });
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
        
        // Error checking
        if (!this.panel) {
            logger.error('AIAssistant', 'Panel element not found in DOM');
        }
        if (!this.mindmateBtn) {
            logger.error('AIAssistant', 'MindMate button not found in DOM');
        }
    }
    
    /**
     * Bind event listeners
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
        } else {
            logger.warn('AIAssistant', 'MindMate button not found during initialization');
        }
        
        // Add test function to window for debugging
        window.testMindMatePanel = () => {
            logger.debug('AIAssistant', 'Testing panel', {
                hasPanel: !!this.panel,
                classes: this.panel?.className
            });
            this.togglePanel();
        };
        
        // Add method to manually open the panel
        window.openMindMatePanel = () => {
            if (this.panel && this.panel.classList.contains('collapsed')) {
                this.togglePanel();
            }
        };
        
        // Panel control is now handled by centralized PanelManager (panel-manager.js)
        
        // Send message
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
     * Toggle AI assistant panel
     */
    togglePanel() {
        logger.info('AIAssistant', '🟢 togglePanel() called - STARTING PANEL TOGGLE');
        
        if (!this.panel) {
            logger.error('AIAssistant', '❌ Panel not found');
            const message = window.languageManager?.getNotification('aiPanelNotFound') 
                || 'AI Assistant panel not found. Please reload the page.';
            alert(message);
            return;
        }
        
        // Log current state of BOTH panels
        const thinkPanel = document.getElementById('thinking-panel');
        const aiPanel = document.getElementById('ai-assistant-panel');
        
        logger.info('AIAssistant', 'Panel state BEFORE toggle:', {
            aiPanelId: aiPanel?.id || 'NOT_FOUND',
            aiPanelCollapsed: aiPanel?.classList.contains('collapsed'),
            thinkPanelId: thinkPanel?.id || 'NOT_FOUND',
            thinkPanelCollapsed: thinkPanel?.classList.contains('collapsed'),
            currentPanelManager: window.panelManager?.getCurrentPanel()
        });
        
        // Ensure the panel is visible (not display:none)
        if (this.panel.style.display === 'none') {
            this.panel.style.display = 'flex';
        }
        
        // Check current state BEFORE any DOM manipulation
        const isCurrentlyClosed = this.panel.classList.contains('collapsed');
        
        logger.info('AIAssistant', 'Panel state', {
            isCurrentlyClosed,
            willOpen: isCurrentlyClosed,
            willClose: !isCurrentlyClosed
        });
        
        // Use PanelManager with EXPLICIT methods - it will manage all panels
        if (window.panelManager) {
            if (isCurrentlyClosed) {
                // Open this panel (PanelManager will close others)
                logger.info('AIAssistant', '🎯 Calling panelManager.openMindMatePanel() - EXPLICIT METHOD');
                
                // Check if we're opening for a new diagram session
                const currentDiagramSessionId = window.currentEditor?.sessionId;
                const isNewDiagramSession = !this.diagramSessionId || this.diagramSessionId !== currentDiagramSessionId;
                
                if (isNewDiagramSession) {
                    logger.info('AIAssistant', 'New diagram session detected - starting new conversation', {
                        oldSession: this.diagramSessionId,
                        newSession: currentDiagramSessionId
                    });
                    
                    // Reset conversation for new diagram
                    this.diagramSessionId = currentDiagramSessionId;
                    this.conversationId = null;
                    this.hasGreeted = false;
                    this.chatMessages.innerHTML = ''; // Clear old messages
                } else {
                    logger.info('AIAssistant', 'Resuming existing conversation', {
                        diagramSession: this.diagramSessionId,
                        conversationId: this.conversationId
                    });
                }
                
                const success = window.panelManager.openMindMatePanel();
                logger.info('AIAssistant', 'openMindMatePanel result:', success);
                
                // Trigger Dify's conversation opener for new sessions
                if (!this.hasGreeted) {
                    this.hasGreeted = true;
                    logger.debug('AIAssistant', 'Triggering Dify conversation opener');
                    
                    // Send empty message to trigger Dify's conversation opener
                    // Dify will respond with its configured opening message
                    setTimeout(() => {
                        this.sendConversationOpener();
                    }, 300);
                }
            } else {
                // Close this panel
                logger.info('AIAssistant', '🎯 Calling panelManager.closeMindMatePanel() - EXPLICIT METHOD');
                window.panelManager.closeMindMatePanel();
            }
        } else {
            // Fallback if PanelManager not available
            logger.warn('AIAssistant', '⚠️ PanelManager not available, using fallback');
            this.panel.classList.toggle('collapsed');
            if (this.mindmateBtn) {
                this.mindmateBtn.classList.toggle('active');
            }
        }
        
        // Brief delay to let DOM update
        setTimeout(() => {
            logger.info('AIAssistant', 'Panel state AFTER toggle:', {
                aiPanelId: aiPanel?.id || 'NOT_FOUND',
                aiPanelCollapsed: aiPanel?.classList.contains('collapsed'),
                aiPanelClasses: aiPanel?.className || 'N/A',
                thinkPanelId: thinkPanel?.id || 'NOT_FOUND',
                thinkPanelCollapsed: thinkPanel?.classList.contains('collapsed'),
                thinkPanelClasses: thinkPanel?.className || 'N/A',
                currentPanelManager: window.panelManager?.getCurrentPanel()
            });
            logger.info('AIAssistant', '✅ Panel toggle sequence completed');
        }, 100);
        
        // Focus input when opening (delay to let greeting finish)
        if (isCurrentlyClosed && this.chatInput) {
            setTimeout(() => this.chatInput.focus(), 800);
        }
        
        // Trigger canvas resize to accommodate AI panel
        setTimeout(() => {
            if (window.currentEditor && typeof window.currentEditor.fitDiagramToWindow === 'function') {
                window.currentEditor.fitDiagramToWindow();
            }
        }, 450); // Wait for CSS transition (400ms) + buffer
    }
    
    /**
     * Auto-resize textarea based on content
     */
    autoResizeTextarea() {
        if (!this.chatInput) return;
        
        this.chatInput.style.height = 'auto';
        this.chatInput.style.height = Math.min(this.chatInput.scrollHeight, 120) + 'px';
    }
    
    /**
     * Trigger Dify's conversation opener for new conversations
     * 
     * IMPLEMENTATION NOTE:
     * Dify API requires a non-empty `query` field per API specification.
     * We send a minimal trigger message that:
     * - Satisfies Dify's API requirement (non-empty query)
     * - Is hidden from user (showUserMessage=false)
     * - Triggers Dify's configured conversation opener feature
     * - Dify responds with your custom welcome message configured in admin
     * 
     * Why not empty string?
     * - Dify API rejects empty query: "query is required"
     * - This is an API constraint, not a design choice
     * 
     * @see https://docs.dify.ai/guides/application-publishing/launch-app
     */
    async sendConversationOpener() {
        if (!this.chatMessages) return;
        
        logger.debug('AIAssistant', 'Triggering Dify conversation opener');
        
        try {
            // Dify API constant - minimal trigger for conversation opener
            const DIFY_OPENER_TRIGGER = 'start';
            
            await this.sendMessageToDify(DIFY_OPENER_TRIGGER, false);
            logger.info('AIAssistant', 'Dify conversation opener triggered successfully');
        } catch (error) {
            logger.error('AIAssistant', 'Failed to trigger conversation opener:', error);
            
            // Fallback: Show static welcome if Dify opener fails
            this.showFallbackWelcome();
        }
    }
    
    /**
     * Fallback static welcome message if Dify opener fails
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
        
        logger.warn('AIAssistant', 'Showing fallback welcome (Dify opener failed)');
    }
    
    /**
     * Detect language from current diagram
     */
    detectLanguage() {
        const editor = window.currentEditor;
        if (!editor) return 'zh'; // default to Chinese
        
        try {
            const diagramData = editor.exportToJSON?.();
            const centerText = diagramData?.center?.text || diagramData?.topic || '';
            
            // Simple Chinese character detection
            const chineseChars = (centerText.match(/[\u4e00-\u9fff]/g) || []).length;
            return chineseChars > centerText.length * 0.3 ? 'zh' : 'en';
        } catch (error) {
            logger.warn('AIAssistant', 'Failed to detect language, defaulting to zh', error);
            return 'zh';
        }
    }
    
    
    /**
     * Send message to AI assistant
     */
    async sendMessage() {
        const message = this.chatInput.value.trim();
        
        if (!message) {
            return;
        }
        
        // Clear input
        this.chatInput.value = '';
        
        // Send to Dify with UI display
        await this.sendMessageToDify(message, true);
    }
    
    /**
     * Send message to Dify API
     * @param {string} message - The message to send
     * @param {boolean} showUserMessage - Whether to display the user's message in chat
     */
    async sendMessageToDify(message, showUserMessage = true) {
        // Add user message to chat (if not invisible)
        if (showUserMessage) {
            this.addMessage('user', message);
        }
        
        // Disable input during streaming
        this.setInputEnabled(false);
        
        // Show typing indicator
        const typingIndicator = this.showTypingIndicator();
        
        try {
            // Stream response from server
            await this.streamResponse(message);
            
        } catch (error) {
            logger.error('AIAssistant', 'Failed to send message', error);
            this.addMessage('assistant', 'Sorry, I encountered an error. Please try again.');
        } finally {
            // Remove typing indicator
            if (typingIndicator && typingIndicator.parentNode) {
                typingIndicator.parentNode.removeChild(typingIndicator);
            }
            
            // Re-enable input
            this.setInputEnabled(true);
        }
    }
    
    /**
     * Stream response from server using SSE
     */
    async streamResponse(message) {
        return new Promise((resolve, reject) => {
            // Prepare streaming message container
            this.messageBuffer = '';
            this.currentStreamingMessage = this.createMessageElement('assistant', '');
            this.chatMessages.appendChild(this.currentStreamingMessage);
            this.currentStreamingMessage.classList.add('streaming');
            
            // Create request payload
            const payload = {
                message: message,
                user_id: this.userId,
                conversation_id: this.conversationId
            };
            
            // Use fetch with SSE-like reading
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
                
                const readChunk = () => {
                    reader.read().then(({ done, value }) => {
                        if (done) {
                            // Stream ended
                            if (this.currentStreamingMessage) {
                                this.currentStreamingMessage.classList.remove('streaming');
                            }
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
                                } catch (e) {
                                    logger.debug('AIAssistant', 'Skipping malformed JSON in stream');
                                }
                            }
                        }
                        
                        // Continue reading
                        readChunk();
                    }).catch(reject);
                };
                
                readChunk();
            })
            .catch(reject);
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
            logger.error('AIAssistant', 'Stream error', { error: data.error });
            
            if (this.currentStreamingMessage && this.currentStreamingMessage.parentNode) {
                this.currentStreamingMessage.parentNode.removeChild(this.currentStreamingMessage);
            }
            
            this.addMessage('assistant', `Error: ${data.error}`);
            this.messageBuffer = '';
            this.currentStreamingMessage = null;
        }
    }
    
    /**
     * Update streaming message content
     */
    updateStreamingMessage(text) {
        if (!this.currentStreamingMessage) {
            return;
        }
        
        const contentDiv = this.currentStreamingMessage.querySelector('.ai-message-content');
        if (contentDiv) {
            // Render markdown and sanitize
            const html = this.md.render(text);
            contentDiv.innerHTML = DOMPurify.sanitize(html);
            
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
        
        if (content) {
            // Render markdown and sanitize
            const html = this.md.render(content);
            contentDiv.innerHTML = DOMPurify.sanitize(html);
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

// Initialize AI Assistant when DOM is ready
if (typeof window !== 'undefined') {
    // Check if DOM is already loaded
    if (document.readyState === 'loading') {
        // DOM is still loading, wait for DOMContentLoaded
        document.addEventListener('DOMContentLoaded', () => {
            logger.debug('AIAssistant', 'Initializing via DOMContentLoaded');
            window.aiAssistant = new AIAssistantManager();
        });
    } else {
        // DOM is already loaded, initialize immediately
        logger.debug('AIAssistant', 'Initializing (DOM already loaded)');
        window.aiAssistant = new AIAssistantManager();
    }
}

