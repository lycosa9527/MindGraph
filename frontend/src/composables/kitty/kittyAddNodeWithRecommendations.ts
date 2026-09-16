/**
 * Kitty voice: add one canvas node, then open inline recommendations on it.
 */
import { nextTick } from 'vue'

import { isNodeEligibleForInlineRec } from '@/composables/canvasPage/inlineRecEligibility'
import {
  BRANCH_NODE_HEIGHT,
  DEFAULT_CENTER_Y,
  DEFAULT_NODE_WIDTH,
  DEFAULT_PADDING,
} from '@/composables/diagrams/layoutConfig'
import type { useDiagramStore } from '@/stores/diagram'
import { braceMapRootId, isBraceMapSubpartNode } from '@/stores/diagram/braceMapParentResolve'
import { recalculateCircleMapLayout } from '@/stores/specLoader'
import type { Connection, DiagramNode, DiagramType } from '@/types'
import {
  isBridgeMapPairNode,
  readBridgePairIndex,
  takeBridgeMapStableId,
} from '@/utils/bridgeMapIdentity'
import { takeBubbleMapStableId } from '@/utils/bubbleMapIdentity'
import { takeCircleMapStableId } from '@/utils/circleMapIdentity'
import { findFlowMapParentStep, readFlowStepIndex } from '@/utils/flowMapIdentity'
import { mindMapNodeDepth } from '@/utils/mindMapLocation'
import { readMultiFlowRole, takeMultiFlowMapStableId } from '@/utils/multiFlowMapIdentity'
import {
  isTreeMapCategoryNode,
  isTreeMapLeafNode,
  readTreeParentCategoryId,
} from '@/utils/treeMapIdentity'

type DiagramPiniaStore = ReturnType<typeof useDiagramStore>

type TranslateFn = (key: string, fallback?: string) => string

function normalizedType(storeType: DiagramType | null): string {
  if (!storeType) return ''
  return storeType === 'mind_map' ? 'mindmap' : storeType
}

function snapshotNodeIds(store: DiagramPiniaStore): Set<string> {
  return new Set((store.data?.nodes ?? []).map((node) => node.id))
}

function newNodeIds(before: Set<string>, store: DiagramPiniaStore): string[] {
  return (store.data?.nodes ?? []).filter((node) => !before.has(node.id)).map((node) => node.id)
}

function mindmapDepth(
  nodeId: string,
  nodes: DiagramNode[],
  connections: Connection[] | undefined
): number {
  return mindMapNodeDepth(nodeId, {
    node: nodes.find((row) => row.id === nodeId),
    nodes,
    connections,
  })
}

export function pickInlineRecTargetNodeId(
  diagramType: DiagramType | null,
  candidateIds: string[],
  nodes: DiagramNode[],
  connections: Connection[] | undefined
): string | null {
  const dt = normalizedType(diagramType)
  const eligible = candidateIds.filter((id) => {
    const node = nodes.find((row) => row.id === id)
    if (!node) return false
    return isNodeEligibleForInlineRec(dt, node, connections ?? null)
  })
  if (eligible.length === 0) return null
  if (dt === 'mindmap') {
    eligible.sort(
      (a, b) => mindmapDepth(a, nodes, connections) - mindmapDepth(b, nodes, connections)
    )
  }
  return eligible[0] ?? null
}

