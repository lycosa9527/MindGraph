/**
 * Mobile Kitty: WebSocket scope, desktop-focus hint, hub preflight bootstrap, and debounced context sync.
 */
import { type ComputedRef, computed, onUnmounted, ref, watch } from 'vue'

import { storeToRefs } from 'pinia'

import { buildKittyVoiceContextPreferStore } from '@/composables/kitty/buildKittyDiagramContext'
import type { KittyAgentContext } from '@/composables/kitty/useKittyAgent'
import type { useKittyAgent } from '@/composables/kitty/useKittyAgent'
import { useKittyDesktopFocusHint } from '@/composables/kitty/useKittyDesktopFocusHint'
import { useAuthStore, useDiagramStore } from '@/stores'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'

export type MobileKittyAgentApi = ReturnType<typeof useKittyAgent>

/** Shortened UX summary mirroring ``buildMobileKittyContext()`` for mobile diagram card. */
export interface MobileKittyContextPreview {
  diagramDisplayTitle: string
  diagramLibraryId: string | null
  diagramType: string
  pairScopeShort: string
  scopeHintShort: string
  hubSource: MobileKittyBootstrapPayload['source'] | null
}

function shortenDiagramScopeHint(raw: string, headChars = 8): string {
  const s = String(raw).trim()
  if (s.length <= headChars) {
    return s
  }
  return `${s.slice(0, headChars)}…`
}

/** JSON shape from ``GET /api/kitty/mobile_open_bootstrap`` (snake_case keys). */
export interface MobileKittyBootstrapPayload {
  recommended_scope: string | null
  desktop_focus: { diagram_library_id: string | null; updated_at: number | null }
  context: KittyAgentContext
  diagram_type: string
  active_panel: string
  source: 'live' | 'library' | 'empty'
}

function createKittySessionId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `kitty_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`
}

const KITTY_CONTEXT_SYNC_MS = 220

