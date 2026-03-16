/**
 * Language Composable - i18n switching
 * Migrated from language-manager.js
 */
import { computed } from 'vue'

import { type Language, useUIStore } from '@/stores/ui'

// Translation dictionaries - exported for use in stores
export const translations: Record<Language, Record<string, string>> = {
  en: {
    // Common
    'common.save': 'Save',
    'common.cancel': 'Cancel',
    'common.delete': 'Delete',
    'common.edit': 'Edit',
    'common.confirm': 'Confirm',
    'common.close': 'Close',
    'common.loading': 'Loading...',
    'common.success': 'Success',
    'common.error': 'Error',
    'common.warning': 'Warning',
    'common.refresh': 'Refresh',

    // Auth
    'auth.login': 'Login',
    'auth.register': 'Register',
    'auth.logout': 'Logout',
    'auth.username': 'Username',
    'auth.phone': 'Phone Number',
    'auth.password': 'Password',
    'auth.captcha': 'Captcha',
    'auth.enterCaptcha': 'Enter captcha',
    'auth.clickToRefresh': 'Click image to refresh',
    'auth.loginFailed': 'Login failed',
    'auth.sessionExpired': 'Session expired. Please login again.',
    'auth.smsLogin': 'SMS Login',
    'auth.resetPassword': 'Reset Password',
    'auth.backToLogin': 'Back to Login',

    // Editor
    'editor.newDiagram': 'New Diagram',
    'editor.saveDiagram': 'Save Diagram',
    'editor.exportImage': 'Export Image',
    'editor.undo': 'Undo',
    'editor.redo': 'Redo',
    'editor.zoomIn': 'Zoom In',
    'editor.zoomOut': 'Zoom Out',
    'editor.fitToScreen': 'Fit to Screen',
    'editor.selectDiagramType': 'Select Diagram Type',
    'editor.autoSavedAt': 'Auto-saved at {time}',
    'editor.clickToSave': 'Click to save',

    // Diagram nodes (matching old JS languageManager)
    'diagram.newAttribute': 'New Attribute',
    'diagram.newBranch': 'New Branch',
    'diagram.newSubitem': 'Sub-item',
    'diagram.newStep': 'New Step',
    'diagram.newSubstep': 'New Substep',
    'diagram.newPart': 'New Part',
    'diagram.newChild': 'New Child',
    'diagram.relationshipPlaceholder': 'Enter relationship...',
    'diagram.aiGenerating': 'AI...',
    'diagram.relationship': 'Relationship',
    'diagram.pressNumberToSelect': 'Press 1–5 to select',

    // Panels
    'panel.mindmate': 'MindMate AI',
    'panel.nodePalette': 'Node Palette',
    'panel.properties': 'Properties',

    // AskOnce
    'askonce.title': 'AskOnce',

    // Admin
    'admin.title': 'Admin Panel',
    'admin.orgManagement': 'Organization Management',
    'admin.dashboard': 'Dashboard',
    'admin.users': 'Users',
    'admin.schools': 'Schools',
    'admin.roleControl': 'Role Control',
    'admin.roleControlDesc': 'Manage admin access. Users with admin role can access the management panel.',
    'admin.addAdmin': 'Add Admin',
    'admin.revokeAdmin': 'Revoke Admin',
    'admin.revokeAdminConfirm': 'Revoke admin access from',
    'admin.grantAdmin': 'Grant Admin',
    'admin.adminRoleGranted': 'Admin role granted',
    'admin.adminRoleRevoked': 'Admin role revoked',
    'admin.envAdmins': 'Environment-configured Admins',
    'admin.envAdminsNote': 'Configured via ADMIN_PHONES in .env (read-only)',
    'admin.source': 'Source',
    'admin.sourceEnv': 'Env (.env)',
    'admin.sourceDatabase': 'Database',
    'admin.searchUserByNameOrPhone': 'Search by name or phone',
    'admin.noUsersFound': 'No users found',
    'admin.confirm': 'Confirm',
    'admin.schoolDashboard': 'School Dashboard',
    'admin.viewSchool': 'View school',
    'admin.selectSchool': 'Select school',
    'admin.schoolDashboardNoOrg': 'You must belong to a school to view the dashboard.',
    'admin.topUsersByTokens': 'Top Users by Token Usage',
    'admin.managers': 'Managers',
    'admin.setManager': 'Set as Manager',
    'admin.removeManager': 'Remove Manager',
    'admin.refreshInvitationCode': 'Refresh Invitation Code',
    'admin.invitationCode': 'Invitation Code',
    'admin.tokens': 'Token Usage',
    'admin.apiKeys': 'API Keys',
    'admin.geweWechat': 'Gewe WeChat',
    'admin.logs': 'Logs',
    'admin.announcements': 'Announcements',
    'admin.totalUsers': 'Total Users',
    'admin.activeToday': 'Active Today',
    'admin.totalDiagrams': 'Total Diagrams',
    'admin.apiCalls': 'API Calls',
    'admin.userActivity': 'User Activity',
    'admin.viewAll': 'View All',
    'admin.chartPlaceholderUserActivity': 'Chart placeholder - User activity over time',
    'admin.diagramTypes': 'Diagram Types',
    'admin.chartPlaceholderDiagramTypes': 'Chart placeholder - Diagram type distribution',
    'admin.userManagement': 'User Management',
    'admin.addUser': 'Add User',
    'admin.userManagementPlaceholder': 'User management interface will be implemented here',
    'admin.loadingTokenStats': 'Loading token statistics...',
    'admin.tokenUsageByService': 'Token Usage by Service',
    'admin.tokenUsageCompare':
      'Compare token usage between MindGraph (diagrams) and MindMate (AI assistant)',
    'admin.diagramGeneration': 'Diagram Generation',
    'admin.aiAssistant': 'AI Assistant (Dify)',
    'admin.today': 'Today',
    'admin.thisWeek': 'This Week',
    'admin.thisMonth': 'This Month',
    'admin.allTime': 'All Time',
    'admin.requests': 'requests',
    'admin.inputTokens': 'Input Tokens (All Time)',
    'admin.outputTokens': 'Output Tokens (All Time)',
    'admin.overallTokenSummary': 'Overall Token Usage Summary',
    'admin.pastWeek': 'Past Week',
    'admin.pastMonth': 'Past Month',
    'admin.noTokenStats': 'No token statistics available',
    'admin.loadStatistics': 'Load Statistics',
    'admin.inShort': 'In',
    'admin.outShort': 'Out',
    'admin.dashboardLoadError': 'Network error, failed to load dashboard stats',
    'admin.tokenStatsLoadError': 'Failed to load token stats',
    'admin.tokenStatsNetworkError': 'Network error, failed to load token stats',
    'admin.managementInterface': 'management interface',
    'admin.todayRegistrations': "Today's Registrations",
    'admin.topSchoolsByTokens': 'Top Schools by Token Usage',
    'admin.schoolName': 'School Name',
    'admin.search': 'Search',
    'admin.reset': 'Reset',
    'admin.actions': 'Actions',
    'admin.createSchool': 'Create School',
    'admin.editSchool': 'Edit School',
    'admin.createApiKey': 'Create API Key',
    'admin.editApiKey': 'Edit API Key',
    'admin.name': 'Name',
    'admin.phone': 'Phone',
    'admin.organization': 'Organization',
    'admin.tokensUsed': 'Tokens Used',
    'admin.registrationTime': 'Registration Time',
    'admin.status': 'Status',
    'admin.usersCount': 'Users',
    'admin.apiKey': 'API Key',
    'admin.usage': 'Usage',
    'admin.created': 'Created',
    'admin.lastUsed': 'Last Used',
    'admin.enabled': 'Enabled',
    'admin.disabled': 'Disabled',
    'admin.save': 'Save',
    'admin.cancel': 'Cancel',
    'admin.delete': 'Delete',
    'admin.refresh': 'Refresh',
    'admin.filterBySchool': 'Filter by School',
    'admin.allSchools': 'All Schools',
    'admin.previous': 'Previous',
    'admin.next': 'Next',
    'admin.noData': 'No data',
    'admin.loading': 'Loading...',
    'admin.description': 'Description',
    'admin.shareInviteTitle': 'Share Invitation',
    'admin.copyShareMessage': 'Copy',
    'admin.shareInviteMessage':
      'Dear School Administrator, we cordially invite you and your school team to experience MindGraph — our AI-powered mind map generation software, dedicated to developing teaching information platforms. Your school\'s exclusive invitation code is: {code} Please visit mg.mingspringedu.com to complete registration and begin efficient, intuitive visual collaboration. We look forward to contributing to your school\'s educational innovation.',
    'admin.trendChart': 'Trend Chart',
    'admin.trendUsers': 'Total Users Trend',
    'admin.trendOrganizations': 'Organizations Trend',
    'admin.trendRegistrations': 'Daily Registrations Trend',
    'admin.trendTokens': 'Token Usage Trend',
    'admin.trendOrgTokens': 'Token Usage by School',
    'admin.trendUserTokens': 'Token Usage by User',
    'admin.displayNameLabel': 'Sidebar Display Text',
    'admin.displayNameHint': 'Custom text shown in user sidebar (e.g. MindGraph Pro). Leave empty to use school name.',

    // Notifications
    'notification.saved': 'Changes saved successfully',
    'notification.copied': 'Copied to clipboard',
    'notification.copyFailed': 'Failed to copy',
    'notification.deleted': 'Item deleted successfully',
    'notification.sessionInvalidated':
      'You have been logged out because you exceeded the maximum number of devices',
    'notification.newVersionAvailable': 'New version available. Click to refresh.',
  },
  zh: {
    // Common
    'common.save': '保存',
    'common.cancel': '取消',
    'common.delete': '删除',
    'common.edit': '编辑',
    'common.confirm': '确认',
    'common.close': '关闭',
    'common.loading': '加载中...',
    'common.success': '成功',
    'common.error': '错误',
    'common.warning': '警告',
    'common.refresh': '刷新',

    // Auth
    'auth.login': '登录',
    'auth.register': '注册',
    'auth.logout': '退出登录',
    'auth.username': '用户名',
    'auth.phone': '手机号',
    'auth.password': '密码',
    'auth.captcha': '验证码',
    'auth.enterCaptcha': '请输入验证码',
    'auth.clickToRefresh': '点击图片刷新验证码',
    'auth.loginFailed': '登录失败',
    'auth.sessionExpired': '会话已过期，请重新登录。',
    'auth.smsLogin': '短信登录',
    'auth.resetPassword': '重置密码',
    'auth.backToLogin': '返回登录',
    'auth.forgotPassword': '忘记密码',

    // Editor
    'editor.newDiagram': '新建图表',
    'editor.saveDiagram': '保存图表',
    'editor.exportImage': '导出图片',
    'editor.undo': '撤销',
    'editor.redo': '重做',
    'editor.zoomIn': '放大',
    'editor.zoomOut': '缩小',
    'editor.fitToScreen': '适应屏幕',
    'editor.selectDiagramType': '选择图表类型',
    'editor.autoSavedAt': '已自动保存 {time}',
    'editor.clickToSave': '点击保存',

    // Diagram nodes (matching old JS languageManager)
    'diagram.newAttribute': '新属性',
    'diagram.newBranch': '新分支',
    'diagram.newSubitem': '子项',
    'diagram.newStep': '新步骤',
    'diagram.newSubstep': '新子步骤',
    'diagram.newPart': '新部分',
    'diagram.newChild': '新子项',
    'diagram.relationshipPlaceholder': '输入关系...',
    'diagram.aiGenerating': 'AI...',
    'diagram.relationship': '关系',
    'diagram.pressNumberToSelect': '按 1–5 选择',

    // Panels
    'panel.mindmate': 'MindMate AI 助手',
    'panel.nodePalette': '节点面板',
    'panel.properties': '属性',

    // AskOnce
    'askonce.title': '多应',

    // Admin
    'admin.title': '管理面板',
    'admin.orgManagement': '组织管理',
    'admin.dashboard': '仪表盘',
    'admin.users': '用户',
    'admin.schools': '学校',
    'admin.roleControl': '角色控制',
    'admin.roleControlDesc': '管理管理员权限。拥有管理员角色的用户可访问管理面板。',
    'admin.addAdmin': '添加管理员',
    'admin.revokeAdmin': '移除管理员',
    'admin.revokeAdminConfirm': '确定要移除以下用户的管理员权限：',
    'admin.grantAdmin': '授予管理员',
    'admin.adminRoleGranted': '已授予管理员权限',
    'admin.adminRoleRevoked': '已移除管理员权限',
    'admin.envAdmins': '环境变量配置的管理员',
    'admin.envAdminsNote': '通过 .env 中的 ADMIN_PHONES 配置（只读）',
    'admin.source': '来源',
    'admin.sourceEnv': '环境变量 (.env)',
    'admin.sourceDatabase': '数据库',
    'admin.searchUserByNameOrPhone': '按姓名或手机号搜索',
    'admin.noUsersFound': '未找到用户',
    'admin.confirm': '确定',
    'admin.schoolDashboard': '学校仪表盘',
    'admin.viewSchool': '查看学校',
    'admin.selectSchool': '选择学校',
    'admin.schoolDashboardNoOrg': '您需要属于某个学校才能查看仪表盘。',
    'admin.topUsersByTokens': '用户 Token 使用排行',
    'admin.managers': '管理员',
    'admin.setManager': '设为管理员',
    'admin.removeManager': '移除管理员',
    'admin.refreshInvitationCode': '刷新邀请码',
    'admin.invitationCode': '邀请码',
    'admin.tokens': 'Token使用量',
    'admin.apiKeys': 'API 密钥',
    'admin.geweWechat': 'Gewe 微信',
    'admin.logs': '日志',
    'admin.announcements': '公告',
    'admin.totalUsers': '总用户数',
    'admin.activeToday': '今日活跃',
    'admin.totalDiagrams': '总图表数',
    'admin.apiCalls': 'API 调用',
    'admin.userActivity': '用户活跃度',
    'admin.viewAll': '查看全部',
    'admin.chartPlaceholderUserActivity': '图表占位 - 用户活跃度随时间变化',
    'admin.diagramTypes': '图表类型',
    'admin.chartPlaceholderDiagramTypes': '图表占位 - 图表类型分布',
    'admin.userManagement': '用户管理',
    'admin.addUser': '添加用户',
    'admin.userManagementPlaceholder': '用户管理界面将在此实现',
    'admin.loadingTokenStats': '正在加载 Token 统计...',
    'admin.tokenUsageByService': '按服务统计 Token 使用量',
    'admin.tokenUsageCompare': '对比 MindGraph（图表）与 MindMate（AI 助手）的 Token 使用',
    'admin.diagramGeneration': '图表生成',
    'admin.aiAssistant': 'AI 助手 (Dify)',
    'admin.today': '今日',
    'admin.thisWeek': '本周',
    'admin.thisMonth': '本月',
    'admin.allTime': '全部',
    'admin.requests': '次请求',
    'admin.inputTokens': '输入 Token（全部）',
    'admin.outputTokens': '输出 Token（全部）',
    'admin.overallTokenSummary': 'Token 使用总览',
    'admin.pastWeek': '过去一周',
    'admin.pastMonth': '过去一月',
    'admin.noTokenStats': '暂无 Token 统计数据',
    'admin.loadStatistics': '加载统计',
    'admin.inShort': '输入',
    'admin.outShort': '输出',
    'admin.dashboardLoadError': '网络错误，加载仪表盘统计失败',
    'admin.tokenStatsLoadError': '加载 Token 统计失败',
    'admin.tokenStatsNetworkError': '网络错误，加载 Token 统计失败',
    'admin.managementInterface': '管理界面',
    'admin.todayRegistrations': '今日注册',
    'admin.topSchoolsByTokens': '学校 Token 使用排行',
    'admin.schoolName': '学校名称',
    'admin.search': '搜索',
    'admin.reset': '重置',
    'admin.actions': '操作',
    'admin.createSchool': '创建学校',
    'admin.editSchool': '编辑学校',
    'admin.createApiKey': '创建 API 密钥',
    'admin.editApiKey': '编辑 API 密钥',
    'admin.name': '姓名',
    'admin.phone': '手机号',
    'admin.organization': '学校',
    'admin.tokensUsed': 'Token 使用量',
    'admin.registrationTime': '注册时间',
    'admin.status': '状态',
    'admin.usersCount': '用户数',
    'admin.apiKey': 'API 密钥',
    'admin.usage': '使用量',
    'admin.created': '创建时间',
    'admin.lastUsed': '最后使用',
    'admin.enabled': '启用',
    'admin.disabled': '禁用',
    'admin.save': '保存',
    'admin.cancel': '取消',
    'admin.delete': '删除',
    'admin.refresh': '刷新',
    'admin.filterBySchool': '按学校筛选',
    'admin.allSchools': '全部学校',
    'admin.previous': '上一页',
    'admin.next': '下一页',
    'admin.noData': '暂无数据',
    'admin.loading': '加载中...',
    'admin.description': '描述',
    'admin.shareInviteTitle': '分享邀请',
    'admin.copyShareMessage': '复制',
    'admin.shareInviteMessage':
      '尊敬的校领导，您好！诚挚邀请您与学校团队体验 MindGraph —— 我们倾力打造的AI思维图示生成软件，致力于开发思维教学信息化平台。贵校的专属邀请码是：{code} 请您访问 mg.mingspringedu.com 完成注册，开启高效、直观的思维可视化协作。期待能为贵校的教育创新增添一份力量。',
    'admin.trendChart': '趋势图表',
    'admin.trendUsers': '总用户数趋势',
    'admin.trendOrganizations': '学校数量趋势',
    'admin.trendRegistrations': '每日注册趋势',
    'admin.trendTokens': 'Token 使用趋势',
    'admin.trendOrgTokens': '学校 Token 使用趋势',
    'admin.trendUserTokens': '用户 Token 使用趋势',
    'admin.displayNameLabel': '侧边栏显示文字',
    'admin.displayNameHint': '用户侧边栏显示的自定义文字（如 MindGraph专业版）。留空则显示学校名称。',

    // Notifications
    'notification.saved': '保存成功',
    'notification.copied': '已复制到剪贴板',
    'notification.copyFailed': '复制失败',
    'notification.deleted': '删除成功',
    'notification.sessionInvalidated': '您已被登出，因为登录设备数量超过上限',
    'notification.newVersionAvailable': '新版本已发布，点击刷新。',
  },
}

