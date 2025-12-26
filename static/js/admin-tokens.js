// Admin Panel - tokens module
// Extracted from admin.html

function zoomChart(direction) {
    if (!trendChartInstance) return;
    
    try {
        if (direction === 'in') {
            trendChartInstance.zoom(1.2);
        } else if (direction === 'out') {
            trendChartInstance.zoom(0.8);
        }
    } catch (e) {
        console.warn('Zoom function not available:', e);
    }
}

function resetChartZoom() {
    if (!trendChartInstance) return;
    try {
        trendChartInstance.resetZoom();
    } catch (e) {
        console.warn('Reset zoom function not available:', e);
    }
}

// Show trend chart modal

async function showOrganizationTrendChart(organizationName, organizationId, period = 'week') {
    const modal = document.getElementById('trend-chart-modal');
    const titleElement = document.getElementById('trend-chart-title');
    const canvas = document.getElementById('trend-chart-canvas');
    
    // Store organization info for period switching
    currentOrgInfo.name = organizationName;
    currentOrgInfo.id = organizationId;
    currentOrgInfo.period = period;
    
    // Clear user info (we're viewing an org, not a user)
    currentUserInfo.name = null;
    currentUserInfo.id = null;
    
    // Hide back button when viewing organization
    const backBtn = document.getElementById('back-to-org-btn');
    if (backBtn) backBtn.style.display = 'none';
    
    // Set title with organization name - use proper multilingual spans
    titleElement.innerHTML = `<span class="lang-zh">${organizationName} - Token使用趋势</span><span class="lang-en">${organizationName} - Token Usage Trend</span><span class="lang-az">${organizationName} - Token İstifadə Tendensiyası</span>`;
    applyCurrentLanguage();
    
    // Show modal and switch to chart tab by default
    modal.classList.add('show');
    switchOrgModalTab('chart');
    
    // Show org stats cards, hide user stats cards
    const orgStatsCards = document.getElementById('org-token-stats-cards');
    const userStatsCards = document.getElementById('user-token-stats-cards');
    if (orgStatsCards) orgStatsCards.style.display = 'block';
    if (userStatsCards) userStatsCards.style.display = 'none';
    
    // Show org tabs
    const orgTabs = document.querySelector('.modal-tabs');
    if (orgTabs) orgTabs.style.display = 'flex';
    
    // Show loading state
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.font = '16px Inter';
    ctx.fillStyle = '#64748b';
    ctx.textAlign = 'center';
    const loadingText = currentLang === 'zh' ? '加载中...' : currentLang === 'az' ? 'Yüklənir...' : 'Loading...';
    ctx.fillText(loadingText, canvas.width / 2, canvas.height / 2);
    
    // Update active stat card styling
    document.querySelectorAll('#org-token-stats-cards .stat-card').forEach(card => {
        card.style.opacity = '1';
        card.style.transform = 'scale(1)';
    });
    const activeCard = document.getElementById(`org-stat-${period}`);
    if (activeCard) {
        activeCard.style.opacity = '0.8';
        activeCard.style.transform = 'scale(0.98)';
    }
    
    try {
        // Build query parameters based on period
        let days = 10;
        let hourly = false;
        
        if (period === 'today') {
            days = 1;
            hourly = true; // Show hourly data for today
        } else if (period === 'week') {
            days = 7;
        } else if (period === 'month') {
            days = 30;
        } else if (period === 'total') {
            days = 0; // 0 means all-time (no limit)
        }
        
        let url = `/api/auth/admin/stats/trends/organization?days=${days}&hourly=${hourly}`;
        // organizationId from dataset is always a string, convert to number if valid
        const orgIdNum = organizationId && organizationId !== 'null' && !isNaN(organizationId) ? parseInt(organizationId, 10) : null;
        if (orgIdNum) {
            url += `&organization_id=${orgIdNum}`;
        } else {
            url += `&organization_name=${encodeURIComponent(organizationName)}`;
        }
        
        // Fetch trends data
        const response = await auth.fetch(url);
        if (!response.ok) {
            throw new Error('Failed to fetch organization trends data');
        }
        
        const data = await response.json();
        
        // Destroy existing chart if it exists
        if (trendChartInstance) {
            trendChartInstance.destroy();
        }
        
        // Prepare chart data
        const labels = data.data.map(item => {
            // Check if this is hourly data (contains time)
            if (item.date.includes(' ') && item.date.includes(':')) {
                // Hourly format: "2024-01-15 14:00:00"
                const date = new Date(item.date.replace(' ', 'T'));
                return date.toLocaleString('en-US', { 
                    month: 'short', 
                    day: 'numeric',
                    hour: 'numeric',
                    hour12: false,
                    timeZone: 'Asia/Shanghai'
                });
            } else {
                // Daily format: "2024-01-15"
                const date = new Date(item.date + 'T00:00:00');
                return date.toLocaleDateString('en-US', { 
                    month: 'short', 
                    day: 'numeric',
                    timeZone: 'Asia/Shanghai'
                });
            }
        });
        
        const values = data.data.map(item => item.value);
        
        // Calculate adaptive Y-axis range
        const maxValue = Math.max(...values);
        const minValue = Math.min(...values);
        const range = maxValue - minValue;
        // Handle edge case when all values are the same (e.g., single day)
        const padding = range === 0 ? maxValue * 0.1 : range * 0.1; // 10% padding
        const yMin = Math.max(0, minValue - padding);
        const yMax = maxValue + padding;
        
        // Get translated labels based on current language
        const getChartLabel = (key) => {
            const labels = {
                'total_tokens': {
                    zh: '总Token',
                    en: 'Total Tokens',
                    az: 'Ümumi Tokenlar'
                },
                'input_tokens': {
                    zh: '输入Token',
                    en: 'Input Tokens',
                    az: 'Giriş Tokenları'
                },
                'output_tokens': {
                    zh: '输出Token',
                    en: 'Output Tokens',
                    az: 'Çıxış Tokenları'
                }
            };
            return labels[key] ? labels[key][currentLang] || labels[key]['en'] : key;
        };
        
        // Chart configuration
        const chartConfig = {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: getChartLabel('total_tokens'),
                    data: values,
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 3,
                    pointHoverRadius: 5,
                    pointBackgroundColor: '#667eea',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        labels: {
                            color: '#64748b',
                            font: { size: 12 },
                            padding: 15,
                            usePointStyle: true
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        padding: 12,
                        titleFont: { size: 14, weight: 'bold' },
                        bodyFont: { size: 13 },
                        cornerRadius: 8,
                        displayColors: true
                    },
                    datalabels: {
                        anchor: 'end',
                        align: 'top',
                        offset: 6,
                        color: '#667eea',
                        font: {
                            size: 11,
                            weight: 'bold'
                        },
                        formatter: function(value) {
                            return formatChartLabel(value);
                        },
                        display: function(context) {
                            // Always show labels on the main dataset (total tokens line)
                            return context.datasetIndex === 0;
                        },
                        clamp: true,
                        clip: false
                    },
                    zoom: {
                        zoom: {
                            wheel: {
                                enabled: true,
                                speed: 0.1
                            },
                            pinch: {
                                enabled: true
                            },
                            mode: 'xy',
                            onZoomComplete: function({ chart }) {
                                // Optional: save zoom state
                            }
                        },
                        pan: {
                            enabled: true,
                            mode: 'xy'
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            color: '#94a3b8',
                            font: { size: 11 }
                        }
                    },
                    y: {
                        beginAtZero: true,
                        min: yMin,
                        max: yMax,
                        grid: {
                            color: 'rgba(148, 163, 184, 0.1)'
                        },
                        ticks: {
                            color: '#94a3b8',
                            font: { size: 11 },
                            callback: function(value) {
                                return formatChartLabel(value);
                            }
                        }
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index'
                }
            }
        };
        
        // Add input/output lines if available
        if (data.data[0] && data.data[0].input !== undefined) {
            const inputValues = data.data.map(item => item.input || 0);
            const outputValues = data.data.map(item => item.output || 0);
            
            chartConfig.data.datasets.push({
                label: getChartLabel('input_tokens'),
                data: inputValues,
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                borderWidth: 2,
                fill: false,
                tension: 0.4,
                pointRadius: 2,
                pointHoverRadius: 4
            });
            
            chartConfig.data.datasets.push({
                label: getChartLabel('output_tokens'),
                data: outputValues,
                borderColor: '#f59e0b',
                backgroundColor: 'rgba(245, 158, 11, 0.1)',
                borderWidth: 2,
                fill: false,
                tension: 0.4,
                pointRadius: 2,
                pointHoverRadius: 4
            });
            
            // Update datalabels to show on all datasets with proper styling
            chartConfig.options.plugins.datalabels.display = function(context) {
                return true; // Show on all token lines
            };
            chartConfig.options.plugins.datalabels.color = function(context) {
                const colors = ['#667eea', '#10b981', '#f59e0b'];
                return colors[context.datasetIndex] || '#667eea';
            };
            chartConfig.options.plugins.datalabels.offset = 6;
            chartConfig.options.plugins.datalabels.font = {
                size: 11,
                weight: 'bold'
            };
        }
        
        // Verify datalabels plugin is available before creating chart
        if (typeof ChartDataLabels === 'undefined') {
            console.warn('ChartDataLabels plugin not found. Data labels will not be displayed.');
        } else if (typeof Chart !== 'undefined') {
            // Try to register if not already registered (register handles duplicates gracefully)
            try {
                Chart.register(ChartDataLabels);
            } catch (e) {
                // Plugin might already be registered, which is fine
                if (!e.message || !e.message.includes('already registered')) {
                    console.warn('Failed to register Chart.js datalabels plugin:', e);
                }
            }
        }
        
        // Create chart
        trendChartInstance = new Chart(ctx, chartConfig);
        
        // Fetch and display organization token stats
        await loadOrganizationTokenStats(organizationId);
        
    } catch (error) {
        console.error('Error loading organization trend chart:', error);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.font = '16px Inter';
        ctx.fillStyle = '#ef4444';
        ctx.textAlign = 'center';
        const errorText = currentLang === 'zh' ? '加载图表数据失败' : currentLang === 'az' ? 'Qrafik məlumatları yükləmək mümkün olmadı' : 'Failed to load chart data';
        ctx.fillText(errorText, canvas.width / 2, canvas.height / 2);
        const alertText = currentLang === 'zh' ? '加载组织趋势数据失败' : currentLang === 'az' ? 'Təşkilat tendensiya məlumatlarını yükləmək mümkün olmadı' : 'Failed to load organization trend data';
        showAlert(alertText, 'error');
    }
}

