/**
 * Delete / Backspace must drop the node from the diagram, not only from the canvas.
 * Vue Flow's default Backspace removal is visual until the next nodes prop update.
 */
import { createPinia, setActivePinia } from 'pinia'

import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  isDiagramDeleteKey,
  resolveDiagramDeleteNodeIds,
} from '@/composables/canvasPage/diagramDeleteKey'
import { useDiagramStore } from '@/stores/diagram'
import type { DiagramNode, DiagramType } from '@/types'
import { diagramNodeToVueFlowNode } from '@/types/vueflow'
import { isBraceMapPartNode, isBraceMapReservedId } from '@/utils/braceMapIdentity'
import { isBridgeMapPairNode, readBridgePairIndex } from '@/utils/bridgeMapIdentity'
import { isBubbleMapAttributeNode } from '@/utils/bubbleMapIdentity'
import { isCircleMapContextNode } from '@/utils/circleMapIdentity'
import { readDoubleBubbleRole } from '@/utils/doubleBubbleMapIdentity'
import { isFlowMapStepNode, isFlowMapSubstepNode } from '@/utils/flowMapIdentity'
import { isMindMapBranchId } from '@/utils/mindMapLocation'
import { isMultiFlowCauseNode, isMultiFlowEffectNode } from '@/utils/multiFlowMapIdentity'
import { isTreeMapCategoryNode, isTreeMapLeafNode } from '@/utils/treeMapIdentity'

const DIAGRAM_TYPES: DiagramType[] = [
  'circle_map',
  'bubble_map',
  'double_bubble_map',
  'tree_map',
  'brace_map',
  'flow_map',
  'multi_flow_map',
  'bridge_map',
  'mindmap',
  'concept_map',
]

function deletableNode(type: DiagramType, nodes: DiagramNode[]): DiagramNode | undefined {
  if (type === 'circle_map') return nodes.find((node) => isCircleMapContextNode(node))
  if (type === 'bubble_map') return nodes.find((node) => isBubbleMapAttributeNode(node))
  if (type === 'double_bubble_map') {
    return nodes.find((node) => readDoubleBubbleRole(node) === 'similarity')
  }
  if (type === 'tree_map') {
    return nodes.find((node) => isTreeMapLeafNode(node) || isTreeMapCategoryNode(node))
  }
  if (type === 'brace_map') {
    return nodes.find((node) => isBraceMapPartNode(node) && !isBraceMapReservedId(node.id))
  }
  if (type === 'flow_map') {
    return nodes.find((node) => isFlowMapSubstepNode(node) || isFlowMapStepNode(node))
  }
  if (type === 'multi_flow_map') {
    return nodes.find((node) => isMultiFlowCauseNode(node) || isMultiFlowEffectNode(node))
  }
  if (type === 'bridge_map') return nodes.find((node) => isBridgeMapPairNode(node))
  if (type === 'mindmap' || type === 'mind_map') {
    return nodes.find((node) => isMindMapBranchId(node.id, nodes))
  }
  return nodes.find((node) => node.type !== 'topic' && node.type !== 'center')
}

function deleteLikeKeyboard(
  store: ReturnType<typeof useDiagramStore>,
  type: DiagramType,
  nodeId: string
): number {
  if (type === 'bubble_map') return store.removeBubbleMapNodes([nodeId])
  if (type === 'circle_map') {
    const node = store.data?.nodes.find((item) => item.id === nodeId)
    if (node && isCircleMapContextNode(node) && store.removeNode(nodeId)) return 1
    return 0
  }
  if (type === 'brace_map') return store.removeBraceMapNodes([nodeId])
  if (type === 'multi_flow_map') {
    if (nodeId === 'event') return 0
    return store.removeNode(nodeId) ? 1 : 0
  }
  if (type === 'mindmap' || type === 'mind_map') return store.removeMindMapNodes([nodeId])
  if (type === 'double_bubble_map') return store.removeDoubleBubbleMapNodes([nodeId]).deleted
  if (type === 'tree_map') return store.removeTreeMapNodes([nodeId])
  if (type === 'bridge_map') {
    const node = store.data?.nodes.find((item) => item.id === nodeId)
    const pairIndex = node ? readBridgePairIndex(node) : -1
    if (pairIndex < 0 || !store.data?.nodes) return 0
    const pair = store.data.nodes.filter(
      (item) => isBridgeMapPairNode(item) && readBridgePairIndex(item) === pairIndex
    )
    let deleted = 0
    for (const item of pair) {
      if (store.removeNode(item.id)) deleted += 1
    }
    return deleted
  }
  if (type === 'flow_map') return store.removeNode(nodeId) ? 1 : 0
  return store.removeNode(nodeId) ? 1 : 0
}

