import { i18n } from '@/i18n'
import {
  braceMapRootId,
  isBraceMapPartAddTarget,
  resolveBraceMapSubpartAttachParentId,
} from '@/stores/diagram/braceMapParentResolve'
import { recalculateBraceMapLayout } from '@/stores/specLoader'
import { type FlowSubstepEntry, findFlowSubstepEntry } from '@/stores/specLoader/flowMapSubsteps'
import type { DiagramNode, DiagramType } from '@/types'
import { takeBraceMapStableId } from '@/utils/braceMapIdentity'
import { isFlowMapStepNode, readFlowStepIndex } from '@/utils/flowMapIdentity'
import type { MindMapBranchSpec } from '@/utils/mindMapSubgraphMerge'
import {
  isTreeMapCategoryNode,
  isTreeMapLeafNode,
  readTreeCategoryIndex,
  readTreeLeafIndex,
  readTreeParentCategoryId,
} from '@/utils/treeMapIdentity'

import type {
  BraceMapClipboardNode,
  FlowMapClipboardPayload,
  HierarchicalClipboard,
  TreeMapClipboardPayload,
} from './hierarchicalClipboardTypes'
import type { DiagramContext } from './types'

function glossField(node: { textSecondary?: string }): { textSecondary?: string } {
  const line = String(node.textSecondary ?? '').trim()
  return line ? { textSecondary: line } : {}
}

function flowMirror(spec: Record<string, unknown>): Record<string, unknown> {
  const raw = spec.secondary
  if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
    return raw as Record<string, unknown>
  }
  const created = {
    title: '',
    steps: [] as string[],
    substeps: [] as Array<{ substeps: string[] }>,
  }
  spec.secondary = created
  return created
}

function appendFlowStepGloss(
  spec: Record<string, unknown>,
  stepCount: number,
  stepGloss: string,
  substepGlosses: string[]
): void {
  const hasNew = stepGloss.trim().length > 0 || substepGlosses.some((line) => line.trim())
  const raw = spec.secondary
  const existed = Boolean(raw && typeof raw === 'object' && !Array.isArray(raw))
  if (!existed && !hasNew) return
  const mirror = flowMirror(spec)
  const steps = Array.isArray(mirror.steps) ? [...(mirror.steps as string[])] : []
  const groups = Array.isArray(mirror.substeps)
    ? [...(mirror.substeps as Array<{ substeps?: string[] }>)]
    : []
  while (steps.length < stepCount - 1) steps.push('')
  while (groups.length < stepCount - 1) groups.push({ substeps: [] })
  steps.push(stepGloss.trim())
  groups.push({ substeps: substepGlosses.map((line) => line.trim()) })
  mirror.steps = steps
  mirror.substeps = groups
}

function appendFlowSubstepGloss(
  spec: Record<string, unknown>,
  stepIndex: number,
  gloss: string
): void {
  const line = gloss.trim()
  const raw = spec.secondary
  const existed = Boolean(raw && typeof raw === 'object' && !Array.isArray(raw))
  if (!existed && !line) return
  if (stepIndex < 0) return
  const mirror = flowMirror(spec)
  const groups = Array.isArray(mirror.substeps)
    ? [...(mirror.substeps as Array<{ substeps?: string[] }>)]
    : []
  while (groups.length <= stepIndex) groups.push({ substeps: [] })
  const group = groups[stepIndex]
  if (!group) return
  const lines = Array.isArray(group.substeps) ? [...group.substeps] : []
  lines.push(line)
  groups[stepIndex] = { ...group, substeps: lines }
  mirror.substeps = groups
}

export type HierarchicalClipboardPasteDeps = {
  pasteMindMapClipboardBranches: (
    anchorNodeId: string,
    branches: MindMapBranchSpec[],
    historyLabel?: string
  ) => boolean
}

function defaultAnchorForType(diagramType: DiagramType | null): string {
  if (diagramType === 'mindmap' || diagramType === 'mind_map') return 'topic'
  if (diagramType === 'tree_map') return 'tree-topic'
  if (diagramType === 'flow_map') return 'flow-topic'
  if (diagramType === 'brace_map') return 'brace-whole'
  return 'topic'
}

function resolvePasteAnchor(ctx: DiagramContext, anchorNodeId?: string): string {
  const explicit = anchorNodeId?.trim()
  if (explicit) return explicit
  const selected = ctx.selectedNodes.value[0]
  if (selected) return selected
  return defaultAnchorForType(ctx.type.value)
}

function pasteMindMapBranches(
  ctx: DiagramContext,
  deps: HierarchicalClipboardPasteDeps,
  anchorNodeId: string,
  branches: MindMapBranchSpec[]
): boolean {
  if (!ctx.data.value?.nodes || !ctx.data.value.connections) return false
  return deps.pasteMindMapClipboardBranches(anchorNodeId, branches)
}

