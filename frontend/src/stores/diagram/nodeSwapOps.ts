import { eventBus } from '@/composables/useEventBus'
import { getMindmapBranchColor } from '@/config/mindmapColors'
import type { Connection } from '@/types'

import { recalculateBraceMapLayout, recalculateBubbleMapLayout } from '../specLoader'
import { emitEvent } from './events'
import type { DiagramContext } from './types'

export function useNodeSwapOpsSlice(ctx: DiagramContext) {
  function parseDiffIndex(nodeId: string): number {
    const match = nodeId.match(/^(?:left|right)-diff-(\d+)$/)
    return match ? parseInt(match[1], 10) : -1
  }

  function getNodeGroupIds(nodeId: string): Set<string> {
    const result = new Set<string>([nodeId])
    const dt = ctx.type.value
    if (!dt || !ctx.data.value) return result

    if (dt === 'bridge_map') {
      const pairMatch = nodeId.match(/^pair-(\d+)-(left|right)$/)
      if (pairMatch) {
        const idx = pairMatch[1]
        result.add(`pair-${idx}-left`)
        result.add(`pair-${idx}-right`)
      }
    } else if (dt === 'double_bubble_map') {
      const leftMatch = nodeId.match(/^left-diff-(\d+)$/)
      const rightMatch = nodeId.match(/^right-diff-(\d+)$/)
      if (leftMatch) result.add(`right-diff-${leftMatch[1]}`)
      else if (rightMatch) result.add(`left-diff-${rightMatch[1]}`)
    } else if (dt === 'flow_map') {
      const stepMatch = nodeId.match(/^flow-step-(\d+)$/)
      if (stepMatch) {
        const stepIdx = stepMatch[1]
        ctx.data.value.nodes
          .filter((n) => n.id.startsWith(`flow-substep-${stepIdx}-`))
          .forEach((n) => result.add(n.id))
      }
    } else if (dt === 'brace_map' && ctx.data.value.connections) {
      const childrenMap = new Map<string, string[]>()
      ctx.data.value.connections.forEach((c) => {
        if (!childrenMap.has(c.source)) childrenMap.set(c.source, [])
        const srcList = childrenMap.get(c.source)
        if (srcList) srcList.push(c.target)
      })
      const collectChildren = (id: string): void => {
        for (const childId of childrenMap.get(id) ?? []) {
          result.add(childId)
          collectChildren(childId)
        }
      }
      collectChildren(nodeId)
    } else if (dt === 'mindmap' || dt === 'mind_map') {
      return ctx.getMindMapDescendantIds(nodeId)
    } else if (dt === 'tree_map') {
      return ctx.getTreeMapDescendantIds(nodeId)
    }

    return result
  }

  function swapBubbleMapNodes(sourceId: string, targetId: string): boolean {
    if (!ctx.data.value?.nodes) return false
    const srcIdx = parseInt(sourceId.replace('bubble-', ''), 10)
    const tgtIdx = parseInt(targetId.replace('bubble-', ''), 10)
    const bubbles = ctx.data.value.nodes
      .filter((n) => n.id.startsWith('bubble-'))
      .sort(
        (a, b) =>
          parseInt(a.id.replace('bubble-', ''), 10) - parseInt(b.id.replace('bubble-', ''), 10)
      )
    if (srcIdx < 0 || srcIdx >= bubbles.length || tgtIdx < 0 || tgtIdx >= bubbles.length)
      return false
    const srcText = bubbles[srcIdx].text
    bubbles[srcIdx].text = bubbles[tgtIdx].text
    bubbles[tgtIdx].text = srcText
    const recalculatedNodes = recalculateBubbleMapLayout(
      ctx.data.value.nodes,
      ctx.nodeDimensions.value
    )
    const recalcBubbles = recalculatedNodes.filter(
      (n) => (n.type === 'bubble' || n.type === 'child') && n.id.startsWith('bubble-')
    )
    ctx.data.value.nodes = recalculatedNodes
    ctx.data.value.connections = recalcBubbles.map((_, i) => ({
      id: `edge-topic-bubble-${i}`,
      source: 'topic',
      target: `bubble-${i}`,
      style: { strokeColor: getMindmapBranchColor(i).border },
    }))
    return true
  }

  function swapCircleMapNodes(sourceId: string, targetId: string): boolean {
    if (!ctx.data.value?.nodes) return false
    const srcIdx = parseInt(sourceId.replace('context-', ''), 10)
    const tgtIdx = parseInt(targetId.replace('context-', ''), 10)
    const contexts = ctx.data.value.nodes
      .filter((n) => n.id.startsWith('context-'))
      .sort(
        (a, b) =>
          parseInt(a.id.replace('context-', ''), 10) - parseInt(b.id.replace('context-', ''), 10)
      )
    if (srcIdx < 0 || srcIdx >= contexts.length || tgtIdx < 0 || tgtIdx >= contexts.length)
      return false
    const topic = ctx.data.value.nodes.find((n) => n.id === 'topic')?.text ?? ''
    const contextTexts = contexts.map((n) => n.text)
    const tmp = contextTexts[srcIdx]
    contextTexts[srcIdx] = contextTexts[tgtIdx]
    contextTexts[tgtIdx] = tmp
    return ctx.loadFromSpec({ topic, context: contextTexts }, 'circle_map')
  }

  function swapDoubleBubbleMapNodes(sourceId: string, targetId: string): boolean {
    const spec = ctx.getDoubleBubbleSpecFromData()
    if (!spec) return false

    const similarities = spec.similarities as string[]
    const leftDiffs = spec.leftDifferences as string[]
    const rightDiffs = spec.rightDifferences as string[]

    const srcSimMatch = sourceId.match(/^similarity-(\d+)$/)
    const tgtSimMatch = targetId.match(/^similarity-(\d+)$/)

    if (srcSimMatch && tgtSimMatch) {
      const si = parseInt(srcSimMatch[1], 10)
      const ti = parseInt(tgtSimMatch[1], 10)
      if (si >= 0 && si < similarities.length && ti >= 0 && ti < similarities.length) {
        const tmp = similarities[si]
        similarities[si] = similarities[ti]
        similarities[ti] = tmp
        return ctx.loadFromSpec(spec, 'double_bubble_map')
      }
      return false
    }

    const srcDiffIdx = parseDiffIndex(sourceId)
    const tgtDiffIdx = parseDiffIndex(targetId)
    if (
      srcDiffIdx >= 0 &&
      tgtDiffIdx >= 0 &&
      srcDiffIdx < leftDiffs.length &&
      tgtDiffIdx < leftDiffs.length &&
      srcDiffIdx < rightDiffs.length &&
      tgtDiffIdx < rightDiffs.length
    ) {
      const tmpL = leftDiffs[srcDiffIdx]
      leftDiffs[srcDiffIdx] = leftDiffs[tgtDiffIdx]
      leftDiffs[tgtDiffIdx] = tmpL
      const tmpR = rightDiffs[srcDiffIdx]
      rightDiffs[srcDiffIdx] = rightDiffs[tgtDiffIdx]
      rightDiffs[tgtDiffIdx] = tmpR
      return ctx.loadFromSpec(spec, 'double_bubble_map')
    }
    return false
  }

  function swapFlowMapNodes(sourceId: string, targetId: string): boolean {
    const spec = ctx.buildFlowMapSpecFromNodes()
    if (!spec) return false
    const steps = spec.steps as string[]
    const substepsList = spec.substeps as Array<{ step: string; substeps: string[] }>

    const srcStepMatch = sourceId.match(/^flow-step-(\d+)$/)
    const tgtStepMatch = targetId.match(/^flow-step-(\d+)$/)
    if (srcStepMatch && tgtStepMatch) {
      const si = parseInt(srcStepMatch[1], 10)
      const ti = parseInt(tgtStepMatch[1], 10)
      if (si >= 0 && si < steps.length && ti >= 0 && ti < steps.length) {
        const srcText = steps[si]
        const tgtText = steps[ti]
        const srcSubs = substepsList.find((e) => e.step === srcText)
        const tgtSubs = substepsList.find((e) => e.step === tgtText)
        steps[si] = tgtText
        steps[ti] = srcText
        if (srcSubs) srcSubs.step = srcText
        if (tgtSubs) tgtSubs.step = tgtText
        return ctx.loadFromSpec(spec, 'flow_map')
      }
      return false
    }

    const srcSubMatch = sourceId.match(/^flow-substep-(\d+)-(\d+)$/)
    const tgtSubMatch = targetId.match(/^flow-substep-(\d+)-(\d+)$/)
    if (srcSubMatch && tgtSubMatch) {
      const srcStep = parseInt(srcSubMatch[1], 10)
      const srcSub = parseInt(srcSubMatch[2], 10)
      const tgtStep = parseInt(tgtSubMatch[1], 10)
      const tgtSub = parseInt(tgtSubMatch[2], 10)
      if (srcStep < steps.length && tgtStep < steps.length) {
        const srcStepText = steps[srcStep]
        const tgtStepText = steps[tgtStep]
        const srcEntry = substepsList.find((e) => e.step === srcStepText)
        const tgtEntry = substepsList.find((e) => e.step === tgtStepText)
        if (
          srcEntry &&
          tgtEntry &&
          srcSub < srcEntry.substeps.length &&
          tgtSub < tgtEntry.substeps.length
        ) {
          const tmp = srcEntry.substeps[srcSub]
          srcEntry.substeps[srcSub] = tgtEntry.substeps[tgtSub]
          tgtEntry.substeps[tgtSub] = tmp
          return ctx.loadFromSpec(spec, 'flow_map')
        }
      }
      return false
    }
    return false
  }

  function moveFlowMapNode(sourceId: string, targetId: string): boolean {
    const spec = ctx.buildFlowMapSpecFromNodes()
    if (!spec) return false
    const steps = spec.steps as string[]
    const substepsList = spec.substeps as Array<{ step: string; substeps: string[] }>

    const srcSubMatch = sourceId.match(/^flow-substep-(\d+)-(\d+)$/)
    const tgtStepMatch = targetId.match(/^flow-step-(\d+)$/)

    let success = false

    if (srcSubMatch && tgtStepMatch) {
      const srcStepIdx = parseInt(srcSubMatch[1], 10)
      const srcSubIdx = parseInt(srcSubMatch[2], 10)
      const tgtStepIdx = parseInt(tgtStepMatch[1], 10)

      if (srcStepIdx === tgtStepIdx) return false
      if (srcStepIdx >= steps.length || tgtStepIdx >= steps.length) return false

      const srcStepText = steps[srcStepIdx]
      const tgtStepText = steps[tgtStepIdx]
      const srcEntry = substepsList.find((e) => e.step === srcStepText)
      if (!srcEntry || srcSubIdx >= srcEntry.substeps.length) return false

      const [movedText] = srcEntry.substeps.splice(srcSubIdx, 1)

      const tgtEntry = substepsList.find((e) => e.step === tgtStepText)
      if (tgtEntry) {
        tgtEntry.substeps.push(movedText)
      } else {
        substepsList.push({ step: tgtStepText, substeps: [movedText] })
      }

      success = ctx.loadFromSpec(spec, 'flow_map')
    } else {
      success = swapFlowMapNodes(sourceId, targetId)
    }

    if (success) {
      if (ctx.data.value?._customPositions) ctx.data.value._customPositions = {}
      if (ctx.data.value?._node_styles) ctx.data.value._node_styles = {}
      ctx.selectedNodes.value = []
      ctx.pushHistory('Move node')
      emitEvent('diagram:operation_completed', { operation: 'move_branch' })
      eventBus.emit('diagram:branch_moved', {})
    }
    return success
  }

  function swapMultiFlowMapNodes(sourceId: string, targetId: string): boolean {
    if (!ctx.data.value?.nodes) return false
    const causeNodes = ctx.data.value.nodes
      .filter((n) => n.id.startsWith('cause-'))
      .sort(
        (a, b) =>
          parseInt(a.id.replace('cause-', ''), 10) - parseInt(b.id.replace('cause-', ''), 10)
      )
    const effectNodes = ctx.data.value.nodes
      .filter((n) => n.id.startsWith('effect-'))
      .sort(
        (a, b) =>
          parseInt(a.id.replace('effect-', ''), 10) - parseInt(b.id.replace('effect-', ''), 10)
      )
    const eventNode = ctx.data.value.nodes.find((n) => n.id === 'event')

    const causes = causeNodes.map((n) => n.text)
    const effects = effectNodes.map((n) => n.text)

    const srcCause = sourceId.match(/^cause-(\d+)$/)
    const tgtCause = targetId.match(/^cause-(\d+)$/)
    if (srcCause && tgtCause) {
      const si = parseInt(srcCause[1], 10)
      const ti = parseInt(tgtCause[1], 10)
      if (si >= 0 && si < causes.length && ti >= 0 && ti < causes.length) {
        const tmp = causes[si]
        causes[si] = causes[ti]
        causes[ti] = tmp
        return ctx.loadFromSpec({ event: eventNode?.text ?? '', causes, effects }, 'multi_flow_map')
      }
      return false
    }

    const srcEffect = sourceId.match(/^effect-(\d+)$/)
    const tgtEffect = targetId.match(/^effect-(\d+)$/)
    if (srcEffect && tgtEffect) {
      const si = parseInt(srcEffect[1], 10)
      const ti = parseInt(tgtEffect[1], 10)
      if (si >= 0 && si < effects.length && ti >= 0 && ti < effects.length) {
        const tmp = effects[si]
        effects[si] = effects[ti]
        effects[ti] = tmp
        return ctx.loadFromSpec({ event: eventNode?.text ?? '', causes, effects }, 'multi_flow_map')
      }
      return false
    }
    return false
  }

  function swapBraceMapNodes(sourceId: string, targetId: string): boolean {
    if (!ctx.data.value?.nodes || !ctx.data.value?.connections) return false

    const targetIdSet = new Set(ctx.data.value.connections.map((c) => c.target))
    const rootId =
      ctx.data.value.nodes.find((n) => n.type === 'topic')?.id ??
      ctx.data.value.nodes.find((n) => !targetIdSet.has(n.id) && n.type !== 'label')?.id
    if (!rootId) return false

    const childrenMap = new Map<string, string[]>()
    ctx.data.value.connections.forEach((c) => {
      if (!childrenMap.has(c.source)) childrenMap.set(c.source, [])
      const srcList = childrenMap.get(c.source)
      if (srcList) srcList.push(c.target)
    })

    const srcParentConn = ctx.data.value.connections.find((c) => c.target === sourceId)
    const tgtParentConn = ctx.data.value.connections.find((c) => c.target === targetId)
    if (!srcParentConn || !tgtParentConn) return false

    const srcParent = srcParentConn.source
    const tgtParent = tgtParentConn.source
    const srcSiblings = childrenMap.get(srcParent) ?? []
    const tgtSiblings = childrenMap.get(tgtParent) ?? []
    const srcIdx = srcSiblings.indexOf(sourceId)
    const tgtIdx = tgtSiblings.indexOf(targetId)
    if (srcIdx < 0 || tgtIdx < 0) return false

    if (srcParent === tgtParent) {
      srcSiblings[srcIdx] = targetId
      srcSiblings[tgtIdx] = sourceId
    } else {
      srcSiblings[srcIdx] = targetId
      tgtSiblings[tgtIdx] = sourceId
    }

    const newConnections = ctx.data.value.connections.map((c: Connection) => {
      if (c.source === srcParent && c.target === sourceId) return { ...c, target: targetId }
      if (c.source === tgtParent && c.target === targetId) return { ...c, target: sourceId }
      if (c.source === sourceId) return { ...c, source: targetId }
      if (c.source === targetId) return { ...c, source: sourceId }
      if (c.target === sourceId) return { ...c, target: targetId }
      if (c.target === targetId) return { ...c, target: sourceId }
      return c
    })

    ctx.data.value.connections = newConnections

    const layoutNodes = recalculateBraceMapLayout(
      ctx.data.value.nodes,
      newConnections,
      ctx.nodeDimensions.value
    )
    ctx.data.value.nodes = layoutNodes
    return true
  }

  function moveBraceMapNode(sourceId: string, targetId: string): boolean {
    if (!ctx.data.value?.nodes || !ctx.data.value?.connections) return false

    const parentMap = new Map<string, string>()
    ctx.data.value.connections.forEach((c) => {
      parentMap.set(c.target, c.source)
    })

    function getDepth(nodeId: string): number {
      let depth = 0
      let current = nodeId
      while (parentMap.has(current)) {
        depth++
        const next = parentMap.get(current)
        if (next === undefined) break
        current = next
      }
      return depth
    }

    const srcDepth = getDepth(sourceId)
    const tgtDepth = getDepth(targetId)

    if (parentMap.get(sourceId) === targetId) return false

    let success = false

    if (srcDepth > tgtDepth) {
      const descendantIds = getNodeGroupIds(sourceId)
      if (descendantIds.has(targetId)) return false

      const oldParent = parentMap.get(sourceId)
      if (!oldParent) return false

      ctx.data.value.connections = ctx.data.value.connections.filter(
        (c) => !(c.source === oldParent && c.target === sourceId)
      )
      ctx.data.value.connections.push({
        id: `edge-${targetId}-${sourceId}`,
        source: targetId,
        target: sourceId,
      })

      const layoutNodes = recalculateBraceMapLayout(
        ctx.data.value.nodes,
        ctx.data.value.connections,
        ctx.nodeDimensions.value
      )
      ctx.data.value.nodes = layoutNodes
      success = true
    } else {
      success = swapBraceMapNodes(sourceId, targetId)
    }

    if (success) {
      if (ctx.data.value?._customPositions) ctx.data.value._customPositions = {}
      if (ctx.data.value?._node_styles) ctx.data.value._node_styles = {}
      ctx.selectedNodes.value = []
      ctx.pushHistory('Move node')
      emitEvent('diagram:operation_completed', { operation: 'move_branch' })
      eventBus.emit('diagram:branch_moved', {})
    }
    return success
  }

  function swapBridgeMapPairs(sourceId: string, targetId: string): boolean {
    if (!ctx.data.value?.nodes) return false
    const srcMatch = sourceId.match(/^pair-(\d+)-(left|right)$/)
    const tgtMatch = targetId.match(/^pair-(\d+)-(left|right)$/)
    if (!srcMatch || !tgtMatch) return false

    const srcPairIdx = parseInt(srcMatch[1], 10)
    const tgtPairIdx = parseInt(tgtMatch[1], 10)
    if (srcPairIdx === tgtPairIdx) return false

    const pairIndices = [
      ...new Set(
        ctx.data.value.nodes
          .filter((n) => n.id.startsWith('pair-'))
          .map((n) => parseInt(n.id.match(/^pair-(\d+)/)?.[1] ?? '-1', 10))
          .filter((i) => i >= 0)
      ),
    ].sort((a, b) => a - b)

    if (!pairIndices.includes(srcPairIdx) || !pairIndices.includes(tgtPairIdx)) return false

    const rawDimension = (ctx.data.value as Record<string, unknown>).dimension as string | undefined
    const rawFactor = (ctx.data.value as Record<string, unknown>).relating_factor as
      | string
      | undefined
    const dimension = rawDimension || rawFactor || ''
    const altDims = (ctx.data.value as Record<string, unknown>).alternative_dimensions as
      | string[]
      | undefined

    const bridgeNodes = ctx.data.value.nodes
    const analogies = pairIndices.map((i) => {
      const leftNode = bridgeNodes.find((n) => n.id === `pair-${i}-left`)
      const rightNode = bridgeNodes.find((n) => n.id === `pair-${i}-right`)
      return { left: leftNode?.text ?? '', right: rightNode?.text ?? '' }
    })

    const srcPos = pairIndices.indexOf(srcPairIdx)
    const tgtPos = pairIndices.indexOf(tgtPairIdx)
    const tmp = analogies[srcPos]
    analogies[srcPos] = analogies[tgtPos]
    analogies[tgtPos] = tmp

    const spec: Record<string, unknown> = {
      relating_factor: dimension,
      dimension,
      analogies,
    }
    if (altDims) spec.alternative_dimensions = altDims
    return ctx.loadFromSpec(spec, 'bridge_map')
  }

  function moveNodeBySwap(sourceId: string, targetId: string): boolean {
    const dt = ctx.type.value
    if (!dt || !ctx.data.value) return false

    let success = false
    switch (dt) {
      case 'bubble_map':
        success = swapBubbleMapNodes(sourceId, targetId)
        break
      case 'circle_map':
        success = swapCircleMapNodes(sourceId, targetId)
        break
      case 'double_bubble_map':
        success = swapDoubleBubbleMapNodes(sourceId, targetId)
        break
      case 'flow_map':
        return moveFlowMapNode(sourceId, targetId)
      case 'multi_flow_map':
        success = swapMultiFlowMapNodes(sourceId, targetId)
        break
      case 'brace_map':
        return moveBraceMapNode(sourceId, targetId)
      case 'bridge_map':
        success = swapBridgeMapPairs(sourceId, targetId)
        break
      default:
        return false
    }

    if (success) {
      if (ctx.data.value?._customPositions) ctx.data.value._customPositions = {}
      if (ctx.data.value?._node_styles) ctx.data.value._node_styles = {}
      ctx.selectedNodes.value = []
      ctx.pushHistory('Move node')
      emitEvent('diagram:operation_completed', { operation: 'move_branch' })
      eventBus.emit('diagram:branch_moved', {})
    }
    return success
  }

  return { getNodeGroupIds, moveNodeBySwap }
}