async function loadOrganizationTokenStats(organizationId) {
    const statsContainer = document.getElementById('org-token-stats-cards');
    if (!statsContainer) return;
    
    // Show container
    statsContainer.style.display = 'block';
    
    // Show loading state
    document.getElementById('org-token-today').textContent = '-';
    document.getElementById('org-token-week').textContent = '-';
    document.getElementById('org-token-month').textContent = '-';
    document.getElementById('org-token-total').textContent = '-';
    
    try {
        const orgIdNum = organizationId && organizationId !== 'null' && !isNaN(organizationId) ? parseInt(organizationId, 10) : null;
        if (!orgIdNum) {
            statsContainer.style.display = 'none';
            return;
        }
        
        const response = await auth.fetch(`/api/auth/admin/token-stats?organization_id=${orgIdNum}`);
        if (!response.ok) {
            throw new Error('Failed to fetch organization token stats');
        }
        
        const data = await response.json();
        
        // Format and display today
        const today = data.today || { input_tokens: 0, output_tokens: 0, total_tokens: 0 };
        const todayInput = formatTokenNumber(today.input_tokens || 0);
        const todayOutput = formatTokenNumber(today.output_tokens || 0);
        document.getElementById('org-token-today').textContent = `${todayInput}+${todayOutput}`;
        
        // Format and display week
        const week = data.past_week || { input_tokens: 0, output_tokens: 0, total_tokens: 0 };
        const weekInput = formatTokenNumber(week.input_tokens || 0);
        const weekOutput = formatTokenNumber(week.output_tokens || 0);
        document.getElementById('org-token-week').textContent = `${weekInput}+${weekOutput}`;
        
        // Format and display month
        const month = data.past_month || { input_tokens: 0, output_tokens: 0, total_tokens: 0 };
        const monthInput = formatTokenNumber(month.input_tokens || 0);
        const monthOutput = formatTokenNumber(month.output_tokens || 0);
        document.getElementById('org-token-month').textContent = `${monthInput}+${monthOutput}`;
        
        // Format and display total
        const total = data.total || { input_tokens: 0, output_tokens: 0, total_tokens: 0 };
        const totalInput = formatTokenNumber(total.input_tokens || 0);
        const totalOutput = formatTokenNumber(total.output_tokens || 0);
        document.getElementById('org-token-total').textContent = `${totalInput}+${totalOutput}`;
        
        // Apply current language to newly injected content
        applyCurrentLanguage();
    } catch (error) {
        console.error('Error loading organization token stats:', error);
        statsContainer.style.display = 'none';
    }
}