function pasteTreeMapPayload(
  ctx: DiagramContext,
  anchorNodeId: string,
  payload: TreeMapClipboardPayload
): boolean {
  if (ctx.type.value !== 'tree_map' || !ctx.data.value?.nodes) return false
  const nodes = ctx.data.value.nodes
  const rootNode = nodes.find((n) => n.id === 'tree-topic')
  if (!rootNode) return false

  const categoryNodes = nodes
    .filter((n) => isTreeMapCategoryNode(n))
    .sort((a, b) => readTreeCategoryIndex(a) - readTreeCategoryIndex(b))

  const categories = categoryNodes.map((cat) => {
    const leaves = nodes
      .filter((n) => {
        if (!isTreeMapLeafNode(n)) return false
        const parentId = readTreeParentCategoryId(n)
        if (parentId) return parentId === cat.id
        return readTreeCategoryIndex(n) === readTreeCategoryIndex(cat)
      })
      .sort((a, b) => readTreeLeafIndex(a) - readTreeLeafIndex(b))
    return {
      text: cat.text,
      ...glossField(cat),
      children: leaves.map((leaf) => ({ text: leaf.text, ...glossField(leaf) })),
    }
  })

  const anchor = nodes.find((n) => n.id === anchorNodeId)

  if (payload.kind === 'category') {
    if (anchorNodeId === 'tree-topic') {
      categories.push({
        text: payload.text,
        ...glossField(payload),
        children: payload.leaves.map((leaf) => ({ text: leaf.text, ...glossField(leaf) })),
      })
    } else if (anchor && isTreeMapCategoryNode(anchor)) {
      const idx = categoryNodes.findIndex((c) => c.id === anchorNodeId)
      const insertAt = idx >= 0 ? idx + 1 : categories.length
      categories.splice(insertAt, 0, {
        text: payload.text,
        ...glossField(payload),
        children: payload.leaves.map((leaf) => ({ text: leaf.text, ...glossField(leaf) })),
      })
    } else {
      return false
    }
  } else if (payload.kind === 'leaf') {
    let targetIdx = -1
    if (anchor && isTreeMapCategoryNode(anchor)) {
      targetIdx = categoryNodes.findIndex((c) => c.id === anchorNodeId)
    } else if (anchorNodeId === 'tree-topic' && categories.length > 0) {
      targetIdx = 0
    }
    if (targetIdx < 0 || targetIdx >= categories.length) return false
    const cat = categories[targetIdx]
    if (!cat.children) cat.children = []
    cat.children.push({ text: payload.text, ...glossField(payload) })
  }

  const dataRecord = ctx.data.value as Record<string, unknown>
  const dimension = dataRecord.dimension
  const altDims = dataRecord.alternative_dimensions
  const dimensionNode = nodes.find((node) => node.id === 'dimension-label')
  const dimensionSecondary = String(dimensionNode?.textSecondary ?? '').trim()
  const languages = dataRecord.languages
  const newSpec = {
    root: { text: rootNode.text, ...glossField(rootNode), children: categories },
    dimension,
    ...(dimensionSecondary ? { dimensionSecondary } : {}),
    alternative_dimensions: altDims,
    ...(languages && typeof languages === 'object' ? { languages } : {}),
  }
  const ok = ctx.loadFromSpec(newSpec, 'tree_map', { mergePreviousNodeStyles: true })
  if (ok) {
    ctx.pushHistory(String(i18n.global.t('diagram.history.pasteNodes')))
  }
  return ok
}

function addBraceSubtree(
  ctx: DiagramContext,
  parentId: string,
  node: BraceMapClipboardNode,
  rootId: string
): void {
  const claimed = new Set((ctx.data.value?.nodes ?? []).map((n) => n.id).filter(Boolean))
  const newId = takeBraceMapStableId(claimed)
  ctx.addNode({
    id: newId,
    text: node.text,
    ...glossField(node),
    type: 'brace',
    position: { x: 0, y: 0 },
  })
  ctx.addConnection(parentId, newId)

  for (const child of node.children) {
    const childId = takeBraceMapStableId(claimed)
    ctx.addNode({
      id: childId,
      text: child.text,
      ...glossField(child),
      type: 'brace',
      position: { x: 0, y: 0 },
    })
    ctx.addConnection(newId, childId)
    for (const grandchild of child.children) {
      addBraceSubtree(ctx, childId, grandchild, rootId)
    }
  }
}

