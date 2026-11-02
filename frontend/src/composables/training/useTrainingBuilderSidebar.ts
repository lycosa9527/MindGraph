/**
 * Course builder wants the full width: collapse the app sidebar on entry
 * and restore the previous state when the teacher leaves.
 * List and editor share one route prefix, so this stays on the layout
 * that outlives both pages.
 */
import { onBeforeUnmount, watch } from 'vue'
import { useRoute } from 'vue-router'

import { useUIStore } from '@/stores/ui'
import { isTrainingBuilderPath } from '@/utils/trainingClient'

export function useTrainingBuilderSidebar(): void {
  const route = useRoute()
  const uiStore = useUIStore()
  let sidebarBeforeEntry: boolean | null = null

  function enter(): void {
    if (sidebarBeforeEntry !== null) return
    sidebarBeforeEntry = uiStore.sidebarCollapsed
    uiStore.setSidebarCollapsed(true)
  }

  function leave(): void {
    if (sidebarBeforeEntry === null) return
    uiStore.setSidebarCollapsed(sidebarBeforeEntry)
    sidebarBeforeEntry = null
  }

  watch(
    () => isTrainingBuilderPath(route.path),
    (active) => {
      if (active) enter()
      else leave()
    },
    { immediate: true }
  )

  onBeforeUnmount(leave)
}
