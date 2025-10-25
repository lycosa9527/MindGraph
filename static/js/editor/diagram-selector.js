/**
 * DiagramSelector - Handles diagram type selection and template loading
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 */

class DiagramSelector {
    constructor() {
        // Session management
        this.currentSession = null;  // Will hold session info: { id, diagramType, startTime }
        this.editorActive = false;
        
        // Store metadata only - templates are generated fresh each time via factory methods
        this.diagramTypes = {
            'circle_map': {
                name: 'Circle Map',
                description: 'Defining in context',
                templateFactory: () => this.getCircleMapTemplate()
            },
            'bubble_map': {
                name: 'Bubble Map',
                description: 'Describing with adjectives',
                templateFactory: () => this.getBubbleMapTemplate()
            },
            'double_bubble_map': {
                name: 'Double Bubble Map',
                description: 'Comparing and contrasting',
                templateFactory: () => this.getDoubleBubbleMapTemplate()
            },
            'tree_map': {
                name: 'Tree Map',
                description: 'Classifying and grouping',
                templateFactory: () => this.getTreeMapTemplate()
            },
            'brace_map': {
                name: 'Brace Map',
                description: 'Whole to parts',
                templateFactory: () => this.getBraceMapTemplate()
            },
            'flow_map': {
                name: 'Flow Map',
                description: 'Sequencing and ordering',
                templateFactory: () => this.getFlowMapTemplate()
            },
            'multi_flow_map': {
                name: 'Multi-Flow Map',
                description: 'Cause and effect',
                templateFactory: () => this.getMultiFlowMapTemplate()
            },
            'bridge_map': {
                name: 'Bridge Map',
                description: 'Seeing analogies',
                templateFactory: () => this.getBridgeMapTemplate()
            },
            'mindmap': {
                name: 'Mind Map',
                description: 'Creative brainstorming',
                templateFactory: () => this.getMindMapTemplate()
            },
            'concept_map': {
                name: 'Concept Map',
                description: 'Complex relationships',
                templateFactory: () => this.getConceptMapTemplate()
            },
            'factor_analysis': {
                name: 'Factor Analysis',
                description: '因素分析法',
                templateFactory: () => this.getFactorAnalysisTemplate()
            },
            'three_position_analysis': {
                name: 'Three-Position Analysis',
                description: '三位分析法',
                templateFactory: () => this.getThreePositionAnalysisTemplate()
            },
            'perspective_analysis': {
                name: 'Perspective Analysis',
                description: '换位分析法',
                templateFactory: () => this.getPerspectiveAnalysisTemplate()
            },
            'goal_analysis': {
                name: 'Goal Analysis',
                description: '目标分析法',
                templateFactory: () => this.getGoalAnalysisTemplate()
            },
            'possibility_analysis': {
                name: 'Possibility Analysis',
                description: '可能分析法',
                templateFactory: () => this.getPossibilityAnalysisTemplate()
            },
            'result_analysis': {
                name: 'Result Analysis',
                description: '结果分析法',
                templateFactory: () => this.getResultAnalysisTemplate()
            },
            'five_w_one_h': {
                name: '5W1H Analysis',
                description: '六何分析法',
                templateFactory: () => this.getFiveWOneHTemplate()
            },
            'whwm_analysis': {
                name: 'WHWM Analysis',
                description: 'WHWM分析法',
                templateFactory: () => this.getWHWMAnalysisTemplate()
            },
            'four_quadrant': {
                name: 'Four Quadrant Analysis',
                description: '四象限分析法',
                templateFactory: () => this.getFourQuadrantTemplate()
            }
        };
        
        this.initializeEventListeners();
    }
    
    /**
     * Initialize event listeners
     */
    initializeEventListeners() {
        // Diagram card click handlers - make entire card clickable
        document.querySelectorAll('.diagram-card').forEach(card => {
            card.addEventListener('click', (e) => {
                // CRITICAL: Only handle clicks if we're actually in gallery view
                const landing = document.getElementById('editor-landing');
                const editorInterface = document.getElementById('editor-interface');
                
                logger.debug('DiagramSelector', 'Card clicked', {
                    cardType: card.dataset.type,
                    editorActive: this.editorActive,
                    hasSession: !!this.currentSession
                });
                
                // CRITICAL: Check for state mismatch first
                const domInGalleryMode = landing && landing.style.display !== 'none' && 
                                        (!editorInterface || editorInterface.style.display === 'none');
                const flagsSayEditorActive = this.editorActive || this.currentSession;
                
                // If DOM shows gallery but flags say editor active -> FORCE RESET
                if (domInGalleryMode && flagsSayEditorActive) {
                    logger.warn('DiagramSelector', 'State mismatch detected - triggering force reset');
                    this.forceReset();
                    // After reset, allow the click to proceed
                    const diagramType = card.dataset.type;
                    logger.debug('DiagramSelector', 'Proceeding after reset', { diagramType });
                    this.selectDiagram(diagramType);
                    return;
                }
                
                // FIXED: Use editorActive flag instead of DOM checks for reliability
                if (this.editorActive) {
                    logger.warn('DiagramSelector', 'Card click blocked - editor is active');
                    e.stopPropagation();
                    e.preventDefault();
                    return;
                }
                
                // Secondary check: Verify DOM state matches our flags (opposite direction)
                if (!landing || landing.style.display === 'none' || 
                    (editorInterface && editorInterface.style.display !== 'none')) {
                    logger.warn('DiagramSelector', 'Card click blocked - DOM in editor mode, resetting');
                    // Force reset to recover from inconsistent state
                    this.forceReset();
                    e.stopPropagation();
                    e.preventDefault();
                    return;
                }
                
                const diagramType = card.dataset.type;
                logger.debug('DiagramSelector', 'Card click proceeding', { diagramType });
                this.selectDiagram(diagramType);
            });
        });
        
        // Back to gallery button
        const backBtn = document.getElementById('back-to-gallery');
        if (backBtn) {
            backBtn.addEventListener('click', () => {
                this.backToGallery();
            });
        }
    }
    
    /**
     * Generate a unique session ID
     */
    generateSessionId() {
        return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }
    
    /**
     * Start a new editing session
     */
    startSession(diagramType) {
        const sessionId = this.generateSessionId();
        this.currentSession = {
            id: sessionId,
            diagramType: diagramType,
            startTime: new Date().toISOString()
        };
        this.editorActive = true;
        
        logger.info('DiagramSelector', 'Session started', {
            sessionId: sessionId.substr(-8),
            diagramType: diagramType
        });
        
        return sessionId;
    }
    
    /**
     * @deprecated - Use logger.debug/info/warn/error directly instead
     * Legacy method for backward compatibility
     */
    logToBackend(level, message, data = null) {
        const levelMap = {
            'DEBUG': () => logger.debug('DiagramSelector', message, data),
            'INFO': () => logger.info('DiagramSelector', message, data),
            'WARN': () => logger.warn('DiagramSelector', message, data),
            'ERROR': () => logger.error('DiagramSelector', message, data)
        };
        (levelMap[level] || levelMap['INFO'])();
    }
    
    /**
     * End the current editing session
     */
    endSession() {
        if (this.currentSession) {
            const duration = (new Date() - new Date(this.currentSession.startTime)) / 1000;
            logger.info('DiagramSelector', 'Session ended', {
                sessionId: this.currentSession.id.substr(-8),
                diagramType: this.currentSession.diagramType,
                duration: `${duration.toFixed(1)}s`
            });
        }
        
        this.currentSession = null;
        this.editorActive = false;
    }
    
    /**
     * Force reset to gallery mode - recovery from inconsistent state
     */
    forceReset() {
        logger.warn('DiagramSelector', 'Force reset - recovering from inconsistent state');
        
        // Reset flags
        this.currentSession = null;
        this.editorActive = false;
        
        // Force DOM to gallery mode
        const landing = document.getElementById('editor-landing');
        if (landing) {
            landing.style.display = 'block';
        }
        
        const editorInterface = document.getElementById('editor-interface');
        if (editorInterface) {
            editorInterface.style.display = 'none';
        }
        
        // Clean up any lingering editor
        if (window.currentEditor) {
            window.currentEditor = null;
        }
        
        // Clear canvas
        const container = document.getElementById('d3-container');
        if (container) {
            d3.select('#d3-container').selectAll('*').remove();
        }
    }
    
    /**
     * Validate that we're in the correct session for a diagram operation
     */
    validateSession(diagramType, operation = 'operation') {
        if (!this.currentSession) {
            logger.error('DiagramSelector', `${operation} rejected - no active session`);
            return false;
        }
        
        if (this.currentSession.diagramType !== diagramType) {
            logger.error('DiagramSelector', `${operation} rejected - diagram mismatch`, {
                sessionDiagram: this.currentSession.diagramType,
                requestedDiagram: diagramType,
                sessionId: this.currentSession.id.substr(-8)
            });
            return false;
        }
        
        return true;
    }
    
