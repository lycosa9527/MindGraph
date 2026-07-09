/**
 * Applies optional ``kitty_*`` URL query hints after ``loadDefaultTemplate`` (mobile Kitty → desktop navigation).
 */
import type { RouteLocationNormalizedLoaded } from 'vue-router'

import { applyKittyTopicSeedToDiagram } from '@/composables/canvasPage/applyKittyTopicSeedToDiagram'
import { useDiagramStore } from '@/stores'
import type { DiagramType } from '@/types'

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

  applyKittyTopicSeedToDiagram(
    diagramType,
    {
      topic: topic?.slice(0, 480),
      left: left?.slice(0, 240),
      right: right?.slice(0, 240),
    },
    diagramStore
  )
}