function switchOrgChartPeriod(period) {
    if (currentOrgInfo.name) {
        showOrganizationTrendChart(currentOrgInfo.name, currentOrgInfo.id, period);
    }
}

// Show user token trend chart

// Store user token stats when loading users (for total stats)
let userTokenStatsCache = {};

async function showUserTrendChart(userId, userName, period = 'week') {
    const modal = document.getElementById('trend-chart-modal');
    const titleElement = document.getElementById('trend-chart-title');
    const canvas = document.getElementById('trend-chart-canvas');
    
    // Store previous org info before clearing (for back button)
    if (currentOrgInfo.name && currentOrgInfo.id) {
        previousOrgInfo.name = currentOrgInfo.name;
        previousOrgInfo.id = currentOrgInfo.id;
    }
    
    // Store user info for period switching
    currentUserInfo.name = userName || 'User';
    currentUserInfo.id = userId;
    currentUserInfo.period = period;
    
    // Clear organization info (we're viewing a user, not an org)
    currentOrgInfo.name = null;
    currentOrgInfo.id = null;
    
    // Set title with user name - use proper multilingual spans
    titleElement.innerHTML = `<span class="lang-zh">${userName || '用户'} - Token使用趋势</span><span class="lang-en">${userName || 'User'} - Token Usage Trend</span><span class="lang-az">${userName || 'İstifadəçi'} - Token İstifadə Tendensiyası</span>`;
    applyCurrentLanguage();
    
    // Show modal and switch to chart tab, hide org tabs
    modal.classList.add('show');
    switchOrgModalTab('chart');
    
    // Hide org stats cards, show user stats cards
    const orgStatsCards = document.getElementById('org-token-stats-cards');
    const userStatsCards = document.getElementById('user-token-stats-cards');
    if (orgStatsCards) orgStatsCards.style.display = 'none';
    if (userStatsCards) userStatsCards.style.display = 'block';
    
    // Hide org tabs (we're in user view)
    const orgTabs = document.querySelector('.modal-tabs');
    if (orgTabs) orgTabs.style.display = 'none';
    
    // Show back button if we have previous org info
    const backBtn = document.getElementById('back-to-org-btn');
    if (backBtn && previousOrgInfo.name && previousOrgInfo.id) {
        backBtn.style.display = 'flex';
    } else if (backBtn) {
        backBtn.style.display = 'none';
    }
    
    // Show loading state
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.font = '16px Inter';
    ctx.fillStyle = '#64748b';
    ctx.textAlign = 'center';
    const loadingText = currentLang === 'zh' ? '加载中...' : currentLang === 'az' ? 'Yüklənir...' : 'Loading...';
    ctx.fillText(loadingText, canvas.width / 2, canvas.height / 2);
    
    // Update active stat card styling
    document.querySelectorAll('#user-token-stats-cards .stat-card').forEach(card => {
        card.style.opacity = '1';
        card.style.transform = 'scale(1)';
    });
    const activeCard = document.getElementById(`user-stat-${period}`);
    if (activeCard) {
        activeCard.style.opacity = '0.8';
        activeCard.style.transform = 'scale(0.98)';
    }
    
    // Load user token stats
    await loadUserTokenStats(userId);
    
    try {
        // Build query parameters based on period
        let days = 7; // Default to week
        
        if (period === 'today') {
            days = 1;
        } else if (period === 'week') {
            days = 7;
        } else if (period === 'month') {
            days = 30;
        } else if (period === 'total') {
            days = 0; // 0 means all-time (no limit)
        }
        
        const userIdNum = userId && !isNaN(userId) ? parseInt(userId, 10) : null;
        if (!userIdNum) {
            throw new Error('Invalid user ID');
        }
        
        const url = `/api/auth/admin/stats/trends/user?user_id=${userIdNum}&days=${days}`;
        
        // Fetch trends data
        const response = await auth.fetch(url);
        if (!response.ok) {
            throw new Error('Failed to fetch user trends data');
        }
        
        const data = await response.json();
        
        // Destroy existing chart if it exists
        if (trendChartInstance) {
            trendChartInstance.destroy();
        }
        
        // Prepare chart data
        const labels = data.data.map(item => {
            // Parse date string and format using Beijing timezone
            const date = new Date(item.date + 'T00:00:00');
            return date.toLocaleDateString('en-US', { 
                month: 'short', 
                day: 'numeric',
                timeZone: 'Asia/Shanghai'
            });
        });
        
        const values = data.data.map(item => item.value);
        
        // Calculate adaptive Y-axis range
        const maxValue = Math.max(...values);
        const minValue = Math.min(...values);
        const range = maxValue - minValue;
        // Handle edge case when all values are the same (e.g., single day)
        const padding = range === 0 ? maxValue * 0.1 : range * 0.1; // 10% padding
        const yMin = Math.max(0, minValue - padding);
        const yMax = maxValue + padding;
        
        // Get translated labels based on current language
        const getChartLabel = (key) => {
            const labels = {
                'total_tokens': {
                    zh: '总Token',
                    en: 'Total Tokens',
                    az: 'Ümumi Tokenlar'
                },
                'input_tokens': {
                    zh: '输入Token',
                    en: 'Input Tokens',
                    az: 'Giriş Tokenları'
                },
                'output_tokens': {
                    zh: '输出Token',
                    en: 'Output Tokens',
                    az: 'Çıxış Tokenları'
                }
            };
            return labels[key] ? labels[key][currentLang] || labels[key]['en'] : key;
        };
        
        // Chart configuration
        const chartConfig = {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: getChartLabel('total_tokens'),
                    data: values,
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 3,
                    pointHoverRadius: 5,
                    pointBackgroundColor: '#667eea',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        labels: {
                            color: '#64748b',
                            font: { size: 12 },
                            padding: 15,
                            usePointStyle: true
                        }
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        padding: 12,
                        titleFont: { size: 14, weight: 'bold' },
                        bodyFont: { size: 13 },
                        cornerRadius: 8,
                        displayColors: true
                    },
                    datalabels: {
                        anchor: 'end',
                        align: 'top',
                        offset: 6,
                        color: '#667eea',
                        font: {
                            size: 11,
                            weight: 'bold'
                        },
                        formatter: function(value) {
                            return formatChartLabel(value);
                        },
                        display: function(context) {
                            // Always show labels on the main dataset (total tokens line)
                            return context.datasetIndex === 0;
                        },
                        clamp: true,
                        clip: false
                    },
                    zoom: {
                        zoom: {
                            wheel: {
                                enabled: true,
                                speed: 0.1
                            },
                            pinch: {
                                enabled: true
                            },
                            mode: 'xy',
                            onZoomComplete: function({ chart }) {
                                // Optional: save zoom state
                            }
                        },
                        pan: {
                            enabled: true,
                            mode: 'xy'
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            color: '#94a3b8',
                            font: { size: 11 }
                        }
                    },
                    y: {
                        beginAtZero: true,
                        min: yMin,
                        max: yMax,
                        grid: {
                            color: 'rgba(148, 163, 184, 0.1)'
                        },
                        ticks: {
                            color: '#94a3b8',
                            font: { size: 11 },
                            callback: function(value) {
                                return formatChartLabel(value);
                            }
                        }
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index'
                }
            }
        };
        
        // Add input/output lines if available
        if (data.data[0] && data.data[0].input !== undefined) {
            const inputValues = data.data.map(item => item.input || 0);
            const outputValues = data.data.map(item => item.output || 0);
            
            chartConfig.data.datasets.push({
                label: getChartLabel('input_tokens'),
                data: inputValues,
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                borderWidth: 2,
                fill: false,
                tension: 0.4,
                pointRadius: 2,
                pointHoverRadius: 4
            });
            
            chartConfig.data.datasets.push({
                label: getChartLabel('output_tokens'),
                data: outputValues,
                borderColor: '#f59e0b',
                backgroundColor: 'rgba(245, 158, 11, 0.1)',
                borderWidth: 2,
                fill: false,
                tension: 0.4,
                pointRadius: 2,
                pointHoverRadius: 4
            });
            
            // Update datalabels to show on all datasets
            chartConfig.options.plugins.datalabels.display = function(context) {
                return true; // Show on all token lines
            };
            chartConfig.options.plugins.datalabels.color = function(context) {
                const colors = ['#667eea', '#10b981', '#f59e0b'];
                return colors[context.datasetIndex] || '#667eea';
            };
            chartConfig.options.plugins.datalabels.offset = 6;
            chartConfig.options.plugins.datalabels.font = {
                size: 11,
                weight: 'bold'
            };
        }
        
        // Verify datalabels plugin is available before creating chart
        if (typeof ChartDataLabels === 'undefined') {
            console.warn('ChartDataLabels plugin not found. Data labels will not be displayed.');
        } else if (typeof Chart !== 'undefined') {
            // Try to register if not already registered (register handles duplicates gracefully)
            try {
                Chart.register(ChartDataLabels);
            } catch (e) {
                // Plugin might already be registered, which is fine
                if (!e.message || !e.message.includes('already registered')) {
                    console.warn('Failed to register Chart.js datalabels plugin:', e);
                }
            }
        }
        
        // Create chart
        trendChartInstance = new Chart(ctx, chartConfig);
        
    } catch (error) {
        console.error('Error loading user trend chart:', error);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.font = '16px Inter';
        ctx.fillStyle = '#ef4444';
        ctx.textAlign = 'center';
        const errorText = currentLang === 'zh' ? '加载图表数据失败' : currentLang === 'az' ? 'Qrafik məlumatları yükləmək mümkün olmadı' : 'Failed to load chart data';
        ctx.fillText(errorText, canvas.width / 2, canvas.height / 2);
        const alertText = currentLang === 'zh' ? '加载用户趋势数据失败' : currentLang === 'az' ? 'İstifadəçi tendensiya məlumatlarını yükləmək mümkün olmadı' : 'Failed to load user trend data';
        showAlert(alertText, 'error');
    }
}

