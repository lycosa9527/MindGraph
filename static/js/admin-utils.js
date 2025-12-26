// Admin Panel - Utilities Module
// Cache detection and global utilities

// Cache detection and refresh mechanism
// Note: window.MINDGRAPH_VERSION is set in admin.html
(function() {
    const CURRENT_VERSION = window.MINDGRAPH_VERSION || 'unknown';
    const VERSION_STORAGE_KEY = 'mindgraph_app_version';
    const CACHE_DETECTED_KEY = 'mindgraph_cache_detected';
    
    // Helper function to safely access localStorage
    const safeLocalStorage = {
        getItem: (key) => {
            try {
                return localStorage.getItem(key);
            } catch (e) {
                return null;
            }
        },
        setItem: (key, value) => {
            try {
                localStorage.setItem(key, value);
                return true;
            } catch (e) {
                return false;
            }
        }
    };
    
    // Helper function to safely access sessionStorage
    const safeSessionStorage = {
        getItem: (key) => {
            try {
                return sessionStorage.getItem(key);
            } catch (e) {
                return null;
            }
        },
        setItem: (key, value) => {
            try {
                sessionStorage.setItem(key, value);
                return true;
            } catch (e) {
                return false;
            }
        },
        removeItem: (key) => {
            try {
                sessionStorage.removeItem(key);
            } catch (e) {
                // Ignore errors
            }
        }
    };
    
    // Get stored version
    const storedVersion = safeLocalStorage.getItem(VERSION_STORAGE_KEY);
    const cacheDetected = safeSessionStorage.getItem(CACHE_DETECTED_KEY);
    
    // Check if version changed (cache detected)
    if (storedVersion && storedVersion !== CURRENT_VERSION && !cacheDetected) {
        // Mark that we've detected cache for this session
        safeSessionStorage.setItem(CACHE_DETECTED_KEY, 'true');
        
        // Show cache warning notification
        const showCacheWarning = () => {
            const currentLang = localStorage.getItem('language') || 'zh';
            const isZh = currentLang === 'zh';
            
            const warningHtml = `
                <div id="cache-warning" style="
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    background: linear-gradient(135deg, #ff6b6b 0%, #ee5a6f 100%);
                    color: white;
                    padding: 20px 25px;
                    border-radius: 12px;
                    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
                    z-index: 10000;
                    max-width: 400px;
                    animation: slideIn 0.3s ease-out;
                ">
                    <style>
                        @keyframes slideIn {
                            from {
                                transform: translateX(100%);
                                opacity: 0;
                            }
                            to {
                                transform: translateX(0);
                                opacity: 1;
                            }
                        }
                        @keyframes slideOut {
                            from {
                                transform: translateX(0);
                                opacity: 1;
                            }
                            to {
                                transform: translateX(100%);
                                opacity: 0;
                            }
                        }
                    </style>
                    <div style="display: flex; align-items: flex-start; gap: 15px;">
                        <div style="flex: 1;">
                            <div style="font-weight: 600; font-size: 16px; margin-bottom: 8px;">
                                ${isZh ? '⚠️ 检测到旧版本缓存' : '⚠️ Old Cache Detected'}
                            </div>
                            <div style="font-size: 14px; opacity: 0.95; line-height: 1.5; margin-bottom: 12px;">
                                ${isZh 
                                    ? `应用已更新到版本 ${CURRENT_VERSION}，但您可能在使用旧版本缓存。请点击下方按钮刷新，或使用快捷键强制刷新页面以获得最新功能。`
                                    : `Application updated to version ${CURRENT_VERSION}, but you may be using cached files. Click the button below to refresh, or use keyboard shortcut to hard refresh and get the latest features.`
                                }
                            </div>
                            <div style="margin-bottom: 12px; padding: 10px; background: rgba(255, 255, 255, 0.15); border-radius: 6px; border-left: 3px solid rgba(255, 255, 255, 0.5);">
                                <div style="font-size: 13px; font-weight: 600; margin-bottom: 4px;">
                                    ${isZh ? '⌨️ 如何强制刷新：' : '⌨️ How to Hard Refresh:'}
                                </div>
                                <div style="font-size: 12px; opacity: 0.95; line-height: 1.6;">
                                    ${isZh 
                                        ? '• Windows/Linux: 按 <kbd style="background: rgba(255,255,255,0.3); padding: 2px 6px; border-radius: 3px; font-family: monospace;">Ctrl</kbd> + <kbd style="background: rgba(255,255,255,0.3); padding: 2px 6px; border-radius: 3px; font-family: monospace;">Shift</kbd> + <kbd style="background: rgba(255,255,255,0.3); padding: 2px 6px; border-radius: 3px; font-family: monospace;">R</kbd><br>• Mac: 按 <kbd style="background: rgba(255,255,255,0.3); padding: 2px 6px; border-radius: 3px; font-family: monospace;">Cmd</kbd> + <kbd style="background: rgba(255,255,255,0.3); padding: 2px 6px; border-radius: 3px; font-family: monospace;">Shift</kbd> + <kbd style="background: rgba(255,255,255,0.3); padding: 2px 6px; border-radius: 3px; font-family: monospace;">R</kbd>'
                                        : '• Windows/Linux: Press <kbd style="background: rgba(255,255,255,0.3); padding: 2px 6px; border-radius: 3px; font-family: monospace;">Ctrl</kbd> + <kbd style="background: rgba(255,255,255,0.3); padding: 2px 6px; border-radius: 3px; font-family: monospace;">Shift</kbd> + <kbd style="background: rgba(255,255,255,0.3); padding: 2px 6px; border-radius: 3px; font-family: monospace;">R</kbd><br>• Mac: Press <kbd style="background: rgba(255,255,255,0.3); padding: 2px 6px; border-radius: 3px; font-family: monospace;">Cmd</kbd> + <kbd style="background: rgba(255,255,255,0.3); padding: 2px 6px; border-radius: 3px; font-family: monospace;">Shift</kbd> + <kbd style="background: rgba(255,255,255,0.3); padding: 2px 6px; border-radius: 3px; font-family: monospace;">R</kbd>'
                                    }
                                </div>
                            </div>
                            <div style="display: flex; gap: 10px;">
                                <button id="cache-refresh-btn" style="
                                    background: white;
                                    color: #ff6b6b;
                                    border: none;
                                    padding: 8px 16px;
                                    border-radius: 6px;
                                    font-weight: 600;
                                    cursor: pointer;
                                    font-size: 14px;
                                    transition: all 0.2s;
                                " onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'">
                                    ${isZh ? '🔄 立即刷新' : '🔄 Refresh Now'}
                                </button>
                                <button id="cache-dismiss-btn" style="
                                    background: rgba(255, 255, 255, 0.2);
                                    color: white;
                                    border: 1px solid rgba(255, 255, 255, 0.3);
                                    padding: 8px 16px;
                                    border-radius: 6px;
                                    font-weight: 600;
                                    cursor: pointer;
                                    font-size: 14px;
                                    transition: all 0.2s;
                                " onmouseover="this.style.background='rgba(255, 255, 255, 0.3)'" onmouseout="this.style.background='rgba(255, 255, 255, 0.2)'">
                                    ${isZh ? '稍后' : 'Later'}
                                </button>
                            </div>
                        </div>
                        <button id="cache-close-btn" style="
                            background: rgba(255, 255, 255, 0.2);
                            border: none;
                            color: white;
                            width: 24px;
                            height: 24px;
                            border-radius: 50%;
                            cursor: pointer;
                            font-size: 18px;
                            line-height: 1;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            transition: all 0.2s;
                        " onmouseover="this.style.background='rgba(255, 255, 255, 0.3)'" onmouseout="this.style.background='rgba(255, 255, 255, 0.2)'">×</button>
                    </div>
                </div>
            `;
            
            document.body.insertAdjacentHTML('beforeend', warningHtml);
            
            // Refresh button - force reload (prevent multiple clicks)
            let isRefreshing = false;
            document.getElementById('cache-refresh-btn').addEventListener('click', () => {
                if (isRefreshing) return; // Prevent multiple clicks
                isRefreshing = true;
                safeLocalStorage.setItem(VERSION_STORAGE_KEY, CURRENT_VERSION);
                safeSessionStorage.removeItem(CACHE_DETECTED_KEY);
                // Use modern reload method with cache bypass
                window.location.reload();
            });
            
            // Dismiss button - hide for this session
            document.getElementById('cache-dismiss-btn').addEventListener('click', () => {
                document.getElementById('cache-warning').remove();
            });
            
            // Close button
            document.getElementById('cache-close-btn').addEventListener('click', () => {
                document.getElementById('cache-warning').remove();
            });
            
            // Auto-dismiss after 30 seconds
            setTimeout(() => {
                const warning = document.getElementById('cache-warning');
                if (warning) {
                    warning.style.animation = 'slideOut 0.3s ease-out';
                    warning.style.animationFillMode = 'forwards';
                    setTimeout(() => warning.remove(), 300);
                }
            }, 30000);
        };
        
        // Show warning after page loads
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', showCacheWarning);
        } else {
            showCacheWarning();
        }
    }
    
    // Update stored version (always, even if cache detection failed)
    safeLocalStorage.setItem(VERSION_STORAGE_KEY, CURRENT_VERSION);
})();

