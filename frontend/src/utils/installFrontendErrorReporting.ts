/**
 * Install global frontend error reporting (production only).
 */
import type { App } from 'vue'

import { reportFrontendError } from '@/utils/frontendLog'
import { reloadForStaleChunk } from '@/utils/staleChunkReload'

function tryReloadStaleAssetTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLScriptElement) && !(target instanceof HTMLLinkElement)) {
    return false
  }
  const href = target instanceof HTMLScriptElement ? target.src : target.href
  if (!href || !href.includes('/assets/')) {
    return false
  }
  const synthetic =
    target instanceof HTMLLinkElement
      ? `Unable to preload CSS for ${href}`
      : `Failed to fetch dynamically imported module: ${href}`
  return reloadForStaleChunk(synthetic)
}

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
      tryReloadStaleAssetTarget(event.target)
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
