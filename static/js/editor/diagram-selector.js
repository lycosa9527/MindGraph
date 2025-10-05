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
                
                console.log('DiagramSelector: Card clicked', {
                    cardType: card.dataset.type,
                    landingDisplay: landing?.style.display,
                    editorDisplay: editorInterface?.style.display,
                    editorActive: this.editorActive,
                    hasSession: !!this.currentSession,
                    target: e.target.tagName,
                    currentTarget: e.currentTarget.className
                });
                
                // CRITICAL: Check for state mismatch first
                const domInGalleryMode = landing && landing.style.display !== 'none' && 
                                        (!editorInterface || editorInterface.style.display === 'none');
                const flagsSayEditorActive = this.editorActive || this.currentSession;
                
                // If DOM shows gallery but flags say editor active -> FORCE RESET
                if (domInGalleryMode && flagsSayEditorActive) {
                    console.warn('DiagramSelector: STATE MISMATCH DETECTED - DOM in gallery but flags say editor active!');
                    console.warn('DiagramSelector: Triggering force reset...');
                    this.forceReset();
                    // After reset, allow the click to proceed
                    const diagramType = card.dataset.type;
                    console.log('DiagramSelector: Card click PROCEEDING after reset for:', diagramType);
                    this.selectDiagram(diagramType);
                    return;
                }
                
                // FIXED: Use editorActive flag instead of DOM checks for reliability
                if (this.editorActive) {
                    console.warn('DiagramSelector: Card click BLOCKED - editor is active (flag check)');
                    e.stopPropagation();
                    e.preventDefault();
                    return;
                }
                
                // Secondary check: Verify DOM state matches our flags (opposite direction)
                if (!landing || landing.style.display === 'none' || 
                    (editorInterface && editorInterface.style.display !== 'none')) {
                    console.warn('DiagramSelector: Card click BLOCKED - DOM in editor mode, resetting...');
                    // Force reset to recover from inconsistent state
                    this.forceReset();
                    e.stopPropagation();
                    e.preventDefault();
                    return;
                }
                
                const diagramType = card.dataset.type;
                console.log('DiagramSelector: Card click PROCEEDING for:', diagramType);
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
        
        const message = `SESSION STARTED - ID: ${sessionId} | Type: ${diagramType} | Time: ${this.currentSession.startTime}`;
        console.log('DiagramSelector:', message);
        
        // Send to backend terminal
        this.logToBackend('INFO', message, {
            sessionId: sessionId,
            diagramType: diagramType,
            startTime: this.currentSession.startTime
        });
        
        return sessionId;
    }
    
    /**
     * Send log to backend terminal console
     */
    logToBackend(level, message, data = null) {
        try {
            fetch('/api/frontend_log', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    level: level,
                    message: message,
                    data: data,
                    source: 'DiagramSelector',
                    sessionId: this.currentSession?.id
                })
            }).catch(() => {});
        } catch (e) {}
    }
    
    /**
     * End the current editing session
     */
    endSession() {
        if (this.currentSession) {
            console.log('DiagramSelector: ========== SESSION ENDED ==========');
            console.log('DiagramSelector: Session ID:', this.currentSession.id);
            console.log('DiagramSelector: Diagram Type:', this.currentSession.diagramType);
            console.log('DiagramSelector: Duration:', 
                (new Date() - new Date(this.currentSession.startTime)) / 1000, 'seconds');
            console.log('DiagramSelector: ========================================');
        }
        
        this.currentSession = null;
        this.editorActive = false;
        
        console.log('DiagramSelector: Session ended - editorActive:', this.editorActive);
    }
    
    /**
     * Force reset to gallery mode - recovery from inconsistent state
     */
    forceReset() {
        console.warn('DiagramSelector: FORCE RESET - Recovering from inconsistent state');
        
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
        
        console.warn('DiagramSelector: Force reset complete - please try clicking again');
    }
    
    /**
     * Validate that we're in the correct session for a diagram operation
     */
    validateSession(diagramType, operation = 'operation') {
        if (!this.currentSession) {
            console.error(`DiagramSelector: ${operation} rejected - No active session!`);
            return false;
        }
        
        if (this.currentSession.diagramType !== diagramType) {
            console.error(`DiagramSelector: ${operation} rejected - Session diagram mismatch!`);
            console.error('DiagramSelector: Session diagram:', this.currentSession.diagramType);
            console.error('DiagramSelector: Requested diagram:', diagramType);
            console.error('DiagramSelector: Session ID:', this.currentSession.id);
            return false;
        }
        
        return true;
    }
    
    /**
     * Select a diagram type
     */
    selectDiagram(diagramType) {
        // CRITICAL: Check if there's an active session
        if (this.currentSession) {
            console.error('DiagramSelector: BLOCKED - Active session in progress!');
            console.error('DiagramSelector: Current session ID:', this.currentSession.id);
            console.error('DiagramSelector: Current diagram:', this.currentSession.diagramType);
            console.error('DiagramSelector: Attempted switch to:', diagramType);
            console.error('DiagramSelector: Stack trace:', new Error().stack);
            return;
        }
        
        // CRITICAL: Check global flag
        if (this.editorActive) {
            console.error('DiagramSelector: BLOCKED BY FLAG - Cannot switch diagram while editor is active!');
            console.error('DiagramSelector: Attempted switch to:', diagramType);
            console.error('DiagramSelector: Current editor:', window.currentEditor?.diagramType);
            console.error('DiagramSelector: Stack trace:', new Error().stack);
            return;
        }
        
        // CRITICAL: Verify we're actually in gallery mode before switching
        const landing = document.getElementById('editor-landing');
        const editorInterface = document.getElementById('editor-interface');
        
        console.log('DiagramSelector: selectDiagram called', {
            diagramType,
            landingDisplay: landing?.style.display,
            editorDisplay: editorInterface?.style.display,
            hasActiveEditor: !!window.currentEditor,
            editorActiveFlag: this.editorActive
        });
        
        // Double-check we're in gallery view
        if (editorInterface && editorInterface.style.display !== 'none') {
            console.error('DiagramSelector: BLOCKED BY DOM CHECK - Cannot switch diagram while editor is active!');
            console.error('DiagramSelector: Current editor diagram type:', window.currentEditor?.diagramType);
            return;
        }
        
        const diagramConfig = this.diagramTypes[diagramType];
        if (diagramConfig) {
            console.log(`DiagramSelector: Proceeding with diagram selection: ${diagramType}`);
            // Get a fresh template using the factory method
            const freshTemplate = this.getTemplate(diagramType);
            this.transitionToEditor(diagramType, freshTemplate, diagramConfig.name);
        } else {
            console.error(`DiagramSelector: Unknown diagram type: ${diagramType}`);
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
            console.error(`No template found for: ${diagramType}`);
            return null;
        }
        
        // Call the factory function to generate a fresh template
        if (typeof diagramConfig.templateFactory === 'function') {
            return diagramConfig.templateFactory();
        }
        
        console.error(`No template factory found for: ${diagramType}`);
        return null;
    }
    
    /**
     * Transition to editor interface
     */
    transitionToEditor(diagramType, template, diagramName) {
        console.log('DiagramSelector: ============= TRANSITION TO EDITOR =============');
        console.log('DiagramSelector: Diagram type:', diagramType);
        console.log('DiagramSelector: Diagram name:', diagramName);
        console.log('DiagramSelector: Stack trace:', new Error().stack);
        
        // Clean up previous editor and canvas first
        this.cleanupCanvas();
        
        // Hide landing page
        const landing = document.getElementById('editor-landing');
        if (landing) {
            landing.style.display = 'none';
            console.log('DiagramSelector: Landing page hidden');
        }
        
        // Show editor interface
        const editorInterface = document.getElementById('editor-interface');
        if (editorInterface) {
            editorInterface.style.display = 'flex';
            console.log('DiagramSelector: Editor interface shown');
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
            
            console.log(`DiagramSelector: Editor initialized successfully for: ${diagramType}`);
            console.log('DiagramSelector: ============= TRANSITION COMPLETE =============');
        } catch (error) {
            console.error('DiagramSelector: Error initializing editor:', error);
            this.endSession();  // End session on error
            alert('Error loading editor. Please try again.');
            this.backToGallery();
        }
    }
    
    /**
     * Clean up canvas and previous editor
     */
    cleanupCanvas() {
        console.log('DiagramSelector: Cleaning up canvas and editor');
        
        // Clear the D3 container
        const container = document.getElementById('d3-container');
        if (container) {
            // Remove all SVG elements
            d3.select('#d3-container').selectAll('*').remove();
            console.log('DiagramSelector: Canvas cleared');
        }
        
        // Clear any existing editor
        // Note: ToolbarManager cleanup is handled automatically via the session registry
        // When a new ToolbarManager is created, it will destroy old instances from different sessions
        if (window.currentEditor) {
            // Clear the toolbar manager's property panel if method exists
            if (window.currentEditor.toolbarManager && 
                typeof window.currentEditor.toolbarManager.clearPropertyPanel === 'function') {
                window.currentEditor.toolbarManager.clearPropertyPanel();
                console.log('DiagramSelector: Property panel cleared');
            }
            
            window.currentEditor = null;
            console.log('DiagramSelector: Editor reference cleared');
        }
        
        // Hide property panel when cleaning up
        const propertyPanel = document.getElementById('property-panel');
        if (propertyPanel) {
            propertyPanel.style.display = 'none';
        }
        
        console.log('DiagramSelector: Cleanup complete (ToolbarManager cleanup handled by session registry)');
    }
    
    /**
     * Return to gallery
     */
    backToGallery() {
        console.log('DiagramSelector: ========== RETURNING TO GALLERY ==========');
        console.log('DiagramSelector: Current state before cleanup:', {
            hasSession: !!this.currentSession,
            editorActive: this.editorActive,
            hasCurrentEditor: !!window.currentEditor
        });
        
        // End the current session FIRST (critical!)
        this.endSession();
        
        // Clean up canvas and editor
        this.cleanupCanvas();
        
        // Close AI assistant if open and reset button state
        const aiPanel = document.getElementById('ai-assistant-panel');
        if (aiPanel && !aiPanel.classList.contains('collapsed')) {
            aiPanel.classList.add('collapsed');
        }
        const mindmateBtn = document.getElementById('mindmate-ai-btn');
        if (mindmateBtn) {
            mindmateBtn.classList.remove('active');
        }
        
        // Hide property panel
        const propertyPanel = document.getElementById('property-panel');
        if (propertyPanel) {
            propertyPanel.style.display = 'none';
        }
        
        // Show landing page (use requestAnimationFrame for reliable DOM update)
        requestAnimationFrame(() => {
            const landing = document.getElementById('editor-landing');
            if (landing) {
                landing.style.display = 'block';
                console.log('DiagramSelector: Landing page shown');
            }
            
            // Hide editor interface
            const editorInterface = document.getElementById('editor-interface');
            if (editorInterface) {
                editorInterface.style.display = 'none';
                console.log('DiagramSelector: Editor interface hidden');
            }
            
            console.log('DiagramSelector: Final state after cleanup:', {
                hasSession: !!this.currentSession,
                editorActive: this.editorActive,
                hasCurrentEditor: !!window.currentEditor,
                landingDisplay: landing?.style.display,
                editorDisplay: editorInterface?.style.display
            });
            console.log('DiagramSelector: ========== GALLERY READY ==========');
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
                context: ['背景1', '背景2', '背景3'],
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
                context: ['Context 1', 'Context 2', 'Context 3'],
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
                        label: '分支3', 
                        text: '分支3',
                        children: [
                            { id: 'sub_2_0', label: '子项3.1', text: '子项3.1', children: [] },
                            { id: 'sub_2_1', label: '子项3.2', text: '子项3.2', children: [] }
                        ] 
                    },
                    { 
                        id: 'branch_3',
                        label: '分支4', 
                        text: '分支4',
                        children: [
                            { id: 'sub_3_0', label: '子项4.1', text: '子项4.1', children: [] },
                            { id: 'sub_3_1', label: '子项4.2', text: '子项4.2', children: [] }
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
                            text: '分支3', 
                            node_type: 'branch', 
                            branch_index: 2, 
                            angle: 0 
                        },
                        'branch_3': { 
                            x: -220, y: 80, 
                            width: 100, height: 50, 
                            text: '分支4', 
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
                            text: '子项3.1', 
                            node_type: 'child', 
                            branch_index: 2, 
                            child_index: 0, 
                            angle: 0 
                        },
                        'child_2_1': { 
                            x: -370, y: -50, 
                            width: 90, height: 40, 
                            text: '子项3.2', 
                            node_type: 'child', 
                            branch_index: 2, 
                            child_index: 1, 
                            angle: 0 
                        },
                        'child_3_0': { 
                            x: -370, y: 50, 
                            width: 90, height: 40, 
                            text: '子项4.1', 
                            node_type: 'child', 
                            branch_index: 3, 
                            child_index: 0, 
                            angle: 0 
                        },
                        'child_3_1': { 
                            x: -370, y: 110, 
                            width: 90, height: 40, 
                            text: '子项4.2', 
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
                        label: 'Branch 3', 
                        text: 'Branch 3',
                        children: [
                            { id: 'sub_2_0', label: 'Sub-item 3.1', text: 'Sub-item 3.1', children: [] },
                            { id: 'sub_2_1', label: 'Sub-item 3.2', text: 'Sub-item 3.2', children: [] }
                        ] 
                    },
                    { 
                        id: 'branch_3',
                        label: 'Branch 4', 
                        text: 'Branch 4',
                        children: [
                            { id: 'sub_3_0', label: 'Sub-item 4.1', text: 'Sub-item 4.1', children: [] },
                            { id: 'sub_3_1', label: 'Sub-item 4.2', text: 'Sub-item 4.2', children: [] }
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
                            text: 'Branch 3', 
                            node_type: 'branch', 
                            branch_index: 2, 
                            angle: 0 
                        },
                        'branch_3': { 
                            x: -220, y: 80, 
                            width: 100, height: 50, 
                            text: 'Branch 4', 
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
                            text: 'Sub-item 3.1', 
                            node_type: 'child', 
                            branch_index: 2, 
                            child_index: 0, 
                            angle: 0 
                        },
                        'child_2_1': { 
                            x: -370, y: -50, 
                            width: 90, height: 40, 
                            text: 'Sub-item 3.2', 
                            node_type: 'child', 
                            branch_index: 2, 
                            child_index: 1, 
                            angle: 0 
                        },
                        'child_3_0': { 
                            x: -370, y: 50, 
                            width: 90, height: 40, 
                            text: 'Sub-item 4.1', 
                            node_type: 'child', 
                            branch_index: 3, 
                            child_index: 0, 
                            angle: 0 
                        },
                        'child_3_1': { 
                            x: -370, y: 110, 
                            width: 90, height: 40, 
                            text: 'Sub-item 4.2', 
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
     * Get Brace Map template
     */
    getBraceMapTemplate() {
        const lang = window.languageManager?.getCurrentLanguage() || 'en';
        
        if (lang === 'zh') {
            return {
                topic: '主题',
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
                _recommended_dimensions: {
                    width: 800,
                    height: 600,
                    padding: 40
                }
            };
        } else {
            return {
                topic: 'Main Topic',
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
                _recommended_dimensions: {
                    width: 800,
                    height: 600,
                    padding: 40
                }
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

