// Admin Panel - users module
// Extracted from admin.html

async function loadUsers(page = 1) {
    document.getElementById('users-loading').style.display = 'block';
    document.getElementById('users-table').style.display = 'none';
    document.getElementById('users-pagination').style.display = 'none';

    try {
        // Build query parameters
        const search = document.getElementById('user-search').value.trim();
        const orgId = document.getElementById('user-org-filter').value;
        
        let url = `/api/auth/admin/users?page=${page}&page_size=${usersPageSize}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (orgId) url += `&organization_id=${orgId}`;
        
        const response = await auth.fetch(url);
        const data = await response.json();
        
        users = data.users;
        usersCurrentPage = data.pagination.page;
        usersTotalPages = data.pagination.total_pages;
        usersTotal = data.pagination.total;

        const tbody = document.getElementById('users-tbody');
        
        // Format number helper (using global formatNumber function)
        tbody.innerHTML = users.map(user => {
            const isLocked = user.locked_until && new Date(user.locked_until) > new Date();
            
            // Get token stats for this user
            const tokenStats = user.token_stats || { input_tokens: 0, output_tokens: 0, total_tokens: 0 };
            const totalTokens = tokenStats.total_tokens || 0;
            const formattedTotal = formatTokenNumber(totalTokens);
            const tokenDisplay = formattedTotal;
            
            return `
                <tr>
                    <td>${user.phone}</td>
                    <td>${user.name || '-'}</td>
                    <td>${user.organization_name || '-'}</td>
                    <td style="font-weight:700;color:#10b981;">
                        ${tokenDisplay} <span style="font-size:0.85rem;font-weight:400;color:#64748b;"><span class="lang-zh">Token</span><span class="lang-en">tokens</span></span>
                    </td>
                    <td style="color:#64748b;">
                        ${user.created_at ? (() => {
                            // Backend returns Beijing time ISO string, parse and format for display
                            const date = new Date(user.created_at);
                            if (isNaN(date.getTime())) return '-';
                            const year = date.getFullYear();
                            const month = String(date.getMonth() + 1).padStart(2, '0');
                            const day = String(date.getDate()).padStart(2, '0');
                            return `${year}-${month}-${day}`;
                        })() : '-'}
                    </td>
                    <td>
                        <button class="btn btn-primary btn-sm" onclick="showEditUserModal(${user.id})" title="${currentLang === 'zh' ? '编辑用户' : currentLang === 'az' ? 'İstifadəçini redaktə et' : 'Edit User'}"><span class="lang-zh">编辑</span><span class="lang-en">Edit</span><span class="lang-az">Redaktə</span></button>
                        <button class="btn btn-danger btn-sm" onclick="deleteUser(${user.id}, '${user.phone}')" title="${currentLang === 'zh' ? '删除用户' : currentLang === 'az' ? 'İstifadəçini sil' : 'Delete User'}"><span class="lang-zh">删除</span><span class="lang-en">Delete</span><span class="lang-az">Sil</span></button>
                        ${isLocked ? 
                            `<button class="btn btn-success btn-sm" onclick="unlockUser(${user.id}, '${user.phone}')" title="${currentLang === 'zh' ? '解锁账户' : currentLang === 'az' ? 'Hesab kilidini aç' : 'Unlock Account'}">🔓 <span class="lang-zh">解锁</span><span class="lang-en">Unlock</span><span class="lang-az">Kilidi Aç</span></button>` : 
                            ''
                        }
                    </td>
                </tr>
            `;
        }).join('');

        // Update pagination info
        updateUsersPagination();

        document.getElementById('users-loading').style.display = 'none';
        document.getElementById('users-table').style.display = 'table';
        document.getElementById('users-pagination').style.display = 'block';
    } catch (error) {
        const errorMsg = currentLang === 'zh' ? '加载用户列表失败' : currentLang === 'az' ? 'İstifadəçi siyahısını yükləmək mümkün olmadı' : 'Failed to load users';
        showAlert(errorMsg, 'error');
        console.error(error);
    }
}

function updateUsersPagination() {
    // Update page info
    const start = (usersCurrentPage - 1) * usersPageSize + 1;
    const end = Math.min(usersCurrentPage * usersPageSize, usersTotal);
    document.getElementById('users-page-info').innerHTML = `
        <span class="lang-zh">显示 ${start}-${end} 共 ${usersTotal} 条</span>
        <span class="lang-en">Showing ${start}-${end} of ${usersTotal}</span>
        <span class="lang-az">Göstərilir ${start}-${end} / ${usersTotal}</span>
    `;
    
    // Update prev/next buttons
    document.getElementById('users-prev-btn').disabled = usersCurrentPage === 1;
    document.getElementById('users-next-btn').disabled = usersCurrentPage === usersTotalPages;
    
    // Generate page numbers (show max 5 pages)
    const pageNumbers = document.getElementById('users-page-numbers');
    pageNumbers.innerHTML = '';
    
    let startPage = Math.max(1, usersCurrentPage - 2);
    let endPage = Math.min(usersTotalPages, startPage + 4);
    
    // Adjust start if we're near the end
    if (endPage - startPage < 4) {
        startPage = Math.max(1, endPage - 4);
    }
    
    for (let i = startPage; i <= endPage; i++) {
        const btn = document.createElement('button');
        btn.className = `btn btn-sm ${i === usersCurrentPage ? 'btn-primary' : 'btn-secondary'}`;
        btn.textContent = i;
        btn.onclick = () => gotoUsersPage(i);
        pageNumbers.appendChild(btn);
    }
}

function filterUsers() {
    usersCurrentPage = 1; // Reset to page 1 when filtering
    loadUsers(1);
}

function clearUserFilters() {
    document.getElementById('user-search').value = '';
    document.getElementById('user-org-filter').value = '';
    filterUsers();
}

function previousUsersPage() {
    if (usersCurrentPage > 1) {
        loadUsers(usersCurrentPage - 1);
    }
}

function nextUsersPage() {
    if (usersCurrentPage < usersTotalPages) {
        loadUsers(usersCurrentPage + 1);
    }
}

function gotoUsersPage(page) {
    loadUsers(page);
}

// Load organizations into filter dropdown

async function loadUserFilters() {
    try {
        const response = await auth.fetch('/api/auth/admin/organizations');
        const orgs = await response.json();
        
        const select = document.getElementById('user-org-filter');
        const currentValue = select.value;
        
        // Get translated text for "All Schools" based on current language
        const allSchoolsText = currentLang === 'zh' ? '全部学校' : 
                               currentLang === 'az' ? 'Bütün Məktəblər' : 
                               'All Schools';
        
        select.innerHTML = `<option value="">${allSchoolsText}</option>` + 
            orgs.map(org => `<option value="${org.id}">${org.code} - ${org.name}</option>`).join('');
        
        select.value = currentValue; // Restore selection if any
    } catch (error) {
        console.error('Failed to load organizations for filter:', error);
    }
}

async function showEditUserModal(userId) {
    const user = users.find(u => u.id === userId);
    if (!user) {
        const errorMsg = currentLang === 'zh' ? '用户未找到' : currentLang === 'az' ? 'İstifadəçi tapılmadı' : 'User not found';
        showAlert(errorMsg, 'error');
        return;
    }

    // Set user data (use real phone for editing)
    document.getElementById('edit-user-id').value = user.id;
    document.getElementById('edit-user-phone').value = user.phone_real || user.phone;
    document.getElementById('edit-user-name').value = user.name || '';
    // Reset password field to default
    document.getElementById('edit-user-reset-password').value = '12345678';

    // Load organizations for dropdown
    try {
        const response = await auth.fetch('/api/auth/organizations');
        const orgs = await response.json();
        
        const select = document.getElementById('edit-user-org');
        select.innerHTML = orgs.map(org => {
            const selected = org.id === user.organization_id ? 'selected' : '';
            return `<option value="${org.id}" ${selected}>${org.code} - ${org.name}</option>`;
        }).join('');
    } catch (error) {
        const errorMsg = currentLang === 'zh' ? '加载组织列表失败' : currentLang === 'az' ? 'Təşkilat siyahısını yükləmək mümkün olmadı' : 'Failed to load organizations';
        showAlert(errorMsg, 'error');
        return;
    }

    openModal('edit-user-modal');
}

async function updateUser() {
    const userId = document.getElementById('edit-user-id').value;
    const phone = document.getElementById('edit-user-phone').value.trim();
    const name = document.getElementById('edit-user-name').value.trim();
    const orgId = parseInt(document.getElementById('edit-user-org').value);

    if (!phone || !name || !orgId) {
        const errorMsg = currentLang === 'zh' ? '所有字段必填' : currentLang === 'az' ? 'Bütün sahələr tələb olunur' : 'All fields required';
        showAlert(errorMsg, 'error');
        return;
    }

    // Validate phone
    if (!/^1\d{10}$/.test(phone)) {
        const errorMsg = currentLang === 'zh' ? '无效的手机号！必须是11位数字且以1开头' : currentLang === 'az' ? 'Yanlış telefon nömrəsi! 1 ilə başlayan 11 rəqəm olmalıdır' : 'Invalid phone number! Must be 11 digits starting with 1';
        showAlert(errorMsg, 'error');
        return;
    }

    // Validate name
    if (/\d/.test(name)) {
        const errorMsg = currentLang === 'zh' ? '姓名不能包含数字！' : currentLang === 'az' ? 'Ad rəqəm ehtiva edə bilməz!' : 'Name cannot contain numbers!';
        showAlert(errorMsg, 'error');
        return;
    }

    try {
        await auth.fetch(`/api/auth/admin/users/${userId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                phone: phone,
                name: name,
                organization_id: orgId
            })
        });

        const successMsg = currentLang === 'zh' ? '用户更新成功' : currentLang === 'az' ? 'İstifadəçi uğurla yeniləndi' : 'User updated successfully';
        showAlert(successMsg, 'success');
        closeModal('edit-user-modal');
        loadUsers();
    } catch (error) {
        const errorMsg = currentLang === 'zh' ? '更新失败: ' : currentLang === 'az' ? 'Yeniləmə uğursuz oldu: ' : 'Update failed: ';
        showAlert(errorMsg + error.message, 'error');
    }
}

