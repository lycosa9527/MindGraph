/**
 * Event Bus - Universal event system for MindGraph
 * 
 * Provides pub/sub pattern for decoupled communication between modules.
 * All modules communicate via events instead of direct calls.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * PROPRIETARY LICENSE - ALL RIGHTS RESERVED
 * 
 * This software and associated documentation files (the "Software") are the proprietary
 * and confidential information of 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.).
 * 
 * WITHOUT EXPLICIT WRITTEN PERMISSION FROM THE COPYRIGHT HOLDER, ALL USE IS PROHIBITED,
 * including but not limited to:
 * - Use, execution, or deployment
 * - Copying, downloading, or access
 * - Modification or creation of derivative works
 * - Distribution, redistribution, or sharing
 * - Commercial use or any production deployment
 * 
 * Unauthorized use may result in severe civil and criminal penalties.
 * 
 * For licensing inquiries, please contact the copyright holder.
 * 
 * @author WANG CUNCHI
 */

class EventBus {
    constructor(logger) {
        this.logger = logger || console;
        this.listeners = {}; // { eventName: [callback1, callback2, ...] }
        this.onceListeners = {}; // { eventName: [callback1, callback2, ...] }
        this.anyListeners = []; // Listeners for all events
        this.debugMode = window.VERBOSE_LOGGING || false;
        this.eventStats = new Map(); // Track event frequency for monitoring
        
        // NEW: Listener Registry - Track listeners by owner
        this.listenerRegistry = new Map(); // { ownerId: [{ event, callback }, ...] }
        
        // Performance monitoring
        this.performanceThreshold = 100; // Warn if event takes > 100ms
        
        this.logger.info('EventBus', 'Event Bus initialized', {
            debugMode: this.debugMode
        });
    }
    
    /**
     * Subscribe to an event
     * @param {string} event - Event name (e.g., 'panel:opened')
     * @param {Function} callback - Function to call when event is emitted
     * @returns {Function} Unsubscribe function
     */
    on(event, callback) {
        if (!this.listeners[event]) {
            this.listeners[event] = [];
        }
        
        this.listeners[event].push(callback);
        
        if (this.debugMode) {
            this.logger.debug('EventBus', `Listener added for: ${event}`, {
                listenerCount: this.listeners[event].length
            });
        }
        
        // Return unsubscribe function
        return () => this.off(event, callback);
    }
    
    /**
     * Subscribe to an event with owner tracking
     * @param {string} event - Event name (e.g., 'panel:opened')
     * @param {Function} callback - Function to call when event is emitted
     * @param {string} owner - Owner identifier (e.g., 'InteractiveEditor', 'ViewManager')
     * @returns {Function} Unsubscribe function
     */
    onWithOwner(event, callback, owner) {
        if (!owner) {
            this.logger.warn('EventBus', 'onWithOwner called without owner - falling back to on()', {
                event
            });
            return this.on(event, callback);
        }
        
        // Register listener normally (existing behavior)
        this.on(event, callback);
        
        // Track ownership in registry
        if (!this.listenerRegistry.has(owner)) {
            this.listenerRegistry.set(owner, []);
        }
        this.listenerRegistry.get(owner).push({ event, callback });
        
        if (this.debugMode) {
            this.logger.debug('EventBus', `Listener added with owner: ${event}`, {
                owner,
                listenerCount: this.listeners[event].length,
                ownerListenerCount: this.listenerRegistry.get(owner).length
            });
        }
        
        // Return unsubscribe function that removes from both places
        return () => {
            this.off(event, callback);
            this.removeFromRegistry(owner, event, callback);
        };
    }
    
    /**
     * Subscribe to an event once (auto-removes after first trigger)
     * @param {string} event - Event name
     * @param {Function} callback - Function to call once
     * @returns {Function} Unsubscribe function
     */
    once(event, callback) {
        if (!this.onceListeners[event]) {
            this.onceListeners[event] = [];
        }
        
        this.onceListeners[event].push(callback);
        
        if (this.debugMode) {
            this.logger.debug('EventBus', `Once listener added for: ${event}`);
        }
        
        // Return unsubscribe function
        return () => this.offOnce(event, callback);
    }
    
    /**
     * Subscribe to all events (useful for Voice Agent context awareness)
     * @param {Function} callback - Function to call for any event
     * @returns {Function} Unsubscribe function
     */
    onAny(callback) {
        this.anyListeners.push(callback);
        
        if (this.debugMode) {
            this.logger.debug('EventBus', 'Global listener added', {
                totalGlobalListeners: this.anyListeners.length
            });
        }
        
        // Return unsubscribe function
        return () => this.offAny(callback);
    }
    