    /**
     * Select a diagram type
     */
    selectDiagram(diagramType) {
        // Check if concept map - show under development notification
        if (diagramType === 'concept_map') {
            const language = window.languageManager?.currentLanguage || 'en';
            const message = language === 'zh' 
                ? '概念图功能正在开发中，敬请期待！' 
                : 'Concept Map is under development. Coming soon!';
            
            // Show browser notification
            if (window.notificationManager) {
                window.notificationManager.show(message, 'info');
            } else {
                alert(message);
            }
            logger.debug('DiagramSelector', 'Concept map blocked - under development');
            return;
        }
        
        // Check if thinking tools - show under development notification
        const thinkingTools = ['factor_analysis', 'three_position_analysis', 'perspective_analysis', 
                               'goal_analysis', 'possibility_analysis', 'result_analysis', 
                               'five_w_one_h', 'whwm_analysis', 'four_quadrant'];
        if (thinkingTools.includes(diagramType)) {
            const language = window.languageManager?.currentLanguage || 'en';
            const message = language === 'zh' 
                ? '思维工具功能正在开发中，敬请期待！' 
                : 'Thinking Tools are under development. Coming soon!';
            
            // Show browser notification
            if (window.notificationManager) {
                window.notificationManager.show(message, 'info');
            } else {
                alert(message);
            }
            logger.debug('DiagramSelector', 'Thinking tools blocked - under development');
            return;
        }
        
        // CRITICAL: Check if there's an active session
        if (this.currentSession) {
            logger.error('DiagramSelector', 'Blocked - active session in progress', {
                sessionId: this.currentSession.id.substr(-8),
                currentDiagram: this.currentSession.diagramType,
                attemptedSwitch: diagramType
            });
            return;
        }
        
        // CRITICAL: Check global flag
        if (this.editorActive) {
            logger.error('DiagramSelector', 'Blocked - editor is active', {
                attemptedSwitch: diagramType,
                currentEditor: window.currentEditor?.diagramType
            });
            return;
        }
        
        // CRITICAL: Verify we're actually in gallery mode before switching
        const landing = document.getElementById('editor-landing');
        const editorInterface = document.getElementById('editor-interface');
        
        logger.debug('DiagramSelector', 'Select diagram called', {
            diagramType,
            hasActiveEditor: !!window.currentEditor,
            editorActive: this.editorActive
        });
        
        // Double-check we're in gallery view
        if (editorInterface && editorInterface.style.display !== 'none') {
            logger.error('DiagramSelector', 'Blocked by DOM check - editor is active', {
                currentEditor: window.currentEditor?.diagramType
            });
            return;
        }
        
        const diagramConfig = this.diagramTypes[diagramType];
        if (diagramConfig) {
            logger.debug('DiagramSelector', 'Proceeding with diagram selection', { diagramType });
            // Get a fresh template using the factory method
            const freshTemplate = this.getTemplate(diagramType);
            this.transitionToEditor(diagramType, freshTemplate, diagramConfig.name);
        } else {
            logger.error('DiagramSelector', `Unknown diagram type: ${diagramType}`);
        }
    }
    
    /**
     * Get a fresh template for a diagram type using factory pattern
     * This ensures each diagram starts with a pristine empty template
     * @param {string} diagramType - The type of diagram to get template for
     * @returns {Object} Fresh template object
     */
    getTemplate(diagramType) {
        const diagramConfig = this.diagramTypes[diagramType];
        if (!diagramConfig) {
            logger.error('DiagramSelector', `No template found for: ${diagramType}`);
            return null;
        }
        
        // Call the factory function to generate a fresh template
        if (typeof diagramConfig.templateFactory === 'function') {
            return diagramConfig.templateFactory();
        }
        
        logger.error('DiagramSelector', `No template factory found for: ${diagramType}`);
        return null;
    }
    
    /**
     * Transition to editor interface
     */
    transitionToEditor(diagramType, template, diagramName) {
        logger.info('DiagramSelector', 'Transitioning to editor', {
            diagramType,
            diagramName
        });
        
        // Clean up previous editor and canvas first
        this.cleanupCanvas();
        
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
        
        // Update diagram type display
        const displayElement = document.getElementById('diagram-type-display');
        if (displayElement) {
            displayElement.textContent = diagramName;
        }
        
        // Initialize editor with selected diagram type
        try {
            // Start a new session
            const sessionId = this.startSession(diagramType);
            
            // Create editor and attach session info
            window.currentEditor = new InteractiveEditor(diagramType, template);
            window.currentEditor.sessionId = sessionId;
            window.currentEditor.sessionDiagramType = diagramType;
            window.currentEditor.initialize();
            
            // CRITICAL: Single auto-fit trigger for initial load
            // This is the ONLY place where auto-fit is called when entering canvas from gallery
            // - Waits for rendering to complete (250ms delay)
            // - Uses instant fit (no animation) to prevent visible shrinking
            // - Reserves space for properties panel (windowWidth - 320px) even though panel is hidden
            // Result: Diagram appears at perfect size, ready for editing when user clicks a node
            setTimeout(() => {
                if (window.currentEditor && typeof window.currentEditor.fitToCanvasWithPanel === 'function') {
                    window.currentEditor.fitToCanvasWithPanel(false); // false = no animation
                }
            }, 250);
            
            logger.info('DiagramSelector', 'Editor initialized successfully', { diagramType });
        } catch (error) {
            logger.error('DiagramSelector', 'Error initializing editor', error);
            this.endSession();  // End session on error
            const message = window.languageManager?.getNotification('editorLoadError') 
                || 'Error loading editor. Please try again.';
            alert(message);
            this.backToGallery();
        }
    }
    
    /**
     * Clean up canvas and previous editor
     * Called during session transitions (gallery <-> editor)
     */
    cleanupCanvas() {
        logger.debug('DiagramSelector', 'SESSION MANAGER: Canvas cleanup initiated');
        
        // ========================================
        // 1. CLEAR D3 CANVAS
        // ========================================
        const container = document.getElementById('d3-container');
        if (container) {
            d3.select('#d3-container').selectAll('*').remove();
            container.style.display = 'block'; // Ensure visible (Node Palette might have hidden it)
            logger.debug('DiagramSelector', 'D3 canvas cleared');
        }
        
        // ========================================
        // 2. CLEAN UP ALL PANELS
        // ========================================
        
        // Node Palette
        const nodePalettePanel = document.getElementById('node-palette-panel');
        if (nodePalettePanel) {
            nodePalettePanel.style.display = 'none';
            nodePalettePanel.classList.remove('thinkguide-visible');
        }
        if (window.nodePaletteManager) {
            window.nodePaletteManager.clearAll();
        }
        
        // Property Panel
        const propertyPanel = document.getElementById('property-panel');
        if (propertyPanel) {
            propertyPanel.style.display = 'none';
        }
        
        // ========================================
        // 3. DESTROY CURRENT EDITOR & MANAGERS
        // ========================================
        if (window.currentEditor) {
            // Call comprehensive destroy() method
            // This removes ALL event listeners, destroys ALL managers, and clears ALL data
            window.currentEditor.destroy();
            
            // Nullify global reference
            window.currentEditor = null;
            logger.debug('DiagramSelector', 'Editor instance destroyed');
        }
        
        // ========================================
        // 4. CLEAR ALL LOADING STATES
        // ========================================
        
        // Remove catapult loader
        const catapultLoader = document.getElementById('catapult-loader');
        if (catapultLoader) {
            catapultLoader.remove();
        }
        
        // Remove batch transition
        const batchTransition = document.getElementById('batch-transition');
        if (batchTransition) {
            batchTransition.remove();
        }
        
        logger.debug('DiagramSelector', 'SESSION MANAGER: Canvas cleanup complete');
    }
    
