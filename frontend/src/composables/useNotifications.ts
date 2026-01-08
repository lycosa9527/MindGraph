/**
 * Notifications Composable - Alert-style notifications at top of screen
 *
 * Features:
 * - Uses Element Plus ElNotification styled like el-alert
 * - Dark theme styling
 * - Type-specific icons
 * - Configurable durations per type
 * - Shows at top-right of screen
 */
import { h, ref } from 'vue'

import { ElMessage, ElNotification } from 'element-plus'
import type { MessageHandler } from 'element-plus'

import { AlertTriangle, Check, CircleX, Info } from 'lucide-vue-next'

export type NotificationType = 'success' | 'warning' | 'info' | 'error'

export interface NotificationOptions {
  title?: string
  message: string
  type?: NotificationType
  duration?: number
  showClose?: boolean
  onClick?: () => void
}

// Icon mapping for each notification type
const iconMap = {
  success: Check,
  error: CircleX,
  warning: AlertTriangle,
  info: Info,
}

export function useNotifications() {
  const loading = ref<MessageHandler | null>(null)

  function showAlert(message: string, type: NotificationType = 'info', duration = 3000): void {
    const IconComponent = iconMap[type]
    ElNotification({
      message,
      type,
      duration,
      showClose: true,
      icon: h(IconComponent, { size: 20 }),
      customClass: 'dark-alert-notification',
      position: 'top-right',
      offset: 16,
    })
  }

  function success(message: string, duration = 3000): void {
    showAlert(message, 'success', duration)
  }

  function error(message: string, duration = 5000): void {
    showAlert(message, 'error', duration)
  }

  function warning(message: string, duration = 5000): void {
    showAlert(message, 'warning', duration)
  }

  function info(message: string, duration = 3000): void {
    showAlert(message, 'info', duration)
  }

  // Legacy ElMessage for backward compatibility
  function showMessage(
    message: string,
    type: NotificationType = 'info',
    duration = 3000
  ): MessageHandler {
    const IconComponent = iconMap[type]
    return ElMessage({
      message,
      type,
      duration,
      showClose: true,
      icon: h(IconComponent, { size: 18 }),
      customClass: 'dark-message',
    })
  }

  function showNotification(options: NotificationOptions): void {
    ElNotification({
      title: options.title,
      message: options.message,
      type: options.type || 'info',
      duration: options.duration ?? 4500,
      showClose: options.showClose ?? true,
      onClick: options.onClick,
    })
  }

  function showLoading(message = 'Loading...'): MessageHandler {
    if (loading.value) {
      loading.value.close()
    }
    loading.value = ElMessage({
      message,
      type: 'info',
      duration: 0,
      showClose: false,
    })
    return loading.value
  }

  function hideLoading(): void {
    if (loading.value) {
      loading.value.close()
      loading.value = null
    }
  }

  function confirm(
    message: string,
    title = 'Confirm',
    type: NotificationType = 'warning'
  ): Promise<boolean> {
    return new Promise((resolve) => {
      ElNotification({
        title,
        message,
        type,
        duration: 0,
        showClose: true,
        onClose: () => resolve(false),
        onClick: () => resolve(true),
      })
    })
  }

  return {
    showMessage,
    success,
    error,
    warning,
    info,
    showNotification,
    showLoading,
    hideLoading,
    confirm,
  }
}
