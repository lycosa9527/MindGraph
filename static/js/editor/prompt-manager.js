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
            const response = await fetch('/api/generate_graph', {
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
            console.error('Error generating diagram:', error);
            
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
        // Hide landing page
        const landing = document.getElementById('editor-landing');
        if (landing) {
            landing.style.display = 'none';
        }
        
        // Show editor interface
        const editorInterface = document.getElementById('editor-interface');
        if (editorInterface) {
            editorInterface.style.display = 'flex';
        }
        
        // Get diagram type (use diagram_type or type from response)
        const diagramType = data.diagram_type || data.type;
        
        // Update diagram type display
        const displayElement = document.getElementById('diagram-type-display');
        if (displayElement && diagramType) {
            const typeNames = {
                'mindmap': window.languageManager?.currentLanguage === 'zh' ? '思维导图' : 'Mind Map',
                'concept_map': window.languageManager?.currentLanguage === 'zh' ? '概念图' : 'Concept Map',
                'bubble_map': window.languageManager?.currentLanguage === 'zh' ? '气泡图' : 'Bubble Map',
                'double_bubble_map': window.languageManager?.currentLanguage === 'zh' ? '双气泡图' : 'Double Bubble Map',
                'tree_map': window.languageManager?.currentLanguage === 'zh' ? '树状图' : 'Tree Map',
                'brace_map': window.languageManager?.currentLanguage === 'zh' ? '括号图' : 'Brace Map',
                'flow_map': window.languageManager?.currentLanguage === 'zh' ? '流程图' : 'Flow Map',
                'multi_flow_map': window.languageManager?.currentLanguage === 'zh' ? '多流程图' : 'Multi-Flow Map',
                'circle_map': window.languageManager?.currentLanguage === 'zh' ? '圆圈图' : 'Circle Map',
                'bridge_map': window.languageManager?.currentLanguage === 'zh' ? '桥接图' : 'Bridge Map'
            };
            displayElement.textContent = typeNames[diagramType] || diagramType;
        }
        
        // Render diagram using the renderer dispatcher
        const container = document.getElementById('d3-container');
        if (container && data.spec && diagramType) {
            // Use the existing renderGraph function to render the diagram
            if (typeof window.renderGraph === 'function') {
                try {
                    // renderGraph clears the container and renders the diagram
                    window.renderGraph(diagramType, data.spec, data.theme || null, data.dimensions || null);
                    
                    console.log('Diagram rendered successfully');
                } catch (error) {
                    console.error('Error rendering diagram:', error);
                    this.showNotification(
                        window.languageManager?.currentLanguage === 'zh' 
                            ? '渲染失败' 
                            : 'Rendering failed',
                        'error'
                    );
                    return;
                }
            } else {
                console.error('renderGraph function not found');
                this.showNotification(
                    window.languageManager?.currentLanguage === 'zh' 
                        ? '渲染器未加载' 
                        : 'Renderer not loaded',
                    'error'
                );
                return;
            }
            
            // Initialize interactive editor if available
            if (window.InteractiveEditor && data.spec) {
                try {
                    window.currentEditor = new window.InteractiveEditor(diagramType, data.spec);
                    window.currentEditor.initialize();
                } catch (error) {
                    console.error('Error initializing interactive editor:', error);
                }
            }
        }
        
        // Show success notification
        this.showNotification(
            window.languageManager?.currentLanguage === 'zh' 
                ? '图表生成成功！' 
                : 'Diagram generated successfully!',
            'success'
        );
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
        
        // Set color based on type
        if (type === 'success') {
            notification.style.backgroundColor = '#4CAF50';
        } else if (type === 'error') {
            notification.style.backgroundColor = '#ff6b6b';
        } else {
            notification.style.backgroundColor = '#2196F3';
        }
        
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
                if (document.body.contains(notification)) {
                    document.body.removeChild(notification);
                }
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

