import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import {
  getDropPreviewBorderRadius,
  getDropTargetShapeClass,
} from '@/composables/diagramCanvas/diagramCanvasZoomPaneStyles'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { useDiagramStore } from '@/stores/diagram'
import { useUIStore } from '@/stores/ui'
import type { MindGraphNode } from '@/types/vueflow'

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

function branchNode(id: string): MindGraphNode {
  return {
    id,
    type: 'branch',
    position: { x: 0, y: 0 },
    data: {
      diagramType: 'mindmap',
      nodeType: 'branch',
      label: id,
    },
  } as MindGraphNode
}

describe('mindmap v2 drop preview shapes', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.stubGlobal('localStorage', {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
      length: 0,
      key: vi.fn(() => null),
    })
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({
        matches: false,
        media: '',
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      }))
    )
    enableMindMapV2Canvas()

    const diagramStore = useDiagramStore()
    diagramStore.loadFromSpec(
      {
        topic: '中心主题',
        rightBranches: [
          {
            text: '分支1',
            children: [{ text: '子项1.1' }],
          },
        ],
        leftBranches: [],
        preserveLeftRight: true,
        _mindmap_diagram_style: 'classic',
      },
      'mindmap'
    )
  })

  it('uses rounded (not pill) radius for classic L1 branches', () => {
    const node = branchNode('branch-r-1-0')
    expect(getDropPreviewBorderRadius(node)).toBe('4.5px')
    expect(getDropTargetShapeClass(node)).toBe('')
  })

  it('uses underline class for classic L2 branches', () => {
    const l2 = useDiagramStore().data?.nodes.find(
      (n) => n.text === '子项1.1' && n.id.startsWith('branch-')
    )
    expect(l2).toBeTruthy()
    const node = branchNode(l2!.id)
    expect(getDropPreviewBorderRadius(node)).toBe('0px')
    expect(getDropTargetShapeClass(node)).toBe('is-underline')
  })

  it('keeps legacy pill radius when canvas mode is classic', () => {
    useUIStore().mindMapCanvasMode = 'legacy'
    const node = branchNode('branch-r-1-0')
    expect(getDropPreviewBorderRadius(node)).toBe('9999px')
    expect(getDropTargetShapeClass(node)).toBe('is-pill')
  })
})
