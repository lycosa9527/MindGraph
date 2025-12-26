// Admin Panel - schools module
// Extracted from admin.html

function showCreateSchoolModal() {
    // Clear form first
    document.getElementById('new-school-name').value = '';
    document.getElementById('new-school-code').value = '';
    document.getElementById('create-school-modal').classList.add('show');
}

function autoGenerateSchoolCode() {
    const nameInput = document.getElementById('new-school-name');
    const codeInput = document.getElementById('new-school-code');
    const name = nameInput.value.trim();
    
    if (!name) {
        codeInput.value = '';
        return;
    }
    
    // Extract English letters and Chinese characters
    const letters = name.match(/[A-Za-z]+/g) || [];
    const chinese = name.match(/[\u4e00-\u9fa5]+/g) || [];
    
    let prefix = '';
    
    // Prefer English letters for code generation
    if (letters.length > 0) {
        prefix = letters.join('').toUpperCase();
    } else if (chinese.length > 0) {
        // Use first letter of Chinese pinyin or just use first character
        // For simplicity, we'll just use "SCHOOL" as fallback
        prefix = 'SCHOOL';
    }
    
    // Take first 2-4 letters for prefix
    prefix = prefix.substring(0, Math.min(prefix.length, 4));
    if (prefix.length < 2) prefix = prefix.padEnd(2, 'X');
    
    // Add random suffix with timestamp component for uniqueness
    const timestamp = Date.now().toString().slice(-3);
    const randomChars = Math.random().toString(36).substring(2, 5).toUpperCase();
    
    codeInput.value = `${prefix}-${randomChars}${timestamp}`;
}

// Regenerate school code manually

function regenerateSchoolCode() {
    const nameInput = document.getElementById('new-school-name');
    const codeInput = document.getElementById('new-school-code');
    const name = nameInput.value.trim();
    
    if (!name) {
        const errorMsg = currentLang === 'zh' ? '请先输入学校名称' : currentLang === 'az' ? 'Zəhmət olmasa əvvəlcə məktəb adını daxil edin' : 'Please enter school name first';
        showAlert(errorMsg, 'error');
        return;
    }
    
    // Generate with different random seed
    autoGenerateSchoolCode();
}

// Format numbers with K/M suffix for readability (shared function)
// Uses Math.ceil() to round up instead of showing decimals

async function loadSchools() {
    document.getElementById('schools-loading').style.display = 'block';
    document.getElementById('schools-table').style.display = 'none';

    try {
        const response = await auth.fetch('/api/auth/admin/organizations');
        schools = await response.json();

        // Populate filter dropdown
        populateSchoolFilter();
        
        // Apply current filter if any
        filterSchools();
    } catch (error) {
        const errorMsg = currentLang === 'zh' ? '加载学校列表失败' : currentLang === 'az' ? 'Məktəb siyahısını yükləmək mümkün olmadı' : 'Failed to load schools';
        showAlert(errorMsg, 'error');
        document.getElementById('schools-loading').style.display = 'none';
    }
}

function populateSchoolFilter() {
    const select = document.getElementById('school-filter');
    if (!select || !schools || schools.length === 0) {
        return;
    }
    
    const currentValue = select.value;
    
    // Sort schools by name for better UX
    const sortedSchools = [...schools].sort((a, b) => {
        const nameA = (a.name || '').toLowerCase();
        const nameB = (b.name || '').toLowerCase();
        return nameA.localeCompare(nameB);
    });
    
    // Get current language for option text
    const allSchoolsText = currentLang === 'zh' ? '全部学校' : 
                           currentLang === 'az' ? 'Bütün Məktəblər' : 
                           'All Schools';
    
    select.innerHTML = `<option value="">${allSchoolsText}</option>` + 
        sortedSchools.map(school => `<option value="${school.id}">${school.name}</option>`).join('');
    
    select.value = currentValue; // Restore selection if any
}