    /**
     * Return to gallery
     */
    backToGallery() {
        logger.info('DiagramSelector', '========================================');
        logger.info('DiagramSelector', 'SESSION MANAGER: TOTAL RESET INITIATED');
        logger.info('DiagramSelector', '========================================');
        logger.info('DiagramSelector', 'Returning to gallery', {
            hasSession: !!this.currentSession,
            editorActive: this.editorActive
        });
        
        // ========================================
        // PHASE 1: CANCEL ALL ACTIVE OPERATIONS
        // ========================================
        
        // Cancel all in-progress LLM requests
        if (window.currentEditor?.toolbarManager) {
            window.currentEditor.toolbarManager.cancelAllLLMRequests();
            logger.debug('DiagramSelector', 'All LLM requests cancelled');
        }
        
        // ========================================
        // PHASE 2: END SESSION & CLEAN CANVAS
        // ========================================
        
        this.endSession();
        this.cleanupCanvas();
        
        // ========================================
        // PHASE 3: RESET ALL PANELS & MANAGERS
        // ========================================
        
        // 1. MindMate AI Assistant
        const aiPanel = document.getElementById('ai-assistant-panel');
        if (aiPanel) {
            aiPanel.classList.add('collapsed');
        }
        const mindmateBtn = document.getElementById('mindmate-ai-btn');
        if (mindmateBtn) {
            mindmateBtn.classList.remove('active');
        }
        if (window.aiAssistantManager) {
            window.aiAssistantManager.diagramSessionId = null;
            window.aiAssistantManager.conversationId = null;
            window.aiAssistantManager.hasGreeted = false;
            logger.debug('DiagramSelector', 'MindMate reset complete');
        }
        
        // 2. ThinkGuide Panel
        const thinkPanel = document.getElementById('thinking-panel');
        if (thinkPanel) {
            thinkPanel.classList.add('collapsed');
        }
        const thinkingBtn = document.getElementById('thinking-btn');
        if (thinkingBtn) {
            thinkingBtn.classList.remove('active');
        }
        if (window.thinkingModeManager) {
            window.thinkingModeManager.diagramSessionId = null;
            window.thinkingModeManager.sessionId = null;
            window.thinkingModeManager.currentState = 'CONTEXT_GATHERING';
            logger.debug('DiagramSelector', 'ThinkGuide reset complete');
        }
        
        // 3. Node Palette (CATAPULT System)
        const nodePalettePanel = document.getElementById('node-palette-panel');
        if (nodePalettePanel) {
            nodePalettePanel.style.display = 'none';
            nodePalettePanel.classList.remove('thinkguide-visible');
        }
        if (window.nodePaletteManager) {
            // Clear all state: nodes, selections, tabs, sessions, animations
            window.nodePaletteManager.clearAll();
            logger.debug('DiagramSelector', 'Node Palette reset complete');
        }
        
        // 4. Property Panel
        const propertyPanel = document.getElementById('property-panel');
        if (propertyPanel) {
            propertyPanel.style.display = 'none';
        }
        
        // 5. Panel Manager (global panel state)
        if (window.panelManager) {
            window.panelManager.closeAll();
            logger.debug('DiagramSelector', 'Panel Manager reset complete');
        }
        
        // 6. Learning Mode Manager (if active)
        if (window.currentEditor?.toolbarManager?.learningModeManager) {
            const learningManager = window.currentEditor.toolbarManager.learningModeManager;
            if (learningManager.isActive) {
                learningManager.exitLearningMode();
                logger.debug('DiagramSelector', 'Learning Mode reset complete');
            }
        }
        
        // ========================================
        // PHASE 4: RESET ALL TOOLBAR BUTTONS
        // ========================================
        
        // Remove active state from all toolbar buttons
        const toolbarButtons = document.querySelectorAll('.toolbar-btn.active');
        toolbarButtons.forEach(btn => {
            btn.classList.remove('active');
        });
        
        // ========================================
        // PHASE 5: CLEAR ALL ANIMATIONS & LOADERS
        // ========================================
        
        // Remove any catapult loaders
        const catapultLoader = document.getElementById('catapult-loader');
        if (catapultLoader) {
            catapultLoader.remove();
        }
        
        // Remove any batch transition elements
        const batchTransition = document.getElementById('batch-transition');
        if (batchTransition) {
            batchTransition.remove();
        }
        
        // ========================================
        // PHASE 6: RESTORE GALLERY VIEW
        // ========================================
        
        requestAnimationFrame(() => {
            const landing = document.getElementById('editor-landing');
            if (landing) {
                landing.style.display = 'block';
            }
            
            const editorInterface = document.getElementById('editor-interface');
            if (editorInterface) {
                editorInterface.style.display = 'none';
            }
            
            logger.info('DiagramSelector', '========================================');
            logger.info('DiagramSelector', 'SESSION MANAGER: TOTAL RESET COMPLETE');
            logger.info('DiagramSelector', '========================================');
        });
    }
    
    /**
     * Get Circle Map template
     */
    getCircleMapTemplate() {
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        
        if (lang === 'zh') {
            return {
                topic: '主题',
                context: ['背景1', '背景2', '背景3', '背景4', '背景5', '背景6', '背景7', '背景8'],
                _layout: {
                    positions: {
                        '主题': { x: 350, y: 250 }
                    }
                },
                _recommended_dimensions: {
                    width: 700,
                    height: 500,
                    padding: 40
                }
            };
        } else {
            return {
                topic: 'Main Topic',
                context: ['Context 1', 'Context 2', 'Context 3', 'Context 4', 'Context 5', 'Context 6', 'Context 7', 'Context 8'],
                _layout: {
                    positions: {
                        'Main Topic': { x: 350, y: 250 }
                    }
                },
                _recommended_dimensions: {
                    width: 700,
                    height: 500,
                    padding: 40
                }
            };
        }
    }
    
    /**
     * Get Double Bubble Map template
     */
    getDoubleBubbleMapTemplate() {
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        
        if (lang === 'zh') {
            return {
                left: '主题A',
                right: '主题B',
                similarities: ['相似点1', '相似点2'],
                left_differences: ['差异A1', '差异A2'],
                right_differences: ['差异B1', '差异B2'],
                _layout: {
                    positions: {
                        '主题A': { x: 200, y: 250 },
                        '主题B': { x: 500, y: 250 }
                    }
                },
                _recommended_dimensions: {
                    width: 700,
                    height: 500,
                    padding: 40
                }
            };
        } else {
            return {
                left: 'Topic A',
                right: 'Topic B',
                similarities: ['Similarity 1', 'Similarity 2'],
                left_differences: ['Difference A1', 'Difference A2'],
                right_differences: ['Difference B1', 'Difference B2'],
                _layout: {
                    positions: {
                        'Topic A': { x: 200, y: 250 },
                        'Topic B': { x: 500, y: 250 }
                    }
                },
                _recommended_dimensions: {
                    width: 700,
                    height: 500,
                    padding: 40
                }
            };
        }
    }
    
    /**
     * Get Multi-Flow Map template
     */
    getMultiFlowMapTemplate() {
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        
        if (lang === 'zh') {
            return {
                event: '主要事件',
                causes: ['原因1', '原因2'],
                effects: ['结果1', '结果2'],
                _layout: {
                    positions: {
                        '主要事件': { x: 350, y: 250 }
                    }
                },
                _recommended_dimensions: {
                    width: 700,
                    height: 500,
                    padding: 40
                }
            };
        } else {
            return {
                event: 'Main Event',
                causes: ['Cause 1', 'Cause 2'],
                effects: ['Effect 1', 'Effect 2'],
                _layout: {
                    positions: {
                        'Main Event': { x: 350, y: 250 }
                    }
                },
                _recommended_dimensions: {
                    width: 700,
                    height: 500,
                    padding: 40
                }
            };
        }
    }
    
    /**
     * Get Bridge Map template
     */
    getBridgeMapTemplate() {
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        
        if (lang === 'zh') {
            return {
                relating_factor: '如同',
                dimension: '',  // Empty = diverse relationships, Filled = specific relationship
                analogies: [
                    { left: '项目1', right: '项目A' },
                    { left: '项目2', right: '项目B' },
                    { left: '项目3', right: '项目C' }
                ],
                _layout: {
                    positions: {}
                },
                _recommended_dimensions: {
                    width: 700,
                    height: 300,
                    padding: 40
                }
            };
        } else {
            return {
                relating_factor: 'as',
                dimension: '',  // Empty = diverse relationships, Filled = specific relationship
                analogies: [
                    { left: 'Item 1', right: 'Item A' },
                    { left: 'Item 2', right: 'Item B' },
                    { left: 'Item 3', right: 'Item C' }
                ],
                _layout: {
                    positions: {}
                },
                _recommended_dimensions: {
                    width: 700,
                    height: 300,
                    padding: 40
                }
            };
        }
    }
    