    /**
     * Unsubscribe from an event
     * @param {string} event - Event name
     * @param {Function} callback - Callback to remove
     */
    off(event, callback) {
        if (!this.listeners[event]) return;
        
        const index = this.listeners[event].indexOf(callback);
        if (index > -1) {
            this.listeners[event].splice(index, 1);
            
            if (this.debugMode) {
                this.logger.debug('EventBus', `Listener removed for: ${event}`, {
                    remainingListeners: this.listeners[event].length
                });
            }
        }
    }
    
    /**
     * Remove once listener
     */
    offOnce(event, callback) {
        if (!this.onceListeners[event]) return;
        
        const index = this.onceListeners[event].indexOf(callback);
        if (index > -1) {
            this.onceListeners[event].splice(index, 1);
        }
    }
    
    /**
     * Remove global listener
     */
    offAny(callback) {
        const index = this.anyListeners.indexOf(callback);
        if (index > -1) {
            this.anyListeners.splice(index, 1);
        }
    }
    
    /**
     * Remove specific listener from registry
     * @private
     */
    removeFromRegistry(owner, event, callback) {
        const ownerListeners = this.listenerRegistry.get(owner);
        if (!ownerListeners) return;
        
        const index = ownerListeners.findIndex(
            item => item.event === event && item.callback === callback
        );
        if (index > -1) {
            ownerListeners.splice(index, 1);
        }
        
        // Clean up empty owner entries
        if (ownerListeners.length === 0) {
            this.listenerRegistry.delete(owner);
        }
    }
    
