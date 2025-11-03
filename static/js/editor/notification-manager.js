/**
 * NotificationManager - Centralized notification system for the editor
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class NotificationManager {
    constructor() {
        this.queue = [];
        this.currentNotifications = [];
        this.maxVisible = 3;
        this.baseTop = 80;
        this.notificationHeight = 70; // Height + gap
        
        // Initialize animations
        this.initializeStyles();
    }
    
    /**
     * Initialize CSS styles and animations
     */
    initializeStyles() {
        if (!document.getElementById('notification-manager-styles')) {
            const style = document.createElement('style');
            style.id = 'notification-manager-styles';
            style.textContent = `
                @keyframes notificationSlideIn {
                    from {
                        transform: translateX(400px);
                        opacity: 0;
                    }
                    to {
                        transform: translateX(0);
                        opacity: 1;
                    }
                }
                
                @keyframes notificationSlideOut {
                    from {
                        transform: translateX(0);
                        opacity: 1;
                    }
                    to {
                        transform: translateX(400px);
                        opacity: 0;
                    }
                }
                
                .notification-manager {
                    position: fixed;
                    z-index: 10001;
                    padding: 14px 24px;
                    border-radius: 12px;
                    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
                    font-size: 14px;
                    font-weight: 600;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    min-width: 250px;
                    max-width: 400px;
                    color: white;
                    animation: notificationSlideIn 0.3s ease;
                    transition: top 0.3s ease;
                }
                
                .notification-manager.closing {
                    animation: notificationSlideOut 0.3s ease;
                }
                
                .notification-icon {
                    font-size: 18px;
                    font-weight: bold;
                    flex-shrink: 0;
                }
                
                .notification-message {
                    flex: 1;
                    word-break: break-word;
                }
            `;
            document.head.appendChild(style);
        }
    }
    
    /**
     * Show a notification
     * @param {string} message - The notification message
     * @param {string} type - Type: 'success', 'error', 'warning', 'info'
     * @param {number} duration - Duration in ms (optional)
     */
    show(message, type = 'info', duration = null) {
        logger.debug('NotificationManager', 'Showing notification', { type });
        
        // Auto duration based on type
        if (!duration) {
            duration = {
                'error': 5000,
                'warning': 4000,
                'success': 2000,
                'info': 3000
            }[type] || 3000;
        }
        
        // Add to queue if max reached
        if (this.currentNotifications.length >= this.maxVisible) {
            logger.debug('NotificationManager', 'Queue full, adding to queue');
            this.queue.push({ message, type, duration });
            return;
        }
        
        this.createNotification(message, type, duration);
    }
    
    /**
     * Create and display a notification
     */
    createNotification(message, type, duration) {
        const notification = document.createElement('div');
        notification.className = 'notification-manager';
        
        // Calculate position based on existing notifications
        const index = this.currentNotifications.length;
        const top = this.baseTop + (index * this.notificationHeight);
        
        notification.style.top = `${top}px`;
        notification.style.right = '20px';
        
        // Set colors based on type
        const styles = {
            success: {
                background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                icon: '✓'
            },
            error: {
                background: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
                icon: '✕'
            },
            info: {
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                icon: 'ℹ'
            },
            warning: {
                background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
                icon: '⚠'
            }
        };
        
        const currentStyle = styles[type] || styles.info;
        notification.style.background = currentStyle.background;
        
        // Add icon
        const icon = document.createElement('span');
        icon.className = 'notification-icon';
        icon.textContent = currentStyle.icon;
        notification.appendChild(icon);
        
        // Add message
        const messageSpan = document.createElement('span');
        messageSpan.className = 'notification-message';
        messageSpan.textContent = message;
        notification.appendChild(messageSpan);
        
        // Add to DOM
        document.body.appendChild(notification);
        
        // Track notification
        const notificationData = { element: notification, top };
        this.currentNotifications.push(notificationData);
        
        // Auto-remove after duration
        setTimeout(() => {
            this.removeNotification(notificationData);
        }, duration);
    }
    
    /**
     * Remove a notification
     */
    removeNotification(notificationData) {
        const { element } = notificationData;
        
        // Add closing animation
        element.classList.add('closing');
        
        setTimeout(() => {
            // Remove from DOM
            if (document.body.contains(element)) {
                document.body.removeChild(element);
            }
            
            // Remove from tracking
            const index = this.currentNotifications.indexOf(notificationData);
            if (index > -1) {
                this.currentNotifications.splice(index, 1);
            }
            
            // Reposition remaining notifications
            this.repositionNotifications();
            
            // Show next queued notification
            if (this.queue.length > 0) {
                const next = this.queue.shift();
                this.createNotification(next.message, next.type, next.duration);
            }
        }, 300); // Wait for animation
    }
    
    /**
     * Reposition all visible notifications
     */
    repositionNotifications() {
        this.currentNotifications.forEach((notificationData, index) => {
            const newTop = this.baseTop + (index * this.notificationHeight);
            notificationData.element.style.top = `${newTop}px`;
            notificationData.top = newTop;
        });
    }
    
    /**
     * Clear all notifications
     */
    clearAll() {
        this.currentNotifications.forEach(data => {
            if (document.body.contains(data.element)) {
                document.body.removeChild(data.element);
            }
        });
        this.currentNotifications = [];
        this.queue = [];
    }
}

// Create global singleton instance
if (typeof window !== 'undefined') {
    window.notificationManager = new NotificationManager();
    logger.debug('NotificationManager', 'Global instance created');
}

