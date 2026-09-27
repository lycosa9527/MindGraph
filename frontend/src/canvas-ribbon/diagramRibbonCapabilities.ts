/**
 * Which ribbon tools a diagram type may show.
 * Mind-map v2 layout, numbering, and path tools stay off for every other type.
 * The eight thinking maps share the mind-map style strip, explain, and classroom.
 */

const THINKING_MAP_TYPES = new Set([
  'circle_map',
  'bubble_map',
  'double_bubble_map',
  'tree_map',
  'brace_map',
  'flow_map',
  'multi_flow_map',
  'bridge_map',
])

export type DiagramRibbonCapabilities = {
  /** Child / sibling mutations. Classic and new mind maps. */
  mindMapTree: boolean
  /** Structure, numbering, summaries, adornments, subgraph, outline. */
  mindMapV2: boolean
  /** Node style, text style, appearance, and follow-node. Mind-map v2 and thinking maps. */
  mindMapFormat: boolean
  /** Eight thinking maps (not concept maps, not mind maps). */
  thinkingMapChrome: boolean
  flowOrientation: boolean
  conceptMap: boolean
  waterfall: boolean
  oneSentence: boolean
  topicGenerate: boolean
  conceptGenerate: boolean
  /** Node explain. Mind maps and the eight thinking maps. */
  explain: boolean
  /** Mind classroom. Mind maps and the eight thinking maps. */
  mindClassroom: boolean
  /** File / web / voice summary. Those routes emit a mind-map spec. */
  docGenerate: boolean
  /** Three-mode blanking panel. Mind-map v2 and the eight thinking maps. */
  learningSheetPanel: boolean
  /** Classic `is_learning_sheet` toggle. */
  learningSheetToggle: boolean
  outline: boolean
  gestureGuide: boolean
  subgraph: boolean
  /** PNG / SVG / PDF / .mg. Mind-map v2 keeps its shorter menu. */
  standardExport: boolean
}

const MIND_MAP_TYPES = new Set(['mindmap', 'mind_map'])

export function isMindMapDiagramType(type: string | null | undefined): boolean {
  return typeof type === 'string' && MIND_MAP_TYPES.has(type)
}

export function isThinkingMapDiagramType(type: string | null | undefined): boolean {
  return typeof type === 'string' && THINKING_MAP_TYPES.has(type)
}

export function diagramRibbonCapabilities(
  type: string | null | undefined,
  mindMapV2: boolean
): DiagramRibbonCapabilities {
  const mindMap = isMindMapDiagramType(type)
  const thinkingMap = isThinkingMapDiagramType(type)
  const v2 = mindMap && mindMapV2
  const conceptMap = type === 'concept_map'
  return {
    mindMapTree: mindMap,
    mindMapV2: v2,
    mindMapFormat: v2 || thinkingMap,
    thinkingMapChrome: thinkingMap,
    flowOrientation: type === 'flow_map',
    conceptMap,
    waterfall: !conceptMap,
    oneSentence: true,
    topicGenerate: true,
    conceptGenerate: conceptMap,
    explain: mindMap || thinkingMap,
    mindClassroom: mindMap || thinkingMap,
    docGenerate: v2,
    learningSheetPanel: v2 || thinkingMap,
    learningSheetToggle: !v2 && !thinkingMap,
    outline: v2,
    gestureGuide: v2,
    subgraph: v2,
    standardExport: !v2,
  }
}
