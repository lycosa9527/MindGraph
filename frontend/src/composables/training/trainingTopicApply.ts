import type { TrainingTopicOption } from '@/types/training'

export type TrainingTopicDiagramTarget = {
  data?: { nodes?: Array<{ id: string; type?: string }> } | null
  updateNode: (nodeId: string, updates: { text: string }) => boolean
}

type TopicApplier = (option: TrainingTopicOption) => void

const appliers: TopicApplier[] = []

export function registerTrainingTopicApplier(apply: TopicApplier): () => void {
  appliers.push(apply)
  return () => {
    const index = appliers.lastIndexOf(apply)
    if (index >= 0) appliers.splice(index, 1)
  }
}

export function applyRegisteredTrainingTopic(option: TrainingTopicOption): void {
  const apply = appliers[appliers.length - 1]
  apply?.(option)
}

export function applyTrainingTopicToDiagram(
  session: TrainingTopicDiagramTarget,
  option: TrainingTopicOption
): void {
  const left = (option.item_a || '').trim()
  const right = (option.item_b || '').trim()
  if (left) session.updateNode('left-topic', { text: left })
  if (right) session.updateNode('right-topic', { text: right })
  if (left || right) return
  const topic = (option.prompt || option.label || '').trim()
  if (!topic) return
  if (session.updateNode('topic', { text: topic })) return
  const nodes = session.data?.nodes || []
  const hit =
    nodes.find((node) => node.type === 'topic' || node.type === 'center') ||
    nodes.find((node) => node.id.endsWith('-topic') || node.id === 'event')
  if (hit) session.updateNode(hit.id, { text: topic })
}