    /**
     * Get Mind Map template
     */
    getMindMapTemplate() {
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        
        if (lang === 'zh') {
            return {
                topic: '中心主题',
                children: [
                    { 
                        id: 'branch_0',
                        label: '分支1', 
                        text: '分支1',
                        children: [
                            { id: 'sub_0_0', label: '子项1.1', text: '子项1.1', children: [] },
                            { id: 'sub_0_1', label: '子项1.2', text: '子项1.2', children: [] }
                        ] 
                    },
                    { 
                        id: 'branch_1',
                        label: '分支2', 
                        text: '分支2',
                        children: [
                            { id: 'sub_1_0', label: '子项2.1', text: '子项2.1', children: [] },
                            { id: 'sub_1_1', label: '子项2.2', text: '子项2.2', children: [] }
                        ] 
                    },
                    { 
                        id: 'branch_2',
                        label: '分支4', 
                        text: '分支4',
                        children: [
                            { id: 'sub_2_0', label: '子项4.1', text: '子项4.1', children: [] },
                            { id: 'sub_2_1', label: '子项4.2', text: '子项4.2', children: [] }
                        ] 
                    },
                    { 
                        id: 'branch_3',
                        label: '分支3', 
                        text: '分支3',
                        children: [
                            { id: 'sub_3_0', label: '子项3.1', text: '子项3.1', children: [] },
                            { id: 'sub_3_1', label: '子项3.2', text: '子项3.2', children: [] }
                        ] 
                    }
                ],
                _layout: {
                    positions: {
                        'topic': { 
                            x: 0, y: 0, 
                            width: 120, height: 60, 
                            text: '中心主题', 
                            node_type: 'topic', 
                            angle: 0 
                        },
                        'branch_0': { 
                            x: 220, y: -80, 
                            width: 100, height: 50, 
                            text: '分支1', 
                            node_type: 'branch', 
                            branch_index: 0, 
                            angle: 0 
                        },
                        'branch_1': { 
                            x: 220, y: 80, 
                            width: 100, height: 50, 
                            text: '分支2', 
                            node_type: 'branch', 
                            branch_index: 1, 
                            angle: 0 
                        },
                        'branch_2': { 
                            x: -220, y: -80, 
                            width: 100, height: 50, 
                            text: '分支4', 
                            node_type: 'branch', 
                            branch_index: 2, 
                            angle: 0 
                        },
                        'branch_3': { 
                            x: -220, y: 80, 
                            width: 100, height: 50, 
                            text: '分支3', 
                            node_type: 'branch', 
                            branch_index: 3, 
                            angle: 0 
                        },
                        'child_0_0': { 
                            x: 370, y: -110, 
                            width: 90, height: 40, 
                            text: '子项1.1', 
                            node_type: 'child', 
                            branch_index: 0, 
                            child_index: 0, 
                            angle: 0 
                        },
                        'child_0_1': { 
                            x: 370, y: -50, 
                            width: 90, height: 40, 
                            text: '子项1.2', 
                            node_type: 'child', 
                            branch_index: 0, 
                            child_index: 1, 
                            angle: 0 
                        },
                        'child_1_0': { 
                            x: 370, y: 50, 
                            width: 90, height: 40, 
                            text: '子项2.1', 
                            node_type: 'child', 
                            branch_index: 1, 
                            child_index: 0, 
                            angle: 0 
                        },
                        'child_1_1': { 
                            x: 370, y: 110, 
                            width: 90, height: 40, 
                            text: '子项2.2', 
                            node_type: 'child', 
                            branch_index: 1, 
                            child_index: 1, 
                            angle: 0 
                        },
                        'child_2_0': { 
                            x: -370, y: -110, 
                            width: 90, height: 40, 
                            text: '子项4.1', 
                            node_type: 'child', 
                            branch_index: 2, 
                            child_index: 0, 
                            angle: 0 
                        },
                        'child_2_1': { 
                            x: -370, y: -50, 
                            width: 90, height: 40, 
                            text: '子项4.2', 
                            node_type: 'child', 
                            branch_index: 2, 
                            child_index: 1, 
                            angle: 0 
                        },
                        'child_3_0': { 
                            x: -370, y: 50, 
                            width: 90, height: 40, 
                            text: '子项3.1', 
                            node_type: 'child', 
                            branch_index: 3, 
                            child_index: 0, 
                            angle: 0 
                        },
                        'child_3_1': { 
                            x: -370, y: 110, 
                            width: 90, height: 40, 
                            text: '子项3.2', 
                            node_type: 'child', 
                            branch_index: 3, 
                            child_index: 1, 
                            angle: 0 
                        }
                    },
                    connections: [
                        { from: { x: 0, y: 0, type: 'topic' }, to: { x: 220, y: -80, type: 'branch' } },
                        { from: { x: 0, y: 0, type: 'topic' }, to: { x: 220, y: 80, type: 'branch' } },
                        { from: { x: 0, y: 0, type: 'topic' }, to: { x: -220, y: -80, type: 'branch' } },
                        { from: { x: 0, y: 0, type: 'topic' }, to: { x: -220, y: 80, type: 'branch' } },
                        { from: { x: 220, y: -80, type: 'branch' }, to: { x: 370, y: -110, type: 'child' } },
                        { from: { x: 220, y: -80, type: 'branch' }, to: { x: 370, y: -50, type: 'child' } },
                        { from: { x: 220, y: 80, type: 'branch' }, to: { x: 370, y: 50, type: 'child' } },
                        { from: { x: 220, y: 80, type: 'branch' }, to: { x: 370, y: 110, type: 'child' } },
                        { from: { x: -220, y: -80, type: 'branch' }, to: { x: -370, y: -110, type: 'child' } },
                        { from: { x: -220, y: -80, type: 'branch' }, to: { x: -370, y: -50, type: 'child' } },
                        { from: { x: -220, y: 80, type: 'branch' }, to: { x: -370, y: 50, type: 'child' } },
                        { from: { x: -220, y: 80, type: 'branch' }, to: { x: -370, y: 110, type: 'child' } }
                    ],
                    params: {
                        background: '#f5f5f5'
                    }
                },
                _recommended_dimensions: {
                    width: 1000,
                    height: 600,
                    padding: 40
                }
            };
        } else {
            return {
                topic: 'Central Topic',
                children: [
                    { 
                        id: 'branch_0',
                        label: 'Branch 1', 
                        text: 'Branch 1',
                        children: [
                            { id: 'sub_0_0', label: 'Sub-item 1.1', text: 'Sub-item 1.1', children: [] },
                            { id: 'sub_0_1', label: 'Sub-item 1.2', text: 'Sub-item 1.2', children: [] }
                        ] 
                    },
                    { 
                        id: 'branch_1',
                        label: 'Branch 2', 
                        text: 'Branch 2',
                        children: [
                            { id: 'sub_1_0', label: 'Sub-item 2.1', text: 'Sub-item 2.1', children: [] },
                            { id: 'sub_1_1', label: 'Sub-item 2.2', text: 'Sub-item 2.2', children: [] }
                        ] 
                    },
                    { 
                        id: 'branch_2',
                        label: 'Branch 4', 
                        text: 'Branch 4',
                        children: [
                            { id: 'sub_2_0', label: 'Sub-item 4.1', text: 'Sub-item 4.1', children: [] },
                            { id: 'sub_2_1', label: 'Sub-item 4.2', text: 'Sub-item 4.2', children: [] }
                        ] 
                    },
                    { 
                        id: 'branch_3',
                        label: 'Branch 3', 
                        text: 'Branch 3',
                        children: [
                            { id: 'sub_3_0', label: 'Sub-item 3.1', text: 'Sub-item 3.1', children: [] },
                            { id: 'sub_3_1', label: 'Sub-item 3.2', text: 'Sub-item 3.2', children: [] }
                        ] 
                    }
                ],
                _layout: {
                    positions: {
                        'topic': { 
                            x: 0, y: 0, 
                            width: 120, height: 60, 
                            text: 'Central Topic', 
                            node_type: 'topic', 
                            angle: 0 
                        },
                        'branch_0': { 
                            x: 220, y: -80, 
                            width: 100, height: 50, 
                            text: 'Branch 1', 
                            node_type: 'branch', 
                            branch_index: 0, 
                            angle: 0 
                        },
                        'branch_1': { 
                            x: 220, y: 80, 
                            width: 100, height: 50, 
                            text: 'Branch 2', 
                            node_type: 'branch', 
                            branch_index: 1, 
                            angle: 0 
                        },
                        'branch_2': { 
                            x: -220, y: -80, 
                            width: 100, height: 50, 
                            text: 'Branch 4', 
                            node_type: 'branch', 
                            branch_index: 2, 
                            angle: 0 
                        },
                        'branch_3': { 
                            x: -220, y: 80, 
                            width: 100, height: 50, 
                            text: 'Branch 3', 
                            node_type: 'branch', 
                            branch_index: 3, 
                            angle: 0 
                        },
                        'child_0_0': { 
                            x: 370, y: -110, 
                            width: 90, height: 40, 
                            text: 'Sub-item 1.1', 
                            node_type: 'child', 
                            branch_index: 0, 
                            child_index: 0, 
                            angle: 0 
                        },
                        'child_0_1': { 
                            x: 370, y: -50, 
                            width: 90, height: 40, 
                            text: 'Sub-item 1.2', 
                            node_type: 'child', 
                            branch_index: 0, 
                            child_index: 1, 
                            angle: 0 
                        },
                        'child_1_0': { 
                            x: 370, y: 50, 
                            width: 90, height: 40, 
                            text: 'Sub-item 2.1', 
                            node_type: 'child', 
                            branch_index: 1, 
                            child_index: 0, 
                            angle: 0 
                        },
                        'child_1_1': { 
                            x: 370, y: 110, 
                            width: 90, height: 40, 
                            text: 'Sub-item 2.2', 
                            node_type: 'child', 
                            branch_index: 1, 
                            child_index: 1, 
                            angle: 0 
                        },
                        'child_2_0': { 
                            x: -370, y: -110, 
                            width: 90, height: 40, 
                            text: 'Sub-item 4.1', 
                            node_type: 'child', 
                            branch_index: 2, 
                            child_index: 0, 
                            angle: 0 
                        },
                        'child_2_1': { 
                            x: -370, y: -50, 
                            width: 90, height: 40, 
                            text: 'Sub-item 4.2', 
                            node_type: 'child', 
                            branch_index: 2, 
                            child_index: 1, 
                            angle: 0 
                        },
                        'child_3_0': { 
                            x: -370, y: 50, 
                            width: 90, height: 40, 
                            text: 'Sub-item 3.1', 
                            node_type: 'child', 
                            branch_index: 3, 
                            child_index: 0, 
                            angle: 0 
                        },
                        'child_3_1': { 
                            x: -370, y: 110, 
                            width: 90, height: 40, 
                            text: 'Sub-item 3.2', 
                            node_type: 'child', 
                            branch_index: 3, 
                            child_index: 1, 
                            angle: 0 
                        }
                    },
                    connections: [
                        { from: { x: 0, y: 0, type: 'topic' }, to: { x: 220, y: -80, type: 'branch' } },
                        { from: { x: 0, y: 0, type: 'topic' }, to: { x: 220, y: 80, type: 'branch' } },
                        { from: { x: 0, y: 0, type: 'topic' }, to: { x: -220, y: -80, type: 'branch' } },
                        { from: { x: 0, y: 0, type: 'topic' }, to: { x: -220, y: 80, type: 'branch' } },
                        { from: { x: 220, y: -80, type: 'branch' }, to: { x: 370, y: -110, type: 'child' } },
                        { from: { x: 220, y: -80, type: 'branch' }, to: { x: 370, y: -50, type: 'child' } },
                        { from: { x: 220, y: 80, type: 'branch' }, to: { x: 370, y: 50, type: 'child' } },
                        { from: { x: 220, y: 80, type: 'branch' }, to: { x: 370, y: 110, type: 'child' } },
                        { from: { x: -220, y: -80, type: 'branch' }, to: { x: -370, y: -110, type: 'child' } },
                        { from: { x: -220, y: -80, type: 'branch' }, to: { x: -370, y: -50, type: 'child' } },
                        { from: { x: -220, y: 80, type: 'branch' }, to: { x: -370, y: 50, type: 'child' } },
                        { from: { x: -220, y: 80, type: 'branch' }, to: { x: -370, y: 110, type: 'child' } }
                    ],
                    params: {
                        background: '#f5f5f5'
                    }
                },
                _recommended_dimensions: {
                    width: 1000,
                    height: 600,
                    padding: 40
                }
            };
        }
    }
    
