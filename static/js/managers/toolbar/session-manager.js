/**
 * Session Manager
 * ===============
 * 
 * Manages toolbar manager instance lifecycle and session tracking.
 * Handles session registration, validation, and cleanup.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class SessionManager {
    constructor(eventBus, logger) {
        this.eventBus = eventBus;
        this.logger = logger || console;
        
        // NEW: Add owner identifier for Event Bus Listener Registry
        this.ownerId = 'SessionManager';
        
        // Session tracking
        this.sessionId = null;
        this.diagramType = null;
        this.registeredInstances = new Map();
        
        // Initialize global registry
        if (!window.toolbarManagerRegistry) {
            window.toolbarManagerRegistry = new Map();
            this.logger.debug('SessionManager', 'Registry initialized');
        }
        
        // Subscribe to events
        this.subscribeToEvents();
        
        this.logger.info('SessionManager', 'Session Manager initialized');
    }
    
    /**
     * Subscribe to Event Bus events
     */
    subscribeToEvents() {
        // Listen for session registration requests
        this.eventBus.onWithOwner('session:register_requested', (data) => {
            this.registerInstance(data.sessionId, data.diagramType, data.instance);
        }, this.ownerId);
        
        // Listen for session validation requests
        this.eventBus.onWithOwner('session:validate_requested', (data) => {
            const isValid = this.validateSession(data.sessionId);
            this.eventBus.emit('session:validation_result', {
                sessionId: data.sessionId,
                isValid
            });
        }, this.ownerId);
        
        // Listen for session cleanup requests
        this.eventBus.onWithOwner('session:cleanup_requested', async (data) => {
            await this.cleanupSession(data.sessionId);
        }, this.ownerId);
        
        this.logger.debug('SessionManager', 'Subscribed to events with owner tracking');
    }
    
    /**
     * Register a toolbar manager instance
     * @param {string} sessionId - Session ID
     * @param {string} diagramType - Diagram type
     * @param {Object} instance - Toolbar manager instance
     */
    registerInstance(sessionId, diagramType, instance) {
        if (!sessionId) {
            this.logger.error('SessionManager', 'Cannot register instance - no session ID');
            return;
        }
        
        this.sessionId = sessionId;
        this.diagramType = diagramType;
        
        // Clean up any existing toolbar manager from a different session
        window.toolbarManagerRegistry.forEach((oldManager, oldSessionId) => {
            if (oldSessionId !== sessionId) {
                this.logger.debug('SessionManager', 'Cleaning up old instance', {
                    oldSession: oldSessionId?.substr(-8)
                });
                
                // Emit cleanup event
                this.eventBus.emit('session:old_instance_cleanup', {
                    sessionId: oldSessionId
                });
                
                // Destroy old instance if it has a destroy method
                if (oldManager && typeof oldManager.destroy === 'function') {
                    oldManager.destroy();
                }
                
                window.toolbarManagerRegistry.delete(oldSessionId);
            }
        });
        
        // Register new instance
        window.toolbarManagerRegistry.set(sessionId, instance);
        this.registeredInstances.set(sessionId, {
            diagramType,
            registeredAt: Date.now()
        });
        
        this.logger.info('SessionManager', 'Instance registered', {
            sessionId: sessionId?.substr(-8),
            diagramType,
            totalRegistered: window.toolbarManagerRegistry.size
        });
        
        // Emit registration event
        this.eventBus.emit('session:registered', {
            sessionId,
            diagramType
        });
    }
    
    /**
     * Validate session
     * @param {string} sessionId - Session ID to validate
     * @returns {boolean} Whether session is valid
     */
    validateSession(sessionId) {
        if (!sessionId) {
            this.logger.warn('SessionManager', 'Validation failed - no session ID provided');
            return false;
        }
        
        if (sessionId !== this.sessionId) {
            this.logger.warn('SessionManager', 'Validation failed - session ID mismatch', {
                expected: this.sessionId?.substr(-8),
                received: sessionId?.substr(-8)
            });
            return false;
        }
        
        return true;
    }
    
    /**
     * Get current session info
     * @returns {Object|null} Session info
     */
    getSessionInfo() {
        if (!this.sessionId) {
            return null;
        }
        
        return {
            sessionId: this.sessionId,
            diagramType: this.diagramType,
            registered: this.registeredInstances.has(this.sessionId)
        };
    }
    
    /**
     * Cleanup session
     * @param {string} sessionId - Session ID to cleanup
     */
    async cleanupSession(sessionId) {
        if (!sessionId) {
            sessionId = this.sessionId;
        }
        
        if (!sessionId) {
            this.logger.warn('SessionManager', 'No session to cleanup');
            return;
        }
        
        this.logger.info('SessionManager', 'Cleaning up session', {
            sessionId: sessionId?.substr(-8)
        });
        
        // CRITICAL: Cleanup backend voice session via API
        // This ensures backend voice sessions are properly cleaned up when diagram session ends
        try {
            const token = localStorage.getItem('access_token');
            if (token) {
                const response = await fetch(`/api/voice/cleanup/${sessionId}`, {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    }
                });
                
                if (response.ok) {
                    const result = await response.json();
                    this.logger.debug('SessionManager', 'Voice session cleaned up', result);
                } else {
                    this.logger.warn('SessionManager', 'Voice cleanup API call failed', {
                        status: response.status,
                        statusText: response.statusText
                    });
                }
            } else {
                this.logger.warn('SessionManager', 'No auth token for voice cleanup');
            }
        } catch (error) {
            // Non-critical - log but don't fail session cleanup
            this.logger.warn('SessionManager', 'Voice cleanup API call error (non-critical)', error);
        }
        
        // Remove from registry
        window.toolbarManagerRegistry.delete(sessionId);
        this.registeredInstances.delete(sessionId);
        
        // Clear current session if it matches
        if (sessionId === this.sessionId) {
            this.sessionId = null;
            this.diagramType = null;
        }
        
        // Emit cleanup complete event
        this.eventBus.emit('session:cleanup_completed', {
            sessionId
        });
    }
    
    /**
     * Cleanup all sessions
     */
    async cleanupAllSessions() {
        this.logger.info('SessionManager', 'Cleaning up all sessions');
        
        const sessionIds = Array.from(this.registeredInstances.keys());
        // Use Promise.all to cleanup all sessions concurrently
        await Promise.all(sessionIds.map(sessionId => this.cleanupSession(sessionId)));
    }
    
    /**
     * Get all registered sessions
     * @returns {Array} List of session info objects
     */
    getAllSessions() {
        const sessions = [];
        
        this.registeredInstances.forEach((info, sessionId) => {
            sessions.push({
                sessionId,
                diagramType: info.diagramType,
                registeredAt: info.registeredAt,
                age: Date.now() - info.registeredAt
            });
        });
        
        return sessions;
    }
    
    /**
     * Destroy session manager
     */
    destroy() {
        this.logger.info('SessionManager', 'Destroying Session Manager');
        
        // Remove all Event Bus listeners (using Listener Registry)
        if (this.eventBus && this.ownerId) {
            const removedCount = this.eventBus.removeAllListenersForOwner(this.ownerId);
            if (removedCount > 0) {
                this.logger.debug('SessionManager', `Removed ${removedCount} Event Bus listeners`);
            }
        }
        
        // Cleanup all sessions
        // Note: This is called from destroy(), which is synchronous, so we don't await
        // The cleanup will happen asynchronously but that's fine for cleanup
        this.cleanupAllSessions().catch(err => {
            this.logger.warn('SessionManager', 'Error during async cleanup (non-critical)', err);
        });
        
        // Clear references
        this.eventBus = null;
        this.logger = null;
    }
}

// Make available globally
window.SessionManager = SessionManager;