// Global state variables (shared across all admin modules)
let currentTab = 'dashboard';
let schools = [];
let users = [];
let currentLang = 'en'; // Default to English

// User pagination state
let usersCurrentPage = 1;
let usersPageSize = 50;
let usersTotalPages = 1;
let usersTotal = 0;

// Chart instance for trend charts
let trendChartInstance = null;

// Organization chart state
let currentOrgInfo = { name: null, id: null, period: 'week' };
let currentUserInfo = { name: null, id: null, period: 'week' };
let previousOrgInfo = { name: null, id: null }; // Store org info when viewing a user

// API keys list
let apiKeys = [];

// Announcement editor state (methods will be added in admin-announcement.js)
const announcementEditor = {};

// Real-time monitoring state
let realtimeEventSource = null;
let realtimeUsers = [];
let reconnectState = {
    attempts: 0,
    maxAttempts: 5,
    delay: 1000
};
let realtimeListenersAdded = false;

// ============================================================================
// Utility Functions
// ============================================================================

// Toggle language between English, Chinese, and Azerbaijani
function toggleLanguage() {
    const languages = ['en', 'zh', 'az'];
    const currentIndex = languages.indexOf(currentLang);
    const nextIndex = (currentIndex + 1) % languages.length;
    currentLang = languages[nextIndex];
    
    // Apply language to all elements
    applyCurrentLanguage();
    
    // Update school filter dropdown if it exists and has been populated
    if (schools && schools.length > 0 && typeof populateSchoolFilter === 'function') {
        populateSchoolFilter();
    }
    
    // Save language preference
    localStorage.setItem('adminLanguage', currentLang);
}

