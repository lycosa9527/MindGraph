/**
 * Notifications Composable - Toast notifications
 * Migrated from notification-manager.js
 */
import { ref } from 'vue'

import { ElMessage, ElNotification } from 'element-plus'
import type { MessageHandler } from 'element-plus'

export type NotificationType = 'success' | 'warning' | 'info' | 'error'

export interface NotificationOptions {
  title?: string
  message: string
  type?: NotificationType
  duration?: number
  showClose?: boolean
  onClick?: () => void
}

export function useNotifications() {
  const loading = ref<MessageHandler | null>(null)

  function showMessage(
    message: string,
    type: NotificationType = 'info',
    duration = 3000
  ): MessageHandler {
    return ElMessage({
      message,
      type,
      duration,
      showClose: true,
    })
  }

  function success(message: string, duration = 3000): MessageHandler {
    return showMessage(message, 'success', duration)
  }

  function error(message: string, duration = 5000): MessageHandler {
    return showMessage(message, 'error', duration)
  }

  function warning(message: string, duration = 4000): MessageHandler {
    return showMessage(message, 'warning', duration)
  }

  function info(message: string, duration = 3000): MessageHandler {
    return showMessage(message, 'info', duration)
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
