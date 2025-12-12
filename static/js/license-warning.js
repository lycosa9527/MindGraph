/**
 * License Warning Script
 * Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
 * Proprietary License - All use without explicit permission is prohibited.
 * 
 * Displays copyright notice immediately on page load to ensure proper attribution and license compliance.
 */

(function() {
    'use strict';
    
    // Display copyright notice in console
    const copyrightNotice = `
%cMindGraph - Enterprise-Grade AI Diagram Generation Platform
Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved

PROPRIETARY LICENSE - All use without explicit permission is prohibited.

This software is NOT open source. Unauthorized use, copying, modification, 
distribution, or execution is strictly prohibited by law.

For licensing inquiries, please contact:
- GitHub: lycosa9527
- Company: 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
    `;
    
    console.log(copyrightNotice, 'color: #667eea; font-weight: bold; font-size: 12px;');
    
    // Optional: Display a subtle notice in the page (can be removed if not desired)
    // This creates a small, unobtrusive notice that appears briefly
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', displayNotice);
    } else {
        displayNotice();
    }
    
    function displayNotice() {
        // Only show notice once per session
        if (sessionStorage.getItem('license-notice-shown')) {
            return;
        }
        
        // Create a subtle notice element
        const notice = document.createElement('div');
        notice.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: rgba(102, 126, 234, 0.95);
            color: white;
            padding: 12px 20px;
            border-radius: 8px;
            font-size: 12px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
            z-index: 10000;
            max-width: 300px;
            opacity: 0;
            transform: translateY(20px);
            transition: opacity 0.3s ease, transform 0.3s ease;
            pointer-events: none;
        `;
        notice.textContent = 'MindGraph © 2024-2025 北京思源智教科技有限公司';
        document.body.appendChild(notice);
        
        // Animate in
        setTimeout(() => {
            notice.style.opacity = '1';
            notice.style.transform = 'translateY(0)';
        }, 100);
        
        // Remove after 3 seconds
        setTimeout(() => {
            notice.style.opacity = '0';
            notice.style.transform = 'translateY(20px)';
            setTimeout(() => {
                if (notice.parentNode) {
                    notice.parentNode.removeChild(notice);
                }
            }, 300);
        }, 3000);
        
        // Mark as shown for this session
        sessionStorage.setItem('license-notice-shown', 'true');
    }
})();

