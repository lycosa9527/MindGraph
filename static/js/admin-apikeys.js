// Admin Panel - apikeys module
// Extracted from admin.html

async function loadAPIKeys() {
    document.getElementById('apikeys-loading').style.display = 'block';
    document.getElementById('apikeys-table').style.display = 'none';

    try {
        const response = await auth.fetch('/api/auth/admin/api_keys');
        apiKeys = await response.json();

        const tbody = document.getElementById('apikeys-tbody');
        tbody.innerHTML = apiKeys.map(key => {
            const isExpired = key.expires_at && new Date(key.expires_at) < new Date();
            const usagePercent = key.usage_percentage || 0;
            
            // Get token stats
            const tokenStats = key.token_stats || { input_tokens: 0, output_tokens: 0, total_tokens: 0 };
            const totalTokens = tokenStats.total_tokens || 0;
            const inputTokens = tokenStats.input_tokens || 0;
            const outputTokens = tokenStats.output_tokens || 0;
            
            // Format token display - show input+output format (e.g., "13+1K")
            const formatTokens = (num) => {
                if (num >= 1000000) return Math.round(num / 1000000) + 'M';
                if (num >= 1000) return Math.round(num / 1000) + 'K';
                return num.toLocaleString();
            };
            
            const tokenDisplay = inputTokens > 0 || outputTokens > 0
                ? `${formatTokens(inputTokens)}+${formatTokens(outputTokens)}`
                : '0';
            
            return `
                <tr>
                    <td>
                        <strong>${key.name}</strong>
                        ${key.description ? `<br><small style="color:#64748b;">${key.description}</small>` : ''}
                    </td>
                    <td>
                        <code style="font-size:0.75rem;background:#f1f5f9;padding:0.25rem 0.5rem;border-radius:4px;" onclick="copyToClipboard('${key.key}', this)">${key.key.substring(0, 8)}...${key.key.substring(key.key.length - 4)}</code>
                    </td>
                    <td>
                        <div style="font-weight:700;color:#10b981;">${tokenDisplay}</div>
                        <small style="color:#64748b;">Requests: ${key.usage_count.toLocaleString()}${key.quota_limit ? ` / ${key.quota_limit.toLocaleString()}` : ''}</small>
                        ${key.quota_limit ? `<br><div style="background:#e2e8f0;height:6px;border-radius:3px;margin-top:4px;overflow:hidden;"><div style="background:${usagePercent > 90 ? '#ef4444' : '#667eea'};width:${Math.min(usagePercent, 100)}%;height:100%;"></div></div>` : ''}
                    </td>
                    <td>
                        ${key.is_active && !isExpired ? 
                            '<span class="badge badge-success">✅ <span class="lang-zh">激活</span><span class="lang-en">Active</span><span class="lang-az">Aktiv</span></span>' : 
                            isExpired ? '<span class="badge badge-danger">⏰ <span class="lang-zh">过期</span><span class="lang-en">Expired</span><span class="lang-az">Müddəti Bitib</span></span>' :
                            '<span class="badge badge-danger">❌ <span class="lang-zh">禁用</span><span class="lang-en">Disabled</span><span class="lang-az">Deaktiv</span></span>'
                        }
                    </td>
                    <td><small>${new Date(key.created_at).toLocaleString('en-US', {timeZone: 'Asia/Shanghai', year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'})}</small></td>
                    <td><small>${key.last_used_at ? new Date(key.last_used_at).toLocaleString('en-US', {timeZone: 'Asia/Shanghai', year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'}) : 'Never'}</small></td>
                    <td>
                        <button class="btn btn-primary btn-sm" onclick="editAPIKey(${key.id})"><span class="lang-zh">编辑</span><span class="lang-en">Edit</span><span class="lang-az">Redaktə</span></button>
                        <button class="btn btn-danger btn-sm" onclick="deleteAPIKey(${key.id}, '${key.name}')"><span class="lang-zh">删除</span><span class="lang-en">Delete</span><span class="lang-az">Sil</span></button>
                    </td>
                </tr>
            `;
        }).join('');

        document.getElementById('apikeys-loading').style.display = 'none';
        document.getElementById('apikeys-table').style.display = 'table';
    } catch (error) {
        const errorMsg = currentLang === 'zh' ? '加载API密钥失败: ' : currentLang === 'az' ? 'API açarlarını yükləmək mümkün olmadı: ' : 'Failed to load API keys: ';
        showAlert(errorMsg + error.message, 'error');
    }
}

function showCreateAPIKeyModal() {
    document.getElementById('create-apikey-modal').classList.add('show');
}

