/**
 * Node Palette stage helpers - stage resolution and parent selection for staged diagrams
 */
import { isPlaceholderText } from '@/composables/editor/useAutoComplete'
import type { DiagramType } from '@/types'

import { DIMENSION_FIRST_TYPES, STAGED_DIAGRAM_TYPES } from './constants'

export { STAGED_DIAGRAM_TYPES }

export interface Stage2Parent {
  id: string
  name: string
}

function normalizeDiagramType(dt: DiagramType | null): DiagramType | null {
  return dt === 'mind_map' ? 'mindmap' : dt
}

export function hasDimension(
  diagramType: DiagramType | null,
  nodes: Array<{ id?: string; text?: string; type?: string }>,
  dataDimension?: string | null
): boolean {
  const dt = normalizeDiagramType(diagramType)
  if (!DIMENSION_FIRST_TYPES.includes(dt as (typeof DIMENSION_FIRST_TYPES)[number])) {
    return true
  }
  const dim = dataDimension ?? nodes.find((n) => n.id === 'dimension-label')?.text ?? ''
  const t = (dim ?? '').trim()
  return t.length > 0 && !isPlaceholderText(t)
}

export function getDefaultStage(
  diagramType: DiagramType | null,
  nodes: Array<{ id?: string; text?: string; type?: string }>,
  connections?: Array<{ source: string; target: string }>,
  dataDimension?: string | null
): string {
  const dt = normalizeDiagramType(diagramType)
  switch (dt) {
    case 'mindmap': {
      const branchNodes = nodes.filter(
        (n) => n.id?.startsWith('branch-l-1-') || n.id?.startsWith('branch-r-1-')
      )
      const hasBranchesWithRealText =
        branchNodes.length > 0 &&
        branchNodes.some((n) => n.text && n.text.trim() && !isPlaceholderText(n.text))
      return hasBranchesWithRealText ? 'children' : 'branches'
    }
    case 'flow_map': {
      const stepNodes = nodes.filter((n) => n.type === 'flow' && n.id?.startsWith('flow-step-'))
      const hasStepsWithRealText =
        stepNodes.length > 0 &&
        stepNodes.some((n) => n.text && n.text.trim() && !isPlaceholderText(n.text))
      return hasStepsWithRealText ? 'substeps' : 'steps'
    }
    case 'tree_map': {
      if (!hasDimension(dt, nodes, dataDimension)) return 'dimensions'
      const categoryNodes = nodes.filter((n) => /^tree-cat-\d+$/.test(n.id ?? ''))
      const hasCategoriesWithRealText =
        categoryNodes.length > 0 &&
        categoryNodes.some((n) => n.text && n.text.trim() && !isPlaceholderText(n.text))
      return hasCategoriesWithRealText ? 'children' : 'categories'
    }
    case 'brace_map': {
      if (!hasDimension(dt, nodes, dataDimension)) return 'dimensions'
      const rootId =
        nodes.find((n) => n.id === 'brace-whole' || n.id === 'brace-0-0')?.id ??
        nodes.find((n) => n.type === 'topic')?.id ??
        (connections
          ? nodes.find((n) => !new Set(connections.map((c) => c.target)).has(n.id ?? ''))?.id
          : undefined)
      const directParts = nodes.filter(
        (n) =>
          n.type === 'brace' &&
          rootId &&
          connections?.some((c) => c.source === rootId && c.target === n.id)
      )
      const hasPartsWithRealText =
        directParts.length > 0 &&
        directParts.some((n) => n.text && n.text.trim() && !isPlaceholderText(n.text))
      return hasPartsWithRealText ? 'subparts' : 'parts'
    }
    case 'bridge_map': {
      if (!hasDimension(dt, nodes, dataDimension)) return 'dimensions'
      return 'pairs'
    }
    default:
      return 'branches'
  }
}

export function stage2StageNameForType(dt: DiagramType | null): string {
  const normalized = normalizeDiagramType(dt)
  switch (normalized) {
    case 'mindmap':
      return 'children'
    case 'flow_map':
      return 'substeps'
    case 'tree_map':
      return 'children'
    case 'brace_map':
      return 'subparts'
    case 'bridge_map':
      return 'pairs'
    default:
      return ''
  }
}

export function getStage2ParentsForDiagram(
  diagramType: DiagramType | null,
  nodes: Array<{ id?: string; text?: string; type?: string }>,
  connections?: Array<{ source: string; target: string }>
): Stage2Parent[] {
  const dt = normalizeDiagramType(diagramType)
  const hasRealText = (n: { text?: string }) =>
    n.text && n.text.trim() && !isPlaceholderText(n.text)
  if (dt === 'mindmap') {
    return nodes
      .filter(
        (n) =>
          (n.id?.startsWith('branch-l-1-') || n.id?.startsWith('branch-r-1-')) && hasRealText(n)
      )
      .map((n) => ({ id: n.id ?? '', name: String(n.text) }))
  }
  if (dt === 'flow_map') {
    return nodes
      .filter((n) => n.type === 'flow' && hasRealText(n))
      .map((n) => ({ id: n.id ?? '', name: String(n.text) }))
  }
  if (dt === 'tree_map') {
    return nodes
      .filter((n) => /^tree-cat-\d+$/.test(n.id ?? '') && hasRealText(n))
      .map((n) => ({ id: n.id ?? '', name: String(n.text) }))
  }
  if (dt === 'brace_map') {
    const targetIds = new Set(connections?.map((c) => c.target) ?? [])
    const rootId =
      nodes.find((n) => n.id === 'brace-whole' || n.id === 'brace-0-0')?.id ??
      nodes.find((n) => n.type === 'topic')?.id ??
      nodes.find((n) => !targetIds.has(n.id ?? ''))?.id
    return nodes
      .filter(
        (n) =>
          n.type === 'brace' &&
          connections?.some((c) => c.source === rootId && c.target === n.id) &&
          hasRealText(n)
      )
      .map((n) => ({ id: n.id ?? '', name: String(n.text) }))
  }
  return []
}

export function buildStageDataForParent(
  parent: Stage2Parent,
  dt: DiagramType | null,
  extras?: { dimension?: string }
): Record<string, unknown> {
  const normalized = normalizeDiagramType(dt)
  const key =
    normalized === 'mindmap'
      ? 'branch_name'
      : normalized === 'flow_map'
        ? 'step_name'
        : normalized === 'tree_map'
          ? 'category_name'
          : 'part_name'
  const data: Record<string, unknown> = { [key]: parent.name }
  if (normalized === 'mindmap') {
    data.branch_id = parent.id
  }
  if (normalized === 'flow_map') {
    data.step_id = parent.id
  }
  if (normalized === 'tree_map') {
    data.category_id = parent.id
  }
  if (normalized === 'brace_map') {
    data.part_id = parent.id
    if (extras?.dimension?.trim()) {
      data.dimension = extras.dimension.trim()
    }
  }
  return data
}
