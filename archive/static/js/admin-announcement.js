// Admin Panel - announcement module
// Extracted from admin.html

async function loadAnnouncementConfig() {
    const loading = document.getElementById('announcement-loading');
    const form = document.getElementById('announcement-form');
    
    loading.style.display = 'block';
    form.style.display = 'none';
    
    try {
        const response = await fetch('/api/admin/update-notification', {
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error('加载公告配置失败');
        }
        
        const data = await response.json();
        
        // Populate form fields
        document.getElementById('announcement-enabled').checked = data.enabled;
        document.getElementById('announcement-version').value = data.version || '';
        document.getElementById('announcement-title').value = data.title || '';
        document.getElementById('announcement-message').innerHTML = data.message || '';
        
        loading.style.display = 'none';
        form.style.display = 'block';
        
    } catch (error) {
        console.error('Failed to load announcement config:', error);
        const errorMsg = currentLang === 'zh' ? '加载公告配置失败: ' : currentLang === 'az' ? 'Elan konfiqurasiyasını yükləmək mümkün olmadı: ' : 'Failed to load announcement config: ';
        showAlert(errorMsg + error.message, 'error');
        loading.style.display = 'none';
    }
}

// Preview announcement modal

function previewAnnouncement() {
    const title = document.getElementById('announcement-title').value.trim() || '系统更新';
    const version = document.getElementById('announcement-version').value.trim();
    const message = document.getElementById('announcement-message').innerHTML.trim();
    
    // Create preview modal
    const previewOverlay = document.createElement('div');
    previewOverlay.id = 'announcement-preview-overlay';
    previewOverlay.innerHTML = `
        <style>
            #announcement-preview-overlay {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.7);
                backdrop-filter: blur(8px);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10000;
                animation: fadeIn 0.3s ease;
            }
            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }
            .preview-modal {
                position: relative;
                background: linear-gradient(145deg, #1e293b 0%, #0f172a 100%);
                border-radius: 20px;
                padding: 32px;
                max-width: 500px;
                width: 90%;
                max-height: 80vh;
                overflow-y: auto;
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5),
                            0 0 0 1px rgba(255, 255, 255, 0.1),
                            inset 0 1px 0 rgba(255, 255, 255, 0.1);
                animation: slideUp 0.3s ease;
            }
            @keyframes slideUp {
                from { transform: translateY(20px) scale(0.95); opacity: 0; }
                to { transform: translateY(0) scale(1); opacity: 1; }
            }
            .preview-badge {
                position: absolute;
                top: -12px;
                left: 50%;
                transform: translateX(-50%);
                background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
                color: white;
                padding: 4px 16px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: 600;
                box-shadow: 0 4px 12px rgba(245, 158, 11, 0.4);
            }
            .preview-close {
                position: absolute;
                top: 16px;
                right: 16px;
                width: 36px;
                height: 36px;
                border: none;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: all 0.2s;
            }
            .preview-close:hover {
                background: rgba(255, 255, 255, 0.2);
                transform: scale(1.05);
            }
            .preview-close svg {
                stroke: #94a3b8;
            }
            .preview-close:hover svg {
                stroke: #ffffff;
            }
            .preview-header {
                text-align: center;
                margin-bottom: 24px;
                padding-top: 8px;
            }
            .preview-icon {
                width: 64px;
                height: 64px;
                margin: 0 auto 16px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 16px;
                display: flex;
                align-items: center;
                justify-content: center;
                box-shadow: 0 8px 24px rgba(102, 126, 234, 0.3);
            }
            .preview-icon svg {
                stroke: white;
            }
            .preview-title {
                color: #ffffff;
                font-size: 24px;
                font-weight: 700;
                margin: 0 0 8px 0;
            }
            .preview-version {
                display: inline-block;
                background: rgba(102, 126, 234, 0.2);
                color: #a5b4fc;
                padding: 4px 14px;
                border-radius: 20px;
                font-size: 13px;
                font-weight: 500;
            }
            .preview-content {
                color: #cbd5e1;
                font-size: 15px;
                line-height: 1.7;
                margin-bottom: 24px;
            }
            .preview-content img {
                max-width: 100%;
                border-radius: 8px;
                margin: 12px 0;
            }
            .preview-content ul, .preview-content ol {
                padding-left: 24px;
                margin: 12px 0;
            }
            .preview-content li {
                margin-bottom: 6px;
            }
            .preview-content b, .preview-content strong {
                color: #ffffff;
            }
            .preview-footer {
                display: flex;
                justify-content: center;
            }
            .preview-dismiss-btn {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                padding: 12px 48px;
                border-radius: 10px;
                font-size: 15px;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s ease;
                box-shadow: 0 4px 16px rgba(102, 126, 234, 0.3);
            }
            .preview-dismiss-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 24px rgba(102, 126, 234, 0.4);
            }
        </style>
        <div class="preview-modal">
            <span class="preview-badge"><span class="lang-zh">预览模式</span><span class="lang-en">Preview Mode</span><span class="lang-az">Önizləmə Rejimi</span></span>
            <button class="preview-close" onclick="closeAnnouncementPreview()">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
            </button>
            <div class="preview-header">
                <div class="preview-icon">
                    <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
                        <path d="M2 17l10 5 10-5"></path>
                        <path d="M2 12l10 5 10-5"></path>
                    </svg>
                </div>
                <h2 class="preview-title">${escapeHtml(title)}</h2>
                ${version ? `<span class="preview-version"><span class="lang-zh">版本</span><span class="lang-en">Version</span><span class="lang-az">Versiya</span> ${escapeHtml(version)}</span>` : ''}
            </div>
            <div class="preview-content">
                ${message || '<p style="color:#64748b;text-align:center;"><span class="lang-zh">暂无内容</span><span class="lang-en">No content</span><span class="lang-az">Məzmun yoxdur</span></p>'}
            </div>
            <div class="preview-footer">
                <button class="preview-dismiss-btn" onclick="closeAnnouncementPreview()"><span class="lang-zh">关闭</span><span class="lang-en">Close</span><span class="lang-az">Bağla</span></button>
            </div>
        </div>
    `;
    
    document.body.appendChild(previewOverlay);
    
    // Close on overlay click
    previewOverlay.addEventListener('click', (e) => {
        if (e.target === previewOverlay) {
            closeAnnouncementPreview();
        }
    });
    
    // Close on Escape
    document.addEventListener('keydown', function escHandler(e) {
        if (e.key === 'Escape') {
            closeAnnouncementPreview();
            document.removeEventListener('keydown', escHandler);
        }
    });
}

function closeAnnouncementPreview() {
    const overlay = document.getElementById('announcement-preview-overlay');
    if (overlay) {
        overlay.style.animation = 'fadeIn 0.2s ease reverse';
        setTimeout(() => overlay.remove(), 200);
    }
}

// Initialize announcementEditor object with methods
// Note: announcementEditor is declared in admin-utils.js, we extend it here
if (typeof announcementEditor !== 'undefined') {
    // Rich text editor commands
    announcementEditor.execCommand = function(command, value = null) {
        const editor = document.getElementById('announcement-message');
        if (!editor) return;
        
        document.execCommand(command, false, value);
        editor.focus();
    };
    
    // Insert image handler
    announcementEditor.insertImage = function() {
        const input = document.getElementById('announcement-image-input');
        if (input) {
            input.click();
        }
    };
    
    // Handle image upload
    announcementEditor.handleImageUpload = function(input) {
        const file = input.files[0];
        if (!file) return;
        
        if (!file.type.startsWith('image/')) {
            const errorMsg = currentLang === 'zh' ? '请选择图片文件' : currentLang === 'az' ? 'Zəhmət olmasa şəkil faylı seçin' : 'Please select an image file';
            showAlert(errorMsg, 'error');
            return;
        }
        
        const reader = new FileReader();
        reader.onload = function(e) {
            const editor = document.getElementById('announcement-message');
            if (editor) {
                document.execCommand('insertImage', false, e.target.result);
            }
        };
        reader.readAsDataURL(file);
        
        // Reset input
        input.value = '';
    };
    
    // Toggle emoji picker
    announcementEditor.toggleEmojiPicker = function() {
        const picker = document.getElementById('emoji-picker');
        if (picker) {
            const isVisible = picker.style.display !== 'none';
            picker.style.display = isVisible ? 'none' : 'block';
        }
    };
    
    // Switch emoji tab
    announcementEditor.switchEmojiTab = function(tab) {
        // Update tab buttons
        document.querySelectorAll('.emoji-tab').forEach(btn => btn.classList.remove('active'));
        event.target.classList.add('active');
        
        // Show/hide emoji grids
        const grids = ['common', 'faces', 'gestures', 'objects', 'symbols'];
        grids.forEach(grid => {
            const gridEl = document.getElementById(`emoji-grid-${grid}`);
            if (gridEl) {
                gridEl.style.display = grid === tab ? 'grid' : 'none';
            }
        });
    };
    
    // Insert emoji into editor
    announcementEditor.insertEmoji = function(emoji) {
        const editor = document.getElementById('announcement-message');
        if (editor) {
            editor.focus();
            document.execCommand('insertText', false, emoji);
        }
        
        // Hide picker after insertion
        const picker = document.getElementById('emoji-picker');
        if (picker) {
            picker.style.display = 'none';
        }
    };
}

// Helper function

async function saveAnnouncementConfig() {
    const enabled = document.getElementById('announcement-enabled').checked;
    const version = document.getElementById('announcement-version').value.trim();
    const title = document.getElementById('announcement-title').value.trim();
    const message = document.getElementById('announcement-message').innerHTML.trim();
    
    // Validation only if enabled
    if (enabled) {
        if (!version) {
            const errorMsg = currentLang === 'zh' ? '请输入版本号' : currentLang === 'az' ? 'Zəhmət olmasa versiya nömrəsini daxil edin' : 'Please enter version number';
            showAlert(errorMsg, 'error');
            return;
        }
        
        if (!title) {
            const errorMsg = currentLang === 'zh' ? '请输入标题' : currentLang === 'az' ? 'Zəhmət olmasa başlıq daxil edin' : 'Please enter title';
            showAlert(errorMsg, 'error');
            return;
        }
    }
    
    try {
        const response = await fetch('/api/admin/update-notification', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                enabled: enabled,
                version: version,
                title: title,
                title_en: '',
                message: message,
                message_en: '',
                show_changelog: false,
                changelog_items: [],
                changelog_items_en: []
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || '保存失败');
        }
        
        if (enabled) {
            const successMsg = currentLang === 'zh' ? '公告已发布，用户登录时将看到此公告（每个版本只显示一次）' : currentLang === 'az' ? 'Elan yayımlandı, istifadəçilər giriş zamanı bu elanı görəcəklər (hər versiya üçün bir dəfə)' : 'Announcement published, users will see this announcement on login (once per version)';
            showAlert(successMsg, 'success');
        } else {
            const successMsg = currentLang === 'zh' ? '公告设置已保存（当前已关闭）' : currentLang === 'az' ? 'Elan parametrləri saxlanıldı (hazırda bağlıdır)' : 'Announcement settings saved (currently disabled)';
            showAlert(successMsg, 'success');
        }
        loadAnnouncementConfig(); // Reload to update status
        
    } catch (error) {
        console.error('Failed to save announcement:', error);
        const errorMsg = currentLang === 'zh' ? '保存失败: ' : currentLang === 'az' ? 'Saxlamaq mümkün olmadı: ' : 'Failed to save: ';
        showAlert(errorMsg + error.message, 'error');
    }
}