function filterSchools() {
    if (!schools || schools.length === 0) {
        return; // Schools not loaded yet
    }
    
    const schoolFilter = document.getElementById('school-filter')?.value || '';
    const filteredSchools = schoolFilter 
        ? schools.filter(school => school.id.toString() === schoolFilter)
        : schools;

    const tbody = document.getElementById('schools-tbody');
    tbody.innerHTML = filteredSchools.map(school => {
            // Backend returns Beijing time ISO strings, parse directly for comparison
            const expiresAt = school.expires_at ? new Date(school.expires_at) : null;
            const now = new Date();
            // Compare dates (backend timestamps are already in Beijing time)
            const isExpired = expiresAt && !isNaN(expiresAt.getTime()) && expiresAt < now;
            const isActive = school.is_active !== false;
            
            // Get token stats for this school - same format as tokens tab
            const tokenStats = school.token_stats || { input_tokens: 0, output_tokens: 0, total_tokens: 0 };
            const inputTokens = tokenStats.input_tokens || 0;
            const outputTokens = tokenStats.output_tokens || 0;
            const formattedInput = formatTokenNumber(inputTokens);
            const formattedOutput = formatTokenNumber(outputTokens);
            const tokenDisplay = inputTokens > 0 || outputTokens > 0 
                ? `${formattedInput}+${formattedOutput}` 
                : '0';
            
            const schoolNameEscaped = (school.name || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
            const schoolId = school.id || null;
            
            return `
                <tr style="${!isActive || isExpired ? 'background:#fee;' : ''}">
                    <td style="cursor:pointer;" 
                        onmouseover="this.style.color='#667eea';this.style.textDecoration='underline';" 
                        onmouseout="this.style.color='';this.style.textDecoration='none';"
                        data-org-name="${schoolNameEscaped}" 
                        data-org-id="${schoolId || ''}"
                        onclick="showOrganizationTrendChart(this.dataset.orgName, this.dataset.orgId || null, 'total')">
                        ${school.name}
                    </td>
                    <td>
                        <span class="badge badge-success">${school.invitation_code}</span>
                        <button class="btn btn-sm" 
                                onclick="event.stopPropagation(); copySchoolInviteInfo('${school.invitation_code}')" 
                                title="复制分享信息"
                                style="background:transparent;border:none;padding:0.25rem 0.5rem;cursor:pointer;font-size:1.1rem;">
                            📤
                        </button>
                    </td>
                    <td style="font-weight:700;color:#10b981;cursor:pointer;" 
                        onmouseover="this.style.color='#059669';" 
                        onmouseout="this.style.color='#10b981';"
                        data-org-name="${schoolNameEscaped}" 
                        data-org-id="${schoolId || ''}"
                        onclick="showOrganizationTrendChart(this.dataset.orgName, this.dataset.orgId || null, 'total')">
                        ${tokenDisplay} <span style="font-size:0.85rem;font-weight:400;color:#64748b;"><span class="lang-zh">Token</span><span class="lang-en">tokens</span></span>
                    </td>
                    <td>
                        ${!isActive ? 
                            '<span class="badge badge-danger">🔒 <span class="lang-zh">锁定</span><span class="lang-en">Locked</span><span class="lang-az">Kilidlənib</span></span>' : 
                            isExpired ? 
                            '<span class="badge badge-danger">⏰ <span class="lang-zh">已过期</span><span class="lang-en">Expired</span><span class="lang-az">Müddəti Bitib</span></span>' :
                            '<span class="badge badge-success">✅ <span class="lang-zh">正常</span><span class="lang-en">Active</span><span class="lang-az">Aktiv</span></span>'
                        }
                    </td>
                    <td>${school.user_count} <span class="lang-zh">用户</span><span class="lang-en">users</span><span class="lang-az">istifadəçi</span></td>
                    <td>
                        <button class="btn btn-primary btn-sm" onclick="event.stopPropagation(); editSchool(${school.id})"><span class="lang-zh">编辑</span><span class="lang-en">Edit</span><span class="lang-az">Redaktə</span></button>
                        <button class="btn btn-danger btn-sm" onclick="event.stopPropagation(); deleteSchool(${school.id}, '${school.code}')"><span class="lang-zh">删除</span><span class="lang-en">Delete</span><span class="lang-az">Sil</span></button>
                    </td>
                </tr>
            `;
        }).join('');

    document.getElementById('schools-loading').style.display = 'none';
    document.getElementById('schools-table').style.display = 'table';
    
    // Apply current language to newly injected content
    applyCurrentLanguage();
}

function clearSchoolFilters() {
    const schoolFilter = document.getElementById('school-filter');
    if (schoolFilter) {
        schoolFilter.value = '';
    }
    filterSchools();
}

async function createSchool() {
    const data = {
        code: document.getElementById('new-school-code').value,
        name: document.getElementById('new-school-name').value
    };

    if (!data.code || !data.name) {
        const errorMsg = currentLang === 'zh' ? '请填写必填字段' : currentLang === 'az' ? 'Zəhmət olmasa tələb olunan sahələri doldurun' : 'Please fill required fields';
        showAlert(errorMsg, 'error');
        return;
    }

    try {
        await auth.fetch('/api/auth/admin/organizations', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });

        const successMsg = currentLang === 'zh' ? '学校创建成功' : currentLang === 'az' ? 'Məktəb uğurla yaradıldı' : 'School created successfully';
        showAlert(successMsg, 'success');
        closeModal('create-school-modal');
        loadSchools();
        
        // Clear form
        document.getElementById('new-school-code').value = '';
        document.getElementById('new-school-name').value = '';
        // Invitation code is generated on the server
    } catch (error) {
        const errorMsg = currentLang === 'zh' ? '创建失败: ' : currentLang === 'az' ? 'Yaradılma uğursuz oldu: ' : 'Creation failed: ';
        showAlert(errorMsg + error.message, 'error');
    }
}

