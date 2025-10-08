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
        this.currentStreamingMessage = null;
        this.messageBuffer = '';
        
        // Initialize Markdown renderer
        this.md = window.markdownit({
            html: false,
            linkify: true,
            breaks: true
        });
        
        this.initializeElements();
        this.bindEvents();
        
        console.log(`AI Assistant initialized for user: ${this.userId}`);
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
        
        // Debug: Log element status
        console.log('AI Assistant Elements:', {
            panel: !!this.panel,
            toggleBtn: !!this.toggleBtn,
            mindmateBtn: !!this.mindmateBtn,
            chatMessages: !!this.chatMessages,
            chatInput: !!this.chatInput,
            sendBtn: !!this.sendBtn
        });
        
        // Error checking
        if (!this.panel) {
            console.error('CRITICAL: AI Assistant panel (#ai-assistant-panel) not found in DOM!');
        }
        if (!this.mindmateBtn) {
            console.error('CRITICAL: MindMate AI button (#mindmate-ai-btn) not found in DOM!');
        }
    }
    
    /**
     * Bind event listeners
     */
    bindEvents() {
        // Close button in panel
        if (this.toggleBtn) {
            this.toggleBtn.addEventListener('click', (e) => {
                console.log('Close button clicked', e);
                e.preventDefault();
                e.stopPropagation();
                this.togglePanel();
            });
            console.log('Bound event to close button');
        }
        
        // MindMate AI button in toolbar
        if (this.mindmateBtn) {
            this.mindmateBtn.addEventListener('click', (e) => {
                console.log('MindMate AI button clicked', e);
                e.preventDefault();
                e.stopPropagation();
                this.togglePanel();
            });
            console.log('Bound event to MindMate AI button');
        } else {
            console.warn('MindMate AI button not found during initialization');
        }
        
        // Add test function to window for debugging
        window.testMindMatePanel = () => {
            console.log('Testing MindMate panel...');
            console.log('Panel element:', this.panel);
            console.log('Panel classes:', this.panel?.className);
            console.log('Button element:', this.mindmateBtn);
            this.togglePanel();
        };
        
        // Add method to manually open the panel
        window.openMindMatePanel = () => {
            console.log('Manually opening MindMate panel...');
            if (this.panel && this.panel.classList.contains('collapsed')) {
                this.togglePanel();
            } else {
                console.log('Panel is already open');
            }
        };
        
        // Add method to manually close the panel
        window.closeMindMatePanel = () => {
            console.log('Manually closing MindMate panel...');
            if (this.panel && !this.panel.classList.contains('collapsed')) {
                this.togglePanel();
            } else {
                console.log('Panel is already closed');
            }
        };
        
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
        console.log('Toggle panel called');
        console.log('Panel element:', this.panel);
        console.log('Panel display:', this.panel?.style.display);
        console.log('Panel className before toggle:', this.panel?.className);
        
        if (!this.panel) {
            console.error('AI Assistant panel not found!');
            const message = window.languageManager?.getNotification('aiPanelNotFound') 
                || 'AI Assistant panel not found. Please reload the page.';
            alert(message);
            return;
        }
        
        // Ensure the panel is visible (not display:none)
        if (this.panel.style.display === 'none') {
            this.panel.style.display = 'flex';
        }
        
        const isCollapsed = this.panel.classList.toggle('collapsed');
        console.log('Panel collapsed state after toggle:', isCollapsed);
        console.log('Panel className after toggle:', this.panel.className);
        
        // If opening AI panel, close property panel to prevent overlap
        if (!isCollapsed) {
            console.log('Opening AI panel');
            const propertyPanel = document.getElementById('property-panel');
            if (propertyPanel && propertyPanel.style.display !== 'none') {
                // Access toolbar manager through current editor to properly hide property panel
                if (window.currentEditor?.toolbarManager && typeof window.currentEditor.toolbarManager.hidePropertyPanel === 'function') {
                    window.currentEditor.toolbarManager.hidePropertyPanel();
                } else {
                    propertyPanel.style.display = 'none';
                }
            }
        } else {
            console.log('Closing AI panel');
        }
        
        // Update MindMate button state
        if (this.mindmateBtn) {
            if (isCollapsed) {
                this.mindmateBtn.classList.remove('active');
            } else {
                this.mindmateBtn.classList.add('active');
                // Focus input when opening
                if (this.chatInput) {
                    setTimeout(() => this.chatInput.focus(), 300);
                }
            }
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
     * Send message to AI assistant
     */
    async sendMessage() {
        const message = this.chatInput.value.trim();
        
        if (!message) {
            return;
        }
        
        // Add user message to chat
        this.addMessage('user', message);
        
        // Clear input
        this.chatInput.value = '';
        
        // Disable input during streaming
        this.setInputEnabled(false);
        
        // Show typing indicator
        const typingIndicator = this.showTypingIndicator();
        
        try {
            // Stream response from server
            await this.streamResponse(message);
            
        } catch (error) {
            console.error('Error sending message:', error);
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
            fetch('/api/ai_assistant/stream', {
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
                                    console.debug('Skipping malformed JSON:', line);
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
            console.error('AI Assistant error:', data.error);
            
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
            console.log('AI Assistant: Initializing via DOMContentLoaded');
            window.aiAssistant = new AIAssistantManager();
        });
    } else {
        // DOM is already loaded, initialize immediately
        console.log('AI Assistant: Initializing immediately (DOM already loaded)');
        window.aiAssistant = new AIAssistantManager();
    }
}

