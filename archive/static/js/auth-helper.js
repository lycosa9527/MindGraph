/**
 * Authentication Helper for MindGraph
 * 
 * Handles JWT token management, authentication state, and API calls.
 * 
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * All Rights Reserved
 * 
 * Proprietary License - All use without explicit permission is prohibited.
 * Unauthorized use, copying, modification, distribution, or execution is strictly prohibited.
 * 
 * @author WANG CUNCHI
 */

class AuthHelper {
    constructor() {
        this.tokenKey = 'auth_token';
        this.userKey = 'auth_user';
        this.modeKey = 'auth_mode';
        this.apiBase = '/api/auth';
    }

    /**
     * Store authentication token
     */
    setToken(token) {
        localStorage.setItem(this.tokenKey, token);
    }

    /**
     * Get stored token
     */
    getToken() {
        return localStorage.getItem(this.tokenKey);
    }

    /**
     * Store user data
     */
    setUser(user) {
        localStorage.setItem(this.userKey, JSON.stringify(user));
    }

    /**
     * Store authentication mode (demo/standard)
     */
    setMode(mode) {
        localStorage.setItem(this.modeKey, mode);
    }

    /**
     * Get authentication mode
     */
    getMode() {
        return localStorage.getItem(this.modeKey) || 'standard';
    }

    /**
     * Get stored user data
     */
    getUser() {
        const user = localStorage.getItem(this.userKey);
        return user ? JSON.parse(user) : null;
    }

    /**
     * Clear authentication data
     */
    clearAuth() {
        localStorage.removeItem(this.tokenKey);
        localStorage.removeItem(this.userKey);
        localStorage.removeItem(this.modeKey);
    }

    /**
     * Check if user is authenticated
     * 
     * Note: Authentication can be done via:
     * 1. httponly cookie (server-side JWT) - JavaScript cannot read this
     * 2. localStorage token (for API calls with Authorization header)
     * 
     * We always call /me endpoint to verify because the httponly cookie
     * will be sent automatically with the request, even if localStorage is empty.
     */
    async isAuthenticated() {
        // Always verify by calling /me endpoint
        // The httponly cookie will be sent automatically with the fetch request
        // This works for all auth modes (standard, enterprise, demo, bayi)
        try {
            const response = await fetch(`${this.apiBase}/me`, {
                credentials: 'same-origin'  // Ensure cookies are sent
            });
            const isAuth = response.ok;
            
            // Start session monitoring if authenticated
            if (isAuth) {
                this.startSessionMonitoring();
            } else {
                this.stopSessionMonitoring();
            }
            
            return isAuth;
        } catch {
            this.stopSessionMonitoring();
            return false;
        }
    }

    /**
     * Detect authentication mode
     */
    async detectMode() {
        try {
            const response = await fetch(`${this.apiBase}/mode`);
            const data = await response.json();
            return data.mode || 'standard';
        } catch {
            return 'standard';
        }
    }

    /**
     * Attempt to refresh authentication token
     * 
     * Note: With httponly cookies, JavaScript cannot directly refresh tokens.
     * This method checks if the session is still valid by calling /me endpoint.
     * If the session is valid, the server automatically refreshes it server-side.
     * If expired, the user will need to re-login (expected behavior).
     * 
     * @returns {Promise<boolean>} True if session is still valid, false if expired
     */
    async refreshToken() {
        // Prevent multiple simultaneous refresh attempts
        if (this._refreshing) {
            // Wait for existing refresh to complete
            return new Promise((resolve) => {
                const checkInterval = setInterval(() => {
                    if (!this._refreshing) {
                        clearInterval(checkInterval);
                        resolve(this._refreshSuccess);
                    }
                }, 100);
            });
        }
        
        this._refreshing = true;
        this._refreshSuccess = false;
        
        try {
            // Attempt to refresh by calling /me endpoint with credentials
            // This will refresh the httponly cookie session if still valid
            const response = await fetch(`${this.apiBase}/me`, {
                method: 'GET',
                credentials: 'same-origin'
            });
            
            if (response.ok) {
                // Session refreshed successfully
                const data = await response.json();
                if (data.user) {
                    this.setUser(data.user);
                }
                this._refreshSuccess = true;
                return true;
            }
            
            // Refresh failed - session expired
            this._refreshSuccess = false;
            return false;
        } catch (e) {
            console.debug('Token refresh failed:', e);
            this._refreshSuccess = false;
            return false;
        } finally {
            this._refreshing = false;
        }
    }

