/**
 * InteractiveEditor - Main controller for the interactive diagram editor
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 */

class InteractiveEditor {
    constructor(diagramType, template) {
        this.diagramType = diagramType;
        this.currentSpec = template;
        this.selectedNodes = new Set();
        this.history = [];
        this.historyIndex = -1;
        
        // Initialize components
        this.selectionManager = new SelectionManager();
        this.canvasManager = new CanvasManager();
        this.renderer = null;
        
        // Bind selection change callback
        this.selectionManager.setSelectionChangeCallback((selectedNodes) => {
            this.selectedNodes = new Set(selectedNodes);
            this.updateToolbarState();
        });
    }
    
    /**
     * Initialize the editor
     */
    initialize() {
        console.log(`Initializing interactive editor for ${this.diagramType}`);
        
        // Setup canvas
        this.canvasManager.setupCanvas('#d3-container', {
            minHeight: '600px',
            backgroundColor: '#f5f5f5'
        });
        
        // Render initial diagram
        this.renderDiagram();
        
        // Setup global event handlers
        this.setupGlobalEventHandlers();
    }
    
    /**
     * Render the diagram
     */
    renderDiagram() {
        try {
            // Use existing renderer functions based on diagram type
            const theme = null; // Use default theme
            const dimensions = null; // Use default dimensions
            
            switch (this.diagramType) {
                case 'mindmap':
                    if (typeof renderMindMap === 'function') {
                        renderMindMap(this.currentSpec, theme, dimensions);
                    }
                    break;
                case 'concept_map':
                    if (typeof renderConceptMap === 'function') {
                        renderConceptMap(this.currentSpec, theme, dimensions);
                    }
                    break;
                case 'bubble_map':
                    if (typeof renderBubbleMap === 'function') {
                        renderBubbleMap(this.currentSpec, theme, dimensions);
                    }
                    break;
                case 'flow_map':
                    if (typeof renderFlowMap === 'function') {
                        renderFlowMap(this.currentSpec, theme, dimensions);
                    }
                    break;
                case 'tree_map':
                    if (typeof renderTreeMap === 'function') {
                        renderTreeMap(this.currentSpec, theme, dimensions);
                    }
                    break;
                case 'brace_map':
                    if (typeof renderBraceMap === 'function') {
                        renderBraceMap(this.currentSpec, theme, dimensions);
                    }
                    break;
                default:
                    console.error(`Unknown diagram type: ${this.diagramType}`);
            }
            
            // Add interaction handlers after rendering
            this.addInteractionHandlers();
            
        } catch (error) {
            console.error('Error rendering diagram:', error);
        }
    }
    
    /**
     * Add interaction handlers to rendered elements
     */
    addInteractionHandlers() {
        // Find all node elements and add click handlers
        d3.selectAll('circle, rect, ellipse').each((d, i, nodes) => {
            const element = d3.select(nodes[i]);
            const nodeId = `node_${i}`;
            
            // Add node ID attribute
            element.attr('data-node-id', nodeId);
            
            // Add click handler for selection
            element
                .style('cursor', 'pointer')
                .on('click', (event) => {
                    event.stopPropagation();
                    
                    if (event.ctrlKey || event.metaKey) {
                        this.selectionManager.toggleNodeSelection(nodeId);
                    } else {
                        this.selectionManager.clearSelection();
                        this.selectionManager.selectNode(nodeId);
                    }
                })
                .on('dblclick', (event) => {
                    event.stopPropagation();
                    this.openNodeEditor(nodeId, d);
                })
                .on('mouseover', function() {
                    d3.select(this).style('opacity', 0.8);
                })
                .on('mouseout', function() {
                    d3.select(this).style('opacity', 1);
                });
        });
        
        // Add text click handlers
        d3.selectAll('text').each((d, i, nodes) => {
            const element = d3.select(nodes[i]);
            const nodeId = `node_${i}`;
            
            element
                .style('cursor', 'pointer')
                .on('click', (event) => {
                    event.stopPropagation();
                    
                    if (event.ctrlKey || event.metaKey) {
                        this.selectionManager.toggleNodeSelection(nodeId);
                    } else {
                        this.selectionManager.clearSelection();
                        this.selectionManager.selectNode(nodeId);
                    }
                })
                .on('dblclick', (event) => {
                    event.stopPropagation();
                    this.openNodeEditor(nodeId, d);
                });
        });
    }
    