function editSchool(id) {
    const school = schools.find(s => s.id === id);
    if (!school) return;

    document.getElementById('edit-school-id').value = school.id;
    document.getElementById('edit-school-code').value = school.code;
    document.getElementById('edit-school-name').value = school.name;
    document.getElementById('edit-school-invite').value = school.invitation_code;
    
    // Set expiration date (extract date part from Beijing time ISO string)
    if (school.expires_at) {
        const date = new Date(school.expires_at);
        if (!isNaN(date.getTime())) {
            // Extract YYYY-MM-DD from the date (backend returns Beijing time ISO string)
            const year = date.getFullYear();
            const month = String(date.getMonth() + 1).padStart(2, '0');
            const day = String(date.getDate()).padStart(2, '0');
            document.getElementById('edit-school-expires').value = `${year}-${month}-${day}`;
        } else {
            document.getElementById('edit-school-expires').value = '';
        }
    } else {
        document.getElementById('edit-school-expires').value = '';
    }
    
    // Set active status
    document.getElementById('edit-school-active').value = school.is_active !== false ? 'true' : 'false';
    
    document.getElementById('edit-school-modal').classList.add('show');
}

function regenerateInviteCode() {
    const name = document.getElementById('edit-school-name').value;
    const code = document.getElementById('edit-school-code').value;
    const prefix = (name || code || '').replace(/[^A-Za-z]/g, '').toUpperCase().slice(0, 4).padEnd(4, 'X');
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
    let suffix = '';
    for (let i = 0; i < 5; i++) {
        suffix += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    document.getElementById('edit-school-invite').value = `${prefix}-${suffix}`;
}

async function updateSchool() {
    const id = document.getElementById('edit-school-id').value;
    const expiresValue = document.getElementById('edit-school-expires').value;
    
    const data = {
        code: document.getElementById('edit-school-code').value,
        name: document.getElementById('edit-school-name').value,
        invitation_code: document.getElementById('edit-school-invite').value,
        expires_at: expiresValue ? expiresValue : null,  // Convert to null if empty
        is_active: document.getElementById('edit-school-active').value === 'true'
    };

    try {
        await auth.fetch(`/api/auth/admin/organizations/${id}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });

        const successMsg = currentLang === 'zh' ? '学校更新成功' : currentLang === 'az' ? 'Məktəb uğurla yeniləndi' : 'School updated successfully';
        showAlert(successMsg, 'success');
        closeModal('edit-school-modal');
        loadSchools();
    } catch (error) {
        const errorMsg = currentLang === 'zh' ? '更新失败: ' : currentLang === 'az' ? 'Yeniləmə uğursuz oldu: ' : 'Update failed: ';
        showAlert(errorMsg + error.message, 'error');
    }
}

async function deleteSchool(id, code) {
    const confirmMsg = currentLang === 'zh' ? `确定删除学校 ${code}？` : currentLang === 'az' ? `${code} məktəbini silmək istədiyinizə əminsiniz?` : `Are you sure to delete school ${code}?`;
    if (!confirm(confirmMsg)) return;

    try {
        await auth.fetch(`/api/auth/admin/organizations/${id}`, {
            method: 'DELETE'
        });

        const successMsg = currentLang === 'zh' ? '学校删除成功' : currentLang === 'az' ? 'Məktəb uğurla silindi' : 'School deleted successfully';
        showAlert(successMsg, 'success');
        loadSchools();
    } catch (error) {
        const errorMsg = currentLang === 'zh' ? '删除失败: ' : currentLang === 'az' ? 'Silinmə uğursuz oldu: ' : 'Delete failed: ';
        showAlert(errorMsg + error.message, 'error');
    }
}

function copySchoolInviteInfo(invitationCode) {
    const shareText = `尊敬的校领导，您好！
诚挚邀请您与学校团队体验 MindGraph —— 我们倾力打造的AI思维图示生成软件，致力于开发思维教学信息化平台。
贵校的专属邀请码是：${invitationCode}
请您访问 mg.mingspringedu.com 完成注册，开启高效、直观的思维可视化协作。
期待能为贵校的教育创新增添一份力量。`;
    
    // Set the text in the modal
    document.getElementById('share-invite-text').value = shareText;
    
    // Show the modal
    openModal('share-invite-modal');
}

async function selectAndCopyShareText(button) {
    const textarea = document.getElementById('share-invite-text');
    const text = textarea.value;
    
    // Select the text
    textarea.select();
    textarea.setSelectionRange(0, 99999); // For mobile devices
    
    // Copy to clipboard
    try {
        await navigator.clipboard.writeText(text);
        // Show feedback
        const originalText = button.innerHTML;
        button.innerHTML = '✅ <span class="lang-zh">已复制！</span><span class="lang-en">Copied!</span>';
        button.style.background = '#10b981';
        setTimeout(() => {
            button.innerHTML = originalText;
            button.style.background = '';
        }, 2000);
    } catch (err) {
        // Fallback for older browsers
        try {
            document.execCommand('copy');
            const originalText = button.innerHTML;
            button.innerHTML = '✅ <span class="lang-zh">已复制！</span><span class="lang-en">Copied!</span>';
            button.style.background = '#10b981';
            setTimeout(() => {
                button.innerHTML = originalText;
                button.style.background = '';
            }, 2000);
        } catch (fallbackErr) {
            alert('无法复制，请手动选择并复制文本');
        }
    }
}

// Users