// Apply current language to all lang-* elements
function applyCurrentLanguage() {
    document.querySelectorAll('.lang-en, .lang-zh, .lang-az').forEach(el => {
        el.style.display = 'none';
    });
    
    if (currentLang === 'zh') {
        document.querySelectorAll('.lang-zh').forEach(el => el.style.display = 'inline');
    } else if (currentLang === 'az') {
        document.querySelectorAll('.lang-az').forEach(el => el.style.display = 'inline');
        // Fallback to English if Azerbaijani not available
        if (document.querySelectorAll('.lang-az').length === 0) {
            document.querySelectorAll('.lang-en').forEach(el => el.style.display = 'inline');
        }
    } else {
        document.querySelectorAll('.lang-en').forEach(el => el.style.display = 'inline');
    }
    
    // Update dropdown options that need dynamic translation
    // Update user filter dropdown "All Schools" option
    const userOrgFilter = document.getElementById('user-org-filter');
    if (userOrgFilter && userOrgFilter.firstElementChild) {
        const allSchoolsText = currentLang === 'zh' ? '全部学校' : 
                               currentLang === 'az' ? 'Bütün Məktəblər' : 
                               'All Schools';
        userOrgFilter.firstElementChild.textContent = allSchoolsText;
    }
}

// Initialize language on page load
function initLanguage() {
    const savedLang = localStorage.getItem('adminLanguage');
    if (savedLang && ['en', 'zh', 'az'].includes(savedLang)) {
        currentLang = savedLang;
    }
    applyCurrentLanguage();
}

// Tab switching
function switchTab(tab, buttonElement) {
    // Update tabs - remove active class from all tabs
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    
    // Add active class to the clicked button
    if (buttonElement) {
        buttonElement.classList.add('active');
    } else {
        // Fallback: find button by data-tab attribute
        const tabButton = document.querySelector(`.tab[data-tab="${tab}"]`);
        if (tabButton) {
            tabButton.classList.add('active');
        }
    }
    
    // Show the corresponding tab content
    const tabContent = document.getElementById(tab + '-tab');
    if (tabContent) {
        tabContent.classList.add('active');
    }
    currentTab = tab;

    // Load data based on tab
    if (tab === 'dashboard' && typeof loadDashboard === 'function') loadDashboard();
    if (tab === 'tokens' && typeof loadTokenStats === 'function') loadTokenStats();
    if (tab === 'schools' && typeof loadSchools === 'function') loadSchools();
    if (tab === 'users') {
        if (typeof loadUserFilters === 'function') loadUserFilters();
        if (typeof loadUsers === 'function') loadUsers();
    }
    if (tab === 'apikeys' && typeof loadAPIKeys === 'function') loadAPIKeys();
    if (tab === 'announcement' && typeof loadAnnouncementConfig === 'function') loadAnnouncementConfig();
}