function pasteBraceSubtree(
  ctx: DiagramContext,
  anchorNodeId: string,
  subtree: BraceMapClipboardNode
): boolean {
  if (ctx.type.value !== 'brace_map' || !ctx.data.value?.nodes || !ctx.data.value.connections) {
    return false
  }
  const connections = ctx.data.value.connections
  const rootId = braceMapRootId(ctx.data.value.nodes, connections)
  if (!rootId) return false

  const anchorNode = ctx.data.value.nodes.find((n) => n.id === anchorNodeId)
  if (!anchorNode) return false

  const attachParentId =
    anchorNodeId === rootId || isBraceMapPartAddTarget(anchorNodeId, anchorNode, rootId)
      ? anchorNodeId
      : resolveBraceMapSubpartAttachParentId(anchorNodeId, connections, rootId)

  addBraceSubtree(ctx, attachParentId, subtree, rootId)
  const layoutNodes = recalculateBraceMapLayout(
    ctx.data.value.nodes,
    ctx.data.value.connections,
    ctx.nodeDimensions.value
  )
  ctx.data.value.nodes = layoutNodes
  ctx.pushHistory(String(i18n.global.t('diagram.history.pasteNodes')))
  return true
}

function pasteFlowMapPayload(
  ctx: DiagramContext,
  anchorNodeId: string,
  payload: FlowMapClipboardPayload
): boolean {
  if (ctx.type.value !== 'flow_map') return false
  const spec = ctx.buildFlowMapSpecFromNodes()
  if (!spec) return false

  const steps = [...(spec.steps as Array<string | { id?: string; text: string }>)]
  const substeps = [...(spec.substeps as FlowSubstepEntry[])]
  const orientation = (ctx.data.value as Record<string, unknown>)?.orientation ?? spec.orientation
  const anchorNode = ctx.data.value?.nodes.find((n) => n.id === anchorNodeId)
  const anchorIsStep = anchorNode != null && isFlowMapStepNode(anchorNode)

  if (payload.kind === 'step') {
    if (anchorNodeId === 'flow-topic' || anchorIsStep) {
      steps.push({ text: payload.step })
      substeps.push({
        step: payload.step,
        stepIndex: steps.length - 1,
        substeps: [...payload.substeps],
      })
      appendFlowStepGloss(
        spec,
        steps.length,
        payload.stepSecondary ?? '',
        payload.substepsSecondary ?? []
      )
    } else {
      return false
    }
  } else if (payload.kind === 'substep') {
    if (!anchorIsStep || !anchorNode) return false
    const stepText = anchorNode.text
    const stepIndex = readFlowStepIndex(anchorNode)
    if (!stepText) return false
    const entry = findFlowSubstepEntry(
      substeps,
      stepText,
      stepIndex >= 0 ? stepIndex : undefined,
      anchorNode.id
    )
    if (entry) {
      entry.substeps.push(payload.text)
      appendFlowSubstepGloss(spec, stepIndex, payload.textSecondary ?? '')
    } else {
      substeps.push({
        step: stepText,
        stepId: anchorNode.id,
        stepIndex: stepIndex >= 0 ? stepIndex : undefined,
        substeps: [payload.text],
      })
      appendFlowSubstepGloss(spec, stepIndex, payload.textSecondary ?? '')
    }
  }

  const ok = ctx.loadFromSpec({ ...spec, steps, substeps, orientation }, 'flow_map', {
    mergePreviousNodeStyles: true,
  })
  if (ok) {
    ctx.pushHistory(String(i18n.global.t('diagram.history.pasteNodes')))
  }
  return ok
}

function pasteFlatNodes(
  ctx: DiagramContext,
  flowPosition: { x: number; y: number },
  nodes: DiagramNode[]
): boolean {
  if (nodes.length === 0) return false
  const offset = 20
  nodes.forEach((node, index) => {
    const newNode: DiagramNode = {
      ...JSON.parse(JSON.stringify(node)),
      id: `node-${Date.now()}-${index}`,
      position: {
        x: flowPosition.x + index * offset,
        y: flowPosition.y + index * offset,
      },
    }
    ctx.addNode(newNode)
  })
  ctx.pushHistory(String(i18n.global.t('diagram.history.pasteNodes')))
  return true
}

export function pasteHierarchicalClipboard(
  ctx: DiagramContext,
  deps: HierarchicalClipboardPasteDeps,
  clipboard: HierarchicalClipboard,
  options: { anchorNodeId?: string; flowPosition?: { x: number; y: number } }
): boolean {
  const targetType = ctx.type.value
  if (!targetType || targetType !== clipboard.sourceDiagramType) {
    return false
  }

  const anchor = resolvePasteAnchor(ctx, options.anchorNodeId)
  const payload = clipboard.payload

  if (payload.kind === 'mindmap_branches') {
    return pasteMindMapBranches(ctx, deps, anchor, payload.branches)
  }
  if (payload.kind === 'tree_map') {
    return pasteTreeMapPayload(ctx, anchor, payload.payload)
  }
  if (payload.kind === 'brace_map') {
    return pasteBraceSubtree(ctx, anchor, payload.subtree)
  }
  if (payload.kind === 'flow_map') {
    return pasteFlowMapPayload(ctx, anchor, payload.payload)
  }
  if (payload.kind === 'flat_nodes' && options.flowPosition) {
    return pasteFlatNodes(ctx, options.flowPosition, payload.nodes)
  }
  return false
}
