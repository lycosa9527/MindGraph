/**
 * Which ribbon tools a diagram type may show.
 * Mind-map v2 layout, numbering, and path tools stay off for every other type.
 * Thinking maps and concept maps share the mind-map tab strip. Mind-map-only
 * layout, numbering, and path tools stay off.
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
  /** Node style, text style, appearance, and follow-node. */
  mindMapFormat: boolean
  /** Eight thinking maps (not concept maps, not mind maps). */
  thinkingMapChrome: boolean
  flowOrientation: boolean
  conceptMap: boolean
  waterfall: boolean
  oneSentence: boolean
  topicGenerate: boolean
  conceptGenerate: boolean
  /** Node explain. Mind maps, thinking maps, and concept maps. */
  explain: boolean
  /** Mind classroom. Mind maps, thinking maps, and concept maps. */
  mindClassroom: boolean
  /** File / web / voice summary. Mind maps use the content agent; other types use that generator. */
  docGenerate: boolean
  /** Three-mode blanking panel. Mind-map v2, thinking maps, and concept maps. */
  learningSheetPanel: boolean
  /** Classic `is_learning_sheet` toggle. */
  learningSheetToggle: boolean
  /** 层级大纲. Mind-map v2 and the eight thinking maps. */
  outline: boolean
  /** Status-bar hand-gesture guide. Mind-map v2 and the eight thinking maps. */
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

/** Mind-map v2, the eight thinking maps, and concept maps use the tab canvas. */
export function isDiagramRibbonFamily(
  type: string | null | undefined,
  mindMapV2: boolean
): boolean {
  const caps = diagramRibbonCapabilities(type, mindMapV2)
  return caps.mindMapV2 || caps.thinkingMapChrome || caps.conceptMap
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
    mindMapFormat: v2 || thinkingMap || conceptMap,
    thinkingMapChrome: thinkingMap,
    flowOrientation: type === 'flow_map',
    conceptMap,
    waterfall: true,
    oneSentence: true,
    topicGenerate: true,
    conceptGenerate: conceptMap,
    explain: mindMap || thinkingMap || conceptMap,
    mindClassroom: mindMap || thinkingMap || conceptMap,
    docGenerate: v2 || thinkingMap,
    learningSheetPanel: v2 || thinkingMap || conceptMap,
    learningSheetToggle: !v2 && !thinkingMap && !conceptMap,
    outline: v2 || thinkingMap,
    gestureGuide: v2 || thinkingMap,
    subgraph: v2 || thinkingMap || conceptMap,
    standardExport: !v2,
  }
}
