/**
 * While the desktop Kitty mobile pairing indicator is on, poll
 * ``GET /api/kitty/live_context/{scope}`` and hydrate Pinia from Redis
 * ``kitty:live_spec`` (hub / voice / context_update ground truth).
 */
import { type ComputedRef, type Ref, onUnmounted, ref, watch } from 'vue'

import { KITTY_PAIR_POLL_MS } from '@/composables/kitty/runKittyIntervalPoll'
import { useDiagramStore } from '@/stores/diagram'
import { VALID_DIAGRAM_TYPES } from '@/stores/diagram/constants'
import type { DiagramType } from '@/types'

function canonicalDiagramKind(t: DiagramType | null): string {
  if (!t) return ''
  return t === 'mind_map' || t === 'mindmap' ? 'mindmap' : t
}

function diagramTypeFromLivePayload(raw: unknown): DiagramType | null {
  if (typeof raw !== 'string' || !raw.trim()) return null
  const candidate = (raw.trim() === 'mind_map' ? 'mindmap' : raw.trim()) as DiagramType
  if (!VALID_DIAGRAM_TYPES.includes(candidate)) return null
  return candidate
}

export function useKittyDesktopLiveSpecSync(options: {
  libraryDiagramId: Ref<string | null> | ComputedRef<string | null>
  syncEnabled: ComputedRef<boolean>
  collabSessionActive: ComputedRef<boolean>
}) {
  const diagramStore = useDiagramStore()
  const lastAppliedUpdatedAt = ref<number | null>(null)
  let intervalId: ReturnType<typeof setInterval> | null = null

  async function tick(): Promise<void> {
    if (
      !options.syncEnabled.value ||
      options.collabSessionActive.value ||
      diagramStore.type == null
    ) {
      return
    }
    const id = options.libraryDiagramId.value
    if (id == null || id === '') return

    try {
      const res = await fetch(`/api/kitty/live_context/${encodeURIComponent(id)}`, {
        credentials: 'same-origin',
      })
      if (!res.ok) return

      const data = (await res.json()) as {
        ok?: boolean
        updated_at?: number
        diagram_type?: string
        diagram_data?: Record<string, unknown>
        selected_nodes?: unknown
      }

      if (!data.ok) return

      const ua = data.updated_at
      if (typeof ua !== 'number') return
      if (lastAppliedUpdatedAt.value !== null && ua <= lastAppliedUpdatedAt.value) return

      const dt = diagramTypeFromLivePayload(data.diagram_type)
      const storeType = diagramStore.type
      if (dt == null || storeType == null) return
      if (canonicalDiagramKind(dt) !== canonicalDiagramKind(storeType)) return

      const spec = data.diagram_data
      if (!spec || typeof spec !== 'object') return

      diagramStore.loadFromSpec(spec, dt, { mergePreviousNodeStyles: true })

      const sel = data.selected_nodes
      if (Array.isArray(sel) && sel.length > 0 && sel.every((x) => typeof x === 'string')) {
        diagramStore.selectNodes(sel as string[])
      }

      lastAppliedUpdatedAt.value = ua
    } catch {
      /* ignore transient network errors */
    }
  }

  function startPolling(): void {
    stopPolling()
    void tick()
    intervalId = setInterval(() => {
      void tick()
    }, KITTY_PAIR_POLL_MS)
  }

  function stopPolling(): void {
    if (intervalId != null) {
      clearInterval(intervalId)
      intervalId = null
    }
  }

  watch(
    () => options.syncEnabled.value,
    (on) => {
      if (on) {
        startPolling()
      } else {
        stopPolling()
        lastAppliedUpdatedAt.value = null
      }
    },
    { immediate: true }
  )

  watch(
    () => options.libraryDiagramId.value,
    () => {
      lastAppliedUpdatedAt.value = null
    }
  )

  onUnmounted(() => {
    stopPolling()
  })

  return { refresh: tick }
}
