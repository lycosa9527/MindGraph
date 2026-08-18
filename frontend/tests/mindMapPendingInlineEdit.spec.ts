import { createPinia, setActivePinia } from 'pinia'

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { useDiagramStore } from '@/stores/diagram'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { useUIStore } from '@/stores/ui'
import { isMindMapBranchNode, mindMapNodeSide } from '@/utils/mindMapLocation'

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

    const left = diagramStore.data?.nodes.find(
      (node) =>
        isMindMapBranchNode(node) &&
        mindMapNodeSide(node.id, {
          nodes: diagramStore.data?.nodes,
          connections: diagramStore.data?.connections,
        }) === 'left'
    )
    const right = diagramStore.data?.nodes.find(
      (node) =>
        isMindMapBranchNode(node) &&
        mindMapNodeSide(node.id, {
          nodes: diagramStore.data?.nodes,
          connections: diagramStore.data?.connections,
        }) === 'right'
    )
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
    // Session must NOT arm before first display measure (layout width/X).
    expect(diagramStore.mindMapEditingNodeId).toBeNull()
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

  function mountInlineEditHost(nodeId: string): {
    hostRoot: HTMLElement
    input: HTMLInputElement
    cleanup: () => void
  } {
    const hostRoot = document.createElement('div')
    hostRoot.className = 'vue-flow__node'
    hostRoot.setAttribute('data-id', nodeId)
    const editable = document.createElement('div')
    editable.className = 'inline-editable-text'
    const input = document.createElement('input')
    input.className = 'inline-edit-input'
    editable.appendChild(input)
    hostRoot.appendChild(editable)
    document.body.appendChild(hostRoot)
    return {
      hostRoot,
      input,
      cleanup: () => {
        hostRoot.remove()
      },
    }
  }

  it('arms store edit session after stable focus so remount can reopen', async () => {
    const diagramStore = useDiagramStore()
    const { createdId } = addSiblingAndGetCreated()
    expect(diagramStore.mindMapPendingEditNodeId).toBe(createdId)
    expect(diagramStore.mindMapEditingNodeId).toBeNull()

    // Mount + focus before flushing tryFocus rAFs — otherwise the no-host
    // rAF chain burns max attempts and clears pending.
    const { input, cleanup } = mountInlineEditHost(createdId)
    input.focus()
    expect(document.activeElement).toBe(input)

    // Flush double-rAF start + stable-focus check → session armed, pending cleared.
    await vi.advanceTimersByTimeAsync(48)
    expect(diagramStore.mindMapEditingNodeId).toBe(createdId)
    expect(diagramStore.mindMapPendingEditNodeId).toBeNull()

    // Session survives after pending clear (write-back remount recovery).
    await vi.advanceTimersByTimeAsync(500)
    expect(diagramStore.mindMapEditingNodeId).toBe(createdId)

    diagramStore.clearMindMapEditingNodeId(createdId)
    expect(diagramStore.mindMapEditingNodeId).toBeNull()

    cleanup()
  })

  it('selection-guard attempts alone do not cancel pending while selection returns', async () => {
    const diagramStore = useDiagramStore()
    const { createdId, otherId } = addSiblingAndGetCreated()
    // Host present but unfocused so we only test selection-guard retries.
    const { cleanup } = mountInlineEditHost(createdId)
    expect(diagramStore.mindMapPendingEditNodeId).toBe(createdId)

    // Flush start so tryFocus is in the setTimeout retry loop (not bare rAF).
    await vi.advanceTimersByTimeAsync(32)

    // Echo selection away without selectNodes (no grace-release path). Past the
    // force-reselect window tryFocus must not cancel pending.
    for (let i = 0; i < 15; i += 1) {
      diagramStore.selectedNodes.splice(0, diagramStore.selectedNodes.length, otherId)
      await vi.advanceTimersByTimeAsync(40)
    }

    expect(diagramStore.mindMapPendingEditNodeId).toBe(createdId)

    diagramStore.selectNodes(createdId)
    expect(diagramStore.mindMapPendingEditNodeId).toBe(createdId)
    expect(diagramStore.selectedNodes[0]).toBe(createdId)

    cleanup()
  })
})
