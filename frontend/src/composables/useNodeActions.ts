/**
 * useNodeActions — Shared add/delete node logic for all diagram types.
 *
 * Registers event-bus listeners for `diagram:add_node_requested`,
 * `diagram:delete_selected_requested`, `diagram:add_branch_requested`,
 * and `diagram:add_child_requested`.
 *
 * Used by both CanvasToolbar (desktop) and MobileCanvasPage (mobile).
 */
import { nextTick, onMounted, onUnmounted } from 'vue'

import {
  BRANCH_NODE_HEIGHT,
  DEFAULT_CENTER_Y,
  DEFAULT_NODE_WIDTH,
  DEFAULT_PADDING,
} from '@/composables/diagrams/layoutConfig'
import { eventBus } from '@/composables/useEventBus'
import { useLanguage } from '@/composables/useLanguage'
import { useNotifications } from '@/composables/useNotifications'
import { useDiagramStore } from '@/stores'
import type { DiagramNode } from '@/types'


function getDoubleBubbleGroup(
  nodeId: string | undefined,
): 'similarity' | 'leftDiff' | 'rightDiff' | null {
  if (!nodeId) return null
  if (/^similarity-\d+$/.test(nodeId)) return 'similarity'
  if (/^left-diff-\d+$/.test(nodeId)) return 'leftDiff'
  if (/^right-diff-\d+$/.test(nodeId)) return 'rightDiff'
  return null
}