export function useMobileKittyPairing(
  kitty: MobileKittyAgentApi,
  options: {
    kittyServerEnabled: ComputedRef<boolean>
    onDebugLine?: (prefix: string, detail: string) => void
  }
) {
  const authStore = useAuthStore()
  const diagramStore = useDiagramStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const {
    type: diagramTypeRef,
    data: diagramDataRef,
    selectedNodes: selectedNodesRef,
  } = storeToRefs(diagramStore)
  const { activeDiagramId } = storeToRefs(savedDiagramsStore)

  const kittyDesktopPollOn = computed(
    () => options.kittyServerEnabled.value && authStore.isAuthenticated
  )
  const { diagramLibraryId: kittyDesktopLibraryId } = useKittyDesktopFocusHint(kittyDesktopPollOn)

  const sessionId = ref(createKittySessionId())
  const bootstrapPayload = ref<MobileKittyBootstrapPayload | null>(null)
  const bootstrapDone = ref(false)
  const bootstrapRecommendedScope = ref<string | null>(null)
  const bootstrapLastFailureAt = ref(0)
  let bootstrapInFlight: Promise<void> | null = null

  const kittyPairScope = computed(() => {
    if (activeDiagramId.value != null && activeDiagramId.value !== '') {
      return activeDiagramId.value
    }
    if (bootstrapRecommendedScope.value != null && bootstrapRecommendedScope.value !== '') {
      return bootstrapRecommendedScope.value
    }
    if (kittyDesktopLibraryId.value != null && kittyDesktopLibraryId.value !== '') {
      return kittyDesktopLibraryId.value
    }
    return sessionId.value
  })

  async function ensureMobileKittyBootstrap(): Promise<void> {
    if (bootstrapInFlight) {
      await bootstrapInFlight
      return
    }
    if (bootstrapDone.value) {
      return
    }
    const now = Date.now()
    if (bootstrapLastFailureAt.value > 0 && now - bootstrapLastFailureAt.value < 3000) {
      return
    }
    if (!options.kittyServerEnabled.value || !authStore.isAuthenticated) {
      bootstrapDone.value = true
      return
    }
    bootstrapInFlight = (async () => {
      let success = false
      try {
        const params = new URLSearchParams()
        const sid = activeDiagramId.value?.trim()
        if (sid) {
          params.set('suggested_scope', sid)
        }
        const q = params.toString()
        const url = q ? `/api/kitty/mobile_open_bootstrap?${q}` : '/api/kitty/mobile_open_bootstrap'
        const res = await fetch(url, { credentials: 'same-origin' })
        if (!res.ok) {
          bootstrapLastFailureAt.value = Date.now()
          return
        }
        const data = (await res.json()) as MobileKittyBootstrapPayload
        bootstrapPayload.value = data
        if (data.recommended_scope && data.source !== 'empty') {
          bootstrapRecommendedScope.value = data.recommended_scope
        }
        success = true
        if (options.onDebugLine) {
          const sc =
            data.recommended_scope != null ? String(data.recommended_scope).slice(0, 12) : '—'
          options.onDebugLine('#boot', `${data.source} scope=${sc}`)
        }
      } catch {
        bootstrapLastFailureAt.value = Date.now()
      } finally {
        bootstrapDone.value = success
        bootstrapInFlight = null
      }
    })()
    await bootstrapInFlight
  }

  let contextSyncTimer: ReturnType<typeof setTimeout> | null = null

  function buildMobileKittyContext(): KittyAgentContext {
    const base = buildKittyVoiceContextPreferStore('none')
    const boot = bootstrapPayload.value
    if (boot && boot.source !== 'empty' && boot.context) {
      const serverCtx = boot.context
      const diagramData = {
        ...(base.diagram_data ?? {}),
        ...(serverCtx.diagram_data ?? {}),
      }
      const merged: KittyAgentContext = {
        ...base,
        ...serverCtx,
        diagram_data: diagramData,
        diagram_type:
          (serverCtx.diagram_type as KittyAgentContext['diagram_type']) ?? base.diagram_type,
        active_panel: serverCtx.active_panel ?? base.active_panel,
        selected_nodes: Array.isArray(serverCtx.selected_nodes)
          ? serverCtx.selected_nodes
          : base.selected_nodes,
      }
      const pairLib =
        activeDiagramId.value ??
        (typeof serverCtx.diagram_library_id === 'string' && serverCtx.diagram_library_id !== ''
          ? serverCtx.diagram_library_id
          : null) ??
        (kittyDesktopLibraryId.value != null && kittyDesktopLibraryId.value !== ''
          ? kittyDesktopLibraryId.value
          : null)
      if (
        pairLib != null &&
        pairLib !== '' &&
        (merged.diagram_library_id == null || merged.diagram_library_id === '')
      ) {
        return { ...merged, diagram_library_id: pairLib }
      }
      return merged
    }

    const ctx = base
    const pairLib =
      activeDiagramId.value ??
      (kittyDesktopLibraryId.value != null && kittyDesktopLibraryId.value !== ''
        ? kittyDesktopLibraryId.value
        : null)
    if (pairLib != null && pairLib !== '' && ctx.diagram_library_id == null) {
      return { ...ctx, diagram_library_id: pairLib }
    }
    return ctx
  }

  const mobileKittyContextPreview = computed<MobileKittyContextPreview>(() => {
    const ctx = buildMobileKittyContext()
    const title = String(ctx.diagram_display_title ?? '').trim()
    const libRaw = ctx.diagram_library_id
    const lib =
      typeof libRaw === 'string' && libRaw.trim() !== '' ? libRaw.trim() : null
    const scope = kittyPairScope.value
    const scopeForHint = lib ?? scope
    const boot = bootstrapPayload.value
    const hubSrc = boot?.source
    const hubSource: MobileKittyBootstrapPayload['source'] | null =
      hubSrc === 'live' || hubSrc === 'library' || hubSrc === 'empty' ? hubSrc : null

    return {
      diagramDisplayTitle: title,
      diagramLibraryId: lib,
      diagramType: String(ctx.diagram_type ?? ''),
      pairScopeShort: shortenDiagramScopeHint(String(scope)),
      scopeHintShort: shortenDiagramScopeHint(String(scopeForHint)),
      hubSource,
    }
  })

  function scheduleMobileKittyContextSync(): void {
    if (contextSyncTimer != null) {
      clearTimeout(contextSyncTimer)
    }
    contextSyncTimer = setTimeout(() => {
      contextSyncTimer = null
      if (!kitty.isConnected.value) {
        return
      }
      const ctx = buildMobileKittyContext()
      kitty.updateContext(ctx)
      if (options.onDebugLine) {
        const titleShort = (ctx.diagram_display_title ?? '').slice(0, 28)
        const lib =
          ctx.diagram_library_id != null ? String(ctx.diagram_library_id).slice(0, 8) : '—'
        options.onDebugLine('#ctx', `${String(ctx.diagram_type)} lib=${lib} ${titleShort}`)
      }
    }, KITTY_CONTEXT_SYNC_MS)
  }

  watch(
    [diagramTypeRef, diagramDataRef, selectedNodesRef, activeDiagramId, kittyDesktopLibraryId],
    () => {
      scheduleMobileKittyContextSync()
    },
    { deep: true }
  )

  watch(
    () => bootstrapRecommendedScope.value,
    () => {
      scheduleMobileKittyContextSync()
    }
  )

  onUnmounted(() => {
    if (contextSyncTimer != null) {
      clearTimeout(contextSyncTimer)
      contextSyncTimer = null
    }
  })

  return {
    sessionId,
    kittyPairScope,
    kittyDesktopLibraryId,
    bootstrapPayload,
    mobileKittyContextPreview,
    ensureMobileKittyBootstrap,
    buildMobileKittyContext,
    scheduleMobileKittyContextSync,
  }
}