async function createAPIKey() {
    const data = {
        name: document.getElementById('new-apikey-name').value,
        description: document.getElementById('new-apikey-description').value,
        quota_limit: document.getElementById('new-apikey-quota').value ? parseInt(document.getElementById('new-apikey-quota').value) : null,
        expires_days: document.getElementById('new-apikey-expires').value ? parseInt(document.getElementById('new-apikey-expires').value) : null
    };

    if (!data.name) {
        const errorMsg = currentLang === 'zh' ? '请输入API密钥名称' : currentLang === 'az' ? 'Zəhmət olmasa API açarı adını daxil edin' : 'Please enter a name for the API key';
        showAlert(errorMsg, 'error');
        return;
    }

    try {
        const response = await auth.fetch('/api/auth/admin/api_keys', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });

        const result = await response.json();
        
        // Show the generated key
        document.getElementById('generated-apikey').value = result.key;
        closeModal('create-apikey-modal');
        document.getElementById('show-apikey-modal').classList.add('show');
        
        // Clear form
        document.getElementById('new-apikey-name').value = '';
        document.getElementById('new-apikey-description').value = '';
        document.getElementById('new-apikey-quota').value = '';
        document.getElementById('new-apikey-expires').value = '';
        
        showAlert(result.message, 'success');
        loadAPIKeys();
    } catch (error) {
        const errorMsg = currentLang === 'zh' ? '创建API密钥失败: ' : currentLang === 'az' ? 'API açarı yaratmaq mümkün olmadı: ' : 'Failed to create API key: ';
        showAlert(errorMsg + error.message, 'error');
    }
}

function copyAPIKey() {
    const apiKeyInput = document.getElementById('generated-apikey');
    apiKeyInput.select();
    navigator.clipboard.writeText(apiKeyInput.value);
    const successMsg = currentLang === 'zh' ? 'API密钥已复制到剪贴板！📋' : currentLang === 'az' ? 'API açarı mübadilə buferinə kopyalandı! 📋' : 'API key copied to clipboard! 📋';
    showAlert(successMsg, 'success');
}

function editAPIKey(id) {
    const key = apiKeys.find(k => k.id === id);
    if (!key) return;

    document.getElementById('edit-apikey-id').value = key.id;
    document.getElementById('edit-apikey-name').value = key.name;
    document.getElementById('edit-apikey-description').value = key.description || '';
    document.getElementById('edit-apikey-quota').value = key.quota_limit || '';
    document.getElementById('edit-apikey-usage').value = key.usage_count;
    
    document.getElementById('edit-apikey-modal').classList.add('show');
}

async function updateAPIKey() {
    const id = document.getElementById('edit-apikey-id').value;
    const data = {
        name: document.getElementById('edit-apikey-name').value,
        description: document.getElementById('edit-apikey-description').value,
        quota_limit: document.getElementById('edit-apikey-quota').value ? parseInt(document.getElementById('edit-apikey-quota').value) : null,
        usage_count: parseInt(document.getElementById('edit-apikey-usage').value)
    };

    try {
        await auth.fetch(`/api/auth/admin/api_keys/${id}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });

        const successMsg = currentLang === 'zh' ? 'API密钥更新成功' : currentLang === 'az' ? 'API açarı uğurla yeniləndi' : 'API key updated successfully';
        showAlert(successMsg, 'success');
        closeModal('edit-apikey-modal');
        loadAPIKeys();
    } catch (error) {
        const errorMsg = currentLang === 'zh' ? '更新API密钥失败: ' : currentLang === 'az' ? 'API açarını yeniləmək mümkün olmadı: ' : 'Failed to update API key: ';
        showAlert(errorMsg + error.message, 'error');
    }
}

async function toggleAPIKey(id) {
    try {
        const response = await auth.fetch(`/api/auth/admin/api_keys/${id}/toggle`, {
            method: 'PUT'
        });

        const result = await response.json();
        showAlert(result.message, 'success');
        loadAPIKeys();
    } catch (error) {
        const errorMsg = currentLang === 'zh' ? '切换API密钥状态失败: ' : currentLang === 'az' ? 'API açarı vəziyyətini dəyişdirmək mümkün olmadı: ' : 'Failed to toggle API key: ';
        showAlert(errorMsg + error.message, 'error');
    }
}

async function deleteAPIKey(id, name) {
    const confirmMsg = currentLang === 'zh' 
        ? `⚠️ 确定删除API密钥 "${name}"？\n\n此操作无法撤销，将立即撤销访问权限。`
        : currentLang === 'az'
        ? `⚠️ "${name}" API açarını silmək istədiyinizə əminsiniz?\n\nBu əməliyyat geri alına bilməz və dərhal giriş ləğv ediləcək.`
        : `⚠️ Delete API key "${name}"?\n\nThis action cannot be undone and will immediately revoke access.`;
    if (!confirm(confirmMsg)) return;

    try {
        const response = await auth.fetch(`/api/auth/admin/api_keys/${id}`, {
            method: 'DELETE'
        });

        const result = await response.json();
        showAlert(result.message, 'success');
        loadAPIKeys();
    } catch (error) {
        const errorMsg = currentLang === 'zh' ? '删除API密钥失败: ' : currentLang === 'az' ? 'API açarını silmək mümkün olmadı: ' : 'Failed to delete API key: ';
        showAlert(errorMsg + error.message, 'error');
    }
}

