<script setup lang="ts">
/**
 * ExportRenderPage - Minimal page for server-side diagram screenshot export.
 *
 * Playwright navigates here with the diagram spec pre-loaded in sessionStorage.
 * Renders only DiagramCanvas (no auth, toolbar, sidebar, panels, etc.)
 *
 * Sequence: first fit (wait for `view:fit_completed` + `waitForNextPaint`) →
 * set `__MINDGRAPH_EXPORT_HEADLESS_CLICK_PENDING`. Playwright clicks the Vue Flow
 * pane, then calls `__MINDGRAPH_EXPORT_finalize()` (second fit + paint) which sets
 * `__MINDGRAPH_RENDER_COMPLETE`. No fixed delays; timing is event + rAF driven.
 *
 * `fit-view-on-init` is off so DiagramCanvas does not schedule its own delayed fit
 * (e.g. FIT_VIEWPORT_DELAY) on top of this page’s explicit `forExport` fits.
 */
import { nextTick, onMounted } from 'vue'

import DiagramCanvas from '@/components/diagram/DiagramCanvas.vue'
import { eventBus } from '@/composables/core/useEventBus'
import { useDiagramStore } from '@/stores'
import { VALID_DIAGRAM_TYPES } from '@/stores/diagram/constants'
import type { DiagramType } from '@/types'
import { waitForNextPaint } from '@/utils/diagramHtmlToImage'

const EXPORT_SPEC_KEY = 'mindgraph_export_spec'
/** Fails if `view:fit_completed` never fires (e.g. zero nodes so fit is a no-op). Shorter than server poll window. */
const EXPORT_FIT_SAFETY_TIMEOUT_MS = 19_000

function waitForFitCompletedSafety(): Promise<void> {
  return new Promise((resolve, reject) => {
    let off: (() => void) | null = null
    const timer = window.setTimeout(() => {
      if (off) {
        off()
        off = null
      }
      reject(
        new Error(
          'Timed out waiting for view:fit_completed (export safety; empty diagram or fit did not run)'
        )
      )
    }, EXPORT_FIT_SAFETY_TIMEOUT_MS)
    off = eventBus.once('view:fit_completed', () => {
      window.clearTimeout(timer)
      resolve()
    })
  })
}

const diagramStore = useDiagramStore()

declare global {
  interface Window {
    __MINDGRAPH_RENDER_COMPLETE: boolean
    __MINDGRAPH_RENDER_ERROR: string | null
    /** True when initial fit + paint done; Playwright should click the pane then call finalize. */
    __MINDGRAPH_EXPORT_HEADLESS_CLICK_PENDING: boolean
    __MINDGRAPH_EXPORT_finalize: () => Promise<void>
  }
}

window.__MINDGRAPH_RENDER_COMPLETE = false
window.__MINDGRAPH_RENDER_ERROR = null

onMounted(async () => {
  try {
    const specJson = sessionStorage.getItem(EXPORT_SPEC_KEY)
    if (!specJson) {
      window.__MINDGRAPH_RENDER_ERROR = 'No spec found in sessionStorage'
      window.__MINDGRAPH_RENDER_COMPLETE = true
      return
    }

    sessionStorage.removeItem(EXPORT_SPEC_KEY)

    const spec = JSON.parse(specJson) as Record<string, unknown>
    const diagramType = (spec.type as DiagramType) || null

    if (!diagramType || !VALID_DIAGRAM_TYPES.includes(diagramType)) {
      window.__MINDGRAPH_RENDER_ERROR = `Invalid diagram type: ${diagramType}`
      window.__MINDGRAPH_RENDER_COMPLETE = true
      return
    }

    const loaded = diagramStore.loadFromSpec(spec, diagramType)
    if (!loaded) {
      window.__MINDGRAPH_RENDER_ERROR = 'loadFromSpec returned false'
      window.__MINDGRAPH_RENDER_COMPLETE = true
      return
    }

    await nextTick()

    const firstFitDone = waitForFitCompletedSafety()
    eventBus.emit('view:fit_to_canvas_requested', { animate: false, forExport: true })
    await firstFitDone
    await waitForNextPaint()

    window.__MINDGRAPH_EXPORT_finalize = async () => {
      try {
        await nextTick()
        // Playwright has performed a real pane click (same as user pane click on the background).
        const secondFitDone = waitForFitCompletedSafety()
        eventBus.emit('view:fit_to_canvas_requested', { animate: false, forExport: true })
        await secondFitDone
        await waitForNextPaint()
        window.__MINDGRAPH_RENDER_COMPLETE = true
      } catch (err) {
        window.__MINDGRAPH_RENDER_ERROR = String(err)
        window.__MINDGRAPH_RENDER_COMPLETE = true
        throw err
      }
    }
    window.__MINDGRAPH_EXPORT_HEADLESS_CLICK_PENDING = true
  } catch (error) {
    window.__MINDGRAPH_RENDER_ERROR = String(error)
    window.__MINDGRAPH_RENDER_COMPLETE = true
  }
})
</script>

<template>
  <div class="export-render-container">
    <DiagramCanvas
      :show-background="false"
      :show-minimap="false"
      :fit-view-on-init="false"
    />
  </div>
</template>

<style scoped>
.export-render-container {
  width: 100vw;
  height: 100vh;
  background: #ffffff;
  overflow: hidden;
}
</style>
