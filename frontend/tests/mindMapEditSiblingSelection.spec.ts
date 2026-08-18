import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useDiagramStore } from '@/stores/diagram'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { useUIStore } from '@/stores/ui'
import { isMindMapBranchNode, mindMapNodeSide } from '@/utils/mindMapLocation'
import { MINDMAP_NODE_UID_DATA_KEY } from '@/utils/mindMapNodeUid'

function nodeSide(
  nodeId: string,
  nodes: { id: string; type?: string; data?: Record<string, unknown> }[],
  connections: { source: string; target: string; sourceHandle?: string }[]
): 'left' | 'right' | 'topic' {
  if (nodeId === 'topic') return 'topic'
  const side = mindMapNodeSide(nodeId, { nodes, connections })
  if (side === 'left' || side === 'right') return side
  throw new Error(`unexpected node id: ${nodeId}`)
}

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

describe('mind map sibling selection anchor', () => {
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
  })

  function loadBranches(): { leftId: string; rightId: string } {
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
      throw new Error('expected left and right branches in default mind map template')
    }
    return { leftId: left.id, rightId: right.id }
  }

  function newestSiblingNodeId(beforeIds: Set<string>): string {
    const diagramStore = useDiagramStore()
    const added = diagramStore.data?.nodes.find(
      (node) => isMindMapBranchNode(node) && !beforeIds.has(node.id)
    )
    if (!added) {
      throw new Error('expected a newly added branch node')
    }
    return added.id
  }

  it('adds sibling on the same side as the selected anchor branch', () => {
    const diagramStore = useDiagramStore()
    const { rightId } = loadBranches()
    const beforeIds = new Set(diagramStore.data?.nodes.map((node) => node.id) ?? [])

    diagramStore.selectNodes(rightId)
    expect(diagramStore.addMindMapSibling(rightId, 'Right sibling')).toBe(true)

    const newId = newestSiblingNodeId(beforeIds)
    expect(
      nodeSide(newId, diagramStore.data?.nodes ?? [], diagramStore.data?.connections ?? [])
    ).toBe('right')
  })

  it('uses stale left selection when anchor id is not updated (regression)', () => {
    const diagramStore = useDiagramStore()
    const { leftId, rightId } = loadBranches()
    const beforeIds = new Set(diagramStore.data?.nodes.map((node) => node.id) ?? [])

    diagramStore.selectNodes(leftId)
    expect(diagramStore.addMindMapSibling(leftId, 'Left sibling')).toBe(true)

    const newId = newestSiblingNodeId(beforeIds)
    expect(
      nodeSide(newId, diagramStore.data?.nodes ?? [], diagramStore.data?.connections ?? [])
    ).toBe('left')
    expect(newId).not.toBe(rightId)
  })

  it('v2 Enter selects the new sibling, not the L1 anchor', () => {
    enableMindMapV2Canvas()
    const diagramStore = useDiagramStore()
    const { leftId } = loadBranches()
    const anchor = diagramStore.data?.nodes.find((node) => node.id === leftId)
    if (anchor) {
      anchor.data = {
        ...anchor.data,
        [MINDMAP_NODE_UID_DATA_KEY]: 'anchor-uid',
        estimatedHeight: 40,
      }
    }

    const beforeIds = (diagramStore.data?.nodes ?? [])
      .filter((node) => isMindMapBranchNode(node))
      .map((node) => node.id)
      .sort()
    diagramStore.selectNodes(leftId)
    expect(diagramStore.addMindMapSibling(leftId, '新分支')).toBe(true)

    const created = diagramStore.data?.nodes.find((node) => node.text === '新分支')
    expect(created).toBeTruthy()
    if (!created) {
      throw new Error('expected created sibling node')
    }
    expect(diagramStore.selectedNodes[0]).toBe(created.id)
    expect(diagramStore.selectedNodes).not.toContain(
      diagramStore.data?.nodes.find(
        (node) => node.data?.[MINDMAP_NODE_UID_DATA_KEY] === 'anchor-uid'
      )?.id
    )

    const remappedAnchor = diagramStore.data?.nodes.find(
      (node) => node.data?.[MINDMAP_NODE_UID_DATA_KEY] === 'anchor-uid'
    )
    expect(remappedAnchor?.id).toBe(leftId)
    // Side-pack may rigid-slide absolute Y; new sibling stays below the anchor.
    expect(created.position?.y).toBeGreaterThan(remappedAnchor?.position?.y ?? Number.NaN)

    const afterExisting = (diagramStore.data?.nodes ?? [])
      .filter((node) => isMindMapBranchNode(node) && node.id !== created.id)
      .map((node) => node.id)
      .sort()
    expect(afterExisting).toEqual(beforeIds)

    const topicChildTargets = (diagramStore.data?.connections ?? [])
      .filter(
        (c) =>
          c.source === 'topic' &&
          mindMapNodeSide(c.target, {
            nodes: diagramStore.data?.nodes,
            connections: diagramStore.data?.connections,
          }) === 'left'
      )
      .map((c) => c.target)
    const leftIdx = topicChildTargets.indexOf(leftId)
    expect(topicChildTargets[leftIdx + 1]).toBe(created.id)
  })
})
