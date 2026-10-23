/**
 * Font size the canvas actually paints, so toolbar controls stay on the same number.
 */
import { isThinkingMapDiagramType } from '@/canvas-ribbon/diagramRibbonCapabilities'
import { MIND_MAP_GEOMETRY } from '@/config/mindMapGeometry'
import type { Connection, DiagramNode, NodeStyle } from '@/types'
import { thinkingMapDisplayedFontSize, thinkingMapRoleChrome } from '@/utils/thinkingMapChrome'

const PAINTED_LABEL_SELECTOR = '.inline-edit-plain, .diagram-node-md'

export function parsePositiveFontSize(value: unknown): number | undefined {
  const parsed = typeof value === 'number' ? value : Number.parseFloat(String(value ?? '').trim())
  if (!Number.isFinite(parsed) || parsed <= 0) return undefined
  return parsed
}

function isMindMap(diagramType: string | null | undefined): boolean {
  return diagramType === 'mindmap' || diagramType === 'mind_map'
}

function isMindMapTopic(node: Pick<DiagramNode, 'id' | 'type'>): boolean {
  return node.type === 'topic' || node.type === 'center' || node.id === 'topic'
}

/**
 * Size shown on the node. A stored size wins. Otherwise the role default
 * (thinking-map chrome, or 18 / 16 for mind-map topic / branch).
 */
export function displayedNodeFontSize(
  diagramType: string | null | undefined,
  node: Pick<DiagramNode, 'id' | 'type' | 'data' | 'style'>,
  style: NodeStyle | undefined,
  connections?: Connection[] | null
): number {
  if (isThinkingMapDiagramType(diagramType)) {
    const chrome = thinkingMapRoleChrome(diagramType, node, connections)
    if (chrome) return thinkingMapDisplayedFontSize(style?.fontSize, chrome.fontSize)
  }
  const stored = parsePositiveFontSize(style?.fontSize)
  if (stored != null) return stored
  if (isMindMap(diagramType)) {
    return isMindMapTopic(node) ? MIND_MAP_GEOMETRY.topicFontSize : MIND_MAP_GEOMETRY.branchFontSize
  }
  return 14
}

function escapeNodeId(nodeId: string): string {
  if (typeof CSS !== 'undefined' && typeof CSS.escape === 'function') return CSS.escape(nodeId)
  return nodeId.replace(/"/g, '')
}

function inlineFontSizePx(el: HTMLElement): number | undefined {
  return parsePositiveFontSize(el.style.fontSize)
}

/**
 * Font size declared on the node shell (what the label inherits), otherwise
 * the label's used size. This is the number the floating toolbar should show.
 */
export function readPaintedNodeFontSizePx(nodeId: string): number | undefined {
  if (typeof document === 'undefined' || !nodeId) return undefined
  const root = document.querySelector(`.vue-flow__node[data-id="${escapeNodeId(nodeId)}"]`)
  if (!(root instanceof HTMLElement)) return undefined
  const label = root.querySelector(PAINTED_LABEL_SELECTOR)
  if (!(label instanceof HTMLElement)) return undefined
  let el: HTMLElement | null = label
  while (el) {
    const inline = inlineFontSizePx(el)
    if (inline != null) return Math.round(inline)
    if (el === root) break
    el = el.parentElement
  }
  const computed = Number.parseFloat(getComputedStyle(label).fontSize)
  if (!Number.isFinite(computed) || computed <= 0) return undefined
  return Math.round(computed)
}
