/**
 * useNodeActions — Shared add/delete node logic for all diagram types.
 *
 * Registers event-bus listeners for `diagram:add_node_requested`,
 * `diagram:delete_selected_requested`, `diagram:add_branch_requested`,
 * and `diagram:add_child_requested`.
 *
 * Used by both CanvasToolbar (desktop) and MobileCanvasPage (mobile).
 */
import { onMounted, onUnmounted } from 'vue'

import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import {
  BRANCH_NODE_HEIGHT,
  DEFAULT_CENTER_Y,
  DEFAULT_NODE_WIDTH,
  DEFAULT_PADDING,
} from '@/composables/diagrams/layoutConfig'
import { createThinkingMapLevelAdds } from '@/composables/editor/thinkingMapLevelAdd'
import { consumeMindMapPostEditSiblingAnchor } from '@/composables/mindMap/mindMapCanvasEnterGuard'
import {
  type InsertLabel,
  diagramInsertLabel,
  insertLabelFields,
} from '@/diagramBilingual/insertLabel'
import { doubleBubbleDeleteKeepWarningKey } from '@/stores/diagram/doubleBubbleMapOps'
import { isDiagramPresentationReadOnly } from '@/stores/diagram/presentationReadOnlyGuard'
import { orderFlowStepNodes, substepsForFlowStep } from '@/stores/specLoader/flowMapSubsteps'
import type { MindMapCanvasMode } from '@/stores/ui'
import type { DiagramNode } from '@/types'
import {
  findBridgePairSide,
  isBridgeMapPairNode,
  readBridgePairIndex,
  takeBridgeMapStableId,
} from '@/utils/bridgeMapIdentity'
import { takeBubbleMapStableId } from '@/utils/bubbleMapIdentity'
import { isCircleMapContextNode, takeCircleMapStableId } from '@/utils/circleMapIdentity'
import { readDoubleBubbleRole } from '@/utils/doubleBubbleMapIdentity'
import { findFlowMapParentStep, readFlowStepIndex } from '@/utils/flowMapIdentity'
import { isSessionMindMapV2VisualDesignActive } from '@/utils/mindMapCanvasMode'
import {
  getLastMindMapSiblingInsertFailure,
  isMindMapSiblingDebugEnabled,
  recordMindMapSiblingInsertAttempt,
} from '@/utils/mindMapSiblingDebug'
import { takeMultiFlowMapStableId } from '@/utils/multiFlowMapIdentity'
import { isTreeMapCategoryNode, isTreeMapLeafNode } from '@/utils/treeMapIdentity'

/** V2/V3 canvas: Enter/Tab create focuses inline edit — success toasts steal focus. */
function shouldToastMindMapNodeAdd(sessionMode: MindMapCanvasMode): boolean {
  return !isSessionMindMapV2VisualDesignActive(sessionMode)
}

export type UseNodeActionsOptions = {
  /** When false, primary add skips tree map (desktop toolbar shows "in development"). */
  includeTreeMapPrimaryAdd?: boolean
  /** When false, primary add skips multi-flow (desktop uses Cause / Effect buttons). */
  includeMultiFlowPrimaryAdd?: boolean
  /** When false, skip diagram:* event-bus listeners (parent already registered). */
  registerEventBusListeners?: boolean
}

const DEFAULT_NODE_ACTIONS_OPTIONS: Required<UseNodeActionsOptions> = {
  includeTreeMapPrimaryAdd: true,
  includeMultiFlowPrimaryAdd: true,
  registerEventBusListeners: true,
}

export type DiagramNodeActionBusHandlers = {
  handleAddNode: () => void | Promise<void>
  handleDeleteNode: () => void | Promise<void>
  handleAddBranch: () => void | Promise<void>
  handleAddChild: () => void | Promise<void>
  handleAddSibling: () => void | Promise<void>
}

/** Wire keyboard / outline / sidebar diagram:* requests to node actions. */
export function registerDiagramNodeActionEventBus(
  handlers: DiagramNodeActionBusHandlers,
  owner?: string
): void {
  const bind = <K extends keyof typeof handlers>(
    event:
      | 'diagram:add_node_requested'
      | 'diagram:delete_selected_requested'
      | 'diagram:add_branch_requested'
      | 'diagram:add_child_requested'
      | 'diagram:add_sibling_requested',
    run: K
  ): void => {
    const fn = () => {
      void handlers[run]()
    }
    if (owner) eventBus.onWithOwner(event, fn, owner)
    else eventBus.on(event, fn)
  }

  bind('diagram:delete_selected_requested', 'handleDeleteNode')
  bind('diagram:add_node_requested', 'handleAddNode')
  bind('diagram:add_branch_requested', 'handleAddBranch')
  bind('diagram:add_child_requested', 'handleAddChild')
  bind('diagram:add_sibling_requested', 'handleAddSibling')
}

