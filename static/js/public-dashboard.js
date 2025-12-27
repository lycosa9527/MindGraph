// Public Dashboard JavaScript

let chart = null;
let eventSource = null;
let chinaGeoJSON = null;

// Bilingual Support (Default: Chinese)
const translations = {
    zh: {
        'stats-title': '统计信息',
        'connected-users': '在线用户',
        'registered-users': '注册用户',
        'tokens-today': '今日tokens',
        'total-tokens': '总tokens',
        'map-title': '当前用户分布',
        'map-subtitle': '实时用户分布地图',
        'activity-title': '实时动态',
        'has-generated': '已生成',
        'about': '关于',
        'users': '用户',
        'active-users': '在线用户',
        'stat-label-active-now': '当前在线',
        'stat-label-total-users': '总用户数',
        'stat-label-today': '今日',
        'stat-label-all-time': '总计',
        // Diagram type translations
        'mind_map': '思维导图',
        'concept_map': '概念图',
        'bubble_map': '气泡图',
        'double_bubble_map': '双气泡图',
        'tree_map': '树状图',
        'brace_map': '括号图',
        'flow_map': '流程图',
        'multi_flow_map': '复流程图',
        'bridge_map': '桥状图',
        'circle_map': '圆圈图',
        'factor_analysis': '要素分析',
        'three_position_analysis': '三位置分析',
        'perspective_analysis': '视角分析',
        'goal_analysis': '目标分析',
        'possibility_analysis': '可能性分析',
        'result_analysis': '结果分析',
        'five_w_one_h': '5W1H分析',
        'whwm_analysis': 'WHWM分析',
        'four_quadrant': '四象限图'
    },
    en: {
        'stats-title': 'Statistics',
        'connected-users': 'Connected Users',
        'registered-users': 'Registered Users',
        'tokens-today': 'Tokens Used Today',
        'total-tokens': 'Total Tokens Used',
        'map-title': 'Current Users by City',
        'map-subtitle': 'Real-time User Distribution Across China',
        'activity-title': 'Live Activity',
        'has-generated': 'has generated',
        'about': 'about',
        'users': 'users',
        'active-users': 'Active Users',
        'stat-label-active-now': 'Active Now',
        'stat-label-total-users': 'Total Users',
        'stat-label-today': 'Today',
        'stat-label-all-time': 'All Time',
        // Diagram type translations
        'mind_map': 'Mind Map',
        'concept_map': 'Concept Map',
        'bubble_map': 'Bubble Map',
        'double_bubble_map': 'Double Bubble Map',
        'tree_map': 'Tree Map',
        'brace_map': 'Brace Map',
        'flow_map': 'Flow Map',
        'multi_flow_map': 'Multi Flow Map',
        'bridge_map': 'Bridge Map',
        'circle_map': 'Circle Map',
        'factor_analysis': 'Factor Analysis',
        'three_position_analysis': 'Three Position Analysis',
        'perspective_analysis': 'Perspective Analysis',
        'goal_analysis': 'Goal Analysis',
        'possibility_analysis': 'Possibility Analysis',
        'result_analysis': 'Result Analysis',
        'five_w_one_h': '5W1H Analysis',
        'whwm_analysis': 'WHWM Analysis',
        'four_quadrant': 'Four Quadrant'
    }
};

// Format diagram type for display
function formatDiagramType(diagramType) {
    // Check if translation exists
    if (translations[currentLang][diagramType]) {
        return translations[currentLang][diagramType];
    }
    // Fallback: convert snake_case to Title Case
    return diagramType
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ');
}

// Get saved language or default to Chinese
let currentLang = localStorage.getItem('dashboard-lang') || 'zh';

// Apply translations
function applyTranslations() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        if (translations[currentLang][key]) {
            el.textContent = translations[currentLang][key];
        }
    });
    
    // Update language button
    const langText = document.getElementById('langText');
    if (langText) {
        langText.textContent = currentLang === 'zh' ? 'English' : '中文';
    }
}

// Toggle language
function toggleLanguage() {
    currentLang = currentLang === 'zh' ? 'en' : 'zh';
    localStorage.setItem('dashboard-lang', currentLang);
    applyTranslations();
}

