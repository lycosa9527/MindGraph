/**
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

/**
 * Update Notification Manager
 * ============================
 * 
 * Displays a modal notification when the application has been updated.
 * Shows a blurred background overlay with update information.
 * 
 * Features:
 * - Blur background overlay
 * - Bilingual support (Chinese/English)
 * - Changelog display
 * - Dismissible (won't show again for same version)
 */

class UpdateNotificationManager {
    constructor() {
        this.modalContainer = null;
        this.isVisible = false;
        this.currentNotification = null;
        
        // Check for notification on initialization
        this.init();
    }
    
    /**
     * Initialize the notification manager
     */
    async init() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.checkForNotification());
        } else {
            // Small delay to ensure auth is complete
            setTimeout(() => this.checkForNotification(), 500);
        }
    }
    
    /**
     * Check if there's a notification to display
     */
    async checkForNotification() {
        try {
            const response = await fetch('/api/update-notification', {
                method: 'GET',
                credentials: 'include'
            });
            
            if (!response.ok) {
                // Not authenticated or error, skip notification
                return;
            }
            
            const data = await response.json();
            
            if (data.notification) {
                this.currentNotification = data.notification;
                this.showNotification(data.notification);
            }
        } catch (error) {
            // Silently fail - notification is not critical
            if (window.logger) {
                window.logger.debug('UpdateNotification', 'Failed to check for notification:', error);
            }
        }
    }
    
    /**
     * Get current language preference
     */
    getCurrentLanguage() {
        return window.DEFAULT_LANGUAGE || 'zh';
    }
    
    /**
     * Show the notification modal
     */
    showNotification(notification) {
        if (this.isVisible) return;
        
        this.isVisible = true;
        this.createModal(notification);
        
        // Add blur to body
        document.body.classList.add('update-notification-blur');
        
        if (window.logger) {
            window.logger.info('UpdateNotification', `Showing update notification for version: ${notification.version}`);
        }
    }
    
    /**
     * Create the modal DOM elements
     */
    createModal(notification) {
        // Get content (Chinese only now)
        const title = notification.title || '系统更新';
        const message = notification.message || '';
        
        // Create modal container
        this.modalContainer = document.createElement('div');
        this.modalContainer.className = 'update-notification-overlay';
        this.modalContainer.innerHTML = `
            <div class="update-notification-modal">
                <button class="update-notification-close" id="update-notification-close" title="关闭">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
                
                <div class="update-notification-header">
                    <div class="update-notification-icon">
                        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
                            <path d="M2 17l10 5 10-5"></path>
                            <path d="M2 12l10 5 10-5"></path>
                        </svg>
                    </div>
                    <h2 class="update-notification-title">${this.escapeHtml(title)}</h2>
                    ${notification.version ? `<span class="update-notification-version">版本 ${this.escapeHtml(notification.version)}</span>` : ''}
                </div>
                
                <div class="update-notification-content">
                    ${message ? `<div class="update-notification-message">${this.sanitizeHtml(message)}</div>` : ''}
                </div>
                
                <div class="update-notification-footer">
                    <button class="update-notification-close-btn" id="update-notification-close-btn">关闭</button>
                </div>
            </div>
        `;
        
        // Add to document
        document.body.appendChild(this.modalContainer);
        
        // Bind close buttons (top X and bottom button)
        const closeBtn = this.modalContainer.querySelector('#update-notification-close');
        const closeBtnBottom = this.modalContainer.querySelector('#update-notification-close-btn');
        closeBtn.addEventListener('click', () => this.dismissNotification());
        closeBtnBottom.addEventListener('click', () => this.dismissNotification());
        
        // Also allow clicking overlay to dismiss
        this.modalContainer.addEventListener('click', (e) => {
            if (e.target === this.modalContainer) {
                this.dismissNotification();
            }
        });
        
        // Allow Escape key to dismiss
        this.escapeHandler = (e) => {
            if (e.key === 'Escape' && this.isVisible) {
                this.dismissNotification();
            }
        };
        document.addEventListener('keydown', this.escapeHandler);
        
        // Trigger animation
        requestAnimationFrame(() => {
            this.modalContainer.classList.add('visible');
        });
    }
    
    /**
     * Dismiss the notification
     */
    async dismissNotification() {
        if (!this.isVisible) return;
        
        // Remove modal with animation
        this.modalContainer.classList.remove('visible');
        document.body.classList.remove('update-notification-blur');
        
        // Remove event listener
        if (this.escapeHandler) {
            document.removeEventListener('keydown', this.escapeHandler);
        }
        
        // Wait for animation then remove DOM element
        setTimeout(() => {
            if (this.modalContainer && this.modalContainer.parentNode) {
                this.modalContainer.parentNode.removeChild(this.modalContainer);
            }
            this.modalContainer = null;
            this.isVisible = false;
        }, 300);
        
        // Send dismiss request to server
        try {
            await fetch('/api/update-notification/dismiss', {
                method: 'POST',
                credentials: 'include'
            });
            
            if (window.logger) {
                window.logger.info('UpdateNotification', 'Notification dismissed');
            }
        } catch (error) {
            // Silently fail - notification is already hidden
            if (window.logger) {
                window.logger.debug('UpdateNotification', 'Failed to persist dismiss:', error);
            }
        }
    }
    
    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    /**
     * Sanitize HTML content from rich text editor
     * Allows only safe tags and attributes
     */
    sanitizeHtml(html) {
        // Use DOMPurify if available (already loaded for AI assistant)
        if (typeof DOMPurify !== 'undefined') {
            return DOMPurify.sanitize(html, {
                ALLOWED_TAGS: ['b', 'i', 'u', 'strong', 'em', 'p', 'br', 'ul', 'ol', 'li', 'span', 'div', 'font', 'img'],
                ALLOWED_ATTR: ['style', 'color', 'size', 'face', 'src', 'alt', 'width', 'height']
            });
        }
        
        // Fallback: basic sanitization
        const allowedTags = ['b', 'i', 'u', 'strong', 'em', 'p', 'br', 'ul', 'ol', 'li', 'span', 'div', 'font', 'img'];
        const temp = document.createElement('div');
        temp.innerHTML = html;
        
        // Remove script tags and event handlers
        const scripts = temp.querySelectorAll('script');
        scripts.forEach(s => s.remove());
        
        // Remove onclick, onerror, etc.
        const allElements = temp.querySelectorAll('*');
        allElements.forEach(el => {
            // Remove event handlers
            [...el.attributes].forEach(attr => {
                if (attr.name.startsWith('on')) {
                    el.removeAttribute(attr.name);
                }
            });
            
            // Remove non-allowed tags but keep their content (except img)
            if (!allowedTags.includes(el.tagName.toLowerCase())) {
                el.replaceWith(...el.childNodes);
            }
        });
        
        return temp.innerHTML;
    }
}

