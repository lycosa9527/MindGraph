/**
 * Session Lifecycle Manager
 * =========================
 * 
 * Centralized manager lifecycle tracking for memory leak prevention.
 * Ensures all managers are properly destroyed during session cleanup.
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 */

class SessionLifecycleManager {
    constructor() {
        this.currentSessionId = null;
        this.diagramType = null;
        this.managers = [];
        
        logger.info('SessionLifecycle', 'Lifecycle manager initialized');
    }
    
    /**
     * Start a new session
     */
    startSession(sessionId, diagramType) {
        // Clean up previous session if any
        if (this.managers.length > 0) {
            logger.warn('SessionLifecycle', 'Starting new session with existing managers', {
                oldSession: this.currentSessionId?.substr(-8),
                newSession: sessionId.substr(-8),
                managerCount: this.managers.length
            });
            this.cleanup();
        }
        
        this.currentSessionId = sessionId;
        this.diagramType = diagramType;
        
        logger.info('SessionLifecycle', 'Session started', {
            sessionId: sessionId.substr(-8),
            diagramType: diagramType
        });
    }
    
    /**
     * Register a manager for lifecycle management
     * @param {Object} manager - Manager instance (must have destroy() method)
     * @param {string} name - Manager name for logging
     * @returns {Object} The manager (for chaining)
     */
    register(manager, name) {
        if (!manager) {
            logger.error('SessionLifecycle', `Cannot register null manager: ${name}`);
            return manager;
        }
        
        // Warn if manager doesn't have destroy()
        if (typeof manager.destroy !== 'function') {
            logger.warn('SessionLifecycle', `Manager "${name}" missing destroy() method`, {
                managerType: manager.constructor.name
            });
        }
        
        this.managers.push({ manager, name });
        
        logger.debug('SessionLifecycle', `Registered: ${name}`, {
            totalManagers: this.managers.length
        });
        
        return manager;  // Allow chaining
    }
    
    /**
     * Clean up all registered managers
     */
    cleanup() {
        if (this.managers.length === 0) {
            logger.debug('SessionLifecycle', 'No managers to clean up');
            return;
        }
        
        logger.info('SessionLifecycle', 'Cleaning up session', {
            sessionId: this.currentSessionId?.substr(-8),
            diagramType: this.diagramType,
            managerCount: this.managers.length
        });
        
        let successCount = 0;
        let errorCount = 0;
        
        // Destroy in reverse order (LIFO - Last In First Out)
        for (let i = this.managers.length - 1; i >= 0; i--) {
            const { manager, name } = this.managers[i];
            
            try {
                if (typeof manager.destroy === 'function') {
                    logger.debug('SessionLifecycle', `Destroying: ${name}`);
                    manager.destroy();
                    successCount++;
                } else {
                    logger.warn('SessionLifecycle', `Skipping ${name} (no destroy method)`);
                }
            } catch (error) {
                errorCount++;
                logger.error('SessionLifecycle', `Error destroying ${name}`, error);
            }
        }
        
        // Clear registry
        this.managers = [];
        this.currentSessionId = null;
        this.diagramType = null;
        
        logger.info('SessionLifecycle', 'Session cleanup complete', {
            success: successCount,
            errors: errorCount
        });
    }
    
    /**
     * Get current session info (for debugging)
     */
    getSessionInfo() {
        return {
            sessionId: this.currentSessionId,
            diagramType: this.diagramType,
            managerCount: this.managers.length,
            managers: this.managers.map(m => m.name)
        };
    }
}

// Create global singleton
if (typeof window !== 'undefined') {
    window.sessionLifecycle = new SessionLifecycleManager();
    logger.info('SessionLifecycle', 'Global instance created');
}

