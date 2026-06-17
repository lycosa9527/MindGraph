import { isPlaceholderText } from '@/composables/editor/useAutoComplete'
import type { DiagramNode } from '@/types'

export interface MindMapWaterfallSource {
  id: string
  name: string
  stage: 'branches' | 'children'
  stageData?: Record<string, unknown>
}

function nodeLabel(node: DiagramNode | undefined): string {
  const text = (node?.text ?? '').trim()
  if (!text || isPlaceholderText(text)) return ''
  return text
}

/** Resolve canvas selection into waterfall generation sources (topic + branches). */
export function resolveMindMapWaterfallSources(
  selectedNodeIds: string[],
  nodes: DiagramNode[]
): MindMapWaterfallSource[] {
  const topicNode = nodes.find((n) => n.id === 'topic')
  const topicLabel = nodeLabel(topicNode) || '…'

  const eligibleIds =
    selectedNodeIds.length > 0
      ? selectedNodeIds.filter((id) => id === 'topic' || id.startsWith('branch-'))
      : ['topic']

  const seen = new Set<string>()
  const sources: MindMapWaterfallSource[] = []

  for (const id of eligibleIds) {
    if (seen.has(id)) continue
    seen.add(id)

    if (id === 'topic') {
      sources.push({ id: 'topic', name: topicLabel, stage: 'branches' })
      continue
    }

    const node = nodes.find((n) => n.id === id)
    const name = nodeLabel(node)
    if (!name) continue
    sources.push({
      id,
      name,
      stage: 'children',
      stageData: { branch_id: id, branch_name: name },
    })
  }

  if (sources.length === 0) {
    sources.push({ id: 'topic', name: topicLabel, stage: 'branches' })
  }

  return sources
}

export function tabLabel(name: string, max = 10): string {
  const t = name.trim()
  if (t.length <= max) return t
  return `${t.slice(0, max - 1)}…`
}