// Load user token stats
async function loadUserTokenStats(userId) {
    const statsContainer = document.getElementById('user-token-stats-cards');
    if (!statsContainer) return;
    
    // Show loading state
    document.getElementById('user-token-today').textContent = '-';
    document.getElementById('user-token-week').textContent = '-';
    document.getElementById('user-token-month').textContent = '-';
    document.getElementById('user-token-total').textContent = '-';
    
    try {
        const userIdNum = userId && !isNaN(userId) ? parseInt(userId, 10) : null;
        if (!userIdNum) {
            return;
        }
        
        // Fetch user token stats from trends endpoint (we'll calculate from trends data)
        // For now, we'll fetch each period separately
        const periods = ['today', 'week', 'month', 'total'];
        const stats = {};
        
        for (const period of periods) {
            // For total stats, use cached token_stats if available (more accurate than summing trends)
            if (period === 'total' && userTokenStatsCache[userIdNum]) {
                const cachedStats = userTokenStatsCache[userIdNum];
                stats[period] = {
                    total_tokens: cachedStats.total_tokens || 0,
                    input_tokens: cachedStats.input_tokens || 0,
                    output_tokens: cachedStats.output_tokens || 0
                };
                continue;
            }
            
            // Determine days for this period
            let days = 1;
            if (period === 'week') {
                days = 7;
            } else if (period === 'month') {
                days = 30;
            } else if (period === 'total') {
                days = 0; // 0 means all-time (no limit)
            }
            
            try {
                const response = await auth.fetch(`/api/auth/admin/stats/trends/user?user_id=${userIdNum}&days=${days}`);
                if (response.ok) {
                    const data = await response.json();
                    // Sum all values for this period
                    const total = data.data.reduce((sum, item) => sum + (item.value || 0), 0);
                    const inputTotal = data.data.reduce((sum, item) => sum + (item.input || 0), 0);
                    const outputTotal = data.data.reduce((sum, item) => sum + (item.output || 0), 0);
                    stats[period] = {
                        total_tokens: total,
                        input_tokens: inputTotal,
                        output_tokens: outputTotal
                    };
                }
            } catch (e) {
                console.warn(`Failed to fetch ${period} stats:`, e);
                stats[period] = { total_tokens: 0, input_tokens: 0, output_tokens: 0 };
            }
        }
        
        // Format and display stats
        const today = stats.today || { input_tokens: 0, output_tokens: 0, total_tokens: 0 };
        const todayInput = formatTokenNumber(today.input_tokens || 0);
        const todayOutput = formatTokenNumber(today.output_tokens || 0);
        document.getElementById('user-token-today').textContent = `${todayInput}+${todayOutput}`;
        
        const week = stats.week || { input_tokens: 0, output_tokens: 0, total_tokens: 0 };
        const weekInput = formatTokenNumber(week.input_tokens || 0);
        const weekOutput = formatTokenNumber(week.output_tokens || 0);
        document.getElementById('user-token-week').textContent = `${weekInput}+${weekOutput}`;
        
        const month = stats.month || { input_tokens: 0, output_tokens: 0, total_tokens: 0 };
        const monthInput = formatTokenNumber(month.input_tokens || 0);
        const monthOutput = formatTokenNumber(month.output_tokens || 0);
        document.getElementById('user-token-month').textContent = `${monthInput}+${monthOutput}`;
        
        const total = stats.total || { input_tokens: 0, output_tokens: 0, total_tokens: 0 };
        const totalInput = formatTokenNumber(total.input_tokens || 0);
        const totalOutput = formatTokenNumber(total.output_tokens || 0);
        document.getElementById('user-token-total').textContent = `${totalInput}+${totalOutput}`;
        
    } catch (error) {
        console.error('Error loading user token stats:', error);
    }
}

