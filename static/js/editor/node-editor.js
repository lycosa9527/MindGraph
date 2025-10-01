/**
 * NodeEditor - Modal editor for node text and properties
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 */

class NodeEditor {
    constructor(nodeData, onSave, onCancel) {
        this.nodeData = nodeData;
        this.onSave = onSave;
        this.onCancel = onCancel;
        this.modal = null;
        this.textInput = null;
    }
    
    /**
     * Show the editor modal
     */
    show() {
        this.createModal();
        this.attachEventListeners();
        
        // Focus on text input
        setTimeout(() => {
            if (this.textInput) {
                this.textInput.select();
            }
        }, 100);
    }
    
    /**
     * Create modal HTML
     */
    createModal() {
        // Create modal overlay
        const overlay = d3.select('body')
            .append('div')
            .attr('class', 'node-editor-overlay')
            .style('position', 'fixed')
            .style('top', 0)
            .style('left', 0)
            .style('width', '100%')
            .style('height', '100%')
            .style('background', 'rgba(0, 0, 0, 0.5)')
            .style('display', 'flex')
            .style('align-items', 'center')
            .style('justify-content', 'center')
            .style('z-index', 10000);
        
        // Create modal content
        this.modal = overlay.append('div')
            .attr('class', 'node-editor-modal')
            .style('background', 'white')
            .style('border-radius', '8px')
            .style('padding', '24px')
            .style('min-width', '400px')
            .style('max-width', '600px')
            .style('box-shadow', '0 4px 20px rgba(0, 0, 0, 0.3)');
        
        // Header
        this.modal.append('h2')
            .text('Edit Node')
            .style('margin', '0 0 16px 0')
            .style('color', '#333')
            .style('font-size', '20px')
            .style('font-weight', '600');
        
        // Text input
        this.modal.append('label')
            .text('Text Content:')
            .style('display', 'block')
            .style('margin-bottom', '8px')
            .style('color', '#666')
            .style('font-size', '14px')
            .style('font-weight', '500');
        
        this.textInput = this.modal.append('textarea')
            .attr('class', 'node-text-input')
            .attr('rows', 4)
            .style('width', '100%')
            .style('padding', '12px')
            .style('border', '1px solid #ddd')
            .style('border-radius', '4px')
            .style('font-size', '14px')
            .style('font-family', 'Inter, Arial, sans-serif')
            .style('resize', 'vertical')
            .style('box-sizing', 'border-box')
            .property('value', this.nodeData.text || '')
            .node();
        
        // Character count
        const charCount = this.modal.append('div')
            .attr('class', 'char-count')
            .style('text-align', 'right')
            .style('margin-top', '4px')
            .style('color', '#999')
            .style('font-size', '12px')
            .text(`${(this.nodeData.text || '').length} characters`);
        
        // Update character count on input
        d3.select(this.textInput).on('input', function() {
            const length = this.value.length;
            charCount.text(`${length} characters`);
            
            if (length > 100) {
                charCount.style('color', '#ff6b6b');
            } else {
                charCount.style('color', '#999');
            }
        });
        
        // Buttons container
        const buttonContainer = this.modal.append('div')
            .style('display', 'flex')
            .style('justify-content', 'flex-end')
            .style('gap', '12px')
            .style('margin-top', '20px');
        
        // Cancel button
        buttonContainer.append('button')
            .attr('class', 'btn-cancel')
            .text('Cancel')
            .style('padding', '8px 16px')
            .style('border', '1px solid #ddd')
            .style('background', 'white')
            .style('color', '#666')
            .style('border-radius', '4px')
            .style('cursor', 'pointer')
            .style('font-size', '14px')
            .style('font-weight', '500')
            .on('click', () => this.handleCancel());
        
        // Save button
        buttonContainer.append('button')
            .attr('class', 'btn-save')
            .text('Save')
            .style('padding', '8px 16px')
            .style('border', 'none')
            .style('background', '#4CAF50')
            .style('color', 'white')
            .style('border-radius', '4px')
            .style('cursor', 'pointer')
            .style('font-size', '14px')
            .style('font-weight', '500')
            .on('click', () => this.handleSave());
    }
    
    /**
     * Attach event listeners
     */
    attachEventListeners() {
        // Close on overlay click
        d3.select('.node-editor-overlay')
            .on('click', (event) => {
                if (event.target.classList.contains('node-editor-overlay')) {
                    this.handleCancel();
                }
            });
        
        // Keyboard shortcuts
        d3.select(this.textInput)
            .on('keydown', (event) => {
                if (event.key === 'Escape') {
                    this.handleCancel();
                } else if (event.key === 'Enter' && event.ctrlKey) {
                    this.handleSave();
                }
            });
    }
    
    /**
     * Handle save action
     */
    handleSave() {
        const newText = this.textInput.value.trim();
        
        if (newText === '') {
            alert('Text cannot be empty');
            return;
        }
        
        if (this.onSave) {
            this.onSave(newText);
        }
        
        this.close();
    }
    
    /**
     * Handle cancel action
     */
    handleCancel() {
        if (this.onCancel) {
            this.onCancel();
        }
        
        this.close();
    }
    
    /**
     * Close the modal
     */
    close() {
        d3.select('.node-editor-overlay').remove();
    }
}

// Make available globally
if (typeof window !== 'undefined') {
    window.NodeEditor = NodeEditor;
}