async function deleteUser(userId, phone) {
    const confirmMsg = currentLang === 'zh' ? `⚠️ 确定删除用户 ${phone}？\n\n此操作无法撤销！` : currentLang === 'az' ? `⚠️ ${phone} istifadəçisini silmək istədiyinizə əminsiniz?\n\nBu əməliyyat geri alına bilməz!` : `⚠️ Are you sure to delete user ${phone}?\n\nThis action cannot be undone!`;
    if (!confirm(confirmMsg)) {
        return;
    }

    try {
        await auth.fetch(`/api/auth/admin/users/${userId}`, {
            method: 'DELETE'
        });

        const successMsg = currentLang === 'zh' ? '用户删除成功' : currentLang === 'az' ? 'İstifadəçi uğurla silindi' : 'User deleted successfully';
        showAlert(successMsg, 'success');
        loadUsers();
    } catch (error) {
        const errorMsg = currentLang === 'zh' ? '删除失败: ' : currentLang === 'az' ? 'Silinmə uğursuz oldu: ' : 'Delete failed: ';
        showAlert(errorMsg + error.message, 'error');
    }
}

async function unlockUser(id, phone) {
    const confirmMsg = currentLang === 'zh' ? `确定解锁用户 ${phone}？` : currentLang === 'az' ? `${phone} istifadəçisinin kilidini açmaq istədiyinizə əminsiniz?` : `Unlock user ${phone}?`;
    if (!confirm(confirmMsg)) return;

    try {
        await auth.fetch(`/api/auth/admin/users/${id}/unlock`, {
            method: 'PUT'
        });

        const successMsg = currentLang === 'zh' ? '用户解锁成功' : currentLang === 'az' ? 'İstifadəçi kilidi uğurla açıldı' : 'User unlocked successfully';
        showAlert(successMsg, 'success');
        loadUsers();
    } catch (error) {
        const errorMsg = currentLang === 'zh' ? '解锁失败: ' : currentLang === 'az' ? 'Kilid açma uğursuz oldu: ' : 'Unlock failed: ';
        showAlert(errorMsg + error.message, 'error');
    }
}