// Switch user chart period
function switchUserChartPeriod(period) {
    if (currentUserInfo.id) {
        showUserTrendChart(currentUserInfo.id, currentUserInfo.name, period);
    }
}

// Go back to organization users tab
function goBackToOrgUsers() {
    if (previousOrgInfo.name && previousOrgInfo.id) {
        // Restore organization info
        currentOrgInfo.name = previousOrgInfo.name;
        currentOrgInfo.id = previousOrgInfo.id;
        
        // Clear user info
        currentUserInfo.name = null;
        currentUserInfo.id = null;
        
        // Show organization modal with users tab
        const modal = document.getElementById('trend-chart-modal');
        if (modal) {
            modal.classList.add('show');
            switchOrgModalTab('users');
            
            // Hide back button
            const backBtn = document.getElementById('back-to-org-btn');
            if (backBtn) backBtn.style.display = 'none';
            
            // Show org tabs
            const orgTabs = document.querySelector('.modal-tabs');
            if (orgTabs) orgTabs.style.display = 'flex';
            
            // Hide user stats cards, show org stats cards (but they'll be hidden in users tab)
            const orgStatsCards = document.getElementById('org-token-stats-cards');
            const userStatsCards = document.getElementById('user-token-stats-cards');
            if (orgStatsCards) orgStatsCards.style.display = 'none';
            if (userStatsCards) userStatsCards.style.display = 'none';
        }
    }
}

