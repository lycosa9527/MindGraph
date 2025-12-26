// Admin Panel - realtime module
// Extracted from admin.html

function toggleRealtimeStream() {
    if (realtimeEventSource) {
        stopRealtimeStream();
    } else {
        startRealtimeStream();
    }
}

function startRealtimeStream() {
    if (realtimeEventSource) {
        return; // Already connected
    }
    
    const statusEl = document.getElementById('realtime-status');
    const btnEl = document.getElementById('realtime-toggle-btn');
    
    // Update UI
    statusEl.innerHTML = '<span style="width:8px;height:8px;border-radius:50%;background:#10b981;animation:pulse 2s infinite;"></span><span class="lang-zh">连接中...</span><span class="lang-en">Connecting...</span><span class="lang-az">Qoşulur...</span>';
    btnEl.innerHTML = '<span class="lang-zh">停止监控</span><span class="lang-en">Stop Monitoring</span><span class="lang-az">Monitoru Dayandır</span>';
    
    // Connect to SSE stream
    realtimeEventSource = new EventSource('/api/auth/admin/realtime/stream');
    
    realtimeEventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            handleRealtimeEvent(data);
        } catch (e) {
            console.error('Failed to parse realtime event:', e, 'Event data:', event.data);
            // Show user-friendly error message
            const statusEl = document.getElementById('realtime-status');
            if (statusEl) {
                statusEl.innerHTML = '<span style="width:8px;height:8px;border-radius:50%;background:#f59e0b;"></span><span class="lang-zh">数据解析错误</span><span class="lang-en">Parse Error</span><span class="lang-az">Parse Xətası</span>';
            }
        }
    };
    
    realtimeEventSource.onerror = function(error) {
        console.error('Realtime stream error:', error);
        if (realtimeEventSource) {
            realtimeEventSource.close();
            realtimeEventSource = null;
        }
        const statusEl = document.getElementById('realtime-status');
        const btnEl = document.getElementById('realtime-toggle-btn');
        statusEl.innerHTML = '<span style="width:8px;height:8px;border-radius:50%;background:#ef4444;"></span><span class="lang-zh">连接错误</span><span class="lang-en">Connection Error</span><span class="lang-az">Qoşulma Xətası</span>';
        btnEl.innerHTML = '<span class="lang-zh">开始监控</span><span class="lang-en">Start Monitoring</span><span class="lang-az">Monitoru Başlat</span>';
        
        // Attempt reconnection with exponential backoff
        // Only if no reconnection already in progress and page is visible
        if (!reconnectState.timeoutId && document.visibilityState === 'visible') {
            if (reconnectState.attempts >= reconnectState.maxAttempts) {
                console.error('Max reconnection attempts reached');
                return;
            }
            
            reconnectState.attempts++;
            console.log(`Scheduling reconnection attempt ${reconnectState.attempts} after ${reconnectState.delay}ms`);
            
            reconnectState.timeoutId = setTimeout(function() {
                reconnectState.timeoutId = null;
                if (!realtimeEventSource && document.visibilityState === 'visible') {
                    console.log(`Attempting to reconnect (attempt ${reconnectState.attempts})...`);
                    startRealtimeStream();
                }
            }, reconnectState.delay);
            
            // Exponential backoff: double delay each time, capped at maxDelay
            reconnectState.delay = Math.min(reconnectState.delay * 2, reconnectState.maxDelay);
        }
    };
    
    realtimeEventSource.onopen = function() {
        const statusEl = document.getElementById('realtime-status');
        statusEl.innerHTML = '<span style="width:8px;height:8px;border-radius:50%;background:#10b981;animation:pulse 2s infinite;"></span><span class="lang-zh">已连接</span><span class="lang-en">Connected</span><span class="lang-az">Qoşulub</span>';
        
        // Reset reconnection state on successful connection
        reconnectState.delay = 1000;
        reconnectState.attempts = 0;
        if (reconnectState.timeoutId) {
            clearTimeout(reconnectState.timeoutId);
            reconnectState.timeoutId = null;
        }
    };
}

function stopRealtimeStream() {
    if (realtimeEventSource) {
        realtimeEventSource.close();
        realtimeEventSource = null;
    }
    
    // Cancel any pending reconnection
    if (reconnectState.timeoutId) {
        clearTimeout(reconnectState.timeoutId);
        reconnectState.timeoutId = null;
    }
    
    const statusEl = document.getElementById('realtime-status');
    const btnEl = document.getElementById('realtime-toggle-btn');
    
    statusEl.innerHTML = '<span style="width:8px;height:8px;border-radius:50%;background:#64748b;"></span><span class="lang-zh">未连接</span><span class="lang-en">Disconnected</span><span class="lang-az">Bağlı Deyil</span>';
    btnEl.innerHTML = '<span class="lang-zh">开始监控</span><span class="lang-en">Start Monitoring</span><span class="lang-az">Monitoru Başlat</span>';
}

