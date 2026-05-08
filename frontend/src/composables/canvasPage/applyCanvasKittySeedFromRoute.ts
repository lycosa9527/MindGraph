/**
 * Applies optional ``kitty_*`` URL query hints after ``loadDefaultTemplate`` (mobile Kitty → desktop navigation).
 */
import type { RouteLocationNormalizedLoaded } from 'vue-router'

import type { DiagramType } from '@/types'
import { useDiagramStore } from '@/stores'

type DiagramPiniaStore = ReturnType<typeof useDiagramStore>

function stringQuery(q: RouteLocationNormalizedLoaded['query'], key: string): string | undefined {
  const raw = q[key]
  if (typeof raw === 'string') return raw.trim() ? raw : undefined
  if (Array.isArray(raw) && typeof raw[0] === 'string' && raw[0].trim()) return raw[0]
  return undefined
}

/** True when URL carries Kitty-open seed strings (even if empty-ish after trim → still strip from bar). */
export function canvasKittySeedQueryKeysPresent(
  query: RouteLocationNormalizedLoaded['query']
): boolean {
  return (
    typeof query.kitty_topic !== 'undefined' ||
    typeof query.kitty_left !== 'undefined' ||
    typeof query.kitty_right !== 'undefined'
  )
}

function patchTopicNode(
  store: DiagramPiniaStore,
  nodeId: string,
  text: string
): boolean {
  const trimmed = text.trim()
  if (!trimmed || !store.data?.nodes.some((n) => n.id === nodeId)) {
    return false
  }
  return store.updateNode(nodeId, { text: trimmed })
}

/** First topic/center/root-like node — brace maps may omit ``brace-whole`` id depending on template. */
function patchFirstTopicLike(store: DiagramPiniaStore, text: string): boolean {
  const trimmed = text.trim()
  if (!trimmed) return false
  const nodes = store.data?.nodes ?? []
  const hit =
    nodes.find((n) => n.type === 'topic' || n.type === 'center') ??
    nodes.find((n) => n.id.endsWith('-topic') || n.id === 'event')
  if (!hit) return false
  return store.updateNode(hit.id, { text: trimmed })
}

/**
 * Applies ``kitty_topic`` / ``kitty_left`` / ``kitty_right`` onto default template centers when present.
 *
 * Diagram-type-specific IDs follow ``stores/specLoader/*`` defaults.
 */
export function applyCanvasKittySeedFromRoute(
  diagramType: DiagramType,
  query: RouteLocationNormalizedLoaded['query'],
  diagramStore: DiagramPiniaStore
): void {
  const topic = stringQuery(query, 'kitty_topic')
  const left = stringQuery(query, 'kitty_left')
  const right = stringQuery(query, 'kitty_right')
  if (!topic && !left && !right) return

  const tslice = topic?.slice(0, 480) ?? ''
  const lslice = left?.slice(0, 240) ?? ''
  const rslice = right?.slice(0, 240) ?? ''

  switch (diagramType) {
    case 'double_bubble_map': {
      if (lslice) patchTopicNode(diagramStore, 'left-topic', lslice)
      if (rslice) patchTopicNode(diagramStore, 'right-topic', rslice)
      if (tslice && !lslice) patchTopicNode(diagramStore, 'left-topic', tslice)
      break
    }
    case 'tree_map':
      patchTopicNode(diagramStore, 'tree-topic', tslice) || patchFirstTopicLike(diagramStore, tslice)
      break
    case 'flow_map':
      patchTopicNode(diagramStore, 'flow-topic', tslice) || patchFirstTopicLike(diagramStore, tslice)
      break
    case 'multi_flow_map':
      patchTopicNode(diagramStore, 'event', tslice) || patchFirstTopicLike(diagramStore, tslice)
      break
    case 'brace_map':
      patchTopicNode(diagramStore, 'brace-whole', tslice) || patchFirstTopicLike(diagramStore, tslice)
      break
    case 'bridge_map':
      patchTopicNode(diagramStore, 'dimension-label', tslice)
      break
    case 'circle_map':
    case 'bubble_map':
    case 'mindmap':
    case 'mind_map':
    case 'concept_map':
      patchTopicNode(diagramStore, 'topic', tslice) || patchFirstTopicLike(diagramStore, tslice)
      break
    default:
      patchFirstTopicLike(diagramStore, tslice)
  }
}
