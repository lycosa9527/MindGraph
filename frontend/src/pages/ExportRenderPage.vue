<script setup lang="ts">
/**
 * ExportRenderPage - Minimal page for server-side diagram screenshot export.
 *
 * Playwright navigates here with the diagram spec pre-loaded in sessionStorage.
 * Renders only DiagramCanvas (no auth, toolbar, sidebar, panels, etc.)
 * and signals completion via window.__MINDGRAPH_RENDER_COMPLETE.
 */
import { nextTick, onMounted } from 'vue'

import DiagramCanvas from '@/components/diagram/DiagramCanvas.vue'
import { eventBus } from '@/composables/core/useEventBus'
import { useDiagramStore } from '@/stores'
import { VALID_DIAGRAM_TYPES } from '@/stores/diagram/constants'
import type { DiagramType } from '@/types'

const EXPORT_SPEC_KEY = 'mindgraph_export_spec'

const diagramStore = useDiagramStore()

declare global {
  interface Window {
    __MINDGRAPH_RENDER_COMPLETE: boolean
    __MINDGRAPH_RENDER_ERROR: string | null
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

    eventBus.emit('view:fit_to_canvas_requested', { animate: false })

    await nextTick()
    await new Promise<void>((resolve) => setTimeout(resolve, 800))

    window.__MINDGRAPH_RENDER_COMPLETE = true
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
      :fit-view-on-init="true"
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
