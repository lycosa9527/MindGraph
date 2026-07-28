import { createPinia, setActivePinia } from 'pinia'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useDiagramStore } from '@/stores/diagram'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { useUIStore } from '@/stores/ui'

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

describe('mind map pending post-add inline edit', () => {
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
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  function addSiblingAndGetCreated(): { createdId: string; otherId: string } {
    enableMindMapV2Canvas()
    const diagramStore = useDiagramStore()
    diagramStore.loadDefaultTemplate('mindmap')

    const left = diagramStore.data?.nodes.find((node) => node.id.startsWith('branch-l-'))
    const right = diagramStore.data?.nodes.find((node) => node.id.startsWith('branch-r-'))
    if (!left || !right) {
      throw new Error('expected left and right branches')
    }

    diagramStore.selectNodes(left.id)
    expect(diagramStore.addMindMapSibling(left.id, '新分支')).toBe(true)

    const created = diagramStore.data?.nodes.find((node) => node.text === '新分支')
    if (!created) {
      throw new Error('expected created sibling')
    }
    return { createdId: created.id, otherId: right.id }
  }

  it('arms pending edit on the new sibling after Enter add', () => {
    const diagramStore = useDiagramStore()
    const { createdId } = addSiblingAndGetCreated()

    expect(diagramStore.mindMapPendingEditNodeId).toBe(createdId)
    expect(diagramStore.selectedNodes[0]).toBe(createdId)
  })

  it('keeps pending during remount-echo grace when selection briefly drifts', () => {
    const diagramStore = useDiagramStore()
    const { createdId, otherId } = addSiblingAndGetCreated()

    diagramStore.selectNodes(otherId)
    expect(diagramStore.mindMapPendingEditNodeId).toBe(createdId)
  })

  it('releases pending after grace when user selects another branch', () => {
    const diagramStore = useDiagramStore()
    const { createdId, otherId } = addSiblingAndGetCreated()

    vi.advanceTimersByTime(450)
    diagramStore.selectNodes(otherId)

    expect(diagramStore.mindMapPendingEditNodeId).toBeNull()
    expect(diagramStore.selectedNodes[0]).toBe(otherId)
    expect(diagramStore.selectedNodes[0]).not.toBe(createdId)
  })

  it('releases pending immediately when pointer lands on another vue-flow node', () => {
    const diagramStore = useDiagramStore()
    const { createdId, otherId } = addSiblingAndGetCreated()

    const otherNode = document.createElement('div')
    otherNode.className = 'vue-flow__node'
    otherNode.setAttribute('data-id', otherId)
    document.body.appendChild(otherNode)

    otherNode.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }))

    expect(diagramStore.mindMapPendingEditNodeId).toBeNull()
    expect(createdId).toBeTruthy()

    otherNode.remove()
  })

  it('does not release pending when pointer lands on ephemeral toast UI', () => {
    const diagramStore = useDiagramStore()
    const { createdId } = addSiblingAndGetCreated()

    const toast = document.createElement('div')
    toast.className = 'el-notification'
    document.body.appendChild(toast)

    toast.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }))

    expect(diagramStore.mindMapPendingEditNodeId).toBe(createdId)

    toast.remove()
  })

  it('cancelMindMapPendingInlineEdit clears pending and stops sticky ownership', () => {
    const diagramStore = useDiagramStore()
    const { otherId } = addSiblingAndGetCreated()

    diagramStore.cancelMindMapPendingInlineEdit()
    expect(diagramStore.mindMapPendingEditNodeId).toBeNull()

    diagramStore.selectNodes(otherId)
    expect(diagramStore.selectedNodes[0]).toBe(otherId)
    expect(diagramStore.mindMapPendingEditNodeId).toBeNull()
  })
})
