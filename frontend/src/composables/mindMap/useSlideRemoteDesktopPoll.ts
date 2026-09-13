/**
 * Drain 演讲模式 Start when the desktop is not on /canvas.
 * Canvas useSlideRemote owns the queue while the editor is open.
 * WebSocket wake + instant LPOP. No interval poll.
 */
import { onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { storeToRefs } from 'pinia'

import { bindSlideRemoteWakeDrain } from '@/composables/mindMap/bindSlideRemoteWakeDrain'
import { useAuthStore } from '@/stores/auth'
import { isMindgraphHeadlessExportSession } from '@/utils/headlessExportSession'
import { drainSlideRemoteCommands } from '@/utils/slideRemoteApi'
import { slideRemoteCanvasIsDraining } from '@/utils/slideRemoteCanvasDrainLock'
import { setSlideRemotePendingStart } from '@/utils/slideRemotePendingStart'

export function useSlideRemoteDesktopPoll(): void {
  const authStore = useAuthStore()
  const { isAuthenticated } = storeToRefs(authStore)
  const route = useRoute()
  const router = useRouter()

  let inFlight = false

  function surfaceAllowsPoll(): boolean {
    if (!isAuthenticated.value) return false
    if (isMindgraphHeadlessExportSession()) return false
    if (route.meta.layout === 'mobile') return false
    if (route.path === '/m' || route.path.startsWith('/m/')) return false
    if (route.path === '/export-render') return false
    if (route.path === '/canvas') return false
    if (slideRemoteCanvasIsDraining()) return false
    return !document.hidden
  }

  async function handleStart(diagramId: string): Promise<void> {
    const id = diagramId.trim()
    if (!id) return
    setSlideRemotePendingStart(id)
    await router.push({ path: '/canvas', query: { diagramId: id } }).catch(() => undefined)
  }

  async function drain(): Promise<void> {
    if (!surfaceAllowsPoll() || inFlight) return
    inFlight = true
    try {
      const items = await drainSlideRemoteCommands()
      for (const row of items) {
        if (row.action !== 'start') continue
        const diagramId = typeof row.diagram_id === 'string' ? row.diagram_id : ''
        await handleStart(diagramId)
      }
    } finally {
      inFlight = false
    }
  }

  const wake = bindSlideRemoteWakeDrain({
    drain,
    shouldRun: surfaceAllowsPoll,
  })

  function sync(): void {
    if (surfaceAllowsPoll()) {
      wake.start()
      return
    }
    wake.stop()
  }

  document.addEventListener('visibilitychange', sync)

  watch(
    () => [isAuthenticated.value, route.path, route.meta.layout] as const,
    () => {
      sync()
    },
    { immediate: true }
  )

  onUnmounted(() => {
    document.removeEventListener('visibilitychange', sync)
    wake.stop()
  })
}
