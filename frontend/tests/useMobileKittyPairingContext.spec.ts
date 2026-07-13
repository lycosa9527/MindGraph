/**
 * Mobile Kitty pairing: desktop_focus follow while connected + library hydrate helpers.
 */
import { computed, effectScope, ref, type EffectScope } from 'vue'

import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const shouldUseEditFlowMock = vi.hoisted(() => vi.fn(() => true))
const setActiveDiagramMock = vi.hoisted(() => vi.fn())
const clearActiveDiagramMock = vi.hoisted(() => vi.fn())
const fetchDiagramsMock = vi.hoisted(() => vi.fn(async () => undefined))
const hydrateFromLibraryMock = vi.hoisted(() => vi.fn(async () => true))
const loadDefaultTemplateMock = vi.hoisted(() => vi.fn(() => true))
const setDiagramTypeMock = vi.hoisted(() => vi.fn(() => true))
const clearHistoryMock = vi.hoisted(() => vi.fn())
const activeState = vi.hoisted(() => ({
  id: 'lib-diagram-1' as string | null,
}))
const activeDiagramRefHolder = vi.hoisted(() => ({
  ref: null as { value: string | null } | null,
}))
const focusApi = vi.hoisted(() => ({
  setLibraryId: (_id: string | null, _updatedAt?: number | null) => {
    /* replaced in mock */
  },
}))

vi.mock('@/composables/canvasToolbar/mindMapOneSentencePhase', () => ({
  shouldUseOneSentenceEditFlow: shouldUseEditFlowMock,
}))

vi.mock('@/composables/kitty/useKittyDesktopFocus', async () => {
  const vue = await import('vue')
  const diagramLibraryId = vue.ref<string | null>(null)
  const updatedAt = vue.ref<number | null>(null)
  focusApi.setLibraryId = (id: string | null, ts: number | null = Math.floor(Date.now() / 1000)) => {
    diagramLibraryId.value = id
    updatedAt.value = id == null ? null : ts
  }
  return {
    useKittyDesktopFocusHint: () => ({
      diagramLibraryId,
      updatedAt,
    }),
  }
})

vi.mock('@/composables/kitty/hydrateMobileKittyFromLibrary', () => ({
  hydrateMobileKittyFromLibrary: hydrateFromLibraryMock,
}))

vi.mock('@/composables/kitty/useDiagramWriteLock', () => ({
  getDiagramWriteLockHolder: () => null,
}))

vi.mock('@/stores', () => ({
  useAuthStore: () => ({
    isAuthenticated: true,
  }),
  useDiagramStore: () => ({
    type: 'mindmap',
    data: {
      nodes: [
        { id: 'topic', text: 'Root', type: 'topic' },
        { id: 'n1', text: 'Leaf', type: 'node' },
      ],
      connections: [],
    },
    selectedNodes: [],
    effectiveTitle: 'Demo',
    title: 'Demo',
    clearHistory: clearHistoryMock,
    setDiagramType: setDiagramTypeMock,
    loadDefaultTemplate: loadDefaultTemplateMock,
  }),
}))

vi.mock('@/stores/diagram', () => ({
  useDiagramStore: () => ({
    type: 'mindmap',
    data: {
      nodes: [
        { id: 'topic', text: 'Root', type: 'topic' },
        { id: 'n1', text: 'Leaf', type: 'node' },
      ],
      connections: [],
    },
    selectedNodes: [],
    effectiveTitle: 'Demo',
    title: 'Demo',
    clearHistory: clearHistoryMock,
    setDiagramType: setDiagramTypeMock,
    loadDefaultTemplate: loadDefaultTemplateMock,
  }),
}))

vi.mock('@/stores/llmResults', () => ({
  useLLMResultsStore: () => ({
    isGenerating: false,
    selectedModel: null,
    modelStates: {},
    modelPhases: {},
  }),
}))