function addNodeForDiagramType(
  store: DiagramPiniaStore,
  translate: TranslateFn,
  optionalText?: string
): boolean {
  const diagramType = store.type
  if (!diagramType || !store.data?.nodes) return false

  const placeholder = optionalText?.trim() || translate('canvas.toolbar.newAttribute', '…')

  if (diagramType === 'bubble_map') {
    const claimed = new Set(store.data.nodes.map((node) => node.id).filter(Boolean))
    store.addNode({
      id: takeBubbleMapStableId(claimed),
      text: placeholder,
      type: 'bubble',
      position: { x: 0, y: 0 },
    })
    store.pushHistory(translate('canvas.toolbar.addAttributeHistory', 'Add attribute'))
    return true
  }

  if (diagramType === 'circle_map') {
    const claimed = new Set(store.data.nodes.map((node) => node.id).filter(Boolean))
    store.addNode({
      id: takeCircleMapStableId(claimed),
      text: placeholder,
      type: 'bubble',
      position: { x: 0, y: 0 },
    })
    store.data.nodes = recalculateCircleMapLayout(store.data.nodes, store.nodeDimensions)
    store.pushHistory(translate('canvas.toolbar.addNodeHistory', 'Add node'))
    return true
  }

  if (diagramType === 'mindmap' || diagramType === 'mind_map') {
    const selectedId = store.selectedNodes[0]
    if (selectedId && selectedId !== 'topic') {
      return store.addMindMapChild(selectedId, placeholder)
    }
    return store.addMindMapBranch(
      undefined,
      placeholder,
      translate('canvas.toolbar.newChild', 'New child')
    )
  }

  if (diagramType === 'flow_map') {
    const selectedId = store.selectedNodes[0]
    const selectedNode = selectedId
      ? store.data.nodes.find((node) => node.id === selectedId)
      : undefined
    if (selectedNode?.type === 'flowSubstep') {
      const stepNode = findFlowMapParentStep(selectedNode, store.data.nodes)
      if (!stepNode?.text) return false
      const stepIndex = readFlowStepIndex(stepNode)
      return store.addFlowMapSubstep(
        stepNode.text,
        placeholder,
        stepIndex >= 0 ? stepIndex : undefined,
        stepNode.id
      )
    }
    const stepCount = store.data.nodes.filter((node) => node.type === 'flow').length
    const stepNum = stepCount + 1
    const subs: [string, string] = [
      translate('canvas.toolbar.substepDefault1', `Substep ${stepNum}.1`),
      translate('canvas.toolbar.substepDefault2', `Substep ${stepNum}.2`),
    ]
    return store.addFlowMapStep(placeholder, subs)
  }

  if (diagramType === 'tree_map') {
    const selectedId = store.selectedNodes[0]
    if (!selectedId || selectedId === 'tree-topic') {
      return store.addTreeMapCategory(placeholder)
    }
    if (selectedId === 'dimension-label') return false
    const selectedNode = store.data.nodes.find((node) => node.id === selectedId)
    const catId = selectedNode
      ? isTreeMapCategoryNode(selectedNode)
        ? selectedNode.id
        : isTreeMapLeafNode(selectedNode)
          ? readTreeParentCategoryId(selectedNode)
          : null
      : null
    if (!catId) return false
    return store.addTreeMapChild(catId, placeholder)
  }

  if (diagramType === 'multi_flow_map') {
    const selectedId = store.selectedNodes[0]
    const selectedNode = selectedId
      ? store.data.nodes.find((node) => node.id === selectedId)
      : undefined
    const catRaw = (selectedNode as (DiagramNode & { category?: string }) | undefined)?.category
    const selectedRole = selectedNode ? readMultiFlowRole(selectedNode) : null
    const isEffect = catRaw === 'effects' || selectedRole === 'effect'
    const claimed = new Set(store.data.nodes.map((node) => node.id).filter(Boolean))
    store.addNode({
      id: takeMultiFlowMapStableId(claimed),
      text: placeholder,
      type: 'flow',
      position: { x: 0, y: 0 },
      ...(isEffect ? { category: 'effects' } : { category: 'causes' }),
    } as DiagramNode & { category?: string })
    store.pushHistory(
      isEffect
        ? translate('canvas.toolbar.addEffectHistory', 'Add effect')
        : translate('canvas.toolbar.addCauseHistory', 'Add cause')
    )
    return true
  }

  if (diagramType === 'brace_map') {
    const selectedId = store.selectedNodes[0]
    const connections = store.data.connections ?? []
    const rootId = braceMapRootId(store.data.nodes, connections)
    const defaultSubparts: [string, string] = [
      translate('canvas.toolbar.subpartLabel1', 'Part A'),
      translate('canvas.toolbar.subpartLabel2', 'Part B'),
    ]
    if (!rootId) return false
    if (
      !selectedId ||
      selectedId === 'dimension-label' ||
      !isBraceMapSubpartNode(selectedId, connections, rootId)
    ) {
      return store.addBraceMapPart(rootId, placeholder, defaultSubparts)
    }
    return store.addBraceMapPart(selectedId, placeholder)
  }

  if (diagramType === 'bridge_map') {
    const pairNodes = store.data.nodes.filter((node) => isBridgeMapPairNode(node))
    let maxPairIndex = -1
    pairNodes.forEach((node) => {
      const pairIndex = readBridgePairIndex(node)
      if (pairIndex > maxPairIndex) maxPairIndex = pairIndex
    })
    const claimed = new Set(store.data.nodes.map((node) => node.id).filter(Boolean))
    const newPairIndex = maxPairIndex + 1
    const centerY = DEFAULT_CENTER_Y
    const verticalGap = 5
    const nodeWidth = DEFAULT_NODE_WIDTH
    const nodeHeight = BRANCH_NODE_HEIGHT
    const startX = DEFAULT_PADDING + 100 + 10
    let nextX = startX
    if (pairNodes.length > 0) {
      const rightmostX = pairNodes.reduce((maxX, node) => Math.max(maxX, node.position?.x || 0), 0)
      nextX = rightmostX + nodeWidth + 50
    }
    store.addNode({
      id: takeBridgeMapStableId(claimed),
      text: placeholder,
      type: 'branch',
      position: { x: nextX, y: centerY - verticalGap - nodeHeight },
      data: { pairIndex: newPairIndex, position: 'left', diagramType: 'bridge_map' },
    })
    store.pushHistory(translate('canvas.toolbar.addAnalogyPairHistory', 'Add analogy pair'))
    return true
  }

  if (diagramType === 'double_bubble_map') {
    return store.addDoubleBubbleMapNode('similarity', placeholder)
  }

  if (diagramType === 'concept_map') {
    const existing = store.data.nodes.filter((node) => node.id.startsWith('concept-'))
    const nextNum = existing.length
    store.addNode({
      id: `concept-${nextNum}`,
      text: placeholder,
      type: 'branch',
      position: { x: 0, y: 0 },
    })
    store.pushHistory('Add concept')
    return true
  }

  return false
}

