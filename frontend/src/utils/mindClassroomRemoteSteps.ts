/**
 * Map queued lecture steps onto the live canvas (drop missing focus ids).
 */
import type { MindClassroomRemoteStep } from '@/composables/mindMap/mindClassroomJobApi'
import {
  lectureCaptionDwellMs,
  type MindClassroomLectureStep,
} from '@/utils/mindClassroomScript'

export function collectLiveNodeIds(
  nodes: Array<{ id?: string }> | null | undefined
): Set<string> {
  const ids = new Set<string>()
  for (const node of nodes ?? []) {
    const id = typeof node.id === 'string' ? node.id.trim() : ''
    if (id) ids.add(id)
  }
  return ids
}

export function classroomJobFitsLiveNodes(
  raw: MindClassroomRemoteStep[] | null | undefined,
  liveIds: Set<string>
): boolean {
  if (!raw?.length) return true
  const refs: string[] = []
  for (const step of raw) {
    for (const id of step.focus_node_ids ?? []) {
      if (id) refs.push(id)
    }
    if (step.branch_node_id) refs.push(step.branch_node_id)
  }
  if (!refs.length) return true
  return refs.some((id) => liveIds.has(id))
}

export function mapRemoteLectureSteps(
  raw: MindClassroomRemoteStep[],
  liveIds: Set<string>
): MindClassroomLectureStep[] {
  return raw.map((step, index) => {
    const focus = (step.focus_node_ids ?? []).filter((id) => liveIds.has(id))
    const branch =
      step.branch_node_id && liveIds.has(step.branch_node_id) ? step.branch_node_id : undefined
    const caption = String(step.caption ?? '').trim()
    return {
      id: String(step.id || `step-${index}`),
      kind: step.kind === 'overview' || step.kind === 'closing' ? step.kind : 'branch',
      title: String(step.title || caption || '').trim() || `Step ${index + 1}`,
      caption,
      bullets: Array.isArray(step.bullets) ? step.bullets.map((item) => String(item)) : [],
      focusNodeIds: focus,
      branchNodeId: branch,
      dwellMs: lectureCaptionDwellMs(caption),
      themeIndex: index % 5,
      imageUrl: step.image_url || undefined,
    }
  })
}
