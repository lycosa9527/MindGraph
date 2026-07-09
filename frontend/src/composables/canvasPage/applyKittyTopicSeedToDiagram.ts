import type { useDiagramStore } from '@/stores/diagram'
import type { DiagramType } from '@/types'

import type { KittyTopicSeed } from '@/composables/canvasPage/diagramTypeFromPrompt'

type DiagramPiniaStore = ReturnType<typeof useDiagramStore>

function patchTopicNode(store: DiagramPiniaStore, nodeId: string, text: string): boolean {
  const trimmed = text.trim()
  if (!trimmed || !store.data?.nodes.some((n) => n.id === nodeId)) {
    return false
  }
  return store.updateNode(nodeId, { text: trimmed })
}

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
 * Seeds center/topic nodes on a freshly loaded default template (Kitty navigation / type switch).
 */
export function applyKittyTopicSeedToDiagram(
  diagramType: DiagramType,
  seed: KittyTopicSeed,
  diagramStore: DiagramPiniaStore
): void {
  const topic = seed.topic?.trim() ?? ''
  const left = seed.left?.trim() ?? ''
  const right = seed.right?.trim() ?? ''
  if (!topic && !left && !right) return

  switch (diagramType) {
    case 'double_bubble_map': {
      if (left) patchTopicNode(diagramStore, 'left-topic', left)
      if (right) patchTopicNode(diagramStore, 'right-topic', right)
      if (topic && !left) patchTopicNode(diagramStore, 'left-topic', topic)
      break
    }
    case 'tree_map':
      if (!patchTopicNode(diagramStore, 'tree-topic', topic)) {
        patchFirstTopicLike(diagramStore, topic)
      }
      break
    case 'flow_map':
      if (!patchTopicNode(diagramStore, 'flow-topic', topic)) {
        patchFirstTopicLike(diagramStore, topic)
      }
      break
    case 'multi_flow_map':
      if (!patchTopicNode(diagramStore, 'event', topic)) {
        patchFirstTopicLike(diagramStore, topic)
      }
      break
    case 'brace_map':
      if (!patchTopicNode(diagramStore, 'brace-whole', topic)) {
        patchFirstTopicLike(diagramStore, topic)
      }
      break
    case 'bridge_map':
      patchTopicNode(diagramStore, 'dimension-label', topic)
      break
    case 'circle_map':
    case 'bubble_map':
    case 'mindmap':
    case 'mind_map':
    case 'concept_map':
      if (!patchTopicNode(diagramStore, 'topic', topic)) {
        patchFirstTopicLike(diagramStore, topic)
      }
      break
    default:
      patchFirstTopicLike(diagramStore, topic)
  }
}
