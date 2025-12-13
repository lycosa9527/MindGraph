/**
 * Session Lifecycle Manager
 * =========================
 * 
 * Centralized manager lifecycle tracking for memory leak prevention.
 * Ensures all managers are properly destroyed during session cleanup.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
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
        
        // CRITICAL: Store the current session ID BEFORE clearing it
        // This ensures managers (like voice agent) can clean up using the correct session ID
        const sessionIdToCleanup = this.currentSessionId;
        
        logger.info('SessionLifecycle', 'Cleaning up session', {
            sessionId: sessionIdToCleanup?.substr(-8),
            diagramType: this.diagramType,
            managerCount: this.managers.length
        });
        
        // Emit lifecycle event BEFORE destroying managers
        // This allows managers to cancel operations before destruction
        // CRITICAL: Use the stored session ID, not this.currentSessionId (which might be cleared)
        if (window.eventBus) {
            window.eventBus.emit('lifecycle:session_ending', {
                sessionId: sessionIdToCleanup,
                diagramType: this.diagramType,
                managerCount: this.managers.length
            });
        }
        
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
        
        // Verify Event Bus listeners are cleaned up
        if (window.eventBus && typeof window.eventBus.getAllListeners === 'function') {
            const remainingListeners = window.eventBus.getAllListeners();
            
            // Session-scoped managers (should be destroyed and have no listeners)
            const sessionOwners = [
                'InteractiveEditor',
                'ViewManager',
                'InteractionHandler',
                'CanvasController',
                'HistoryManager',
                'DiagramOperationsLoader',
                'MindMateManager',
                'LLMAutoCompleteManager',
                'SessionManager',
                'ToolbarManager',
                'PropertyPanelManager',
                'ExportManager',
                'AutoCompleteManager',
                'SmallOperationsManager',
                'TextToolbarStateManager',
                'ThinkGuideManager',
                'VoiceAgentManager',
                'LLMValidationManager',
                'NodePropertyOperationsManager',
                'NodeCounterFeatureModeManager',
                'UIStateLLMManager'
            ];
            
            // Global managers (persist across sessions - listeners are expected)
            const globalOwners = [
                'PanelManager'  // Global panel management, persists across sessions
            ];
            
            sessionOwners.forEach(owner => {
                if (remainingListeners[owner] && remainingListeners[owner].length > 0) {
                    logger.warn('SessionLifecycle', `Listener leak detected for ${owner}`, {
                        count: remainingListeners[owner].length,
                        events: remainingListeners[owner].map(l => l.event)
                    });
                }
            });
            
            // Log global owners for debugging (not a leak, just informational)
            if (logger.debugMode) {
                globalOwners.forEach(owner => {
                    if (remainingListeners[owner] && remainingListeners[owner].length > 0) {
                        logger.debug('SessionLifecycle', `Global manager ${owner} has ${remainingListeners[owner].length} listeners (expected)`, {
                            count: remainingListeners[owner].length,
                            events: remainingListeners[owner].map(l => l.event)
                        });
                    }
                });
            }
        }
        
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