// Dashboard

async function loadTokenStats() {
    try {
        const response = await auth.fetch('/api/auth/admin/token-stats');
        const data = await response.json();

        // Display stats cards
        const today = data.today || { input_tokens: 0, output_tokens: 0, total_tokens: 0 };
        const week = data.past_week || { input_tokens: 0, output_tokens: 0, total_tokens: 0 };
        const month = data.past_month || { input_tokens: 0, output_tokens: 0, total_tokens: 0 };
        const total = data.total || { input_tokens: 0, output_tokens: 0, total_tokens: 0 };

        // Format and display today
        const todayInput = formatTokenNumber(today.input_tokens || 0);
        const todayOutput = formatTokenNumber(today.output_tokens || 0);
        document.getElementById('token-today').textContent = `${todayInput}+${todayOutput}`;

        // Format and display week
        const weekInput = formatTokenNumber(week.input_tokens || 0);
        const weekOutput = formatTokenNumber(week.output_tokens || 0);
        document.getElementById('token-week').textContent = `${weekInput}+${weekOutput}`;

        // Format and display month
        const monthInput = formatTokenNumber(month.input_tokens || 0);
        const monthOutput = formatTokenNumber(month.output_tokens || 0);
        document.getElementById('token-month').textContent = `${monthInput}+${monthOutput}`;

        // Format and display total
        const totalInput = formatTokenNumber(total.input_tokens || 0);
        const totalOutput = formatTokenNumber(total.output_tokens || 0);
        document.getElementById('token-total').textContent = `${totalInput}+${totalOutput}`;

        // Helper function to render user table
        function renderUserTable(users, containerId) {
            const container = document.getElementById(containerId);
            const userList = users || [];

            if (userList.length === 0) {
                container.innerHTML = '<div style="color:#64748b;text-align:center;padding:2rem;"><span class="lang-zh">暂无用户数据</span><span class="lang-en">No user data yet</span></div>';
            } else {
                // Table header
                let tableHtml = `
                    <table style="width:100%;border-collapse:collapse;">
                        <thead>
                            <tr style="background:#f8fafc;border-bottom:2px solid #e2e8f0;">
                                <th style="padding:0.75rem;text-align:center;font-weight:600;color:#475569;width:60px;"><span class="lang-zh">排名</span><span class="lang-en">Rank</span></th>
                                <th style="padding:0.75rem;text-align:left;font-weight:600;color:#475569;"><span class="lang-zh">姓名</span><span class="lang-en">Name</span></th>
                                <th style="padding:0.75rem;text-align:left;font-weight:600;color:#475569;"><span class="lang-zh">学校</span><span class="lang-en">School</span></th>
                                <th style="padding:0.75rem;text-align:right;font-weight:600;color:#475569;width:150px;"><span class="lang-zh">Token使用量</span><span class="lang-en">Token Usage</span></th>
                            </tr>
                        </thead>
                        <tbody>
                `;
                
                tableHtml += userList.map((user, index) => {
                    const rank = index + 1;
                    let rankBadge = '';
                    let rankStyle = '';
                    
                    if (rank === 1) {
                        rankBadge = '🥇';
                        rankStyle = 'background:linear-gradient(135deg, #ffd700 0%, #ffed4e 100%);color:#000;';
                    } else if (rank === 2) {
                        rankBadge = '🥈';
                        rankStyle = 'background:linear-gradient(135deg, #c0c0c0 0%, #e8e8e8 100%);color:#000;';
                    } else if (rank === 3) {
                        rankBadge = '🥉';
                        rankStyle = 'background:linear-gradient(135deg, #cd7f32 0%, #d4a574 100%);color:#000;';
                    } else {
                        rankBadge = `#${rank}`;
                        rankStyle = 'background:#f1f5f9;color:#64748b;';
                    }
                    
                    // Get token stats - same format as school's tab
                    const inputTokens = user.input_tokens || 0;
                    const outputTokens = user.output_tokens || 0;
                    const formattedInput = formatTokenNumber(inputTokens);
                    const formattedOutput = formatTokenNumber(outputTokens);
                    const tokenDisplay = inputTokens > 0 || outputTokens > 0 
                        ? `${formattedInput}+${formattedOutput}` 
                        : '0';
                    const maskedPhoneDisplay = maskPhone(user.phone);
                    const orgName = user.organization_name || '';
                    const displayName = user.name || maskedPhoneDisplay;
                    const userId = user.id || null;
                    const userNameEscaped = (displayName || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
                    
                    return `
                        <tr style="border-bottom:1px solid #e2e8f0;transition:background 0.2s;cursor:pointer;" 
                            onmouseover="this.style.background='#f1f5f9';this.style.transform='translateX(2px)'" 
                            onmouseout="this.style.background='transparent';this.style.transform='translateX(0)'"
                            data-user-id="${userId || ''}"
                            data-user-name="${userNameEscaped}"
                            onclick="showUserTrendChart(this.dataset.userId, this.dataset.userName)">
                            <td style="padding:0.75rem;text-align:center;">
                                <span style="display:inline-block;min-width:40px;text-align:center;font-weight:700;padding:0.35rem 0.5rem;border-radius:6px;${rankStyle}">${rankBadge}</span>
                            </td>
                            <td style="padding:0.75rem;font-weight:500;">${displayName}</td>
                            <td style="padding:0.75rem;font-size:0.875rem;">
                                ${orgName ? `<span style="background:#eef2ff;color:#6366f1;padding:0.25rem 0.5rem;border-radius:4px;">${orgName}</span>` : '<span style="color:#94a3b8;">-</span>'}
                            </td>
                            <td style="padding:0.75rem;text-align:right;font-weight:700;color:#10b981;font-size:1.05rem;">
                                ${tokenDisplay} <span style="font-size:0.85rem;font-weight:400;color:#64748b;"><span class="lang-zh">Token</span><span class="lang-en">tokens</span></span>
                            </td>
                        </tr>
                    `;
                }).join('');
                
                tableHtml += '</tbody></table>';
                container.innerHTML = tableHtml;
            }
        }

        // Display top 10 users by total token usage
        const topUsers = data.top_users || [];
        renderUserTable(topUsers, 'token-users-list');

        // Display top 10 users by today's token usage
        const topUsersToday = data.top_users_today || [];
        renderUserTable(topUsersToday, 'token-users-today-list');
        
        // Apply current language to newly injected content
        applyCurrentLanguage();
    } catch (error) {
        const errorMsg = currentLang === 'zh' ? '加载Token统计失败' : currentLang === 'az' ? 'Token statistikalarını yükləmək mümkün olmadı' : 'Failed to load token stats';
        showAlert(errorMsg, 'error');
        console.error('Token stats error:', error);
    }
}

// Organization modal tab switching
function switchOrgModalTab(tab) {
    const chartTab = document.getElementById('org-chart-tab');
    const usersTab = document.getElementById('org-users-tab');
    const chartContent = document.getElementById('org-chart-content');
    const usersContent = document.getElementById('org-users-content');
    
    // Remove active class from all tabs
    chartTab.classList.remove('active');
    usersTab.classList.remove('active');
    
    // Hide all content
    chartContent.style.display = 'none';
    usersContent.style.display = 'none';
    
    // Show selected tab and content
    if (tab === 'chart') {
        chartTab.classList.add('active');
        chartContent.style.display = 'block';
    } else if (tab === 'users') {
        usersTab.classList.add('active');
        usersContent.style.display = 'block';
        // Load users when switching to users tab
        loadOrganizationUsers();
    }
}

// Load users for the current organization
async function loadOrganizationUsers() {
    const loadingEl = document.getElementById('org-users-loading');
    const listEl = document.getElementById('org-users-list');
    const emptyEl = document.getElementById('org-users-empty');
    
    // Show loading, hide list and empty
    loadingEl.style.display = 'block';
    listEl.style.display = 'none';
    emptyEl.style.display = 'none';
    
    try {
        const orgId = currentOrgInfo.id;
        if (!orgId || orgId === 'null' || isNaN(orgId)) {
            emptyEl.style.display = 'block';
            loadingEl.style.display = 'none';
            return;
        }
        
        const orgIdNum = parseInt(orgId, 10);
        
        // Fetch users for this organization
        const response = await auth.fetch(`/api/auth/admin/users?organization_id=${orgIdNum}&page_size=100`);
        if (!response.ok) {
            throw new Error('Failed to fetch organization users');
        }
        
        const data = await response.json();
        const users = data.users || [];
        
        // Cache user token stats for later use in total stats
        userTokenStatsCache = {};
        users.forEach(user => {
            if (user.id && user.token_stats) {
                userTokenStatsCache[user.id] = user.token_stats;
            }
        });
        
        loadingEl.style.display = 'none';
        
        if (users.length === 0) {
            emptyEl.style.display = 'block';
            return;
        }
        
        // Sort users by total token usage (descending)
        users.sort((a, b) => {
            const aTotal = (a.token_stats && a.token_stats.total_tokens) || 0;
            const bTotal = (b.token_stats && b.token_stats.total_tokens) || 0;
            return bTotal - aTotal;
        });
        
        // Render user list
        listEl.innerHTML = users.map((user, index) => {
            const tokenStats = user.token_stats || { input_tokens: 0, output_tokens: 0, total_tokens: 0 };
            const inputTokens = tokenStats.input_tokens || 0;
            const outputTokens = tokenStats.output_tokens || 0;
            const formattedInput = formatTokenNumber(inputTokens);
            const formattedOutput = formatTokenNumber(outputTokens);
            const tokenDisplay = inputTokens > 0 || outputTokens > 0 
                ? `${formattedInput}+${formattedOutput}` 
                : '0';
            
            // Format registration date
            const regDate = user.created_at ? new Date(user.created_at).toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                timeZone: 'Asia/Shanghai'
            }) : '-';
            
            const userNameEscaped = (user.name || 'User').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
            return `
                <div class="org-user-item" 
                     style="display:flex;align-items:center;gap:1rem;padding:0.75rem;border-bottom:1px solid #e2e8f0;transition:background 0.2s;cursor:pointer;"
                     onmouseover="this.style.background='#f1f5f9';this.style.transform='translateX(2px)'"
                     onmouseout="this.style.background='transparent';this.style.transform='translateX(0)'"
                     onclick="showUserTrendChart(${user.id}, '${userNameEscaped}')">
                    <div style="min-width:40px;text-align:center;font-weight:700;color:#64748b;">
                        #${index + 1}
                    </div>
                    <div style="flex:1;">
                        <div style="font-weight:600;color:#1e293b;margin-bottom:0.25rem;">
                            ${user.name || '-'}
                        </div>
                        <div style="font-size:0.875rem;color:#64748b;">
                            ${user.phone || '-'}
                        </div>
                    </div>
                    <div style="font-weight:700;color:#10b981;font-size:1rem;min-width:120px;text-align:right;">
                        ${tokenDisplay} <span style="font-size:0.85rem;font-weight:400;color:#64748b;"><span class="lang-zh">Token</span><span class="lang-en">tokens</span><span class="lang-az">tokenlar</span></span>
                    </div>
                    <div style="font-size:0.875rem;color:#64748b;min-width:120px;text-align:right;">
                        ${regDate}
                    </div>
                </div>
            `;
        }).join('');
        
        listEl.style.display = 'block';
        applyCurrentLanguage();
        
    } catch (error) {
        console.error('Error loading organization users:', error);
        loadingEl.style.display = 'none';
        emptyEl.style.display = 'block';
        const errorMsg = currentLang === 'zh' ? '加载用户列表失败' : currentLang === 'az' ? 'İstifadəçi siyahısını yükləmək mümkün olmadı' : 'Failed to load user list';
        showAlert(errorMsg, 'error');
    }
}

// Edit user from organization modal (opens the edit user modal)
function editUserFromOrgModal(userId) {
    // Close the trend chart modal first
    closeModal('trend-chart-modal');
    
    // Find the user and open edit modal
    // This function should be available from admin-users.js
    if (typeof showEditUserModal === 'function') {
        showEditUserModal(userId);
    } else {
        // Fallback: navigate to users tab
        switchTab('users');
        const errorMsg = currentLang === 'zh' ? '请稍候，正在加载用户信息...' : currentLang === 'az' ? 'Zəhmət olmasa gözləyin, istifadəçi məlumatları yüklənir...' : 'Please wait, loading user information...';
        showAlert(errorMsg, 'info');
    }
}

// Schools

