import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  tryCollabGuardedRedo,
  tryCollabGuardedUndo,
} from '@/composables/canvasPage/useCanvasCollabHistoryGuard'
import { eventBus } from '@/composables/core/useEventBus'
import { useDiagramCanvasEventBus } from '@/composables/diagramCanvas/useDiagramCanvasEventBus'
import { useDiagramStore } from '@/stores/diagram'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { useUIStore } from '@/stores/ui'
import type { NodeStyle } from '@/types'

function enableMindMapV2Canvas(): void {
  const flagsStore = useFeatureFlagsStore()
  flagsStore.flags = {
    external_base_url: '',
    feature_rag_chunk_test: false,
    feature_course: false,
    feature_template: false,
    feature_community: false,
    feature_showcase: false,
    feature_askonce: true,
    feature_debateverse: false,
    feature_knowledge_space: false,
    feature_mindmap_v2_canvas: true,
    feature_library: false,
    feature_gewe: false,
    feature_smart_response: false,
    feature_teacher_usage: false,
    feature_workshop_chat: false,
    feature_markets: false,
    feature_mindbot: false,
    feature_mindmate_export: false,
    feature_kitty_agent: false,
    feature_auth_pixel_battle: false,
    feature_test_server_banner: false,
    feature_thinking_coins: false,
    workshop_chat_preview_org_ids: [],
    feature_org_access: {},
  }
  useUIStore().mindMapCanvasMode = 'v2'
}

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
    enableMindMapV2Canvas()

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
      capturePngBlob: async () => new Blob(),
      copyPngToClipboard: async () => {},
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

  it('Enter sibling matches selected style and undo clears seeded _node_styles', () => {
    const diagramStore = useDiagramStore()
    const { branchId } = loadMindMapWithBranch()
    const custom: NodeStyle = {
      backgroundColor: '#dbeafe',
      borderColor: '#0f766e',
      textColor: '#134e4a',
      nodeShape: 'oval',
    }
    diagramStore.updateNode(branchId, { style: custom })
    if (diagramStore.data) {
      diagramStore.data._mindmap_diagram_style = 'bubble'
      diagramStore.data._mindmap_theme = 'vibrantBlue'
    }

    const beforeIds = new Set(diagramStore.data?.nodes.map((node) => node.id) ?? [])
    diagramStore.selectNodes(branchId)
    expect(diagramStore.addMindMapSibling(branchId, 'Styled sibling')).toBe(true)

    const newNode = diagramStore.data?.nodes.find(
      (node) => !beforeIds.has(node.id) && String(node.text ?? '').includes('Styled sibling')
    )
    expect(newNode).toBeTruthy()
    const seeded = diagramStore.data?._node_styles?.[newNode!.id]
    expect(seeded?.backgroundColor).toBe('#dbeafe')
    expect(seeded?.borderColor).toBe('#0f766e')
    expect(seeded?.nodeShape).toBe('oval')
    expect(newNode?.style?.backgroundColor).toBe('#dbeafe')

    tryCollabGuardedUndo()
    expect(diagramStore.data?.nodes.some((node) => node.id === newNode!.id)).toBe(false)
    expect(diagramStore.data?._node_styles?.[newNode!.id]).toBeUndefined()
  })
})
