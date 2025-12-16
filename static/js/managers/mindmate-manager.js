/**
 * MindMate Manager (Event Bus Version)
 * =====================================
 * 
 * Manages MindMate AI assistant with Event Bus architecture.
 * Already uses correct SSE pattern (recursive promise chain) ✅
 * This version adds Event Bus integration for decoupled communication.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class MindMateManager {
    constructor(eventBus, stateManager, logger) {
        this.eventBus = eventBus;
        this.stateManager = stateManager;
        // Ensure logger is always available - use global logger as fallback
        this.logger = logger || window.logger || console;
        
        // NEW: Add owner identifier for Event Bus Listener Registry
        this.ownerId = 'MindMateManager';
        
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
        
        // Store callback references for proper cleanup
        this.callbacks = {
            panelOpen: (data) => {
                if (data.panel === 'mindmate') {
                    this.openPanel();
                }
            },
            panelClose: (data) => {
                if (data.panel === 'mindmate') {
                    this.closePanel();
                }
            },
            sendMessage: (data) => {
                if (data.message) {
                    this.chatInput.value = data.message;
                    this.sendMessage(data.message);
                }
            }
        };
        
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
        // Listen for panel open requests - use stored callback
        this.eventBus.onWithOwner('panel:open_requested', this.callbacks.panelOpen, this.ownerId);
        
        // Listen for panel close requests - use stored callback
        this.eventBus.onWithOwner('panel:close_requested', this.callbacks.panelClose, this.ownerId);
        
        // Listen for message send requests (from voice agent) - use stored callback
        this.eventBus.onWithOwner('mindmate:send_message', this.callbacks.sendMessage, this.ownerId);
        
        this.logger.debug('MindMateManager', 'Event listeners registered');
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
        
        // Mobile: Lock body scroll to prevent page shift
        if (window.innerWidth <= 768) {
            document.body.style.overflow = 'hidden';
            document.body.style.position = 'fixed';
            document.body.style.width = '100%';
            document.body.style.top = `-${window.scrollY}px`;
        }
        
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
            // Use Event Bus to request fit via ViewManager
            if (window.eventBus) {
                window.eventBus.emit('view:fit_diagram_requested');
            } else if (window.currentEditor && typeof window.currentEditor.fitDiagramToWindow === 'function') {
                // Fallback for backward compatibility
                window.currentEditor.fitDiagramToWindow();
            }
        }, 450);
        
        // Emit event
        this.eventBus.emit('mindmate:opened', { diagramSessionId: this.diagramSessionId });
    }
    
    /**
     * Close MindMate panel
     * 
     * @param {Object} options - Options for closing
     * @param {boolean} options._internal - If true, called from PanelManager (skip PanelManager call)
     */
    closePanel(options = {}) {
        // Check if destroyed (eventBus is null after destroy)
        if (!this.eventBus) {
            // Already destroyed, ignore
            return;
        }
        
        if (!this.panel) return;
        
        // Check if already closed (prevent duplicate operations)
        if (this.panel.classList.contains('collapsed')) {
            this.logger.debug('MindMateManager', 'Panel already closed, skipping');
            return;
        }
        
        const source = options._internal ? 'panel_manager' : 'user';
        this.logger.info('MindMateManager', 'Closing panel', { source });
        
        // Mobile: Unlock body scroll
        if (window.innerWidth <= 768) {
            const scrollY = document.body.style.top;
            document.body.style.overflow = '';
            document.body.style.position = '';
            document.body.style.width = '';
            document.body.style.top = '';
            window.scrollTo(0, parseInt(scrollY || '0') * -1);
        }
        
        // If called from PanelManager, just do internal cleanup
        // Otherwise, ask PanelManager to close (which will call us back with _internal flag)
        if (options._internal) {
            // Internal call from PanelManager - just cleanup internal state
            // PanelManager will handle DOM and state updates
            // Do any manager-specific cleanup here if needed
            // No need to call PanelManager - it's already handling the close
            
        } else {
            // User-initiated close - delegate to PanelManager
            // PanelManager will call this method again with _internal: true
            // to allow us to do cleanup, but we prevent that double-call with the check above
            if (window.panelManager) {
                window.panelManager.closeMindMatePanel();
            } else {
                // Fallback if PanelManager not available
                this.panel.classList.add('collapsed');
                if (this.mindmateBtn) {
                    this.mindmateBtn.classList.remove('active');
                }
                // Emit event for fallback case
                this.eventBus.emit('mindmate:closed', {});
            }
            return; // Exit early - PanelManager will handle the rest
        }
        
        // Only emit event if this was an internal call (PanelManager-initiated)
        // User-initiated closes are handled above
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
            const errorMsg = error?.message || String(error) || 'Unknown error';
            const isAuthError = error?.status === 401 || errorMsg.includes('401');
            this.logger.error('MindMateManager', `Failed to trigger conversation opener: ${errorMsg}`, {
                error: errorMsg,
                stack: error?.stack,
                status: error?.status,
                isAuthError
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
                            if (this.eventBus) {
                                this.eventBus.emit('mindmate:message_completed', {
                                    conversationId: this.conversationId
                                });
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
                        const errorMsg = error?.message || String(error) || 'Unknown stream error';
                        const isNetworkError = error?.name === 'NetworkError' || error?.name === 'TypeError';
                        const isAuthError = error?.status === 401 || errorMsg.includes('401');
                        
                        this.logger.error('MindMateManager', `Stream error: ${errorMsg}`, {
                            error: errorMsg,
                            stack: error?.stack,
                            name: error?.name,
                            status: error?.status,
                            isNetworkError,
                            isAuthError
                        });
                        
                        // Remove typing indicator (immediately on error)
                        typingIndicatorRemoved = true;
                        if (typingIndicator && typingIndicator.parentNode) {
                            typingIndicator.parentNode.removeChild(typingIndicator);
                        }
                        
                        // Re-enable input
                        this.setInputEnabled(true);
                        
                        // Emit error event with detailed context
                        if (this.eventBus) {
                            this.eventBus.emit('mindmate:error', { 
                                error: errorMsg,
                                isNetworkError,
                                isAuthError
                            });
                        }
                        
                        reject(error);
                    });
                };
                
                readChunk(); // Start recursive chain
            })
            .catch(error => {
                const errorMsg = error?.message || String(error) || 'Unknown fetch error';
                const isNetworkError = error?.name === 'NetworkError' || error?.name === 'TypeError';
                const isAuthError = error?.status === 401 || errorMsg.includes('401');
                
                this.logger.error('MindMateManager', `Fetch error: ${errorMsg}`, {
                    error: errorMsg,
                    stack: error?.stack,
                    name: error?.name,
                    status: error?.status,
                    isNetworkError,
                    isAuthError
                });
                
                // Remove typing indicator (immediately on error)
                typingIndicatorRemoved = true;
                if (typingIndicator && typingIndicator.parentNode) {
                    typingIndicator.parentNode.removeChild(typingIndicator);
                }
                
                // Re-enable input
                this.setInputEnabled(true);
                
                // Emit error event
                if (this.eventBus) {
                    this.eventBus.emit('mindmate:error', { error: error.message });
                }
                
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
                if (this.eventBus) {
                    this.eventBus.emit('mindmate:message_chunk', { chunk: content });
                }
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
            // Handle error with error_type for user-friendly messages
            const errorType = data.error_type || 'unknown';
            const errorMessage = data.message || data.error || 'An error occurred';
            
            const errorMsg = data.error || 'Unknown stream error';
            const isNetworkError = errorType === 'network' || errorMsg.includes('network');
            const isAuthError = errorMsg.includes('401') || errorMsg.includes('Unauthorized');
            
            this.logger.error('MindMateManager', `Stream error: ${errorMsg}`, { 
                error: errorMsg,
                error_type: errorType,
                isNetworkError,
                isAuthError
            });
            
            if (this.currentStreamingMessage && this.currentStreamingMessage.parentNode) {
                this.currentStreamingMessage.parentNode.removeChild(this.currentStreamingMessage);
            }
            
            // Use localized message from backend if available, otherwise fallback
            this.addMessage('assistant', errorMessage);
            this.messageBuffer = '';
            this.currentStreamingMessage = null;
            
            // Emit error event with error_type
            if (this.eventBus) {
                this.eventBus.emit('mindmate:stream_error', { 
                    error: data.error,
                    error_type: errorType,
                    message: errorMessage
                });
            }
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
            
            // Enhance images after rendering
            this.enhanceImages(contentDiv);
            
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
            
            // Enhance images after rendering
            this.enhanceImages(contentDiv);
        } else {
            contentDiv.textContent = content;
        }
        
        messageDiv.appendChild(contentDiv);
        return messageDiv;
    }
    
    /**
     * Get translated text for save button
     */
    getSaveButtonText() {
        const language = this.detectLanguage();
        return language === 'zh' ? '保存图片' : 'Save';
    }
    
    /**
     * Enhance images with click-to-enlarge and save functionality
     */
    enhanceImages(container) {
        if (!container) return;
        
        const images = container.querySelectorAll('img');
        const saveText = this.getSaveButtonText();
        
        images.forEach(img => {
            // Skip if already enhanced
            if (img.dataset.enhanced === 'true') return;
            
            // Mark as enhanced
            img.dataset.enhanced = 'true';
            
            // Wrap image in container
            const wrapper = document.createElement('div');
            wrapper.className = 'image-container';
            img.parentNode.insertBefore(wrapper, img);
            wrapper.appendChild(img);
            
            // Add save button
            const saveBtn = document.createElement('button');
            saveBtn.className = 'image-save-btn';
            saveBtn.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg> ${saveText}`;
            saveBtn.onclick = (e) => {
                e.stopPropagation();
                this.saveImage(img.src);
            };
            wrapper.appendChild(saveBtn);
            
            // Add click handler to enlarge
            img.style.cursor = 'pointer';
            img.onclick = () => {
                this.showImageLightbox(img.src);
            };
        });
    }
    
    /**
     * Show image in lightbox modal
     */
    showImageLightbox(imageSrc) {
        // Create or get lightbox
        let lightbox = document.getElementById('image-lightbox');
        if (!lightbox) {
            lightbox = document.createElement('div');
            lightbox.id = 'image-lightbox';
            lightbox.className = 'image-lightbox';
            
            const content = document.createElement('div');
            content.className = 'image-lightbox-content';
            
            const img = document.createElement('img');
            img.src = '';
            content.appendChild(img);
            
            const closeBtn = document.createElement('span');
            closeBtn.className = 'image-lightbox-close';
            closeBtn.innerHTML = '&times;';
            closeBtn.onclick = () => {
                lightbox.classList.remove('active');
            };
            content.appendChild(closeBtn);
            
            const saveBtn = document.createElement('button');
            saveBtn.className = 'image-lightbox-save';
            const saveText = this.getSaveButtonText();
            const saveImageText = this.detectLanguage() === 'zh' ? '保存图片' : 'Save Image';
            saveBtn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg> ${saveImageText}`;
            saveBtn.onclick = () => {
                this.saveImage(imageSrc);
            };
            content.appendChild(saveBtn);
            
            lightbox.appendChild(content);
            document.body.appendChild(lightbox);
            
            // Close on background click
            lightbox.onclick = (e) => {
                if (e.target === lightbox) {
                    lightbox.classList.remove('active');
                }
            };
            
            // Close on Escape key
            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && lightbox.classList.contains('active')) {
                    lightbox.classList.remove('active');
                }
            });
        }
        
        // Update image source
        const img = lightbox.querySelector('.image-lightbox-content img');
        if (img) {
            img.src = imageSrc;
        }
        
        // Update save button text and handler
        const saveBtn = lightbox.querySelector('.image-lightbox-save');
        if (saveBtn) {
            const saveImageText = this.detectLanguage() === 'zh' ? '保存图片' : 'Save Image';
            saveBtn.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg> ${saveImageText}`;
            saveBtn.onclick = () => {
                this.saveImage(imageSrc);
            };
        }
        
        // Show lightbox
        lightbox.classList.add('active');
    }
    
    /**
     * Save image to downloads
     */
    async saveImage(imageSrc) {
        try {
            // For same-origin images or CORS-enabled images, try to download directly
            if (imageSrc.startsWith('blob:') || imageSrc.startsWith('data:')) {
                // Blob or data URL - can download directly
                const link = document.createElement('a');
                link.href = imageSrc;
                link.download = `mindmate-image-${Date.now()}.png`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                this.logger.debug('MindMateManager', 'Image saved (blob/data)', { src: imageSrc });
                return;
            }
            
            // For external images, try to fetch and convert to blob
            try {
                const response = await fetch(imageSrc, { mode: 'cors' });
                if (!response.ok) throw new Error('Failed to fetch image');
                
                const blob = await response.blob();
                const blobUrl = URL.createObjectURL(blob);
                
                const link = document.createElement('a');
                link.href = blobUrl;
                link.download = `mindmate-image-${Date.now()}.png`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                
                // Clean up blob URL after a delay
                setTimeout(() => URL.revokeObjectURL(blobUrl), 100);
                
                this.logger.debug('MindMateManager', 'Image saved (fetched)', { src: imageSrc });
            } catch (fetchError) {
                // If fetch fails (CORS issue), fallback to opening in new tab
                this.logger.debug('MindMateManager', 'CORS blocked, opening in new tab', { src: imageSrc });
                window.open(imageSrc, '_blank');
            }
        } catch (error) {
            this.logger.error('MindMateManager', 'Failed to save image', {
                error: error.message || String(error),
                src: imageSrc
            });
            
            // Final fallback: open in new tab
            window.open(imageSrc, '_blank');
        }
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
    
    /**
     * Clean up resources
     */
    destroy() {
        this.logger.debug('MindMateManager', 'Destroying');
        
        // Remove all Event Bus listeners (using Listener Registry)
        if (this.eventBus && this.ownerId) {
            const removedCount = this.eventBus.removeAllListenersForOwner(this.ownerId);
            if (removedCount > 0) {
                this.logger.debug('MindMateManager', `Removed ${removedCount} Event Bus listeners`);
            }
        }
        
        // Clear session data
        this.conversationId = null;
        this.diagramSessionId = null;
        this.hasGreeted = false;
        
        // Nullify references (but keep logger for potential error logging)
        this.callbacks = null;
        this.eventBus = null;
        this.stateManager = null;
        this.chatPanel = null;
        this.chatMessages = null;
        this.chatInput = null;
        this.chatSendBtn = null;
        this.md = null;
        // Don't nullify logger - methods may still be called and need to log errors
        // this.logger = null;
    }
}

// NOTE: No longer auto-initialized globally.
// Now created per-session in DiagramSelector and managed by SessionLifecycleManager.