    /**
     * Setup global event handlers
     */
    setupGlobalEventHandlers() {
        // Click on canvas to deselect all
        d3.select('#d3-container').on('click', () => {
            this.selectionManager.clearSelection();
        });
        
        // Keyboard shortcuts
        d3.select('body').on('keydown', (event) => {
            this.handleKeyboardShortcut(event);
        });
    }
    
    /**
     * Handle keyboard shortcuts
     */
    handleKeyboardShortcut(event) {
        // Delete selected nodes
        if (event.key === 'Delete' || event.key === 'Backspace') {
            if (this.selectedNodes.size > 0) {
                event.preventDefault();
                this.deleteSelectedNodes();
            }
        }
        
        // Undo
        if (event.ctrlKey && event.key === 'z') {
            event.preventDefault();
            this.undo();
        }
        
        // Redo
        if (event.ctrlKey && event.key === 'y') {
            event.preventDefault();
            this.redo();
        }
        
        // Select all
        if (event.ctrlKey && event.key === 'a') {
            event.preventDefault();
            this.selectAll();
        }
    }
    
    /**
     * Open node editor
     */
    openNodeEditor(nodeId, nodeData) {
        const editor = new NodeEditor(
            { id: nodeId, text: nodeData?.text || 'Edit me' },
            (newText) => {
                this.updateNodeText(nodeId, newText);
            },
            () => {
                // Cancel callback
            }
        );
        
        editor.show();
    }
    
    /**
     * Update node text
     */
    updateNodeText(nodeId, newText) {
        // Find the text element and update it
        const textElement = d3.select(`[data-node-id="${nodeId}"]`)
            .select('text');
        
        if (!textElement.empty()) {
            textElement.text(newText);
            this.saveToHistory('update_text', { nodeId, newText });
        }
    }
    
    /**
     * Delete selected nodes
     */
    deleteSelectedNodes() {
        if (this.selectedNodes.size === 0) return;
        
        const nodesToDelete = Array.from(this.selectedNodes);
        
        nodesToDelete.forEach(nodeId => {
            d3.select(`[data-node-id="${nodeId}"]`).remove();
        });
        
        this.selectionManager.clearSelection();
        this.saveToHistory('delete_nodes', { nodeIds: nodesToDelete });
    }
    
    /**
     * Select all nodes
     */
    selectAll() {
        d3.selectAll('[data-node-id]').each((d, i, nodes) => {
            const nodeId = d3.select(nodes[i]).attr('data-node-id');
            if (nodeId) {
                this.selectionManager.selectNode(nodeId);
            }
        });
    }
    
    /**
     * Save state to history
     */
    saveToHistory(action, state) {
        // Remove any history after current index
        this.history = this.history.slice(0, this.historyIndex + 1);
        
        // Add new history entry
        this.history.push({
            action,
            state: JSON.parse(JSON.stringify(state)),
            timestamp: Date.now()
        });
        
        this.historyIndex = this.history.length - 1;
        
        // Limit history size
        if (this.history.length > 50) {
            this.history.shift();
            this.historyIndex--;
        }
    }
    
    /**
     * Undo last action
     */
    undo() {
        if (this.historyIndex > 0) {
            this.historyIndex--;
            console.log('Undo:', this.history[this.historyIndex]);
            // Re-render diagram with previous state
            this.renderDiagram();
        }
    }
    
    /**
     * Redo last undone action
     */
    redo() {
        if (this.historyIndex < this.history.length - 1) {
            this.historyIndex++;
            console.log('Redo:', this.history[this.historyIndex]);
            // Re-render diagram with next state
            this.renderDiagram();
        }
    }
    
    /**
     * Update toolbar state
     */
    updateToolbarState() {
        const hasSelection = this.selectedNodes.size > 0;
        
        // Dispatch custom event for toolbar to listen
        window.dispatchEvent(new CustomEvent('editor-selection-change', {
            detail: {
                selectedNodes: Array.from(this.selectedNodes),
                hasSelection: hasSelection
            }
        }));
    }
    
    /**
     * Get current diagram data
     */
    getCurrentDiagramData() {
        return {
            type: this.diagramType,
            spec: this.currentSpec,
            selectedNodes: Array.from(this.selectedNodes),
            timestamp: Date.now()
        };
    }
}

// Make available globally
if (typeof window !== 'undefined') {
    window.InteractiveEditor = InteractiveEditor;
}

