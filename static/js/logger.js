/**
 * Centralized Console Logger for MindGraph
 * 
 * Provides structured logging with levels, controlled by debug mode.
 * Clean and professional logging that respects user preferences.
 * 
 * @author lycosa9527
 * @made_by MindSpring Team
 */

class Logger {
    constructor() {
        // Check if debug mode is enabled via URL parameter or localStorage
        const urlParams = new URLSearchParams(window.location.search);
        const urlDebug = urlParams.get('debug');
        const storedDebug = localStorage.getItem('mindgraph_debug');
        
        // Debug mode enabled if: ?debug=1 in URL or localStorage is 'true'
        this.debugMode = urlDebug === '1' || storedDebug === 'true';
        
        // Log levels (only show if debug is enabled)
        this.levels = {
            DEBUG: 0,
            INFO: 1,
            WARN: 2,
            ERROR: 3
        };
        
        // Current minimum level to display
        this.minLevel = this.debugMode ? this.levels.DEBUG : this.levels.WARN;
        
        // Show startup message if debug mode enabled
        if (this.debugMode) {
            console.log('%c[MindGraph] Debug mode ENABLED', 'color: #4caf50; font-weight: bold;');
            console.log('[MindGraph] To disable: localStorage.removeItem("mindgraph_debug") and reload');
        }
        
        // Track last log to avoid duplicates
        this.lastLog = null;
        this.lastLogCount = 0;
    }
    
    /**
     * Enable or disable debug mode
     */
    setDebugMode(enabled) {
        this.debugMode = enabled;
        this.minLevel = enabled ? this.levels.DEBUG : this.levels.WARN;
        localStorage.setItem('mindgraph_debug', enabled ? 'true' : 'false');
        
        if (enabled) {
            console.log('%c[MindGraph] Debug mode ENABLED', 'color: #4caf50; font-weight: bold;');
        } else {
            console.log('%c[MindGraph] Debug mode DISABLED', 'color: #f44336; font-weight: bold;');
        }
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
        
        return { prefix, color, message, data };
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
        
        // Send to backend in debug mode
        if (this.debugMode) {
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
        
        // Send to backend in debug mode
        if (this.debugMode) {
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
            console.error(`%c${prefix} | ${msg}`, `color: ${color}; font-weight: bold;`, e);
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
     * Send logs to backend Python terminal
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
                    dataStr = JSON.stringify(data);
                } else {
                    dataStr = data.toString();
                }
            }
            
            // Create full message with component and data
            let fullMessage = `[${component}] ${message}`;
            if (dataStr) {
                fullMessage += ` | ${dataStr}`;
            }
            
            fetch('/api/frontend_log', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    level: level,
                    message: fullMessage,
                    source: component
                })
            }).catch(() => {}); // Fail silently - don't break frontend
        } catch (e) {
            // Silently ignore logging errors
        }
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

