/**
 * useNotifications — unified ElNotification helpers (RTL-aware placement)
 */
import { type VNode, h, ref } from 'vue'

import type { MessageHandler } from 'element-plus'

import { AlertTriangle } from '@lucide/vue'

import { bilingualNotifyMessage } from '@/i18n/bilingualNotifyMessage'

import {
  getDefaultElNotificationOptions,
  loadElNotification,
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
    void loadElNotification().then((ElNotification) => {
      ElNotification({
        ...getDefaultElNotificationOptions(),
        title: options.title,
        message: options.message,
        type: options.type || 'info',
        duration: options.duration ?? 4000,
        showClose: options.showClose ?? true,
        onClick: options.onClick,
      })
    })
  }

  function showLoading(message: string | VNode = 'Loading...'): MessageHandler {
    if (loading.value) {
      loading.value.close()
    }
    loading.value = showLoadingImpl(message)
    return loading.value
  }

  function showLoadingKey(key: string, params?: Record<string, unknown>): MessageHandler {
    return showLoading(bilingualNotifyMessage(key, params))
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
    return loadElNotification().then(
      (ElNotification) =>
        new Promise<boolean>((resolve) => {
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
    )
  }

  return {
    success: notify.success,
    error: notify.error,
    warning: notify.warning,
    info: notify.info,
    successKey: notify.successKey,
    errorKey: notify.errorKey,
    warningKey: notify.warningKey,
    infoKey: notify.infoKey,
    showMessage,
    showNotification,
    showLoading,
    showLoadingKey,
    hideLoading,
    confirm,
  }
}
