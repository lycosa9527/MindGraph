/**
 * Map queued lecture steps onto the live canvas (drop missing focus ids).
 */
import type { MindClassroomJobDetail, MindClassroomRemoteStep } from '@/composables/mindMap/mindClassroomJobApi'
import type { DiagramNode } from '@/types'
import { classroomPrepFitsLiveView } from '@/utils/mindClassroomPrepSlot'
import {
  lectureCaptionDwellMs,
  type MindClassroomLectureStep,
} from '@/utils/mindClassroomScript'
import { resolveMindMapIdentityId } from '@/utils/mindMapIdentityMigrate'

export type LectureLiveRef =
  | Set<string>
  | ReadonlyArray<{ id?: string; data?: Record<string, unknown> | null }>

export function collectLiveNodeIds(
  nodes: ReadonlyArray<{ id?: string }> | null | undefined
): Set<string> {
  const ids = new Set<string>()
  for (const node of nodes ?? []) {
    const id = typeof node.id === 'string' ? node.id.trim() : ''
    if (id) ids.add(id)
  }
  return ids
}

export function resolveLectureLiveId(
  hint: string | null | undefined,
  live: LectureLiveRef
): string | null {
  if (!hint?.trim()) return null
  const cleaned = hint.trim()
  if (live instanceof Set) {
    return live.has(cleaned) ? cleaned : null
  }
  return resolveMindMapIdentityId(cleaned, live as DiagramNode[])
}

function remapIdList(ids: readonly string[] | null | undefined, live: LectureLiveRef): string[] {
  const out: string[] = []
  const seen = new Set<string>()
  for (const id of ids ?? []) {
    const liveId = resolveLectureLiveId(id, live)
    if (liveId && !seen.has(liveId)) {
      seen.add(liveId)
      out.push(liveId)
    }
  }
  return out
}


export function lectureStepNodeIds(
  raw: MindClassroomRemoteStep[] | null | undefined
): string[] {
  const refs: string[] = []
  for (const step of raw ?? []) {
    for (const id of step.focus_node_ids ?? []) {
      if (id) refs.push(id)
    }
    if (step.branch_node_id) refs.push(step.branch_node_id)
  }
  return refs
}

export function lectureStepsBindLive(
  raw: MindClassroomRemoteStep[] | null | undefined,
  live: LectureLiveRef
): boolean {
  const refs = lectureStepNodeIds(raw)
  if (!refs.length) return false
  return refs.some((id) => resolveLectureLiveId(id, live) != null)
}

export function classroomJobFitsLiveNodes(
  raw: MindClassroomRemoteStep[] | null | undefined,
  live: LectureLiveRef
): boolean {
  if (!raw?.length) return true
  const refs = lectureStepNodeIds(raw)
  if (!refs.length) return true
  return refs.some((id) => resolveLectureLiveId(id, live) != null)
}

export function remapPreparedStepsToLive(
  steps: readonly MindClassroomLectureStep[],
  live: LectureLiveRef
): MindClassroomLectureStep[] {
  return steps
    .filter((step) => step.caption.trim())
    .map((step) => ({
      ...step,
      focusNodeIds: remapIdList(step.focusNodeIds, live),
      branchNodeId: resolveLectureLiveId(step.branchNodeId, live) ?? undefined,
    }))
}

export function preparedLectureFitsLive(
  steps: readonly MindClassroomLectureStep[],
  live: LectureLiveRef,
  specNodeIds?: readonly string[] | null
): boolean {
  if (specNodeIds?.length && !classroomPrepFitsLiveView(specNodeIds, live)) {
    return false
  }
  const remapped = remapPreparedStepsToLive(steps, live)
  if (!remapped.some((step) => step.caption.trim())) return false
  const hadFocus = steps.some((step) => step.focusNodeIds.length > 0 || Boolean(step.branchNodeId))
  if (!hadFocus) return true
  return remapped.some((step) => step.focusNodeIds.length > 0 || Boolean(step.branchNodeId))
}

export function classroomReadyJobIsUsable(
  detail: Pick<MindClassroomJobDetail, 'result_json' | 'spec_node_ids'>,
  live: LectureLiveRef
): boolean {
  const result = detail.result_json
  if (!result || result.transcript_replaced === true) return false
  const raw = result.steps ?? []
  if (!raw.some((step) => String(step.caption ?? '').trim())) return false
  if (!classroomJobFitsLiveNodes(raw, live)) return false
  const specIds = detail.spec_node_ids
  if (!specIds?.length) return true
  if (classroomPrepFitsLiveView(specIds, live)) return true
  return lectureStepsBindLive(raw, live)
}

export function mapRemoteLectureSteps(
  raw: MindClassroomRemoteStep[],
  live: LectureLiveRef
): MindClassroomLectureStep[] {
  return raw.map((step, index) => {
    const caption = String(step.caption ?? '').trim()
    return {
      id: String(step.id || `step-${index}`),
      kind: step.kind === 'overview' || step.kind === 'closing' ? step.kind : 'branch',
      title: String(step.title || caption || '').trim() || `Step ${index + 1}`,
      caption,
      bullets: Array.isArray(step.bullets) ? step.bullets.map((item) => String(item)) : [],
      focusNodeIds: remapIdList(step.focus_node_ids, live),
      branchNodeId: resolveLectureLiveId(step.branch_node_id, live) ?? undefined,
      dwellMs: lectureCaptionDwellMs(caption),
      themeIndex: index % 5,
      imageUrl: step.image_url || undefined,
    }
  })
}
