import {
  DEFAULT_CENTER_X,
  DEFAULT_NODE_WIDTH,
  MULTI_FLOW_MAP_TOPIC_WIDTH,
} from '@/composables/diagrams/layoutConfig'
import { eventBus } from '@/composables/useEventBus'
import type { Connection, DiagramNode, DiagramType } from '@/types'
import { normalizeAllConceptMapTopicRootLabels } from '@/utils/conceptMapTopicRootEdge'

import { useConceptMapRelationshipStore } from '../conceptMapRelationship'
import { useUIStore } from '../ui'
import {
  getDefaultTemplate,
  loadSpecForDiagramType,
  normalizeMindMapHorizontalSymmetry,
  recalculateBubbleMapLayout,
} from '../specLoader'
import { getMindMapCurveExtents } from './events'
import type { DiagramContext, LoadFromSpecOptions } from './types'

export function useSpecIOSlice(ctx: DiagramContext) {
  function loadFromSpec(
    spec: Record<string, unknown>,
    diagramTypeValue: DiagramType,
    options?: LoadFromSpecOptions
  ): boolean {
    if (!spec || !diagramTypeValue) return false

    ctx.resetSessionEditCount()
    useConceptMapRelationshipStore().clearAll()

    if (!ctx.setDiagramType(diagramTypeValue)) return false

    const result = loadSpecForDiagramType(spec, diagramTypeValue)

    let nodesToStore = result.nodes
    if (diagramTypeValue === 'bubble_map' && result.nodes.length > 0) {
      nodesToStore = recalculateBubbleMapLayout(result.nodes)
    }

    if (
      (diagramTypeValue === 'mindmap' || diagramTypeValue === 'mind_map') &&
      nodesToStore.length > 0
    ) {
      const topicNode = nodesToStore.find(
        (n) => n.id === 'topic' && (n.type === 'topic' || n.type === 'center')
      )
      const centerX =
        topicNode?.position != null
          ? topicNode.position.x + DEFAULT_NODE_WIDTH / 2
          : DEFAULT_CENTER_X
      normalizeMindMapHorizontalSymmetry(nodesToStore, centerX)
      ctx.mindMapCurveExtentBaseline.value = getMindMapCurveExtents(nodesToStore, centerX)
      console.log('[BranchMove] baseline captured (load)', ctx.mindMapCurveExtentBaseline.value)
    } else {
      ctx.mindMapCurveExtentBaseline.value = null
    }

    if (diagramTypeValue === 'multi_flow_map') {
      ctx.topicNodeWidth.value = MULTI_FLOW_MAP_TOPIC_WIDTH
    }

    ctx.data.value = {
      type: diagramTypeValue,
      nodes: nodesToStore,
      connections: result.connections,
      ...Object.fromEntries(
        Object.entries(spec).filter(
          ([key]) =>
            ![
              'nodes',
              'connections',
              'topic',
              'context',
              'attributes',
              'root',
              'whole',
              'steps',
              'pairs',
              'concepts',
              'event',
              'causes',
              'effects',
              'left',
              'right',
              'similarities',
              'leftDifferences',
              'rightDifferences',
              'leftBranches',
              'rightBranches',
              'analogies',
            ].includes(key)
        )
      ),
      ...(result.metadata || {}),
    }

    if (diagramTypeValue === 'concept_map' && ctx.data.value?.connections && ctx.data.value.nodes) {
      normalizeAllConceptMapTopicRootLabels(ctx.data.value.connections, ctx.data.value.nodes)
    }

    if (options?.emitLoaded !== false) {
      eventBus.emit('diagram:loaded', { diagramType: diagramTypeValue })
    }
    return true
  }

  function getDoubleBubbleSpecFromData(): Record<string, unknown> | null {
    if (ctx.type.value !== 'double_bubble_map' || !ctx.data.value?.nodes?.length) return null
    const nodes = ctx.data.value.nodes
    let left = ''
    let right = ''
    const leftNode = nodes.find((n) => n.id === 'left-topic')
    const rightNode = nodes.find((n) => n.id === 'right-topic')
    if (leftNode) left = String(leftNode.text ?? '').trim()
    if (rightNode) right = String(rightNode.text ?? '').trim()
    const simIndices = [
      ...new Set(
        nodes
          .filter((n) => /^similarity-\d+$/.test(n.id))
          .map((n) => parseInt(n.id.replace('similarity-', ''), 10))
      ),
    ].sort((a, b) => a - b)
    const leftDiffIndices = [
      ...new Set(
        nodes
          .filter((n) => /^left-diff-\d+$/.test(n.id))
          .map((n) => parseInt(n.id.replace('left-diff-', ''), 10))
      ),
    ].sort((a, b) => a - b)
    const rightDiffIndices = [
      ...new Set(
        nodes
          .filter((n) => /^right-diff-\d+$/.test(n.id))
          .map((n) => parseInt(n.id.replace('right-diff-', ''), 10))
      ),
    ].sort((a, b) => a - b)
    const similarities = simIndices.map((i) =>
      String(nodes.find((n) => n.id === `similarity-${i}`)?.text ?? '').trim()
    )
    const leftDifferences = leftDiffIndices.map((i) =>
      String(nodes.find((n) => n.id === `left-diff-${i}`)?.text ?? '').trim()
    )
    const rightDifferences = rightDiffIndices.map((i) =>
      String(nodes.find((n) => n.id === `right-diff-${i}`)?.text ?? '').trim()
    )
    const getRadius = (n: { style?: { size?: number; width?: number; height?: number } }) => {
      const s = n.style?.size
      if (s != null && s > 0) return s / 2
      const w = n.style?.width
      const h = n.style?.height
      if (w != null && h != null) return Math.min(w, h) / 2
      return undefined
    }
    const _doubleBubbleMapNodeSizes: Record<string, unknown> = {}
    if (leftNode) {
      const r = getRadius(leftNode)
      if (r != null) _doubleBubbleMapNodeSizes['leftTopicR'] = r
    }
    if (rightNode) {
      const r = getRadius(rightNode)
      if (r != null) _doubleBubbleMapNodeSizes['rightTopicR'] = r
    }
    const simRadii = simIndices.map((i) => {
      const nd = nodes.find((n) => n.id === `similarity-${i}`)
      return nd != null ? getRadius(nd) : undefined
    })
    if (simRadii.some((r) => r != null)) _doubleBubbleMapNodeSizes['simRadii'] = simRadii
    const leftDiffRadii = leftDiffIndices.map((i) => {
      const nd = nodes.find((n) => n.id === `left-diff-${i}`)
      return nd != null ? getRadius(nd) : undefined
    })
    if (leftDiffRadii.some((r) => r != null))
      _doubleBubbleMapNodeSizes['leftDiffRadii'] = leftDiffRadii
    const rightDiffRadii = rightDiffIndices.map((i) => {
      const nd = nodes.find((n) => n.id === `right-diff-${i}`)
      return nd != null ? getRadius(nd) : undefined
    })
    if (rightDiffRadii.some((r) => r != null))
      _doubleBubbleMapNodeSizes['rightDiffRadii'] = rightDiffRadii

    return {
      left,
      right,
      similarities,
      leftDifferences,
      rightDifferences,
      ...(Object.keys(_doubleBubbleMapNodeSizes).length > 0 ? { _doubleBubbleMapNodeSizes } : {}),
    }
  }

  function getSpecForSave(): Record<string, unknown> | null {
    if (!ctx.data.value) return null
    let nodes = ctx.data.value.nodes
    if (ctx.type.value === 'bubble_map' && nodes.length > 0) {
      nodes = recalculateBubbleMapLayout(nodes)
    }
    const spec: Record<string, unknown> = {
      type: ctx.type.value,
      nodes,
      connections: ctx.data.value.connections,
      _customPositions: ctx.data.value._customPositions,
      _node_styles: ctx.data.value._node_styles,
    }
    if (ctx.type.value === 'flow_map') {
      const orientation = (ctx.data.value as Record<string, unknown>).orientation ?? 'horizontal'
      spec.orientation = orientation
    }
    const dataRecord = ctx.data.value as Record<string, unknown>
    if (ctx.type.value === 'bridge_map' || ctx.type.value === 'tree_map') {
      if (dataRecord.dimension !== undefined) spec.dimension = dataRecord.dimension
      if (dataRecord.relating_factor !== undefined)
        spec.relating_factor = dataRecord.relating_factor
      if (Array.isArray(dataRecord.alternative_dimensions))
        spec.alternative_dimensions = dataRecord.alternative_dimensions
      if (Array.isArray(dataRecord.alternativeDimensions))
        spec.alternative_dimensions = dataRecord.alternativeDimensions
    }
    const hiddenAnswers = (ctx.data.value as { hiddenAnswers?: string[] }).hiddenAnswers
    const d = ctx.data.value as {
      isLearningSheet?: boolean
      is_learning_sheet?: boolean
    }
    const isLS = d?.isLearningSheet === true || d?.is_learning_sheet === true
    if (isLS) spec.is_learning_sheet = true
    if (hiddenAnswers?.length) spec.hiddenAnswers = hiddenAnswers
    if (ctx.type.value === 'concept_map') {
      const fq = dataRecord.focus_question
      if (typeof fq === 'string' && fq.trim()) {
        spec.focus_question = fq.trim()
      }
    }
    return spec
  }

  function buildFlowMapSpecFromNodes(): Record<string, unknown> | null {
    if (!ctx.data.value || ctx.type.value !== 'flow_map') return null
    const topicNode = ctx.data.value.nodes.find((n) => n.id === 'flow-topic')
    const title = topicNode?.text ?? (ctx.data.value as Record<string, unknown>).title ?? ''
    const stepNodes = ctx.data.value.nodes.filter((n) => n.type === 'flow')
    const substepNodes = ctx.data.value.nodes.filter((n) => n.type === 'flowSubstep')
    const steps = stepNodes.map((node) => node.text)
    const stepToSubsteps: Record<string, string[]> = {}
    substepNodes.forEach((node) => {
      const match = node.id.match(/flow-substep-(\d+)-/)
      if (match) {
        const stepIndex = parseInt(match[1], 10)
        if (stepIndex < stepNodes.length) {
          const stepText = stepNodes[stepIndex].text
          if (!stepToSubsteps[stepText]) {
            stepToSubsteps[stepText] = []
          }
          stepToSubsteps[stepText].push(node.text)
        }
      }
    })
    const substeps = Object.entries(stepToSubsteps).map(([step, subs]) => ({
      step,
      substeps: subs,
    }))
    const orientation = (ctx.data.value as Record<string, unknown>).orientation ?? 'horizontal'
    return { title, steps, substeps, orientation }
  }

  function loadDefaultTemplate(diagramTypeValue: DiagramType): boolean {
    const template = getDefaultTemplate(diagramTypeValue, useUIStore().language)
    if (!template) return false
    return loadFromSpec(template, diagramTypeValue)
  }

  function mergeGranularUpdate(
    updatedNodes?: Array<Record<string, unknown>>,
    updatedConnections?: Array<Record<string, unknown>>
  ): boolean {
    if (!ctx.data.value) return false

    if (updatedNodes && updatedNodes.length > 0) {
      for (const updatedNode of updatedNodes) {
        const nodeId = updatedNode.id as string
        if (!nodeId) continue

        const existingIndex = ctx.data.value.nodes.findIndex((n) => n.id === nodeId)
        if (existingIndex >= 0) {
          ctx.data.value.nodes[existingIndex] = {
            ...ctx.data.value.nodes[existingIndex],
            ...updatedNode,
          } as DiagramNode
        } else {
          ctx.data.value.nodes.push(updatedNode as unknown as DiagramNode)
        }
      }
    }

    if (updatedConnections && updatedConnections.length > 0) {
      for (const updatedConn of updatedConnections) {
        const source = updatedConn.source as string
        const target = updatedConn.target as string
        if (!source || !target) continue

        let conns: Connection[]
        if (ctx.data.value.connections) {
          conns = ctx.data.value.connections
        } else {
          conns = []
          ctx.data.value.connections = conns
        }
        const existingIndex = conns.findIndex((c) => c.source === source && c.target === target)

        if (existingIndex >= 0) {
          const existing = conns[existingIndex]
          conns[existingIndex] = {
            ...existing,
            ...updatedConn,
          } as Connection
        } else {
          conns.push(updatedConn as unknown as Connection)
        }
      }
    }

    if (ctx.type.value === 'concept_map' && ctx.data.value?.connections && ctx.data.value.nodes) {
      normalizeAllConceptMapTopicRootLabels(ctx.data.value.connections, ctx.data.value.nodes)
    }

    return true
  }

  return {
    loadFromSpec,
    getDoubleBubbleSpecFromData,
    getSpecForSave,
    buildFlowMapSpecFromNodes,
    loadDefaultTemplate,
    mergeGranularUpdate,
  }
}