function handleRealtimeEvent(data) {
    switch(data.type) {
        case 'initial':
            updateRealtimeStats(data.stats);
            updateRealtimeUsers(data.users);
            break;
        case 'stats':
            updateRealtimeStats(data.stats);
            break;
        case 'users_update':
            updateRealtimeUsers(data.users);
            break;
        case 'user_joined':
            // User joined - use incremental update from SSE event
            if (data && data.user && data.user.session_id) {
                // Add or update user in local list
                const existingIndex = realtimeUsers.findIndex(u => u.session_id === data.user.session_id);
                if (existingIndex >= 0) {
                    realtimeUsers[existingIndex] = data.user;
                } else {
                    realtimeUsers.push(data.user);
                }
                renderRealtimeUsers();
                // Update stats if available
                if (data.stats) {
                    updateRealtimeStats(data.stats);
                }
            }
            break;
        case 'user_left':
            // User/session left - remove from local list
            if (data && data.session_id) {
                realtimeUsers = realtimeUsers.filter(u => u.session_id !== data.session_id);
                renderRealtimeUsers();
            }
            break;
        case 'heartbeat':
            // Keep-alive ping
            break;
        case 'error':
            console.error('Realtime stream error:', data.error);
            break;
    }
}

function updateRealtimeStats(stats) {
    document.getElementById('realtime-active-users').textContent = stats.active_users_count || 0;
    document.getElementById('realtime-total-sessions').textContent = stats.total_sessions || 0;
    document.getElementById('realtime-unique-users').textContent = stats.unique_users_count || 0;
    document.getElementById('realtime-recent-activities').textContent = stats.recent_activities_count || 0;
}

function updateRealtimeUsers(users) {
    realtimeUsers = users || [];
    renderRealtimeUsers();
}

function renderRealtimeUsers() {
    const tbody = document.getElementById('realtime-users-tbody');
    const container = document.getElementById('realtime-users-container');
    const loading = document.getElementById('realtime-users-loading');
    
    if (loading) loading.style.display = 'none';
    if (container) container.style.display = 'block';
    
    if (!realtimeUsers || realtimeUsers.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;padding:2rem;color:#64748b;"><span class="lang-zh">暂无在线用户</span><span class="lang-en">No active users</span><span class="lang-az">Aktiv istifadəçi yoxdur</span></td></tr>';
        return;
    }
    
    tbody.innerHTML = realtimeUsers.map(user => {
        // Validate date before parsing
        let lastActivity;
        try {
            lastActivity = new Date(user.last_activity);
            if (isNaN(lastActivity.getTime())) {
                // Invalid date, use current time as fallback
                lastActivity = new Date();
            }
        } catch (e) {
            // Date parsing failed, use current time
            lastActivity = new Date();
        }
        const timeAgo = formatTimeAgo(lastActivity);
        const userPhone = user.user_phone ? escapeHtml(user.user_phone) : '<span class="lang-zh">未知</span><span class="lang-en">Unknown</span><span class="lang-az">Naməlum</span>';
        const activityLabel = user.current_activity_label ? escapeHtml(user.current_activity_label) : '<span class="lang-zh">未知</span><span class="lang-en">Unknown</span><span class="lang-az">Naməlum</span>';
        // Handle user_name: show if it exists and is not empty
        const userName = user.user_name && user.user_name.trim() ? escapeHtml(user.user_name.trim()) : null;
        
        return `
            <tr style="border-bottom:1px solid rgba(255,255,255,0.05);">
                <td style="padding:0.75rem;">
                    <div style="display:flex;flex-direction:column;gap:0.25rem;">
                        <span style="font-weight:600;color:#ffffff;">${userPhone}</span>
                        ${userName ? `<span style="font-size:0.875rem;color:#94a3b8;">${userName}</span>` : ''}
                        ${user.ip_address ? `<span style="font-size:0.75rem;color:#64748b;">IP: ${escapeHtml(user.ip_address)}</span>` : ''}
                    </div>
                </td>
                <td style="padding:0.75rem;">
                    <span style="display:inline-block;padding:0.25rem 0.75rem;background:rgba(59,130,246,0.2);color:#60a5fa;border-radius:6px;font-size:0.875rem;">
                        ${activityLabel}
                    </span>
                </td>
                <td style="padding:0.75rem;color:#cbd5e1;">${user.activity_count || 0}</td>
                <td style="padding:0.75rem;color:#cbd5e1;">${escapeHtml(user.session_duration || '0:00')}</td>
                <td style="padding:0.75rem;color:#94a3b8;font-size:0.875rem;">${timeAgo}</td>
            </tr>
        `;
    }).join('');
}

async function loadRealtimeUsers() {
    try {
        const response = await auth.fetch('/api/auth/admin/realtime/active-users');
        const data = await response.json();
        updateRealtimeUsers(data.users);
        updateRealtimeStats(data);
    } catch (error) {
        console.error('Failed to load realtime users:', error);
    }
}

