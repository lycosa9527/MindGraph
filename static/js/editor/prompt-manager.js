/**
 * PromptManager - Handles AI prompt input and history
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 */

class PromptManager {
    constructor() {
        this.maxHistory = 10;
        this.history = this.loadHistory();
        this.isHistoryOpen = false;
        
        this.initializeElements();
        this.initializeEventListeners();
        this.renderHistory();
    }
    
    /**
     * Initialize DOM elements
     */
    initializeElements() {
        this.promptInput = document.getElementById('prompt-input');
        this.sendBtn = document.getElementById('prompt-send-btn');
        this.historyToggle = document.getElementById('history-toggle');
        this.historyDropdown = document.getElementById('prompt-history');
        this.historyList = document.getElementById('prompt-history-list');
        this.clearHistoryBtn = document.getElementById('clear-history-btn');
        this.emptyHistoryMsg = document.getElementById('history-empty');
    }
    
    /**
     * Initialize event listeners
     */
    initializeEventListeners() {
        // Send button click
        if (this.sendBtn) {
            this.sendBtn.addEventListener('click', () => this.handleSend());
        }
        
        // Enter key to send
        if (this.promptInput) {
            this.promptInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.handleSend();
                }
            });
            
            // Update send button state on input
            this.promptInput.addEventListener('input', () => {
                this.updateSendButtonState();
            });
        }
        
        // History toggle
        if (this.historyToggle) {
            this.historyToggle.addEventListener('click', () => {
                this.toggleHistory();
            });
        }
        
        // Clear history
        if (this.clearHistoryBtn) {
            this.clearHistoryBtn.addEventListener('click', () => {
                this.clearHistory();
            });
        }
        
        // Close history when clicking outside
        document.addEventListener('click', (e) => {
            if (this.isHistoryOpen && 
                !this.historyToggle.contains(e.target) && 
                !this.historyDropdown.contains(e.target)) {
                this.closeHistory();
            }
        });
    }
    
    /**
     * Handle send action
     */
    handleSend() {
        const prompt = this.promptInput.value.trim();
        
        if (!prompt) {
            return;
        }
        
        // Add to history
        this.addToHistory(prompt);
        
        // TODO: Send to AI generation endpoint
        console.log('Sending prompt to AI:', prompt);
        
        // Show notification
        this.showNotification(
            window.languageManager?.currentLanguage === 'zh' 
                ? '正在生成图表...' 
                : 'Generating diagram...',
            'info'
        );
        
        // Clear input
        this.promptInput.value = '';
        this.updateSendButtonState();
        
        // Close history if open
        this.closeHistory();
        
        // TODO: Redirect to AI generation or show result
        // For now, just log
        alert('AI generation feature coming soon!\n\nYour prompt: ' + prompt);
    }
    
    /**
     * Add prompt to history
     */
    addToHistory(prompt) {
        // Remove if already exists
        this.history = this.history.filter(item => item !== prompt);
        
        // Add to beginning
        this.history.unshift(prompt);
        
        // Limit to max history
        if (this.history.length > this.maxHistory) {
            this.history = this.history.slice(0, this.maxHistory);
        }
        
        // Save and render
        this.saveHistory();
        this.renderHistory();
    }
    
    /**
     * Toggle history dropdown
     */
    toggleHistory() {
        if (this.isHistoryOpen) {
            this.closeHistory();
        } else {
            this.openHistory();
        }
    }
    
    /**
     * Open history dropdown
     */
    openHistory() {
        this.historyDropdown.style.display = 'block';
        this.historyToggle.classList.add('active');
        this.isHistoryOpen = true;
    }
    
    /**
     * Close history dropdown
     */
    closeHistory() {
        this.historyDropdown.style.display = 'none';
        this.historyToggle.classList.remove('active');
        this.isHistoryOpen = false;
    }
    
    /**
     * Render history list
     */
    renderHistory() {
        if (this.history.length === 0) {
            this.emptyHistoryMsg.style.display = 'block';
            // Clear any existing items
            const items = this.historyList.querySelectorAll('.prompt-history-item');
            items.forEach(item => item.remove());
            return;
        }
        
        this.emptyHistoryMsg.style.display = 'none';
        
        // Clear existing items
        const items = this.historyList.querySelectorAll('.prompt-history-item');
        items.forEach(item => item.remove());
        
        // Render each history item
        this.history.forEach((prompt, index) => {
            const item = document.createElement('div');
            item.className = 'prompt-history-item';
            
            item.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <polyline points="12 6 12 12 16 14"></polyline>
                </svg>
                <span class="prompt-history-item-text">${this.escapeHtml(prompt)}</span>
            `;
            
            item.addEventListener('click', () => {
                this.promptInput.value = prompt;
                this.closeHistory();
                this.promptInput.focus();
                this.updateSendButtonState();
            });
            
            this.historyList.appendChild(item);
        });
    }
    
    /**
     * Clear history
     */
    clearHistory() {
        const confirmMessage = window.languageManager?.currentLanguage === 'zh'
            ? '确定要清除所有历史记录吗？'
            : 'Clear all history?';
            
        if (confirm(confirmMessage)) {
            this.history = [];
            this.saveHistory();
            this.renderHistory();
        }
    }
    
    /**
     * Update send button state
     */
    updateSendButtonState() {
        const hasText = this.promptInput.value.trim().length > 0;
        this.sendBtn.disabled = !hasText;
    }
    
    /**
     * Load history from localStorage
     */
    loadHistory() {
        try {
            const saved = localStorage.getItem('mindgraph_prompt_history');
            return saved ? JSON.parse(saved) : [];
        } catch (e) {
            return [];
        }
    }
    
    /**
     * Save history to localStorage
     */
    saveHistory() {
        try {
            localStorage.setItem('mindgraph_prompt_history', JSON.stringify(this.history));
        } catch (e) {
            console.error('Failed to save history:', e);
        }
    }
    
    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        
        // Style the notification
        notification.style.position = 'fixed';
        notification.style.top = '80px';
        notification.style.right = '20px';
        notification.style.padding = '12px 24px';
        notification.style.borderRadius = '8px';
        notification.style.backgroundColor = type === 'success' ? '#4CAF50' : '#2196F3';
        notification.style.color = 'white';
        notification.style.fontWeight = '600';
        notification.style.fontSize = '14px';
        notification.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.2)';
        notification.style.zIndex = '10001';
        notification.style.opacity = '0';
        notification.style.transition = 'opacity 0.3s ease';
        
        document.body.appendChild(notification);
        
        // Fade in
        setTimeout(() => {
            notification.style.opacity = '1';
        }, 10);
        
        // Fade out and remove
        setTimeout(() => {
            notification.style.opacity = '0';
            setTimeout(() => {
                document.body.removeChild(notification);
            }, 300);
        }, 3000);
    }
}

// Initialize when DOM is ready
if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', () => {
        window.promptManager = new PromptManager();
    });
}

