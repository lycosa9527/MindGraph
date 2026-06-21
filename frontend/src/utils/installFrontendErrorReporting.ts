/**
 * Install global frontend error reporting (production only).
 */
import type { App } from 'vue'

import { reportFrontendError } from '@/utils/frontendLog'

export function installFrontendErrorReporting(app: App): void {
  app.config.errorHandler = (err, instance, info) => {
    console.error('Vue Error:', err)
    console.error('Component:', instance)
    console.error('Info:', info)
    const componentName =
      instance && typeof instance === 'object' && '$options' in instance
        ? String((instance as { $options?: { name?: string } }).$options?.name ?? '')
        : ''
    reportFrontendError(err, {
      source: 'vue',
      info: [info, componentName].filter(Boolean).join(' | '),
    })
  }

  window.addEventListener('error', (event) => {
    if (event.target && event.target !== window) {
      return
    }
    reportFrontendError(event.error ?? event.message, { source: 'window.onerror' })
  })

  window.addEventListener('unhandledrejection', (event) => {
    reportFrontendError(event.reason, { source: 'unhandledrejection' })
  })
}