    /**
     * Emit an event with data
     * @param {string} event - Event name
     * @param {*} data - Data to pass to listeners
     */
    emit(event, data = null) {
        const startTime = performance.now();
        
        // Track event frequency
        this.eventStats.set(event, (this.eventStats.get(event) || 0) + 1);
        
        if (this.debugMode) {
            this.logger.debug('EventBus', `Event emitted: ${event}`, {
                data: this._sanitizeLogData(data),
                listenerCount: (this.listeners[event] || []).length,
                onceListenerCount: (this.onceListeners[event] || []).length,
                globalListenerCount: this.anyListeners.length
            });
        }
        
        // Call regular listeners
        if (this.listeners[event]) {
            const listeners = [...this.listeners[event]]; // Copy to avoid modification during iteration
            listeners.forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    this.logger.error('EventBus', `Listener error for ${event}`, {
                        error: error.message,
                        stack: error.stack
                    });
                }
            });
        }
        
        // Call once listeners and remove them
        if (this.onceListeners[event]) {
            const onceListeners = [...this.onceListeners[event]];
            this.onceListeners[event] = []; // Clear all once listeners
            
            onceListeners.forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    this.logger.error('EventBus', `Once listener error for ${event}`, {
                        error: error.message,
                        stack: error.stack
                    });
                }
            });
        }
        
        // Call global listeners
        this.anyListeners.forEach(callback => {
            try {
                callback(event, data);
            } catch (error) {
                this.logger.error('EventBus', `Global listener error for ${event}`, {
                    error: error.message,
                    stack: error.stack
                });
            }
        });
        
        // Performance warning
        const duration = performance.now() - startTime;
        if (duration > this.performanceThreshold) {
            this.logger.warn('EventBus', `Slow event: ${event}`, {
                duration: `${duration.toFixed(2)}ms`,
                threshold: `${this.performanceThreshold}ms`,
                listenerCount: (this.listeners[event] || []).length
            });
        }
    }
    
    /**
     * Remove all listeners for an event
     * @param {string} event - Event name (optional, if not provided removes ALL listeners)
     */
    removeAllListeners(event = null) {
        if (event) {
            delete this.listeners[event];
            delete this.onceListeners[event];
            this.logger.debug('EventBus', `All listeners removed for: ${event}`);
        } else {
            this.listeners = {};
            this.onceListeners = {};
            this.anyListeners = [];
            this.logger.debug('EventBus', 'All listeners removed');
        }
    }
    
    /**
     * Remove ALL listeners for an owner (automatic cleanup)
     * @param {string} owner - Owner identifier
     * @returns {number} Number of listeners removed
     */
    removeAllListenersForOwner(owner) {
        const listeners = this.listenerRegistry.get(owner) || [];
        
        if (listeners.length === 0) {
            return 0;
        }
        
        // Remove each listener from Event Bus
        listeners.forEach(({ event, callback }) => {
            this.off(event, callback);
        });
        
        // Remove from registry
        this.listenerRegistry.delete(owner);
        
        if (this.debugMode) {
            this.logger.debug('EventBus', `Removed ${listeners.length} listeners for ${owner}`);
        }
        
        return listeners.length;
    }
    
    /**
     * Get event statistics (for debugging and monitoring)
     */
    getStats() {
        const totalEvents = Array.from(this.eventStats.values()).reduce((a, b) => a + b, 0);
        const uniqueEvents = this.eventStats.size;
        const topEvents = Array.from(this.eventStats.entries())
            .sort((a, b) => b[1] - a[1])
            .slice(0, 10)
            .map(([event, count]) => ({ event, count }));
        
        return {
            totalEvents,
            uniqueEvents,
            topEvents,
            totalListeners: Object.values(this.listeners).reduce((sum, arr) => sum + arr.length, 0),
            totalOnceListeners: Object.values(this.onceListeners).reduce((sum, arr) => sum + arr.length, 0),
            globalListeners: this.anyListeners.length
        };
    }
    
    /**
     * Get all registered event names
     */
    getEventNames() {
        const regularEvents = Object.keys(this.listeners);
        const onceEvents = Object.keys(this.onceListeners);
        return [...new Set([...regularEvents, ...onceEvents])].sort();
    }
    
    /**
     * Check if event has listeners
     */
    hasListeners(event) {
        return (this.listeners[event] && this.listeners[event].length > 0) ||
               (this.onceListeners[event] && this.onceListeners[event].length > 0) ||
               this.anyListeners.length > 0;
    }
    
    /**
     * Get all listeners for an owner (for debugging)
     * @param {string} owner - Owner identifier
     * @returns {Array} List of {event, callback}
     */
    getListenersForOwner(owner) {
        return this.listenerRegistry.get(owner) || [];
    }

    /**
     * Get all active listeners grouped by owner (for debugging)
     * @returns {Object} { owner: [{event, callback}, ...] }
     */
    getAllListeners() {
        const result = {};
        this.listenerRegistry.forEach((listeners, owner) => {
            result[owner] = listeners.map(l => ({
                event: l.event,
                callback: l.callback.toString().substring(0, 100) // Truncate for readability
            }));
        });
        return result;
    }

    /**
     * Get listener count by owner (for debugging)
     * @returns {Object} { owner: count }
     */
    getListenerCounts() {
        const counts = {};
        this.listenerRegistry.forEach((listeners, owner) => {
            counts[owner] = listeners.length;
        });
        return counts;
    }
    
    /**
     * Enable/disable debug mode
     */
    setDebugMode(enabled) {
        this.debugMode = enabled;
        this.logger.info('EventBus', `Debug mode ${enabled ? 'enabled' : 'disabled'}`);
    }
    
    /**
     * Sanitize data for logging (avoid circular references, limit size)
     */
    _sanitizeLogData(data) {
        if (data === null || data === undefined) return data;
        
        try {
            const jsonStr = JSON.stringify(data);
            if (jsonStr.length > 500) {
                return jsonStr.substring(0, 500) + '...(truncated)';
            }
            return JSON.parse(jsonStr); // Return clean copy
        } catch (e) {
            return '[Circular reference or non-serializable object]';
        }
    }
}

// Create global instance
if (typeof window !== 'undefined') {
    window.eventBus = new EventBus(window.logger);
    
    // Expose debug tools
    window.debugEventBus = {
        stats: () => window.eventBus.getStats(),
        events: () => window.eventBus.getEventNames(),
        clear: (event) => window.eventBus.removeAllListeners(event),
        debug: (enabled) => window.eventBus.setDebugMode(enabled),
        // NEW: Listener registry debug tools
        listeners: (owner) => owner ? window.eventBus.getListenersForOwner(owner) : window.eventBus.getAllListeners(),
        counts: () => window.eventBus.getListenerCounts(),
        removeOwner: (owner) => window.eventBus.removeAllListenersForOwner(owner)
    };
    
    if (window.logger?.debugMode) {
        console.log('%c[EventBus] Debug tools available:', 'color: #4caf50; font-weight: bold;');
        console.log('  window.debugEventBus.stats()  - View event statistics');
        console.log('  window.debugEventBus.events() - List all event names');
        console.log('  window.debugEventBus.clear()  - Remove all listeners');
        console.log('  window.debugEventBus.debug(true/false) - Toggle debug mode');
        console.log('  window.debugEventBus.listeners() - List all listeners by owner');
        console.log('  window.debugEventBus.listeners("Owner") - List listeners for specific owner');
        console.log('  window.debugEventBus.counts() - Get listener counts by owner');
        console.log('  window.debugEventBus.removeOwner("Owner") - Remove all listeners for owner');
    }
}

