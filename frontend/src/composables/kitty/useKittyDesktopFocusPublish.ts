/**
 * Debounced ``PUT /api/kitty/desktop_focus`` from desktop MindGraph so phones can discover
 * which saved diagram is focused (library id).
 */
import { type Ref, onUnmounted, watch } from 'vue'

const DEBOUNCE_MS = 480

async function putDesktopFocusDiagram(diagramLibraryId: string | null): Promise<void> {
  try {
    await fetch('/api/kitty/desktop_focus', {
      method: 'PUT',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ diagram_library_id: diagramLibraryId }),
    })
  } catch {
    /* best-effort */
  }
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
