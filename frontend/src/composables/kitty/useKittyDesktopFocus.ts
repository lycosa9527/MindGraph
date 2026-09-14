/**
 * Desktop focus discovery (mobile) and publish (desktop PUT) for Kitty pairing.
 *
 * Publish is event-only: canvas open / diagram switch / leave.
 * Discovery: one GET when pairing starts or Kitty WS connects; then WS
 * ``desktop_focus_update``. GET applies only when ``canvas_owner_present``.
 */
import { type Ref, onUnmounted, ref, watch } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import { apiRequest } from '@/utils/apiClient'
import { awaitSessionRefreshIdle } from '@/utils/sessionRefresh'

const DEBOUNCE_MS = 480

async function putDesktopFocusDiagram(diagramLibraryId: string | null): Promise<void> {
  try {
    // Wait out Kitty / apiClient refresh so this PUT does not race Redis delete of
    // the access session and trigger a second token rotation.
    await awaitSessionRefreshIdle()
    // apiRequest refreshes once on 401 then expires the session.
    await apiRequest('/api/kitty/desktop_focus', {
      method: 'PUT',
      body: JSON.stringify({ diagram_library_id: diagramLibraryId }),
    })
  } catch {
    /* best-effort */
  }
}

export function useKittyDesktopFocusHint(
  hydrateEnabled: Ref<boolean>,
  /** When Kitty WS connects, hydrate once more then trust push. */
  pushPreferred?: Ref<boolean>
) {
  const diagramLibraryId = ref<string | null>(null)
  const updatedAt = ref<number | null>(null)

  function applyFocus(lib: string | null, ts: number | null): void {
    diagramLibraryId.value = lib
    updatedAt.value = ts
  }

  async function hydrate(): Promise<void> {
    if (!hydrateEnabled.value) {
      return
    }
    try {
      const res = await apiRequest('/api/kitty/desktop_focus', {
        method: 'GET',
      })
      if (!res.ok) {
        applyFocus(null, null)
        return
      }
      const data: unknown = await res.json()
      if (typeof data !== 'object' || data === null || !('diagram_library_id' in data)) {
        applyFocus(null, null)
        return
      }
      const raw = data as Record<string, unknown>
      const libRaw = raw.diagram_library_id
      const lib = typeof libRaw === 'string' && libRaw.length > 0 ? libRaw : null
      const ts = raw.updated_at
      const tsNum =
        typeof ts === 'number'
          ? ts
          : typeof ts === 'string' && /^\d+$/.test(ts)
            ? Number(ts)
            : null
      // Bind only while the desktop canvas-owner WS lease is live.
      if (raw.canvas_owner_present !== true) {
        applyFocus(null, tsNum)
        return
      }
      applyFocus(lib, tsNum)
    } catch {
      applyFocus(null, null)
    }
  }

  function onFocusPush(payload: {
    diagram_library_id: string | null
    updated_at: number | null
  }): void {
    applyFocus(payload.diagram_library_id, payload.updated_at)
  }

  eventBus.on('kitty:desktop_focus_update', onFocusPush)

  watch(
    () =>
      [hydrateEnabled.value, pushPreferred != null ? pushPreferred.value : false] as const,
    ([enabled]) => {
      if (enabled) {
        void hydrate()
      }
    },
    { immediate: true }
  )

  onUnmounted(() => {
    eventBus.off('kitty:desktop_focus_update', onFocusPush)
  })

  return { diagramLibraryId, updatedAt, refresh: hydrate }
}

export function useKittyDesktopFocusPublish(options: {
  libraryDiagramId: Ref<string | null | undefined>
  enabled: Ref<boolean>
}): void {
  let debounceTimer: ReturnType<typeof setTimeout> | null = null

  function flush(): void {
    const idRaw = options.libraryDiagramId.value
    const id = options.enabled.value && idRaw != null && idRaw !== '' ? String(idRaw) : null
    void putDesktopFocusDiagram(id)
  }

  function schedule(): void {
    if (debounceTimer != null) {
      clearTimeout(debounceTimer)
    }
    debounceTimer = setTimeout(() => {
      debounceTimer = null
      flush()
    }, DEBOUNCE_MS)
  }

  watch(
    () => [options.libraryDiagramId.value, options.enabled.value] as const,
    () => {
      schedule()
    },
    { flush: 'post', immediate: true }
  )

  onUnmounted(() => {
    if (debounceTimer != null) {
      clearTimeout(debounceTimer)
      debounceTimer = null
    }
    void putDesktopFocusDiagram(null)
  })
}