export function useNodeActions(options: UseNodeActionsOptions = {}) {
  const opts = { ...DEFAULT_NODE_ACTIONS_OPTIONS, ...options }
  const diagramStore = useDiagramSession()
  const { t } = useLanguage()
  const notify = useNotifications()
  const label = (key: string, named?: Record<string, unknown>): InsertLabel =>
    diagramInsertLabel(diagramStore.data?.languages, key, named)
  const {
    addTreeCategoryNode,
    addTreeItemNode,
    addBracePartNode,
    addBraceSubpartNode,
    addBraceNextLevelNode,
    addDoubleBubbleSimilarityNode,
    addDoubleBubbleDifferenceNode,
  } = createThinkingMapLevelAdds(
    diagramStore,
    (key, named) => (named ? t(key, named) : t(key)),
    label,
    notify
  )

  // ---- Add helpers ----

  function selectFlowNode(nodeId: string | undefined): void {
    if (nodeId) diagramStore.selectNodes(nodeId)
  }

  /** Enter and the Add Step button add one step, with no bundled substeps. */
  function addFlowStepNode(): boolean {
    if (!diagramStore.addFlowMapStep(label('canvas.toolbar.newStep'))) return false
    const ordered = orderFlowStepNodes(diagramStore.data?.nodes ?? [])
    selectFlowNode(ordered[ordered.length - 1]?.id)
    notify.successKey('canvas.toolbar.stepAdded')
    return true
  }

  /**
   * Tab and the Add Substep button add one substep.
   * A selected step or substep chooses the parent; otherwise the last step does.
   */
  function addFlowSubstepNode(): boolean {
    const nodes = diagramStore.data?.nodes
    if (!nodes) {
      notify.warningKey('canvas.toolbar.createDiagramFirst')
      return false
    }
    const selectedId = diagramStore.selectedNodes[0]
    const selected = selectedId ? nodes.find((node) => node.id === selectedId) : undefined
    const fromSelection = selected ? findFlowMapParentStep(selected, nodes) : undefined
    const orderedSteps = orderFlowStepNodes(nodes)
    const stepNode = fromSelection ?? orderedSteps[orderedSteps.length - 1]
    if (!stepNode) {
      notify.warningKey('canvas.toolbar.selectStepForSubstep')
      return false
    }
    const addStepIndex = readFlowStepIndex(stepNode)
    const added = diagramStore.addFlowMapSubstep(
      stepNode.text ?? '',
      label('canvas.toolbar.newSubstep'),
      addStepIndex >= 0 ? addStepIndex : undefined,
      stepNode.id
    )
    if (!added) return false
    const refreshed = diagramStore.data?.nodes ?? []
    const parent = refreshed.find((node) => node.id === stepNode.id)
    const children = parent
      ? substepsForFlowStep(
          refreshed.filter((node) => node.type === 'flowSubstep'),
          parent
        )
      : []
    selectFlowNode(children[children.length - 1]?.id)
    notify.successKey('canvas.toolbar.substepAdded')
    return true
  }

  function handleAddBranch(): void {
    if (isDiagramPresentationReadOnly(diagramStore)) return
    const diagramType = diagramStore.type
    if (!diagramStore.data?.nodes) {
      notify.warningKey('canvas.toolbar.createDiagramFirst')
      return
    }

    if (diagramType === 'flow_map') {
      addFlowStepNode()
      return
    }

    if (diagramType === 'brace_map') {
      addBracePartNode()
      return
    }

    if (diagramType !== 'mindmap' && diagramType !== 'mind_map') return

    if (
      diagramStore.addMindMapBranch(
        undefined,
        label('canvas.toolbar.newBranch'),
        label('canvas.toolbar.newChild')
      ) &&
      shouldToastMindMapNodeAdd(diagramStore.mindMapCanvasMode)
    ) {
      notify.successKey('canvas.toolbar.branchAdded')
    }
  }

  function handleAddChild(): void {
    if (isDiagramPresentationReadOnly(diagramStore)) return
    const diagramType = diagramStore.type
    if (!diagramStore.data?.nodes) {
      notify.warningKey('canvas.toolbar.createDiagramFirst')
      return
    }

    if (diagramType === 'multi_flow_map') {
      handleAddEffect()
      return
    }

    if (diagramType === 'tree_map') {
      addTreeItemNode()
      return
    }

    if (diagramType === 'flow_map') {
      addFlowSubstepNode()
      return
    }

    if (diagramType === 'brace_map') {
      addBraceSubpartNode()
      return
    }

    if (diagramType === 'double_bubble_map') {
      addDoubleBubbleDifferenceNode()
      return
    }

    if (diagramType !== 'mindmap' && diagramType !== 'mind_map') return

    const selectedId = diagramStore.selectedNodes[0]
    if (!selectedId || selectedId === 'topic') {
      handleAddBranch()
      return
    }
    if (diagramStore.addMindMapChild(selectedId, label('canvas.toolbar.newChild'))) {
      if (shouldToastMindMapNodeAdd(diagramStore.mindMapCanvasMode)) {
        notify.successKey('canvas.toolbar.childAdded')
      }
    } else {
      notify.warningKey('canvas.toolbar.cannotAddChild')
    }
  }

  function handleAddBraceNextLevel(): void {
    if (isDiagramPresentationReadOnly(diagramStore)) return
    if (diagramStore.type !== 'brace_map') return
    addBraceNextLevelNode()
  }

  function handleAddSibling(): void {
    if (isDiagramPresentationReadOnly(diagramStore)) return
    const diagramType = diagramStore.type
    if (diagramType !== 'mindmap' && diagramType !== 'mind_map') return
    if (!diagramStore.data?.nodes) {
      notify.warningKey('canvas.toolbar.createDiagramFirst')
      return
    }

    const selectedId = diagramStore.selectedNodes[0]
    const anchorId = consumeMindMapPostEditSiblingAnchor(selectedId)
    if (isMindMapSiblingDebugEnabled()) {
      recordMindMapSiblingInsertAttempt({
        stage: 'toolbar_or_enter',
        selectedId: selectedId ?? null,
        resolvedAnchorId: anchorId,
        selectedNodes: diagramStore.selectedNodes.slice(),
      })
    }
    if (!anchorId) {
      if (isMindMapSiblingDebugEnabled()) {
        console.warn('[MindMap sibling debug] no anchor', {
          selectedId: selectedId ?? null,
          selectedNodes: diagramStore.selectedNodes.slice(),
        })
      }
      notify.warningKey('canvas.toolbar.selectBranchForSibling')
      return
    }
    if (diagramStore.addMindMapSibling(anchorId, label('canvas.toolbar.newBranch'))) {
      if (shouldToastMindMapNodeAdd(diagramStore.mindMapCanvasMode)) {
        notify.successKey('canvas.toolbar.siblingAdded')
      }
    } else {
      if (isMindMapSiblingDebugEnabled()) {
        console.warn(
          '[MindMap sibling debug] toast 无法添加同级节点',
          getLastMindMapSiblingInsertFailure()
        )
      }
      notify.warningKey('canvas.toolbar.cannotAddSibling')
    }
  }

  // ---- Main add handler ----

  function handleAddNode(): void {
    if (isDiagramPresentationReadOnly(diagramStore)) return
    const diagramType = diagramStore.type
    if (!diagramStore.data?.nodes) {
      notify.warningKey('canvas.toolbar.createDiagramFirst')
      return
    }

    if (diagramType === 'bubble_map') {
      const claimed = new Set(diagramStore.data.nodes.map((n) => n.id).filter(Boolean))
      diagramStore.addNode({
        id: takeBubbleMapStableId(claimed),
        ...insertLabelFields(label('canvas.toolbar.newAttribute')),
        type: 'bubble',
        position: { x: 0, y: 0 },
      })
      diagramStore.pushHistory(t('canvas.toolbar.addAttributeHistory'))
      notify.successKey('canvas.toolbar.attributeAdded')
      return
    }

    if (diagramType === 'circle_map') {
      const claimed = new Set(diagramStore.data.nodes.map((n) => n.id).filter(Boolean))
      diagramStore.addNode({
        id: takeCircleMapStableId(claimed),
        ...insertLabelFields(label('canvas.toolbar.newAssociation')),
        type: 'bubble',
        position: { x: 0, y: 0 },
      })
      diagramStore.pushHistory(t('canvas.toolbar.addNodeHistory'))
      notify.successKey('canvas.toolbar.nodeAddedCircle')
      return
    }

    if (diagramType === 'bridge_map') {
      const pairNodes = diagramStore.data.nodes.filter((n) => isBridgeMapPairNode(n))
      let maxPairIndex = -1
      pairNodes.forEach((node) => {
        const pi = readBridgePairIndex(node)
        if (pi > maxPairIndex) maxPairIndex = pi
      })
      const newPairIndex = maxPairIndex + 1
      const claimed = new Set(diagramStore.data.nodes.map((n) => n.id).filter(Boolean))

      const centerY = DEFAULT_CENTER_Y
      const verticalGap = 5
      const nodeWidth = DEFAULT_NODE_WIDTH
      const nodeHeight = BRANCH_NODE_HEIGHT
      const startX = DEFAULT_PADDING + 100 + 10

      let nextX = startX
      if (pairNodes.length > 0) {
        const rightmostX = pairNodes.reduce((mx, n) => Math.max(mx, n.position?.x || 0), 0)
        nextX = rightmostX + nodeWidth + 50
      }

      diagramStore.addNode({
        id: takeBridgeMapStableId(claimed),
        ...insertLabelFields(label('canvas.toolbar.newItemA')),
        type: 'branch',
        position: { x: nextX, y: centerY - verticalGap - nodeHeight },
        data: { pairIndex: newPairIndex, position: 'left', diagramType: 'bridge_map' },
      })
      diagramStore.addNode({
        id: takeBridgeMapStableId(claimed),
        ...insertLabelFields(label('canvas.toolbar.newItemB')),
        type: 'branch',
        position: { x: nextX, y: centerY + verticalGap },
        data: { pairIndex: newPairIndex, position: 'right', diagramType: 'bridge_map' },
      })
      diagramStore.pushHistory(t('canvas.toolbar.addAnalogyPairHistory'))
      notify.successKey('canvas.toolbar.analogyPairAdded')
      return
    }

    if (diagramType === 'mindmap' || diagramType === 'mind_map') {
      const selectedId = diagramStore.selectedNodes[0]
      if (!selectedId || selectedId === 'topic') {
        handleAddBranch()
      } else {
        handleAddChild()
      }
      return
    }

    if (diagramType === 'brace_map') {
      addBracePartNode()
      return
    }

    if (diagramType === 'tree_map') {
      if (!opts.includeTreeMapPrimaryAdd) {
        notify.infoKey('canvas.toolbar.addNodeInDevelopment')
        return
      }
      addTreeCategoryNode()
      return
    }

    if (diagramType === 'flow_map') {
      addFlowStepNode()
      return
    }

    if (diagramType === 'double_bubble_map') {
      addDoubleBubbleSimilarityNode()
      return
    }

    if (diagramType === 'multi_flow_map') {
      if (!opts.includeMultiFlowPrimaryAdd) {
        notify.infoKey('canvas.toolbar.addNodeInDevelopment')
        return
      }
      handleAddCause()
      return
    }

    notify.infoKey('canvas.toolbar.addNodeInDevelopment')
  }

  function handleAddCause(): void {
    if (!diagramStore.data?.nodes) {
      notify.warningKey('canvas.toolbar.createDiagramFirst')
      return
    }
    if (diagramStore.type !== 'multi_flow_map') return
    const claimedCause = new Set(diagramStore.data.nodes.map((n) => n.id).filter(Boolean))
    diagramStore.addNode({
      id: takeMultiFlowMapStableId(claimedCause),
      ...insertLabelFields(label('canvas.toolbar.newCause')),
      type: 'flow',
      position: { x: 0, y: 0 },
      category: 'causes',
    } as DiagramNode & { category?: string })
    diagramStore.pushHistory(t('canvas.toolbar.addCauseHistory'))
    notify.successKey('canvas.toolbar.causeAdded')
  }

  function handleAddEffect(): void {
    if (!diagramStore.data?.nodes) {
      notify.warningKey('canvas.toolbar.createDiagramFirst')
      return
    }
    if (diagramStore.type !== 'multi_flow_map') return
    const claimedEffect = new Set(diagramStore.data.nodes.map((n) => n.id).filter(Boolean))
    diagramStore.addNode({
      id: takeMultiFlowMapStableId(claimedEffect),
      ...insertLabelFields(label('canvas.toolbar.newEffect')),
      type: 'flow',
      position: { x: 0, y: 0 },
      category: 'effects',
    } as DiagramNode & { category?: string })
    diagramStore.pushHistory(t('canvas.toolbar.addEffectHistory'))
    notify.successKey('canvas.toolbar.effectAdded')
  }

  // ---- Main delete handler ----

  function handleDeleteNode(): void {
    if (isDiagramPresentationReadOnly(diagramStore)) return
    const diagramType = diagramStore.type
    if (!diagramStore.data?.nodes) {
      notify.warningKey('canvas.toolbar.createDiagramFirst')
      return
    }

    const selectedNodesArray = [...diagramStore.selectedNodes]
    if (selectedNodesArray.length === 0) {
      notify.warningKey('canvas.toolbar.selectNodesToDelete')
      return
    }

    if (diagramType === 'bubble_map') {
      const deleted = diagramStore.removeBubbleMapNodes(selectedNodesArray)
      if (deleted > 0) {
        diagramStore.clearSelection()
        diagramStore.pushHistory(t('canvas.toolbar.deleteAttributeHistory'))
        notify.successKey('canvas.toolbar.deletedAttributes', { count: deleted })
      } else {
        notify.warningKey('canvas.toolbar.cannotDeleteTopic')
      }
      return
    }

    if (diagramType === 'circle_map') {
      let deleted = 0
      for (const nodeId of selectedNodesArray) {
        const node = diagramStore.data.nodes.find((n) => n.id === nodeId)
        if (node && isCircleMapContextNode(node) && diagramStore.removeNode(nodeId)) deleted++
      }
      if (deleted > 0) {
        diagramStore.clearSelection()
        diagramStore.pushHistory(t('canvas.toolbar.deleteNodesHistory'))
        notify.successKey('canvas.toolbar.deletedNodes', { count: deleted })
      } else {
        notify.warningKey('canvas.toolbar.cannotDeleteTopic')
      }
      return
    }

    if (diagramType === 'brace_map') {
      const deleted = diagramStore.removeBraceMapNodes(selectedNodesArray)
      if (deleted > 0) {
        diagramStore.clearSelection()
        diagramStore.pushHistory(t('canvas.toolbar.deleteNodesHistory'))
        notify.successKey('canvas.toolbar.deletedNodes', { count: deleted })
      } else {
        notify.warningKey('canvas.toolbar.cannotDeleteTopic')
      }
      return
    }

    if (diagramType === 'multi_flow_map') {
      let deleted = 0
      for (const nodeId of selectedNodesArray) {
        if (nodeId === 'event') continue
        if (diagramStore.removeNode(nodeId)) deleted++
      }
      if (deleted > 0) {
        diagramStore.clearSelection()
        diagramStore.pushHistory(t('canvas.toolbar.deleteNodesHistory'))
        notify.successKey('canvas.toolbar.deletedNodes', { count: deleted })
      } else {
        notify.warningKey('canvas.toolbar.cannotDeleteEvent')
      }
      return
    }

    if (diagramType === 'mindmap' || diagramType === 'mind_map') {
      const adornmentsCleared = diagramStore.clearMindMapNodeAdornments(selectedNodesArray)
      if (adornmentsCleared > 0) return

      const deleted = diagramStore.removeMindMapNodes(selectedNodesArray)
      if (deleted > 0) {
        diagramStore.clearSelection()
        notify.successKey('canvas.toolbar.deletedNodes', { count: deleted })
      } else {
        notify.warningKey('canvas.toolbar.cannotDeleteTopic')
      }
      return
    }

    if (diagramType === 'double_bubble_map') {
      const toDelete = selectedNodesArray.filter((id) => {
        const node = diagramStore.data?.nodes.find((n) => n.id === id)
        return Boolean(node && readDoubleBubbleRole(node))
      })
      if (toDelete.length === 0) {
        notify.warningKey('canvas.toolbar.selectSimilarityOrDifferenceDelete')
        return
      }
      const outcome = diagramStore.removeDoubleBubbleMapNodes(toDelete)
      if (outcome.deleted > 0) {
        diagramStore.clearSelection()
        diagramStore.pushHistory(t('canvas.toolbar.deleteNodesHistory'))
        notify.successKey('canvas.toolbar.deletedNodes', { count: outcome.deleted })
      }
      const keepKey = doubleBubbleDeleteKeepWarningKey(outcome)
      if (keepKey) notify.warningKey(keepKey)
      return
    }

    if (diagramType === 'tree_map') {
      const toDelete = selectedNodesArray.filter((id) => {
        const node = diagramStore.data?.nodes.find((n) => n.id === id)
        return Boolean(node && (isTreeMapCategoryNode(node) || isTreeMapLeafNode(node)))
      })
      if (toDelete.length === 0) {
        notify.warningKey('canvas.toolbar.selectCategoryOrLeafDelete')
        return
      }
      const deleted = diagramStore.removeTreeMapNodes(toDelete)
      if (deleted > 0) {
        diagramStore.clearSelection()
        notify.successKey('canvas.toolbar.deletedNodes', { count: deleted })
      } else {
        notify.warningKey('canvas.toolbar.cannotDeleteTopicGeneric')
      }
      return
    }

    if (diagramType === 'bridge_map') {
      const pairIndicesToDelete = new Set<number>()
      for (const nodeId of selectedNodesArray) {
        if (nodeId === 'dimension-label') continue
        const node = diagramStore.data.nodes.find((n) => n.id === nodeId)
        const pi = node?.data?.pairIndex
        if (typeof pi === 'number') pairIndicesToDelete.add(pi)
      }
      let deleted = 0
      for (const pi of pairIndicesToDelete) {
        const left = findBridgePairSide(diagramStore.data.nodes, pi, 'left')
        const right = findBridgePairSide(diagramStore.data.nodes, pi, 'right')
        if (left && diagramStore.removeNode(left.id)) deleted++
        if (right && diagramStore.removeNode(right.id)) deleted++
      }
      if (deleted > 0) {
        diagramStore.clearSelection()
        diagramStore.pushHistory(t('canvas.toolbar.deleteAnalogyPairHistory'))
        notify.successKey('canvas.toolbar.deletedAnalogyPairs', { count: pairIndicesToDelete.size })
      } else {
        notify.warningKey('canvas.toolbar.cannotDeleteDimension')
      }
      return
    }

    if (diagramType === 'flow_map') {
      const deleted = selectedNodesArray.reduce(
        (c, id) => c + (diagramStore.removeNode(id) ? 1 : 0),
        0
      )
      if (deleted > 0) {
        diagramStore.clearSelection()
        diagramStore.pushHistory(t('canvas.toolbar.deleteNodesHistory'))
        notify.successKey('canvas.toolbar.deletedNodes', { count: deleted })
      } else {
        notify.warningKey('canvas.toolbar.cannotDeleteSelected')
      }
      return
    }

    let deleted = 0
    for (const nodeId of selectedNodesArray) {
      if (diagramStore.removeNode(nodeId)) deleted++
    }
    if (deleted > 0) {
      diagramStore.clearSelection()
      diagramStore.pushHistory(t('canvas.toolbar.deleteNodesHistory'))
      notify.successKey('canvas.toolbar.deletedNodes', { count: deleted })
    } else {
      notify.warningKey('canvas.toolbar.cannotDeleteSelected')
    }
  }

  // ---- Lifecycle: auto-register event listeners ----

  const onDiagramAddNodeRequested = () => {
    void handleAddNode()
  }
  const onDiagramDeleteSelectedRequested = () => {
    void handleDeleteNode()
  }
  const onDiagramAddBranchRequested = () => {
    void handleAddBranch()
  }
  const onDiagramAddChildRequested = () => {
    void handleAddChild()
  }
  const onDiagramAddSiblingRequested = () => {
    void handleAddSibling()
  }

  onMounted(() => {
    if (!opts.registerEventBusListeners) return
    eventBus.on('diagram:add_node_requested', onDiagramAddNodeRequested)
    eventBus.on('diagram:delete_selected_requested', onDiagramDeleteSelectedRequested)
    eventBus.on('diagram:add_branch_requested', onDiagramAddBranchRequested)
    eventBus.on('diagram:add_child_requested', onDiagramAddChildRequested)
    eventBus.on('diagram:add_sibling_requested', onDiagramAddSiblingRequested)
  })

  onUnmounted(() => {
    if (!opts.registerEventBusListeners) return
    eventBus.off('diagram:add_node_requested', onDiagramAddNodeRequested)
    eventBus.off('diagram:delete_selected_requested', onDiagramDeleteSelectedRequested)
    eventBus.off('diagram:add_branch_requested', onDiagramAddBranchRequested)
    eventBus.off('diagram:add_child_requested', onDiagramAddChildRequested)
    eventBus.off('diagram:add_sibling_requested', onDiagramAddSiblingRequested)
  })

  return {
    handleAddNode,
    handleDeleteNode,
    handleAddBranch,
    handleAddChild,
    handleAddBraceNextLevel,
    handleAddSibling,
    handleAddCause,
    handleAddEffect,
  }
}