    /**
     * Check if token should be refreshed proactively
     * @returns {Promise<boolean>} True if token should be refreshed
     */
    async _shouldRefreshToken() {
        // For httponly cookie-based auth, we can't check expiration directly
        // Instead, check if we've refreshed recently (within last 5 minutes)
        const lastRefresh = sessionStorage.getItem('auth_last_refresh');
        if (lastRefresh) {
            const timeSinceRefresh = Date.now() - parseInt(lastRefresh, 10);
            const fiveMinutes = 5 * 60 * 1000;
            if (timeSinceRefresh < fiveMinutes) {
                return false; // Recently refreshed, no need to refresh again
            }
        }
        return true;
    }

    /**
     * Make authenticated API call with automatic token refresh on 401
     */
    async fetch(url, options = {}) {
        const token = this.getToken();
        
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };

        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        let response = await fetch(url, {
            ...options,
            headers,
            credentials: 'same-origin'
        });

        // Handle 401 errors with automatic token refresh
        if (response.status === 401) {
            // Check if we should attempt refresh (avoid loops)
            const shouldRetry = options._retryAttempt !== true;
            
            if (shouldRetry) {
                // Attempt to refresh token
                const refreshed = await this.refreshToken();
                
                if (refreshed) {
                    // Retry original request with refreshed token
                    const retryToken = this.getToken();
                    if (retryToken) {
                        headers['Authorization'] = `Bearer ${retryToken}`;
                    }
                    
                    // Mark retry attempt to prevent infinite loops
                    const retryOptions = {
                        ...options,
                        _retryAttempt: true
                    };
                    
                    response = await fetch(url, {
                        ...retryOptions,
                        headers,
                        credentials: 'same-origin'
                    });
                    
                    // If retry succeeded, update last refresh time
                    if (response.ok) {
                        sessionStorage.setItem('auth_last_refresh', Date.now().toString());
                    }
                }
            }
        }