describe('diagram delete key resolution', () => {
  it('treats Delete and Backspace as delete, including the key code', () => {
    expect(isDiagramDeleteKey({ key: 'Delete', code: 'Delete' })).toBe(true)
    expect(isDiagramDeleteKey({ key: 'Backspace', code: 'Backspace' })).toBe(true)
    expect(isDiagramDeleteKey({ key: 'Del', code: 'Delete' })).toBe(true)
    expect(isDiagramDeleteKey({ key: 'Enter', code: 'Enter' })).toBe(false)
  })

  it('prefers the canvas highlight and falls back to the store', () => {
    expect(resolveDiagramDeleteNodeIds(['canvas-node'], ['store-node'])).toEqual(['canvas-node'])
    expect(resolveDiagramDeleteNodeIds([], ['store-node'])).toEqual(['store-node'])
    expect(resolveDiagramDeleteNodeIds([''], [])).toEqual([])
  })

  it('marks canvas nodes as not deletable by Vue Flow', () => {
    const flowNode = diagramNodeToVueFlowNode(
      { id: 'n1', text: 'Node', type: 'bubble', position: { x: 0, y: 0 } },
      'circle_map'
    )
    expect(flowNode.deletable).toBe(false)
  })
})

describe('diagram node delete stays gone for every diagram', () => {
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

  it.each(DIAGRAM_TYPES)(
    '%s removes a selected node from the store and the canvas list',
    (type) => {
      const store = useDiagramStore()
      expect(store.loadDefaultTemplate(type)).toBe(true)
      if (type === 'concept_map') {
        store.addNode({
          id: 'concept-delete-test',
          text: 'Concept',
          type: 'branch',
          position: { x: 40, y: 40 },
        })
      }
      const nodes = store.data?.nodes ?? []
      const target = deletableNode(type, nodes)
      expect(target, `${type} template has a deletable node`).toBeTruthy()
      if (!target) return

      const canvasIds = store.vueFlowNodes.map((node) => node.id)
      expect(canvasIds, `${type} canvas id is not in the diagram`).toContain(target.id)

      store.setNodeDimensions(target.id, 120, 48)
      const before = new Map(
        (store.data?.nodes ?? []).map((node) => [
          node.id,
          `${node.position?.x ?? ''},${node.position?.y ?? ''}`,
        ])
      )

      store.selectNodes(target.id)
      const removed = deleteLikeKeyboard(store, type, target.id)
      expect(removed, `${type} delete returned 0`).toBeGreaterThan(0)
      expect(store.data?.nodes.some((node) => node.id === target.id)).toBe(false)
      expect(store.vueFlowNodes.some((node) => node.id === target.id)).toBe(false)
      if (type !== 'mindmap') {
        expect(
          store.getNodeDimension(target.id),
          `${type} kept the deleted measurement`
        ).toBeUndefined()
      }

      if (type !== 'concept_map') {
        const moved = (store.data?.nodes ?? []).filter((node) => {
          const prev = before.get(node.id)
          if (!prev || !node.position) return false
          return prev !== `${node.position.x},${node.position.y}`
        })
        expect(moved.length, `${type} left the deleted slot in place`).toBeGreaterThan(0)
      }
    }
  )
})
