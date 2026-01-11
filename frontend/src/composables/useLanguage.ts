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

    // Diagram nodes (matching old JS languageManager)
    'diagram.newAttribute': 'New Attribute',
    'diagram.newBranch': 'New Branch',
    'diagram.newSubitem': 'Sub-item',
    'diagram.newStep': 'New Step',
    'diagram.newSubstep': 'New Substep',
    'diagram.newPart': 'New Part',
    'diagram.newChild': 'New Child',

    // Panels
    'panel.mindmate': 'MindMate AI',
    'panel.nodePalette': 'Node Palette',
    'panel.properties': 'Properties',

    // AskOnce
    'askonce.title': 'AskOnce',

    // Notifications
    'notification.saved': 'Changes saved successfully',
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

    // Diagram nodes (matching old JS languageManager)
    'diagram.newAttribute': '新属性',
    'diagram.newBranch': '新分支',
    'diagram.newSubitem': '子项',
    'diagram.newStep': '新步骤',
    'diagram.newSubstep': '新子步骤',
    'diagram.newPart': '新部分',
    'diagram.newChild': '新子项',

    // Panels
    'panel.mindmate': 'MindMate AI 助手',
    'panel.nodePalette': '节点面板',
    'panel.properties': '属性',

    // AskOnce
    'askonce.title': '多应',

    // Notifications
    'notification.saved': '保存成功',
    'notification.deleted': '删除成功',
    'notification.sessionInvalidated': '您已被登出，因为登录设备数量超过上限',
    'notification.newVersionAvailable': '新版本已发布，点击刷新。',
  },
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
