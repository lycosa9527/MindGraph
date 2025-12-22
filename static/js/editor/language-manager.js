/**
 * LanguageManager - Handles language switching and translations
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class LanguageManager {
    constructor() {
        // Get default language from .env (via window.DEFAULT_LANGUAGE) or localStorage, fallback to 'zh'
        const savedLang = localStorage.getItem('preferredLanguage');
        const defaultLang = window.DEFAULT_LANGUAGE || 'zh';
        this.currentLanguage = savedLang || defaultLang;
        
        // Ensure currentLanguage is one of the supported languages
        if (!['en', 'zh', 'az'].includes(this.currentLanguage)) {
            this.currentLanguage = defaultLang;
        }
        
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
                thinkingTools: 'Thinking Tools',
                comingSoon: 'Coming Soon',
                factorAnalysis: 'Factor Analysis',
                factorAnalysisDesc: 'Analyzing key factors',
                threePositionAnalysis: 'Three-Position Analysis',
                threePositionAnalysisDesc: 'Three perspectives',
                perspectiveAnalysis: 'Perspective Analysis',
                perspectiveAnalysisDesc: 'Understanding viewpoints',
                goalAnalysis: 'Goal Analysis',
                goalAnalysisDesc: 'Breaking down goals',
                possibilityAnalysis: 'Possibility Analysis',
                possibilityAnalysisDesc: 'Exploring options',
                resultAnalysis: 'Result Analysis',
                resultAnalysisDesc: 'Analyzing outcomes',
                fiveWOneH: '5W1H Analysis',
                fiveWOneHDesc: 'Systematic analysis',
                whwmAnalysis: 'WHWM Analysis',
                whwmAnalysisDesc: 'Project planning',
                fourQuadrant: 'Four Quadrant Analysis',
                fourQuadrantDesc: 'Categorizing items',
                selectButton: 'Select',
                backToGallery: 'Back to Gallery',
                reset: 'Reset',
                export: 'Export',
                exportTooltip: 'Export as PNG',
                save: 'Save',
                import: 'Import',
                fileGroup: 'File:',
                saveTooltip: 'Save as .mg file',
                importTooltip: 'Import .mg file',
                nodes: 'Edit',
                add: 'Add',
                delete: 'Delete',
                copy: 'Copy',
                auto: 'Auto',
                line: 'Line',
                learn: 'Learn',
                thinking: 'Node Palette',
                tools: 'Actions',
                empty: 'Empty',
                undo: 'Undo',
                redo: 'Redo',
                nodeCount: 'Nodes',
                editMode: 'Edit Mode: Active',
                resetView: 'Reset View',
                resetViewTitle: 'Fit diagram to window',
                nodePalette: 'Node Palette',
                // LLM Selector
                aiModel: 'AI Model',
                llmQwen: 'Qwen',
                llmQwenTooltip: 'Qwen (Fast & Reliable)',
                llmDeepSeek: 'DeepSeek',
                llmDeepSeekTooltip: 'DeepSeek-v3.1 (High Quality)',
                llmKimi: 'Kimi',
                llmKimiTooltip: 'Kimi (Moonshot AI)',
                llmDoubao: 'Doubao',
                llmDoubaoTooltip: 'Doubao/豆包 (Volcengine)',
                shareSuccess: 'Link copied to clipboard!',
                shareError: 'Unable to copy link. Please copy manually:',
                learningModeComingSoon: 'Learning Mode: Phase 1 in progress!',
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
                learningModeTooltip: 'Start Interactive Learning Mode',
                thinkingModeTooltip: 'Explore more node ideas with AI',
                nodePaletteTooltip: 'Open Node Palette to brainstorm nodes with AI',
                thinkingModeTitle: 'Node Palette',
                thinkingInputPlaceholder: 'Type your response...',
                // Node Palette UI
                nodePaletteSelected: 'Selected',
                nodePaletteCancel: 'Cancel',
                nodePaletteNext: 'Next',
                nodePaletteNextSelected: (count) => `Next (${count} selected)`,
                nodePaletteFinishSelection: 'Finish Selection',
                nodePaletteNextSelectDimension: '📐 Next: Select Dimension →',
                nodePaletteNextSelectCategories: '📂 Next: Select Categories →',
                nodePaletteNextSelectParts: '🧩 Next: Select Parts →',
                nodePaletteNextSelectBranches: '🌿 Next: Select Branches →',
                nodePaletteNextSelectSteps: '📝 Next: Select Steps →',
                nodePalettePairs: ' pairs',
                nodePaletteStage: (stageNum) => `Stage ${stageNum}: `,
                nodePaletteTabSimilarities: 'Similarities',
                nodePaletteTabDifferences: 'Differences',
                nodePaletteTabDimensions: 'Dimensions',
                nodePaletteTabCategories: 'Categories',
                nodePaletteTabChildren: 'Children',
                nodePaletteTabParts: 'Parts',
                nodePaletteTabSubparts: 'Subparts',
                nodePaletteTabBranches: 'Branches',
                nodePaletteTabSteps: 'Steps',
                nodePaletteTabSubsteps: 'Substeps',
                nodePaletteTabCauses: 'Causes',
                nodePaletteTabEffects: 'Effects',
                nodePaletteStage2GenerateCategories: 'Stage 2: Generate Categories',
                nodePaletteStage3AddItems: (count) => `Stage 3: Add Items to ${count} Categories`,
                nodePaletteStage2GenerateParts: 'Stage 2: Generate Parts',
                nodePaletteStage3AddSubparts: (count) => `Stage 3: Add Subparts to ${count} Parts`,
                nodePaletteStage2AddChildren: (count) => `Stage 2: Add Children to ${count} Branches`,
                // Learning Mode UI
                learningModeTitle: 'Learning Mode',
                learningModeProgress: (current, total) => `Question <strong>${current}</strong> of <strong>${total}</strong>`,
                learningModeFillIn: 'Fill in the missing node:',
                learningModeQuestionPrefix: 'What is the text for',
                learningModeQuestionSuffix: '?',
                learningModeContextHint: 'Hint: Look at the diagram structure and context',
                learningModeInputPlaceholder: 'Type your answer here...',
                learningModeSubmit: 'Submit',
                learningModeHint: 'Hint',
                learningModeExit: 'Exit Learning Mode',
                learningModeCorrect: 'Correct!',
                learningModeIncorrect: (correctAnswer) => `Not quite. The correct answer is: <strong>${correctAnswer}</strong>`,
                learningModeEnterAnswer: 'Please enter an answer',
                learningModeBasicHint: (firstChar, length) => `Hint: The answer starts with "<strong>${firstChar}</strong>" and has <strong>${length}</strong> characters.`,
                learningModeComplete: 'Learning Complete!',
                learningModeScore: (correct, total) => `You got <strong>${correct}</strong> out of <strong>${total}</strong> correct`,
                learningModeAccuracy: (accuracy) => `Accuracy: <strong>${accuracy}%</strong>`,
                learningModeFinish: 'Finish',
                // Learning Material Modal
                learningMaterialTitle: "Let's Learn This Concept!",
                learningMaterialAcknowledgment: 'Acknowledgment',
                learningMaterialContrast: 'Key Difference',
                learningMaterialVisualAid: 'Visual Aid',
                learningMaterialAnalogy: 'Analogy',
                learningMaterialKeyPrinciple: 'Key Principle',
                learningMaterialUnderstand: 'I Understand',
                learningMaterialContinue: 'Continue',
                learningMaterialClose: 'Close',
                // Phase 4: Verification & Escalation
                verificationTitle: 'Let\'s Verify Your Understanding',
                skipQuestion: 'Skip',
                emptyNodeTooltip: 'Empty selected node text',
                undoTooltip: 'Undo',
                redoTooltip: 'Redo',
                switchLanguageTooltip: 'Switch Language',
                share: 'Share',
                shareTooltip: 'Share',
                logout: 'Logout',
                logoutTooltip: 'Logout',
                gallery: 'Gallery',
                galleryTooltip: 'Gallery',
                admin: 'Admin',
                adminTooltip: 'Admin Panel',
                feedback: 'Feedback',
                feedbackTooltip: 'Send Feedback',
                feedbackTitle: 'Send Feedback',
                feedbackSubtitle: 'Report bugs, suggest features, or share your thoughts',
                feedbackType: 'Type',
                feedbackTypeBug: 'Bug Report',
                feedbackTypeFeature: 'Feature Request',
                feedbackTypeIssue: 'Issue Report',
                feedbackTypeOther: 'Other',
                feedbackMessage: 'Message',
                feedbackMessagePlaceholder: 'Please describe your feedback in detail...',
                feedbackSubmit: 'Submit',
                feedbackCancel: 'Cancel',
                feedbackSuccess: 'Thank you! Your feedback has been sent successfully.',
                feedbackError: 'Failed to send feedback. Please try again later.',
                feedbackRequired: 'Please fill in all required fields.',
                boldTooltip: 'Bold',
                italicTooltip: 'Italic',
                underlineTooltip: 'Underline',
                strikethroughTooltip: 'Strikethrough',
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
                fontFamily: 'Font Family',
                textStyle: 'Text Style',
                textColor: 'Text Color',
                fillColor: 'Fill Color',
                strokeColor: 'Stroke Color',
                strokeWidth: 'Stroke Width',
                colors: 'Colors',
                textColorLabel: 'Text',
                fillColorLabel: 'Fill',
                strokeColorLabel: 'Stroke',
                opacity: 'Opacity',
                applyAllChanges: 'Apply All Changes',
                // MindMate AI Panel (uses configurable name from backend)
                mindMateAI: window.AI_ASSISTANT_NAME || 'MindMate AI',
                online: 'Online',
                welcomeTitle: `Welcome to ${window.AI_ASSISTANT_NAME || 'MindMate AI'}!`,
                welcomeMessage: "I'm here to help you with your diagrams. Ask me anything about creating, editing, or improving your work.",
                askMindMatePlaceholder: `Ask ${window.AI_ASSISTANT_NAME || 'MindMate'} anything...`,
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
                    multiLLMReady: (count, total, modelName) => `${count}/${total} models ready. Showing ${modelName}. Click buttons to switch.`,
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
                    noDiagramToSave: 'No diagram to save!',
                    diagramSaved: 'Diagram saved as .mg file!',
                    saveFailed: 'Failed to save diagram',
                    importSuccess: 'Diagram imported successfully!',
                    importFailed: 'Failed to import diagram',
                    invalidFileFormat: 'Invalid file format',
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
                    cannotDeleteCentralTopic: 'Cannot delete the central topic',
                    // System errors
                    aiPanelNotFound: 'AI Assistant panel not found. Please reload the page.',
                    editorLoadError: 'Error loading editor. Please try again.',
                    clearHistoryConfirm: 'Clear all history?',
                    // Version update
                    newVersionAvailable: (version) => `New version available (${version}). Click here to refresh.`,
                    newVersionConfirm: (version) => `A new version (${version}) is available. Refresh now?`
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
                mindMapDesc: '概念梳理',
                conceptMap: '概念图',
                conceptMapDesc: '概念关系',
                thinkingTools: '思维工具',
                comingSoon: '即将推出',
                factorAnalysis: '因素分析法',
                factorAnalysisDesc: '分析关键因素',
                threePositionAnalysis: '三位分析法',
                threePositionAnalysisDesc: '三个视角',
                perspectiveAnalysis: '换位分析法',
                perspectiveAnalysisDesc: '理解不同视角',
                goalAnalysis: '目标分析法',
                goalAnalysisDesc: '分解目标',
                possibilityAnalysis: '可能分析法',
                possibilityAnalysisDesc: '探索选项',
                resultAnalysis: '结果分析法',
                resultAnalysisDesc: '分析结果',
                fiveWOneH: '六何分析法',
                fiveWOneHDesc: '系统分析',
                whwmAnalysis: 'WHWM分析法',
                whwmAnalysisDesc: '项目规划',
                fourQuadrant: '四象限分析法',
                fourQuadrantDesc: '项目分类',
                selectButton: '选择',
                backToGallery: '返回图库',
                reset: '重置',
                export: '导出为图片',
                exportTooltip: '导出为 PNG',
                save: '保存文件',
                import: '打开文件',
                fileGroup: '文件:',
                saveTooltip: '保存为 .mg 文件',
                importTooltip: '导入 .mg 文件',
                nodes: '编辑',
                add: '添加',
                delete: '删除',
                copy: '复制',
                auto: '自动',
                line: '线稿',
                learn: '学习',
                thinking: '瀑布流',
                tools: '操作',
                empty: '清空',
                undo: '撤销',
                redo: '重做',
                nodeCount: '节点',
                editMode: '编辑模式：激活',
                resetView: '重置视图',
                resetViewTitle: '将图表适应窗口',
                nodePalette: '瀑布流',
                // LLM Selector
                aiModel: 'AI模型',
                llmQwen: 'Qwen',
                llmQwenTooltip: 'Qwen（快速可靠）',
                llmDeepSeek: 'DeepSeek',
                llmDeepSeekTooltip: 'DeepSeek-v3.1（高质量）',
                llmKimi: 'Kimi',
                llmKimiTooltip: 'Kimi（月之暗面）',
                llmDoubao: '豆包',
                llmDoubaoTooltip: '豆包（火山引擎）',
                shareSuccess: '链接已复制到剪贴板！',
                shareError: '无法复制链接，请手动复制：',
                learningModeComingSoon: '学习模式：第一阶段开发中！',
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
                learningModeTooltip: '开始交互式学习模式',
                thinkingModeTooltip: '使用AI探索更多节点想法',
                nodePaletteTooltip: '打开瀑布流，AI为您头脑风暴更多节点',
                thinkingModeTitle: '瀑布流',
                thinkingInputPlaceholder: '输入你的回答...',
                // Node Palette UI | 节点选择板界面
                nodePaletteSelected: '已选择',
                nodePaletteCancel: '取消',
                nodePaletteNext: '下一步',
                nodePaletteNextSelected: (count) => `下一步 (已选择 ${count})`,
                nodePaletteFinishSelection: '完成选择',
                nodePaletteNextSelectDimension: '📐 下一步：选择维度 →',
                nodePaletteNextSelectCategories: '📂 下一步：选择类别 →',
                nodePaletteNextSelectParts: '🧩 下一步：选择部分 →',
                nodePaletteNextSelectBranches: '🌿 下一步：选择分支 →',
                nodePaletteNextSelectSteps: '📝 下一步：选择步骤 →',
                nodePalettePairs: '对',
                nodePaletteStage: (stageNum) => `阶段 ${stageNum}：`,
                nodePaletteTabSimilarities: '相似点',
                nodePaletteTabDifferences: '差异点',
                nodePaletteTabDimensions: '维度',
                nodePaletteTabCategories: '类别',
                nodePaletteTabChildren: '子项',
                nodePaletteTabParts: '部分',
                nodePaletteTabSubparts: '子部分',
                nodePaletteTabBranches: '分支',
                nodePaletteTabSteps: '步骤',
                nodePaletteTabSubsteps: '子步骤',
                nodePaletteTabCauses: '原因',
                nodePaletteTabEffects: '结果',
                nodePaletteStage2GenerateCategories: '阶段 2：生成类别',
                nodePaletteStage3AddItems: (count) => `阶段 3：向 ${count} 个类别添加项目`,
                nodePaletteStage2GenerateParts: '阶段 2：生成部分',
                nodePaletteStage3AddSubparts: (count) => `阶段 3：向 ${count} 个部分添加子部分`,
                nodePaletteStage2AddChildren: (count) => `阶段 2：向 ${count} 个分支添加子项`,
                // Learning Mode UI | 学习模式界面
                learningModeTitle: '学习模式',
                learningModeProgress: (current, total) => `问题 <strong>${current}</strong> / <strong>${total}</strong>`,
                learningModeFillIn: '填写缺失的节点：',
                learningModeQuestionPrefix: '请填写',
                learningModeQuestionSuffix: '的文本内容',
                learningModeContextHint: '提示：观察图示结构和上下文',
                learningModeInputPlaceholder: '在此输入答案...',
                learningModeSubmit: '提交',
                learningModeHint: '提示',
                learningModeExit: '退出学习模式',
                learningModeCorrect: '正确！',
                learningModeIncorrect: (correctAnswer) => `不完全正确。正确答案是：<strong>${correctAnswer}</strong>`,
                learningModeEnterAnswer: '请输入答案',
                learningModeBasicHint: (firstChar, length) => `提示：答案以"<strong>${firstChar}</strong>"开头，共 <strong>${length}</strong> 个字符。`,
                learningModeComplete: '学习完成！',
                learningModeScore: (correct, total) => `您答对了 <strong>${correct}</strong> / <strong>${total}</strong> 题`,
                learningModeAccuracy: (accuracy) => `准确率：<strong>${accuracy}%</strong>`,
                learningModeFinish: '完成',
                // Learning Material Modal | 学习材料弹窗
                learningMaterialTitle: '让我们一起学习这个概念！',
                learningMaterialAcknowledgment: '理解你的想法',
                learningMaterialContrast: '关键区别',
                learningMaterialVisualAid: '视觉辅助',
                learningMaterialAnalogy: '类比',
                learningMaterialKeyPrinciple: '核心原则',
                learningMaterialUnderstand: '我明白了',
                learningMaterialContinue: '继续',
                learningMaterialClose: '关闭',
                // Phase 4: Verification & Escalation | 阶段4：验证与升级
                verificationTitle: '让我们验证一下你的理解',
                skipQuestion: '跳过',
                emptyNodeTooltip: '清空选中节点文本',
                undoTooltip: '撤销',
                redoTooltip: '重做',
                switchLanguageTooltip: '切换语言',
                share: '分享',
                shareTooltip: '分享',
                logout: '注销',
                logoutTooltip: '注销登录',
                gallery: '图库',
                galleryTooltip: '图库',
                admin: '后台',
                adminTooltip: '管理后台',
                feedback: '反馈',
                feedbackTooltip: '发送反馈',
                feedbackTitle: '发送反馈',
                feedbackSubtitle: '报告错误、建议功能或分享您的想法',
                feedbackType: '类型',
                feedbackTypeBug: '错误报告',
                feedbackTypeFeature: '功能建议',
                feedbackTypeIssue: '问题报告',
                feedbackTypeOther: '其他',
                feedbackMessage: '消息',
                feedbackMessagePlaceholder: '请详细描述您的反馈...',
                feedbackSubmit: '提交',
                feedbackCancel: '取消',
                feedbackSuccess: '谢谢！您的反馈已成功发送。',
                feedbackError: '发送反馈失败。请稍后重试。',
                feedbackRequired: '请填写所有必填字段。',
                boldTooltip: '粗体',
                italicTooltip: '斜体',
                underlineTooltip: '下划线',
                strikethroughTooltip: '删除线',
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
                fontFamily: '字体',
                textStyle: '文字样式',
                textColor: '文本颜色',
                fillColor: '填充颜色',
                strokeColor: '边框颜色',
                strokeWidth: '边框宽度',
                colors: '颜色',
                textColorLabel: '文字',
                fillColorLabel: '填充',
                strokeColorLabel: '边框',
                opacity: '透明度',
                applyAllChanges: '应用所有更改',
                // MindMate AI Panel (uses configurable name from backend)
                mindMateAI: window.AI_ASSISTANT_NAME || 'MindMate AI',
                online: '在线',
                welcomeTitle: `欢迎使用${window.AI_ASSISTANT_NAME || 'MindMate AI'}！`,
                welcomeMessage: '我在这里帮助您创建图示。随时询问有关创建、编辑或改进您作品的任何问题。',
                askMindMatePlaceholder: `向${window.AI_ASSISTANT_NAME || 'MindMate AI'}提出任何问题...`,
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
                    multiLLMReady: (count, total, modelName) => `${count}/${total} 个模型就绪。正在显示 ${modelName}。点击按钮切换。`,
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
                    noDiagramToSave: '没有可保存的图示！',
                    diagramSaved: '图表已保存为 .mg 文件！',
                    saveFailed: '保存图表失败',
                    importSuccess: '图表导入成功！',
                    importFailed: '图表导入失败',
                    invalidFileFormat: '无效的文件格式',
                    // Interactive Editor Notifications
                    couldNotDetermineNodeType: '无法确定节点类型。请重试。',
                    cannotAddMainTopics: '无法添加主主题。请选择相似或不同点节点。',
                    unknownNodeType: '未知节点类型。请选择相似或不同点节点。',
                    similarityNodeAdded: '相似节点已添加！',
                    differencePairAdded: '不同点对已添加！',
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
                    cannotDeleteCentralTopic: '无法删除中心主题',
                    // System errors
                    aiPanelNotFound: '未找到AI助手面板。请刷新页面。',
                    editorLoadError: '加载编辑器错误。请重试。',
                    clearHistoryConfirm: '确定要清除所有历史记录吗？',
                    // Version update
                    newVersionAvailable: (version) => `新版本已发布 (${version})。点击此处刷新。`,
                    newVersionConfirm: (version) => `新版本 (${version}) 已发布，是否立即刷新？`
                }
            },
            az: {
                mainTitle: 'MindGraph Pro',
                mainSubtitle: 'Kainatın ən güclü AI diaqram yaratma proqramı',
                promptPlaceholder: 'Diaqramınızı təsvir edin və ya aşağıdakı şablonlardan seçin...',
                recentPrompts: 'Son İstəklər',
                clearHistory: 'Təmizlə',
                noRecentPrompts: 'Heç bir son istək yoxdur',
                thinkingMaps: 'Düşüncə Xəritələri',
                advancedDiagrams: 'Qabaqcıl Diaqramlar',
                circleMap: 'Dairə Xəritəsi',
                circleMapDesc: 'Assosiasiya, beyin fırtınası',
                bubbleMap: 'Baloncuk Xəritəsi',
                bubbleMapDesc: 'Xüsusiyyətləri təsvir etmək',
                doubleBubbleMap: 'İkili Baloncuk Xəritəsi',
                doubleBubbleMapDesc: 'Müqayisə və ziddiyyət',
                treeMap: 'Ağac Xəritəsi',
                treeMapDesc: 'Təsnif etmək və kateqoriyalamaq',
                braceMap: 'Qığırcaq Xəritəsi',
                braceMapDesc: 'Bütöv və hissələr',
                flowMap: 'Axın Xəritəsi',
                flowMapDesc: 'Ardıcıllıq və addımlar',
                multiFlowMap: 'Çoxlu Axın Xəritəsi',
                multiFlowMapDesc: 'Səbəb və nəticə analizi',
                bridgeMap: 'Körpü Xəritəsi',
                bridgeMapDesc: 'Analog əsaslandırma',
                mindMap: 'Düşüncə Xəritəsi',
                mindMapDesc: 'Səbəb və nəticə analizi',
                conceptMap: 'Konsepsiya Xəritəsi',
                conceptMapDesc: 'Konseptual əlaqələr',
                thinkingTools: 'Düşüncə Alətləri',
                comingSoon: 'Tezliklə',
                factorAnalysis: 'Faktor Analizi',
                factorAnalysisDesc: 'Əsas amilləri analiz etmək',
                threePositionAnalysis: 'Üç Mövqe Analizi',
                threePositionAnalysisDesc: 'Üç baxış bucağı',
                perspectiveAnalysis: 'Perspektiv Analizi',
                perspectiveAnalysisDesc: 'Baxış bucaqlarını anlamaq',
                goalAnalysis: 'Hədəf Analizi',
                goalAnalysisDesc: 'Hədəfləri parçalamaq',
                possibilityAnalysis: 'Ehtimal Analizi',
                possibilityAnalysisDesc: 'Seçimləri araşdırmaq',
                resultAnalysis: 'Nəticə Analizi',
                resultAnalysisDesc: 'Nəticələri analiz etmək',
                fiveWOneH: '5W1H Analizi',
                fiveWOneHDesc: 'Sistemli analiz',
                whwmAnalysis: 'WHWM Analizi',
                whwmAnalysisDesc: 'Layihə planlaşdırması',
                fourQuadrant: 'Dörd Kvadrant Analizi',
                fourQuadrantDesc: 'Elementləri kateqoriyalamaq',
                selectButton: 'Seç',
                backToGallery: 'Qalereya',
                reset: 'Sıfırla',
                export: 'İxrac Et',
                exportTooltip: 'PNG kimi ixrac et',
                save: 'Saxla',
                import: 'İdxal',
                fileGroup: 'Fayl:',
                saveTooltip: '.mg faylı kimi saxla',
                importTooltip: '.mg faylı idxal et',
                nodes: 'Redaktə',
                add: 'Əlavə',
                delete: 'Sil',
                copy: 'Kopyala',
                auto: 'Avto',
                line: 'Xətt',
                learn: 'Öyrən',
                thinking: 'Düşüncə',
                tools: 'Əməliyyat',
                empty: 'Boşalt',
                undo: 'Geri Al',
                redo: 'Təkrar',
                nodeCount: 'Düyünlər',
                editMode: 'Redaktə Rejimi: Aktiv',
                resetView: 'Sıfırla',
                resetViewTitle: 'Diaqramı pəncərəyə uyğunlaşdır',
                nodePalette: 'Palet',
                // LLM Selector
                aiModel: 'AI Modeli',
                llmQwen: 'Qwen',
                llmQwenTooltip: 'Qwen (Sürətli və Etibarlı)',
                llmDeepSeek: 'DeepSeek',
                llmDeepSeekTooltip: 'DeepSeek-v3.1 (Yüksək Keyfiyyət)',
                llmKimi: 'Kimi',
                llmKimiTooltip: 'Kimi (Moonshot AI)',
                shareSuccess: 'Link panoya kopyalandı!',
                shareError: 'Linki kopyalamaq mümkün deyil. Xahiş edirik əl ilə kopyalayın:',
                learningModeComingSoon: 'Öyrənmə Rejimi: Mərhələ 1 işləyir!',
                languageButton: 'AZ',
                // Dynamic node text for adding new nodes
                newAttribute: 'Yeni Atribut',
                newStep: 'Yeni Addım',
                newCause: 'Yeni Səbəb',
                newEffect: 'Yeni Nəticə',
                newBranch: 'Yeni Qol',
                newNode: 'Yeni Düyün',
                newItem: 'Yeni Element',
                newCategory: 'Yeni Kateqoriya',
                newSubitem: 'Yeni Alt Element',
                newConcept: 'Yeni Konsept',
                newRelation: 'əlaqəlidir',
                // Tooltips
                addNodeTooltip: 'Düyün Əlavə Et',
                deleteNodeTooltip: 'Seçilmişləri Sil',
                autoCompleteTooltip: 'AI ilə diaqramı avtomatik tamamla',
                lineModeTooltip: 'Qara və ağ xətt rejimini dəyişdir',
                learningModeTooltip: 'İnteraktiv Öyrənmə Rejimini Başlat',
                thinkingModeTooltip: 'Sokrat Düşüncə Rejimini Başlat',
                nodePaletteTooltip: 'Düyün Paletini açın, AI sizə daha çox düyün yaradacaq',
                thinkingModeTitle: 'Düşüncə Bələdçisi - Düşüncə Bələdçisi',
                thinkingInputPlaceholder: 'Cavabınızı yazın...',
                // Learning Mode UI
                learningModeTitle: 'Öyrənmə Rejimi',
                learningModeProgress: (current, total) => `Sual <strong>${current}</strong> / <strong>${total}</strong>`,
                learningModeFillIn: 'Çatışmayan düyünü doldurun:',
                learningModeQuestionPrefix: 'Mətn nədir',
                learningModeQuestionSuffix: '?',
                learningModeContextHint: 'İpucu: Diaqram strukturuna və kontekstə baxın',
                learningModeInputPlaceholder: 'Cavabınızı buraya yazın...',
                learningModeSubmit: 'Göndər',
                learningModeHint: 'İpucu',
                learningModeExit: 'Çıx',
                learningModeCorrect: 'Düzgündür!',
                learningModeIncorrect: (correctAnswer) => `Tam düzgün deyil. Düzgün cavab: <strong>${correctAnswer}</strong>`,
                learningModeEnterAnswer: 'Xahiş edirik cavab daxil edin',
                learningModeBasicHint: (firstChar, length) => `İpucu: Cavab "<strong>${firstChar}</strong>" ilə başlayır və <strong>${length}</strong> simvoldan ibarətdir.`,
                learningModeComplete: 'Öyrənmə Tamamlandı!',
                learningModeScore: (correct, total) => `Siz <strong>${correct}</strong> / <strong>${total}</strong> düzgün cavab verdiniz`,
                learningModeAccuracy: (accuracy) => `Düzgünlük: <strong>${accuracy}%</strong>`,
                learningModeFinish: 'Bitir',
                // Learning Material Modal
                learningMaterialTitle: 'Gəlin bu konsepti öyrənək!',
                learningMaterialAcknowledgment: 'Anlayışınızı qəbul edirik',
                learningMaterialContrast: 'Əsas Fərq',
                learningMaterialVisualAid: 'Vizual Kömək',
                learningMaterialAnalogy: 'Analoji',
                learningMaterialKeyPrinciple: 'Əsas Prinsip',
                learningMaterialUnderstand: 'Başa Düşürəm',
                learningMaterialContinue: 'Davam Et',
                learningMaterialClose: 'Bağla',
                // Phase 4: Verification & Escalation
                verificationTitle: 'Gəlin anlayışınızı yoxlayaq',
                skipQuestion: 'Keç',
                emptyNodeTooltip: 'Seçilmiş düyün mətnini boşalt',
                undoTooltip: 'Geri Al',
                redoTooltip: 'Təkrar Et',
                switchLanguageTooltip: 'Dili Dəyişdir',
                share: 'Paylaş',
                shareTooltip: 'Paylaş',
                logout: 'Çıxış',
                logoutTooltip: 'Çıxış',
                gallery: 'Qalereya',
                galleryTooltip: 'Qalereya',
                admin: '后台',
                adminTooltip: 'Admin Paneli',
                feedback: 'Rəy',
                feedbackTooltip: 'Rəy',
                feedbackTitle: 'Rəy Göndər',
                feedbackSubtitle: 'Xətaları bildirin, funksiya təklif edin və ya düşüncələrinizi paylaşın',
                feedbackType: 'Növ',
                feedbackTypeBug: 'Xəta Hesabatı',
                feedbackTypeFeature: 'Funksiya Təklifi',
                feedbackTypeIssue: 'Məsələ Hesabatı',
                feedbackTypeOther: 'Digər',
                feedbackMessage: 'Mesaj',
                feedbackMessagePlaceholder: 'Xahiş edirik rəyinizi ətraflı təsvir edin...',
                feedbackSubmit: 'Göndər',
                feedbackCancel: 'Ləğv Et',
                feedbackSuccess: 'Təşəkkürlər! Rəyiniz uğurla göndərildi.',
                feedbackError: 'Rəy göndərilmədi. Xahiş edirik daha sonra yenidən cəhd edin.',
                feedbackRequired: 'Xahiş edirik bütün tələb olunan sahələri doldurun.',
                boldTooltip: 'Qalın',
                italicTooltip: 'İtalik',
                underlineTooltip: 'Altı Xətt',
                strikethroughTooltip: 'Üstündən Xətt',
                closeTooltip: 'Bağla',
                // Node Editor
                editNodeContent: 'Redaktə Et',
                characters: 'simvollar',
                cancel: 'Ləğv Et',
                saveChanges: 'Saxla',
                // Properties Panel
                properties: 'Xüsusiyyətlər',
                text: 'Mətn',
                nodeTextPlaceholder: 'Düyün mətni',
                apply: 'Tətbiq Et',
                resetStyles: 'Sıfırla',
                fontSize: 'Şrift Ölçüsü',
                fontFamily: 'Şrift',
                textStyle: 'Mətn Üslubu',
                textColor: 'Mətn Rəngi',
                fillColor: 'Doldurma Rəngi',
                strokeColor: 'Kontur Rəngi',
                strokeWidth: 'Kontur Genişliyi',
                colors: 'Rənglər',
                textColorLabel: 'Mətn',
                fillColorLabel: 'Doldurma',
                strokeColorLabel: 'Kontur',
                opacity: 'Şəffaflıq',
                applyAllChanges: 'Hamısını Tətbiq',
                // MindMate AI Panel (uses configurable name from backend)
                mindMateAI: window.AI_ASSISTANT_NAME || 'MindMate AI',
                online: 'Onlayn',
                welcomeTitle: `${window.AI_ASSISTANT_NAME || 'MindMate AI'}-a xoş gəlmisiniz!`,
                welcomeMessage: 'Mən burada diaqramlarınızda kömək etmək üçün buradayam. Yaratma, redaktə etmə və ya işinizi təkmilləşdirmə ilə bağlı hər şeyi soruşa bilərsiniz.',
                askMindMatePlaceholder: `${window.AI_ASSISTANT_NAME || 'MindMate'}-dən hər şeyi soruşun...`,
                // Notification Messages
                notif: {
                    textEmpty: 'Mətn boş ola bilməz',
                    textUpdated: 'Mətn uğurla yeniləndi',
                    propertiesApplied: 'Bütün xüsusiyyətlər uğurla tətbiq edildi!',
                    editorNotInit: 'Redaktor işə salınmayıb',
                    selectNodeToAdd: 'Əlavə etmək üçün əvvəlcə bir düyün seçin',
                    nodeAdded: 'Düyün əlavə edildi! Mətn redaktə etmək üçün iki dəfə klikləyin.',
                    nodesDeleted: (count) => `${count} düyün silindi`,
                    selectNodeToDelete: 'Silmək üçün əvvəlcə bir düyün seçin',
                    nodesEmptied: (count) => `${count} düyün boşaldıldı`,
                    selectNodeToEmpty: 'Boşaltmaq üçün əvvəlcə bir düyün seçin',
                    addNodesFirst: 'Avtomatik istifadə etmədən əvvəl xahiş edirik bir neçə düyün əlavə edin',
                    aiCompleting: (topic) => `AI "${topic}" haqqında diaqramı tamamlayır...`,
                    diagramChanged: 'Avtomatik tamamlama zamanı diaqram dəyişdirildi',
                    sessionChanged: 'Avtomatik tamamlama zamanı sessiya dəyişdirildi',
                    autoCompleteSuccess: 'Diaqram avtomatik olaraq uğurla tamamlandı!',
                    autoCompleteFailed: (error) => `Avtomatik tamamlama uğursuz oldu: ${error}`,
                    multiLLMReady: (count, total, modelName) => `${count}/${total} model hazırdır. ${modelName} göstərilir. Dəyişdirmək üçün düymələrə klikləyin.`,
                    lineModeEnabled: 'Xətt rejimi aktivləşdirildi',
                    lineModeDisabled: 'Xətt rejimi deaktivləşdirildi',
                    duplicateComingSoon: 'Düyün təkrarlama funksiyası tezliklə!',
                    resetFailed: 'Sıfırlama uğursuz oldu: diaqram seçici tapılmadı',
                    templateNotFound: 'Sıfırlama uğursuz oldu: şablon tapılmadı',
                    canvasReset: 'Kətan boş şablona sıfırlandı',
                    resetConfirm: 'Kətanı boş şablona sıfırlamağa əminsiniz? Bütün cari dəyişikliklər itiriləcək.',
                    noDiagramToExport: 'İxrac ediləcək diaqram yoxdur!',
                    diagramExported: 'Diaqram PNG kimi ixrac edildi!',
                    exportFailed: 'Diaqramı ixrac etmək mümkün olmadı',
                    noDiagramToSave: 'Saxlanılacaq diaqram yoxdur!',
                    diagramSaved: 'Diaqram .mg faylı kimi saxlanıldı!',
                    saveFailed: 'Diaqramı saxlamaq mümkün olmadı',
                    importSuccess: 'Diaqram uğurla idxal edildi!',
                    importFailed: 'Diaqramı idxal etmək mümkün olmadı',
                    invalidFileFormat: 'Yanlış fayl formatı',
                    // Interactive Editor Notifications
                    couldNotDetermineNodeType: 'Düyün növünü müəyyən etmək mümkün olmadı. Xahiş edirik yenidən cəhd edin.',
                    cannotAddMainTopics: 'Əsas mövzular əlavə edilə bilməz. Xahiş edirik oxşar və ya fərq düyünü seçin.',
                    unknownNodeType: 'Naməlum düyün növü. Xahiş edirik oxşar və ya fərq düyünü seçin.',
                    similarityNodeAdded: 'Oxşarlıq düyünü əlavə edildi!',
                    differencePairAdded: 'Fərq cütü əlavə edildi!',
                    invalidPartIndex: 'Etibarsız hissə indeksi',
                    cannotAddToTopic: 'Mövzuya əlavə edilə bilməz. Xahiş edirik hissə və ya alt hissə düyünü seçin.',
                    unknownNodeSelectPart: 'Naməlum düyün növü. Xahiş edirik hissə və ya alt hissə düyünü seçin.',
                    invalidStepIndex: 'Etibarsız addım indeksi',
                    invalidSubstepIndex: 'Etibarsız alt addım indeksi',
                    cannotAddToTitle: 'Başlığa əlavə edilə bilməz. Xahiş edirik addım və ya alt addım düyünü seçin.',
                    selectStepOrSubstep: 'Xahiş edirik addım və ya alt addım düyünü seçin',
                    cannotAddToEvent: 'Hadisəyə əlavə edilə bilməz. Xahiş edirik səbəb və ya nəticə düyünü seçin.',
                    selectCauseOrEffect: 'Xahiş edirik səbəb və ya nəticə düyünü seçin',
                    cannotAddToTopicSelectCategory: 'Mövzuya əlavə edilə bilməz. Xahiş edirik kateqoriya və ya uşaq düyünü seçin.',
                    selectCategoryOrChild: 'Xahiş edirik kateqoriya və ya uşaq düyünü seçin',
                    selectBranchOrSubitem: 'Əlavə etmək üçün qol və ya alt element seçin',
                    cannotAddToCentral: 'Mərkəzi mövzuya əlavə edilə bilməz. Xahiş edirik qol və ya alt element seçin.',
                    invalidBranchIndex: 'Etibarsız qol indeksi',
                    newSubitemAdded: 'Yeni alt element əlavə edildi!',
                    unknownNodeSelectBranch: 'Naməlum düyün növü. Xahiş edirik qol və ya alt element seçin.',
                    updatingLayout: 'Düzən yenilənir...',
                    layoutUpdateFailed: 'Düzən yeniləməsi uğursuz oldu. Dəyişikliklər görünməyə bilər.',
                    cannotDeleteTitle: 'Başlığı silmək mümkün deyil',
                    cannotDeleteCentralEvent: 'Mərkəzi hadisəni silmək mümkün deyil',
                    cannotDeleteRootTopic: 'Kök mövzunu silmək mümkün deyil',
                    cannotDeleteFirstAnalogy: 'İlk analoji cütü silmək mümkün deyil',
                    cannotDeleteCentralTopic: 'Mərkəzi mövzunu silmək mümkün deyil',
                    // System errors
                    aiPanelNotFound: 'AI Köməkçi paneli tapılmadı. Xahiş edirik səhifəni yeniləyin.',
                    editorLoadError: 'Redaktor yüklənərkən xəta. Xahiş edirik yenidən cəhd edin.',
                    clearHistoryConfirm: 'Bütün tarixçəni təmizləmək istəyirsiniz?',
                    // Version update
                    newVersionAvailable: (version) => `Yeni versiya mövcuddur (${version}). Yeniləmək üçün bura klikləyin.`,
                    newVersionConfirm: (version) => `Yeni versiya (${version}) mövcuddur. İndi yeniləmək istəyirsiniz?`
                }
            }
        };
        
        this.initializeEventListeners();
        // Apply initial translations
        this.applyTranslations();
    }
    
    /**
     * Initialize event listeners
     */
    initializeEventListeners() {
        // Desktop/main buttons
        const langToggle = document.getElementById('language-toggle');
        const adminBtn = document.getElementById('admin-btn');
        const feedbackBtn = document.getElementById('feedback-btn');
        const logoutBtn = document.getElementById('logout-btn');
        
        // Add language toggle listener
        if (langToggle) {
            langToggle.addEventListener('click', () => {
                this.toggleLanguage();
            });
        }
        
        // Add admin button listener
        if (adminBtn) {
            adminBtn.addEventListener('click', () => {
                window.location.href = '/admin';
            });
        }
        
        // Add feedback button listener
        if (feedbackBtn) {
            feedbackBtn.addEventListener('click', () => {
                this.showFeedbackModal();
            });
        }
        
        // Add logout button listener
        if (logoutBtn) {
            logoutBtn.addEventListener('click', () => {
                if (typeof auth !== 'undefined') {
                    auth.logout();
                } else {
                    // Fallback if auth helper not loaded
                    localStorage.clear();
                    window.location.href = '/auth';
                }
            });
        }
    }
    
    /**
     * Toggle between English, Chinese, and Azerbaijani
     * Cycles: en -> zh -> az -> en
     */
    toggleLanguage() {
        const languages = ['en', 'zh', 'az'];
        const currentIndex = languages.indexOf(this.currentLanguage);
        const nextIndex = (currentIndex + 1) % languages.length;
        this.currentLanguage = languages[nextIndex];
        
        this.applyTranslations();
        this.updateLanguageButton();
        
        // Save to localStorage
        localStorage.setItem('preferredLanguage', this.currentLanguage);
        
        // Dispatch language change event for other managers
        window.dispatchEvent(new CustomEvent('languageChanged', {
            detail: { language: this.currentLanguage }
        }));
        
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
                logger.debug('LanguageManager', 'Refreshing diagram', {
                    type: currentDiagramType,
                    language: this.currentLanguage
                });
                
                // Get fresh template in new language
                const freshTemplate = window.diagramSelector.getTemplate(currentDiagramType);
                
                // Update the editor's spec and re-render
                if (freshTemplate) {
                    window.interactiveEditor.currentSpec = freshTemplate;
                    window.interactiveEditor.renderDiagram();
                    
                // Show notification
                const refreshMessages = {
                    'en': 'Template refreshed in English',
                    'zh': '模板已刷新为中文',
                    'az': 'Şablon İngiliscə yeniləndi'
                };
                this.showNotification(
                    refreshMessages[this.currentLanguage] || refreshMessages['en'],
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
        
        if (promptInput) {
            promptInput.placeholder = t.promptPlaceholder;
            // Enable scrolling placeholder for mobile if text is long
            this.enableScrollingPlaceholder(promptInput, t.promptPlaceholder);
        }
        if (historyToggleText) historyToggleText.textContent = t.recentPrompts;
        if (historyHeaderText) historyHeaderText.textContent = t.recentPrompts;
        if (emptyHistoryText) emptyHistoryText.textContent = t.noRecentPrompts;
        if (clearHistoryBtn) clearHistoryBtn.textContent = t.clearHistory;
        
        // Update category headers
        const categories = document.querySelectorAll('.diagram-category h2');
        if (categories.length >= 1) categories[0].textContent = t.thinkingMaps;
        if (categories.length >= 2) categories[1].textContent = t.advancedDiagrams;
        
        // Update Thinking Tools header with badge
        if (categories.length >= 3) {
            const thinkingToolsHeader = categories[2];
            thinkingToolsHeader.innerHTML = `
                ${t.thinkingTools}
                <span class="coming-soon-badge">${t.comingSoon}</span>
            `;
        }
        
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
        
        // Update diagram cards - Thinking Tools
        this.updateDiagramCard('factor_analysis', t.factorAnalysis, t.factorAnalysisDesc);
        this.updateDiagramCard('three_position_analysis', t.threePositionAnalysis, t.threePositionAnalysisDesc);
        this.updateDiagramCard('perspective_analysis', t.perspectiveAnalysis, t.perspectiveAnalysisDesc);
        this.updateDiagramCard('goal_analysis', t.goalAnalysis, t.goalAnalysisDesc);
        this.updateDiagramCard('possibility_analysis', t.possibilityAnalysis, t.possibilityAnalysisDesc);
        this.updateDiagramCard('result_analysis', t.resultAnalysis, t.resultAnalysisDesc);
        this.updateDiagramCard('five_w_one_h', t.fiveWOneH, t.fiveWOneHDesc);
        this.updateDiagramCard('whwm_analysis', t.whwmAnalysis, t.whwmAnalysisDesc);
        this.updateDiagramCard('four_quadrant', t.fourQuadrant, t.fourQuadrantDesc);
        
        // Update toolbar buttons (if in editor view)
        const backBtn = document.getElementById('back-to-gallery');
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
        if (exportBtn) {
            exportBtn.textContent = t.export;
            exportBtn.title = t.exportTooltip;
        }
        
        // File operations group
        const saveBtn = document.getElementById('save-btn');
        const importBtn = document.getElementById('import-btn');
        const fileGroupLabel = document.getElementById('file-group-label');
        
        if (saveBtn) {
            saveBtn.textContent = t.save;
            saveBtn.title = t.saveTooltip;
        }
        if (importBtn) {
            importBtn.textContent = t.import;
            importBtn.title = t.importTooltip;
        }
        if (fileGroupLabel) {
            fileGroupLabel.textContent = t.fileGroup;
        }
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
        
        // Update Learning button text (keep icon, update text in span)
        const learningBtn = document.getElementById('learning-btn');
        if (learningBtn) {
            const learningBtnText = document.getElementById('learning-btn-text');
            if (learningBtnText) {
                learningBtnText.textContent = t.learn;
            }
            learningBtn.title = t.learningModeTooltip;
        }
        
        // Update Node Palette button text and title
        const nodePaletteBtn = document.getElementById('node-palette-btn');
        if (nodePaletteBtn) {
            const nodePaletteBtnText = document.getElementById('node-palette-btn-text');
            if (nodePaletteBtnText) {
                nodePaletteBtnText.textContent = t.nodePalette;
            }
            nodePaletteBtn.title = t.nodePaletteTooltip;
        }
        
        // Update logout button text and language classes
        const logoutBtn = document.getElementById('logout-btn');
        if (logoutBtn) {
            const langEnSpan = logoutBtn.querySelector('.lang-en');
            const langZhSpan = logoutBtn.querySelector('.lang-zh');
            const langAzSpan = logoutBtn.querySelector('.lang-az');
            
            if (langEnSpan) {
                langEnSpan.style.display = this.currentLanguage === 'en' ? 'inline' : 'none';
            }
            if (langZhSpan) {
                langZhSpan.style.display = this.currentLanguage === 'zh' ? 'inline' : 'none';
            }
            if (langAzSpan) {
                langAzSpan.style.display = this.currentLanguage === 'az' ? 'inline' : 'none';
            }
            logoutBtn.dataset.tooltip = t.logoutTooltip;
        }
        
        // Update admin button text and language classes
        const adminBtn = document.getElementById('admin-btn');
        if (adminBtn) {
            const langEnSpan = adminBtn.querySelector('.lang-en');
            const langZhSpan = adminBtn.querySelector('.lang-zh');
            
            if (langEnSpan && langZhSpan) {
                langEnSpan.style.display = this.currentLanguage === 'en' ? 'inline' : 'none';
                langZhSpan.style.display = this.currentLanguage === 'zh' ? 'inline' : 'none';
            }
            adminBtn.dataset.tooltip = t.adminTooltip;
        }
        
        // Update feedback button text and language classes
        const feedbackBtn = document.getElementById('feedback-btn');
        if (feedbackBtn) {
            const langEnSpan = feedbackBtn.querySelector('.lang-en');
            const langZhSpan = feedbackBtn.querySelector('.lang-zh');
            
            if (langEnSpan && langZhSpan) {
                langEnSpan.style.display = this.currentLanguage === 'en' ? 'inline' : 'none';
                langZhSpan.style.display = this.currentLanguage === 'zh' ? 'inline' : 'none';
            }
            feedbackBtn.dataset.tooltip = t.feedbackTooltip;
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
            langToggle.dataset.tooltip = t.switchLanguageTooltip;
        }
        
        // Update feedback button is handled above (line 751-762)
        // Old share button code removed - replaced with feedback button
        
        // Update mobile menu language text
        const mobileLangText = document.getElementById('mobile-lang-text');
        if (mobileLangText) {
            const languages = ['en', 'zh', 'az'];
            const currentIndex = languages.indexOf(this.currentLanguage);
            const nextIndex = (currentIndex + 1) % languages.length;
            const nextLang = languages[nextIndex];
            const buttonTexts = {
                'en': '中文',
                'zh': 'AZ',
                'az': 'EN'
            };
            mobileLangText.textContent = `Switch to ${buttonTexts[this.currentLanguage] || 'EN'}`;
        }
        
        // Update mobile menu share text
        const shareBtnMobile = document.getElementById('share-btn-mobile');
        if (shareBtnMobile) {
            const shareText = shareBtnMobile.querySelector('.menu-text:not(#mobile-lang-text)');
            if (shareText) shareText.textContent = t.share;
        }
        
        // Update property panel tooltips
        const propBold = document.getElementById('prop-bold');
        const propItalic = document.getElementById('prop-italic');
        const propUnderline = document.getElementById('prop-underline');
        if (propBold) propBold.title = t.boldTooltip;
        if (propItalic) propItalic.title = t.italicTooltip;
        if (propUnderline) propUnderline.title = t.underlineTooltip;
        
        const propStrikethrough = document.getElementById('prop-strikethrough');
        if (propStrikethrough) propStrikethrough.title = t.strikethroughTooltip;
        
        // Update AI assistant close button tooltip
        const aiCloseBtn = document.getElementById('toggle-ai-assistant');
        if (aiCloseBtn) aiCloseBtn.title = t.closeTooltip;
        
        // Update toolbar labels (now using span instead of label)
        // File group label is already updated above (around line 1021)
        
        // Edit group label (nodes-toolbar-group)
        const editGroupLabel = document.querySelector('.nodes-toolbar-group .toolbar-group-label');
        if (editGroupLabel) editGroupLabel.textContent = t.nodes + ':';
        
        // Actions group label (tools-toolbar-group)
        const actionsGroupLabel = document.querySelector('.tools-toolbar-group .toolbar-group-label');
        if (actionsGroupLabel) actionsGroupLabel.textContent = t.tools + ':';
        
        // Update status bar
        const editMode = document.getElementById('edit-mode');
        if (editMode) editMode.textContent = t.editMode;
        
        // Update reset view button
        const resetViewBtn = document.getElementById('reset-view-btn');
        if (resetViewBtn) {
            const resetViewText = resetViewBtn.querySelector('.reset-view-icon').nextSibling;
            if (resetViewText) {
                resetViewText.textContent = ' ' + t.resetView;
            }
            resetViewBtn.setAttribute('title', t.resetViewTitle);
        }
        
        // Update Node Palette title
        const nodePaletteTitle = document.querySelector('.node-palette-title h3');
        if (nodePaletteTitle) {
            nodePaletteTitle.textContent = t.nodePalette || t.thinkingModeTitle;
        }
        
        // Update Node Palette button text and tooltip
        const nodePaletteBtnText = document.getElementById('node-palette-btn-text');
        if (nodePaletteBtnText) {
            nodePaletteBtnText.textContent = t.nodePalette;
        }
        const nodePaletteTooltip = document.getElementById('node-palette-tooltip');
        if (nodePaletteTooltip) {
            nodePaletteTooltip.textContent = t.nodePaletteTooltip;
        }
        
        // Update Node Palette buttons
        const cancelPaletteBtn = document.getElementById('cancel-palette-btn');
        if (cancelPaletteBtn && (!cancelPaletteBtn.textContent || cancelPaletteBtn.textContent.trim() === '')) {
            cancelPaletteBtn.textContent = t.nodePaletteCancel;
        }
        
        const finishSelectionBtn = document.getElementById('finish-selection-btn');
        if (finishSelectionBtn && (!finishSelectionBtn.textContent || finishSelectionBtn.textContent.trim() === '')) {
            finishSelectionBtn.textContent = t.nodePaletteNext;
        }
        
        // Update selection counter initial text
        const selectionCounter = document.getElementById('selection-counter');
        if (selectionCounter && (!selectionCounter.textContent || selectionCounter.textContent.trim() === '')) {
            selectionCounter.textContent = `${t.nodePaletteSelected}: 0/0`;
        }
        
        // Update Properties Panel
        const propHeader = document.querySelector('.property-panel .property-header h3');
        if (propHeader) propHeader.textContent = t.properties;
        
        // Update property labels - use specific selectors to ensure 'for' attributes are preserved
        const propTextLabel = document.querySelector('label[for="prop-text"]');
        if (propTextLabel) propTextLabel.textContent = t.text;
        
        const propFontSizeLabel = document.querySelector('label[for="prop-font-size"]');
        if (propFontSizeLabel) propFontSizeLabel.textContent = t.fontSize;
        
        const propFontFamilyLabel = document.querySelector('label[for="prop-font-family"]');
        if (propFontFamilyLabel) propFontFamilyLabel.textContent = t.fontFamily || 'Font Family';
        
        const propTextStyleLabel = document.querySelector('.property-group:nth-of-type(3) label');
        if (propTextStyleLabel && !propTextStyleLabel.getAttribute('for')) {
            propTextStyleLabel.textContent = t.textStyle;
        }
        
        const propTextColorLabel = document.querySelector('label[for="prop-text-color"]');
        if (propTextColorLabel) propTextColorLabel.textContent = t.textColor;
        
        const propFillColorLabel = document.querySelector('label[for="prop-fill-color"]');
        if (propFillColorLabel) propFillColorLabel.textContent = t.fillColor;
        
        const propStrokeColorLabel = document.querySelector('label[for="prop-stroke-color"]');
        if (propStrokeColorLabel) propStrokeColorLabel.textContent = t.strokeColor;
        
        // Update color button titles (tooltips) and labels
        const btnTextColor = document.getElementById('btn-text-color');
        if (btnTextColor) {
            btnTextColor.title = t.textColor;
            const textColorLabel = btnTextColor.querySelector('.color-btn-label');
            if (textColorLabel) textColorLabel.textContent = t.textColorLabel || 'Text';
        }
        
        const btnFillColor = document.getElementById('btn-fill-color');
        if (btnFillColor) {
            btnFillColor.title = t.fillColor;
            const fillColorLabel = btnFillColor.querySelector('.color-btn-label');
            if (fillColorLabel) fillColorLabel.textContent = t.fillColorLabel || 'Fill';
        }
        
        const btnStrokeColor = document.getElementById('btn-stroke-color');
        if (btnStrokeColor) {
            btnStrokeColor.title = t.strokeColor;
            const strokeColorLabel = btnStrokeColor.querySelector('.color-btn-label');
            if (strokeColorLabel) strokeColorLabel.textContent = t.strokeColorLabel || 'Stroke';
        }
        
        // Update color group label (the label before color-buttons-row)
        const colorButtonsRow = document.querySelector('.color-buttons-row');
        if (colorButtonsRow) {
            const colorGroup = colorButtonsRow.closest('.property-group');
            if (colorGroup) {
                const colorGroupLabel = colorGroup.querySelector('label:not([for])');
                if (colorGroupLabel) {
                    colorGroupLabel.textContent = t.colors || 'Colors';
                }
            }
        }
        
        const propStrokeWidthLabel = document.querySelector('label[for="prop-stroke-width"]');
        if (propStrokeWidthLabel) propStrokeWidthLabel.textContent = t.strokeWidth;
        
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
        
        // Update MindMate AI toolbar button (hardcoded to "教学设计")
        const mindmateBtn = document.getElementById('mindmate-ai-btn');
        if (mindmateBtn) {
            const btnText = mindmateBtn.querySelector('span');
            if (btnText) btnText.textContent = '教学设计';
        }
        
        // Update LLM selector label and tooltips
        const llmLabel = document.querySelector('.llm-label');
        if (llmLabel) {
            llmLabel.textContent = t.aiModel;
        }
        
        // Update LLM button text and tooltips
        const llmButtons = document.querySelectorAll('.llm-btn');
        llmButtons.forEach(btn => {
            const llmModel = btn.getAttribute('data-llm');
            if (llmModel === 'qwen') {
                btn.textContent = t.llmQwen;
                btn.title = t.llmQwenTooltip;
            } else if (llmModel === 'deepseek') {
                btn.textContent = t.llmDeepSeek;
                btn.title = t.llmDeepSeekTooltip;
            } else if (llmModel === 'kimi') {
                btn.textContent = t.llmKimi;
                btn.title = t.llmKimiTooltip;
            }
        });
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
        // Update desktop/main button
        const langToggle = document.getElementById('language-toggle');
        if (langToggle) {
            const langText = langToggle.querySelector('.lang-text');
            if (langText) {
                // Show next language in button
                const languages = ['en', 'zh', 'az'];
                const currentIndex = languages.indexOf(this.currentLanguage);
                const nextIndex = (currentIndex + 1) % languages.length;
                const nextLang = languages[nextIndex];
                
                const buttonTexts = {
                    'en': '中文',
                    'zh': 'AZ',
                    'az': 'EN'
                };
                langText.textContent = buttonTexts[this.currentLanguage] || 'EN';
            }
        }
    }
    
    /**
     * Enable scrolling placeholder on mobile for long text
     */
    enableScrollingPlaceholder(input, placeholderText) {
        // Only on mobile devices
        if (window.innerWidth > 768) return;
        
        // Clear any existing interval
        if (this.placeholderInterval) {
            clearInterval(this.placeholderInterval);
        }
        
        let scrollPosition = 0;
        const scrollSpeed = 1;
        const pauseAtStart = 2000; // 2 seconds pause
        const pauseAtEnd = 1000;   // 1 second pause
        let isPaused = true;
        let pauseTimer = null;
        
        // Check if text overflows
        const checkOverflow = () => {
            const inputWidth = input.offsetWidth - 40; // Account for padding
            const canvas = document.createElement('canvas');
            const context = canvas.getContext('2d');
            const computedStyle = window.getComputedStyle(input);
            context.font = `${computedStyle.fontSize} ${computedStyle.fontFamily}`;
            const textWidth = context.measureText(placeholderText).width;
            return textWidth > inputWidth;
        };
        
        if (!checkOverflow()) return; // Text fits, no scrolling needed
        
        // Start scrolling animation
        const startScrolling = () => {
            pauseTimer = setTimeout(() => {
                isPaused = false;
                
                this.placeholderInterval = setInterval(() => {
                    if (!isPaused && input === document.activeElement === false) {
                        scrollPosition += scrollSpeed;
                        
                        // Calculate max scroll (text length - visible area)
                        const maxScroll = placeholderText.length * 8; // Approximate
                        
                        if (scrollPosition >= maxScroll) {
                            isPaused = true;
                            clearInterval(this.placeholderInterval);
                            
                            // Pause at end, then reset
                            setTimeout(() => {
                                scrollPosition = 0;
                                input.placeholder = placeholderText;
                                startScrolling();
                            }, pauseAtEnd);
                        } else {
                            // Create scrolling effect by showing substring
                            const visibleLength = Math.floor(input.offsetWidth / 9);
                            const startChar = Math.floor(scrollPosition / 8);
                            input.placeholder = placeholderText.substring(startChar) + '  ' + placeholderText.substring(0, startChar);
                        }
                    }
                }, 50);
            }, pauseAtStart);
        };
        
        startScrolling();
        
        // Stop scrolling when input is focused
        input.addEventListener('focus', () => {
            if (this.placeholderInterval) {
                clearInterval(this.placeholderInterval);
                clearTimeout(pauseTimer);
            }
            input.placeholder = placeholderText;
        });
        
        // Resume scrolling when input loses focus and is empty
        input.addEventListener('blur', () => {
            if (!input.value && checkOverflow()) {
                scrollPosition = 0;
                startScrolling();
            }
        });
    }
    
    /**
     * Share current URL - Show QR code
     */
    async shareUrl() {
        const url = window.location.href;
        this.showQRCodeModal(url);
    }
    
    /**
     * Show Feedback Modal
     */
    showFeedbackModal() {
        const qrImageName = window.WECHAT_QR_IMAGE || '';
        
        if (!qrImageName) {
            logger.warn('LanguageManager', 'WeChat QR image not configured');
            return;
        }
        
        // Create modal overlay
        const overlay = document.createElement('div');
        overlay.className = 'feedback-modal-overlay';
        overlay.style.position = 'fixed';
        overlay.style.top = '0';
        overlay.style.left = '0';
        overlay.style.width = '100%';
        overlay.style.height = '100%';
        overlay.style.background = 'rgba(0, 0, 0, 0.7)';
        overlay.style.display = 'flex';
        overlay.style.alignItems = 'center';
        overlay.style.justifyContent = 'center';
        overlay.style.zIndex = '9999';
        overlay.style.opacity = '0';
        overlay.style.transition = 'opacity 0.3s ease';
        
        // Create modal content
        const modal = document.createElement('div');
        modal.className = 'feedback-modal';
        modal.style.background = 'white';
        modal.style.borderRadius = '20px';
        modal.style.padding = '40px';
        modal.style.maxWidth = '500px';
        modal.style.width = '90%';
        modal.style.boxShadow = '0 20px 60px rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(102, 126, 234, 0.1)';
        modal.style.position = 'relative';
        modal.style.border = '2px solid transparent';
        modal.style.backgroundImage = 'linear-gradient(white, white), linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
        modal.style.backgroundOrigin = 'border-box';
        modal.style.backgroundClip = 'padding-box, border-box';
        modal.style.textAlign = 'center';
        
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
        
        const closeModal = () => {
            overlay.style.opacity = '0';
            setTimeout(() => overlay.remove(), 300);
        };
        closeBtn.addEventListener('click', closeModal);
        
        // Title
        const title = document.createElement('h2');
        title.textContent = this.currentLanguage === 'en' ? 'Join Feedback Group' : '加入反馈群';
        title.style.margin = '0 0 12px 0';
        title.style.color = '#1a1a1a';
        title.style.fontSize = '26px';
        title.style.fontWeight = '700';
        title.style.letterSpacing = '-0.5px';
        
        // Subtitle
        const subtitle = document.createElement('p');
        subtitle.textContent = this.currentLanguage === 'en' 
            ? 'Scan the QR code to join our WeChat group for feedback' 
            : '扫描二维码加入微信群，提供反馈和建议';
        subtitle.style.margin = '0 0 28px 0';
        subtitle.style.color = '#64748b';
        subtitle.style.fontSize = '14px';
        subtitle.style.lineHeight = '1.5';
        
        // QR Code Image
        const qrImage = document.createElement('img');
        qrImage.src = `/static/qr/${qrImageName}`;
        qrImage.alt = this.currentLanguage === 'en' ? 'WeChat Group QR Code' : '微信群二维码';
        qrImage.style.width = '100%';
        qrImage.style.maxWidth = '400px';
        qrImage.style.height = 'auto';
        qrImage.style.borderRadius = '12px';
        qrImage.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.1)';
        qrImage.style.margin = '0 auto 20px';
        qrImage.style.display = 'block';
        
        // Handle image load error
        qrImage.addEventListener('error', () => {
            qrImage.style.display = 'none';
            const errorMsg = document.createElement('p');
            errorMsg.textContent = this.currentLanguage === 'en' 
                ? 'QR code image not found' 
                : '二维码图片未找到';
            errorMsg.style.color = '#dc2626';
            errorMsg.style.marginTop = '20px';
            modal.appendChild(errorMsg);
        });
        
        // Assemble modal
        modal.appendChild(closeBtn);
        modal.appendChild(title);
        modal.appendChild(subtitle);
        modal.appendChild(qrImage);
        overlay.appendChild(modal);
        document.body.appendChild(overlay);
        
        // Fade in
        setTimeout(() => {
            overlay.style.opacity = '1';
        }, 10);
        
        // Close on overlay click
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                closeModal();
            }
        });
        
        // Close on Escape key
        const escapeHandler = (e) => {
            if (e.key === 'Escape') {
                closeModal();
                document.removeEventListener('keydown', escapeHandler);
            }
        };
        document.addEventListener('keydown', escapeHandler);
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
                logger.error('LanguageManager', 'Copy to clipboard failed', err);
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
            logger.error('LanguageManager', 'NotificationManager not available');
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
    translate(key, ...args) {
        const translation = this.translations[this.currentLanguage][key];
        
        // If translation is a function, call it with arguments
        if (typeof translation === 'function') {
            return translation(...args);
        }
        
        return translation || key;
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
    
    /**
     * Check if current user is admin and show/hide admin button
     * SECURITY: Removes button from DOM if not admin (prevents CSS/JS manipulation)
     */
    async checkAdminStatus() {
        const adminBtn = document.getElementById('admin-btn');
        if (!adminBtn) return;
        
        // SECURITY: Default to removing button (fail-secure)
        let isAdmin = false;
        
        // Check if auth helper is available
        if (typeof auth === 'undefined') {
            // Auth helper not loaded - remove button for security
            adminBtn.remove();
            return;
        }
        
        try {
            // Check if user is authenticated first
            const isAuthenticated = await auth.isAuthenticated();
            if (!isAuthenticated) {
                // Not authenticated - remove button
                adminBtn.remove();
                return;
            }
            
            // SECURITY: Check if user is admin by testing admin endpoint
            // This endpoint requires valid JWT and admin check on backend
            const adminCheck = await auth.fetch('/api/auth/admin/stats');
            
            if (adminCheck.ok) {
                // User is admin - verify response is valid JSON
                try {
                    const responseData = await adminCheck.json(); // Parse and verify response
                    // Additional validation: ensure response has expected structure
                    if (responseData && typeof responseData === 'object') {
                        isAdmin = true;
                    } else {
                        // Invalid response structure - fail secure
                        isAdmin = false;
                    }
                } catch (e) {
                    // Invalid JSON response - fail secure
                    isAdmin = false;
                }
            } else {
                // Not admin (403 or other error) - fail secure
                isAdmin = false;
            }
        } catch (error) {
            // SECURITY: Any error = fail secure (remove button)
            // Don't log sensitive error details to console in production
            if (window.VERBOSE_LOGGING) {
                console.error('Error checking admin status:', error);
            }
            isAdmin = false;
        }
        
        // SECURITY: Remove button from DOM if not admin (prevents manipulation)
        if (!isAdmin) {
            adminBtn.remove();
        } else {
            // User is admin - show button
            adminBtn.style.display = 'inline-flex';
        }
    }
}