export function useNodeActions() {
  const diagramStore = useDiagramStore()
  const { t } = useLanguage()
  const notify = useNotifications()

  // ---- Add helpers ----

  function handleAddBranch(): void {
    const diagramType = diagramStore.type
    if (!diagramStore.data?.nodes) {
      notify.warning(t('canvas.toolbar.createDiagramFirst'))
      return
    }

    if (diagramType === 'flow_map') {
      const stepCount = diagramStore.data.nodes.filter((n) => n.type === 'flow').length
      const stepNum = stepCount + 1
      const subs: [string, string] = [
        t('canvas.toolbar.substepDefault1', { n: stepNum }),
        t('canvas.toolbar.substepDefault2', { n: stepNum }),
      ]
      if (diagramStore.addFlowMapStep(t('canvas.toolbar.newStep'), subs)) {
        diagramStore.pushHistory(t('canvas.toolbar.addStepHistory'))
        notify.success(t('canvas.toolbar.stepAdded'))
      }
      return
    }

    if (diagramType === 'brace_map') {
      const targetIds = new Set(diagramStore.data.connections?.map((c) => c.target) ?? [])
      const rootId =
        diagramStore.data.nodes.find((n) => n.type === 'topic')?.id ??
        diagramStore.data.nodes.find((n) => !targetIds.has(n.id))?.id
      if (!rootId) return
      const subparts: [string, string] = [
        t('canvas.toolbar.subpartLabel1'),
        t('canvas.toolbar.subpartLabel2'),
      ]
      if (diagramStore.addBraceMapPart(rootId, t('canvas.toolbar.newPart'), subparts)) {
        notify.success(t('canvas.toolbar.partAdded'))
      }
      return
    }

    if (diagramType !== 'mindmap' && diagramType !== 'mind_map') return

    const selectedId = diagramStore.selectedNodes[0]
    const side: 'left' | 'right' = selectedId?.startsWith('branch-l-') ? 'left' : 'right'
    if (diagramStore.addMindMapBranch(side, t('canvas.toolbar.newBranch'), t('canvas.toolbar.newChild'))) {
      notify.success(t('canvas.toolbar.branchAdded'))
    }
  }

  function handleAddChild(): void {
    const diagramType = diagramStore.type
    if (!diagramStore.data?.nodes) {
      notify.warning(t('canvas.toolbar.createDiagramFirst'))
      return
    }

    if (diagramType === 'flow_map') {
      const selectedId = diagramStore.selectedNodes[0]
      const selectedNode = selectedId
        ? diagramStore.data.nodes.find((n) => n.id === selectedId)
        : undefined

      let stepNode: DiagramNode | undefined
      if (selectedNode?.type === 'flow') {
        stepNode = selectedNode
      } else if (selectedNode?.type === 'flowSubstep') {
        const match = selectedNode.id?.match(/^flow-substep-(\d+)-/)
        const stepIndex = match ? parseInt(match[1], 10) : -1
        stepNode =
          stepIndex >= 0
            ? diagramStore.data.nodes.find((n) => n.id === `flow-step-${stepIndex}`)
            : undefined
      }

      if (!stepNode?.text) {
        notify.warning(t('canvas.toolbar.selectStepForSubstep'))
        return
      }
      if (diagramStore.addFlowMapSubstep(stepNode.text, t('canvas.toolbar.newSubstep'))) {
        diagramStore.pushHistory(t('canvas.toolbar.addSubstepHistory'))
        notify.success(t('canvas.toolbar.substepAdded'))
      }
      return
    }

    if (diagramType === 'brace_map') {
      const selectedId = diagramStore.selectedNodes[0]
      if (!selectedId) {
        notify.warning(t('canvas.toolbar.selectPartForSubpart'))
        return
      }
      const targetIds = new Set(diagramStore.data.connections?.map((c) => c.target) ?? [])
      const rootId =
        diagramStore.data.nodes.find((n) => n.type === 'topic')?.id ??
        diagramStore.data.nodes.find((n) => !targetIds.has(n.id))?.id
      if (selectedId === rootId || selectedId === 'dimension-label') {
        notify.warning(t('canvas.toolbar.selectPartThenEnter'))
        return
      }
      if (diagramStore.addBraceMapPart(selectedId, t('canvas.toolbar.newSubpart'))) {
        notify.success(t('canvas.toolbar.subpartAdded'))
      }
      return
    }

    if (diagramType !== 'mindmap' && diagramType !== 'mind_map') return

    const selectedId = diagramStore.selectedNodes[0]
    if (!selectedId || selectedId === 'topic') {
      notify.warning(t('canvas.toolbar.selectBranchOrChild'))
      return
    }
    if (diagramStore.addMindMapChild(selectedId, t('canvas.toolbar.newChild'))) {
      notify.success(t('canvas.toolbar.childAdded'))
    } else {
      notify.warning(t('canvas.toolbar.cannotAddChild'))
    }
  }

  // ---- Main add handler ----

  function handleAddNode(): void {
    const diagramType = diagramStore.type
    if (!diagramStore.data?.nodes) {
      notify.warning(t('canvas.toolbar.createDiagramFirst'))
      return
    }

    if (diagramType === 'bubble_map') {
      const bubbleNodes = diagramStore.data.nodes.filter(
        (n) => (n.type === 'bubble' || n.type === 'child') && n.id.startsWith('bubble-'),
      )
      diagramStore.addNode({
        id: `bubble-${bubbleNodes.length}`,
        text: t('canvas.toolbar.newAttribute'),
        type: 'bubble',
        position: { x: 0, y: 0 },
      })
      diagramStore.pushHistory(t('canvas.toolbar.addAttributeHistory'))
      notify.success(t('canvas.toolbar.attributeAdded'))
      return
    }

    if (diagramType === 'circle_map') {
      const contextNodes = diagramStore.data.nodes.filter(
        (n) => n.type === 'bubble' && n.id.startsWith('context-'),
      )
      diagramStore.addNode({
        id: `context-${contextNodes.length}`,
        text: t('canvas.toolbar.newAssociation'),
        type: 'bubble',
        position: { x: 0, y: 0 },
      })
      diagramStore.pushHistory(t('canvas.toolbar.addNodeHistory'))
      notify.success(t('canvas.toolbar.nodeAddedCircle'))
      return
    }

    if (diagramType === 'bridge_map') {
      const pairNodes = diagramStore.data.nodes.filter(
        (n) =>
          n.data?.diagramType === 'bridge_map' &&
          n.data?.pairIndex !== undefined &&
          !n.data?.isDimensionLabel,
      )
      let maxPairIndex = -1
      pairNodes.forEach((node) => {
        const pi = node.data?.pairIndex
        if (typeof pi === 'number' && pi > maxPairIndex) maxPairIndex = pi
      })
      const newPairIndex = maxPairIndex + 1

      const centerY = DEFAULT_CENTER_Y
      const verticalGap = 5
      const nodeWidth = DEFAULT_NODE_WIDTH
      const nodeHeight = BRANCH_NODE_HEIGHT
      const startX = DEFAULT_PADDING + 100 + 10

      let nextX = startX
      if (pairNodes.length > 0) {
        const rightmostX = pairNodes.reduce(
          (mx, n) => Math.max(mx, n.position?.x || 0), 0,
        )
        nextX = rightmostX + nodeWidth + 50
      }

      diagramStore.addNode({
        id: `pair-${newPairIndex}-left`,
        text: t('canvas.toolbar.newItemA'),
        type: 'branch',
        position: { x: nextX, y: centerY - verticalGap - nodeHeight },
        data: { pairIndex: newPairIndex, position: 'left', diagramType: 'bridge_map' },
      })
      diagramStore.addNode({
        id: `pair-${newPairIndex}-right`,
        text: t('canvas.toolbar.newItemB'),
        type: 'branch',
        position: { x: nextX, y: centerY + verticalGap },
        data: { pairIndex: newPairIndex, position: 'right', diagramType: 'bridge_map' },
      })
      diagramStore.pushHistory(t('canvas.toolbar.addAnalogyPairHistory'))
      notify.success(t('canvas.toolbar.analogyPairAdded'))
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
      const selectedId = diagramStore.selectedNodes[0]
      if (!selectedId || selectedId === 'dimension-label') {
        handleAddBranch()
      } else {
        handleAddChild()
      }
      return
    }

    if (diagramType === 'tree_map') {
      const selectedId = diagramStore.selectedNodes[0]
      if (!selectedId || selectedId === 'tree-topic') {
        if (diagramStore.addTreeMapCategory(t('canvas.toolbar.newBranch'))) {
          diagramStore.pushHistory(t('canvas.toolbar.addNodeHistory'))
          notify.success(t('canvas.toolbar.branchAdded'))
        }
      } else {
        const catId = selectedId.startsWith('tree-cat-')
          ? selectedId
          : selectedId.replace(/^tree-leaf-(\d+)-\d+$/, 'tree-cat-$1')
        if (diagramStore.addTreeMapChild(catId, t('canvas.toolbar.newChild'))) {
          diagramStore.pushHistory(t('canvas.toolbar.addNodeHistory'))
          notify.success(t('canvas.toolbar.childAdded'))
        }
      }
      return
    }

    if (diagramType === 'flow_map') {
      const selectedId = diagramStore.selectedNodes[0]
      const selectedNode = selectedId
        ? diagramStore.data.nodes.find((n) => n.id === selectedId)
        : undefined

      if (selectedNode?.type === 'flowSubstep') {
        // Substep selected → add another substep to the same parent step
        const match = selectedNode.id?.match(/^flow-substep-(\d+)-/)
        const stepIndex = match ? parseInt(match[1], 10) : -1
        const stepNode =
          stepIndex >= 0
            ? diagramStore.data.nodes.find((n) => n.id === `flow-step-${stepIndex}`)
            : undefined
        if (stepNode?.text && diagramStore.addFlowMapSubstep(stepNode.text, t('canvas.toolbar.newSubstep'))) {
          diagramStore.pushHistory(t('canvas.toolbar.addSubstepHistory'))
          notify.success(t('canvas.toolbar.substepAdded'))
        }
      } else {
        // Step selected or nothing selected → add a step
        const stepCount = diagramStore.data.nodes.filter((n) => n.type === 'flow').length
        const stepNum = stepCount + 1
        const subs: [string, string] = [
          t('canvas.toolbar.substepDefault1', { n: stepNum }),
          t('canvas.toolbar.substepDefault2', { n: stepNum }),
        ]
        if (diagramStore.addFlowMapStep(t('canvas.toolbar.newStep'), subs)) {
          diagramStore.pushHistory(t('canvas.toolbar.addStepHistory'))
          notify.success(t('canvas.toolbar.stepAdded'))
        }
      }
      return
    }

    if (diagramType === 'double_bubble_map') {
      const selectedId = diagramStore.selectedNodes[0]
      const group = getDoubleBubbleGroup(selectedId)
      if (!group) {
        notify.warning(t('canvas.toolbar.selectSimilarityOrDifferenceFirst'))
        return
      }
      const spec = diagramStore.getDoubleBubbleSpecFromData()
      if (!spec) return
      const similarities = (spec.similarities as string[]) || []
      const leftDifferences = (spec.leftDifferences as string[]) || []
      const rightDifferences = (spec.rightDifferences as string[]) || []
      const simIndex = similarities.length + 1
      const pairIndex = Math.max(leftDifferences.length, rightDifferences.length) + 1
      const text = group === 'similarity'
        ? t('canvas.toolbar.similarityWithIndex', { n: simIndex })
        : t('canvas.toolbar.differenceAWithIndex', { n: pairIndex })
      const pairText = group === 'similarity'
        ? undefined
        : t('canvas.toolbar.differenceBWithIndex', { n: pairIndex })
      if (diagramStore.addDoubleBubbleMapNode(group, text, pairText)) {
        diagramStore.pushHistory(t('canvas.toolbar.addNodeHistory'))
        notify.success(
          group === 'similarity'
            ? t('canvas.toolbar.nodeAddedGeneric')
            : t('canvas.toolbar.differencePairAdded'),
        )
      }
      return
    }

    if (diagramType === 'multi_flow_map') {
      const selectedId = diagramStore.selectedNodes[0]
      const isCause = selectedId?.startsWith('cause-')
      const isEffect = selectedId?.startsWith('effect-')
      const category = isCause ? 'causes' : isEffect ? 'effects' : 'causes'
      const label = category === 'causes'
        ? t('canvas.toolbar.newCause')
        : t('canvas.toolbar.newEffect')
      diagramStore.addNode({
        id: `${category === 'causes' ? 'cause' : 'effect'}-temp`,
        text: label,
        type: 'flow',
        position: { x: 0, y: 0 },
        category,
      } as DiagramNode & { category?: string })
      diagramStore.pushHistory(
        category === 'causes'
          ? t('canvas.toolbar.addCauseHistory')
          : t('canvas.toolbar.addEffectHistory'),
      )
      notify.success(
        category === 'causes'
          ? t('canvas.toolbar.causeAdded')
          : t('canvas.toolbar.effectAdded'),
      )
      return
    }

    notify.info(t('canvas.toolbar.addNodeInDevelopment'))
  }

  // ---- Bridge-map reposition helper ----

  function repositionBridgeMapPairs(): void {
    if (!diagramStore.data) return

    const pairs = new Map<number, { left: DiagramNode | null; right: DiagramNode | null }>()
    for (const node of diagramStore.data.nodes) {
      if (
        node.data?.diagramType !== 'bridge_map' ||
        node.data?.pairIndex === undefined ||
        node.data?.isDimensionLabel
      ) continue
      const pi = node.data.pairIndex as number
      const pos = node.data.position as 'left' | 'right'
      if (!pairs.has(pi)) pairs.set(pi, { left: null, right: null })
      const pair = pairs.get(pi)!
      if (pos === 'left') pair.left = node
      else pair.right = node
    }

    const sorted = Array.from(pairs.entries())
      .filter(([, p]) => p.left && p.right)
      .sort(([a], [b]) => a - b)

    const startX = DEFAULT_PADDING + 100 + 10
    const nodeWidth = DEFAULT_NODE_WIDTH
    const nodeHeight = BRANCH_NODE_HEIGHT
    const centerY = DEFAULT_CENTER_Y
    const verticalGap = 5
    const gapBetweenPairs = 50

    let currentX = startX
    for (const [, pair] of sorted) {
      if (!pair.left || !pair.right) continue
      diagramStore.updateNodePosition(pair.left.id, { x: currentX, y: centerY - verticalGap - nodeHeight }, false)
      diagramStore.updateNodePosition(pair.right.id, { x: currentX, y: centerY + verticalGap }, false)
      currentX += nodeWidth + gapBetweenPairs
    }
  }

  // ---- Main delete handler ----

  async function handleDeleteNode(): Promise<void> {
    const diagramType = diagramStore.type
    if (!diagramStore.data?.nodes) {
      notify.warning(t('canvas.toolbar.createDiagramFirst'))
      return
    }

    const selectedNodesArray = [...diagramStore.selectedNodes]
    if (selectedNodesArray.length === 0) {
      notify.warning(t('canvas.toolbar.selectNodesToDelete'))
      return
    }

    if (diagramType === 'bubble_map') {
      const deleted = diagramStore.removeBubbleMapNodes(selectedNodesArray)
      if (deleted > 0) {
        diagramStore.clearSelection()
        diagramStore.pushHistory(t('canvas.toolbar.deleteAttributeHistory'))
        notify.success(t('canvas.toolbar.deletedAttributes', { count: deleted }))
      } else {
        notify.warning(t('canvas.toolbar.cannotDeleteTopic'))
      }
      return
    }

    if (diagramType === 'circle_map') {
      let deleted = 0
      for (const nodeId of selectedNodesArray) {
        if (nodeId.startsWith('context-') && diagramStore.removeNode(nodeId)) deleted++
      }
      if (deleted > 0) {
        const remaining = diagramStore.data.nodes.filter(
          (n) => n.type === 'bubble' && n.id.startsWith('context-'),
        )
        remaining.forEach((node, i) => { node.id = `context-${i}` })
        diagramStore.clearSelection()
        diagramStore.pushHistory(t('canvas.toolbar.deleteNodesHistory'))
        notify.success(t('canvas.toolbar.deletedNodes', { count: deleted }))
      } else {
        notify.warning(t('canvas.toolbar.cannotDeleteTopic'))
      }
      return
    }

    if (diagramType === 'brace_map') {
      const deleted = diagramStore.removeBraceMapNodes(selectedNodesArray)
      if (deleted > 0) {
        diagramStore.clearSelection()
        diagramStore.pushHistory(t('canvas.toolbar.deleteNodesHistory'))
        notify.success(t('canvas.toolbar.deletedNodes', { count: deleted }))
      } else {
        notify.warning(t('canvas.toolbar.cannotDeleteTopic'))
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
        notify.success(t('canvas.toolbar.deletedNodes', { count: deleted }))
      } else {
        notify.warning(t('canvas.toolbar.cannotDeleteEvent'))
      }
      return
    }

    if (diagramType === 'mindmap' || diagramType === 'mind_map') {
      const deleted = diagramStore.removeMindMapNodes(selectedNodesArray)
      if (deleted > 0) {
        diagramStore.clearSelection()
        diagramStore.pushHistory(t('canvas.toolbar.deleteNodesHistory'))
        notify.success(t('canvas.toolbar.deletedNodes', { count: deleted }))
      } else {
        notify.warning(t('canvas.toolbar.cannotDeleteTopic'))
      }
      return
    }

    if (diagramType === 'double_bubble_map') {
      const toDelete = selectedNodesArray.filter(
        (id) =>
          /^similarity-\d+$/.test(id) ||
          /^left-diff-\d+$/.test(id) ||
          /^right-diff-\d+$/.test(id),
      )
      if (toDelete.length === 0) {
        notify.warning(t('canvas.toolbar.selectSimilarityOrDifferenceDelete'))
        return
      }
      const deleted = diagramStore.removeDoubleBubbleMapNodes(toDelete)
      if (deleted > 0) {
        diagramStore.clearSelection()
        diagramStore.pushHistory(t('canvas.toolbar.deleteNodesHistory'))
        notify.success(t('canvas.toolbar.deletedNodes', { count: deleted }))
      }
      return
    }

    if (diagramType === 'tree_map') {
      const toDelete = selectedNodesArray.filter(
        (id) => /^tree-cat-\d+$/.test(id) || /^tree-leaf-\d+-\d+$/.test(id),
      )
      if (toDelete.length === 0) {
        notify.warning(t('canvas.toolbar.selectCategoryOrLeafDelete'))
        return
      }
      const deleted = diagramStore.removeTreeMapNodes(toDelete)
      if (deleted > 0) {
        diagramStore.clearSelection()
        diagramStore.pushHistory(t('canvas.toolbar.deleteNodesHistory'))
        notify.success(t('canvas.toolbar.deletedNodes', { count: deleted }))
      } else {
        notify.warning(t('canvas.toolbar.cannotDeleteTopicGeneric'))
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
        if (diagramStore.removeNode(`pair-${pi}-left`)) deleted++
        if (diagramStore.removeNode(`pair-${pi}-right`)) deleted++
      }
      if (deleted > 0) {
        await nextTick()
        repositionBridgeMapPairs()
        diagramStore.clearSelection()
        diagramStore.pushHistory(t('canvas.toolbar.deleteAnalogyPairHistory'))
        notify.success(t('canvas.toolbar.deletedAnalogyPairs', { count: pairIndicesToDelete.size }))
      } else {
        notify.warning(t('canvas.toolbar.cannotDeleteDimension'))
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
        notify.success(t('canvas.toolbar.deletedNodes', { count: deleted }))
      } else {
        notify.warning(t('canvas.toolbar.cannotDeleteSelected'))
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
      notify.success(t('canvas.toolbar.deletedNodes', { count: deleted }))
    } else {
      notify.warning(t('canvas.toolbar.cannotDeleteSelected'))
    }
  }

  // ---- Lifecycle: auto-register event listeners ----

  onMounted(() => {
    eventBus.on('diagram:add_node_requested', handleAddNode)
    eventBus.on('diagram:delete_selected_requested', handleDeleteNode)
    eventBus.on('diagram:add_branch_requested', handleAddBranch)
    eventBus.on('diagram:add_child_requested', handleAddChild)
  })

  onUnmounted(() => {
    eventBus.off('diagram:add_node_requested', handleAddNode)
    eventBus.off('diagram:delete_selected_requested', handleDeleteNode)
    eventBus.off('diagram:add_branch_requested', handleAddBranch)
    eventBus.off('diagram:add_child_requested', handleAddChild)
  })

  return { handleAddNode, handleDeleteNode, handleAddBranch, handleAddChild }
}
