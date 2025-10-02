/**
 * DiagramSelector - Handles diagram type selection and template loading
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 */

class DiagramSelector {
    constructor() {
        this.diagramTypes = {
            'circle_map': {
                name: 'Circle Map',
                template: this.getCircleMapTemplate(),
                description: 'Defining in context'
            },
            'bubble_map': {
                name: 'Bubble Map',
                template: this.getBubbleMapTemplate(),
                description: 'Describing with adjectives'
            },
            'double_bubble_map': {
                name: 'Double Bubble Map',
                template: this.getDoubleBubbleMapTemplate(),
                description: 'Comparing and contrasting'
            },
            'tree_map': {
                name: 'Tree Map',
                template: this.getTreeMapTemplate(),
                description: 'Classifying and grouping'
            },
            'brace_map': {
                name: 'Brace Map',
                template: this.getBraceMapTemplate(),
                description: 'Whole to parts'
            },
            'flow_map': {
                name: 'Flow Map',
                template: this.getFlowMapTemplate(),
                description: 'Sequencing and ordering'
            },
            'multi_flow_map': {
                name: 'Multi-Flow Map',
                template: this.getMultiFlowMapTemplate(),
                description: 'Cause and effect'
            },
            'bridge_map': {
                name: 'Bridge Map',
                template: this.getBridgeMapTemplate(),
                description: 'Seeing analogies'
            },
            'mindmap': {
                name: 'Mind Map',
                template: this.getMindMapTemplate(),
                description: 'Creative brainstorming'
            },
            'concept_map': {
                name: 'Concept Map',
                template: this.getConceptMapTemplate(),
                description: 'Complex relationships'
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
            this.transitionToEditor(diagramType, diagramConfig.template, diagramConfig.name);
        } else {
            console.error(`Unknown diagram type: ${diagramType}`);
        }
    }
    
    /**
     * Transition to editor interface
     */
    transitionToEditor(diagramType, template, diagramName) {
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
        } catch (error) {
            console.error('Error initializing editor:', error);
            alert('Error loading editor. Please try again.');
            this.backToGallery();
        }
    }
    
    /**
     * Return to gallery
     */
    backToGallery() {
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
        
        // Clean up editor
        if (window.currentEditor) {
            window.currentEditor = null;
        }
    }
    
    /**
     * Get Circle Map template
     */
    getCircleMapTemplate() {
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
    
    /**
     * Get Double Bubble Map template
     */
    getDoubleBubbleMapTemplate() {
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
    
    /**
     * Get Multi-Flow Map template
     */
    getMultiFlowMapTemplate() {
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
    
    /**
     * Get Bridge Map template
     */
    getBridgeMapTemplate() {
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
    
    /**
     * Get Mind Map template
     */
    getMindMapTemplate() {
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
    
    /**
     * Get Bubble Map template
     */
    getBubbleMapTemplate() {
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
    
    /**
     * Get Concept Map template
     */
    getConceptMapTemplate() {
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
    
    /**
     * Get Flow Map template
     */
    getFlowMapTemplate() {
        return {
            title: 'Process Flow',
            steps: [
                'Step 1: Start',
                'Step 2: Process',
                'Step 3: Review',
                'Step 4: Complete'
            ],
            _layout: {
                positions: {
                    'Step 1: Start': { x: 150, y: 250 },
                    'Step 2: Process': { x: 300, y: 250 },
                    'Step 3: Review': { x: 450, y: 250 },
                    'Step 4: Complete': { x: 600, y: 250 }
                }
            },
            _recommended_dimensions: {
                width: 750,
                height: 500,
                padding: 40
            }
        };
    }
    
    /**
     * Get Tree Map template
     */
    getTreeMapTemplate() {
        return {
            root: 'Root Topic',
            children: [
                { 
                    text: 'Category 1', 
                    children: [
                        { text: 'Item 1.1', children: [] },
                        { text: 'Item 1.2', children: [] }
                    ] 
                },
                { 
                    text: 'Category 2', 
                    children: [
                        { text: 'Item 2.1', children: [] },
                        { text: 'Item 2.2', children: [] }
                    ] 
                }
            ],
            _layout: {
                positions: {
                    'Root Topic': { x: 350, y: 100 },
                    'Category 1': { x: 250, y: 200 },
                    'Category 2': { x: 450, y: 200 },
                    'Item 1.1': { x: 200, y: 300 },
                    'Item 1.2': { x: 300, y: 300 },
                    'Item 2.1': { x: 400, y: 300 },
                    'Item 2.2': { x: 500, y: 300 }
                }
            },
            _recommended_dimensions: {
                width: 700,
                height: 400,
                padding: 40
            }
        };
    }
    
    /**
     * Get Brace Map template
     */
    getBraceMapTemplate() {
        return {
            topic: 'Main Topic',
            parts: [
                'Part 1',
                'Part 2',
                'Part 3'
            ],
            _layout: {
                positions: {
                    'Main Topic': { x: 200, y: 250 },
                    'Part 1': { x: 450, y: 150 },
                    'Part 2': { x: 450, y: 250 },
                    'Part 3': { x: 450, y: 350 }
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

// Initialize when DOM is ready
if (typeof window !== 'undefined') {
    window.addEventListener('DOMContentLoaded', () => {
        window.diagramSelector = new DiagramSelector();
    });
}

