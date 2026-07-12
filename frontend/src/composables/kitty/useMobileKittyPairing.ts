/**
 * Mobile Kitty: WebSocket scope, desktop-focus hint, hub preflight bootstrap, and debounced context sync.
 */
import { type ComputedRef, type Ref, computed, onMounted, onUnmounted, ref, watch } from 'vue'

import { storeToRefs } from 'pinia'

import { shouldUseOneSentenceEditFlow } from '@/composables/canvasToolbar/mindMapOneSentencePhase'
import { kittyInteractionLanguageFromUi } from '@/composables/kitty/buildKittyDiagramContext'
import { hydrateMobileKittyFromLibrary } from '@/composables/kitty/hydrateMobileKittyFromLibrary'
import type { KittyAgentContext } from '@/composables/kitty/useKittyAgent'
import type { useKittyAgent } from '@/composables/kitty/useKittyAgent'
import { useKittyDesktopFocusHint } from '@/composables/kitty/useKittyDesktopFocus'
import { useMobileKittyLiveContextPoll } from '@/composables/kitty/useMobileKittyLiveContextPoll'
import { runKittyHubSync } from '@/composables/kitty/pipeline/hubSyncWorker'
import { useAuthStore, useDiagramStore } from '@/stores'
import { useLLMResultsStore } from '@/stores/llmResults'
import { useSavedDiagramsStore } from '@/stores/savedDiagrams'
import { safeRandomUUID } from '@/utils/safeRandomUUID'

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
  return safeRandomUUID()
}

const KITTY_CONTEXT_SYNC_MS = 220
/** Ignore desktop_focus switches briefly after the user picks a diagram on mobile. */
const USER_DIAGRAM_OVERRIDE_MS = 3000
/**
 * Desktop focus is trusted only when recently refreshed (canvas heartbeat keeps it warm).
 * Stale Redis leftovers after a crash/logout must not bind mobile to an old diagram.
 */
const DESKTOP_FOCUS_FRESH_SEC = 180

function isDesktopFocusFresh(updatedAtEpochSec: number | null): boolean {
  if (updatedAtEpochSec == null || !Number.isFinite(updatedAtEpochSec)) {
    return false
  }
  const ageSec = Math.floor(Date.now() / 1000) - updatedAtEpochSec
  return ageSec >= 0 && ageSec <= DESKTOP_FOCUS_FRESH_SEC
}

