/**
 * LanguageManager - Handles language switching and translations
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 */

class LanguageManager {
    constructor() {
        this.currentLanguage = 'zh';
        this.translations = {
            en: {
                mainTitle: 'MindGraph Pro',
                mainSubtitle: 'The universe\'s most powerful AI diagram generation software',
                promptPlaceholder: 'Describe your diagram or choose from templates below...',
                recentPrompts: 'Recent Prompts',
                clearHistory: 'Clear',
                noRecentPrompts: 'No recent prompts',
                thinkingMaps: 'Thinking Maps',
                advancedDiagrams: 'Advanced Diagrams',
                circleMap: 'Circle Map',
                circleMapDesc: 'Association, brainstorming',
                bubbleMap: 'Bubble Map',
                bubbleMapDesc: 'Describing characteristics',
                doubleBubbleMap: 'Double Bubble Map',
                doubleBubbleMapDesc: 'Comparing and contrasting',
                treeMap: 'Tree Map',
                treeMapDesc: 'Classifying and categorizing',
                braceMap: 'Brace Map',
                braceMapDesc: 'Whole and parts',
                flowMap: 'Flow Map',
                flowMapDesc: 'Sequence and steps',
                multiFlowMap: 'Multi-Flow Map',
                multiFlowMapDesc: 'Cause and effect analysis',
                bridgeMap: 'Bridge Map',
                bridgeMapDesc: 'Analogical reasoning',
                mindMap: 'Mind Map',
                mindMapDesc: 'Cause and effect analysis',
                conceptMap: 'Concept Map',
                conceptMapDesc: 'Conceptual relationships',
                selectButton: 'Select',
                backToGallery: 'Back to Gallery',
                reset: 'Reset',
                export: 'Export',
                nodes: 'Nodes',
                add: 'Add',
                delete: 'Delete',
                copy: 'Copy',
                auto: 'Auto',
                line: 'Line',
                tools: 'Tools',
                empty: 'Empty',
                undo: 'Undo',
                redo: 'Redo',
                nodeCount: 'Nodes',
                editMode: 'Edit Mode: Active',
                shareSuccess: 'Link copied to clipboard!',
                shareError: 'Unable to copy link. Please copy manually:',
                languageButton: '中文',
                // Dynamic node text for adding new nodes
                newAttribute: 'New Attribute',
                newStep: 'New Step',
                newCause: 'New Cause',
                newEffect: 'New Effect',
                newBranch: 'New Branch',
                newNode: 'New Node',
                newItem: 'New Item',
                newCategory: 'New Category',
                newSubitem: 'New Subitem',
                newConcept: 'New Concept',
                newRelation: 'relates to',
                // Tooltips
                addNodeTooltip: 'Add Node',
                deleteNodeTooltip: 'Delete Selected',
                autoCompleteTooltip: 'Auto-complete diagram with AI',
                lineModeTooltip: 'Toggle black & white line mode',
                emptyNodeTooltip: 'Empty selected node text',
                undoTooltip: 'Undo',
                redoTooltip: 'Redo',
                switchLanguageTooltip: 'Switch Language',
                share: 'Share',
                shareTooltip: 'Share',
                boldTooltip: 'Bold',
                italicTooltip: 'Italic',
                underlineTooltip: 'Underline',
                closeTooltip: 'Close',
                // Node Editor
                editNodeContent: 'Edit Node Content',
                characters: 'characters',
                cancel: 'Cancel',
                saveChanges: 'Save Changes',
                // Properties Panel
                properties: 'Properties',
                text: 'Text',
                nodeTextPlaceholder: 'Node text',
                apply: 'Apply',
                resetStyles: 'Reset Styles',
                fontSize: 'Font Size',
                textStyle: 'Text Style',
                textColor: 'Text Color',
                fillColor: 'Fill Color',
                strokeColor: 'Stroke Color',
                strokeWidth: 'Stroke Width',
                opacity: 'Opacity',
                applyAllChanges: 'Apply All Changes',
                // MindMate AI Panel
                mindMateAI: 'MindMate AI',
                online: 'Online',
                welcomeTitle: 'Welcome to MindMate AI!',
                welcomeMessage: "I'm here to help you with your diagrams. Ask me anything about creating, editing, or improving your work.",
                askMindMatePlaceholder: 'Ask MindMate anything...',
                // Notification Messages
                notif: {
                    textEmpty: 'Text cannot be empty',
                    textUpdated: 'Text updated successfully',
                    propertiesApplied: 'All properties applied successfully!',
                    editorNotInit: 'Editor not initialized',
                    selectNodeToAdd: 'Please select a node first to add',
                    nodeAdded: 'Node added! Double-click to edit text.',
                    nodesDeleted: (count) => `Deleted ${count} node${count > 1 ? 's' : ''}`,
                    selectNodeToDelete: 'Select a node first to delete',
                    nodesEmptied: (count) => `Emptied ${count} node${count > 1 ? 's' : ''}`,
                    selectNodeToEmpty: 'Select a node first to empty',
                    addNodesFirst: 'Please add some nodes first before using Auto',
                    aiCompleting: (topic) => `AI is completing diagram about "${topic}"...`,
                    diagramChanged: 'Diagram changed during auto-complete',
                    sessionChanged: 'Session changed during auto-complete',
                    autoCompleteSuccess: 'Diagram auto-completed successfully!',
                    autoCompleteFailed: (error) => `Auto-complete failed: ${error}`,
                    lineModeEnabled: 'Line mode enabled',
                    lineModeDisabled: 'Line mode disabled',
                    duplicateComingSoon: 'Duplicate node feature coming soon!',
                    resetFailed: 'Failed to reset: diagram selector not found',
                    templateNotFound: 'Failed to reset: template not found',
                    canvasReset: 'Canvas reset to blank template',
                    resetConfirm: 'Are you sure you want to reset the canvas to a blank template? All current changes will be lost.',
                    noDiagramToExport: 'No diagram to export!',
                    diagramExported: 'Diagram exported as PNG!',
                    exportFailed: 'Failed to export diagram',
                    // Interactive Editor Notifications
                    couldNotDetermineNodeType: 'Could not determine node type. Please try again.',
                    cannotAddMainTopics: 'Cannot add main topics. Please select a similarity or difference node.',
                    unknownNodeType: 'Unknown node type. Please select a similarity or difference node.',
                    similarityNodeAdded: 'Similarity node added!',
                    differencePairAdded: 'Difference pair added!',
                    invalidPartIndex: 'Invalid part index',
                    cannotAddToTopic: 'Cannot add to topic. Please select a part or subpart node.',
                    unknownNodeSelectPart: 'Unknown node type. Please select a part or subpart node.',
                    invalidStepIndex: 'Invalid step index',
                    invalidSubstepIndex: 'Invalid substep index',
                    cannotAddToTitle: 'Cannot add to title. Please select a step or substep node.',
                    selectStepOrSubstep: 'Please select a step or substep node',
                    cannotAddToEvent: 'Cannot add to event. Please select a cause or effect node.',
                    selectCauseOrEffect: 'Please select a cause or effect node',
                    cannotAddToTopicSelectCategory: 'Cannot add to topic. Please select a category or child node.',
                    selectCategoryOrChild: 'Please select a category or child node',
                    selectBranchOrSubitem: 'Please select a branch or sub-item to add',
                    cannotAddToCentral: 'Cannot add to central topic. Please select a branch or sub-item.',
                    invalidBranchIndex: 'Invalid branch index',
                    newSubitemAdded: 'New sub-item added!',
                    unknownNodeSelectBranch: 'Unknown node type. Please select a branch or sub-item.',
                    updatingLayout: 'Updating layout...',
                    layoutUpdateFailed: 'Failed to update layout. Changes may not be visible.',
                    cannotDeleteTitle: 'Cannot delete the title',
                    cannotDeleteCentralEvent: 'Cannot delete the central event',
                    cannotDeleteRootTopic: 'Cannot delete the root topic',
                    cannotDeleteFirstAnalogy: 'Cannot delete the first analogy pair',
                    cannotDeleteCentralTopic: 'Cannot delete the central topic'
                }
            },
            zh: {
                mainTitle: 'MindGraph专业版',
                mainSubtitle: '宇宙中最强大的AI思维图示生成软件',
                promptPlaceholder: '描述您的图表或从下方模板中选择...',
                recentPrompts: '提示词历史',
                clearHistory: '清除',
                noRecentPrompts: '暂无历史记录',
                thinkingMaps: '八大思维图示',
                advancedDiagrams: '进阶图示',
                circleMap: '圆圈图',
                circleMapDesc: '联想，头脑风暴',
                bubbleMap: '气泡图',
                bubbleMapDesc: '描述特性',
                doubleBubbleMap: '双气泡图',
                doubleBubbleMapDesc: '比较与对比',
                treeMap: '树形图',
                treeMapDesc: '分类与归纳',
                braceMap: '括号图',
                braceMapDesc: '整体与部分',
                flowMap: '流程图',
                flowMapDesc: '顺序与步骤',
                multiFlowMap: '复流程图',
                multiFlowMapDesc: '因果分析',
                bridgeMap: '桥形图',
                bridgeMapDesc: '类比推理',
                mindMap: '思维导图',
                mindMapDesc: '因果分析',
                conceptMap: '概念图',
                conceptMapDesc: '概念关系',
                selectButton: '选择',
                backToGallery: '返回图库',
                reset: '重置',
                export: '导出',
                nodes: '节点',
                add: '添加',
                delete: '删除',
                copy: '复制',
                auto: '自动',
                line: '线稿',
                tools: '工具',
                empty: '清空',
                undo: '撤销',
                redo: '重做',
                nodeCount: '节点',
                editMode: '编辑模式：激活',
                shareSuccess: '链接已复制到剪贴板！',
                shareError: '无法复制链接，请手动复制：',
                languageButton: 'EN',
                // Dynamic node text for adding new nodes
                newAttribute: '新属性',
                newStep: '新步骤',
                newCause: '新原因',
                newEffect: '新结果',
                newBranch: '新分支',
                newNode: '新节点',
                newItem: '新项目',
                newCategory: '新类别',
                newSubitem: '新子项',
                newConcept: '新概念',
                newRelation: '关联',
                // Tooltips
                addNodeTooltip: '添加节点',
                deleteNodeTooltip: '删除选中节点',
                autoCompleteTooltip: '使用AI自动完成图示',
                lineModeTooltip: '切换黑白线稿模式',
                emptyNodeTooltip: '清空选中节点文本',
                undoTooltip: '撤销',
                redoTooltip: '重做',
                switchLanguageTooltip: '切换语言',
                share: '分享',
                shareTooltip: '分享',
                boldTooltip: '粗体',
                italicTooltip: '斜体',
                underlineTooltip: '下划线',
                closeTooltip: '关闭',
                // Node Editor
                editNodeContent: '编辑节点内容',
                characters: '字',
                cancel: '取消',
                saveChanges: '保存更改',
                // Properties Panel
                properties: '属性',
                text: '文本',
                nodeTextPlaceholder: '节点文本',
                apply: '应用',
                resetStyles: '重置样式',
                fontSize: '字体大小',
                textStyle: '文本样式',
                textColor: '文本颜色',
                fillColor: '填充颜色',
                strokeColor: '边框颜色',
                strokeWidth: '边框宽度',
                opacity: '透明度',
                applyAllChanges: '应用所有更改',
                // MindMate AI Panel
                mindMateAI: 'MindMate AI',
                online: '在线',
                welcomeTitle: '欢迎使用MindMate AI！',
                welcomeMessage: '我在这里帮助您创建图示。随时询问有关创建、编辑或改进您作品的任何问题。',
                askMindMatePlaceholder: '向MindMate提问任何问题...',
                // Notification Messages
                notif: {
                    textEmpty: '文本不能为空',
                    textUpdated: '文本更新成功',
                    propertiesApplied: '所有属性应用成功！',
                    editorNotInit: '编辑器未初始化',
                    selectNodeToAdd: '请先选择一个节点以添加',
                    nodeAdded: '节点已添加！双击编辑文本。',
                    nodesDeleted: (count) => `已删除 ${count} 个节点`,
                    selectNodeToDelete: '请先选择一个节点以删除',
                    nodesEmptied: (count) => `已清空 ${count} 个节点`,
                    selectNodeToEmpty: '请先选择一个节点以清空',
                    addNodesFirst: '请先添加一些节点再使用自动完成',
                    aiCompleting: (topic) => `AI正在完成关于"${topic}"的图示...`,
                    diagramChanged: '自动完成期间图示已更改',
                    sessionChanged: '自动完成期间会话已更改',
                    autoCompleteSuccess: '图示自动完成成功！',
                    autoCompleteFailed: (error) => `自动完成失败：${error}`,
                    lineModeEnabled: '线稿模式已启用',
                    lineModeDisabled: '线稿模式已禁用',
                    duplicateComingSoon: '复制节点功能即将推出！',
                    resetFailed: '重置失败：未找到图表选择器',
                    templateNotFound: '重置失败：未找到模板',
                    canvasReset: '画布已重置为空白模板',
                    resetConfirm: '确定要将画布重置为空白模板吗？当前所有更改将丢失。',
                    noDiagramToExport: '没有可导出的图示！',
                    diagramExported: '图示已导出为PNG！',
                    exportFailed: '导出图示失败',
                    // Interactive Editor Notifications
                    couldNotDetermineNodeType: '无法确定节点类型。请重试。',
                    cannotAddMainTopics: '无法添加主主题。请选择相似或差异节点。',
                    unknownNodeType: '未知节点类型。请选择相似或差异节点。',
                    similarityNodeAdded: '相似节点已添加！',
                    differencePairAdded: '差异对已添加！',
                    invalidPartIndex: '无效的部分索引',
                    cannotAddToTopic: '无法添加到主题。请选择部分或子部分节点。',
                    unknownNodeSelectPart: '未知节点类型。请选择部分或子部分节点。',
                    invalidStepIndex: '无效的步骤索引',
                    invalidSubstepIndex: '无效的子步骤索引',
                    cannotAddToTitle: '无法添加到标题。请选择步骤或子步骤节点。',
                    selectStepOrSubstep: '请选择步骤或子步骤节点',
                    cannotAddToEvent: '无法添加到事件。请选择原因或结果节点。',
                    selectCauseOrEffect: '请选择原因或结果节点',
                    cannotAddToTopicSelectCategory: '无法添加到主题。请选择类别或子节点。',
                    selectCategoryOrChild: '请选择类别或子节点',
                    selectBranchOrSubitem: '请选择分支或子项以添加',
                    cannotAddToCentral: '无法添加到中心主题。请选择分支或子项。',
                    invalidBranchIndex: '无效的分支索引',
                    newSubitemAdded: '新子项已添加！',
                    unknownNodeSelectBranch: '未知节点类型。请选择分支或子项。',
                    updatingLayout: '正在更新布局...',
                    layoutUpdateFailed: '布局更新失败。更改可能不可见。',
                    cannotDeleteTitle: '无法删除标题',
                    cannotDeleteCentralEvent: '无法删除中心事件',
                    cannotDeleteRootTopic: '无法删除根主题',
                    cannotDeleteFirstAnalogy: '无法删除第一个类比对',
                    cannotDeleteCentralTopic: '无法删除中心主题'
                }
            }
        };
        
        this.initializeEventListeners();
        // Apply initial translations for Chinese default
        this.applyTranslations();
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
        
        // If in editor mode, refresh the diagram with language-appropriate template
        this.refreshEditorIfActive();
    }
    
