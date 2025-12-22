/**
 * NodeEditor - Modal editor for node text and properties
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
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
        logger.debug('NodeEditor', 'Opening modal', {
            nodeId: this.nodeData.nodeId,
            textLength: this.nodeData.currentText?.length || 0
        });
        
        // Mobile: Lock body scroll to prevent page shift
        if (window.innerWidth <= 768) {
            this._savedScrollY = window.scrollY;
            document.body.style.overflow = 'hidden';
            document.body.style.position = 'fixed';
            document.body.style.width = '100%';
            document.body.style.top = `-${this._savedScrollY}px`;
        }
        
        this.createModal();
        this.attachEventListeners();
        
        // Focus on text input
        setTimeout(() => {
            if (this.textInput) {
                this.textInput.select();
                
                // Setup Tab Mode autocomplete if enabled
                if (window.currentEditor?.modules?.tabMode) {
                    window.currentEditor.modules.tabMode.setupAutocomplete(
                        this.textInput,
                        this.nodeData.nodeId,
                        window.currentEditor?.diagramType
                    );
                }
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
            .style('background', 'rgba(0, 0, 0, 0.6)')
            .style('display', 'flex')
            .style('align-items', 'center')
            .style('justify-content', 'center')
            .style('z-index', 10000)
            .style('backdrop-filter', 'blur(4px)')
            .style('animation', 'fadeIn 0.2s ease');
        
        // Create modal content - responsive for mobile
        const isMobile = window.innerWidth <= 768;
        this.modal = overlay.append('div')
            .attr('class', 'node-editor-modal')
            .style('background', 'white')
            .style('border-radius', isMobile ? '12px' : '16px')
            .style('padding', isMobile ? '20px' : '28px 32px')
            .style('width', isMobile ? '90%' : 'auto')
            .style('min-width', isMobile ? 'auto' : '480px')
            .style('max-width', isMobile ? '90%' : '600px')
            .style('max-height', isMobile ? '80vh' : 'auto')
            .style('overflow-y', isMobile ? 'auto' : 'visible')
            .style('box-shadow', '0 12px 40px rgba(0, 0, 0, 0.25)')
            .style('animation', 'slideUp 0.3s ease');
        
        // Add animation keyframes
        if (!document.getElementById('node-editor-animations')) {
            const style = document.createElement('style');
            style.id = 'node-editor-animations';
            style.textContent = `
                @keyframes fadeIn {
                    from { opacity: 0; }
                    to { opacity: 1; }
                }
                @keyframes slideUp {
                    from { 
                        opacity: 0;
                        transform: translateY(20px); 
                    }
                    to { 
                        opacity: 1;
                        transform: translateY(0); 
                    }
                }
            `;
            document.head.appendChild(style);
        }
        
        // Header with icon
        const header = this.modal.append('div')
            .style('display', 'flex')
            .style('align-items', 'center')
            .style('gap', '12px')
            .style('margin-bottom', '24px');
        
        header.append('div')
            .style('width', '40px')
            .style('height', '40px')
            .style('background', 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)')
            .style('border-radius', '10px')
            .style('display', 'flex')
            .style('align-items', 'center')
            .style('justify-content', 'center')
            .html(`<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
            </svg>`);
        
        // Get language manager
        const lang = window.languageManager;
        
        header.append('h2')
            .text(lang?.translate('editNodeContent') || 'Edit Node Content')
            .style('margin', '0')
            .style('color', '#1a1a1a')
            .style('font-size', '20px')
            .style('font-weight', '700');
        
        // Text input label
        const textInputId = `node-text-input-${Date.now()}`;
        this.modal.append('label')
            .attr('for', textInputId)
            .text((lang?.translate('text') || 'Text') + ':')
            .style('display', 'block')
            .style('margin-bottom', '10px')
            .style('color', '#4a5568')
            .style('font-size', '14px')
            .style('font-weight', '600');
        
        // Input wrapper
        const inputWrapper = this.modal.append('div')
            .style('position', 'relative');
        
        this.textInput = inputWrapper.append('textarea')
            .attr('id', textInputId)
            .attr('name', 'node-text-input')
            .attr('class', 'node-text-input')
            .attr('rows', 4)
            .attr('autocomplete', 'off')
            .style('width', '100%')
            .style('padding', '14px 16px')
            .style('border', '2px solid #e2e8f0')
            .style('border-radius', '12px')
            .style('font-size', '15px')
            .style('font-family', 'Inter, Arial, sans-serif')
            .style('line-height', '1.6')
            .style('resize', 'vertical')
            .style('box-sizing', 'border-box')
            .style('transition', 'all 0.2s ease')
            .style('outline', 'none')
            .property('value', this.nodeData.text || '')
            .on('focus', function() {
                d3.select(this)
                    .style('border-color', '#667eea')
                    .style('box-shadow', '0 0 0 3px rgba(102, 126, 234, 0.1)');
            })
            .on('blur', function() {
                d3.select(this)
                    .style('border-color', '#e2e8f0')
                    .style('box-shadow', 'none');
            })
            .node();
        
        // Character count
        const charCount = this.modal.append('div')
            .attr('class', 'char-count')
            .style('text-align', 'right')
            .style('margin-top', '8px')
            .style('color', '#94a3b8')
            .style('font-size', '13px')
            .style('font-weight', '500')
            .text(`${(this.nodeData.text || '').length} ${lang?.translate('characters') || 'characters'}`);
        
        // Update character count on input
        d3.select(this.textInput).on('input', function() {
            const length = this.value.length;
            charCount.text(`${length} ${lang?.translate('characters') || 'characters'}`);
            
            if (length > 200) {
                charCount.style('color', '#ef4444').style('font-weight', '600');
            } else if (length > 100) {
                charCount.style('color', '#f59e0b').style('font-weight', '600');
            } else {
                charCount.style('color', '#94a3b8').style('font-weight', '500');
            }
        });
        
        // Buttons container
        const buttonContainer = this.modal.append('div')
            .style('display', 'flex')
            .style('justify-content', 'flex-end')
            .style('gap', '12px')
            .style('margin-top', '28px');
        
        // Cancel button
        buttonContainer.append('button')
            .attr('class', 'btn-cancel')
            .text(lang?.translate('cancel') || 'Cancel')
            .style('padding', '12px 24px')
            .style('border', '2px solid #e2e8f0')
            .style('background', 'white')
            .style('color', '#64748b')
            .style('border-radius', '10px')
            .style('cursor', 'pointer')
            .style('font-size', '14px')
            .style('font-weight', '600')
            .style('transition', 'all 0.2s ease')
            .on('mouseover', function() {
                d3.select(this)
                    .style('background', '#f8fafc')
                    .style('border-color', '#cbd5e1');
            })
            .on('mouseout', function() {
                d3.select(this)
                    .style('background', 'white')
                    .style('border-color', '#e2e8f0');
            })
            .on('click', () => this.handleCancel());
        
        // Save button
        buttonContainer.append('button')
            .attr('class', 'btn-save')
            .text(lang?.translate('saveChanges') || 'Save Changes')
            .style('padding', '12px 28px')
            .style('border', 'none')
            .style('background', 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)')
            .style('color', 'white')
            .style('border-radius', '10px')
            .style('cursor', 'pointer')
            .style('font-size', '14px')
            .style('font-weight', '600')
            .style('transition', 'all 0.2s ease')
            .style('box-shadow', '0 2px 8px rgba(102, 126, 234, 0.3)')
            .on('mouseover', function() {
                d3.select(this)
                    .style('transform', 'translateY(-2px)')
                    .style('box-shadow', '0 4px 14px rgba(102, 126, 234, 0.5)');
            })
            .on('mouseout', function() {
                d3.select(this)
                    .style('transform', 'translateY(0)')
                    .style('box-shadow', '0 2px 8px rgba(102, 126, 234, 0.3)');
            })
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
                    // Insert manual line break at cursor position
                    event.preventDefault();
                    const textarea = this.textInput;
                    const start = textarea.selectionStart;
                    const end = textarea.selectionEnd;
                    const value = textarea.value;
                    
                    // Insert newline at cursor position
                    textarea.value = value.substring(0, start) + '\n' + value.substring(end);
                    
                    // Restore cursor position after the newline
                    textarea.selectionStart = textarea.selectionEnd = start + 1;
                    
                    // Trigger input event to update character count
                    textarea.dispatchEvent(new Event('input', { bubbles: true }));
                }
            });
    }
    
    /**
     * Handle save action
     */
    handleSave() {
        // Preserve newlines and spaces (for learning sheets - users need spaces to control node length)
        // Replace multiple consecutive newlines with single newline, but preserve leading/trailing spaces
        let newText = this.textInput.value
            .replace(/\n{3,}/g, '\n\n');  // Replace 3+ newlines with 2
        // Note: Removed trim operation to allow users to use spaces to control node length
        // This is important for learning sheets where empty nodes need specific dimensions
        // Also removed empty text validation to allow users to save blank nodes directly
        
        logger.debug('NodeEditor', 'Saving node', {
            nodeId: this.nodeData.id,
            textLength: newText?.length || 0,
            changed: this.nodeData.text !== newText,
            hasNewlines: newText.includes('\n'),
            isEmpty: !newText || newText.length === 0
        });
        
        // Allow empty text - users can save blank nodes to control dimensions using spaces
        // This is easier than using the Empty button and gives users more control
        
        if (this.onSave) {
            this.onSave(newText);
        }
        
        this.close();
    }
    
    /**
     * Handle cancel action
     */
    handleCancel() {
        logger.debug('NodeEditor', 'Edit cancelled');
        
        if (this.onCancel) {
            this.onCancel();
        }
        
        this.close();
    }
    
    /**
     * Close the modal
     */
    close() {
        // Mobile: Unlock body scroll
        if (window.innerWidth <= 768) {
            document.body.style.overflow = '';
            document.body.style.position = '';
            document.body.style.width = '';
            document.body.style.top = '';
            window.scrollTo(0, this._savedScrollY || 0);
        }
        
        d3.select('.node-editor-overlay').remove();
    }
}

// Make available globally
if (typeof window !== 'undefined') {
    window.NodeEditor = NodeEditor;
}

