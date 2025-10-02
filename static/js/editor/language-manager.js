/**
 * LanguageManager - Handles language switching and translations
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 */

class LanguageManager {
    constructor() {
        this.currentLanguage = 'en';
        this.translations = {
            en: {
                mainTitle: 'MindGraph Professional',
                mainSubtitle: 'Choose a diagram type to start creating',
                promptPlaceholder: 'Describe your diagram or choose from templates below...',
                recentPrompts: 'Recent Prompts',
                clearHistory: 'Clear',
                noRecentPrompts: 'No recent prompts',
                thinkingMaps: 'Thinking Maps',
                advancedDiagrams: 'Advanced Diagrams',
                circleMap: 'Circle Map',
                circleMapDesc: 'Defining in context',
                bubbleMap: 'Bubble Map',
                bubbleMapDesc: 'Describing with adjectives',
                doubleBubbleMap: 'Double Bubble Map',
                doubleBubbleMapDesc: 'Comparing and contrasting',
                treeMap: 'Tree Map',
                treeMapDesc: 'Classifying and grouping',
                braceMap: 'Brace Map',
                braceMapDesc: 'Whole to parts',
                flowMap: 'Flow Map',
                flowMapDesc: 'Sequencing and ordering',
                multiFlowMap: 'Multi-Flow Map',
                multiFlowMapDesc: 'Cause and effect',
                bridgeMap: 'Bridge Map',
                bridgeMapDesc: 'Seeing analogies',
                mindMap: 'Mind Map',
                mindMapDesc: 'Creative brainstorming',
                conceptMap: 'Concept Map',
                conceptMapDesc: 'Complex relationships',
                selectButton: 'Select',
                backToGallery: 'Back to Gallery',
                reset: 'Reset',
                export: 'Export',
                nodes: 'Nodes',
                add: 'Add',
                delete: 'Delete',
                copy: 'Copy',
                tools: 'Tools',
                undo: 'Undo',
                redo: 'Redo',
                nodeCount: 'Nodes',
                editMode: 'Edit Mode: Active',
                shareSuccess: 'Link copied to clipboard!',
                shareError: 'Unable to copy link. Please copy manually:',
                languageButton: 'EN'
            },
            zh: {
                mainTitle: 'MindGraph 专业版',
                mainSubtitle: '选择图表类型开始创作',
                promptPlaceholder: '描述您的图表或从下方模板中选择...',
                recentPrompts: '最近的提示',
                clearHistory: '清除',
                noRecentPrompts: '暂无历史记录',
                thinkingMaps: '思维导图',
                advancedDiagrams: '高级图表',
                circleMap: '圆圈图',
                circleMapDesc: '情境中定义',
                bubbleMap: '气泡图',
                bubbleMapDesc: '用形容词描述',
                doubleBubbleMap: '双气泡图',
                doubleBubbleMapDesc: '比较和对比',
                treeMap: '树状图',
                treeMapDesc: '分类和分组',
                braceMap: '括号图',
                braceMapDesc: '整体到部分',
                flowMap: '流程图',
                flowMapDesc: '排序和顺序',
                multiFlowMap: '多流程图',
                multiFlowMapDesc: '因果关系',
                bridgeMap: '桥接图',
                bridgeMapDesc: '类比思维',
                mindMap: '思维导图',
                mindMapDesc: '创意头脑风暴',
                conceptMap: '概念图',
                conceptMapDesc: '复杂关系',
                selectButton: '选择',
                backToGallery: '返回图库',
                reset: '重置',
                export: '导出',
                nodes: '节点',
                add: '添加',
                delete: '删除',
                copy: '复制',
                tools: '工具',
                undo: '撤销',
                redo: '重做',
                nodeCount: '节点',
                editMode: '编辑模式：激活',
                shareSuccess: '链接已复制到剪贴板！',
                shareError: '无法复制链接，请手动复制：',
                languageButton: '中文'
            }
        };
        
        this.initializeEventListeners();
    }
    
    /**
     * Initialize event listeners
     */
    initializeEventListeners() {
        const langToggle = document.getElementById('language-toggle');
        const shareBtn = document.getElementById('share-btn');
        
        if (langToggle) {
            langToggle.addEventListener('click', () => this.toggleLanguage());
        }
        
        if (shareBtn) {
            shareBtn.addEventListener('click', () => this.shareUrl());
        }
    }
    