/** Dimension label translations (English → Chinese) for brace/tree map classification */
export const DIMENSION_TRANSLATIONS: Record<string, string> = {
  'Physical Characteristics': '物理特征',
  Parts: '组成部分',
  Components: '组件',
  Structure: '结构',
  Attributes: '属性',
  Properties: '属性',
  Types: '类型',
  Kinds: '种类',
  Categories: '类别',
  Characteristics: '特征',
  Features: '特点',
  Elements: '要素',
  Aspects: '方面',
  Factors: '因素',
}

export function translateDimension(value: string, toChinese: boolean): string {
  if (!toChinese || !value?.trim()) return value
  const trimmed = value.trim()
  return DIMENSION_TRANSLATIONS[trimmed] ?? trimmed
}

export function useLanguage() {
  const uiStore = useUIStore()

  const currentLanguage = computed(() => uiStore.language)
  const isZh = computed(() => uiStore.language === 'zh')
  const isEn = computed(() => uiStore.language === 'en')

  function t(key: string, fallback?: string): string {
    const dict = translations[uiStore.language]
    return dict[key] || fallback || key
  }

  function setLanguage(lang: Language): void {
    uiStore.setLanguage(lang)
  }

  function toggleLanguage(): void {
    uiStore.toggleLanguage()
  }

  function getNotification(key: string, ...args: unknown[]): string {
    let message = t(`notification.${key}`)

    // Simple template replacement
    args.forEach((arg, index) => {
      message = message.replace(`{${index}}`, String(arg))
    })

    return message
  }

  return {
    currentLanguage,
    isZh,
    isEn,
    t,
    setLanguage,
    toggleLanguage,
    getNotification,
  }
}
