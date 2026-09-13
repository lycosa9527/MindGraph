/**
 * Drain 演讲模式 Start when the desktop is not on /canvas.
 * Canvas useSlideRemote owns the queue while the editor is open.
 */
import { onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { storeToRefs } from 'pinia'

import { useAuthStore } from '@/stores/auth'
import { isMindgraphHeadlessExportSession } from '@/utils/headlessExportSession'
import { drainSlideRemoteCommands } from '@/utils/slideRemoteApi'
import { slideRemoteCanvasIsDraining } from '@/utils/slideRemoteCanvasDrainLock'
import { setSlideRemotePendingStart } from '@/utils/slideRemotePendingStart'

const DRAIN_MS = 400

export function useSlideRemoteDesktopPoll(): void {
  const authStore = useAuthStore()
  const { isAuthenticated } = storeToRefs(authStore)
  const route = useRoute()
  const router = useRouter()

  let timer: ReturnType<typeof setInterval> | null = null
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

  function stop(): void {
    if (timer !== null) {
      clearInterval(timer)
      timer = null
    }
  }

  function start(): void {
    if (timer !== null) return
    void drain()
    timer = window.setInterval(() => {
      void drain()
    }, DRAIN_MS)
  }

  function sync(): void {
    if (surfaceAllowsPoll()) {
      start()
      return
    }
    stop()
  }

  function onVisibility(): void {
    sync()
  }

  document.addEventListener('visibilitychange', onVisibility)

  watch(
    () => [isAuthenticated.value, route.path, route.meta.layout] as const,
    () => {
      sync()
    },
    { immediate: true }
  )

  onUnmounted(() => {
    document.removeEventListener('visibilitychange', onVisibility)
    stop()
  })
}