    /**
     * Toggle between English and Chinese
     */
    toggleLanguage() {
        this.currentLanguage = this.currentLanguage === 'en' ? 'zh' : 'en';
        this.applyTranslations();
        this.updateLanguageButton();
    }
    
    /**
     * Apply translations to the page
     */
    applyTranslations() {
        const t = this.translations[this.currentLanguage];
        
        // Update main title and subtitle
        const mainTitle = document.getElementById('main-title');
        const mainSubtitle = document.getElementById('main-subtitle');
        if (mainTitle) mainTitle.textContent = t.mainTitle;
        if (mainSubtitle) mainSubtitle.textContent = t.mainSubtitle;
        
        // Update prompt section
        const promptInput = document.getElementById('prompt-input');
        const historyToggleText = document.getElementById('history-toggle-text');
        const historyHeaderText = document.getElementById('history-header-text');
        const emptyHistoryText = document.getElementById('empty-history-text');
        const clearHistoryBtn = document.getElementById('clear-history-btn');
        
        if (promptInput) promptInput.placeholder = t.promptPlaceholder;
        if (historyToggleText) historyToggleText.textContent = t.recentPrompts;
        if (historyHeaderText) historyHeaderText.textContent = t.recentPrompts;
        if (emptyHistoryText) emptyHistoryText.textContent = t.noRecentPrompts;
        if (clearHistoryBtn) clearHistoryBtn.textContent = t.clearHistory;
        
        // Update category headers
        const categories = document.querySelectorAll('.diagram-category h2');
        if (categories.length >= 1) categories[0].textContent = t.thinkingMaps;
        if (categories.length >= 2) categories[1].textContent = t.advancedDiagrams;
        
        // Update diagram cards - Thinking Maps
        this.updateDiagramCard('circle_map', t.circleMap, t.circleMapDesc);
        this.updateDiagramCard('bubble_map', t.bubbleMap, t.bubbleMapDesc);
        this.updateDiagramCard('double_bubble_map', t.doubleBubbleMap, t.doubleBubbleMapDesc);
        this.updateDiagramCard('tree_map', t.treeMap, t.treeMapDesc);
        this.updateDiagramCard('brace_map', t.braceMap, t.braceMapDesc);
        this.updateDiagramCard('flow_map', t.flowMap, t.flowMapDesc);
        this.updateDiagramCard('multi_flow_map', t.multiFlowMap, t.multiFlowMapDesc);
        this.updateDiagramCard('bridge_map', t.bridgeMap, t.bridgeMapDesc);
        
        // Update diagram cards - Advanced Diagrams
        this.updateDiagramCard('mindmap', t.mindMap, t.mindMapDesc);
        this.updateDiagramCard('concept_map', t.conceptMap, t.conceptMapDesc);
        
        // Update toolbar buttons (if in editor view)
        const backBtn = document.getElementById('back-to-gallery');
        const resetBtn = document.getElementById('reset-btn');
        const exportBtn = document.getElementById('export-btn');
        const addBtn = document.getElementById('add-node-btn');
        const deleteBtn = document.getElementById('delete-node-btn');
        const autoBtn = document.getElementById('auto-complete-btn');
        const duplicateBtn = document.getElementById('duplicate-node-btn');
        const undoBtn = document.getElementById('undo-btn');
        const redoBtn = document.getElementById('redo-btn');
        
        if (backBtn) backBtn.textContent = t.backToGallery;
        if (resetBtn) resetBtn.textContent = t.reset;
        if (exportBtn) exportBtn.textContent = t.export;
        if (addBtn) addBtn.textContent = t.add;
        if (deleteBtn) deleteBtn.textContent = t.delete;
        // Auto button has icon + text in HTML, skip text update
        if (duplicateBtn) duplicateBtn.textContent = t.copy;
        if (undoBtn) undoBtn.textContent = t.undo;
        if (redoBtn) redoBtn.textContent = t.redo;
        
        // Update toolbar labels
        const toolbarLabels = document.querySelectorAll('.toolbar-group label');
        if (toolbarLabels.length >= 1) toolbarLabels[0].textContent = t.nodes + ':';
        if (toolbarLabels.length >= 2) toolbarLabels[1].textContent = t.tools + ':';
        
        // Update status bar
        const editMode = document.getElementById('edit-mode');
        if (editMode) editMode.textContent = t.editMode;
    }
    