vi.mock('@/stores/savedDiagrams', () => ({
  useSavedDiagramsStore: () => ({
    get activeDiagramId() {
      return activeState.id
    },
    setActiveDiagram: (id: string | null) => {
      activeState.id = id
      if (activeDiagramRefHolder.ref != null) {
        activeDiagramRefHolder.ref.value = id
      }
      setActiveDiagramMock(id)
    },
    clearActiveDiagram: () => {
      activeState.id = null
      if (activeDiagramRefHolder.ref != null) {
        activeDiagramRefHolder.ref.value = null
      }
      clearActiveDiagramMock()
    },
    fetchDiagrams: fetchDiagramsMock,
  }),
}))

vi.mock('@/composables/kitty/buildKittyDiagramContext', () => ({
  buildKittyContextPreferStore: (panel = 'none') => ({
    diagram_type: 'mindmap',
    active_panel: panel,
    selected_nodes: [],
    diagram_data: { nodes: [] },
    diagram_library_id: 'lib-diagram-1',
    diagram_display_title: 'Demo',
    interaction_language: 'zh' as const,
  }),
  buildKittyDiagramContext: (
    _store: unknown,
    panel: string,
    options?: { oneSentencePhase?: 'create' | 'edit' }
  ) => ({
    diagram_type: 'mindmap',
    active_panel: panel,
    selected_nodes: [],
    diagram_data: { nodes: [{ id: 'topic' }, { id: 'n1' }] },
    diagram_library_id: activeState.id ?? 'lib-diagram-1',
    diagram_display_title: 'Demo',
    interaction_language: 'zh' as const,
    one_sentence_phase: options?.oneSentencePhase,
  }),
  kittyInteractionLanguageFromUi: () => 'zh' as const,
}))

vi.mock('pinia', async () => {
  const actual = await vi.importActual<typeof import('pinia')>('pinia')
  const vue = await import('vue')
  return {
    ...actual,
    storeToRefs: (store: Record<string, unknown>) => {
      const out: Record<string, unknown> = {}
      for (const [k, v] of Object.entries(store)) {
        if (k === 'activeDiagramId') {
          const diagramRef = vue.ref(activeState.id)
          activeDiagramRefHolder.ref = diagramRef
          out[k] = diagramRef
          continue
        }
        out[k] = vue.ref(v)
      }
      return out
    },
  }
})

import { useMobileKittyPairing } from '@/composables/kitty/useMobileKittyPairing'