// Initialize dashboard
document.addEventListener('DOMContentLoaded', async function() {
    // Apply translations
    applyTranslations();
    
    // Load China geoJSON
    await loadChinaGeoJSON();
    
    // Initialize ECharts map
    initializeMap();
    
    // Load initial data
    await loadStats();
    await loadMapData();
    
    // Connect to activity stream
    connectActivityStream();
    
    // Set up periodic updates
    setInterval(loadStats, 10000);  // Update stats every 10 seconds
    setInterval(loadMapData, 30000);  // Update map every 30 seconds
});

async function loadChinaGeoJSON() {
    try {
        const response = await fetch('/static/data/china-geo.json');
        if (response.ok) {
            chinaGeoJSON = await response.json();
            console.log('China geoJSON loaded successfully');
            
            // Register map immediately if chart is already initialized
            if (chart && chinaGeoJSON) {
                try {
                    echarts.registerMap('china', chinaGeoJSON);
                    console.log('China map registered successfully');
                    // Re-initialize map to apply the registered map
                    if (chart) {
                        chart.setOption({
                            geo: {
                                map: 'china'
                            },
                            series: [{
                                map: 'china'
                            }]
                        }, { notMerge: false });
                    }
                } catch (regError) {
                    console.error('Error registering China map:', regError);
                }
            }
        } else {
            console.error('Failed to load China geoJSON: HTTP', response.status);
            throw new Error(`Failed to load GeoJSON: HTTP ${response.status}`);
        }
    } catch (error) {
        console.error('Error loading China geoJSON:', error);
        // Show user-friendly error message
        const mapContainer = document.getElementById('china-map');
        if (mapContainer) {
            mapContainer.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 100%; color: #e2e8f0; font-size: 16px;">地图数据加载失败，请刷新页面重试</div>';
        }
    }
}

