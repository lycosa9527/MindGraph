/**
 * Mobile Kitty: WebSocket scope, desktop-focus hint, hub preflight bootstrap, and debounced context sync.
 */
import { type ComputedRef, computed, onUnmounted, ref, watch } from 'vue'

import { storeToRefs } from 'pinia'

import { buildKittyContextPreferStore } from '@/composables/kitty/buildKittyDiagramContext'
import { kittyInteractionLanguageFromUi } from '@/composables/kitty/buildKittyDiagramContext'
import type { KittyAgentContext } from '@/composables/kitty/useKittyAgent'
import type { useKittyAgent } from '@/composables/kitty/useKittyAgent'
import { useKittyDesktopFocusHint } from '@/composables/kitty/useKittyDesktopFocus'
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

  const sessionId = ref(createKittySessionId())
  const bootstrapPayload = ref<MobileKittyBootstrapPayload | null>(null)
  const bootstrapDone = ref(false)
  const bootstrapRecommendedScope = ref<string | null>(null)
  const bootstrapDesktopLibraryId = computed(() => {
    const lib = bootstrapPayload.value?.desktop_focus?.diagram_library_id
    return typeof lib === 'string' && lib.trim() !== '' ? lib.trim() : null
  })
  const desktopFocusPollActive = ref(true)

  /** Poll desktop_focus only until pre-connect scope is known (not while connected). */
  const kittyDesktopPollOn = computed(() => {
    if (!desktopFocusPollActive.value) {
      return false
    }
    if (!options.kittyServerEnabled.value || !authStore.isAuthenticated) {
      return false
    }
    if (activeDiagramId.value != null && activeDiagramId.value !== '') {
      return false
    }
    if (kitty.isConnected.value) {
      return false
    }
    if (bootstrapRecommendedScope.value != null && bootstrapRecommendedScope.value !== '') {
      return false
    }
    if (bootstrapDesktopLibraryId.value != null) {
      return false
    }
    return true
  })
  const { diagramLibraryId: kittyDesktopLibraryId } = useKittyDesktopFocusHint(kittyDesktopPollOn)
  const bootstrapLastFailureAt = ref(0)
  let bootstrapInFlight: Promise<void> | null = null

  watch(kittyDesktopLibraryId, (libraryId) => {
    if (libraryId != null && libraryId !== '') {
      desktopFocusPollActive.value = false
    }
  })

  watch([bootstrapRecommendedScope, bootstrapDesktopLibraryId], ([scope, bootLib]) => {
    if ((scope != null && scope !== '') || bootLib != null) {
      desktopFocusPollActive.value = false
    }
  })

  watch(
    () => kitty.isConnected.value,
    (connected, wasConnected) => {
      if (wasConnected && !connected && desktopFocusPollActive.value === false) {
        const hasLocalScope =
          (activeDiagramId.value != null && activeDiagramId.value !== '') ||
          (bootstrapRecommendedScope.value != null && bootstrapRecommendedScope.value !== '') ||
          bootstrapDesktopLibraryId.value != null ||
          (kittyDesktopLibraryId.value != null && kittyDesktopLibraryId.value !== '')
        if (!hasLocalScope) {
          desktopFocusPollActive.value = true
        }
      }
    }
  )

  const kittyPairScope = computed(() => {
    if (activeDiagramId.value != null && activeDiagramId.value !== '') {
      return activeDiagramId.value
    }
    if (bootstrapRecommendedScope.value != null && bootstrapRecommendedScope.value !== '') {
      return bootstrapRecommendedScope.value
    }
    if (bootstrapDesktopLibraryId.value != null) {
      return bootstrapDesktopLibraryId.value
    }
    if (kittyDesktopLibraryId.value != null && kittyDesktopLibraryId.value !== '') {
      return kittyDesktopLibraryId.value
    }
    return sessionId.value
  })

  const kittyPairScopeIsEphemeral = computed(
    () =>
      (activeDiagramId.value == null || activeDiagramId.value === '') &&
      (bootstrapRecommendedScope.value == null || bootstrapRecommendedScope.value === '') &&
      bootstrapDesktopLibraryId.value == null &&
      (kittyDesktopLibraryId.value == null || kittyDesktopLibraryId.value === '')
  )

  const kittyPairScopeWarning = computed(() => {
    if (!kittyPairScopeIsEphemeral.value) {
      return null
    }
    return 'Using a temporary session scope — desktop pairing sync may not work until you open a saved diagram.'
  })

  async function fetchMobileKittyBootstrap(scopeId?: string): Promise<boolean> {
    if (!options.kittyServerEnabled.value || !authStore.isAuthenticated) {
      return false
    }
    try {
      const params = new URLSearchParams()
      const sid = (scopeId ?? activeDiagramId.value)?.trim()
      if (sid) {
        params.set('suggested_scope', sid)
      }
      const q = params.toString()
      const url = q ? `/api/kitty/mobile_open_bootstrap?${q}` : '/api/kitty/mobile_open_bootstrap'
      const res = await fetch(url, { credentials: 'same-origin' })
      if (!res.ok) {
        bootstrapLastFailureAt.value = Date.now()
        return false
      }
      const data = (await res.json()) as MobileKittyBootstrapPayload
      bootstrapPayload.value = data
      if (data.recommended_scope && data.source !== 'empty') {
        bootstrapRecommendedScope.value = data.recommended_scope
      } else if (scopeId != null && scopeId !== '') {
        bootstrapRecommendedScope.value = scopeId
      }
      if (options.onDebugLine) {
        const sc =
          data.recommended_scope != null ? String(data.recommended_scope).slice(0, 12) : '—'
        options.onDebugLine('#boot', `${data.source} scope=${sc}`)
      }
      return true
    } catch {
      bootstrapLastFailureAt.value = Date.now()
      return false
    }
  }

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
      const success = await fetchMobileKittyBootstrap()
      bootstrapDone.value = success
      bootstrapInFlight = null
    })()
    await bootstrapInFlight
  }

  async function refreshMobileKittyBootstrap(scopeId: string): Promise<void> {
    bootstrapDone.value = false
    bootstrapRecommendedScope.value = null
    await fetchMobileKittyBootstrap(scopeId)
    bootstrapDone.value = true
  }

  let contextSyncTimer: ReturnType<typeof setTimeout> | null = null

  function resolveMobileLibraryDiagramId(): string | null {
    const active = activeDiagramId.value?.trim()
    if (active) {
      return active
    }
    const bootCtx = bootstrapPayload.value?.context
    const fromBoot =
      typeof bootCtx?.diagram_library_id === 'string' && bootCtx.diagram_library_id.trim() !== ''
        ? bootCtx.diagram_library_id.trim()
        : null
    if (fromBoot) {
      return fromBoot
    }
    const desk = kittyDesktopLibraryId.value?.trim()
    if (desk) {
      return desk
    }
    const boot = bootstrapPayload.value
    const scope = bootstrapRecommendedScope.value?.trim()
    if (boot?.source === 'library' && scope && scope !== sessionId.value) {
      return scope
    }
    return null
  }

  function buildMinimalLibraryKittyContext(libId: string): KittyAgentContext {
    const boot = bootstrapPayload.value
    const bootCtx = boot?.context
    const selected = [...diagramStore.selectedNodes]
    const displayTitle = String(bootCtx?.diagram_display_title ?? '').trim()
    const diagramType = (bootCtx?.diagram_type ??
      boot?.diagram_type ??
      'circle_map') as KittyAgentContext['diagram_type']
    const diagramData: Record<string, unknown> =
      selected.length > 0 ? { selected_nodes: selected } : {}
    return {
      diagram_type: diagramType,
      active_panel: 'none',
      selected_nodes: selected,
      diagram_data: diagramData,
      diagram_library_id: libId,
      diagram_display_title: displayTitle,
      interaction_language: kittyInteractionLanguageFromUi(),
    }
  }

  function buildMobileKittyContext(): KittyAgentContext {
    const libId = resolveMobileLibraryDiagramId()
    if (libId) {
      return buildMinimalLibraryKittyContext(libId)
    }

    const base = buildKittyContextPreferStore('none')
    const boot = bootstrapPayload.value
    if (boot && boot.source !== 'empty' && boot.context) {
      const serverCtx = boot.context
      const merged: KittyAgentContext = {
        ...base,
        ...serverCtx,
        diagram_data: {
          ...(serverCtx.diagram_data ?? {}),
          selected_nodes: [...(base.selected_nodes ?? [])],
        },
        diagram_type:
          (serverCtx.diagram_type as KittyAgentContext['diagram_type']) ?? base.diagram_type,
        active_panel: serverCtx.active_panel ?? base.active_panel,
        selected_nodes: [...(base.selected_nodes ?? [])],
      }
      const pairLib =
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
      kittyDesktopLibraryId.value != null && kittyDesktopLibraryId.value !== ''
        ? kittyDesktopLibraryId.value
        : null
    if (pairLib != null && pairLib !== '' && ctx.diagram_library_id == null) {
      return { ...ctx, diagram_library_id: pairLib }
    }
    return ctx
  }

  const mobileKittyContextPreview = computed<MobileKittyContextPreview>(() => {
    const boot = bootstrapPayload.value
    const bootCtx = boot?.context
    const libRaw = activeDiagramId.value ?? bootCtx?.diagram_library_id
    const lib = typeof libRaw === 'string' && libRaw.trim() !== '' ? libRaw.trim() : null
    const title = String(bootCtx?.diagram_display_title ?? '').trim()
    const scope = kittyPairScope.value
    const scopeForHint = lib ?? scope
    const hubSrc = boot?.source
    const hubSource: MobileKittyBootstrapPayload['source'] | null =
      hubSrc === 'live' || hubSrc === 'library' || hubSrc === 'empty' ? hubSrc : null

    return {
      diagramDisplayTitle: title,
      diagramLibraryId: lib,
      diagramType: String(bootCtx?.diagram_type ?? boot?.diagram_type ?? ''),
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
      syncMobileKittyContextNow()
    }, KITTY_CONTEXT_SYNC_MS)
  }

  function syncMobileKittyContextNow(): void {
    if (!kitty.isConnected.value) {
      return
    }
    const ctx = buildMobileKittyContext()
    kitty.updateContext(ctx)
    if (options.onDebugLine) {
      const titleShort = (ctx.diagram_display_title ?? '').slice(0, 28)
      const lib = ctx.diagram_library_id != null ? String(ctx.diagram_library_id).slice(0, 8) : '—'
      options.onDebugLine('#ctx', `${String(ctx.diagram_type)} lib=${lib} ${titleShort}`)
    }
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
    kittyPairScopeIsEphemeral,
    kittyPairScopeWarning,
    kittyDesktopLibraryId,
    bootstrapPayload,
    mobileKittyContextPreview,
    ensureMobileKittyBootstrap,
    refreshMobileKittyBootstrap,
    buildMobileKittyContext,
    scheduleMobileKittyContextSync,
    syncMobileKittyContextNow,
  }
}