describe('useMobileKittyPairing one-sentence context', () => {
  let scope: EffectScope

  beforeEach(() => {
    setActivePinia(createPinia())
    scope = effectScope()
    shouldUseEditFlowMock.mockReturnValue(true)
    focusApi.setLibraryId(null, null)
    activeState.id = 'lib-diagram-1'
    activeDiagramRefHolder.ref = null
    setActiveDiagramMock.mockClear()
    clearActiveDiagramMock.mockClear()
    hydrateFromLibraryMock.mockClear()
    fetchDiagramsMock.mockClear()
    loadDefaultTemplateMock.mockClear()
    setDiagramTypeMock.mockClear()
    clearHistoryMock.mockClear()
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          recommended_scope: 'lib-diagram-2',
          desktop_focus: { diagram_library_id: 'lib-diagram-2', updated_at: 1 },
          context: {
            diagram_type: 'mindmap',
            active_panel: 'none',
            diagram_library_id: 'lib-diagram-2',
            diagram_display_title: 'From desk',
            diagram_data: {},
            selected_nodes: [],
          },
          diagram_type: 'mindmap',
          active_panel: 'none',
          source: 'library',
        }),
      }))
    )
  })

  afterEach(() => {
    scope.stop()
  })

  it('sets active_panel one_sentence and edit phase when canvas is edit-ready', () => {
    const kitty = {
      isConnected: ref(true),
      updateContext: vi.fn(),
    } as unknown as Parameters<typeof useMobileKittyPairing>[0]

    const { buildMobileKittyContext, resolveMobileOneSentencePhase } = scope.run(() =>
      useMobileKittyPairing(kitty, {
        kittyServerEnabled: computed(() => true),
      })
    )!

    expect(resolveMobileOneSentencePhase()).toBe('edit')
    const ctx = buildMobileKittyContext()
    expect(ctx.active_panel).toBe('one_sentence')
    expect(ctx.one_sentence_phase).toBe('edit')
    expect(ctx.diagram_library_id).toBe('lib-diagram-1')
    // Thin mobile: never push full Pinia nodes[] — server prefers live_spec.
    expect(ctx.diagram_data).not.toHaveProperty('nodes')
    expect(ctx.diagram_data).not.toHaveProperty('connections')
  })

  it('uses create phase when edit flow is not ready', () => {
    shouldUseEditFlowMock.mockReturnValue(false)
    const kitty = {
      isConnected: ref(true),
      updateContext: vi.fn(),
    } as unknown as Parameters<typeof useMobileKittyPairing>[0]

    const { buildMobileKittyContext, resolveMobileOneSentencePhase } = scope.run(() =>
      useMobileKittyPairing(kitty, {
        kittyServerEnabled: computed(() => true),
      })
    )!

    expect(resolveMobileOneSentencePhase()).toBe('create')
    const ctx = buildMobileKittyContext()
    expect(ctx.active_panel).toBe('one_sentence')
    expect(ctx.one_sentence_phase).toBe('create')
  })

  it('follows desktop_focus while connected: setActiveDiagram + hydrate', async () => {
    const onFollow = vi.fn()
    const kitty = {
      isConnected: ref(true),
      updateContext: vi.fn(),
    } as unknown as Parameters<typeof useMobileKittyPairing>[0]

    const { applyDesktopFocusLibrary } = scope.run(() =>
      useMobileKittyPairing(kitty, {
        kittyServerEnabled: computed(() => true),
        onDesktopDiagramFollow: onFollow,
      })
    )!

    await applyDesktopFocusLibrary('lib-diagram-2')

    expect(setActiveDiagramMock).toHaveBeenCalledWith('lib-diagram-2')
    expect(hydrateFromLibraryMock).toHaveBeenCalledWith('lib-diagram-2')
    expect(onFollow).toHaveBeenCalledWith('lib-diagram-2')
  })

  it('desktop focus watch triggers applyDesktopFocusLibrary for a fresh library id', async () => {
    const onFollow = vi.fn()
    const kitty = {
      isConnected: ref(true),
      updateContext: vi.fn(),
    } as unknown as Parameters<typeof useMobileKittyPairing>[0]

    scope.run(() =>
      useMobileKittyPairing(kitty, {
        kittyServerEnabled: computed(() => true),
        onDesktopDiagramFollow: onFollow,
      })
    )

    focusApi.setLibraryId('lib-diagram-2', Math.floor(Date.now() / 1000))
    await vi.waitFor(() => {
      expect(onFollow).toHaveBeenCalledWith('lib-diagram-2')
    })
    expect(setActiveDiagramMock).toHaveBeenCalledWith('lib-diagram-2')
    expect(hydrateFromLibraryMock).toHaveBeenCalledWith('lib-diagram-2')
  })

  it('ignores stale desktop_focus and does not follow', async () => {
    const onFollow = vi.fn()
    const kitty = {
      isConnected: ref(true),
      updateContext: vi.fn(),
    } as unknown as Parameters<typeof useMobileKittyPairing>[0]

    scope.run(() =>
      useMobileKittyPairing(kitty, {
        kittyServerEnabled: computed(() => true),
        onDesktopDiagramFollow: onFollow,
      })
    )

    focusApi.setLibraryId('lib-diagram-stale', Math.floor(Date.now() / 1000) - 10_000)
    await new Promise((r) => setTimeout(r, 50))
    expect(onFollow).not.toHaveBeenCalled()
  })

  it('promotes residual ephemeral session when desktop saves (desktop_focus follow)', async () => {
    const onFollow = vi.fn()
    const kitty = {
      isConnected: ref(true),
      updateContext: vi.fn(),
    } as unknown as Parameters<typeof useMobileKittyPairing>[0]

    const {
      kittyPairScopeIsEphemeral,
      startNewEphemeralMindmapSession,
      kittyPairScope,
    } = scope.run(() =>
      useMobileKittyPairing(kitty, {
        kittyServerEnabled: computed(() => true),
        onDesktopDiagramFollow: onFollow,
      })
    )!

    const ephemeralScope = startNewEphemeralMindmapSession()
    expect(kittyPairScopeIsEphemeral.value).toBe(true)
    expect(kittyPairScope.value).toBe(ephemeralScope)

    focusApi.setLibraryId('lib-saved-from-desktop', Math.floor(Date.now() / 1000))
    await vi.waitFor(() => {
      expect(onFollow).toHaveBeenCalledWith('lib-saved-from-desktop')
    })

    expect(setActiveDiagramMock).toHaveBeenCalledWith('lib-saved-from-desktop')
    expect(fetchDiagramsMock).toHaveBeenCalled()
    expect(hydrateFromLibraryMock).toHaveBeenCalledWith('lib-saved-from-desktop')
    expect(kittyPairScopeIsEphemeral.value).toBe(false)
    expect(kittyPairScope.value).toBe('lib-saved-from-desktop')
  })

  it('clears to ephemeral session when desktop_focus goes null', async () => {
    const kitty = {
      isConnected: ref(true),
      updateContext: vi.fn(),
    } as unknown as Parameters<typeof useMobileKittyPairing>[0]

    const { kittyPairScopeIsEphemeral, startNewEphemeralMindmapSession } = scope.run(() =>
      useMobileKittyPairing(kitty, {
        kittyServerEnabled: computed(() => true),
      })
    )!

    focusApi.setLibraryId('lib-diagram-2', Math.floor(Date.now() / 1000))
    await vi.waitFor(() => {
      expect(setActiveDiagramMock).toHaveBeenCalledWith('lib-diagram-2')
    })

    focusApi.setLibraryId(null, null)
    await vi.waitFor(() => {
      expect(clearActiveDiagramMock).toHaveBeenCalled()
    })
    expect(kittyPairScopeIsEphemeral.value).toBe(true)
    expect(loadDefaultTemplateMock).toHaveBeenCalledWith('mindmap')
    // create-new path still works
    const sessionScope = startNewEphemeralMindmapSession()
    expect(sessionScope.length).toBeGreaterThan(8)
    expect(kittyPairScopeIsEphemeral.value).toBe(true)
  })

  it('empty bootstrap resets sticky active diagram to ephemeral mindmap', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({
        recommended_scope: null,
        desktop_focus: { diagram_library_id: 'stale-lib', updated_at: 1 },
        context: {
          diagram_type: 'circle_map',
          active_panel: 'none',
          diagram_data: {},
          selected_nodes: [],
        },
        diagram_type: 'circle_map',
        active_panel: 'none',
        source: 'empty',
      }),
    }))
    vi.stubGlobal('fetch', fetchMock)

    const kitty = {
      isConnected: ref(false),
      updateContext: vi.fn(),
    } as unknown as Parameters<typeof useMobileKittyPairing>[0]

    const { ensureMobileKittyBootstrap, kittyPairScopeIsEphemeral, kittyPairScope } = scope.run(
      () =>
        useMobileKittyPairing(kitty, {
          kittyServerEnabled: computed(() => true),
        })
    )!

    await ensureMobileKittyBootstrap()
    // Cold open must not send sticky local library id as suggested_scope.
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/kitty/mobile_open_bootstrap',
      expect.objectContaining({ credentials: 'same-origin' })
    )
    expect(clearActiveDiagramMock).toHaveBeenCalled()
    expect(kittyPairScopeIsEphemeral.value).toBe(true)
    expect(kittyPairScope.value).not.toBe('stale-lib')
    expect(kittyPairScope.value).not.toBe('lib-diagram-1')
    expect(loadDefaultTemplateMock).toHaveBeenCalledWith('mindmap')
  })

  it('hydrateLibraryScopeIfNeeded refreshes bootstrap + hydrates for active library', async () => {
    const kitty = {
      isConnected: ref(true),
      updateContext: vi.fn(),
    } as unknown as Parameters<typeof useMobileKittyPairing>[0]

    const { hydrateLibraryScopeIfNeeded } = scope.run(() =>
      useMobileKittyPairing(kitty, {
        kittyServerEnabled: computed(() => true),
      })
    )!

    await hydrateLibraryScopeIfNeeded('lib-diagram-1')
    expect(hydrateFromLibraryMock).toHaveBeenCalledWith('lib-diagram-1')
    expect(fetch).toHaveBeenCalled()
  })
})