function initializeMap() {
    const mapContainer = document.getElementById('china-map');
    if (!mapContainer) {
        console.error('Map container not found');
        return;
    }
    
    // Check if ECharts is available
    if (typeof echarts === 'undefined') {
        console.error('ECharts library not loaded');
        mapContainer.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 100%; color: #e2e8f0; font-size: 16px;">ECharts 库未加载，请刷新页面重试</div>';
        return;
    }
    
    chart = echarts.init(mapContainer, 'dark');
    
    // Register China map if geoJSON is loaded
    if (chinaGeoJSON) {
        try {
            echarts.registerMap('china', chinaGeoJSON);
            console.log('China map registered during initialization');
        } catch (error) {
            console.error('Error registering China map during initialization:', error);
        }
    } else {
        console.warn('China geoJSON not loaded yet, map will be registered when GeoJSON loads');
    }
    
    // Enhanced map configuration with premium styling and province highlighting
    const option = {
        backgroundColor: 'transparent',
        visualMap: {
            show: true,
            min: 0,
            max: 50,
            left: 'left',
            top: 'bottom',
            text: ['高', '低'],
            textStyle: {
                color: '#e2e8f0'
            },
            inRange: {
                color: ['#0f172a', '#1e293b', '#1e40af', '#3b82f6', '#60a5fa', '#a78bfa', '#f472b6']
            },
            calculable: true,
            realtime: true,
            itemWidth: 15,
            itemHeight: 150,
            borderWidth: 2,
            borderColor: '#334155',
            backgroundColor: 'rgba(30, 41, 59, 0.8)',
            textGap: 10
        },
        geo: {
            map: 'china',
            roam: true,
            zoom: 1.2,
            center: [105, 36],
            itemStyle: {
                areaColor: {
                    type: 'linear',
                    x: 0,
                    y: 0,
                    x2: 0,
                    y2: 1,
                    colorStops: [
                        { offset: 0, color: '#0f172a' },
                        { offset: 1, color: '#1e293b' }
                    ]
                },
                borderColor: '#334155',
                borderWidth: 1.5,
                shadowColor: 'rgba(0, 0, 0, 0.5)',
                shadowBlur: 10
            },
            emphasis: {
                itemStyle: {
                    areaColor: {
                        type: 'linear',
                        x: 0,
                        y: 0,
                        x2: 0,
                        y2: 1,
                        colorStops: [
                            { offset: 0, color: '#3b82f6' },
                            { offset: 1, color: '#1e40af' }
                        ]
                    },
                    borderColor: '#60a5fa',
                    borderWidth: 3,
                    shadowColor: 'rgba(96, 165, 250, 0.8)',
                    shadowBlur: 30
                },
                label: {
                    show: true,
                    color: '#e2e8f0',
                    fontSize: 14,
                    fontWeight: 'bold',
                    textShadowBlur: 10,
                    textShadowColor: 'rgba(96, 165, 250, 0.8)'
                }
            },
            label: {
                show: true,
                color: '#94a3b8',
                fontSize: 11,
                fontWeight: 'normal'
            },
            regions: [{
                name: '南海诸岛',
                itemStyle: {
                    areaColor: 'rgba(0, 10, 52, 0)',
                    borderColor: 'rgba(0, 10, 52, 0)',
                    opacity: 0,
                    label: {
                        show: false,
                        color: 'rgba(0, 0, 0, 0)'
                    }
                }
            }]
        },
        series: [
            // Map series for province highlighting
            {
                name: '用户分布',
                type: 'map',
                map: 'china',
                geoIndex: 0,
                data: [],
                itemStyle: {
                    borderColor: '#334155',
                    borderWidth: 1.5,
                    shadowBlur: 10,
                    shadowColor: 'rgba(0, 0, 0, 0.5)'
                },
                emphasis: {
                    itemStyle: {
                        borderColor: '#60a5fa',
                        borderWidth: 3,
                        shadowBlur: 30,
                        shadowColor: 'rgba(96, 165, 250, 0.8)'
                    },
                    label: {
                        show: true,
                        color: '#e2e8f0',
                        fontSize: 14,
                        fontWeight: 'bold'
                    }
                },
                animation: true,
                animationDuration: 1000,
                animationEasing: 'cubicOut',
                animationDelay: function(idx) {
                    return idx * 50;
                }
            },
            // Scatter series for city points
            {
                name: '城市用户',
                type: 'scatter',
                coordinateSystem: 'geo',
                data: [],
                symbolSize: function(val) {
                    const baseSize = Math.sqrt(val[2]) * 4;
                    return Math.max(8, Math.min(baseSize, 40));  // Min 8, Max 40
                },
                itemStyle: {
                    color: function(params) {
                        // Gradient colors based on user count
                        const count = params.value[2];
                        if (count >= 20) return '#ef4444';  // Red for high activity
                        if (count >= 10) return '#f59e0b';  // Orange for medium-high
                        if (count >= 5) return '#eab308';   // Yellow for medium
                        return '#10b981';  // Green for low
                    },
                    shadowBlur: 20,
                    shadowColor: function(params) {
                        const count = params.value[2];
                        if (count >= 20) return 'rgba(239, 68, 68, 0.8)';
                        if (count >= 10) return 'rgba(245, 158, 11, 0.8)';
                        if (count >= 5) return 'rgba(234, 179, 8, 0.8)';
                        return 'rgba(16, 185, 129, 0.8)';
                    },
                    borderColor: '#ffffff',
                    borderWidth: 2,
                    opacity: 0.95
                },
                label: {
                    show: true,
                    formatter: function(params) {
                        return `${params.name}\n${params.value[2]} ${translations[currentLang]['users']}`;
                    },
                    position: 'right',
                    color: '#e2e8f0',
                    fontSize: 11,
                    fontWeight: 'bold',
                    backgroundColor: 'rgba(30, 41, 59, 0.9)',
                    padding: [4, 8],
                    borderRadius: 4,
                    borderColor: 'rgba(148, 163, 184, 0.3)',
                    borderWidth: 1
                },
                emphasis: {
                    itemStyle: {
                        shadowBlur: 30,
                        shadowColor: 'rgba(96, 165, 250, 0.9)',
                        borderWidth: 3,
                        borderColor: '#60a5fa'
                    },
                    label: {
                        fontSize: 13,
                        backgroundColor: 'rgba(59, 130, 246, 0.95)',
                        borderColor: '#60a5fa'
                    }
                },
                animation: true,
                animationDuration: 1000,
                animationEasing: 'cubicOut'
            }
        ],
        tooltip: {
            trigger: 'item',
            backgroundColor: 'rgba(30, 41, 59, 0.95)',
            backdropFilter: 'blur(10px)',
            borderColor: '#334155',
            borderWidth: 1,
            borderRadius: 8,
            padding: [12, 16],
            textStyle: {
                color: '#e2e8f0',
                fontSize: 13
            },
            formatter: function(params) {
                if (params.seriesType === 'scatter') {
                    const count = params.value[2];
                    const color = params.color;
                    return `
                        <div style="font-weight: bold; margin-bottom: 8px; font-size: 14px;">
                            ${params.name}
                        </div>
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span style="display: inline-block; width: 12px; height: 12px; background: ${color}; border-radius: 50%; box-shadow: 0 0 8px ${color};"></span>
                            <span>${translations[currentLang]['active-users']}: <strong style="color: #60a5fa;">${count}</strong></span>
                        </div>
                    `;
                } else if (params.seriesType === 'map') {
                    const count = params.value || 0;
                    const color = params.color || '#60a5fa';
                    return `
                        <div style="font-weight: bold; margin-bottom: 8px; font-size: 14px;">
                            ${params.name}
                        </div>
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span style="display: inline-block; width: 12px; height: 12px; background: ${color}; border-radius: 50%; box-shadow: 0 0 8px ${color};"></span>
                            <span>${translations[currentLang]['active-users']}: <strong style="color: #60a5fa;">${count}</strong></span>
                        </div>
                    `;
                }
                return params.name;
            }
        }
    };
    
    // Only set option if map is registered or we have a fallback
    try {
        chart.setOption(option);
        
        // Verify map was set correctly
        if (!chinaGeoJSON) {
            console.warn('Map initialized without GeoJSON - will update when GeoJSON loads');
        }
    } catch (error) {
        console.error('Error setting map option:', error);
        // If map registration failed, try to register again
        if (chinaGeoJSON) {
            try {
                echarts.registerMap('china', chinaGeoJSON);
                chart.setOption(option);
            } catch (retryError) {
                console.error('Retry failed:', retryError);
            }
        }
    }
    
    // Handle window resize with debounce
    let resizeTimer;
    window.addEventListener('resize', function() {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function() {
            if (chart) {
                chart.resize();
            }
        }, 250);
    });
}

