import { beforeEach, describe, expect, it, vi } from 'vitest'

const setDiagramType = vi.fn((type: string) => {
  diagramState.type = type
  return true
})
const reset = vi.fn(() => {
  diagramState.data = null
  diagramState.type = null
  diagramState.collabSessionActive = false
})
const setCollabSessionActive = vi.fn((active: boolean) => {
  diagramState.collabSessionActive = active
})
const clearActiveDiagram = vi.fn(() => {
  savedState.activeDiagramId = null
})

const diagramState = {
  type: null as string | null,
  data: { nodes: [] } as { nodes: unknown[] } | null,
  collabSessionActive: false,
  setDiagramType,
  reset,
  setCollabSessionActive,
}

const savedState = {
  activeDiagramId: 'old-id' as string | null,
  clearActiveDiagram,
}

const closeAllPanels = vi.fn()
const clearNodePaletteState = vi.fn()
const clearAiBrainstormState = vi.fn()

const closeModal = vi.fn()

vi.mock('@/stores', () => ({
  useDiagramStore: () => diagramState,
  useLLMResultsStore: () => ({ reset: vi.fn() }),
  useInlineRecommendationsStore: () => ({ reset: vi.fn() }),
  useConceptMapFocusReviewStore: () => ({ clear: vi.fn() }),
  useConceptMapRelationshipStore: () => ({ clearAll: vi.fn() }),
  useMindClassroomStore: () => ({ closeModal }),
  usePanelsStore: () => ({
    closeAllPanels,
    clearNodePaletteState,
    clearAiBrainstormState,
  }),
}))

vi.mock('@/stores/savedDiagrams', () => ({
  useSavedDiagramsStore: () => savedState,
}))

vi.mock('@/stores/canvasNodeIndicators', () => ({
  useCanvasNodeIndicatorsStore: () => ({ clearAll: vi.fn() }),
}))

vi.mock('@/stores/conceptMapRootConceptReview', () => ({
  useConceptMapRootConceptReviewStore: () => ({ clear: vi.fn() }),
}))

vi.mock('@/stores/diagramTranslateUi', () => ({
  useDiagramTranslateUiStore: () => ({ abortTranslate: vi.fn() }),
}))

vi.mock('@/stores/kittySession', () => ({
  useKittySessionStore: () => ({ resetSessionUi: vi.fn() }),
}))

vi.mock('@/stores/mindMapSubgraphPreview', () => ({
  useMindMapSubgraphPreviewStore: () => ({ clear: vi.fn() }),
}))

vi.mock('@/composables/canvasToolbar/useCanvasVirtualKeyboardOpen', () => ({
  canvasVirtualKeyboardOpen: { value: false },
}))

vi.mock('@/composables/canvasToolbar/useMindMapSideToolbarState', () => ({
  resetMindMapSideToolbarState: vi.fn(),
}))

vi.mock('@/composables/mindMap/useLearningSheetCustomMode', () => ({
  resetLearningSheetCustomModeUi: vi.fn(),
}))

const teardownMindClassroomLecture = vi.fn()
vi.mock('@/composables/mindMap/useMindClassroomLecture', () => ({
  teardownMindClassroomLecture: (...args: unknown[]) => teardownMindClassroomLecture(...args),
}))

describe('unloadCanvasForLibrarySwitch', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    diagramState.type = 'circle_map'
    diagramState.data = { nodes: [] }
    diagramState.collabSessionActive = false
    savedState.activeDiagramId = 'old-id'
  })

  it('clears previous canvas data and applies next chrome type', async () => {
    const { unloadCanvasForLibrarySwitch } = await import(
      '@/composables/canvasPage/unloadCanvasForLibrarySwitch'
    )

    unloadCanvasForLibrarySwitch('mindmap')

    expect(reset).toHaveBeenCalledOnce()
    expect(clearActiveDiagram).toHaveBeenCalledOnce()
    expect(setDiagramType).toHaveBeenCalledWith('mindmap')
    expect(diagramState.data).toBeNull()
    expect(diagramState.type).toBe('mindmap')
    expect(savedState.activeDiagramId).toBeNull()
    expect(closeAllPanels).toHaveBeenCalledOnce()
    expect(clearNodePaletteState).toHaveBeenCalledWith({ clearSessions: false })
    expect(clearAiBrainstormState).toHaveBeenCalledWith({ clearSessions: false })
    expect(teardownMindClassroomLecture).toHaveBeenCalledWith({ restoreViewport: false })
    expect(closeModal).toHaveBeenCalledOnce()
  })

  it('preserves collabSessionActive when a workshop was live', async () => {
    const { unloadCanvasForLibrarySwitch } = await import(
      '@/composables/canvasPage/unloadCanvasForLibrarySwitch'
    )
    diagramState.collabSessionActive = true

    unloadCanvasForLibrarySwitch('circle_map')

    expect(reset).toHaveBeenCalledOnce()
    expect(setCollabSessionActive).toHaveBeenCalledWith(true)
    expect(diagramState.collabSessionActive).toBe(true)
    expect(setDiagramType).toHaveBeenCalledWith('circle_map')
  })
})
