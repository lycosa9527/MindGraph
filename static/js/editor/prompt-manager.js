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
    async handleSend() {
        const prompt = this.promptInput.value.trim();
        
        if (!prompt) {
            return;
        }
        
        // Add to history
        this.addToHistory(prompt);
        
        // Disable send button
        this.sendBtn.disabled = true;
        
        // Show loading spinner
        this.showLoadingSpinner();
        
        try {
            // Get current language
            const language = window.languageManager?.currentLanguage || 'en';
            
            // Send to AI generation endpoint
            const response = await auth.fetch('/api/generate_graph', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    prompt: prompt,
                    language: language
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Check for errors in response
            if (data.error) {
                throw new Error(data.error);
            }
            
            // Clear input
            this.promptInput.value = '';
            this.updateSendButtonState();
            
            // Close history if open
            this.closeHistory();
            
            // Transition to editor with generated diagram
            this.transitionToEditorWithDiagram(data);
            
            // Hide loading spinner (will be hidden by transition anyway)
            this.hideLoadingSpinner();
            
        } catch (error) {
            logger.error('PromptManager', 'Diagram generation failed', error);
            
            // Hide loading spinner
            this.hideLoadingSpinner();
            
            // Show error notification
            this.showNotification(
                window.languageManager?.currentLanguage === 'zh' 
                    ? '生成失败，请重试' 
                    : 'Generation failed, please try again',
                'error'
            );
            
            // Re-enable send button
            this.sendBtn.disabled = false;
        }
    }
    
    /**
     * Transition to editor with generated diagram
     */
    transitionToEditorWithDiagram(data) {
        logger.info('PromptManager', 'Transitioning to editor', {
            diagramType: data.diagram_type || data.type,
            hasSpec: !!data.spec
        });
        
        // Get diagram type
        const diagramType = data.diagram_type || data.type;
        
        if (!diagramType || !data.spec) {
            logger.error('PromptManager', 'Missing diagram type or spec');
            this.showNotification(
                window.languageManager?.currentLanguage === 'zh' 
                    ? '数据不完整' 
                    : 'Incomplete data',
                'error'
            );
            return;
        }
        
        // CRITICAL: Use DiagramSelector to properly create session-aware editor
        if (!window.diagramSelector) {
            logger.error('PromptManager', 'DiagramSelector not available');
            this.showNotification(
                window.languageManager?.currentLanguage === 'zh' 
                    ? '系统错误' 
                    : 'System error',
                'error'
            );
            return;
        }
        
        try {
            // Get localized diagram name
            const diagramName = this.getDiagramName(diagramType);
            
            logger.debug('PromptManager', 'Using DiagramSelector for session management');
            
            // This will:
            // 1. Start a proper session with unique ID
            // 2. Set session protection flags
            // 3. Create InteractiveEditor with session info
            // 4. Initialize the editor properly
            window.diagramSelector.transitionToEditor(diagramType, data.spec, diagramName);
            
            logger.debug('PromptManager', 'Transition complete');
            
            // Show success notification
            this.showNotification(
                window.languageManager?.currentLanguage === 'zh' 
                    ? '图表生成成功！' 
                    : 'Diagram generated successfully!',
                'success'
            );
        } catch (error) {
            logger.error('PromptManager', 'Transition error', error);
            this.showNotification(
                window.languageManager?.currentLanguage === 'zh' 
                    ? '创建编辑器失败' 
                    : 'Failed to create editor',
                'error'
            );
        }
    }
    
    /**
     * Get localized diagram name
     */
    getDiagramName(diagramType) {
        const isZh = window.languageManager?.currentLanguage === 'zh';
        
        const typeNames = {
            'mindmap': isZh ? '思维导图' : 'Mind Map',
            'concept_map': isZh ? '概念图' : 'Concept Map',
            'bubble_map': isZh ? '气泡图' : 'Bubble Map',
            'double_bubble_map': isZh ? '双气泡图' : 'Double Bubble Map',
            'tree_map': isZh ? '树形图' : 'Tree Map',
            'brace_map': isZh ? '括号图' : 'Brace Map',
            'flow_map': isZh ? '流程图' : 'Flow Map',
            'multi_flow_map': isZh ? '复流程图' : 'Multi-Flow Map',
            'circle_map': isZh ? '圆圈图' : 'Circle Map',
            'bridge_map': isZh ? '桥形图' : 'Bridge Map'
        };
        
        return typeNames[diagramType] || diagramType;
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
        const confirmMessage = window.languageManager?.getNotification('clearHistoryConfirm') 
            || 'Clear all history?';
            
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
            logger.error('PromptManager', 'Failed to save history', e);
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
     * Show loading spinner
     */
    showLoadingSpinner() {
        // Create overlay
        const overlay = document.createElement('div');
        overlay.id = 'loading-overlay';
        overlay.style.position = 'fixed';
        overlay.style.top = '0';
        overlay.style.left = '0';
        overlay.style.width = '100%';
        overlay.style.height = '100%';
        overlay.style.background = 'rgba(0, 0, 0, 0.7)';
        overlay.style.display = 'flex';
        overlay.style.flexDirection = 'column';
        overlay.style.alignItems = 'center';
        overlay.style.justifyContent = 'center';
        overlay.style.zIndex = '10000';
        overlay.style.backdropFilter = 'blur(4px)';
        
        // Create spinner container
        const spinnerContainer = document.createElement('div');
        spinnerContainer.style.textAlign = 'center';
        
        // Create spinner
        const spinner = document.createElement('div');
        spinner.className = 'loading-spinner';
        spinner.style.width = '80px';
        spinner.style.height = '80px';
        spinner.style.border = '8px solid rgba(255, 255, 255, 0.2)';
        spinner.style.borderTop = '8px solid #667eea';
        spinner.style.borderRadius = '50%';
        spinner.style.animation = 'spin 1s linear infinite';
        
        // Create loading text
        const loadingText = document.createElement('div');
        loadingText.style.marginTop = '24px';
        loadingText.style.color = 'white';
        loadingText.style.fontSize = '18px';
        loadingText.style.fontWeight = '600';
        loadingText.textContent = window.languageManager?.currentLanguage === 'zh' 
            ? 'AI正在生成图表...' 
            : 'AI is generating your diagram...';
        
        // Create subtext
        const subText = document.createElement('div');
        subText.style.marginTop = '8px';
        subText.style.color = 'rgba(255, 255, 255, 0.8)';
        subText.style.fontSize = '14px';
        subText.textContent = window.languageManager?.currentLanguage === 'zh' 
            ? '请稍候，这可能需要几秒钟' 
            : 'Please wait, this may take a few seconds';
        
        // Add CSS animation if not exists
        if (!document.getElementById('spinner-style')) {
            const style = document.createElement('style');
            style.id = 'spinner-style';
            style.textContent = `
                @keyframes spin {
                    0% { transform: rotate(0deg); }
                    100% { transform: rotate(360deg); }
                }
                
                @keyframes pulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.5; }
                }
            `;
            document.head.appendChild(style);
        }
        
        // Add pulsing animation to text
        loadingText.style.animation = 'pulse 2s ease-in-out infinite';
        
        // Assemble
        spinnerContainer.appendChild(spinner);
        spinnerContainer.appendChild(loadingText);
        spinnerContainer.appendChild(subText);
        overlay.appendChild(spinnerContainer);
        
        document.body.appendChild(overlay);
    }
    
    /**
     * Hide loading spinner
     */
    hideLoadingSpinner() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.style.transition = 'opacity 0.3s ease';
            overlay.style.opacity = '0';
            setTimeout(() => {
                if (overlay.parentNode) {
                    overlay.parentNode.removeChild(overlay);
                }
            }, 300);
        }
    }
    
    /**
     * Show notification using centralized notification manager
     */
    showNotification(message, type = 'info') {
        if (window.notificationManager) {
            window.notificationManager.show(message, type);
        } else {
            logger.error('PromptManager', 'NotificationManager not available');
        }
    }
}

// Initialize when DOM is ready
if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', () => {
        window.promptManager = new PromptManager();
    });
}