    /**
     * Get Bubble Map template
     */
    getBubbleMapTemplate() {
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        
        if (lang === 'zh') {
            return {
                topic: '主题',
                attributes: [
                    '属性1',
                    '属性2',
                    '属性3',
                    '属性4',
                    '属性5'
                ],
                _layout: {
                    positions: {
                        '主题': { x: 350, y: 250 },
                        '属性1': { x: 200, y: 150 },
                        '属性2': { x: 500, y: 150 },
                        '属性3': { x: 200, y: 350 },
                        '属性4': { x: 500, y: 350 },
                        '属性5': { x: 350, y: 100 }
                    }
                },
                _recommended_dimensions: {
                    width: 700,
                    height: 500,
                    padding: 40
                }
            };
        } else {
            return {
                topic: 'Main Topic',
                attributes: [
                    'Attribute 1',
                    'Attribute 2',
                    'Attribute 3',
                    'Attribute 4',
                    'Attribute 5'
                ],
                _layout: {
                    positions: {
                        'Main Topic': { x: 350, y: 250 },
                        'Attribute 1': { x: 200, y: 150 },
                        'Attribute 2': { x: 500, y: 150 },
                        'Attribute 3': { x: 200, y: 350 },
                        'Attribute 4': { x: 500, y: 350 },
                        'Attribute 5': { x: 350, y: 100 }
                    }
                },
                _recommended_dimensions: {
                    width: 700,
                    height: 500,
                    padding: 40
                }
            };
        }
    }
    
    /**
     * Get Concept Map template
     */
    getConceptMapTemplate() {
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        
        if (lang === 'zh') {
            return {
                topic: '主要概念',
                concepts: ['概念1', '概念2', '概念3'],
                relationships: [
                    { from: '主要概念', to: '概念1', label: '关联' },
                    { from: '主要概念', to: '概念2', label: '包含' },
                    { from: '概念1', to: '概念3', label: '导致' }
                ],
                _layout: {
                    positions: {
                        '主要概念': { x: 350, y: 150 },
                        '概念1': { x: 200, y: 300 },
                        '概念2': { x: 500, y: 300 },
                        '概念3': { x: 350, y: 400 }
                    }
                },
                _recommended_dimensions: {
                    width: 700,
                    height: 500,
                    padding: 40
                }
            };
        } else {
            return {
                topic: 'Main Concept',
                concepts: ['Concept 1', 'Concept 2', 'Concept 3'],
                relationships: [
                    { from: 'Main Concept', to: 'Concept 1', label: 'relates to' },
                    { from: 'Main Concept', to: 'Concept 2', label: 'includes' },
                    { from: 'Concept 1', to: 'Concept 3', label: 'leads to' }
                ],
                _layout: {
                    positions: {
                        'Main Concept': { x: 350, y: 150 },
                        'Concept 1': { x: 200, y: 300 },
                        'Concept 2': { x: 500, y: 300 },
                        'Concept 3': { x: 350, y: 400 }
                    }
                },
                _recommended_dimensions: {
                    width: 700,
                    height: 500,
                    padding: 40
                }
            };
        }
    }
    
    /**
     * Get Flow Map template
     */
    getFlowMapTemplate() {
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        
        if (lang === 'zh') {
            return {
                title: '流程',
                steps: [
                    '步骤1',
                    '步骤2',
                    '步骤3',
                    '步骤4'
                ],
                substeps: [
                    {
                        step: '步骤1',
                        substeps: [
                            '子步骤1.1',
                            '子步骤1.2'
                        ]
                    },
                    {
                        step: '步骤2',
                        substeps: [
                            '子步骤2.1',
                            '子步骤2.2'
                        ]
                    },
                    {
                        step: '步骤3',
                        substeps: [
                            '子步骤3.1',
                            '子步骤3.2'
                        ]
                    },
                    {
                        step: '步骤4',
                        substeps: [
                            '子步骤4.1',
                            '子步骤4.2'
                        ]
                    }
                ],
                _recommended_dimensions: {
                    width: 800,
                    height: 600,
                    padding: 40
                }
            };
        } else {
            return {
                title: 'Process Flow',
                steps: [
                    'Step 1',
                    'Step 2',
                    'Step 3',
                    'Step 4'
                ],
                substeps: [
                    {
                        step: 'Step 1',
                        substeps: [
                            'Substep 1.1',
                            'Substep 1.2'
                        ]
                    },
                    {
                        step: 'Step 2',
                        substeps: [
                            'Substep 2.1',
                            'Substep 2.2'
                        ]
                    },
                    {
                        step: 'Step 3',
                        substeps: [
                            'Substep 3.1',
                            'Substep 3.2'
                        ]
                    },
                    {
                        step: 'Step 4',
                        substeps: [
                            'Substep 4.1',
                            'Substep 4.2'
                        ]
                    }
                ],
                _recommended_dimensions: {
                    width: 800,
                    height: 600,
                    padding: 40
                }
            };
        }
    }
    
    /**
     * Get Tree Map template
     */
    getTreeMapTemplate() {
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        
        if (lang === 'zh') {
            return {
                topic: '根主题',
                children: [
                    { 
                        text: '类别1', 
                        children: [
                            { text: '项目1.1', children: [] },
                            { text: '项目1.2', children: [] },
                            { text: '项目1.3', children: [] }
                        ] 
                    },
                    { 
                        text: '类别2', 
                        children: [
                            { text: '项目2.1', children: [] },
                            { text: '项目2.2', children: [] },
                            { text: '项目2.3', children: [] }
                        ] 
                    },
                    { 
                        text: '类别3', 
                        children: [
                            { text: '项目3.1', children: [] },
                            { text: '项目3.2', children: [] },
                            { text: '项目3.3', children: [] }
                        ] 
                    },
                    { 
                        text: '类别4', 
                        children: [
                            { text: '项目4.1', children: [] },
                            { text: '项目4.2', children: [] },
                            { text: '项目4.3', children: [] }
                        ] 
                    }
                ],
                _layout: {
                    positions: {
                        '根主题': { x: 400, y: 80 },
                        '类别1': { x: 150, y: 180 },
                        '类别2': { x: 350, y: 180 },
                        '类别3': { x: 550, y: 180 },
                        '类别4': { x: 750, y: 180 },
                        '项目1.1': { x: 80, y: 280 },
                        '项目1.2': { x: 150, y: 280 },
                        '项目1.3': { x: 220, y: 280 },
                        '项目2.1': { x: 280, y: 280 },
                        '项目2.2': { x: 350, y: 280 },
                        '项目2.3': { x: 420, y: 280 },
                        '项目3.1': { x: 480, y: 280 },
                        '项目3.2': { x: 550, y: 280 },
                        '项目3.3': { x: 620, y: 280 },
                        '项目4.1': { x: 680, y: 280 },
                        '项目4.2': { x: 750, y: 280 },
                        '项目4.3': { x: 820, y: 280 }
                    }
                },
                _recommended_dimensions: {
                    width: 900,
                    height: 400,
                    padding: 60
                }
            };
        } else {
            return {
                topic: 'Root Topic',
                children: [
                    { 
                        text: 'Category 1', 
                        children: [
                            { text: 'Item 1.1', children: [] },
                            { text: 'Item 1.2', children: [] },
                            { text: 'Item 1.3', children: [] }
                        ] 
                    },
                    { 
                        text: 'Category 2', 
                        children: [
                            { text: 'Item 2.1', children: [] },
                            { text: 'Item 2.2', children: [] },
                            { text: 'Item 2.3', children: [] }
                        ] 
                    },
                    { 
                        text: 'Category 3', 
                        children: [
                            { text: 'Item 3.1', children: [] },
                            { text: 'Item 3.2', children: [] },
                            { text: 'Item 3.3', children: [] }
                        ] 
                    },
                    { 
                        text: 'Category 4', 
                        children: [
                            { text: 'Item 4.1', children: [] },
                            { text: 'Item 4.2', children: [] },
                            { text: 'Item 4.3', children: [] }
                        ] 
                    }
                ],
                _layout: {
                    positions: {
                        'Root Topic': { x: 400, y: 80 },
                        'Category 1': { x: 150, y: 180 },
                        'Category 2': { x: 350, y: 180 },
                        'Category 3': { x: 550, y: 180 },
                        'Category 4': { x: 750, y: 180 },
                        'Item 1.1': { x: 80, y: 280 },
                        'Item 1.2': { x: 150, y: 280 },
                        'Item 1.3': { x: 220, y: 280 },
                        'Item 2.1': { x: 280, y: 280 },
                        'Item 2.2': { x: 350, y: 280 },
                        'Item 2.3': { x: 420, y: 280 },
                        'Item 3.1': { x: 480, y: 280 },
                        'Item 3.2': { x: 550, y: 280 },
                        'Item 3.3': { x: 620, y: 280 },
                        'Item 4.1': { x: 680, y: 280 },
                        'Item 4.2': { x: 750, y: 280 },
                        'Item 4.3': { x: 820, y: 280 }
                    }
                },
                _recommended_dimensions: {
                    width: 900,
                    height: 400,
                    padding: 60
                }
            };
        }
    }
    
