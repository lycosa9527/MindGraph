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
     */
    async isAuthenticated() {
        const token = this.getToken();
        if (!token) return false;

        // Verify token by calling /me endpoint
        // This works for all auth modes (standard, enterprise, demo)
        try {
            const response = await this.fetch(`${this.apiBase}/me`);
            return response.ok;
        } catch {
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
     * Make authenticated API call
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

        return fetch(url, {
            ...options,
            headers
        });
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

