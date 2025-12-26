// Admin Panel - dashboard module
// Extracted from admin.html

async function showTrendChart(metric, cardElement) {
    const modal = document.getElementById('trend-chart-modal');
    const titleElement = document.getElementById('trend-chart-title');
    const canvas = document.getElementById('trend-chart-canvas');
    
    // Map token-specific metrics to API metric and days
    let apiMetric = metric;
    let days = 30;
    
    if (metric === 'token-today') {
        apiMetric = 'tokens';
        days = 1;
    } else if (metric === 'token-week') {
        apiMetric = 'tokens';
        days = 7;
    } else if (metric === 'token-month') {
        apiMetric = 'tokens';
        days = 30;
    } else if (metric === 'token-total') {
        apiMetric = 'tokens';
        days = 0; // 0 means all-time (no limit)
    }
    
    // Set title based on metric
    const titles = {
        'users': { zh: '总用户数趋势', en: 'Total Users Trend', az: 'Ümumi İstifadəçilər Tendensiyası' },
        'organizations': { zh: '学校数量趋势', en: 'Organizations Trend', az: 'Təşkilatlar Tendensiyası' },
        'registrations': { zh: '每日注册趋势', en: 'Daily Registrations Trend', az: 'Günlük Qeydiyyat Tendensiyası' },
        'tokens': { zh: 'Token使用趋势', en: 'Token Usage Trend', az: 'Token İstifadə Tendensiyası' },
        'token-today': { zh: '今日Token趋势', en: 'Today Token Trend', az: 'Bu Gün Token Tendensiyası' },
        'token-week': { zh: '过去一周Token趋势', en: 'Past Week Token Trend', az: 'Keçən Həftə Token Tendensiyası' },
        'token-month': { zh: '过去一月Token趋势', en: 'Past Month Token Trend', az: 'Keçən Ay Token Tendensiyası' },
        'token-total': { zh: 'Token总计趋势', en: 'Total Token Trend', az: 'Ümumi Token Tendensiyası' }
    };
    
    const title = titles[metric] || { zh: '趋势图表', en: 'Trend Chart', az: 'Tendensiya Qrafiki' };
    titleElement.innerHTML = `<span class="lang-zh">${title.zh}</span><span class="lang-en">${title.en}</span><span class="lang-az">${title.az}</span>`;
    applyCurrentLanguage();
    
    // Show modal
    modal.classList.add('show');
    
    // Show loading state
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.font = '16px Inter';
    ctx.fillStyle = '#64748b';
    ctx.textAlign = 'center';
    // Get translated loading text
    const loadingText = currentLang === 'zh' ? '加载中...' : currentLang === 'az' ? 'Yüklənir...' : 'Loading...';
    ctx.fillText(loadingText, canvas.width / 2, canvas.height / 2);
    
    try {
        // Fetch trends data
        const response = await auth.fetch(`/api/auth/admin/stats/trends?metric=${apiMetric}&days=${days}`);
        if (!response.ok) {
            throw new Error('Failed to fetch trends data');
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
        
        // Chart configuration
        const chartConfig = {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: currentLang === 'zh' ? title.zh : currentLang === 'az' ? title.az : title.en,
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
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'rgba(0, 0, 0, 0.8)',
                        padding: 12,
                        titleFont: { size: 14, weight: 'bold' },
                        bodyFont: { size: 13 },
                        cornerRadius: 8,
                        displayColors: false
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
                            // Always show labels on the main dataset
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
                            onZoomComplete: function({chart}) {
                                // Keep chart centered after zoom
                                chart.update('none');
                            }
                        },
                        pan: {
                            enabled: true,
                            mode: 'xy'
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: false,
                        min: yMin,
                        max: yMax,
                        grid: {
                            color: 'rgba(0, 0, 0, 0.05)'
                        },
                        ticks: {
                            color: '#64748b',
                            font: { size: 12 },
                            callback: function(value) {
                                return formatChartLabel(value);
                            }
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            color: '#64748b',
                            font: { size: 11 },
                            maxRotation: 45,
                            minRotation: 45
                        },
                        afterFit: function(scale) {
                            // Keep x-axis centered
                        }
                    }
                },
                animation: {
                    duration: 0
                },
                interaction: {
                    intersect: false,
                    mode: 'index'
                }
            }
        };
        
        // For tokens, add input/output lines if available
        if ((metric === 'tokens' || metric.startsWith('token-')) && data.data[0] && data.data[0].input !== undefined) {
            const inputValues = data.data.map(item => item.input || 0);
            const outputValues = data.data.map(item => item.output || 0);
            
            // Get translated labels
            const getChartLabel = (key) => {
                const labels = {
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
            
            // Update datalabels to show on all datasets for tokens with proper styling
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
            
            chartConfig.options.plugins.legend.display = true;
            chartConfig.options.plugins.legend.position = 'top';
            chartConfig.options.plugins.legend.labels = {
                color: '#64748b',
                font: { size: 12 },
                padding: 15,
                usePointStyle: true
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
        console.error('Error loading trend chart:', error);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.font = '16px Inter';
        ctx.fillStyle = '#ef4444';
        ctx.textAlign = 'center';
        const errorText = currentLang === 'zh' ? '加载图表数据失败' : currentLang === 'az' ? 'Qrafik məlumatları yükləmək mümkün olmadı' : 'Failed to load chart data';
        ctx.fillText(errorText, canvas.width / 2, canvas.height / 2);
        const alertText = currentLang === 'zh' ? '加载趋势数据失败' : currentLang === 'az' ? 'Tendensiya məlumatlarını yükləmək mümkün olmadı' : 'Failed to load trend data';
        showAlert(alertText, 'error');
    }
}

// Show organization token trend chart
// Note: currentOrgInfo is declared in admin-utils.js

async function loadDashboard() {
    try {
        const response = await auth.fetch('/api/auth/admin/stats');
        const stats = await response.json();

        document.getElementById('stat-users').textContent = stats.total_users;
        document.getElementById('stat-orgs').textContent = stats.total_organizations;
        document.getElementById('stat-recent').textContent = stats.recent_registrations;
        
        // Fetch total token stats
        try {
            const tokenResponse = await auth.fetch('/api/auth/admin/token-stats');
            const tokenData = await tokenResponse.json();
            const totalStats = tokenData.total || { input_tokens: 0, output_tokens: 0 };
            const inputTokens = totalStats.input_tokens || 0;
            const outputTokens = totalStats.output_tokens || 0;
            
            const formattedInput = formatTokenNumber(inputTokens);
            const formattedOutput = formatTokenNumber(outputTokens);
            document.getElementById('stat-tokens').textContent = `${formattedInput}+${formattedOutput}`;
        } catch (error) {
            // Show error instead of fallback to week stats (which would be incorrect)
            console.error('Failed to load total token stats:', error);
            document.getElementById('stat-tokens').textContent = '-';
            showAlert('Failed to load token statistics', 'error');
        }

        // Organization distribution - Top 10 by token usage (active schools)
        const dist = document.getElementById('org-distribution');
        const tokenStatsByOrg = stats.token_stats_by_org || {};
        const usersByOrg = stats.users_by_org || {};
        
        // Sort by total token usage (descending) to show most active schools
        const sortedOrgs = Object.entries(tokenStatsByOrg)
            .sort((a, b) => (b[1].total_tokens || 0) - (a[1].total_tokens || 0))
            .slice(0, 10);  // Take top 10 only
        
        if (sortedOrgs.length === 0) {
            dist.innerHTML = '<div style="color:#64748b;text-align:center;padding:2rem;"><span class="lang-zh">暂无活跃学校数据</span><span class="lang-en">No active schools yet</span><span class="lang-az">Hələ aktiv məktəb yoxdur</span></div>';
        } else {
            dist.innerHTML = sortedOrgs.map(([org, orgTokenStats], index) => {
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
                
                // Get user count for this organization
                const userCount = usersByOrg[org] || 0;
                
                // Get token stats
                const inputTokens = orgTokenStats.input_tokens || 0;
                const outputTokens = orgTokenStats.output_tokens || 0;
                const formattedInput = formatTokenNumber(inputTokens);
                const formattedOutput = formatTokenNumber(outputTokens);
                const tokenDisplay = inputTokens > 0 || outputTokens > 0 
                    ? `${formattedInput}+${formattedOutput}` 
                    : '0';
                
                // Get organization ID if available
                const orgId = orgTokenStats.org_id || null;
                const orgNameEscaped = org.replace(/"/g, '&quot;').replace(/'/g, '&#39;');
                const orgIdValue = orgId !== null ? orgId : '';
                
                return `
                    <div style="display:flex;align-items:center;gap:1rem;padding:0.75rem;border-bottom:1px solid #e2e8f0;transition:background 0.2s;cursor:pointer;" 
                         onmouseover="this.style.background='#f1f5f9';this.style.transform='translateX(2px)'" 
                         onmouseout="this.style.background='transparent';this.style.transform='translateX(0)'"
                         data-org-name="${orgNameEscaped}" 
                         data-org-id="${orgIdValue}"
                         onclick="showOrganizationTrendChart(this.dataset.orgName, this.dataset.orgId || null)">
                        <div style="min-width:50px;text-align:center;font-weight:700;padding:0.5rem;border-radius:8px;${rankStyle}">
                            ${rankBadge}
                        </div>
                        <div style="flex:1;font-weight:500;">
                            ${org}
                        </div>
                        <div style="font-weight:700;color:#10b981;font-size:1.1rem;min-width:120px;text-align:right;">
                            ${tokenDisplay} <span style="font-size:0.85rem;font-weight:400;color:#64748b;"><span class="lang-zh">Token</span><span class="lang-en">tokens</span><span class="lang-az">tokenlar</span></span>
                        </div>
                        <div style="font-weight:500;color:#64748b;font-size:0.95rem;min-width:80px;text-align:right;">
                            ${userCount} <span style="font-size:0.85rem;font-weight:400;"><span class="lang-zh">用户</span><span class="lang-en">users</span><span class="lang-az">istifadəçi</span></span>
                        </div>
                    </div>
                `;
            }).join('');
        }
        
        // Apply current language to newly injected content
        applyCurrentLanguage();
    } catch (error) {
        showAlert('加载统计数据失败 Failed to load stats', 'error');
    }
}

// Token Statistics