// Show alert message
function showAlert(message, type = 'success') {
    const alert = document.getElementById('alert');
    if (alert) {
        alert.className = `alert alert-${type} show`;
        alert.textContent = message;
        setTimeout(() => alert.classList.remove('show'), 5000);
    }
}

// Format number with commas
function formatNumber(num) {
    if (num === null || num === undefined) return '0';
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

// Format chart label (abbreviate large numbers)
function formatChartLabel(value) {
    if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M';
    if (value >= 1000) return (value / 1000).toFixed(1) + 'K';
    return value.toString();
}

// Format token numbers with rounding up (for display)
function formatTokenNumber(num) {
    if (num === null || num === undefined || num === 0) return '0';
    
    // Round up to nearest significant digit
    if (num >= 1000000000) {
        // Billions - round up to nearest 100M
        const rounded = Math.ceil(num / 100000000) * 100000000;
        return (rounded / 1000000000).toFixed(1) + 'B';
    } else if (num >= 1000000) {
        // Millions - round up to nearest 100K
        const rounded = Math.ceil(num / 100000) * 100000;
        return (rounded / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
        // Thousands - round up to nearest 100
        const rounded = Math.ceil(num / 100) * 100;
        return (rounded / 1000).toFixed(1) + 'K';
    } else {
        // Less than 1000 - round up to nearest 10
        return Math.ceil(num / 10) * 10;
    }
}

// Mask phone number for display
function maskPhone(phone) {
    if (!phone || phone.length < 7) return phone;
    return phone.substring(0, 3) + '****' + phone.substring(phone.length - 4);
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Copy text to clipboard
function copyToClipboard(text, element) {
    navigator.clipboard.writeText(text).then(() => {
        if (element) {
            const originalText = element.textContent;
            element.textContent = 'Copied!';
            setTimeout(() => {
                element.textContent = originalText;
            }, 2000);
        }
        showAlert('Copied to clipboard', 'success');
    }).catch(err => {
        console.error('Failed to copy:', err);
        showAlert('Failed to copy', 'error');
    });
}

// Modal functions
function openModal(id) {
    const modal = document.getElementById(id);
    if (modal) {
        modal.classList.add('show');
    }
}

function closeModal(id) {
    const modal = document.getElementById(id);
    if (modal) {
        modal.classList.remove('show');
    }
    // Destroy chart when closing trend modal
    if (id === 'trend-chart-modal' && trendChartInstance) {
        trendChartInstance.destroy();
        trendChartInstance = null;
        // Hide organization and user token stats
        const orgStatsContainer = document.getElementById('org-token-stats-cards');
        const userStatsContainer = document.getElementById('user-token-stats-cards');
        if (orgStatsContainer) {
            orgStatsContainer.style.display = 'none';
        }
        if (userStatsContainer) {
            userStatsContainer.style.display = 'none';
        }
        // Show org tabs again
        const orgTabs = document.querySelector('.modal-tabs');
        if (orgTabs) orgTabs.style.display = 'flex';
        // Reset to chart tab
        if (typeof switchOrgModalTab === 'function') {
            switchOrgModalTab('chart');
        }
        // Hide back button
        const backBtn = document.getElementById('back-to-org-btn');
        if (backBtn) backBtn.style.display = 'none';
        // Clear current info
        if (typeof currentOrgInfo !== 'undefined') {
            currentOrgInfo.name = null;
            currentOrgInfo.id = null;
        }
        if (typeof currentUserInfo !== 'undefined') {
            currentUserInfo.name = null;
            currentUserInfo.id = null;
        }
        if (typeof previousOrgInfo !== 'undefined') {
            previousOrgInfo.name = null;
            previousOrgInfo.id = null;
        }
    }
}

// Format time ago (for real-time monitoring)
function formatTimeAgo(date) {
    if (!date) return '';
    const now = new Date();
    const diff = now - new Date(date);
    const seconds = Math.floor(diff / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    
    if (days > 0) return `${days}d ago`;
    if (hours > 0) return `${hours}h ago`;
    if (minutes > 0) return `${minutes}m ago`;
    return `${seconds}s ago`;
}
