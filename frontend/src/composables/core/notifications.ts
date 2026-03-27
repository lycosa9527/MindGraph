/**
 * Unified Notifications - Top-right ElNotification style
 * All app notifications use this for consistent UX (AI content, etc.)
 *
 * Use: import { notify } from '@/composables/core/notifications' for stores/outside setup
 * Or: useNotifications() composable for components
 */
import { h } from 'vue'

import { ElMessage, ElNotification } from 'element-plus'
import type { MessageHandler } from 'element-plus'

import { AlertTriangle, Check, CircleX, Info } from 'lucide-vue-next'

export type NotificationType = 'success' | 'warning' | 'info' | 'error'

const NOTIFICATION_OPTIONS = {
  customClass: 'dark-alert-notification',
  position: 'top-right' as const,
  offset: 16,
  showClose: true,
}

const DEFAULT_DURATION_MS = 4000

const iconMap = {
  success: Check,
  error: CircleX,
  warning: AlertTriangle,
  info: Info,
}

function showNotification(
  message: string,
  type: NotificationType,
  duration = DEFAULT_DURATION_MS
): void {
  const IconComponent = iconMap[type]
  const durationMs = duration > 0 ? duration : DEFAULT_DURATION_MS
  ElNotification({
    message,
    type,
    duration: durationMs,
    ...NOTIFICATION_OPTIONS,
    icon: h(IconComponent, { size: 20 }),
  })
}

export const notify = {
  success(message: string, duration = DEFAULT_DURATION_MS): void {
    showNotification(message, 'success', duration)
  },
  error(message: string, duration = DEFAULT_DURATION_MS): void {
    showNotification(message, 'error', duration)
  },
  warning(message: string, duration = DEFAULT_DURATION_MS): void {
    showNotification(message, 'warning', duration)
  },
  info(message: string, duration = DEFAULT_DURATION_MS): void {
    showNotification(message, 'info', duration)
  },
}

export function showLoading(message = 'Loading...'): MessageHandler {
  return ElMessage({
    message,
    type: 'info',
    duration: 0,
    showClose: false,
  })
}