        return response;
    }

    /**
     * Logout user
     */
    async logout() {
        const mode = this.getMode();
        
        try {
            await this.fetch(`${this.apiBase}/logout`, { method: 'POST' });
        } catch (e) {
            console.error('Logout error:', e);
        }
        
        this.clearAuth();
        
        // Stop session monitoring
        this.stopSessionMonitoring();
        
        // Redirect based on mode: demo users go back to demo page
        if (mode === 'demo') {
            window.location.href = '/demo';
        } else if (mode === 'bayi') {
            // Bayi mode: redirect to root (which will redirect to editor)
            // Users need to authenticate via /loginByXz
            window.location.href = '/';
        } else {
            window.location.href = '/auth';
        }
    }

    /**
     * Start session monitoring (polling for session status)
     */
    startSessionMonitoring() {
        // Stop any existing monitoring
        this.stopSessionMonitoring();
        
        // Poll every 45 seconds (configurable)
        const pollInterval = 45000; // 45 seconds
        
        this._sessionMonitorInterval = setInterval(async () => {
            // Only check if page is visible
            if (document.visibilityState === 'visible') {
                await this.checkSessionStatus();
            }
        }, pollInterval);
        
        // Also check immediately
        this.checkSessionStatus();
    }

    /**
     * Stop session monitoring
     */
    stopSessionMonitoring() {
        if (this._sessionMonitorInterval) {
            clearInterval(this._sessionMonitorInterval);
            this._sessionMonitorInterval = null;
        }
    }

    /**
     * Check session status and handle invalidation
     */
    async checkSessionStatus() {
        try {
            const response = await this.fetch(`${this.apiBase}/session-status`, {
                method: 'GET',
                credentials: 'same-origin'
            });
            
            if (response.status === 401) {
                // Session invalidated - 401 means authentication failed
                this.handleSessionInvalidation({
                    status: 'invalidated',
                    message: 'Your session was invalidated because you logged in from another location'
                });
                return;
            }
            
            if (!response.ok) {
                return; // Ignore other errors, will check again next interval
            }
            
            const data = await response.json();
            
            if (data.status === 'invalidated') {
                // Session was invalidated - show notification and logout
                this.handleSessionInvalidation(data);
            }
        } catch (e) {
            // Ignore errors, will check again next interval
            console.debug('Session status check failed:', e);
        }
    }

    /**
     * Handle session invalidation notification
     */
    handleSessionInvalidation(data) {
        // Stop monitoring
        this.stopSessionMonitoring();
        
        // Show notification
        const message = data.message || 'Your account was logged in from another location. You have been logged out for security.';
        
        // Use existing notification system if available
        if (window.NotificationManager && window.NotificationManager.show) {
            window.NotificationManager.show(
                message,
                'warning',
                10000,
                () => this.logout()
            );
        } else if (window.languageManager && window.languageManager.getNotification) {
            // Try to get translated message
            const translatedMsg = window.languageManager.getNotification('sessionInvalidated') || message;
            alert(translatedMsg);
            this.logout();
        } else {
            // Fallback: show alert
            if (confirm(message + '\n\nClick OK to return to login page.')) {
                this.logout();
            } else {
                // User clicked cancel, but still logout after delay
                setTimeout(() => this.logout(), 5000);
            }
        }
    }

    /**
     * Require authentication (redirect if not authenticated)
     */
    async requireAuth(redirectUrl = null) {
        const authenticated = await this.isAuthenticated();
        if (!authenticated) {
            // If no redirect URL specified, use appropriate page based on mode
            if (!redirectUrl) {
                const mode = await this.detectMode();
                if (mode === 'demo') {
                    redirectUrl = '/demo';
                } else if (mode === 'bayi') {
                    // Bayi mode: users must authenticate via /loginByXz
                    // Don't redirect, just return false (let the page handle it)
                    console.warn('Bayi mode: Authentication required via /loginByXz endpoint');
                    return false;
                } else {
                    redirectUrl = '/auth';
                }
            }
            if (redirectUrl) {
                window.location.href = redirectUrl;
            }
            return false;
        }
        return true;
    }

    /**
     * Get current user info
     */
    async getCurrentUser() {
        try {
            const response = await this.fetch(`${this.apiBase}/me`);
            if (response.ok) {
                const user = await response.json();
                this.setUser(user);
                return user;
            }
        } catch (e) {
            console.error('Get user error:', e);
        }
        return null;
    }

    /**
     * Hard refresh the page to clear browser cache
     * 
     * This forces the browser to fetch all resources fresh from the server.
     * Useful when users experience issues due to cached outdated code.
     */
    hardRefresh() {
        // Clear service worker cache if present
        if ('caches' in window) {
            caches.keys().then(names => {
                names.forEach(name => caches.delete(name));
            });
        }
        
        // Clear cache detection session flag so notification can show again after refresh
        try {
            sessionStorage.removeItem('mindgraph_cache_detected');
        } catch (e) {
            // Ignore errors
        }
        
        // Force reload from server, bypassing cache
        // Modern browsers handle cache bypass automatically with reload()
        window.location.reload();
    }

    /**
     * Check if app version has changed and trigger refresh if needed
     * 
     * Compares current app version with server version.
     * If different, prompts user to refresh or auto-refreshes.
     * 
     * NOTE: This works alongside the template-based cache detection system.
     * The template system handles initial page load detection, while this handles
     * periodic checks for long-running sessions. Both use the same localStorage key
     * to avoid duplicate notifications.
     * 
     * @param {boolean} autoRefresh - If true, refresh without prompting
     * @returns {Promise<boolean>} - True if version changed
     */
    async checkVersionAndRefresh(autoRefresh = false) {
        try {
            // Get current version from page (set during template render)
            const currentVersion = window.MINDGRAPH_VERSION;
            if (!currentVersion) {
                return false;
            }
            
            // Check if template-based cache detection already showed notification this session
            // This prevents duplicate notifications when both systems detect the same version change
            try {
                const cacheDetected = sessionStorage.getItem('mindgraph_cache_detected');
                if (cacheDetected === 'true') {
                    // Template system already handled this, skip to avoid duplicate
                    return false;
                }
            } catch (e) {
                // Ignore errors
            }
            
            // Fetch latest version from server
            const response = await fetch('/health');
            if (!response.ok) {
                return false;
            }
            
            const data = await response.json();
            const serverVersion = data.version;
            
            if (serverVersion && serverVersion !== currentVersion) {
                console.log(`Version changed: ${currentVersion} -> ${serverVersion}`);
                
                // Update localStorage version (same key as template system uses)
                try {
                    localStorage.setItem('mindgraph_app_version', serverVersion);
                } catch (e) {
                    // Ignore errors
                }
                
                if (autoRefresh) {
                    this.hardRefresh();
                    return true;
                }
                
                // Mark that we've detected cache for this session (same flag as template system)
                try {
                    sessionStorage.setItem('mindgraph_cache_detected', 'true');
                } catch (e) {
                    // Ignore errors
                }
                
                // Show notification to user (with translation support)
                // Get language preference (check languageManager first, then localStorage)
                const currentLang = window.languageManager?.getCurrentLanguage?.() 
                    || localStorage.getItem('language') 
                    || 'zh';
                const isZh = currentLang === 'zh';
                
                const notifMessage = window.languageManager?.getNotification('newVersionAvailable', serverVersion) 
                    || (isZh 
                        ? `新版本已发布 (${serverVersion})。点击此处刷新。`
                        : `New version available (${serverVersion}). Click here to refresh.`);
                const confirmMessage = window.languageManager?.getNotification('newVersionConfirm', serverVersion)
                    || (isZh 
                        ? `新版本 (${serverVersion}) 已发布，是否立即刷新？`
                        : `A new version (${serverVersion}) is available. Refresh now?`);
                
                if (window.NotificationManager && window.NotificationManager.show) {
                    window.NotificationManager.show(
                        notifMessage,
                        'info',
                        10000,
                        () => this.hardRefresh()
                    );
                } else {
                    // Fallback: confirm dialog
                    if (confirm(confirmMessage)) {
                        this.hardRefresh();
                    }
                }
                return true;
            }
            
            return false;
        } catch (e) {
            console.error('Version check failed:', e);
            return false;
        }
    }
}

