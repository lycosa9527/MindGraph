/**
 * Comic Bubble - Speech bubble for VoiceAgent
 * Displays streaming text responses in a comic-style bubble
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 */

class ComicBubble {
    constructor() {
        this.container = null;
        this.textElement = null;
        this.isVisible = false;
        this.currentText = '';
        this.typingSpeed = 30; // ms per character for typing effect
        this.hideTimeout = null;
        
        this.logger = window.logger || console;
    }
    
    init(parentElement = document.body) {
        // Create bubble container
        this.container = document.createElement('div');
        this.container.className = 'comic-bubble';
        this.container.style.display = 'none';
        
        // Create text element
        this.textElement = document.createElement('div');
        this.textElement.className = 'comic-bubble-text';
        
        this.container.appendChild(this.textElement);
        parentElement.appendChild(this.container);
        
        this.logger.info('ComicBubble', 'Initialized');
    }
    
    /**
     * Append text chunk to bubble (streaming)
     */
    appendText(chunk) {
        if (!chunk) return;
        
        this.currentText += chunk;
        this.textElement.textContent = this.currentText;
        
        // Show bubble if hidden
        if (!this.isVisible) {
            this.show();
        }
        
        // Clear any pending hide timeout
        if (this.hideTimeout) {
            clearTimeout(this.hideTimeout);
            this.hideTimeout = null;
        }
        
        this.logger.debug('ComicBubble', 'Appended chunk:', chunk);
    }
    
    /**
     * Set complete text (non-streaming)
     */
    setText(text) {
        this.currentText = text;
        this.textElement.textContent = text;
        
        if (!this.isVisible) {
            this.show();
        }
    }
    
    /**
     * Clear text and reset
     */
    clear() {
        this.currentText = '';
        this.textElement.textContent = '';
    }
    
    /**
     * Show bubble with animation
     */
    show() {
        if (this.isVisible) return;
        
        this.container.style.display = 'block';
        // Trigger reflow for animation
        this.container.offsetHeight;
        this.container.classList.add('visible');
        this.isVisible = true;
        
        this.logger.debug('ComicBubble', 'Shown');
    }
    
    /**
     * Hide bubble with animation
     */
    hide() {
        if (!this.isVisible) return;
        
        this.container.classList.remove('visible');
        
        // Wait for animation to complete
        setTimeout(() => {
            this.container.style.display = 'none';
            this.isVisible = false;
            this.logger.debug('ComicBubble', 'Hidden');
        }, 300); // Match CSS transition duration
    }
    
    /**
     * Auto-hide after delay
     */
    autoHide(delay = 3000) {
        if (this.hideTimeout) {
            clearTimeout(this.hideTimeout);
        }
        
        this.hideTimeout = setTimeout(() => {
            this.hide();
            this.clear();
        }, delay);
    }
    
    /**
     * Show thinking indicator (...)
     */
    showThinking() {
        this.setText('...');
        this.show();
    }
    
    /**
     * Destroy bubble
     */
    destroy() {
        if (this.hideTimeout) {
            clearTimeout(this.hideTimeout);
        }
        
        if (this.container && this.container.parentNode) {
            this.container.parentNode.removeChild(this.container);
        }
        
        this.logger.info('ComicBubble', 'Destroyed');
    }
}

// Make available globally
window.ComicBubble = ComicBubble;

// Export for module usage (if needed)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ComicBubble;
}