    /**
     * Calculate adaptive dimensions based on current window size
     * This ensures templates are sized appropriately for the user's screen
     */
    calculateAdaptiveDimensions() {
        try {
            // Get current window dimensions
            const windowWidth = window.innerWidth;
            const windowHeight = window.innerHeight;
            
            // Calculate available canvas space (accounting for toolbar and status bar)
            // Toolbar height: ~60px, Status bar height: ~40px
            const toolbarHeight = 60;
            const statusBarHeight = 40;
            const availableHeight = windowHeight - toolbarHeight - statusBarHeight;
            
            // Calculate available width (accounting for properties panel space)
            // Always reserve space for properties panel to prevent overlap
            const propertyPanelWidth = 320;
            const availableWidth = windowWidth - propertyPanelWidth;
            
            // Calculate optimal dimensions with padding
            const padding = Math.min(40, Math.max(20, Math.min(availableWidth, availableHeight) * 0.05));
            
            // Ensure minimum dimensions for readability
            const minWidth = 400;
            const minHeight = 300;
            
            const adaptiveWidth = Math.max(minWidth, availableWidth * 0.9);
            const adaptiveHeight = Math.max(minHeight, availableHeight * 0.9);
            
            const dimensions = {
                width: Math.round(adaptiveWidth),
                height: Math.round(adaptiveHeight),
                padding: Math.round(padding)
            };
            
            logger.debug('DiagramSelector', 'Calculated adaptive dimensions', dimensions);
            
            return dimensions;
            
        } catch (error) {
            logger.error('DiagramSelector', 'Error calculating adaptive dimensions', error);
            // Fallback to reasonable defaults
            return {
                width: 800,
                height: 600,
                padding: 40
            };
        }
    }

    /**
     * Get Brace Map template
     */
    getBraceMapTemplate() {
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        
        if (lang === 'zh') {
            return {
                whole: '主题',
                dimension: '',  // Empty by default - users can specify or leave empty for LLM to auto-select
                parts: [
                    {
                        name: '部分1',
                        subparts: [
                            { name: '子部分1.1' },
                            { name: '子部分1.2' }
                        ]
                    },
                    {
                        name: '部分2',
                        subparts: [
                            { name: '子部分2.1' },
                            { name: '子部分2.2' }
                        ]
                    },
                    {
                        name: '部分3',
                        subparts: [
                            { name: '子部分3.1' },
                            { name: '子部分3.2' }
                        ]
                    }
                ],
                // Don't include alternative_dimensions in template - LLM will generate them
                _recommended_dimensions: this.calculateAdaptiveDimensions()
            };
        } else {
            return {
                whole: 'Main Topic',
                dimension: '',  // Empty by default - users can specify or leave empty for LLM to auto-select
                parts: [
                    {
                        name: 'Part 1',
                        subparts: [
                            { name: 'Subpart 1.1' },
                            { name: 'Subpart 1.2' }
                        ]
                    },
                    {
                        name: 'Part 2',
                        subparts: [
                            { name: 'Subpart 2.1' },
                            { name: 'Subpart 2.2' }
                        ]
                    },
                    {
                        name: 'Part 3',
                        subparts: [
                            { name: 'Subpart 3.1' },
                            { name: 'Subpart 3.2' }
                        ]
                    }
                ],
                // Don't include alternative_dimensions in template - LLM will generate them
                _recommended_dimensions: this.calculateAdaptiveDimensions()
            };
        }
    }
    
    /**
     * Get Factor Analysis template (因素分析法)
     */
    getFactorAnalysisTemplate() {
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        
        if (lang === 'zh') {
            return {
                topic: '中心议题',
                children: [
                    { 
                        id: 'branch_0',
                        label: '因素1', 
                        text: '因素1',
                        children: [
                            { id: 'sub_0_0', label: '细节1.1', text: '细节1.1', children: [] },
                            { id: 'sub_0_1', label: '细节1.2', text: '细节1.2', children: [] }
                        ] 
                    },
                    { 
                        id: 'branch_1',
                        label: '因素2', 
                        text: '因素2',
                        children: [
                            { id: 'sub_1_0', label: '细节2.1', text: '细节2.1', children: [] },
                            { id: 'sub_1_1', label: '细节2.2', text: '细节2.2', children: [] }
                        ] 
                    },
                    { 
                        id: 'branch_2',
                        label: '因素3', 
                        text: '因素3',
                        children: [
                            { id: 'sub_2_0', label: '细节3.1', text: '细节3.1', children: [] },
                            { id: 'sub_2_1', label: '细节3.2', text: '细节3.2', children: [] }
                        ] 
                    },
                    { 
                        id: 'branch_3',
                        label: '因素4', 
                        text: '因素4',
                        children: [
                            { id: 'sub_3_0', label: '细节4.1', text: '细节4.1', children: [] },
                            { id: 'sub_3_1', label: '细节4.2', text: '细节4.2', children: [] }
                        ] 
                    }
                ],
                _layout: { positions: {}, connections: [], params: { background: '#f5f5f5' } },
                _recommended_dimensions: { width: 1000, height: 600, padding: 40 }
            };
        } else {
            return {
                topic: 'Central Issue',
                children: [
                    { id: 'branch_0', label: 'Factor 1', text: 'Factor 1', 
                      children: [
                          { id: 'sub_0_0', label: 'Detail 1.1', text: 'Detail 1.1', children: [] },
                          { id: 'sub_0_1', label: 'Detail 1.2', text: 'Detail 1.2', children: [] }
                      ] 
                    },
                    { id: 'branch_1', label: 'Factor 2', text: 'Factor 2',
                      children: [
                          { id: 'sub_1_0', label: 'Detail 2.1', text: 'Detail 2.1', children: [] },
                          { id: 'sub_1_1', label: 'Detail 2.2', text: 'Detail 2.2', children: [] }
                      ] 
                    },
                    { id: 'branch_2', label: 'Factor 3', text: 'Factor 3',
                      children: [
                          { id: 'sub_2_0', label: 'Detail 3.1', text: 'Detail 3.1', children: [] },
                          { id: 'sub_2_1', label: 'Detail 3.2', text: 'Detail 3.2', children: [] }
                      ] 
                    },
                    { id: 'branch_3', label: 'Factor 4', text: 'Factor 4',
                      children: [
                          { id: 'sub_3_0', label: 'Detail 4.1', text: 'Detail 4.1', children: [] },
                          { id: 'sub_3_1', label: 'Detail 4.2', text: 'Detail 4.2', children: [] }
                      ] 
                    }
                ],
                _layout: { positions: {}, connections: [], params: { background: '#f5f5f5' } },
                _recommended_dimensions: { width: 1000, height: 600, padding: 40 }
            };
        }
    }
    