// Global instance (available both as 'auth' and 'window.auth')
const auth = new AuthHelper();
window.auth = auth;

// Expose hardRefresh globally for easy access
window.hardRefresh = () => auth.hardRefresh();

// Auto-redirect to appropriate auth page on 401
window.addEventListener('unhandledrejection', async event => {
    if (event.reason && event.reason.status === 401) {
        const mode = await auth.detectMode();
        auth.clearAuth();
        if (mode === 'demo') {
            window.location.href = '/demo';
        } else if (mode === 'bayi') {
            // Bayi mode: don't auto-redirect, let user authenticate via /loginByXz
            console.warn('Bayi mode: 401 error - user needs to authenticate via /loginByXz');
        } else {
            window.location.href = '/auth';
        }
    }
});

// Check for version updates when page becomes visible after being hidden
// This helps users get the latest version when they switch back to the app
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
        // Small delay to avoid checking immediately on every tab switch
        setTimeout(() => {
            auth.checkVersionAndRefresh(false);
        }, 1000);
    }
});

// Check for updates periodically (every 5 minutes) for long-running sessions
setInterval(() => {
    // Only check if page is visible
    if (document.visibilityState === 'visible') {
        auth.checkVersionAndRefresh(false);
    }
}, 5 * 60 * 1000);

