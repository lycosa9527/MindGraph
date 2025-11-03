/**
 * LLM Progress Renderer
 * ====================
 * 
 * Handles UI rendering for LLM auto-complete progress and results.
 * Manages button states, progress notifications, and result display.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class LLMProgressRenderer {
    constructor(toolbarManager, logger) {
        this.toolbarManager = toolbarManager;
        this.logger = logger || console;
        this.llmButtons = toolbarManager.llmButtons || [];
        this.progressIndicator = document.getElementById('progress-indicator');
        
        this.logger.debug('LLMProgressRenderer', 'Progress renderer initialized');
    }
    
    /**
     * Show loading progress state
     */
    showProgress(message) {
        this.updateProgressMessage(message);
        this.updateProgressBar(0);
        
        this.logger.debug('LLMProgressRenderer', 'Progress shown', {
            message: message
        });
    }
    
    /**
     * Update progress message
     */
    updateProgressMessage(message) {
        if (!message) return;
        
        if (this.progressIndicator) {
            const messageEl = this.progressIndicator.querySelector('.progress-message');
            if (messageEl) {
                messageEl.textContent = message;
            }
        }
        
        this.logger.debug('LLMProgressRenderer', 'Progress message updated', {
            message: message
        });
    }
    
    /**
     * Update progress bar percentage
     */
    updateProgressBar(percentage) {
        if (percentage < 0) percentage = 0;
        if (percentage > 100) percentage = 100;
        
        if (this.progressIndicator) {
            const bar = this.progressIndicator.querySelector('.progress-bar');
            if (bar) {
                bar.style.width = `${percentage}%`;
            }
        }
    }
    
    /**
     * Show result ready notification
     */
    showResultReady(message, isSuccess = true) {
        this.updateProgressBar(100);
        this.updateProgressMessage(message);
        
        // Clear buttons loading state
        this.setAllLLMButtonsLoading(false);
        
        this.logger.debug('LLMProgressRenderer', 'Result ready shown', {
            message: message,
            isSuccess: isSuccess
        });
    }
    
    /**
     * Show error state
     */
    showError(message) {
        this.updateProgressMessage(message);
        this.setAllLLMButtonsLoading(false);
        
        this.logger.error('LLMProgressRenderer', 'Error displayed', {
            message: message
        });
    }
    
    /**
     * Set specific LLM button state
     */
    setLLMButtonState(modelName, state) {
        const button = this.llmButtons.find(btn => {
            const btnModel = btn.dataset?.llm || btn.id?.replace('llm-', '');
            return btnModel === modelName;
        });
        
        if (!button) {
            this.logger.warn('LLMProgressRenderer', `Button not found for model: ${modelName}`);
            return;
        }
        
        // Remove all state classes
        button.classList.remove('loading', 'ready', 'error', 'idle');
        
        // Add appropriate state class
        switch (state) {
            case 'loading':
                button.classList.add('loading');
                button.disabled = true;
                break;
            case 'ready':
                button.classList.add('ready');
                button.disabled = false;
                break;
            case 'error':
                button.classList.add('error');
                button.disabled = false;
                break;
            case 'idle':
                button.classList.add('idle');
                button.disabled = false;
                break;
        }
        
        this.logger.debug('LLMProgressRenderer', `Button state set for ${modelName}: ${state}`);
    }
    
    /**
     * Update all button states based on cached results
     */
    updateButtonStates(llmResults) {
        if (!llmResults) return;
        
        Object.entries(llmResults).forEach(([modelName, result]) => {
            if (result.success) {
                this.setLLMButtonState(modelName, 'ready');
            } else if (result.error) {
                this.setLLMButtonState(modelName, 'error');
            } else {
                this.setLLMButtonState(modelName, 'idle');
            }
        });
        
        this.logger.debug('LLMProgressRenderer', 'Button states updated');
    }
    
    /**
     * Set LLM buttons to loading state
     * @param {boolean} isLoading - Whether to set loading state
     * @param {Array<string>} models - Optional: specific models to set loading on (defaults to all)
     */
    setAllLLMButtonsLoading(isLoading, models = null) {
        this.llmButtons.forEach(btn => {
            const btnModel = btn.dataset?.llm || btn.id?.replace('llm-', '');
            
            // If models array is provided, only set loading for those specific models
            if (models && !models.includes(btnModel)) {
                return; // Skip this button
            }
            
            if (isLoading) {
                btn.classList.add('loading');
                btn.disabled = true;
            } else {
                btn.classList.remove('loading');
                btn.disabled = false;
            }
        });
        
        const targetInfo = models ? `models: ${models.join(', ')}` : 'all buttons';
        this.logger.debug('LLMProgressRenderer', `Loading state: ${isLoading} for ${targetInfo}`);
    }
    
    /**
     * Highlight selected model button
     */
    highlightSelectedModel(modelName) {
        this.llmButtons.forEach(btn => {
            const btnModel = btn.dataset?.llm || btn.id?.replace('llm-', '');
            if (btnModel === modelName) {
                btn.classList.add('selected');
            } else {
                btn.classList.remove('selected');
            }
        });
    }
    
    /**
     * Clear all button states
     */
    clearAllStates() {
        this.llmButtons.forEach(btn => {
            btn.classList.remove('loading', 'ready', 'error', 'idle', 'selected');
            btn.disabled = false;
        });
        
        if (this.progressIndicator) {
            this.progressIndicator.style.display = 'none';
        }
    }
}