    /**
     * Get Three-Position Analysis template (三位分析法)
     */
    getThreePositionAnalysisTemplate() {
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        
        if (lang === 'zh') {
            return {
                topic: '问题',
                children: [
                    { id: 'branch_0', label: '角度1', text: '角度1', children: [
                        { id: 'sub_0_0', label: '观点1.1', text: '观点1.1', children: [] }
                    ]},
                    { id: 'branch_1', label: '角度2', text: '角度2', children: [
                        { id: 'sub_1_0', label: '观点2.1', text: '观点2.1', children: [] }
                    ]},
                    { id: 'branch_2', label: '角度3', text: '角度3', children: [
                        { id: 'sub_2_0', label: '观点3.1', text: '观点3.1', children: [] }
                    ]}
                ],
                _layout: { positions: {}, connections: [], params: { background: '#f5f5f5' } },
                _recommended_dimensions: { width: 1000, height: 600, padding: 40 }
            };
        } else {
            return {
                topic: 'Issue',
                children: [
                    { id: 'branch_0', label: 'Position 1', text: 'Position 1', children: [
                        { id: 'sub_0_0', label: 'View 1.1', text: 'View 1.1', children: [] }
                    ]},
                    { id: 'branch_1', label: 'Position 2', text: 'Position 2', children: [
                        { id: 'sub_1_0', label: 'View 2.1', text: 'View 2.1', children: [] }
                    ]},
                    { id: 'branch_2', label: 'Position 3', text: 'Position 3', children: [
                        { id: 'sub_2_0', label: 'View 3.1', text: 'View 3.1', children: [] }
                    ]}
                ],
                _layout: { positions: {}, connections: [], params: { background: '#f5f5f5' } },
                _recommended_dimensions: { width: 1000, height: 600, padding: 40 }
            };
        }
    }
    
    /**
     * Get Perspective Analysis template (换位分析法)
     */
    getPerspectiveAnalysisTemplate() {
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        
        if (lang === 'zh') {
            return {
                topic: '情境',
                children: [
                    { id: 'branch_0', label: '视角A', text: '视角A', children: [
                        { id: 'sub_0_0', label: '感受1', text: '感受1', children: [] },
                        { id: 'sub_0_1', label: '反应1', text: '反应1', children: [] }
                    ]},
                    { id: 'branch_1', label: '视角B', text: '视角B', children: [
                        { id: 'sub_1_0', label: '感受2', text: '感受2', children: [] },
                        { id: 'sub_1_1', label: '反应2', text: '反应2', children: [] }
                    ]}
                ],
                _layout: { positions: {}, connections: [], params: { background: '#f5f5f5' } },
                _recommended_dimensions: { width: 1000, height: 600, padding: 40 }
            };
        } else {
            return {
                topic: 'Situation',
                children: [
                    { id: 'branch_0', label: 'Perspective A', text: 'Perspective A', children: [
                        { id: 'sub_0_0', label: 'Feeling 1', text: 'Feeling 1', children: [] },
                        { id: 'sub_0_1', label: 'Response 1', text: 'Response 1', children: [] }
                    ]},
                    { id: 'branch_1', label: 'Perspective B', text: 'Perspective B', children: [
                        { id: 'sub_1_0', label: 'Feeling 2', text: 'Feeling 2', children: [] },
                        { id: 'sub_1_1', label: 'Response 2', text: 'Response 2', children: [] }
                    ]}
                ],
                _layout: { positions: {}, connections: [], params: { background: '#f5f5f5' } },
                _recommended_dimensions: { width: 1000, height: 600, padding: 40 }
            };
        }
    }
    
    /**
     * Get Goal Analysis template (目标分析法)
     */
    getGoalAnalysisTemplate() {
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        
        if (lang === 'zh') {
            return {
                topic: '目标',
                children: [
                    { id: 'branch_0', label: '行动1', text: '行动1', children: [
                        { id: 'sub_0_0', label: '步骤1.1', text: '步骤1.1', children: [] },
                        { id: 'sub_0_1', label: '步骤1.2', text: '步骤1.2', children: [] }
                    ]},
                    { id: 'branch_1', label: '行动2', text: '行动2', children: [
                        { id: 'sub_1_0', label: '步骤2.1', text: '步骤2.1', children: [] },
                        { id: 'sub_1_1', label: '步骤2.2', text: '步骤2.2', children: [] }
                    ]},
                    { id: 'branch_2', label: '行动3', text: '行动3', children: [
                        { id: 'sub_2_0', label: '步骤3.1', text: '步骤3.1', children: [] },
                        { id: 'sub_2_1', label: '步骤3.2', text: '步骤3.2', children: [] }
                    ]},
                    { id: 'branch_3', label: '行动4', text: '行动4', children: [
                        { id: 'sub_3_0', label: '步骤4.1', text: '步骤4.1', children: [] },
                        { id: 'sub_3_1', label: '步骤4.2', text: '步骤4.2', children: [] }
                    ]}
                ],
                _layout: { positions: {}, connections: [], params: { background: '#f5f5f5' } },
                _recommended_dimensions: { width: 1000, height: 600, padding: 40 }
            };
        } else {
            return {
                topic: 'Goal',
                children: [
                    { id: 'branch_0', label: 'Action 1', text: 'Action 1', children: [
                        { id: 'sub_0_0', label: 'Step 1.1', text: 'Step 1.1', children: [] },
                        { id: 'sub_0_1', label: 'Step 1.2', text: 'Step 1.2', children: [] }
                    ]},
                    { id: 'branch_1', label: 'Action 2', text: 'Action 2', children: [
                        { id: 'sub_1_0', label: 'Step 2.1', text: 'Step 2.1', children: [] },
                        { id: 'sub_1_1', label: 'Step 2.2', text: 'Step 2.2', children: [] }
                    ]},
                    { id: 'branch_2', label: 'Action 3', text: 'Action 3', children: [
                        { id: 'sub_2_0', label: 'Step 3.1', text: 'Step 3.1', children: [] },
                        { id: 'sub_2_1', label: 'Step 3.2', text: 'Step 3.2', children: [] }
                    ]},
                    { id: 'branch_3', label: 'Action 4', text: 'Action 4', children: [
                        { id: 'sub_3_0', label: 'Step 4.1', text: 'Step 4.1', children: [] },
                        { id: 'sub_3_1', label: 'Step 4.2', text: 'Step 4.2', children: [] }
                    ]}
                ],
                _layout: { positions: {}, connections: [], params: { background: '#f5f5f5' } },
                _recommended_dimensions: { width: 1000, height: 600, padding: 40 }
            };
        }
    }
    
    /**
     * Get Possibility Analysis template (可能分析法)
     */
    getPossibilityAnalysisTemplate() {
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        
        if (lang === 'zh') {
            return {
                topic: '决策',
                children: [
                    { id: 'branch_0', label: '可能性1', text: '可能性1', children: [
                        { id: 'sub_0_0', label: '优势', text: '优势', children: [] },
                        { id: 'sub_0_1', label: '劣势', text: '劣势', children: [] }
                    ]},
                    { id: 'branch_1', label: '可能性2', text: '可能性2', children: [
                        { id: 'sub_1_0', label: '优势', text: '优势', children: [] },
                        { id: 'sub_1_1', label: '劣势', text: '劣势', children: [] }
                    ]},
                    { id: 'branch_2', label: '可能性3', text: '可能性3', children: [
                        { id: 'sub_2_0', label: '优势', text: '优势', children: [] },
                        { id: 'sub_2_1', label: '劣势', text: '劣势', children: [] }
                    ]}
                ],
                _layout: { positions: {}, connections: [], params: { background: '#f5f5f5' } },
                _recommended_dimensions: { width: 1000, height: 600, padding: 40 }
            };
        } else {
            return {
                topic: 'Decision',
                children: [
                    { id: 'branch_0', label: 'Possibility 1', text: 'Possibility 1', children: [
                        { id: 'sub_0_0', label: 'Pros', text: 'Pros', children: [] },
                        { id: 'sub_0_1', label: 'Cons', text: 'Cons', children: [] }
                    ]},
                    { id: 'branch_1', label: 'Possibility 2', text: 'Possibility 2', children: [
                        { id: 'sub_1_0', label: 'Pros', text: 'Pros', children: [] },
                        { id: 'sub_1_1', label: 'Cons', text: 'Cons', children: [] }
                    ]},
                    { id: 'branch_2', label: 'Possibility 3', text: 'Possibility 3', children: [
                        { id: 'sub_2_0', label: 'Pros', text: 'Pros', children: [] },
                        { id: 'sub_2_1', label: 'Cons', text: 'Cons', children: [] }
                    ]}
                ],
                _layout: { positions: {}, connections: [], params: { background: '#f5f5f5' } },
                _recommended_dimensions: { width: 1000, height: 600, padding: 40 }
            };
        }
    }
    
