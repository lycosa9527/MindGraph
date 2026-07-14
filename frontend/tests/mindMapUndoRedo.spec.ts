import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  tryCollabGuardedRedo,
  tryCollabGuardedUndo,
} from '@/composables/canvasPage/useCanvasCollabHistoryGuard'
import { eventBus } from '@/composables/core/useEventBus'
import { useDiagramCanvasEventBus } from '@/composables/diagramCanvas/useDiagramCanvasEventBus'
import { useDiagramStore } from '@/stores/diagram'

describe('mind map undo/redo', () => {
  let unmountEventBus: (() => void) | null = null

  beforeEach(() => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: false,
        media: '',
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        addListener: vi.fn(),
        removeListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }))
    )
    setActivePinia(createPinia())

    const diagramStore = useDiagramStore()
    const { mountSubscriptions } = useDiagramCanvasEventBus()
    unmountEventBus = mountSubscriptions({
      diagramStore,
      getNodes: () => diagramStore.vueFlowNodes,
      getViewport: () => ({ x: 0, y: 0, zoom: 1 }),
      setViewport: () => {},
      zoomIn: () => {},
      zoomOut: () => {},
      fitApi: {
        fitToFullCanvas: () => {},
        fitWithPanel: () => {},
        fitDiagram: () => {},
        fitForExport: () => {},
        fitToNodes: async () => {},
      },
      emit: () => {},
      exportByFormat: async () => {},
      showExportToCommunityModal: { value: false } as { value: boolean },
      getExportContainer: () => null,
      prepareForCommunityExport: async () => {},
      restoreViewportAfterCommunityExport: () => {},
      regenerateForNodeIfNeeded: () => {},
    })
  })

  afterEach(() => {
    unmountEventBus?.()
    unmountEventBus = null
  })

  function loadMindMapWithBranch(): { branchId: string; branchText: string } {
    const diagramStore = useDiagramStore()
    diagramStore.loadDefaultTemplate('mindmap')
    diagramStore.seedHistoryBaselineIfEmpty()

    const branch = diagramStore.data?.nodes.find(
      (node) => node.id.startsWith('branch-') && String(node.text ?? '').trim().length > 0
    )
    if (!branch) {
      throw new Error('expected a branch node in default mind map template')
    }

    return { branchId: branch.id, branchText: String(branch.text ?? '').trim() }
  }

  it('undoes and redoes branch text edits via node:text_updated', () => {
    const diagramStore = useDiagramStore()
    const { branchId, branchText } = loadMindMapWithBranch()
    const editedText = `${branchText} edited`

    eventBus.emit('node:text_updated', { nodeId: branchId, text: editedText })

    const edited = diagramStore.data?.nodes.find((node) => node.id === branchId)
    expect(edited?.text).toBe(editedText)
    expect(diagramStore.canUndo).toBe(true)
    expect(diagramStore.canRedo).toBe(false)

    tryCollabGuardedUndo()
    const undone = diagramStore.data?.nodes.find((node) => node.id === branchId)
    expect(undone?.text).toBe(branchText)
    expect(diagramStore.canRedo).toBe(true)

    tryCollabGuardedRedo()
    const redone = diagramStore.data?.nodes.find((node) => node.id === branchId)
    expect(redone?.text).toBe(editedText)
  })

  it('undoes add sibling below the selected branch', () => {
    const diagramStore = useDiagramStore()
    const { branchId } = loadMindMapWithBranch()

    diagramStore.selectNodes(branchId)
    const added = diagramStore.addMindMapSibling(branchId, 'Sibling test')
    expect(added).toBe(true)
    expect(
      diagramStore.data?.nodes.some((node) => String(node.text ?? '').includes('Sibling test'))
    ).toBe(true)
    expect(diagramStore.canUndo).toBe(true)

    tryCollabGuardedUndo()
    expect(
      diagramStore.data?.nodes.some((node) => String(node.text ?? '').includes('Sibling test'))
    ).toBe(false)
  })
})