export function addKittyNodeForInlineRec(
  store: DiagramPiniaStore,
  translate: TranslateFn,
  optionalText?: string
): string | null {
  const before = snapshotNodeIds(store)
  const ok = addNodeForDiagramType(store, translate, optionalText)
  if (!ok) return null
  const added = newNodeIds(before, store)
  return pickInlineRecTargetNodeId(
    store.type,
    added,
    store.data?.nodes ?? [],
    store.data?.connections
  )
}

export interface KittyAddNodeWithRecHandlerOptions {
  text?: string
  diagramStore: DiagramPiniaStore
  startRecommendations: (nodeId: string) => Promise<{ success: boolean; error?: string }>
  inlineRecReady: boolean
  isAuthenticated: boolean
  conceptMapAiEnabled: boolean
  translate: TranslateFn
  notifyWarning: (message: string) => void
}

export async function handleKittyAddNodeWithRecommendationsRequest(
  options: KittyAddNodeWithRecHandlerOptions
): Promise<void> {
  const nodeId = addKittyNodeForInlineRec(options.diagramStore, options.translate, options.text)
  if (!nodeId) {
    options.notifyWarning(
      options.translate('canvas.toolbar.createDiagramFirst', 'Could not add a node on this canvas')
    )
    return
  }

  options.diagramStore.selectNodes([nodeId])
  await nextTick()

  const nodes = options.diagramStore.data?.nodes ?? []
  const node = nodes.find((row) => row.id === nodeId)
  if (
    !node ||
    !isNodeEligibleForInlineRec(
      options.diagramStore.type,
      node,
      options.diagramStore.data?.connections
    )
  ) {
    options.notifyWarning(options.translate('notification.nodeNotEligible'))
    return
  }
  if (options.diagramStore.type === 'concept_map' && !options.conceptMapAiEnabled) {
    options.notifyWarning(options.translate('notification.conceptMapTabNeedsAi'))
    return
  }
  if (!options.isAuthenticated) {
    options.notifyWarning(options.translate('notification.signInToUse', 'Please sign in'))
    return
  }

  await options.startRecommendations(nodeId)
}
