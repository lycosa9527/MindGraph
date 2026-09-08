import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { peekKittyPendingDesktopExplain } from '@/composables/kitty/kittyPendingCanvasAction'

const emitMock = vi.hoisted(() => vi.fn())
const applySelectionMock = vi.hoisted(() => vi.fn())
const confirmOpenMock = vi.hoisted(() => vi.fn(async () => true))

vi.mock('@/composables/core/useEventBus', () => ({
  eventBus: {
    emit: emitMock,
  },
}))

vi.mock('@/composables/kitty/kittySelectionApply', () => ({
  applyKittySelectionTarget: applySelectionMock,
}))

vi.mock('@/composables/kitty/kittyWorkflowTrace', () => ({
  traceKittyWorkflow: vi.fn(),
}))

vi.mock('@/composables/canvasPage/canvasLibraryDiagramOpen', async (importOriginal) => {
  const mod = await importOriginal<typeof import('@/composables/canvasPage/canvasLibraryDiagramOpen')>()
  return {
    ...mod,
    confirmCanvasLibraryDiagramOpen: (...args: unknown[]) => confirmOpenMock(...args),
  }
})

import {
  handleKittyDesktopQueuedAction,
  handleKittyExplainNodeAction,
} from '@/composables/kitty/kittyDesktopActionHandlers'

describe('handleKittyExplainNodeAction', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    sessionStorage.clear()
    emitMock.mockClear()
    applySelectionMock.mockClear()
    confirmOpenMock.mockReset()
    confirmOpenMock.mockResolvedValue(true)
  })

  it('selects the node and emits mindmap explain (节点解释)', async () => {
    await handleKittyExplainNodeAction({
      kind: 'explain_node',
      node_id: 'branch-r-1-0',
      node_label: '广东',
    })

    expect(applySelectionMock).toHaveBeenCalledWith(
      { nodeId: 'branch-r-1-0' },
      { canvasHighlight: true }
    )
    expect(emitMock).toHaveBeenCalledWith('mindmap:explain_node_requested', {
      nodeId: 'branch-r-1-0',
    })
  })

  it('queued action dispatcher routes explain_node', async () => {
    await handleKittyDesktopQueuedAction(
      { kind: 'explain_node', node_id: 'topic' },
      {
        routePath: '/canvas',
        savedDiagramsStore: { activeDiagramId: 'lib-1' } as never,
        router: { push: vi.fn() } as never,
        t: (key, fallback) => fallback ?? key,
      }
    )

    expect(emitMock).toHaveBeenCalledWith('mindmap:explain_node_requested', {
      nodeId: 'topic',
    })
  })

  it('ignores missing node id', async () => {
    await handleKittyExplainNodeAction({ kind: 'explain_node', node_id: '  ' })
    expect(applySelectionMock).not.toHaveBeenCalled()
    expect(emitMock).not.toHaveBeenCalled()
  })

  it('stashes explain and opens the library when desktop is not on canvas', async () => {
    sessionStorage.clear()
    const push = vi.fn(async () => undefined)
    await handleKittyExplainNodeAction(
      {
        kind: 'explain_node',
        node_id: 'branch-1',
        diagram_library_id: 'lib-diagram-9',
      },
      {
        routePath: '/library',
        savedDiagramsStore: { activeDiagramId: null } as never,
        router: { push } as never,
        t: (key, fallback) => fallback ?? key,
      }
    )
    expect(emitMock).not.toHaveBeenCalled()
    expect(peekKittyPendingDesktopExplain()).toEqual({
      nodeId: 'branch-1',
      libraryId: 'lib-diagram-9',
    })
    expect(push).toHaveBeenCalledWith({
      path: '/canvas',
      query: { diagramId: 'lib-diagram-9' },
    })
  })

  it('clears pending explain when the user declines a canvas switch', async () => {
    sessionStorage.clear()
    confirmOpenMock.mockResolvedValueOnce(false)
    const push = vi.fn(async () => undefined)
    await handleKittyExplainNodeAction(
      {
        kind: 'explain_node',
        node_id: 'topic',
        diagram_library_id: 'lib-other',
      },
      {
        routePath: '/canvas',
        savedDiagramsStore: {
          activeDiagramId: 'lib-current',
          diagrams: [{ id: 'lib-current', title: 'Current' }],
        } as never,
        router: { push } as never,
        t: (key, fallback) => fallback ?? key,
      }
    )
    expect(emitMock).not.toHaveBeenCalled()
    expect(push).not.toHaveBeenCalled()
    expect(peekKittyPendingDesktopExplain()).toBeNull()
  })
})
