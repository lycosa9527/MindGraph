/**
 * Node Palette constants - API paths and diagram type groupings
 */

export const NODE_PALETTE_START = '/thinking_mode/node_palette/start'
export const NODE_PALETTE_NEXT = '/thinking_mode/node_palette/next_batch'

export const RELATIONSHIP_LABELS_START = '/thinking_mode/relationship_labels/start'
export const RELATIONSHIP_LABELS_NEXT = '/thinking_mode/relationship_labels/next_batch'
export const RELATIONSHIP_LABELS_CLEANUP = '/thinking_mode/relationship_labels/cleanup'

export const INLINE_RECOMMENDATIONS_START =
  '/thinking_mode/inline_recommendations/start'
export const INLINE_RECOMMENDATIONS_NEXT =
  '/thinking_mode/inline_recommendations/next_batch'
export const INLINE_RECOMMENDATIONS_CLEANUP =
  '/thinking_mode/inline_recommendations/cleanup'

export const INLINE_RECOMMENDATIONS_SUPPORTED_TYPES = [
  'mindmap',
  'flow_map',
  'tree_map',
  'brace_map',
  'circle_map',
  'bubble_map',
  'double_bubble_map',
  'multi_flow_map',
  'bridge_map',
] as const

export const LEARNING_SHEET_PLACEHOLDER = '___'

export const STAGED_DIAGRAM_TYPES = [
  'mindmap',
  'flow_map',
  'tree_map',
  'brace_map',
  'bridge_map',
] as const

export const DIMENSION_FIRST_TYPES = ['tree_map', 'brace_map', 'bridge_map'] as const

/** Default subpart texts when adding a new brace map part (part with 2 subparts) */
export const BRACE_MAP_DEFAULT_SUBPARTS: Record<'zh' | 'en', [string, string]> = {
  zh: ['新子部分 1', '新子部分 2'],
  en: ['New Subpart 1', 'New Subpart 2'],
}

/** Get stable parent_id from stage_data for tab routing. Prefer ID over name. */
export function getParentIdFromStageData(
  diagramType: string,
  stage: string | undefined,
  stageData: Record<string, unknown> | undefined
): string | null {
  if (!stageData) return null
  const dt = diagramType === 'mind_map' ? 'mindmap' : diagramType
  const stage2 = ['children', 'substeps', 'subparts'].includes(stage ?? '')
  if (!stage2) return null
  if (dt === 'mindmap') return (stageData.branch_id as string) ?? null
  if (dt === 'flow_map') return (stageData.step_id as string) ?? null
  if (dt === 'tree_map') return (stageData.category_id as string) ?? null
  if (dt === 'brace_map') return (stageData.part_id as string) ?? null
  return null
}

/** Check if suggestion belongs to parent: prefer parent_id when available, fallback to mode (name) */
export function suggestionBelongsToParent(
  s: { parent_id?: string; mode?: string },
  parentId: string | null,
  parentNameNorm: string
): boolean {
  if (parentId && s.parent_id) return s.parent_id === parentId
  return (s.mode ?? '').trim() === parentNameNorm
}
