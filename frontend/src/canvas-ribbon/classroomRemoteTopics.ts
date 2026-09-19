import { applyKittyTopicSeedToDiagram } from '@/composables/canvasPage/applyKittyTopicSeedToDiagram'
import type { useDiagramStore } from '@/stores/diagram'

export const CLASSROOM_REMOTE_TOPICS_STORAGE_KEY = 'mg.classroom-remote-topics.v1'
export const CLASSROOM_REMOTE_TOPIC_MAX_LEN = 64
export const CLASSROOM_REMOTE_TOPICS_MAX = 20
export const CLASSROOM_REMOTE_VS_SEPARATOR = ' vs '

/** Split `left vs right` (case-insensitive, optional dots/spaces). */
const CLASSROOM_REMOTE_VS_SPLIT = /\s*vs\.?\s+/i

/** Offline ClassIn demo starters — teachers can rewrite this list. */
export const DEFAULT_CLASSROOM_REMOTE_TOPICS = [
  '光合作用',
  '水循环',
  '牛顿三大定律',
  '植物细胞 vs 动物细胞',
  '一元二次方程',
  '唐朝',
] as const

type DiagramPiniaStore = ReturnType<typeof useDiagramStore>

export function normalizeClassroomRemoteTopic(value: unknown): string {
  if (typeof value !== 'string') {
    return ''
  }
  return value.replace(/\s+/g, ' ').trim().slice(0, CLASSROOM_REMOTE_TOPIC_MAX_LEN)
}

export function parseClassroomRemoteTopics(raw: string | null | undefined): string[] | null {
  if (typeof raw !== 'string' || raw.length === 0) {
    return null
  }
  try {
    const parsed = JSON.parse(raw) as unknown
    if (!Array.isArray(parsed)) {
      return null
    }
    const topics = parsed
      .map((item) => normalizeClassroomRemoteTopic(item))
      .filter((item) => item.length > 0)
      .slice(0, CLASSROOM_REMOTE_TOPICS_MAX)
    return topics
  } catch {
    return null
  }
}

export function readClassroomRemoteTopics(): string[] {
  if (typeof localStorage === 'undefined') {
    return [...DEFAULT_CLASSROOM_REMOTE_TOPICS]
  }
  try {
    const stored = parseClassroomRemoteTopics(
      localStorage.getItem(CLASSROOM_REMOTE_TOPICS_STORAGE_KEY)
    )
    return stored ?? [...DEFAULT_CLASSROOM_REMOTE_TOPICS]
  } catch {
    return [...DEFAULT_CLASSROOM_REMOTE_TOPICS]
  }
}

export function writeClassroomRemoteTopics(topics: string[]): void {
  if (typeof localStorage === 'undefined') {
    return
  }
  try {
    localStorage.setItem(CLASSROOM_REMOTE_TOPICS_STORAGE_KEY, JSON.stringify(topics))
  } catch {
    /* quota / private mode */
  }
}

export function splitClassroomRemoteVsTopic(topic: string): { left: string; right: string } | null {
  const trimmed = normalizeClassroomRemoteTopic(topic)
  if (!trimmed) {
    return null
  }
  const parts = trimmed
    .split(CLASSROOM_REMOTE_VS_SPLIT)
    .map((part) => part.trim())
    .filter((part) => part.length > 0)
  if (parts.length < 2) {
    return null
  }
  return { left: parts[0], right: parts.slice(1).join(CLASSROOM_REMOTE_VS_SEPARATOR) }
}

export function formatClassroomRemoteVsTopic(left: string, right: string): string {
  const a = normalizeClassroomRemoteTopic(left)
  const b = normalizeClassroomRemoteTopic(right)
  if (!a || !b) {
    return a || b
  }
  return `${a}${CLASSROOM_REMOTE_VS_SEPARATOR}${b}`
}

export function applyClassroomRemoteTopic(diagramStore: DiagramPiniaStore, topic: string): boolean {
  const trimmed = normalizeClassroomRemoteTopic(topic)
  const diagramType = diagramStore.type
  if (!trimmed || !diagramType || !diagramStore.data?.nodes?.length) {
    return false
  }
  const pair = splitClassroomRemoteVsTopic(trimmed)
  const isDoubleBubble = diagramType === 'double_bubble_map'
  if (isDoubleBubble && pair) {
    applyKittyTopicSeedToDiagram(diagramType, { left: pair.left, right: pair.right }, diagramStore)
  } else {
    applyKittyTopicSeedToDiagram(diagramType, { topic: trimmed }, diagramStore)
  }
  return (
    readDiagramCenterTopic(diagramStore) ===
    (isDoubleBubble && pair ? formatClassroomRemoteVsTopic(pair.left, pair.right) : trimmed)
  )
}

export function readDiagramCenterTopic(diagramStore: DiagramPiniaStore): string {
  const nodes = diagramStore.data?.nodes ?? []
  if (diagramStore.type === 'double_bubble_map') {
    const left = nodes.find((node) => node.id === 'left-topic')?.text ?? ''
    const right = nodes.find((node) => node.id === 'right-topic')?.text ?? ''
    return formatClassroomRemoteVsTopic(left, right)
  }
  const hit =
    nodes.find((node) => node.id === 'topic') ??
    nodes.find((node) => node.type === 'topic' || node.type === 'center')
  return (hit?.text ?? '').trim()
}
