import { mindMapBranchDepth } from '@/config/mindMapGeometry'
import type { DiagramNode } from '@/types'
import type { NodeShape } from '@/utils/nodeShapeStyle'

export type MindMapDiagramStyleId =
  | 'classic'
  | 'formal'
  | 'bubble'
  | 'underline'
  | 'soft'

export interface MindMapDiagramStylePreset {
  id: MindMapDiagramStyleId
  nameKey: string
  descKey: string
  topicShape: NodeShape
  branchDepth1Shape: NodeShape
  branchDepth2Shape: NodeShape
  branchDepth3PlusShape: NodeShape
}

export const DEFAULT_MIND_MAP_DIAGRAM_STYLE_ID: MindMapDiagramStyleId = 'classic'

/** @deprecated Renamed — classic now includes underline L2+. */
const LEGACY_STYLE_IDS: Record<string, MindMapDiagramStyleId> = {
  layered: 'classic',
}

const CLASSIC: MindMapDiagramStylePreset = {
  id: 'classic',
  nameKey: 'canvas.toolbar.mindMapDiagramStyleClassic',
  descKey: 'canvas.toolbar.mindMapDiagramStyleClassicDesc',
  topicShape: 'rectangle',
  branchDepth1Shape: 'rounded',
  branchDepth2Shape: 'underline',
  branchDepth3PlusShape: 'underline',
}

const FORMAL: MindMapDiagramStylePreset = {
  id: 'formal',
  nameKey: 'canvas.toolbar.mindMapDiagramStyleFormal',
  descKey: 'canvas.toolbar.mindMapDiagramStyleFormalDesc',
  topicShape: 'rectangle',
  branchDepth1Shape: 'rectangle',
  branchDepth2Shape: 'rectangle',
  branchDepth3PlusShape: 'rectangle',
}

const BUBBLE: MindMapDiagramStylePreset = {
  id: 'bubble',
  nameKey: 'canvas.toolbar.mindMapDiagramStyleBubble',
  descKey: 'canvas.toolbar.mindMapDiagramStyleBubbleDesc',
  topicShape: 'oval',
  branchDepth1Shape: 'oval',
  branchDepth2Shape: 'underline',
  branchDepth3PlusShape: 'underline',
}

const UNDERLINE: MindMapDiagramStylePreset = {
  id: 'underline',
  nameKey: 'canvas.toolbar.mindMapDiagramStyleUnderline',
  descKey: 'canvas.toolbar.mindMapDiagramStyleUnderlineDesc',
  topicShape: 'rectangle',
  branchDepth1Shape: 'underline',
  branchDepth2Shape: 'underline',
  branchDepth3PlusShape: 'underline',
}

const SOFT: MindMapDiagramStylePreset = {
  id: 'soft',
  nameKey: 'canvas.toolbar.mindMapDiagramStyleSoft',
  descKey: 'canvas.toolbar.mindMapDiagramStyleSoftDesc',
  topicShape: 'rounded',
  branchDepth1Shape: 'oval',
  branchDepth2Shape: 'oval',
  branchDepth3PlusShape: 'underline',
}

export const MIND_MAP_DIAGRAM_STYLES: MindMapDiagramStylePreset[] = [
  CLASSIC,
  FORMAL,
  BUBBLE,
  UNDERLINE,
  SOFT,
]

export function getMindMapDiagramStyleById(id?: string | null): MindMapDiagramStylePreset {
  const resolved = id ? (LEGACY_STYLE_IDS[id] ?? id) : undefined
  const found = MIND_MAP_DIAGRAM_STYLES.find((item) => item.id === resolved)
  return found ?? CLASSIC
}

export function resolveMindMapDiagramStyleId(stored?: string | null): MindMapDiagramStyleId {
  if (!stored) return DEFAULT_MIND_MAP_DIAGRAM_STYLE_ID
  const mapped = LEGACY_STYLE_IDS[stored] ?? stored
  if (MIND_MAP_DIAGRAM_STYLES.some((item) => item.id === mapped)) {
    return mapped as MindMapDiagramStyleId
  }
  return DEFAULT_MIND_MAP_DIAGRAM_STYLE_ID
}

/** Formal & soft styles: center / L1 / L2 / L3+ use depth-layered fills from theme accent. */
export function mindMapDiagramStyleUsesLayeredBranchColors(
  diagramStyleId?: string | null
): boolean {
  const id = resolveMindMapDiagramStyleId(diagramStyleId)
  return id === 'formal' || id === 'soft'
}

export function mindMapNodeShapeFromPreset(
  node: Pick<DiagramNode, 'id' | 'type'>,
  preset: MindMapDiagramStylePreset
): NodeShape {
  if (node.type === 'topic' || node.type === 'center' || node.id === 'topic') {
    return preset.topicShape
  }
  if (node.id.startsWith('branch-')) {
    const depth = mindMapBranchDepth(node.id)
    if (depth <= 1) return preset.branchDepth1Shape
    if (depth === 2) return preset.branchDepth2Shape
    return preset.branchDepth3PlusShape
  }
  return 'rounded'
}

/** Diagram-level default shape when the node has no explicit nodeShape. */
export function resolveMindMapNodeShape(
  node: Pick<DiagramNode, 'id' | 'type' | 'style'>,
  diagramStyleId?: string | null
): NodeShape {
  if (node.style?.nodeShape) return node.style.nodeShape
  return mindMapNodeShapeFromPreset(node, getMindMapDiagramStyleById(diagramStyleId))
}