// Inject CSS styles
const updateNotificationStyles = document.createElement('style');
updateNotificationStyles.textContent = `
    /* Blur effect for body when notification is shown */
    body.update-notification-blur > *:not(.update-notification-overlay) {
        filter: blur(4px);
        pointer-events: none;
        user-select: none;
    }
    
    /* Overlay */
    .update-notification-overlay {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.6);
        backdrop-filter: blur(8px);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
        opacity: 0;
        transition: opacity 0.3s ease;
    }
    
    .update-notification-overlay.visible {
        opacity: 1;
    }
    
    /* Modal */
    .update-notification-modal {
        position: relative;
        background: linear-gradient(145deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 16px;
        padding: 32px;
        max-width: 480px;
        width: 90%;
        max-height: 80vh;
        overflow-y: auto;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5),
                    0 0 0 1px rgba(255, 255, 255, 0.1);
        transform: scale(0.9) translateY(20px);
        transition: transform 0.3s ease;
    }
    
    .update-notification-overlay.visible .update-notification-modal {
        transform: scale(1) translateY(0);
    }
    
    /* Close Button */
    .update-notification-close {
        position: absolute;
        top: 16px;
        right: 16px;
        width: 32px;
        height: 32px;
        border: none;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s;
    }
    
    .update-notification-close:hover {
        background: rgba(255, 255, 255, 0.2);
    }
    
    .update-notification-close svg {
        stroke: #94a3b8;
    }
    
    .update-notification-close:hover svg {
        stroke: #ffffff;
    }
    
    /* Header */
    .update-notification-header {
        text-align: center;
        margin-bottom: 24px;
    }
    
    .update-notification-icon {
        width: 64px;
        height: 64px;
        margin: 0 auto 16px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 16px;
        display: flex;
        align-items: center;
        justify-content: center;
        box-shadow: 0 8px 24px rgba(102, 126, 234, 0.3);
    }
    
    .update-notification-icon svg {
        stroke: white;
    }
    
    .update-notification-title {
        color: #ffffff;
        font-size: 24px;
        font-weight: 700;
        margin: 0 0 8px 0;
        font-family: 'Inter', 'Source Han Sans SC', 'Noto Sans SC', sans-serif;
    }
    
    .update-notification-version {
        display: inline-block;
        background: rgba(102, 126, 234, 0.2);
        color: #a5b4fc;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 13px;
        font-weight: 500;
    }
    
    /* Content */
    .update-notification-content {
        margin-bottom: 24px;
    }
    
    /* Footer */
    .update-notification-footer {
        display: flex;
        justify-content: center;
    }
    
    .update-notification-close-btn {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 10px 40px;
        border-radius: 8px;
        font-size: 15px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s ease;
        font-family: 'Inter', 'Source Han Sans SC', 'Noto Sans SC', sans-serif;
    }
    
    .update-notification-close-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 16px -8px rgba(102, 126, 234, 0.5);
    }
    
    .update-notification-close-btn:active {
        transform: translateY(0);
    }
    
    .update-notification-message {
        color: #e2e8f0;
        font-size: 15px;
        line-height: 1.7;
        margin: 0 0 20px 0;
    }
    
    .update-notification-message p {
        margin: 0 0 12px 0;
    }
    
    .update-notification-message ul,
    .update-notification-message ol {
        margin: 12px 0;
        padding-left: 24px;
    }
    
    .update-notification-message li {
        margin-bottom: 6px;
    }
    
    .update-notification-message b,
    .update-notification-message strong {
        color: #ffffff;
        font-weight: 600;
    }

    .update-notification-message img {
        max-width: 100%;
        height: auto;
        border-radius: 8px;
        margin: 12px 0;
    }
    
    /* Changelog */
    .update-notification-changelog {
        background: rgba(0, 0, 0, 0.2);
        border-radius: 12px;
        padding: 16px 20px;
    }
    
    .changelog-title {
        color: #94a3b8;
        font-size: 13px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin: 0 0 12px 0;
    }
    
    .changelog-list {
        margin: 0;
        padding: 0;
        list-style: none;
    }
    
    .changelog-list li {
        color: #e2e8f0;
        font-size: 14px;
        line-height: 1.5;
        padding: 8px 0;
        padding-left: 20px;
        position: relative;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    .changelog-list li:last-child {
        border-bottom: none;
    }
    
    .changelog-list li::before {
        content: '';
        position: absolute;
        left: 0;
        top: 50%;
        transform: translateY(-50%);
        width: 6px;
        height: 6px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 50%;
    }
    
    /* Responsive */
    @media (max-width: 480px) {
        .update-notification-modal {
            padding: 24px;
            margin: 16px;
        }
        
        .update-notification-title {
            font-size: 20px;
        }
    }
`;
document.head.appendChild(updateNotificationStyles);

// Initialize the manager
window.updateNotificationManager = new UpdateNotificationManager();