// Initialize when DOM is ready
if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', async () => {
        window.languageManager = new LanguageManager();
        
        // SECURITY: Check admin status after auth helper is loaded
        // Use a more robust check that waits for auth helper to be available
        const checkAdminWhenReady = async () => {
            // Wait for auth helper to be available (max 3 seconds)
            let attempts = 0;
            const maxAttempts = 30; // 30 attempts * 100ms = 3 seconds max
            
            while (typeof auth === 'undefined' && attempts < maxAttempts) {
                await new Promise(resolve => setTimeout(resolve, 100));
                attempts++;
            }
            
            if (window.languageManager) {
                await window.languageManager.checkAdminStatus();
                
                // SECURITY: Periodic re-check admin status (every 5 minutes)
                // Prevents showing admin button if session expires or admin status revoked
                setInterval(async () => {
                    if (window.languageManager) {
                        await window.languageManager.checkAdminStatus();
                    }
                }, 5 * 60 * 1000); // 5 minutes
                
                // SECURITY: Re-check when page becomes visible (catches session expiration)
                document.addEventListener('visibilitychange', async () => {
                    if (!document.hidden && window.languageManager) {
                        await window.languageManager.checkAdminStatus();
                    }
                });
            }
        };
        
        checkAdminWhenReady();
    });
}

