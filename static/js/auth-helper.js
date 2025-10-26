/**
 * Authentication Helper for MindGraph
 * Author: lycosa9527
 * Made by: MindSpring Team
 * 
 * Handles JWT token management, authentication state, and API calls.
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
                const mode = this.getMode();
                redirectUrl = (mode === 'demo') ? '/demo' : '/auth';
            }
            window.location.href = redirectUrl;
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
}

// Global instance (available both as 'auth' and 'window.auth')
const auth = new AuthHelper();
window.auth = auth;

// Auto-redirect to appropriate auth page on 401
window.addEventListener('unhandledrejection', event => {
    if (event.reason && event.reason.status === 401) {
        const mode = auth.getMode();
        auth.clearAuth();
        window.location.href = (mode === 'demo') ? '/demo' : '/auth';
    }
});