// Animate number counting
function animateNumber(element, targetValue, duration = 1000) {
    const elementId = element.id;
    const currentValue = parseFloat(element.textContent.replace(/[^0-9.]/g, '')) || 0;
    const target = parseFloat(targetValue.toString().replace(/[^0-9.]/g, '')) || 0;
    
    if (currentValue === target) return;
    
    const startTime = performance.now();
    const isFormatted = targetValue.toString().includes('K') || targetValue.toString().includes('M');
    
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        // Easing function (ease-out)
        const easeOut = 1 - Math.pow(1 - progress, 3);
        const current = currentValue + (target - currentValue) * easeOut;
        
        if (isFormatted) {
            element.textContent = formatNumber(Math.round(current));
        } else {
            element.textContent = Math.round(current).toLocaleString();
        }
        
        // Add pulse effect during animation
        element.style.transform = `scale(${1 + Math.sin(progress * Math.PI * 4) * 0.05})`;
        
        if (progress < 1) {
            requestAnimationFrame(update);
        } else {
            element.style.transform = 'scale(1)';
            element.textContent = typeof targetValue === 'number' ? formatNumber(targetValue) : targetValue;
        }
    }
    
    requestAnimationFrame(update);
}

// Add ripple effect on stat card click
function addRippleEffect(event) {
    const card = event.currentTarget;
    const ripple = document.createElement('div');
    const rect = card.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    const x = event.clientX - rect.left - size / 2;
    const y = event.clientY - rect.top - size / 2;
    
    ripple.style.cssText = `
        position: absolute;
        width: ${size}px;
        height: ${size}px;
        left: ${x}px;
        top: ${y}px;
        background: radial-gradient(circle, rgba(96, 165, 250, 0.4) 0%, transparent 70%);
        border-radius: 50%;
        transform: scale(0);
        animation: ripple 0.6s ease-out;
        pointer-events: none;
        z-index: 0;
    `;
    
    card.appendChild(ripple);
    
    setTimeout(() => {
        ripple.remove();
    }, 600);
}