export function useMobileKittyPairing(
  kitty: MobileKittyAgentApi,
  options: {
    kittyServerEnabled: ComputedRef<boolean>
    onDebugLine?: (prefix: string, detail: string) => void
    /** Fired after mobile follows a new desktop library diagram. */
    onDesktopDiagramFollow?: (libraryId: string) => void
    /** Skip debounced WS context sync while voice edit pipeline is active. */
    editPipelineActive?: Ref<boolean> | ComputedRef<boolean>
  }
) {
  const authStore = useAuthStore()
  const diagramStore = useDiagramStore()
  const savedDiagramsStore = useSavedDiagramsStore()
  const llmResultsStore = useLLMResultsStore()
  const {
    type: diagramTypeRef,
    data: diagramDataRef,
    selectedNodes: selectedNodesRef,
  } = storeToRefs(diagramStore)
  const { activeDiagramId } = storeToRefs(savedDiagramsStore)

  /** Mobile Kitty uses the one-sentence edit pipeline for verified diagram mutations. */
  function resolveMobileOneSentencePhase(): 'create' | 'edit' {
    if (shouldUseOneSentenceEditFlow(diagramStore, savedDiagramsStore, llmResultsStore, 'create')) {
      return 'edit'
    }
    return 'create'
  }

  function withOneSentencePanel(ctx: KittyAgentContext): KittyAgentContext {
    return {
      ...ctx,
      active_panel: 'one_sentence',
      one_sentence_phase: resolveMobileOneSentencePhase(),
    }
  }

  const sessionId = ref(createKittySessionId())
  const bootstrapPayload = ref<MobileKittyBootstrapPayload | null>(null)
  const bootstrapDone = ref(false)
  const bootstrapRecommendedScope = ref<string | null>(null)
  const bootstrapDesktopLibraryId = computed(() => {
    const lib = bootstrapPayload.value?.desktop_focus?.diagram_library_id
    return typeof lib === 'string' && lib.trim() !== '' ? lib.trim() : null
  })
  const pageVisible = ref(typeof document === 'undefined' ? true : !document.hidden)
  let userDiagramOverrideUntil = 0
  let desktopFollowInFlight: Promise<void> | null = null
  /** User tapped “new mindmap”: stay on ephemeral scope until they pick a library diagram. */
  const forceEphemeralSession = ref(false)

  function markUserDiagramOverride(): void {
    userDiagramOverrideUntil = Date.now() + USER_DIAGRAM_OVERRIDE_MS
  }

  function clearForceEphemeralSession(): void {
    forceEphemeralSession.value = false
  }

  /**
   * Fresh mobile session (no library binding). Optionally pin against desktop_focus
   * until the user picks a saved diagram (create-new mindmap).
   */
  function resetToFreshEphemeralSession(optionsReset?: {
    pinAgainstDesktopFocus?: boolean
    loadMindmapTemplate?: boolean
  }): string {
    const pin = optionsReset?.pinAgainstDesktopFocus === true
    const loadTemplate = optionsReset?.loadMindmapTemplate !== false
    if (pin) {
      markUserDiagramOverride()
      forceEphemeralSession.value = true
    } else {
      forceEphemeralSession.value = false
    }
    savedDiagramsStore.clearActiveDiagram()
    bootstrapRecommendedScope.value = null
    bootstrapPayload.value = {
      recommended_scope: null,
      desktop_focus: { diagram_library_id: null, updated_at: null },
      context: {
        diagram_type: 'mindmap',
        active_panel: 'one_sentence',
        selected_nodes: [],
        diagram_data: {},
        one_sentence_phase: 'create',
      },
      diagram_type: 'mindmap',
      active_panel: 'one_sentence',
      source: 'empty',
    }
    sessionId.value = createKittySessionId()
    if (loadTemplate) {
      diagramStore.clearHistory()
      diagramStore.setDiagramType('mindmap')
      diagramStore.loadDefaultTemplate('mindmap')
    }
    options.onDebugLine?.('#sess', `ephemeral ${sessionId.value.slice(0, 8)}`)
    return sessionId.value
  }

  /** Start a blank mindmap session on mobile (ephemeral scope). */
  function startNewEphemeralMindmapSession(): string {
    return resetToFreshEphemeralSession({
      pinAgainstDesktopFocus: true,
      loadMindmapTemplate: true,
    })
  }

  function handleVisibilityForFocusPoll(): void {
    pageVisible.value = !document.hidden
  }

  /**
   * Focus discovery: WS ``desktop_focus_update`` while connected (incl. cross-worker
   * Redis relay); REST poll is faster pre-WS and slow recovery after connect.
   */
  const kittyDesktopPollOn = computed(() => {
    if (!pageVisible.value) {
      return false
    }
    if (!options.kittyServerEnabled.value || !authStore.isAuthenticated) {
      return false
    }
    return true
  })
  const kittyFocusPushPreferred = computed(() => kitty.isConnected.value === true)
  const { diagramLibraryId: kittyDesktopLibraryId, updatedAt: kittyDesktopFocusUpdatedAt } =
    useKittyDesktopFocusHint(kittyDesktopPollOn, kittyFocusPushPreferred)
  const bootstrapLastFailureAt = ref(0)
  let bootstrapInFlight: Promise<void> | null = null

  /**
   * Pairing scope rules:
   * - force ephemeral / create-new → page session id
   * - user/follow library id → that id
   * - bootstrap live|library recommended_scope → that id
   * - never bind from bare stale desktop_focus alone
   */
  const kittyPairScope = computed(() => {
    if (forceEphemeralSession.value) {
      return sessionId.value
    }
    if (activeDiagramId.value != null && activeDiagramId.value !== '') {
      return activeDiagramId.value
    }
    if (bootstrapRecommendedScope.value != null && bootstrapRecommendedScope.value !== '') {
      return bootstrapRecommendedScope.value
    }
    return sessionId.value
  })

  const kittyPairScopeIsEphemeral = computed(() => {
    if (forceEphemeralSession.value) {
      return true
    }
    const scope = kittyPairScope.value
    const active = activeDiagramId.value?.trim() ?? ''
    const recommended = bootstrapRecommendedScope.value?.trim() ?? ''
    return scope !== active && scope !== recommended
  })

  const kittyPairScopeWarning = computed(() => {
    if (!kittyPairScopeIsEphemeral.value) {
      return null
    }
    return 'Using a temporary session scope — desktop pairing sync may not work until you open a saved diagram.'
  })

  const liveContextLibraryId = computed(() => {
    if (kittyPairScopeIsEphemeral.value) {
      return null
    }
    const scope = kittyPairScope.value?.trim() ?? ''
    return scope !== '' ? scope : null
  })
  const liveContextPollEnabled = computed(
    () =>
      options.kittyServerEnabled.value &&
      authStore.isAuthenticated &&
      pageVisible.value &&
      liveContextLibraryId.value != null
  )
  const liveContextEditPipelineActive = computed(() => options.editPipelineActive?.value === true)
  useMobileKittyLiveContextPoll({
    libraryDiagramId: liveContextLibraryId,
    enabled: liveContextPollEnabled,
    editPipelineActive: liveContextEditPipelineActive,
    onDebugLine: options.onDebugLine,
  })

  async function fetchMobileKittyBootstrap(scopeId?: string): Promise<boolean> {
    if (!options.kittyServerEnabled.value || !authStore.isAuthenticated) {
      return false
    }
    try {
      const params = new URLSearchParams()
      // Only pass an explicit scope (follow / hydrate). Never send sticky local
      // activeDiagramId on cold open — that re-bound mobile to the last diagram
      // when desktop had no live canvas.
      const sid = scopeId?.trim()
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
      if (data.recommended_scope && (data.source === 'live' || data.source === 'library')) {
        bootstrapRecommendedScope.value = data.recommended_scope
      } else if (scopeId != null && scopeId !== '' && data.source !== 'empty') {
        bootstrapRecommendedScope.value = scopeId
      } else if (data.source === 'empty' && (scopeId == null || scopeId === '')) {
        bootstrapRecommendedScope.value = null
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
      try {
        const success = await fetchMobileKittyBootstrap()
        if (success && !forceEphemeralSession.value) {
          const boot = bootstrapPayload.value
          if (boot?.source === 'empty') {
            resetToFreshEphemeralSession({
              pinAgainstDesktopFocus: false,
              loadMindmapTemplate: true,
            })
          } else if (
            (boot?.source === 'live' || boot?.source === 'library') &&
            boot.recommended_scope
          ) {
            clearForceEphemeralSession()
            savedDiagramsStore.setActiveDiagram(boot.recommended_scope)
            await hydrateMobileKittyFromLibrary(boot.recommended_scope)
          }
        }
        bootstrapDone.value = success
      } finally {
        bootstrapInFlight = null
      }
    })()
    await bootstrapInFlight
  }

  async function refreshMobileKittyBootstrap(scopeId: string): Promise<void> {
    bootstrapDone.value = false
    bootstrapRecommendedScope.value = null
    await fetchMobileKittyBootstrap(scopeId)
    bootstrapDone.value = true
  }

  async function applyDesktopFocusLibrary(libraryId: string): Promise<void> {
    if (forceEphemeralSession.value) {
      return
    }
    const id = libraryId.trim()
    if (!id) {
      return
    }
    if (Date.now() < userDiagramOverrideUntil) {
      return
    }
    if (activeDiagramId.value === id) {
      return
    }
    if (desktopFollowInFlight) {
      await desktopFollowInFlight
      if (activeDiagramId.value === id) {
        return
      }
    }
    desktopFollowInFlight = (async () => {
      try {
        clearForceEphemeralSession()
        savedDiagramsStore.setActiveDiagram(id)
        await refreshMobileKittyBootstrap(id)
        await hydrateMobileKittyFromLibrary(id)
        options.onDebugLine?.('#desk', `follow ${id.slice(0, 12)}`)
        options.onDesktopDiagramFollow?.(id)
      } finally {
        desktopFollowInFlight = null
      }
    })()
    await desktopFollowInFlight
  }

  async function hydrateLibraryScopeIfNeeded(scope: string): Promise<void> {
    const id = scope.trim()
    if (!id || id === sessionId.value) {
      return
    }
    const isActiveLibrary = activeDiagramId.value === id
    const isKnownLibraryHint =
      bootstrapRecommendedScope.value === id ||
      bootstrapDesktopLibraryId.value === id ||
      kittyDesktopLibraryId.value === id
    if (!isActiveLibrary && !isKnownLibraryHint) {
      return
    }
    await refreshMobileKittyBootstrap(id)
    await hydrateMobileKittyFromLibrary(id)
  }

  let contextSyncTimer: ReturnType<typeof setTimeout> | null = null

  function resolveMobileLibraryDiagramId(): string | null {
    if (forceEphemeralSession.value) {
      return null
    }
    const active = activeDiagramId.value?.trim()
    if (active) {
      return active
    }
    const boot = bootstrapPayload.value
    const scope = bootstrapRecommendedScope.value?.trim()
    if (
      (boot?.source === 'live' || boot?.source === 'library') &&
      scope &&
      scope !== sessionId.value
    ) {
      return scope
    }
    return null
  }

  function buildMinimalLibraryKittyContext(libId: string): KittyAgentContext {
    // Thin mobile: never push full Pinia diagram_data — server prefers live_spec/library.
    const boot = bootstrapPayload.value
    const bootCtx = boot?.context
    const selected = [...diagramStore.selectedNodes]
    const displayTitle = String(
      bootCtx?.diagram_display_title ?? diagramStore.effectiveTitle ?? diagramStore.title ?? ''
    ).trim()
    const diagramType = (bootCtx?.diagram_type ??
      boot?.diagram_type ??
      diagramStore.type ??
      'circle_map') as KittyAgentContext['diagram_type']
    const diagramData: Record<string, unknown> =
      selected.length > 0 ? { selected_nodes: selected } : {}
    return withOneSentencePanel({
      diagram_type: diagramType,
      active_panel: 'one_sentence',
      selected_nodes: selected,
      diagram_data: diagramData,
      diagram_library_id: libId,
      diagram_display_title: displayTitle,
      interaction_language: kittyInteractionLanguageFromUi(),
      one_sentence_phase: resolveMobileOneSentencePhase(),
      selected_llm_model: llmResultsStore.selectedModel,
    })
  }

  function buildMobileKittyContext(): KittyAgentContext {
    const libId = resolveMobileLibraryDiagramId()
    if (libId) {
      const libCtx = buildMinimalLibraryKittyContext(libId)
      if (libCtx.diagram_library_id == null || libCtx.diagram_library_id === '') {
        return { ...libCtx, diagram_library_id: libId }
      }
      return libCtx
    }

    // Ephemeral / unpaired: metadata only (no full store diagram push).
    const selected = [...diagramStore.selectedNodes]
    const boot = bootstrapPayload.value
    const bootCtx = boot?.context
    const displayTitle = String(
      diagramStore.effectiveTitle ?? diagramStore.title ?? bootCtx?.diagram_display_title ?? ''
    ).trim()
    const diagramType = (bootCtx?.diagram_type ??
      boot?.diagram_type ??
      diagramStore.type ??
      'circle_map') as KittyAgentContext['diagram_type']
    const pairLib =
      (typeof bootCtx?.diagram_library_id === 'string' && bootCtx.diagram_library_id !== ''
        ? bootCtx.diagram_library_id
        : null) ??
      (kittyDesktopLibraryId.value != null && kittyDesktopLibraryId.value !== ''
        ? kittyDesktopLibraryId.value
        : null)
    return withOneSentencePanel({
      diagram_type: diagramType,
      active_panel: 'one_sentence',
      selected_nodes: selected,
      diagram_data: selected.length > 0 ? { selected_nodes: selected } : {},
      diagram_library_id: pairLib ?? undefined,
      diagram_display_title: displayTitle,
      interaction_language: kittyInteractionLanguageFromUi(),
      one_sentence_phase: resolveMobileOneSentencePhase(),
      selected_llm_model: llmResultsStore.selectedModel,
    })
  }

  const mobileKittyContextPreview = computed<MobileKittyContextPreview>(() => {
    const boot = bootstrapPayload.value
    const bootCtx = boot?.context
    const libRaw = forceEphemeralSession.value
      ? null
      : (activeDiagramId.value ??
        (boot?.source === 'live' || boot?.source === 'library'
          ? bootCtx?.diagram_library_id
          : null))
    const lib = typeof libRaw === 'string' && libRaw.trim() !== '' ? libRaw.trim() : null
    const liveTitle = String(diagramStore.effectiveTitle ?? diagramStore.title ?? '').trim()
    const title = liveTitle !== '' ? liveTitle : String(bootCtx?.diagram_display_title ?? '').trim()
    const scope = kittyPairScope.value
    const scopeForHint = lib ?? scope
    const hubSrc = boot?.source
    const hubSource: MobileKittyBootstrapPayload['source'] | null =
      hubSrc === 'live' || hubSrc === 'library' || hubSrc === 'empty' ? hubSrc : null

    return {
      diagramDisplayTitle: title,
      diagramLibraryId: lib,
      diagramType: String(diagramStore.type ?? bootCtx?.diagram_type ?? boot?.diagram_type ?? ''),
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
    if (options.editPipelineActive?.value) {
      scheduleMobileKittyContextSync()
      return
    }
    if (contextSyncTimer != null) {
      clearTimeout(contextSyncTimer)
      contextSyncTimer = null
    }
    if (!kitty.isConnected.value) {
      return
    }
    void runKittyHubSync({
      deps: {
        buildContext: buildMobileKittyContext,
        updateContext: kitty.updateContext,
        getScope: () => kittyPairScope.value,
        isConnected: () => kitty.isConnected.value,
        lane: 'mobile',
      },
      ctx: {
        requestId: `pair-sync-${Date.now()}`,
        scope: kittyPairScope.value || 'scope',
        lane: 'mobile',
      },
      reason: 'background',
    }).then(() => {
      if (options.onDebugLine) {
        const built = buildMobileKittyContext()
        const titleShort = (built.diagram_display_title ?? '').slice(0, 28)
        const lib =
          built.diagram_library_id != null ? String(built.diagram_library_id).slice(0, 8) : '—'
        options.onDebugLine('#ctx', `${String(built.diagram_type)} lib=${lib} ${titleShort}`)
      }
    })
  }

  watch(
    [kittyDesktopLibraryId, kittyDesktopFocusUpdatedAt],
    ([libraryId, focusUpdatedAt], previous) => {
      if (forceEphemeralSession.value) {
        return
      }
      const previousId = Array.isArray(previous) ? previous[0] : undefined
      if (libraryId == null || libraryId === '') {
        const hadPrevious = typeof previousId === 'string' && previousId.trim() !== ''
        if (hadPrevious || (activeDiagramId.value != null && activeDiagramId.value !== '')) {
          resetToFreshEphemeralSession({
            pinAgainstDesktopFocus: false,
            loadMindmapTemplate: true,
          })
          options.onDebugLine?.('#desk', 'focus cleared → ephemeral')
        }
        return
      }
      if (!isDesktopFocusFresh(focusUpdatedAt)) {
        options.onDebugLine?.('#desk', `stale focus ignored ${libraryId.slice(0, 8)}`)
        return
      }
      void applyDesktopFocusLibrary(libraryId)
    }
  )

  watch(
    [diagramTypeRef, diagramDataRef, selectedNodesRef, activeDiagramId, kittyDesktopLibraryId],
    () => {
      scheduleMobileKittyContextSync()
    },
    { deep: true }
  )

  watch(
    () => llmResultsStore.selectedModel,
    () => {
      scheduleMobileKittyContextSync()
    }
  )

  watch(
    () => bootstrapRecommendedScope.value,
    () => {
      scheduleMobileKittyContextSync()
    }
  )

  if (options.editPipelineActive != null) {
    watch(options.editPipelineActive, (active, wasActive) => {
      if (wasActive && !active) {
        scheduleMobileKittyContextSync()
      }
    })
  }

  onMounted(() => {
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', handleVisibilityForFocusPoll)
    }
  })

  onUnmounted(() => {
    if (typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', handleVisibilityForFocusPoll)
    }
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
    hydrateLibraryScopeIfNeeded,
    markUserDiagramOverride,
    startNewEphemeralMindmapSession,
    clearForceEphemeralSession,
    applyDesktopFocusLibrary,
    buildMobileKittyContext,
    resolveMobileOneSentencePhase,
    scheduleMobileKittyContextSync,
    syncMobileKittyContextNow,
  }
}