    /**
     * Update a specific diagram card
     */
    updateDiagramCard(type, title, description) {
        const card = document.querySelector(`[data-type="${type}"]`);
        if (card) {
            const h3 = card.querySelector('h3');
            const p = card.querySelector('p');
            if (h3) h3.textContent = title;
            if (p) p.textContent = description;
        }
    }
    
    /**
     * Update language button text
     */
    updateLanguageButton() {
        const langToggle = document.getElementById('language-toggle');
        if (langToggle) {
            const langText = langToggle.querySelector('.lang-text');
            if (langText) {
                langText.textContent = this.currentLanguage === 'en' ? 'EN' : '中文';
            }
        }
    }
    
    /**
     * Share current URL - Show QR code
     */
    async shareUrl() {
        const url = window.location.href;
        this.showQRCodeModal(url);
    }
    
    /**
     * Show QR Code modal
     */
    showQRCodeModal(url) {
        const t = this.translations[this.currentLanguage];
        
        // Create modal overlay
        const overlay = document.createElement('div');
        overlay.className = 'qr-modal-overlay';
        overlay.style.position = 'fixed';
        overlay.style.top = '0';
        overlay.style.left = '0';
        overlay.style.width = '100%';
        overlay.style.height = '100%';
        overlay.style.background = 'rgba(0, 0, 0, 0.7)';
        overlay.style.display = 'flex';
        overlay.style.alignItems = 'center';
        overlay.style.justifyContent = 'center';
        overlay.style.zIndex = '9999'; /* Below the fixed buttons */
        overlay.style.opacity = '0';
        overlay.style.transition = 'opacity 0.3s ease';
        
        // Create modal content
        const modal = document.createElement('div');
        modal.className = 'qr-modal';
        modal.style.background = 'white';
        modal.style.borderRadius = '16px';
        modal.style.padding = '32px';
        modal.style.maxWidth = '400px';
        modal.style.boxShadow = '0 8px 32px rgba(0, 0, 0, 0.3)';
        modal.style.textAlign = 'center';
        modal.style.position = 'relative';
        
        // Close button
        const closeBtn = document.createElement('button');
        closeBtn.innerHTML = '×';
        closeBtn.style.position = 'absolute';
        closeBtn.style.top = '12px';
        closeBtn.style.right = '12px';
        closeBtn.style.background = 'none';
        closeBtn.style.border = 'none';
        closeBtn.style.fontSize = '32px';
        closeBtn.style.color = '#666';
        closeBtn.style.cursor = 'pointer';
        closeBtn.style.width = '40px';
        closeBtn.style.height = '40px';
        closeBtn.style.display = 'flex';
        closeBtn.style.alignItems = 'center';
        closeBtn.style.justifyContent = 'center';
        closeBtn.style.borderRadius = '50%';
        closeBtn.style.transition = 'all 0.2s ease';
        closeBtn.addEventListener('mouseover', () => {
            closeBtn.style.background = '#f0f0f0';
            closeBtn.style.color = '#333';
        });
        closeBtn.addEventListener('mouseout', () => {
            closeBtn.style.background = 'none';
            closeBtn.style.color = '#666';
        });
        closeBtn.addEventListener('click', () => {
            overlay.style.opacity = '0';
            setTimeout(() => overlay.remove(), 300);
        });
        
        // Title
        const title = document.createElement('h2');
        title.textContent = this.currentLanguage === 'en' ? 'Scan to Open' : '扫码打开';
        title.style.margin = '0 0 24px 0';
        title.style.color = '#333';
        title.style.fontSize = '24px';
        title.style.fontWeight = '600';
        
        // QR Code container
        const qrContainer = document.createElement('div');
        qrContainer.style.background = '#fff';
        qrContainer.style.padding = '20px';
        qrContainer.style.borderRadius = '12px';
        qrContainer.style.display = 'inline-block';
        qrContainer.style.border = '2px solid #e0e0e0';
        
        // Generate QR code using Google Charts API
        const qrImage = document.createElement('img');
        const qrSize = 256;
        qrImage.src = `https://api.qrserver.com/v1/create-qr-code/?size=${qrSize}x${qrSize}&data=${encodeURIComponent(url)}`;
        qrImage.style.width = `${qrSize}px`;
        qrImage.style.height = `${qrSize}px`;
        qrImage.style.display = 'block';
        
        // URL text
        const urlText = document.createElement('p');
        urlText.textContent = url;
        urlText.style.margin = '20px 0 0 0';
        urlText.style.color = '#666';
        urlText.style.fontSize = '14px';
        urlText.style.wordBreak = 'break-all';
        urlText.style.padding = '12px';
        urlText.style.background = '#f5f5f5';
        urlText.style.borderRadius = '8px';
        
        // Copy button
        const copyBtn = document.createElement('button');
        copyBtn.textContent = this.currentLanguage === 'en' ? 'Copy Link' : '复制链接';
        copyBtn.style.marginTop = '16px';
        copyBtn.style.padding = '10px 24px';
        copyBtn.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
        copyBtn.style.color = 'white';
        copyBtn.style.border = 'none';
        copyBtn.style.borderRadius = '8px';
        copyBtn.style.fontSize = '14px';
        copyBtn.style.fontWeight = '600';
        copyBtn.style.cursor = 'pointer';
        copyBtn.style.transition = 'all 0.2s ease';
        copyBtn.addEventListener('mouseover', () => {
            copyBtn.style.transform = 'translateY(-2px)';
            copyBtn.style.boxShadow = '0 4px 12px rgba(102, 126, 234, 0.4)';
        });
        copyBtn.addEventListener('mouseout', () => {
            copyBtn.style.transform = 'translateY(0)';
            copyBtn.style.boxShadow = 'none';
        });
        copyBtn.addEventListener('click', async () => {
            try {
                if (navigator.clipboard && navigator.clipboard.writeText) {
                    await navigator.clipboard.writeText(url);
                } else {
                    this.fallbackCopyToClipboard(url);
                }
                copyBtn.textContent = this.currentLanguage === 'en' ? 'Copied!' : '已复制！';
                copyBtn.style.background = '#4CAF50';
                setTimeout(() => {
                    copyBtn.textContent = this.currentLanguage === 'en' ? 'Copy Link' : '复制链接';
                    copyBtn.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
                }, 2000);
            } catch (err) {
                console.error('Copy failed:', err);
            }
        });
        
        // Assemble modal
        qrContainer.appendChild(qrImage);
        modal.appendChild(closeBtn);
        modal.appendChild(title);
        modal.appendChild(qrContainer);
        modal.appendChild(urlText);
        modal.appendChild(copyBtn);
        overlay.appendChild(modal);
        document.body.appendChild(overlay);
        
        // Fade in
        setTimeout(() => {
            overlay.style.opacity = '1';
        }, 10);
        
        // Close on overlay click
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                overlay.style.opacity = '0';
                setTimeout(() => overlay.remove(), 300);
            }
        });
        
        // Close on Escape key
        const escapeHandler = (e) => {
            if (e.key === 'Escape') {
                overlay.style.opacity = '0';
                setTimeout(() => overlay.remove(), 300);
                document.removeEventListener('keydown', escapeHandler);
            }
        };
        document.addEventListener('keydown', escapeHandler);
    }
    
    /**
     * Fallback copy method for older browsers
     */
    fallbackCopyToClipboard(text) {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.top = '0';
        textArea.style.left = '0';
        textArea.style.opacity = '0';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        try {
            document.execCommand('copy');
        } catch (err) {
            throw new Error('Copy failed');
        } finally {
            document.body.removeChild(textArea);
        }
    }
    
    /**
     * Show notification message
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
    
    /**
     * Get current language
     */
    getCurrentLanguage() {
        return this.currentLanguage;
    }
    
    /**
     * Get translation for a key
     */
    translate(key) {
        return this.translations[this.currentLanguage][key] || key;
    }
}

// Initialize when DOM is ready
if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', () => {
        window.languageManager = new LanguageManager();
    });
}