// Add ripple animation to CSS if not exists
if (!document.getElementById('ripple-style')) {
    const style = document.createElement('style');
    style.id = 'ripple-style';
    style.textContent = `
        @keyframes ripple {
            to {
                transform: scale(2);
                opacity: 0;
            }
        }
    `;
    document.head.appendChild(style);
}

async function loadStats() {
    try {
        const response = await fetch('/api/public/stats', {
            credentials: 'include'
        });
        
        if (!response.ok) {
            if (response.status === 401) {
                // Session expired - redirect to login
                window.location.href = '/pub-dash';
                return;
            }
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        // Update stats display with animated counting
        const updateStat = (elementId, value) => {
            const element = document.getElementById(elementId);
            if (element) {
                const formattedValue = typeof value === 'number' ? formatNumber(value) : value;
                const currentText = element.textContent;
                
                if (currentText !== formattedValue && currentText !== '-') {
                    // Animate number change
                    animateNumber(element, value, 800);
                } else if (currentText === '-') {
                    // First load - set immediately
                    element.textContent = formattedValue;
                }
            }
        };
        
        updateStat('connected-users', data.connected_users || 0);
        updateStat('registered-users', data.registered_users || 0);
        updateStat('tokens-today', data.tokens_used_today || 0);
        updateStat('total-tokens', data.total_tokens_used || 0);
        
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// Add click ripple effects to stat cards after DOM loads
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(() => {
        const statCards = document.querySelectorAll('.stat-card');
        statCards.forEach(card => {
            card.addEventListener('click', addRippleEffect);
        });
    }, 1000);
});

async function loadMapData() {
    try {
        const response = await fetch('/api/public/map-data', {
            credentials: 'include'
        });
        
        if (!response.ok) {
            if (response.status === 401) {
                // Session expired - redirect to login
                window.location.href = '/pub-dash';
                return;
            }
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        // Update map with smooth animation
        if (chart) {
            // Calculate max value for visual map scaling
            const mapMaxValue = data.map_data && data.map_data.length > 0 
                ? Math.max(...data.map_data.map(item => item.value), 1)
                : 1;
            const scatterMaxValue = data.series_data && data.series_data.length > 0
                ? Math.max(...data.series_data.map(item => item.value[2]), 1)
                : 1;
            const maxValue = Math.max(mapMaxValue, scatterMaxValue, 50);
            
            chart.setOption({
                visualMap: {
                    max: maxValue,
                    inRange: {
                        color: ['#0f172a', '#1e293b', '#1e40af', '#3b82f6', '#60a5fa', '#a78bfa', '#f472b6']
                    }
                },
                series: [
                    {
                        // Map series for province highlighting
                        name: '用户分布',
                        type: 'map',
                        map: 'china',
                        geoIndex: 0,
                        data: data.map_data || [],
                        itemStyle: {
                            borderColor: '#334155',
                            borderWidth: 1.5,
                            shadowBlur: 10,
                            shadowColor: 'rgba(0, 0, 0, 0.5)'
                        },
                        emphasis: {
                            itemStyle: {
                                borderColor: '#60a5fa',
                                borderWidth: 3,
                                shadowBlur: 30,
                                shadowColor: 'rgba(96, 165, 250, 0.8)'
                            },
                            label: {
                                show: true,
                                color: '#e2e8f0',
                                fontSize: 14,
                                fontWeight: 'bold'
                            }
                        },
                        animation: true,
                        animationDuration: 1000,
                        animationEasing: 'cubicOut',
                        animationDelay: function(idx) {
                            return idx * 30;
                        }
                    },
                    {
                        // Scatter series for city points
                        name: '城市用户',
                        type: 'scatter',
                        coordinateSystem: 'geo',
                        data: data.series_data || [],
                        symbolSize: function(val) {
                            return Math.sqrt(val[2]) * 8 + 5;
                        },
                        itemStyle: {
                            color: '#ef4444',
                            shadowBlur: 10,
                            shadowColor: 'rgba(239, 68, 68, 0.5)'
                        },
                        label: {
                            show: true,
                            formatter: '{b}\n{c[2]}',
                            position: 'right',
                            color: '#e2e8f0',
                            fontSize: 12
                        },
                        animation: true,
                        animationDuration: 800,
                        animationEasing: 'cubicOut'
                    }
                ]
            }, {
                notMerge: false,  // Merge with existing options to preserve geo component
                lazyUpdate: false
            });
        }
        
    } catch (error) {
        console.error('Error loading map data:', error);
    }
}

function connectActivityStream() {
    // Close existing connection if any
    if (eventSource) {
        eventSource.close();
    }
    
    // Connect to SSE stream
    eventSource = new EventSource('/api/public/activity-stream');
    
    eventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            
            if (data.type === 'activity') {
                addActivityItem(data);
            } else if (data.type === 'stats_update') {
                updateStatsFromStream(data);
            } else if (data.type === 'heartbeat') {
                // Keep connection alive
                console.debug('Heartbeat received');
            } else if (data.type === 'initial') {
                // Initial stats
                if (data.stats) {
                    updateStatsFromStream(data.stats);
                }
            } else if (data.type === 'error') {
                console.error('SSE error:', data.error);
            }
        } catch (error) {
            console.error('Error parsing SSE message:', error);
        }
    };
    
    eventSource.onerror = function(error) {
        console.error('SSE connection error:', error);
        // Attempt to reconnect after 5 seconds
        setTimeout(function() {
            if (eventSource && eventSource.readyState === EventSource.CLOSED) {
                console.log('Reconnecting to activity stream...');
                connectActivityStream();
            }
        }, 5000);
    };
}

