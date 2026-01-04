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
 * AI Disclaimer Notification Manager
 * ===================================
 * 
 * Displays a small notification popup when user re-logins to the gallery page.
 * Shows AI content disclaimer message.
 * 
 * Features:
 * - Small, unobtrusive popup
 * - Shows once per login session
 * - Auto-dismisses after a few seconds or can be manually closed
 */

class AIDisclaimerNotificationManager {
    constructor() {
        this.notificationContainer = null;
        this.isVisible = false;
        this.COOKIE_NAME = 'show_ai_disclaimer';
        this.MESSAGE = '本产品内容由AI自动生成，请您根据国家法律法规规范使用。';
        
        // Initialize when DOM is ready
        this.init();
    }
    
    /**
     * Get cookie value by name
     */
    getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) {
            return parts.pop().split(';').shift();
        }
        return null;
    }
    
    /**
     * Delete cookie by name
     */
    deleteCookie(name) {
        document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`;
    }
    
    /**
     * Initialize the notification manager
     */
    init() {
        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => {
                // Small delay to ensure gallery is rendered
                setTimeout(() => this.checkAndShow(), 300);
            });
        } else {
            // Small delay to ensure gallery is visible
            setTimeout(() => this.checkAndShow(), 300);
        }
    }
    
    /**
     * Check if notification should be shown
     */
    checkAndShow() {
        // Check if cookie indicates we should show the notification
        const shouldShow = this.getCookie(this.COOKIE_NAME);
        if (shouldShow !== 'true') {
            return;
        }
        
        // Check if we're on the gallery landing page
        const landing = document.getElementById('editor-landing');
        if (!landing || landing.style.display === 'none') {
            // If gallery is not visible, wait a bit and check again
            setTimeout(() => {
                const landingRetry = document.getElementById('editor-landing');
                if (landingRetry && landingRetry.style.display !== 'none') {
                    this.showNotification();
                }
            }, 500);
            return;
        }
        
        // Check if user is authenticated (only show for logged-in users)
        if (typeof auth !== 'undefined') {
            auth.isAuthenticated().then(isAuth => {
                if (isAuth) {
                    // Double-check gallery is visible before showing
                    const landing = document.getElementById('editor-landing');
                    if (landing && landing.style.display !== 'none') {
                        // Small delay to ensure smooth animation
                        setTimeout(() => {
                            this.showNotification();
                        }, 200);
                    }
                }
            }).catch(() => {
                // Ignore auth errors
            });
        } else {
            // Wait for auth to be available
            const checkAuth = setInterval(() => {
                if (typeof auth !== 'undefined') {
                    clearInterval(checkAuth);
                    auth.isAuthenticated().then(isAuth => {
                        if (isAuth) {
                            // Double-check gallery is visible before showing
                            const landing = document.getElementById('editor-landing');
                            if (landing && landing.style.display !== 'none') {
                                // Small delay to ensure smooth animation
                                setTimeout(() => {
                                    this.showNotification();
                                }, 200);
                            }
                        }
                    }).catch(() => {
                        // Ignore auth errors
                    });
                }
            }, 200);
            
            // Stop checking after 5 seconds
            setTimeout(() => clearInterval(checkAuth), 5000);
        }
    }
    
    /**
     * Show the notification popup
     */
    showNotification() {
        if (this.isVisible) return;
        
        // Clear the cookie so it won't show again until next login
        this.deleteCookie(this.COOKIE_NAME);
        
        this.isVisible = true;
        this.createNotification();
        
        if (window.logger) {
            window.logger.info('AIDisclaimer', 'Showing AI disclaimer notification');
        }
    }
    
    /**
     * Create the notification DOM element
     */
    createNotification() {
        // Create notification container
        this.notificationContainer = document.createElement('div');
        this.notificationContainer.className = 'ai-disclaimer-notification';
        this.notificationContainer.innerHTML = `
            <div class="ai-disclaimer-content">
                <span class="ai-disclaimer-message">${this.escapeHtml(this.MESSAGE)}</span>
                <button class="ai-disclaimer-close" id="ai-disclaimer-close" title="关闭">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
            </div>
        `;
        
        // Add to document
        document.body.appendChild(this.notificationContainer);
        
        // Bind close button
        const closeBtn = this.notificationContainer.querySelector('#ai-disclaimer-close');
        closeBtn.addEventListener('click', () => this.dismissNotification());
        
        // Auto-dismiss after 5 seconds
        this.autoDismissTimer = setTimeout(() => {
            this.dismissNotification();
        }, 5000);
        
        // Trigger animation
        requestAnimationFrame(() => {
            this.notificationContainer.classList.add('visible');
        });
    }
    
    /**
     * Dismiss the notification
     */
    dismissNotification() {
        if (!this.isVisible) return;
        
        // Clear auto-dismiss timer
        if (this.autoDismissTimer) {
            clearTimeout(this.autoDismissTimer);
            this.autoDismissTimer = null;
        }
        
        // Remove notification with animation
        if (this.notificationContainer) {
            this.notificationContainer.classList.remove('visible');
            
            // Wait for animation then remove DOM element
            setTimeout(() => {
                if (this.notificationContainer && this.notificationContainer.parentNode) {
                    this.notificationContainer.parentNode.removeChild(this.notificationContainer);
                }
                this.notificationContainer = null;
                this.isVisible = false;
            }, 300);
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
}

// Inject CSS styles
const aiDisclaimerStyles = document.createElement('style');
aiDisclaimerStyles.textContent = `
    /* AI Disclaimer Notification */
    .ai-disclaimer-notification {
        position: fixed;
        bottom: 24px;
        right: 24px;
        z-index: 9999;
        opacity: 0;
        transform: translateY(20px);
        transition: opacity 0.3s ease, transform 0.3s ease;
        pointer-events: none;
    }
    
    .ai-disclaimer-notification.visible {
        opacity: 1;
        transform: translateY(0);
        pointer-events: auto;
    }
    
    .ai-disclaimer-content {
        background: rgba(255, 255, 255, 0.95);
        backdrop-filter: blur(10px);
        border-radius: 12px;
        padding: 14px 20px;
        padding-right: 48px;
        max-width: 600px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15),
                    0 0 0 1px rgba(102, 126, 234, 0.2);
        position: relative;
        display: flex;
        align-items: center;
        border: 1px solid rgba(102, 126, 234, 0.15);
    }
    
    .ai-disclaimer-message {
        color: #333;
        font-size: 13px;
        line-height: 1.5;
        font-family: 'Inter', 'Microsoft YaHei', sans-serif;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    .ai-disclaimer-close {
        position: absolute;
        top: 10px;
        right: 10px;
        width: 24px;
        height: 24px;
        border: none;
        background: rgba(102, 126, 234, 0.1);
        border-radius: 6px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.2s;
        padding: 0;
    }
    
    .ai-disclaimer-close:hover {
        background: rgba(102, 126, 234, 0.2);
    }
    
    .ai-disclaimer-close svg {
        stroke: #667eea;
    }
    
    .ai-disclaimer-close:hover svg {
        stroke: #764ba2;
    }
    
    /* Responsive */
    @media (max-width: 768px) {
        .ai-disclaimer-content {
            max-width: calc(100vw - 32px);
        }
        
        .ai-disclaimer-message {
            white-space: normal;
            line-height: 1.5;
        }
    }
    
    @media (max-width: 480px) {
        .ai-disclaimer-notification {
            bottom: 16px;
            right: 16px;
            left: 16px;
        }
        
        .ai-disclaimer-content {
            max-width: 100%;
            padding: 12px 16px;
            padding-right: 40px;
        }
        
        .ai-disclaimer-message {
            font-size: 12px;
            white-space: normal;
        }
    }
`;
document.head.appendChild(aiDisclaimerStyles);

// Initialize the manager when DOM is ready
if (typeof window !== 'undefined') {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            window.aiDisclaimerNotification = new AIDisclaimerNotificationManager();
        });
    } else {
        window.aiDisclaimerNotification = new AIDisclaimerNotificationManager();
    }
}

