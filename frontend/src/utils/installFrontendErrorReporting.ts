/**
 * Install global frontend error reporting (production only).
 */
import type { App } from 'vue'

import { reportFrontendError } from '@/utils/frontendLog'
import { reloadForStaleChunk } from '@/utils/staleChunkReload'

export function installFrontendErrorReporting(app: App): void {
  app.config.errorHandler = (err, instance, info) => {
    if (import.meta.env.DEV) {
      console.error('Vue Error:', err)
      console.error('Component:', instance)
      console.error('Info:', info)
    }
    if (reloadForStaleChunk(err)) {
      return
    }
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
    const payload = event.error ?? event.message
    if (reloadForStaleChunk(payload)) {
      return
    }
    reportFrontendError(payload, { source: 'window.onerror' })
  })

  window.addEventListener('unhandledrejection', (event) => {
    if (reloadForStaleChunk(event.reason)) {
      return
    }
    reportFrontendError(event.reason, { source: 'unhandledrejection' })
  })
}
