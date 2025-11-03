/**
 * Centralized Console Logger for MindGraph
 * 
 * Provides structured logging with levels, controlled by debug mode.
 * Clean and professional logging that respects user preferences.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class Logger {
    constructor() {
        // Check if debug mode is enabled via URL parameter or localStorage
        const urlParams = new URLSearchParams(window.location.search);
        const urlDebug = urlParams.get('debug');
        
        // Try to access localStorage (may not be available in headless contexts)
        let storedDebug = null;
        try {
            storedDebug = localStorage.getItem('mindgraph_debug');
        } catch (e) {
            // localStorage not available (e.g., headless browser with raw HTML)
            storedDebug = null;
        }
        
        // Debug mode enabled if: ?debug=1 in URL or localStorage is 'true'
        this.debugMode = urlDebug === '1' || storedDebug === 'true';
        
        // Verbose mode enabled from backend (set by template)
        this.verboseMode = window.VERBOSE_LOGGING || false;
        
        // Log levels (only show if debug is enabled)
        this.levels = {
            DEBUG: 0,
            INFO: 1,
            WARN: 2,
            ERROR: 3
        };
        
        // Current minimum level to display
        this.minLevel = (this.debugMode || this.verboseMode) ? this.levels.DEBUG : this.levels.INFO;
        
        // Batching system for backend logs
        this.logBatch = [];
        this.batchSize = 10; // Send after 10 logs
        this.batchTimeout = 2000; // Or after 2 seconds
        this.batchTimer = null;
        this.isSendingBatch = false;
        
        // Show startup message if debug/verbose mode enabled
        if (this.debugMode || this.verboseMode) {
            const mode = this.verboseMode ? 'VERBOSE' : 'Debug';
            console.log(`%c[MindGraph] ${mode} mode ENABLED`, 'color: #4caf50; font-weight: bold;');
            if (this.verboseMode) {
                console.log('[MindGraph] Verbose logging: All user interactions will be logged');
            }
            if (this.debugMode) {
                console.log('[MindGraph] To disable: localStorage.removeItem("mindgraph_debug") and reload');
            }
            console.log('%c[MindGraph] Frontend logs streaming to backend', 'color: #00bcd4; font-weight: bold;');
        }
        
        // Track last log to avoid duplicates
        this.lastLog = null;
        this.lastLogCount = 0;
        
        // Flush logs before page unload
        window.addEventListener('beforeunload', () => {
            this._flushBatch(true); // Force flush
        });
    }
    
    /**
     * Enable or disable debug mode
     */
    setDebugMode(enabled) {
        this.debugMode = enabled;
        this.minLevel = (enabled || this.verboseMode) ? this.levels.DEBUG : this.levels.INFO;
        
        // Try to save to localStorage (may not be available in headless contexts)
        try {
            localStorage.setItem('mindgraph_debug', enabled ? 'true' : 'false');
        } catch (e) {
            // localStorage not available
        }
        
        if (enabled) {
            console.log('%c[MindGraph] Debug mode ENABLED', 'color: #4caf50; font-weight: bold;');
        } else {
            console.log('%c[MindGraph] Debug mode DISABLED', 'color: #f44336; font-weight: bold;');
        }
    }
    
    /**
     * Check if verbose logging is enabled
     */
    isVerbose() {
        return this.verboseMode || this.debugMode;
    }
    
    /**
     * Round numbers to 2 decimal places for cleaner logs
     * Recursively processes objects and arrays
     * Also handles strings containing numbers (like viewBox)
     */
    _roundNumbers(obj, depth = 0) {
        // Prevent infinite recursion
        if (depth > 10) return obj;
        
        if (typeof obj === 'number') {
            // Round to 2 decimal places
            return Math.round(obj * 100) / 100;
        }
        
        if (typeof obj === 'string') {
            // Round numbers within strings (e.g., viewBox: "106.80 18.996125030517575 320.40 785.7038940429687")
            return obj.replace(/\d+\.\d+/g, (match) => {
                const num = parseFloat(match);
                return (Math.round(num * 100) / 100).toString();
            });
        }
        
        if (Array.isArray(obj)) {
            return obj.map(item => this._roundNumbers(item, depth + 1));
        }
        
        if (obj && typeof obj === 'object') {
            const rounded = {};
            for (const key in obj) {
                if (obj.hasOwnProperty(key)) {
                    rounded[key] = this._roundNumbers(obj[key], depth + 1);
                }
            }
            return rounded;
        }
        
        return obj;
    }
    
    /**
     * Format log message with timestamp and context
     */
    _format(level, component, message, data = null) {
        const timestamp = new Date().toTimeString().split(' ')[0];
        const levelStr = Object.keys(this.levels).find(key => this.levels[key] === level);
        
        // Color codes for different levels
        const colors = {
            DEBUG: '#9e9e9e',
            INFO: '#2196f3',
            WARN: '#ff9800',
            ERROR: '#f44336'
        };
        
        const color = colors[levelStr];
        const prefix = `[${timestamp}] ${levelStr.padEnd(5)} | ${component.padEnd(20)}`;
        
        // Round numbers in data for cleaner logs
        // Skip _roundNumbers for Error objects to preserve error information
        const cleanData = data ? (data instanceof Error ? data : this._roundNumbers(data)) : null;
        
        return { prefix, color, message, data: cleanData };
    }
    
    /**
     * Check if we should suppress duplicate logs
     */
    _shouldSuppress(prefix, message) {
        const currentLog = `${prefix}${message}`;
        
        if (currentLog === this.lastLog) {
            this.lastLogCount++;
            // Suppress if we've seen this more than 3 times
            if (this.lastLogCount > 3) {
                return true;
            }
        } else {
            // Show count if we suppressed duplicates
            if (this.lastLogCount > 3) {
                console.log(`%c(Last message repeated ${this.lastLogCount - 3} times)`, 'color: #9e9e9e; font-style: italic;');
            }
            this.lastLog = currentLog;
            this.lastLogCount = 1;
        }
        
        return false;
    }
    
    /**
     * Log at DEBUG level (only visible in debug mode)
     */
    debug(component, message, data = null) {
        if (this.levels.DEBUG < this.minLevel) return;
        
        const { prefix, color, message: msg, data: d } = this._format(this.levels.DEBUG, component, message, data);
        
        if (this._shouldSuppress(prefix, msg)) return;
        
        if (d) {
            console.log(`%c${prefix} | ${msg}`, `color: ${color}`, d);
        } else {
            console.log(`%c${prefix} | ${msg}`, `color: ${color}`);
        }
        
        // Send to backend in debug/verbose mode
        if (this.debugMode || this.verboseMode) {
            this._sendToBackend('DEBUG', component, msg, d);
        }
    }
    
    /**
     * Log at INFO level (important operations)
     */
    info(component, message, data = null) {
        if (this.levels.INFO < this.minLevel) return;
        
        const { prefix, color, message: msg, data: d } = this._format(this.levels.INFO, component, message, data);
        
        if (d) {
            console.log(`%c${prefix} | ${msg}`, `color: ${color}; font-weight: bold;`, d);
        } else {
            console.log(`%c${prefix} | ${msg}`, `color: ${color}; font-weight: bold;`);
        }
        
        // Send to backend in debug/verbose mode
        if (this.debugMode || this.verboseMode) {
            this._sendToBackend('INFO', component, msg, d);
        }
    }
    
    /**
     * Log at WARN level (always visible)
     */
    warn(component, message, data = null) {
        if (this.levels.WARN < this.minLevel) return;
        
        const { prefix, color, message: msg, data: d } = this._format(this.levels.WARN, component, message, data);
        
        if (d) {
            console.warn(`%c${prefix} | ${msg}`, `color: ${color}; font-weight: bold;`, d);
        } else {
            console.warn(`%c${prefix} | ${msg}`, `color: ${color}; font-weight: bold;`);
        }
        
        // Always send warnings to backend
        this._sendToBackend('WARN', component, msg, d);
    }
    
    /**
     * Log at ERROR level (always visible, sends to backend)
     */
    error(component, message, error = null) {
        const { prefix, color, message: msg, data: e } = this._format(this.levels.ERROR, component, message, error);
        
        if (e) {
            // Format error information for better console display
            let errorInfo = '';
            if (e instanceof Error) {
                errorInfo = `\n    Error: ${e.message}`;
                if (this.debugMode && e.stack) {
                    errorInfo += `\n    Stack: ${e.stack}`;
                }
            } else if (typeof e === 'object') {
                try {
                    errorInfo = `\n    ${JSON.stringify(e, null, 2)}`;
                } catch (err) {
                    errorInfo = `\n    ${e.toString()}`;
                }
            } else {
                errorInfo = `\n    ${e}`;
            }
            console.error(`%c${prefix} | ${msg}${errorInfo}`, `color: ${color}; font-weight: bold;`);
        } else {
            console.error(`%c${prefix} | ${msg}`, `color: ${color}; font-weight: bold;`);
        }
        
        // Send errors to backend for tracking
        this._sendToBackend('ERROR', component, msg, e);
    }
    
    /**
     * Log a group of related messages (collapsed by default)
     */
    group(component, title, callback, collapsed = true) {
        if (!this.debugMode) return;
        
        if (collapsed) {
            console.groupCollapsed(`[${component}] ${title}`);
        } else {
            console.group(`[${component}] ${title}`);
        }
        
        callback();
        console.groupEnd();
    }
    
    /**
     * Send logs to backend Python terminal with batching
     * - Production mode: Only ERROR and WARN
     * - Debug mode: All levels (DEBUG, INFO, WARN, ERROR)
     */
    _sendToBackend(level, component, message, data = null) {
        try {
            // Format data for backend
            let dataStr = null;
            if (data) {
                if (data instanceof Error) {
                    dataStr = data.stack || data.toString();
                } else if (typeof data === 'object') {
                    // Limit object size to prevent huge payloads
                    try {
                        const jsonStr = JSON.stringify(data);
                        dataStr = jsonStr.length > 2000 ? jsonStr.substring(0, 2000) + '...(truncated)' : jsonStr;
                    } catch (e) {
                        dataStr = '[Circular reference or non-serializable object]';
                    }
                } else {
                    dataStr = data.toString();
                }
            }
            
            // Create full message with component and data
            let fullMessage = `[${component}] ${message}`;
            if (dataStr) {
                fullMessage += ` | ${dataStr}`;
            }
            
            // Add to batch instead of sending immediately
            this.logBatch.push({
                level: level,
                message: fullMessage,
                source: component,
                timestamp: new Date().toISOString()
            });
            
            // Send batch if it reaches the size limit
            if (this.logBatch.length >= this.batchSize) {
                this._flushBatch();
            } else {
                // Set timer to flush after timeout
                if (this.batchTimer) {
                    clearTimeout(this.batchTimer);
                }
                this.batchTimer = setTimeout(() => this._flushBatch(), this.batchTimeout);
            }
        } catch (e) {
            // Silently ignore logging errors
        }
    }
    
    /**
     * Flush accumulated logs to backend
     */
    _flushBatch(isSync = false) {
        if (this.logBatch.length === 0 || this.isSendingBatch) return;
        
        this.isSendingBatch = true;
        const logsToSend = [...this.logBatch];
        this.logBatch = [];
        
        if (this.batchTimer) {
            clearTimeout(this.batchTimer);
            this.batchTimer = null;
        }
        
        try {
            const payload = {
                logs: logsToSend,
                batch_size: logsToSend.length
            };
            
            if (isSync) {
                // Use sendBeacon for synchronous page unload
                const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
                navigator.sendBeacon('/api/frontend_log_batch', blob);
            } else {
                // Normal async fetch
                fetch('/api/frontend_log_batch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                    keepalive: true // Allow request to continue even if page is closing
                }).catch(() => {
                    // If batch fails, try sending individually as fallback
                    logsToSend.forEach(log => {
                        fetch('/api/frontend_log', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(log)
                        }).catch(() => {});
                    });
                }).finally(() => {
                    this.isSendingBatch = false;
                });
                return;
            }
        } catch (e) {
            // Silently ignore logging errors
        }
        
        this.isSendingBatch = false;
    }
}

// Create global logger instance
window.logger = new Logger();

// Expose debug toggle for console
window.enableDebug = () => window.logger.setDebugMode(true);
window.disableDebug = () => window.logger.setDebugMode(false);

// Log initialization
if (window.logger.debugMode) {
    console.log('%cLogger initialized. Commands available:', 'color: #4caf50; font-weight: bold;');
    console.log('  enableDebug()  - Enable debug logging');
    console.log('  disableDebug() - Disable debug logging');
}

