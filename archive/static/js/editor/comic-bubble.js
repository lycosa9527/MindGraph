/**
 * Comic Bubble / Chat Window - Conversation interface for VoiceAgent
 * Displays streaming text responses and allows text input
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class ComicBubble {
    constructor() {
        // UI Elements
        this.chatWindow = null;
        this.messagesContainer = null;
        this.inputElement = null;
        this.sendButton = null;
        this.voiceButton = null;
        this.statusDot = null;
        
        // Legacy bubble (for quick responses)
        this.bubbleContainer = null;
        this.bubbleText = null;
        
        // State
        this.isWindowVisible = false;
        this.isBubbleVisible = false;
        this.messages = [];
        this.currentStreamingMessage = null;
        this.hideTimeout = null;
        this.isVoiceActive = false;
        
        // Callbacks
        this.onSendMessage = null;
        this.onVoiceToggle = null;
        
        this.logger = window.logger || console;
    }
    
    init(parentElement = document.body) {
        // Create chat window
        this._createChatWindow(parentElement);
        
        // Create legacy bubble for quick responses
        this._createBubble(parentElement);
        
        // Setup bubble event listeners (after bubble is created)
        this._setupBubbleEventListeners();
        
        this.logger.info('ComicBubble', 'Chat window initialized');
    }
    
    _createChatWindow(parentElement) {
        // Create main container
        this.chatWindow = document.createElement('div');
        this.chatWindow.className = 'chat-window';
        
        // Header
        const header = document.createElement('div');
        header.className = 'chat-header';
        header.innerHTML = `
            <div class="chat-header-title">
                <div class="status-dot"></div>
                <span>Omni Agent</span>
            </div>
            <div class="chat-header-actions">
                <button class="chat-header-btn minimize-btn" title="Minimize">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M19 9l-7 7-7-7"/>
                    </svg>
                </button>
                <button class="chat-header-btn close-btn" title="Close">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M18 6L6 18M6 6l12 12"/>
                    </svg>
                </button>
            </div>
        `;
        
        // Store status dot reference
        this.statusDot = header.querySelector('.status-dot');
        
        // Messages container
        this.messagesContainer = document.createElement('div');
        this.messagesContainer.className = 'chat-messages';
        
        // Input container
        const inputContainer = document.createElement('div');
        inputContainer.className = 'chat-input-container';
        inputContainer.innerHTML = `
            <div class="chat-input-wrapper">
                <textarea class="chat-input" placeholder="输入消息..." rows="1"></textarea>
                <button class="chat-voice-btn" title="语音输入">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                        <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                        <line x1="12" y1="19" x2="12" y2="23"/>
                        <line x1="8" y1="23" x2="16" y2="23"/>
                    </svg>
                </button>
                <button class="chat-send-btn" title="发送">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="22" y1="2" x2="11" y2="13"/>
                        <polygon points="22 2 15 22 11 13 2 9 22 2"/>
                    </svg>
                </button>
            </div>
        `;
        
        // Assemble
        this.chatWindow.appendChild(header);
        this.chatWindow.appendChild(this.messagesContainer);
        this.chatWindow.appendChild(inputContainer);
        parentElement.appendChild(this.chatWindow);
        
        // Get references - ensure elements exist before attaching listeners
        this.inputElement = inputContainer.querySelector('.chat-input');
        this.sendButton = inputContainer.querySelector('.chat-send-btn');
        this.voiceButton = inputContainer.querySelector('.chat-voice-btn');
        
        // Verify elements were found
        if (!this.inputElement) {
            this.logger.warn('ComicBubble', 'Chat input element not found');
        }
        if (!this.sendButton) {
            this.logger.warn('ComicBubble', 'Send button element not found');
        }
        if (!this.voiceButton) {
            this.logger.warn('ComicBubble', 'Voice button element not found');
        }
        
        // Event listeners - attach after elements are in DOM
        this._setupEventListeners(header);
    }
    
    _createBubble(parentElement) {
        // Create legacy bubble container
        this.bubbleContainer = document.createElement('div');
        this.bubbleContainer.className = 'comic-bubble';
        
        // Expand button
        const expandBtn = document.createElement('button');
        expandBtn.className = 'comic-bubble-expand';
        expandBtn.title = 'Open chat window';
        expandBtn.innerHTML = `
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>
            </svg>
        `;
        expandBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.showWindow();
        });
        
        // Text element
        this.bubbleText = document.createElement('div');
        this.bubbleText.className = 'comic-bubble-text';
        
        this.bubbleContainer.appendChild(expandBtn);
        this.bubbleContainer.appendChild(this.bubbleText);
        parentElement.appendChild(this.bubbleContainer);
    }
    
    _setupEventListeners(header) {
        // Minimize button
        const minimizeBtn = header?.querySelector('.minimize-btn');
        if (minimizeBtn) {
            minimizeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.hideWindow();
            });
        }
        
        // Close button
        const closeBtn = header?.querySelector('.close-btn');
        if (closeBtn) {
            closeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.hideWindow();
            });
        }
        
        // Send button - ensure it's clickable
        if (this.sendButton) {
            // Remove any existing listeners by cloning
            const newSendBtn = this.sendButton.cloneNode(true);
            this.sendButton.parentNode.replaceChild(newSendBtn, this.sendButton);
            this.sendButton = newSendBtn;
            
            this.sendButton.addEventListener('click', (e) => {
                e.stopPropagation();
                e.preventDefault();
                this.logger.debug('ComicBubble', 'Send button clicked');
                this._handleSend();
            });
            this.logger.debug('ComicBubble', 'Send button event listener attached');
        } else {
            this.logger.warn('ComicBubble', 'Send button not found when setting up listeners');
        }
        
        // Voice button - ensure it's clickable
        if (this.voiceButton) {
            // Remove any existing listeners by cloning
            const newVoiceBtn = this.voiceButton.cloneNode(true);
            this.voiceButton.parentNode.replaceChild(newVoiceBtn, this.voiceButton);
            this.voiceButton = newVoiceBtn;
            
            this.voiceButton.addEventListener('click', (e) => {
                e.stopPropagation();
                e.preventDefault();
                this.logger.debug('ComicBubble', 'Voice button clicked');
                this._handleVoiceToggle();
            });
            this.logger.debug('ComicBubble', 'Voice button event listener attached');
        } else {
            this.logger.warn('ComicBubble', 'Voice button not found when setting up listeners');
        }
        
        // Input handling - ensure it's interactive
        if (this.inputElement) {
            // Remove any existing listeners by cloning
            const newInput = this.inputElement.cloneNode(true);
            this.inputElement.parentNode.replaceChild(newInput, this.inputElement);
            this.inputElement = newInput;
            
            this.inputElement.addEventListener('keydown', (e) => {
                e.stopPropagation();
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.logger.debug('ComicBubble', 'Enter key pressed in input');
                    this._handleSend();
                }
            });
            
            // Auto-resize textarea
            this.inputElement.addEventListener('input', () => {
                this.inputElement.style.height = 'auto';
                this.inputElement.style.height = Math.min(this.inputElement.scrollHeight, 100) + 'px';
            });
            
            // Ensure input is focusable
            this.inputElement.addEventListener('click', (e) => {
                e.stopPropagation();
            });
            
            this.logger.debug('ComicBubble', 'Input element event listeners attached');
        } else {
            this.logger.warn('ComicBubble', 'Input element not found when setting up listeners');
        }
    }
    
    _setupBubbleEventListeners() {
        // Click on bubble to expand
        if (this.bubbleContainer) {
            this.bubbleContainer.addEventListener('click', () => {
                this.showWindow();
            });
        }
    }
    
    _handleSend() {
        const text = this.inputElement.value.trim();
        if (!text) return;
        
        // Add user message to display
        this.addMessage(text, 'user');
        
        // Clear input
        this.inputElement.value = '';
        this.inputElement.style.height = 'auto';
        
        // Show thinking indicator
        this.showThinking();
        
        // Trigger callback
        if (this.onSendMessage) {
            this.onSendMessage(text);
        } else {
            this.logger.warn('ComicBubble', 'No onSendMessage callback set');
        }
        
        this.logger.debug('ComicBubble', 'Message sent:', text);
    }
    
    _handleVoiceToggle() {
        this.isVoiceActive = !this.isVoiceActive;
        this.voiceButton.classList.toggle('active', this.isVoiceActive);
        
        if (this.onVoiceToggle) {
            this.onVoiceToggle(this.isVoiceActive);
        }
        
        this.logger.debug('ComicBubble', 'Voice toggle:', this.isVoiceActive);
    }
    
    /**
     * Show chat window
     */
    showWindow() {
        if (this.isWindowVisible) return;
        
        // Hide bubble if visible
        this.hideBubble();
        
        // Ensure chat window exists
        if (!this.chatWindow) {
            this.logger.error('ComicBubble', 'Cannot show window - chatWindow is null');
            return;
        }
        
        this.chatWindow.classList.add('visible');
        this.isWindowVisible = true;
        
        // Ensure elements are accessible and re-attach listeners if needed
        if (!this.inputElement || !this.sendButton || !this.voiceButton) {
            // Re-query elements in case they were lost
            const inputContainer = this.chatWindow.querySelector('.chat-input-container');
            if (inputContainer) {
                this.inputElement = inputContainer.querySelector('.chat-input');
                this.sendButton = inputContainer.querySelector('.chat-send-btn');
                this.voiceButton = inputContainer.querySelector('.chat-voice-btn');
                
                // Re-attach event listeners
                const header = this.chatWindow.querySelector('.chat-header');
                if (header) {
                    this._setupEventListeners(header);
                }
            }
        }
        
        // Focus input
        if (this.inputElement) {
            setTimeout(() => {
                if (this.inputElement) {
                    this.inputElement.focus();
                }
            }, 100);
        }
        
        // Scroll to bottom
        this._scrollToBottom();
        
        this.logger.debug('ComicBubble', 'Window shown', {
            hasInput: !!this.inputElement,
            hasSendButton: !!this.sendButton,
            hasVoiceButton: !!this.voiceButton
        });
    }
    
    /**
     * Hide chat window
     */
    hideWindow() {
        if (!this.isWindowVisible) return;
        
        this.chatWindow.classList.remove('visible');
        this.isWindowVisible = false;
        
        this.logger.debug('ComicBubble', 'Window hidden');
    }
    
    /**
     * Toggle chat window visibility
     */
    toggleWindow() {
        if (this.isWindowVisible) {
            this.hideWindow();
        } else {
            this.showWindow();
        }
    }
    
    /**
     * Show bubble with text (for quick responses)
     */
    showBubble() {
        if (this.isWindowVisible) return; // Don't show bubble if window is open
        if (this.isBubbleVisible) return;
        
        this.bubbleContainer.classList.add('visible');
        this.isBubbleVisible = true;
        
        this.logger.debug('ComicBubble', 'Bubble shown');
    }
    
    /**
     * Hide bubble
     */
    hideBubble() {
        if (!this.isBubbleVisible) return;
        
        this.bubbleContainer.classList.remove('visible');
        this.isBubbleVisible = false;
        
        this.logger.debug('ComicBubble', 'Bubble hidden');
    }
    
    /**
     * Add a message to the conversation
     */
    addMessage(text, role = 'agent', showTimestamp = true) {
        const message = {
            id: Date.now(),
            text: text,
            role: role, // 'agent' or 'user'
            timestamp: new Date()
        };
        
        this.messages.push(message);
        this._renderMessage(message, showTimestamp);
        this._scrollToBottom();
        
        return message;
    }
    
    /**
     * Start streaming a message (for agent responses)
     */
    startStreaming() {
        // Remove any existing thinking message
        this._removeThinkingMessage();
        
        // Create streaming message placeholder
        this.currentStreamingMessage = {
            id: Date.now(),
            text: '',
            role: 'agent',
            timestamp: new Date()
        };
        
        this.messages.push(this.currentStreamingMessage);
        
        const messageEl = document.createElement('div');
        messageEl.className = 'chat-message agent';
        messageEl.dataset.messageId = this.currentStreamingMessage.id;
        messageEl.innerHTML = `<span class="message-content"></span>`;
        
        this.messagesContainer.appendChild(messageEl);
        this._scrollToBottom();
        
        // Also update bubble
        this.bubbleText.textContent = '';
        
        return this.currentStreamingMessage;
    }
    
    /**
     * Append text to streaming message
     */
    appendText(chunk) {
        if (!chunk) return;
        
        // Update current streaming message
        if (this.currentStreamingMessage) {
            this.currentStreamingMessage.text += chunk;
            
            const messageEl = this.messagesContainer.querySelector(
                `[data-message-id="${this.currentStreamingMessage.id}"] .message-content`
            );
            if (messageEl) {
                messageEl.textContent = this.currentStreamingMessage.text;
            }
        }
        
        // Also update bubble text
        this.bubbleText.textContent = (this.bubbleText.textContent || '') + chunk;
        
        // Show bubble if window is not visible
        if (!this.isWindowVisible) {
            this.showBubble();
        }
        
        // Clear any pending hide timeout
        if (this.hideTimeout) {
            clearTimeout(this.hideTimeout);
            this.hideTimeout = null;
        }
        
        this._scrollToBottom();
    }
    
    /**
     * Finish streaming
     */
    finishStreaming() {
        if (this.currentStreamingMessage) {
            // Add timestamp
            const messageEl = this.messagesContainer.querySelector(
                `[data-message-id="${this.currentStreamingMessage.id}"]`
            );
            if (messageEl) {
                const timeEl = document.createElement('div');
                timeEl.className = 'chat-message-time';
                timeEl.textContent = this._formatTime(this.currentStreamingMessage.timestamp);
                messageEl.appendChild(timeEl);
            }
        }
        
        this.currentStreamingMessage = null;
    }
    
    /**
     * Show thinking indicator
     */
    showThinking() {
        this._removeThinkingMessage();
        
        const thinkingEl = document.createElement('div');
        thinkingEl.className = 'chat-message agent thinking';
        thinkingEl.dataset.thinking = 'true';
        thinkingEl.innerHTML = `
            <div class="thinking-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
        `;
        
        this.messagesContainer.appendChild(thinkingEl);
        this._scrollToBottom();
        
        // Also show in bubble
        this.bubbleText.textContent = '...';
        if (!this.isWindowVisible) {
            this.showBubble();
        }
        
        // Update status
        this.setStatus('thinking');
    }
    
    _removeThinkingMessage() {
        const thinkingEl = this.messagesContainer.querySelector('[data-thinking="true"]');
        if (thinkingEl) {
            thinkingEl.remove();
        }
    }
    
    _renderMessage(message, showTimestamp = true) {
        const messageEl = document.createElement('div');
        messageEl.className = `chat-message ${message.role}`;
        messageEl.dataset.messageId = message.id;
        
        let html = `<span class="message-content">${this._escapeHtml(message.text)}</span>`;
        
        if (showTimestamp) {
            html += `<div class="chat-message-time">${this._formatTime(message.timestamp)}</div>`;
        }
        
        messageEl.innerHTML = html;
        this.messagesContainer.appendChild(messageEl);
    }
    
    _scrollToBottom() {
        if (this.messagesContainer) {
            this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
        }
    }
    
    _formatTime(date) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    
    _escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    /**
     * Set status indicator
     */
    setStatus(status) {
        if (!this.statusDot) return;
        
        this.statusDot.className = 'status-dot';
        
        if (status === 'thinking') {
            this.statusDot.classList.add('thinking');
        } else if (status === 'error') {
            this.statusDot.classList.add('error');
        }
        // Default is active/green
    }
    
    /**
     * Set voice button active state
     */
    setVoiceActive(active) {
        this.isVoiceActive = active;
        if (this.voiceButton) {
            this.voiceButton.classList.toggle('active', active);
        }
    }
    
    /**
     * Auto-hide bubble after delay
     */
    autoHide(delay = 3000) {
        if (this.hideTimeout) {
            clearTimeout(this.hideTimeout);
        }
        
        this.hideTimeout = setTimeout(() => {
            this.hideBubble();
        }, delay);
    }
    
    /**
     * Clear all messages
     */
    clearMessages() {
        this.messages = [];
        this.messagesContainer.innerHTML = '';
        this.bubbleText.textContent = '';
        this.currentStreamingMessage = null;
    }
    
    /**
     * Legacy methods for backward compatibility
     */
    show() {
        this.showBubble();
    }
    
    hide() {
        this.hideBubble();
    }
    
    clear() {
        this.bubbleText.textContent = '';
    }
    
    setText(text) {
        this.bubbleText.textContent = text;
        if (!this.isWindowVisible) {
            this.showBubble();
        }
    }
    
    /**
     * Destroy and cleanup
     */
    destroy() {
        this.logger.debug('ComicBubble', 'Destroying - cleaning up modal and bubble');
        
        // Clear any pending timeouts
        if (this.hideTimeout) {
            clearTimeout(this.hideTimeout);
            this.hideTimeout = null;
        }
        
        // CRITICAL: Hide window and bubble FIRST before removing DOM elements
        // This ensures proper cleanup of visible state and CSS classes
        if (this.isWindowVisible) {
            this.hideWindow();
        }
        
        if (this.isBubbleVisible) {
            this.hideBubble();
        }
        
        // Clear all messages and reset streaming state
        // CRITICAL: Clear DOM content explicitly to ensure UI is reset
        if (this.messagesContainer) {
            this.messagesContainer.innerHTML = '';
        }
        if (this.bubbleText) {
            this.bubbleText.textContent = '';
        }
        this.currentStreamingMessage = null;
        this.messages = [];
        
        // Remove DOM elements
        if (this.chatWindow) {
            // Remove all event listeners by cloning (safety measure)
            const clone = this.chatWindow.cloneNode(false);
            if (this.chatWindow.parentNode) {
                this.chatWindow.parentNode.replaceChild(clone, this.chatWindow);
            }
            this.chatWindow = null;
        }
        
        if (this.bubbleContainer) {
            // Remove all event listeners by cloning (safety measure)
            const clone = this.bubbleContainer.cloneNode(false);
            if (this.bubbleContainer.parentNode) {
                this.bubbleContainer.parentNode.replaceChild(clone, this.bubbleContainer);
            }
            this.bubbleContainer = null;
        }
        
        // Reset all state flags
        this.isWindowVisible = false;
        this.isBubbleVisible = false;
        this.isVoiceActive = false;
        this.messagesContainer = null;
        this.inputElement = null;
        this.sendButton = null;
        this.voiceButton = null;
        this.statusDot = null;
        this.bubbleText = null;
        
        // Clear callbacks
        this.onSendMessage = null;
        this.onVoiceToggle = null;
        
        this.logger.info('ComicBubble', 'Destroyed - modal and bubble fully cleaned up');
    }
}

// Make available globally
window.ComicBubble = ComicBubble;

// Export for module usage (if needed)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ComicBubble;
}
