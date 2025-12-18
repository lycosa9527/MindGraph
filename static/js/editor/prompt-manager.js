/**
 * PromptManager - Handles AI prompt input and history
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
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
            
            // ALWAYS use Qwen for initial prompt generation (fast, reliable)
            // Then catapult the other 3 LLMs in background after canvas loads
            const initialLLM = 'qwen';
            
            // Send to AI generation endpoint
            const response = await auth.fetch('/api/generate_graph', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    prompt: prompt,
                    language: language,
                    llm: initialLLM  // Force Qwen for prompt-based generation
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Check for prompt too complex error - show guidance modal
            if (data.error_type === 'prompt_too_complex' || data.show_guidance) {
                // Hide loading spinner
                this.hideLoadingSpinner();
                
                // Re-enable send button
                this.sendBtn.disabled = false;
                
                // Show friendly guidance modal
                if (window.modalManager) {
                    window.modalManager.showPromptGuidance(language);
                } else {
                    // Fallback to notification if modal manager not available
                    const errorMsg = language === 'zh' 
                        ? '您的指令有点复杂，请尝试使用更简单明确的描述，包括主题和想做什么。'
                        : 'Your prompt is a bit complex. Please try using simpler and clearer instructions with a topic and what you want to do.';
                    window.notificationManager?.show(errorMsg, 'warning', 6000);
                }
                return;
            }
            
            // Check for other errors in response
            if (data.error) {
                throw new Error(data.error);
            }
            
            // Check for warnings (partial recovery)
            if (data.warning) {
                const warningMsg = window.languageManager?.currentLanguage === 'zh'
                    ? 'LLM响应存在问题，部分分支可能缺失。您可以使用自动补全功能添加更多内容。'
                    : 'LLM response had issues. Some branches may be missing. You can use auto-complete to add more.';
                this.showNotification(warningMsg, 'warning', 8000);
            }
            
            // Clear input
            this.promptInput.value = '';
            this.updateSendButtonState();
            
            // Close history if open
            this.closeHistory();
            
            // Hide loading spinner immediately so user sees canvas right away
            // Auto-complete will enrich it in the background
            this.hideLoadingSpinner();
            
            // Transition to editor with generated diagram
            this.transitionToEditorWithDiagram(data);
            
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
            hasSpec: !!data.spec,
            useDefaultTemplate: !!data.use_default_template,
            extractedTopic: data.extracted_topic,
            fullData: data
        });
        
        // Get diagram type
        const diagramType = data.diagram_type || data.type;
        
        if (!diagramType) {
            logger.error('PromptManager', 'Missing diagram type');
            this.showNotification(
                window.languageManager?.currentLanguage === 'zh' 
                    ? '数据不完整' 
                    : 'Incomplete data',
                'error'
            );
            return;
        }
        
        // Handle default template mode (prompt-based generation)
        if (data.use_default_template && data.extracted_topic) {
            logger.info('PromptManager', `Using default template mode: diagramType=${diagramType}, topic="${data.extracted_topic}"`);
            
            // Check if DiagramSelector is available
            if (!window.diagramSelector) {
                logger.error('PromptManager', 'DiagramSelector not available');
                this.showNotification(
                    window.languageManager?.currentLanguage === 'zh' 
                        ? '系统未初始化' 
                        : 'System not initialized',
                    'error'
                );
                return;
            }
            
            // Normalize diagram type (mind_map → mindmap)
            const normalizedType = diagramType === 'mind_map' ? 'mindmap' : diagramType;
            logger.info('PromptManager', `Normalized type: ${normalizedType}`);
            
            // Load default template from DiagramSelector using factory method
            const template = window.diagramSelector.getTemplate(normalizedType);
            logger.info('PromptManager', `Template loaded:`, template);
            
            if (!template) {
                logger.error('PromptManager', `No default template for ${normalizedType}`);
                this.showNotification(
                    window.languageManager?.currentLanguage === 'zh' 
                        ? '无法加载模板' 
                        : 'Failed to load template',
                    'error'
                );
                return;
            }
            
            // Replace topic in template based on diagram type
            const extractedTopic = data.extracted_topic;
            
            if (normalizedType === 'double_bubble_map') {
                // Double bubble map: parse "TopicA和TopicB" or "TopicA vs TopicB" format
                // Split by common separators: 和, vs, VS, 与, versus, compared to
                const separators = [' vs ', ' VS ', '和', '与', ' versus ', ' compared to '];
                let leftTopic = extractedTopic;
                let rightTopic = extractedTopic;
                
                for (const sep of separators) {
                    if (extractedTopic.includes(sep)) {
                        const parts = extractedTopic.split(sep);
                        if (parts.length >= 2) {
                            leftTopic = parts[0].trim();
                            rightTopic = parts[1].trim();
                            break;
                        }
                    }
                }
                
                template.left = leftTopic;
                template.right = rightTopic;
                
                // Update positions if exists
                if (template._layout && template._layout.positions) {
                    if (template._layout.positions['主题A']) {
                        delete template._layout.positions['主题A'];
                        template._layout.positions[leftTopic] = { x: 200, y: 250 };
                    }
                    if (template._layout.positions['主题B']) {
                        delete template._layout.positions['主题B'];
                        template._layout.positions[rightTopic] = { x: 500, y: 250 };
                    }
                    if (template._layout.positions['Topic A']) {
                        delete template._layout.positions['Topic A'];
                        template._layout.positions[leftTopic] = { x: 200, y: 250 };
                    }
                    if (template._layout.positions['Topic B']) {
                        delete template._layout.positions['Topic B'];
                        template._layout.positions[rightTopic] = { x: 500, y: 250 };
                    }
                }
                
                logger.info('PromptManager', `Double bubble map: left="${leftTopic}", right="${rightTopic}"`);
                
            } else if (normalizedType === 'flow_map') {
                // Flow map uses 'title' field
                template.title = extractedTopic;
                if (template.topic) template.topic = extractedTopic;
                logger.info('PromptManager', `Flow map: title="${extractedTopic}"`);
                
            } else if (normalizedType === 'multi_flow_map') {
                // Multi-flow map uses 'event' field
                template.event = extractedTopic;
                if (template.topic) template.topic = extractedTopic;
                logger.info('PromptManager', `Multi-flow map: event="${extractedTopic}"`);
                
            } else if (normalizedType === 'brace_map') {
                // Brace map uses 'whole' field
                template.whole = extractedTopic;
                if (template.topic) template.topic = extractedTopic;
                logger.info('PromptManager', `Brace map: whole="${extractedTopic}"`);
                
            } else if (normalizedType === 'bridge_map') {
                // Bridge map: try to parse as dimension/relationship or first analogy pair
                // Common patterns: "A:B", "A和B的关系", "A relates to B"
                const pairSeparators = [':', '：', ' relates to ', ' is to ', '对应'];
                let foundPair = false;
                
                for (const sep of pairSeparators) {
                    if (extractedTopic.includes(sep)) {
                        const parts = extractedTopic.split(sep);
                        if (parts.length >= 2) {
                            // Set the first analogy pair
                            if (template.analogies && template.analogies.length > 0) {
                                template.analogies[0].left = parts[0].trim();
                                template.analogies[0].right = parts[1].trim();
                            }
                            foundPair = true;
                            logger.info('PromptManager', `Bridge map: first pair="${parts[0].trim()}:${parts[1].trim()}"`);
                            break;
                        }
                    }
                }
                
                // If no pair pattern found, use as dimension/relationship description
                if (!foundPair) {
                    template.dimension = extractedTopic;
                    logger.info('PromptManager', `Bridge map: dimension="${extractedTopic}"`);
                }
                
            } else {
                // Standard handling for other diagram types
                template.topic = extractedTopic;
                if (template.center) template.center = extractedTopic;
                if (template.central_topic) template.central_topic = extractedTopic;
                
                // Update positions if exists
                if (template._layout && template._layout.positions && template._layout.positions.topic) {
                    template._layout.positions.topic.text = extractedTopic;
                }
                
                logger.info('PromptManager', `Standard diagram: topic="${extractedTopic}"`);
            }
            
            logger.info('PromptManager', 'Template loaded and topic replaced successfully');
            
            // Use this template as spec
            data.spec = template;
        }
        
        if (!data.spec) {
            logger.error('PromptManager', 'Missing spec');
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
            
            // Check if we should trigger auto-complete (prompt-based generation)
            if (data.use_default_template) {
                // Default template loaded - trigger auto-complete with ALL 4 LLMs to enrich it
                logger.info('PromptManager', 'Default template loaded, scheduling auto-complete with ALL 4 LLMs');
                setTimeout(() => {
                    this.triggerAutoComplete(null); // No exclusion - use all 4 LLMs
                }, 1200); // Wait for canvas to fully render before triggering
            }
            
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
        spinner.style.margin = '0 auto';
        
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
     * Auto-trigger auto-complete to enrich the diagram with LLM suggestions
     * @param {string} excludeModel - Model to exclude (already used for initial generation)
     */
    triggerAutoComplete(excludeModel = null) {
        try {
            // Find the auto-complete button
            const autoCompleteBtn = document.getElementById('auto-complete-btn');
            
            if (!autoCompleteBtn) {
                logger.warn('PromptManager', 'Auto-complete button not found');
                return;
            }
            
            // Check if editor is ready
            if (!window.currentEditor || !window.currentEditor.currentSpec) {
                logger.warn('PromptManager', 'Editor not ready for auto-complete');
                return;
            }
            
            // Store excluded model in window for auto-complete manager to read
            if (excludeModel) {
                window._autoCompleteExcludeModel = excludeModel;
                logger.info('PromptManager', `Catapult triggering - excluding ${excludeModel} (already used)`);
            } else {
                window._autoCompleteExcludeModel = null;
                logger.info('PromptManager', 'Triggering auto-complete with all models');
            }
            
            // Count of models to run
            const modelCount = excludeModel ? 3 : 4;
            
            // Show info notification
            this.showNotification(
                window.languageManager?.currentLanguage === 'zh'
                    ? `正在使用${modelCount}个AI模型自动补全内容...`
                    : `Auto-completing with ${modelCount} AI models...`,
                'info'
            );
            
            // Trigger the auto-complete button click
            autoCompleteBtn.click();
            
        } catch (error) {
            logger.error('PromptManager', 'Error triggering auto-complete', error);
            // Don't show error to user - auto-complete is optional enhancement
        }
    }
    
    /**
     * Show notification using centralized notification manager
     */
    showNotification(message, type = 'info', duration = null) {
        if (window.notificationManager) {
            window.notificationManager.show(message, type, duration);
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