    /**
     * Refresh editor with new language template if currently editing
     */
    refreshEditorIfActive() {
        // Check if we're in editor mode
        const editorView = document.getElementById('editor-view');
        const galleryView = document.getElementById('gallery-view');
        
        if (editorView && editorView.style.display !== 'none' && 
            galleryView && galleryView.style.display === 'none') {
            
            // We're in editor mode, refresh with new template
            if (window.interactiveEditor && window.diagramSelector) {
                const currentDiagramType = window.interactiveEditor.diagramType;
                console.log(`Refreshing ${currentDiagramType} with ${this.currentLanguage} template`);
                
                // Get fresh template in new language
                const freshTemplate = window.diagramSelector.getTemplate(currentDiagramType);
                
                // Update the editor's spec and re-render
                if (freshTemplate) {
                    window.interactiveEditor.currentSpec = freshTemplate;
                    window.interactiveEditor.renderDiagram();
                    
                    // Show notification
                    this.showNotification(
                        this.currentLanguage === 'en' ? 'Template refreshed in English' : '模板已刷新为中文',
                        'success'
                    );
                }
            }
        }
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
        const lineBtn = document.getElementById('line-mode-btn');
        const emptyBtn = document.getElementById('empty-node-btn');
        const duplicateBtn = document.getElementById('duplicate-node-btn');
        const undoBtn = document.getElementById('undo-btn');
        const redoBtn = document.getElementById('redo-btn');
        
        if (backBtn) backBtn.textContent = t.backToGallery;
        if (resetBtn) resetBtn.textContent = t.reset;
        if (exportBtn) exportBtn.textContent = t.export;
        if (addBtn) {
            addBtn.textContent = t.add;
            addBtn.title = t.addNodeTooltip;
        }
        if (deleteBtn) {
            deleteBtn.textContent = t.delete;
            deleteBtn.title = t.deleteNodeTooltip;
        }
        
        // Update Auto button text (keep icon, update text)
        if (autoBtn) {
            // Find text nodes and update the one with actual text
            const childNodes = Array.from(autoBtn.childNodes);
            childNodes.forEach(node => {
                if (node.nodeType === Node.TEXT_NODE && node.textContent.trim()) {
                    node.textContent = '\n                        ' + t.auto + '\n                    ';
                }
            });
            autoBtn.title = t.autoCompleteTooltip;
        }
        
        // Update Line button text (keep icon, update text)
        if (lineBtn) {
            // Find text nodes and update the one with actual text
            const childNodes = Array.from(lineBtn.childNodes);
            childNodes.forEach(node => {
                if (node.nodeType === Node.TEXT_NODE && node.textContent.trim()) {
                    node.textContent = '\n                        ' + t.line + '\n                    ';
                }
            });
            lineBtn.title = t.lineModeTooltip;
        }
        
        if (emptyBtn) {
            emptyBtn.textContent = t.empty;
            emptyBtn.title = t.emptyNodeTooltip;
        }
        if (duplicateBtn) duplicateBtn.textContent = t.copy;
        if (undoBtn) {
            undoBtn.textContent = t.undo;
            undoBtn.title = t.undoTooltip;
        }
        if (redoBtn) {
            redoBtn.textContent = t.redo;
            redoBtn.title = t.redoTooltip;
        }
        
        // Update language toggle button tooltip
        const langToggle = document.getElementById('language-toggle');
        if (langToggle) {
            langToggle.title = t.switchLanguageTooltip;
        }
        
        // Update share button text and tooltip
        const shareBtn = document.getElementById('share-btn');
        if (shareBtn) {
            const shareSpan = shareBtn.querySelector('span');
            if (shareSpan) shareSpan.textContent = t.share;
            shareBtn.title = t.shareTooltip;
        }
        
        // Update property panel tooltips
        const propBold = document.getElementById('prop-bold');
        const propItalic = document.getElementById('prop-italic');
        const propUnderline = document.getElementById('prop-underline');
        if (propBold) propBold.title = t.boldTooltip;
        if (propItalic) propItalic.title = t.italicTooltip;
        if (propUnderline) propUnderline.title = t.underlineTooltip;
        
        // Update AI assistant close button tooltip
        const aiCloseBtn = document.getElementById('toggle-ai-assistant');
        if (aiCloseBtn) aiCloseBtn.title = t.closeTooltip;
        
        // Update toolbar labels
        const toolbarLabels = document.querySelectorAll('.toolbar-group label');
        if (toolbarLabels.length >= 1) toolbarLabels[0].textContent = t.nodes + ':';
        if (toolbarLabels.length >= 2) toolbarLabels[1].textContent = t.tools + ':';
        
        // Update status bar
        const editMode = document.getElementById('edit-mode');
        if (editMode) editMode.textContent = t.editMode;
        
        // Update Properties Panel
        const propHeader = document.querySelector('.property-panel .property-header h3');
        if (propHeader) propHeader.textContent = t.properties;
        
        const propLabels = document.querySelectorAll('.property-panel .property-group label');
        if (propLabels[0]) propLabels[0].textContent = t.text;
        if (propLabels[1]) propLabels[1].textContent = t.fontSize;
        if (propLabels[2]) propLabels[2].textContent = t.textStyle;
        if (propLabels[3]) propLabels[3].textContent = t.textColor;
        if (propLabels[4]) propLabels[4].textContent = t.fillColor;
        if (propLabels[5]) propLabels[5].textContent = t.strokeColor;
        if (propLabels[6]) propLabels[6].textContent = t.strokeWidth;
        if (propLabels[7]) propLabels[7].textContent = t.opacity;
        
        const propTextInput = document.getElementById('prop-text');
        if (propTextInput) propTextInput.placeholder = t.nodeTextPlaceholder;
        
        const propTextApply = document.getElementById('prop-text-apply');
        if (propTextApply) propTextApply.textContent = t.apply;
        
        const resetStylesBtn = document.getElementById('reset-styles-btn');
        if (resetStylesBtn) resetStylesBtn.textContent = t.resetStyles;
        
        // Update MindMate AI Panel
        const aiTitle = document.querySelector('.ai-assistant-panel .ai-header-text h3');
        if (aiTitle) aiTitle.textContent = t.mindMateAI;
        
        const aiStatus = document.querySelector('.ai-assistant-panel .ai-status');
        if (aiStatus) aiStatus.textContent = t.online;
        
        const welcomeTitle = document.querySelector('.ai-welcome-message .welcome-text h4');
        if (welcomeTitle) welcomeTitle.textContent = t.welcomeTitle;
        
        const welcomeMessage = document.querySelector('.ai-welcome-message .welcome-text p');
        if (welcomeMessage) welcomeMessage.textContent = t.welcomeMessage;
        
        const aiChatInput = document.getElementById('ai-chat-input');
        if (aiChatInput) aiChatInput.placeholder = t.askMindMatePlaceholder;
        
        // Update MindMate AI toolbar button
        const mindmateBtn = document.getElementById('mindmate-ai-btn');
        if (mindmateBtn) {
            const btnText = mindmateBtn.querySelector('span');
            if (btnText) btnText.textContent = t.mindMateAI;
        }
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
                // Show the opposite language (what you can switch TO)
                langText.textContent = this.currentLanguage === 'en' ? '中文' : 'EN';
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
     * Show notification using centralized notification manager
     */
    showNotification(message, type = 'info') {
        if (window.notificationManager) {
            window.notificationManager.show(message, type);
        } else {
            console.error('NotificationManager not available');
        }
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
    
    /**
     * Get notification message in current language
     * @param {string} key - Notification key (e.g., 'textEmpty', 'nodeAdded')
     * @param  {...any} args - Arguments for function-based notifications
     */
    getNotification(key, ...args) {
        const notif = this.translations[this.currentLanguage].notif[key];
        if (typeof notif === 'function') {
            return notif(...args);
        }
        return notif || key;
    }
}

// Initialize when DOM is ready
if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', () => {
        window.languageManager = new LanguageManager();
    });
}

