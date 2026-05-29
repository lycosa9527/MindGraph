/**
 * Unified Notifications — ElNotification with RTL-aware corner placement
 * (LTR: top-right, RTL: top-left). Matches `document.documentElement.dir`.
 *
 * Use: import { notify } from '@/composables/core/notifications' for stores/outside setup
 * Or: useNotifications() composable for components
 */
import { h } from 'vue'

import { ElMessage, ElNotification } from 'element-plus'
import type { MessageHandler } from 'element-plus'

import { AlertTriangle, Check, CircleX, Info } from '@lucide/vue'

let programmaticStylesPromise: Promise<void> | null = null

/** Load Message / MessageBox / Notification / Loading CSS once (not auto-resolved by unplugin). */
export function ensureElementPlusProgrammaticStyles(): Promise<void> {
  if (!programmaticStylesPromise) {
    programmaticStylesPromise = Promise.all([
      import('element-plus/es/components/loading/style/css'),
      import('element-plus/es/components/message-box/style/css'),
      import('element-plus/es/components/message/style/css'),
      import('element-plus/es/components/notification/style/css'),
    ]).then(() => undefined)
  }
  return programmaticStylesPromise
}

export type NotificationType = 'success' | 'warning' | 'info' | 'error'

export type ElNotificationCornerPosition = 'top-left' | 'top-right'

/** Shared defaults for programmatic ElNotification (position mirrors for RTL). */
export function getDefaultElNotificationOptions(): {
  customClass: string
  position: ElNotificationCornerPosition
  offset: number
  showClose: boolean
} {
  const rtl = typeof document !== 'undefined' && document.documentElement.dir === 'rtl'
  return {
    customClass: 'dark-alert-notification',
    position: rtl ? 'top-left' : 'top-right',
    offset: 16,
    showClose: true,
  }
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
    ...getDefaultElNotificationOptions(),
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
