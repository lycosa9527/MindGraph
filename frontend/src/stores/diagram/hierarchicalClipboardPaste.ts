import { i18n } from '@/i18n'
import { recalculateBraceMapLayout } from '@/stores/specLoader'
import {
  braceMapRootId,
  isBraceMapPartAddTarget,
  resolveBraceMapSubpartAttachParentId,
} from '@/stores/diagram/braceMapParentResolve'
import type { DiagramNode, DiagramType } from '@/types'
import type { MindMapBranchSpec } from '@/utils/mindMapSubgraphMerge'

import type { DiagramContext } from './types'
import type {
  BraceMapClipboardNode,
  FlowMapClipboardPayload,
  HierarchicalClipboard,
  TreeMapClipboardPayload,
} from './hierarchicalClipboardTypes'

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
    .filter((n) => /^tree-cat-\d+$/.test(n.id ?? ''))
    .sort(
      (a, b) =>
        parseInt((a.id ?? '0').replace('tree-cat-', ''), 10) -
        parseInt((b.id ?? '0').replace('tree-cat-', ''), 10)
    )

  const categories = categoryNodes.map((cat) => {
    const idMatch = (cat.id ?? '').match(/^tree-cat-(\d+)$/)
    const categoryNum = idMatch ? parseInt(idMatch[1], 10) : -1
    const leaves = nodes
      .filter((n) => {
        const m = (n.id ?? '').match(/^tree-leaf-(\d+)-(\d+)$/)
        return m && parseInt(m[1], 10) === categoryNum
      })
      .sort(
        (a, b) =>
          parseInt((a.id ?? '0').split('-').pop() ?? '0', 10) -
          parseInt((b.id ?? '0').split('-').pop() ?? '0', 10)
      )
    return {
      text: cat.text,
      children: leaves.map((l) => ({ text: l.text })),
    }
  })

  if (payload.kind === 'category') {
    if (anchorNodeId === 'tree-topic') {
      categories.push({
        text: payload.text,
        children: payload.leaves.map((leaf) => ({ text: leaf.text })),
      })
    } else if (/^tree-cat-\d+$/.test(anchorNodeId)) {
      const idx = categoryNodes.findIndex((c) => c.id === anchorNodeId)
      const insertAt = idx >= 0 ? idx + 1 : categories.length
      categories.splice(insertAt, 0, {
        text: payload.text,
        children: payload.leaves.map((leaf) => ({ text: leaf.text })),
      })
    } else {
      return false
    }
  } else if (payload.kind === 'leaf') {
    let targetIdx = -1
    if (/^tree-cat-\d+$/.test(anchorNodeId)) {
      targetIdx = categoryNodes.findIndex((c) => c.id === anchorNodeId)
    } else if (anchorNodeId === 'tree-topic' && categories.length > 0) {
      targetIdx = 0
    }
    if (targetIdx < 0 || targetIdx >= categories.length) return false
    const cat = categories[targetIdx]
    if (!cat.children) cat.children = []
    cat.children.push({ text: payload.text })
  }

  const dimension = (ctx.data.value as Record<string, unknown>).dimension
  const altDims = (ctx.data.value as Record<string, unknown>).alternative_dimensions
  const newSpec = {
    root: { text: rootNode.text, children: categories },
    dimension,
    alternative_dimensions: altDims,
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
  const baseId = Date.now()
  const newId = `brace-part-${baseId}`
  ctx.addNode({
    id: newId,
    text: node.text,
    type: 'brace',
    position: { x: 0, y: 0 },
  })
  ctx.addConnection(parentId, newId)

  let childIndex = 0
  for (const child of node.children) {
    const childId = `brace-part-${baseId}-${childIndex}`
    childIndex += 1
    ctx.addNode({
      id: childId,
      text: child.text,
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

  const steps = [...(spec.steps as string[])]
  const substeps = [
    ...(spec.substeps as Array<{ step: string; substeps: string[] }>),
  ]
  const orientation = (ctx.data.value as Record<string, unknown>)?.orientation ?? spec.orientation

  if (payload.kind === 'step') {
    if (anchorNodeId === 'flow-topic' || anchorNodeId.startsWith('flow-step-')) {
      steps.push(payload.step)
      substeps.push({ step: payload.step, substeps: [...payload.substeps] })
    } else {
      return false
    }
  } else if (payload.kind === 'substep') {
    let stepText = ''
    if (anchorNodeId.startsWith('flow-step-')) {
      const match = anchorNodeId.match(/flow-step-(\d+)/)
      const idx = match ? parseInt(match[1], 10) : -1
      stepText = idx >= 0 && idx < steps.length ? steps[idx] : ''
    }
    if (!stepText) return false
    const entry = substeps.find((row) => row.step === stepText)
    if (entry) {
      entry.substeps.push(payload.text)
    } else {
      substeps.push({ step: stepText, substeps: [payload.text] })
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