    /**
     * Get Result Analysis template (结果分析法)
     */
    getResultAnalysisTemplate() {
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        
        if (lang === 'zh') {
            return {
                topic: '行动',
                children: [
                    { id: 'branch_0', label: '短期结果', text: '短期结果', children: [
                        { id: 'sub_0_0', label: '影响1', text: '影响1', children: [] },
                        { id: 'sub_0_1', label: '影响2', text: '影响2', children: [] }
                    ]},
                    { id: 'branch_1', label: '长期结果', text: '长期结果', children: [
                        { id: 'sub_1_0', label: '影响1', text: '影响1', children: [] },
                        { id: 'sub_1_1', label: '影响2', text: '影响2', children: [] }
                    ]}
                ],
                _layout: { positions: {}, connections: [], params: { background: '#f5f5f5' } },
                _recommended_dimensions: { width: 1000, height: 600, padding: 40 }
            };
        } else {
            return {
                topic: 'Action',
                children: [
                    { id: 'branch_0', label: 'Short-term Results', text: 'Short-term Results', children: [
                        { id: 'sub_0_0', label: 'Impact 1', text: 'Impact 1', children: [] },
                        { id: 'sub_0_1', label: 'Impact 2', text: 'Impact 2', children: [] }
                    ]},
                    { id: 'branch_1', label: 'Long-term Results', text: 'Long-term Results', children: [
                        { id: 'sub_1_0', label: 'Impact 1', text: 'Impact 1', children: [] },
                        { id: 'sub_1_1', label: 'Impact 2', text: 'Impact 2', children: [] }
                    ]}
                ],
                _layout: { positions: {}, connections: [], params: { background: '#f5f5f5' } },
                _recommended_dimensions: { width: 1000, height: 600, padding: 40 }
            };
        }
    }
    
    /**
     * Get 5W1H Analysis template (六何分析法)
     */
    getFiveWOneHTemplate() {
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        
        if (lang === 'zh') {
            return {
                topic: '问题',
                children: [
                    { id: 'branch_0', label: 'What (什么)', text: 'What (什么)', children: [
                        { id: 'sub_0_0', label: '内容', text: '内容', children: [] }
                    ]},
                    { id: 'branch_1', label: 'Why (为什么)', text: 'Why (为什么)', children: [
                        { id: 'sub_1_0', label: '原因', text: '原因', children: [] }
                    ]},
                    { id: 'branch_2', label: 'When (何时)', text: 'When (何时)', children: [
                        { id: 'sub_2_0', label: '时间', text: '时间', children: [] }
                    ]},
                    { id: 'branch_3', label: 'Where (何地)', text: 'Where (何地)', children: [
                        { id: 'sub_3_0', label: '地点', text: '地点', children: [] }
                    ]},
                    { id: 'branch_4', label: 'Who (谁)', text: 'Who (谁)', children: [
                        { id: 'sub_4_0', label: '人物', text: '人物', children: [] }
                    ]},
                    { id: 'branch_5', label: 'How (如何)', text: 'How (如何)', children: [
                        { id: 'sub_5_0', label: '方法', text: '方法', children: [] }
                    ]}
                ],
                _layout: { positions: {}, connections: [], params: { background: '#f5f5f5' } },
                _recommended_dimensions: { width: 1000, height: 600, padding: 40 }
            };
        } else {
            return {
                topic: 'Issue',
                children: [
                    { id: 'branch_0', label: 'What', text: 'What', children: [
                        { id: 'sub_0_0', label: 'Content', text: 'Content', children: [] }
                    ]},
                    { id: 'branch_1', label: 'Why', text: 'Why', children: [
                        { id: 'sub_1_0', label: 'Reason', text: 'Reason', children: [] }
                    ]},
                    { id: 'branch_2', label: 'When', text: 'When', children: [
                        { id: 'sub_2_0', label: 'Time', text: 'Time', children: [] }
                    ]},
                    { id: 'branch_3', label: 'Where', text: 'Where', children: [
                        { id: 'sub_3_0', label: 'Location', text: 'Location', children: [] }
                    ]},
                    { id: 'branch_4', label: 'Who', text: 'Who', children: [
                        { id: 'sub_4_0', label: 'Person', text: 'Person', children: [] }
                    ]},
                    { id: 'branch_5', label: 'How', text: 'How', children: [
                        { id: 'sub_5_0', label: 'Method', text: 'Method', children: [] }
                    ]}
                ],
                _layout: { positions: {}, connections: [], params: { background: '#f5f5f5' } },
                _recommended_dimensions: { width: 1000, height: 600, padding: 40 }
            };
        }
    }
    
    /**
     * Get WHWM Analysis template (WHWM分析法)
     */
    getWHWMAnalysisTemplate() {
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        
        if (lang === 'zh') {
            return {
                topic: '项目',
                children: [
                    { id: 'branch_0', label: 'What (做什么)', text: 'What (做什么)', children: [
                        { id: 'sub_0_0', label: '任务', text: '任务', children: [] }
                    ]},
                    { id: 'branch_1', label: 'How (怎么做)', text: 'How (怎么做)', children: [
                        { id: 'sub_1_0', label: '方法', text: '方法', children: [] }
                    ]},
                    { id: 'branch_2', label: 'Who (谁来做)', text: 'Who (谁来做)', children: [
                        { id: 'sub_2_0', label: '负责人', text: '负责人', children: [] }
                    ]},
                    { id: 'branch_3', label: 'Measure (如何衡量)', text: 'Measure (如何衡量)', children: [
                        { id: 'sub_3_0', label: '标准', text: '标准', children: [] }
                    ]}
                ],
                _layout: { positions: {}, connections: [], params: { background: '#f5f5f5' } },
                _recommended_dimensions: { width: 1000, height: 600, padding: 40 }
            };
        } else {
            return {
                topic: 'Project',
                children: [
                    { id: 'branch_0', label: 'What', text: 'What', children: [
                        { id: 'sub_0_0', label: 'Task', text: 'Task', children: [] }
                    ]},
                    { id: 'branch_1', label: 'How', text: 'How', children: [
                        { id: 'sub_1_0', label: 'Method', text: 'Method', children: [] }
                    ]},
                    { id: 'branch_2', label: 'Who', text: 'Who', children: [
                        { id: 'sub_2_0', label: 'Owner', text: 'Owner', children: [] }
                    ]},
                    { id: 'branch_3', label: 'Measure', text: 'Measure', children: [
                        { id: 'sub_3_0', label: 'Metrics', text: 'Metrics', children: [] }
                    ]}
                ],
                _layout: { positions: {}, connections: [], params: { background: '#f5f5f5' } },
                _recommended_dimensions: { width: 1000, height: 600, padding: 40 }
            };
        }
    }
    
    /**
     * Get Four Quadrant Analysis template (四象限分析法)
     */
    getFourQuadrantTemplate() {
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        
        if (lang === 'zh') {
            return {
                topic: '分析主题',
                children: [
                    { id: 'branch_0', label: '象限1', text: '象限1', children: [
                        { id: 'sub_0_0', label: '项目1', text: '项目1', children: [] },
                        { id: 'sub_0_1', label: '项目2', text: '项目2', children: [] }
                    ]},
                    { id: 'branch_1', label: '象限2', text: '象限2', children: [
                        { id: 'sub_1_0', label: '项目1', text: '项目1', children: [] },
                        { id: 'sub_1_1', label: '项目2', text: '项目2', children: [] }
                    ]},
                    { id: 'branch_2', label: '象限3', text: '象限3', children: [
                        { id: 'sub_2_0', label: '项目1', text: '项目1', children: [] },
                        { id: 'sub_2_1', label: '项目2', text: '项目2', children: [] }
                    ]},
                    { id: 'branch_3', label: '象限4', text: '象限4', children: [
                        { id: 'sub_3_0', label: '项目1', text: '项目1', children: [] },
                        { id: 'sub_3_1', label: '项目2', text: '项目2', children: [] }
                    ]}
                ],
                _layout: { positions: {}, connections: [], params: { background: '#f5f5f5' } },
                _recommended_dimensions: { width: 1000, height: 600, padding: 40 }
            };
        } else {
            return {
                topic: 'Analysis Topic',
                children: [
                    { id: 'branch_0', label: 'Quadrant 1', text: 'Quadrant 1', children: [
                        { id: 'sub_0_0', label: 'Item 1', text: 'Item 1', children: [] },
                        { id: 'sub_0_1', label: 'Item 2', text: 'Item 2', children: [] }
                    ]},
                    { id: 'branch_1', label: 'Quadrant 2', text: 'Quadrant 2', children: [
                        { id: 'sub_1_0', label: 'Item 1', text: 'Item 1', children: [] },
                        { id: 'sub_1_1', label: 'Item 2', text: 'Item 2', children: [] }
                    ]},
                    { id: 'branch_2', label: 'Quadrant 3', text: 'Quadrant 3', children: [
                        { id: 'sub_2_0', label: 'Item 1', text: 'Item 1', children: [] },
                        { id: 'sub_2_1', label: 'Item 2', text: 'Item 2', children: [] }
                    ]},
                    { id: 'branch_3', label: 'Quadrant 4', text: 'Quadrant 4', children: [
                        { id: 'sub_3_0', label: 'Item 1', text: 'Item 1', children: [] },
                        { id: 'sub_3_1', label: 'Item 2', text: 'Item 2', children: [] }
                    ]}
                ],
                _layout: { positions: {}, connections: [], params: { background: '#f5f5f5' } },
                _recommended_dimensions: { width: 1000, height: 600, padding: 40 }
            };
        }
    }
}

// Initialize when DOM is ready
if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', () => {
        window.diagramSelector = new DiagramSelector();
    });
}

