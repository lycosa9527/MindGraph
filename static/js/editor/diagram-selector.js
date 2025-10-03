/**
 * DiagramSelector - Handles diagram type selection and template loading
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 */

class DiagramSelector {
    constructor() {
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
                const diagramType = card.dataset.type;
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
     * Select a diagram type
     */
    selectDiagram(diagramType) {
        const diagramConfig = this.diagramTypes[diagramType];
        if (diagramConfig) {
            console.log(`Selected diagram type: ${diagramType}`);
            // Get a fresh template using the factory method
            const freshTemplate = this.getTemplate(diagramType);
            this.transitionToEditor(diagramType, freshTemplate, diagramConfig.name);
        } else {
            console.error(`Unknown diagram type: ${diagramType}`);
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
            window.currentEditor = new InteractiveEditor(diagramType, template);
            window.currentEditor.initialize();
            
            console.log(`Editor initialized for diagram type: ${diagramType}`);
        } catch (error) {
            console.error('Error initializing editor:', error);
            alert('Error loading editor. Please try again.');
            this.backToGallery();
        }
    }
    
    /**
     * Clean up canvas and previous editor
     */
    cleanupCanvas() {
        // Clear the D3 container
        const container = document.getElementById('d3-container');
        if (container) {
            // Remove all SVG elements
            d3.select('#d3-container').selectAll('*').remove();
            console.log('Canvas cleared for new diagram');
        }
        
        // Clear any existing editor
        if (window.currentEditor) {
            window.currentEditor = null;
        }
    }
    
    /**
     * Return to gallery
     */
    backToGallery() {
        // Clean up canvas and editor first
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
        
        // Show landing page
        const landing = document.getElementById('editor-landing');
        if (landing) {
            landing.style.display = 'block';
        }
        
        // Hide editor interface
        const editorInterface = document.getElementById('editor-interface');
        if (editorInterface) {
            editorInterface.style.display = 'none';
        }
        
        console.log('Returned to gallery - all cleanup complete');
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
                        text: '分支1', 
                        children: [
                            { text: '子项1.1', children: [] },
                            { text: '子项1.2', children: [] }
                        ] 
                    },
                    { 
                        text: '分支2', 
                        children: [
                            { text: '子项2.1', children: [] }
                        ] 
                    },
                    { 
                        text: '分支3', 
                        children: [] 
                    }
                ],
                _layout: {
                    positions: {
                        '中心主题': { x: 350, y: 250 },
                        '分支1': { x: 200, y: 150 },
                        '分支2': { x: 200, y: 250 },
                        '分支3': { x: 200, y: 350 },
                        '子项1.1': { x: 100, y: 120 },
                        '子项1.2': { x: 100, y: 180 },
                        '子项2.1': { x: 100, y: 250 }
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
                topic: 'Central Topic',
                children: [
                    { 
                        text: 'Branch 1', 
                        children: [
                            { text: 'Sub-item 1.1', children: [] },
                            { text: 'Sub-item 1.2', children: [] }
                        ] 
                    },
                    { 
                        text: 'Branch 2', 
                        children: [
                            { text: 'Sub-item 2.1', children: [] }
                        ] 
                    },
                    { 
                        text: 'Branch 3', 
                        children: [] 
                    }
                ],
                _layout: {
                    positions: {
                        'Central Topic': { x: 350, y: 250 },
                        'Branch 1': { x: 200, y: 150 },
                        'Branch 2': { x: 200, y: 250 },
                        'Branch 3': { x: 200, y: 350 },
                        'Sub-item 1.1': { x: 100, y: 120 },
                        'Sub-item 1.2': { x: 100, y: 180 },
                        'Sub-item 2.1': { x: 100, y: 250 }
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
                    '开始',
                    '执行',
                    '检查',
                    '完成'
                ],
                substeps: [
                    {
                        step: '开始',
                        substeps: [
                            '收集需求',
                            '明确目标'
                        ]
                    },
                    {
                        step: '执行',
                        substeps: [
                            '实施任务',
                            '监控进度'
                        ]
                    },
                    {
                        step: '检查',
                        substeps: [
                            '检查质量',
                            '验证完成度'
                        ]
                    },
                    {
                        step: '完成',
                        substeps: [
                            '最终交付',
                            '记录成果'
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
                    'Start',
                    'Process',
                    'Review',
                    'Complete'
                ],
                substeps: [
                    {
                        step: 'Start',
                        substeps: [
                            'Gather requirements',
                            'Define objectives'
                        ]
                    },
                    {
                        step: 'Process',
                        substeps: [
                            'Execute tasks',
                            'Monitor progress'
                        ]
                    },
                    {
                        step: 'Review',
                        substeps: [
                            'Check quality',
                            'Verify completion'
                        ]
                    },
                    {
                        step: 'Complete',
                        substeps: [
                            'Finalize deliverables',
                            'Document results'
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

