// Admin Panel - auth module
// Extracted from admin.html

async function checkAdminAuth() {
    const authenticated = await auth.isAuthenticated();
    if (!authenticated) {
        // Show overlay instead of redirecting
        document.getElementById('auth-required-overlay').style.display = 'flex';
        return false;
    }
    
    // Verify user is admin
    try {
        const response = await auth.fetch('/api/auth/me');
        const user = await response.json();
        
        // Check if user is admin by making a test admin API call
        const adminCheck = await auth.fetch('/api/auth/admin/stats');
        if (!adminCheck.ok) {
            // User is authenticated but not admin
            alert('⚠️ Admin access denied.\n\n您不是管理员，无法访问此页面。\nYou are not an administrator and cannot access this page.');
            window.location.href = '/editor';
            return false;
        }
        
        // Update admin name in header
        document.getElementById('adminName').textContent = user.name || 'Admin';
        
        return true;
    } catch (error) {
        console.error('Admin check failed:', error);
        document.getElementById('auth-required-overlay').style.display = 'flex';
        return false;
    }
}

function logout() {
    // Show confirmation message in current language only
    let confirmMessage;
    if (currentLang === 'zh') {
        confirmMessage = '确定登出？';
    } else if (currentLang === 'az') {
        confirmMessage = 'Çıxış etmək istəyirsiniz?';
    } else {
        confirmMessage = 'Are you sure to logout?';
    }
    
    if (confirm(confirmMessage)) {
        auth.logout();
    }
}

// Log Viewer Integration Functions

