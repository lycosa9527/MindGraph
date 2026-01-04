/**
 * Admin Log Viewer
 * =================
 * 
 * Real-time log streaming and viewing for admin panel.
 * 
 * Features:
 * - Real-time log streaming via Server-Sent Events (SSE)
 * - Log level filtering (DEBUG, INFO, WARNING, ERROR, CRITICAL)
 * - Search functionality
 * - Auto-scroll with pause/resume
 * - Color-coded log levels
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class AdminLogViewer {
    constructor() {
        this.eventSource = null;
        this.autoScroll = true;
        this.logBuffer = [];
        this.maxBufferSize = 1000;
        this.currentSource = 'app';
        this.filterLevel = 'ALL';
        this.searchQuery = '';
        
        this.logContainer = null;
        this.initialized = false;
    }
    
    init() {
        if (this.initialized) return;
        
        this.logContainer = document.getElementById('log-viewer-content');
        
        if (!this.logContainer) {
            console.error('Log container not found');
            return;
        }
        
        this.initialized = true;
        this.loadInitialLogs();
    }
    
    async loadInitialLogs() {
        try {
            const response = await auth.fetch(
                `/api/auth/admin/logs/tail?source=${this.currentSource}&lines=50`
            );
            const logs = await response.json();
            
            this.logBuffer = logs;
            this.renderLogs();
            
        } catch (error) {
            console.error('Failed to load initial logs:', error);
            this.appendLog({
                level: 'ERROR',
                message: 'Failed to load initial logs: ' + error.message,
                timestamp: new Date().toISOString(),
                source: 'viewer'
            });
        }
    }
    
    startStreaming() {
        this.stopStreaming();
        
        const url = `/api/auth/admin/logs/stream?source=${this.currentSource}&follow=true&max_lines=0`;
        
        try {
            this.eventSource = new EventSource(url);
            
            this.eventSource.onmessage = (event) => {
                try {
                    const logEntry = JSON.parse(event.data);
                    this.appendLog(logEntry);
                } catch (e) {
                    console.error('Failed to parse log entry:', e);
                }
            };
            
            this.eventSource.onerror = (error) => {
                console.error('EventSource error:', error);
                this.stopStreaming();
                
                this.appendLog({
                    level: 'ERROR',
                    message: 'Log stream disconnected. Click "Start Stream" to reconnect.',
                    timestamp: new Date().toISOString(),
                    source: 'viewer'
                });
            };
            
            this.updateStreamButton(true);
            
        } catch (error) {
            console.error('Failed to start streaming:', error);
            this.appendLog({
                level: 'ERROR',
                message: 'Failed to start streaming: ' + error.message,
                timestamp: new Date().toISOString(),
                source: 'viewer'
            });
        }
    }
    
    stopStreaming() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
        
        this.updateStreamButton(false);
    }
    
    updateStreamButton(streaming) {
        const btn = document.getElementById('stream-toggle-btn');
        if (btn) {
            if (streaming) {
                btn.textContent = '⏸ Pause Stream';
                btn.classList.remove('btn-success');
                btn.classList.add('btn-warning');
            } else {
                btn.textContent = '▶ Start Stream';
                btn.classList.remove('btn-warning');
                btn.classList.add('btn-success');
            }
        }
    }
    
    appendLog(entry) {
        // Add to buffer
        this.logBuffer.push(entry);
        
        // Trim buffer if too large
        if (this.logBuffer.length > this.maxBufferSize) {
            this.logBuffer.shift();
        }
        
        // Apply filters
        if (!this.shouldShowLog(entry)) {
            return;
        }
        
        // Create log element
        const logLine = this.createLogElement(entry);
        
        // Append to container
        if (this.logContainer) {
            this.logContainer.appendChild(logLine);
            
            // Auto-scroll if enabled
            if (this.autoScroll) {
                this.logContainer.scrollTop = this.logContainer.scrollHeight;
            }
            
            // Trim DOM if too many elements
            while (this.logContainer.children.length > this.maxBufferSize) {
                this.logContainer.removeChild(this.logContainer.firstChild);
            }
        }
    }
    
    shouldShowLog(entry) {
        // Filter by level
        if (this.filterLevel !== 'ALL') {
            if (entry.level !== this.filterLevel) {
                return false;
            }
        }
        
        // Filter by search query
        if (this.searchQuery) {
            const query = this.searchQuery.toLowerCase();
            const message = (entry.message || '').toLowerCase();
            const raw = (entry.raw || '').toLowerCase();
            
            if (!message.includes(query) && !raw.includes(query)) {
                return false;
            }
        }
        
        return true;
    }
    
    createLogElement(entry) {
        const div = document.createElement('div');
        div.className = 'log-line';
        
        // Add level-specific class for coloring
        const level = entry.level || 'INFO';
        div.classList.add('log-' + level.toLowerCase());
        
        // Format timestamp
        const timestamp = entry.timestamp ? 
            new Date(entry.timestamp).toLocaleTimeString() : 
            new Date().toLocaleTimeString();
        
        // Build log line HTML
        div.innerHTML = `
            <span class="log-timestamp">[${timestamp}]</span>
            <span class="log-level log-level-${level.toLowerCase()}">${level}</span>
            <span class="log-module">${entry.module || entry.source || 'app'}</span>
            <span class="log-message">${this.escapeHtml(entry.message || entry.raw || '')}</span>
        `;
        
        return div;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    renderLogs() {
        if (!this.logContainer) return;
        
        // Clear container
        this.logContainer.innerHTML = '';
        
        // Render filtered logs
        for (const entry of this.logBuffer) {
            if (this.shouldShowLog(entry)) {
                const logLine = this.createLogElement(entry);
                this.logContainer.appendChild(logLine);
            }
        }
        
        // Auto-scroll to bottom
        if (this.autoScroll) {
            this.logContainer.scrollTop = this.logContainer.scrollHeight;
        }
    }
    
    clearLogs() {
        this.logBuffer = [];
        if (this.logContainer) {
            this.logContainer.innerHTML = '';
        }
    }
    
    setSource(source) {
        this.currentSource = source;
        this.clearLogs();
        
        const wasStreaming = this.eventSource !== null;
        if (wasStreaming) {
            this.stopStreaming();
        }
        
        this.loadInitialLogs();
        
        if (wasStreaming) {
            setTimeout(() => this.startStreaming(), 100);
        }
    }
    
    setFilterLevel(level) {
        this.filterLevel = level;
        this.renderLogs();
    }
    
    setSearchQuery(query) {
        this.searchQuery = query;
        this.renderLogs();
    }
    
    toggleAutoScroll() {
        this.autoScroll = !this.autoScroll;
        
        const btn = document.getElementById('autoscroll-toggle-btn');
        if (btn) {
            btn.textContent = this.autoScroll ? '📜 Auto-scroll: ON' : '📜 Auto-scroll: OFF';
        }
    }
    
    async downloadLogs() {
        try {
            const response = await auth.fetch(
                `/api/auth/admin/logs/tail?source=${this.currentSource}&lines=500`
            );
            const logs = await response.json();
            
            // Format logs as text
            const logText = logs.map(entry => {
                const timestamp = entry.timestamp || '';
                const level = (entry.level || 'INFO').padEnd(8);
                const module = (entry.module || entry.source || 'app').padEnd(15);
                const message = entry.message || entry.raw || '';
                
                return `[${timestamp}] ${level} | ${module} | ${message}`;
            }).join('\n');
            
            // Create download link
            const blob = new Blob([logText], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `${this.currentSource}-${new Date().toISOString().split('T')[0]}.log`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
        } catch (error) {
            console.error('Failed to download logs:', error);
            alert('Failed to download logs: ' + error.message);
        }
    }
    
    async searchLogs(query) {
        if (!query || query.trim() === '') {
            this.setSearchQuery('');
            return;
        }
        
        try {
            const response = await auth.fetch(
                `/api/auth/admin/logs/search?query=${encodeURIComponent(query)}&source=${this.currentSource}&max_results=200`
            );
            const results = await response.json();
            
            // Replace buffer with search results
            this.logBuffer = results;
            this.renderLogs();
            
            // Show count
            const countEl = document.getElementById('search-results-count');
            if (countEl) {
                countEl.textContent = `Found ${results.length} matching entries`;
                countEl.style.display = 'block';
            }
            
        } catch (error) {
            console.error('Failed to search logs:', error);
            alert('Failed to search logs: ' + error.message);
        }
    }
}

// Global instance
const logViewer = new AdminLogViewer();

