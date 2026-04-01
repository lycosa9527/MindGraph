/**
 * useNotifications — unified ElNotification helpers (RTL-aware placement)
 */
import { h, ref } from 'vue'

import { ElNotification } from 'element-plus'
import type { MessageHandler } from 'element-plus'

import { AlertTriangle } from 'lucide-vue-next'

import {
  getDefaultElNotificationOptions,
  notify,
  showLoading as showLoadingImpl,
} from './notifications'
import type { NotificationType } from './notifications'

export type { NotificationType } from './notifications'

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
    duration = 4000
  ): MessageHandler {
    notify[type](message, duration)
    return { close: () => {} } as MessageHandler
  }

  function showNotification(options: NotificationOptions): void {
    ElNotification({
      ...getDefaultElNotificationOptions(),
      title: options.title,
      message: options.message,
      type: options.type || 'info',
      duration: options.duration ?? 4000,
      showClose: options.showClose ?? true,
      onClick: options.onClick,
    })
  }

  function showLoading(message = 'Loading...'): MessageHandler {
    if (loading.value) {
      loading.value.close()
    }
    loading.value = showLoadingImpl(message)
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
        ...getDefaultElNotificationOptions(),
        title,
        message,
        type,
        duration: 0,
        showClose: true,
        onClose: () => resolve(false),
        onClick: () => resolve(true),
        icon: h(AlertTriangle, { size: 20 }),
      })
    })
  }

  return {
    success: notify.success,
    error: notify.error,
    warning: notify.warning,
    info: notify.info,
    showMessage,
    showNotification,
    showLoading,
    hideLoading,
    confirm,
  }
}