function addActivityItem(data) {
    const activityStream = document.getElementById('activity-stream');
    if (!activityStream) return;
    
    const item = document.createElement('div');
    item.className = 'activity-item';
    
    const timestamp = new Date(data.timestamp).toLocaleTimeString();
    const formattedDiagramType = formatDiagramType(data.diagram_type || 'unknown');
    
    // Format based on language for better readability
    let activityText;
    if (currentLang === 'zh') {
        // Chinese: "已生成关于{topic}的{diagram_type}"
        activityText = `${translations[currentLang]['has-generated']}${translations[currentLang]['about']}<em>${escapeHtml(data.topic)}</em>的<strong>${escapeHtml(formattedDiagramType)}</strong>`;
    } else {
        // English: "has generated {diagram_type} about {topic}"
        activityText = `${translations[currentLang]['has-generated']} <strong>${escapeHtml(formattedDiagramType)}</strong> ${translations[currentLang]['about']} <em>${escapeHtml(data.topic)}</em>`;
    }
    
    item.innerHTML = `
        <span class="timestamp">${timestamp}</span>
        <strong>${escapeHtml(data.user)}</strong> ${activityText}
    `;
    
    // Add fade-in animation
    item.style.opacity = '0';
    item.style.transform = 'translateX(30px)';
    
    activityStream.insertBefore(item, activityStream.firstChild);
    
    // Trigger animation
    setTimeout(() => {
        item.style.transition = 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)';
        item.style.opacity = '1';
        item.style.transform = 'translateX(0)';
    }, 10);
    
    // Keep only last 50 items
    while (activityStream.children.length > 50) {
        const lastItem = activityStream.lastChild;
        lastItem.style.transition = 'all 0.3s ease-out';
        lastItem.style.opacity = '0';
        lastItem.style.transform = 'translateX(30px)';
        setTimeout(() => {
            if (lastItem.parentNode) {
                lastItem.parentNode.removeChild(lastItem);
            }
        }, 300);
    }
}

function updateStatsFromStream(data) {
    if (data.connected_users !== undefined) {
        const element = document.getElementById('connected-users');
        if (element) animateNumber(element, data.connected_users, 600);
    }
    if (data.registered_users !== undefined) {
        const element = document.getElementById('registered-users');
        if (element) animateNumber(element, data.registered_users, 600);
    }
    if (data.tokens_used_today !== undefined) {
        const element = document.getElementById('tokens-today');
        if (element) animateNumber(element, data.tokens_used_today, 600);
    }
    if (data.total_tokens_used !== undefined) {
        const element = document.getElementById('total-tokens');
        if (element) animateNumber(element, data.total_tokens_used, 600);
    }
}

function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
    }
    return num.toLocaleString();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    if (eventSource) {
        eventSource.close();
    }
});

