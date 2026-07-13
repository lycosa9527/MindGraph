/**
 * Durable create-new: library draft + open_library_diagram (no ephemeral open_canvas).
 */
import { effectScope, type EffectScope } from 'vue'

import { beforeEach, describe, expect, it, vi } from 'vitest'

const saveDiagramMock = vi.hoisted(() =>
  vi.fn(async () => ({ id: 'lib-new-1', title: '新建思维导图' }))
)
const setActiveDiagramMock = vi.hoisted(() => vi.fn())
const clearForceMock = vi.hoisted(() => vi.fn())
const reportIngressMock = vi.hoisted(() => vi.fn(async () => undefined))
const getSpecForSaveMock = vi.hoisted(() => vi.fn(() => ({ topic: '', children: [] })))
const loadDefaultTemplateMock = vi.hoisted(() => vi.fn(() => true))
const notifyWarning = vi.hoisted(() => vi.fn())
const notifySuccess = vi.hoisted(() => vi.fn())
const notifyError = vi.hoisted(() => vi.fn())
const canSaveMoreState = vi.hoisted(() => ({ value: true }))

vi.mock('@/composables', () => ({
  useLanguage: () => ({
    t: (_key: string, fallback: string) => fallback,
  }),
  useNotifications: () => ({
    warning: notifyWarning,
    success: notifySuccess,
    error: notifyError,
  }),
}))

vi.mock('@/composables/kitty/useKittySessionManager', () => ({
  reportKittySessionIngress: reportIngressMock,
}))

vi.mock('@/composables/kitty/kittyWorkflowTrace', () => ({
  traceKittyWorkflow: vi.fn(),
}))

vi.mock('@/utils/safeRandomUUID', () => ({
  safeRandomUUID: () => 'req-1',
}))

vi.mock('@/stores/diagram', () => ({
  useDiagramStore: () => ({
    clearHistory: vi.fn(),
    setDiagramType: vi.fn(),
    loadDefaultTemplate: loadDefaultTemplateMock,
    getSpecForSave: getSpecForSaveMock,
  }),
}))

vi.mock('@/stores/ui', () => ({
  useUIStore: () => ({ language: 'zh' }),
}))

vi.mock('@/stores/savedDiagrams', () => ({
  useSavedDiagramsStore: () => ({
    get canSaveMore() {
      return canSaveMoreState.value
    },
    saveDiagram: saveDiagramMock,
    setActiveDiagram: setActiveDiagramMock,
    error: null,
    fetchDiagrams: vi.fn(async () => undefined),
  }),
}))

import { useKittyMobileLibraryDiagramSelect } from '@/composables/kitty/useKittyMobileLibraryDiagramSelect'

describe('useKittyMobileLibraryDiagramSelect createNewMindmap', () => {
  let scope: EffectScope
  const fetchMock = vi.fn()

  beforeEach(() => {
    scope = effectScope()
    vi.clearAllMocks()
    canSaveMoreState.value = true
    loadDefaultTemplateMock.mockReturnValue(true)
    getSpecForSaveMock.mockReturnValue({ topic: '', children: [] })
    saveDiagramMock.mockResolvedValue({ id: 'lib-new-1', title: '新建思维导图' })
    globalThis.fetch = fetchMock as unknown as typeof fetch
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true }),
    })
  })

  it('saves a library draft and enqueues open_library_diagram', async () => {
    const refreshBootstrap = vi.fn(async () => undefined)
    const hydrateFromLibrary = vi.fn(async () => true)
    const scheduleContextSync = vi.fn()

    const { createNewMindmap } = scope.run(() =>
      useKittyMobileLibraryDiagramSelect({
        scheduleContextSync,
        refreshBootstrap,
        hydrateFromLibrary,
        hydrateStoreFromBootstrap: vi.fn(),
        clearForceEphemeralSession: clearForceMock,
      })
    )!

    await createNewMindmap()

    expect(clearForceMock).toHaveBeenCalled()
    expect(saveDiagramMock).toHaveBeenCalledWith(
      '新建思维导图',
      'mindmap',
      { topic: '', children: [] },
      'zh'
    )
    expect(setActiveDiagramMock).toHaveBeenCalledWith('lib-new-1')
    expect(reportIngressMock).toHaveBeenCalledWith(
      'lib-new-1',
      expect.objectContaining({ source: 'ui_create', lane: 'mobile' })
    )
    expect(refreshBootstrap).toHaveBeenCalledWith('lib-new-1')
    expect(hydrateFromLibrary).toHaveBeenCalledWith('lib-new-1')
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/kitty/desktop_action/enqueue',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          kind: 'open_library_diagram',
          diagram_library_id: 'lib-new-1',
          title: '新建思维导图',
        }),
      })
    )
    expect(notifySuccess).toHaveBeenCalled()
    expect(scheduleContextSync).toHaveBeenCalled()
  })

  it('blocks create when library slots are full', async () => {
    canSaveMoreState.value = false
    const { createNewMindmap } = scope.run(() =>
      useKittyMobileLibraryDiagramSelect({
        scheduleContextSync: vi.fn(),
        refreshBootstrap: vi.fn(async () => undefined),
        hydrateFromLibrary: vi.fn(async () => true),
        hydrateStoreFromBootstrap: vi.fn(),
      })
    )!

    await createNewMindmap()

    expect(saveDiagramMock).not.toHaveBeenCalled()
    expect(fetchMock).not.toHaveBeenCalled()
    expect(notifyWarning).toHaveBeenCalled()
  })
})