async function resetPasswordFromModal() {
    const userId = document.getElementById('edit-user-id').value;
    const phone = document.getElementById('edit-user-phone').value;
    const passwordInput = document.getElementById('edit-user-reset-password');
    const newPassword = passwordInput.value.trim() || '12345678';
    
    const confirmMessage = newPassword === '12345678' 
        ? (currentLang === 'zh' 
            ? `⚠️ 确定重置该用户的密码为 '12345678'？\n\n用户: ${phone}\n\n用户需要使用新密码重新登录。`
            : currentLang === 'az'
            ? `⚠️ Bu istifadəçinin parolunu '12345678' olaraq sıfırlamaq istədiyinizə əminsiniz?\n\nİstifadəçi: ${phone}\n\nİstifadəçi yeni parolla yenidən giriş etməlidir.`
            : `⚠️ Reset this user's password to '12345678'?\n\nUser: ${phone}\n\nThe user will need to login again with the new password.`)
        : (currentLang === 'zh'
            ? `⚠️ 确定重置该用户的密码？\n\n用户: ${phone}\n\n新密码: ${'*'.repeat(newPassword.length)}\n\n用户需要使用新密码重新登录。`
            : currentLang === 'az'
            ? `⚠️ Bu istifadəçinin parolunu sıfırlamaq istədiyinizə əminsiniz?\n\nİstifadəçi: ${phone}\n\nYeni parol: ${'*'.repeat(newPassword.length)}\n\nİstifadəçi yeni parolla yenidən giriş etməlidir.`
            : `⚠️ Reset this user's password?\n\nUser: ${phone}\n\nNew password: ${'*'.repeat(newPassword.length)}\n\nThe user will need to login again with the new password.`);
    
    if (!confirm(confirmMessage)) {
        return;
    }

    try {
        const requestBody = { password: newPassword };
        await auth.fetch(`/api/auth/admin/users/${userId}/reset-password`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });

        const successMessage = newPassword === '12345678'
            ? (currentLang === 'zh' ? '密码重置成功 (重置为默认密码 "12345678")' : currentLang === 'az' ? 'Parol uğurla sıfırlandı (standart "12345678" olaraq)' : 'Password reset successfully (to default "12345678")')
            : (currentLang === 'zh' ? '密码重置成功' : currentLang === 'az' ? 'Parol uğurla sıfırlandı' : 'Password reset successfully');
        showAlert(successMessage, 'success');
        closeModal('edit-user-modal');
        loadUsers();
    } catch (error) {
        showAlert('密码重置失败 Password reset failed: ' + error.message, 'error');
    }
}

// Enhanced Settings Management

