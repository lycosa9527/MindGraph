import type { Router } from 'vue-router'

import { VALID_DIAGRAM_TYPES } from '@/composables/canvasPage/diagramTypeMaps'
import { trainingPagePath } from '@/config/trainingPages'
import type { DiagramType } from '@/types'
import type { TrainingCourseStep, TrainingSnapshot, TrainingTopicOption } from '@/types/training'
import { canvasEditorPathForRoute } from '@/utils/canvasBackNavigation'

export function shouldAcceptTrainingSnapshot(
  current: TrainingSnapshot,
  next: TrainingSnapshot
): boolean {
  if (next.state === 'none') return true
  if (next.session_id && next.session_id === current.session_id) {
    return next.seq >= current.seq
  }
  if (
    (current.state === 'live' || current.state === 'paused') &&
    next.state === 'ended' &&
    Boolean(next.session_id) &&
    next.session_id !== current.session_id
  ) {
    return false
  }
  return true
}

export function trainingFollowCursorResets(
  current: TrainingSnapshot,
  next: TrainingSnapshot
): boolean {
  return (
    next.session_id !== current.session_id || next.state === 'none' || next.state === 'ended'
  )
}

export function canSeeTrainingSpeakerNotes(
  snapshot: TrainingSnapshot,
  userId: number | null | undefined
): boolean {
  if (snapshot.state !== 'live' && snapshot.state !== 'paused') return false
  if (userId == null || snapshot.instructor_id == null) return false
  return Number(snapshot.instructor_id) === Number(userId)
}

export function isMediaTrainingStep(snapshot: TrainingSnapshot): boolean {
  const stepType = snapshot.step?.type
  return stepType === 'slide' || stepType === 'video'
}

export function isTrainingRoomArmed(snapshot: TrainingSnapshot): boolean {
  if (snapshot.state !== 'live' && snapshot.state !== 'paused') return false
  return !snapshot.course_id
}

export function teachersSeeTrainingBanner(snapshot: TrainingSnapshot): boolean {
  if (snapshot.state !== 'live' && snapshot.state !== 'paused') return false
  return Boolean(snapshot.course_id)
}

export type TrainingSteerMode = 'free' | 'pull'

export function trainingSteerMode(snapshot: TrainingSnapshot): TrainingSteerMode {
  return snapshot.pull_users === false ? 'free' : 'pull'
}

export function liveLessonStep(
  snapshot: TrainingSnapshot,
  opts: { skip?: boolean; trainingRoute?: boolean }
): TrainingCourseStep | null {
  if (opts.skip || opts.trainingRoute) return null
  if (snapshot.state !== 'live' && snapshot.state !== 'paused') return null
  if (snapshot.pull_users === false) return null
  return snapshot.step ?? null
}

export function liveLessonCoversMedia(step: TrainingCourseStep | null | undefined): boolean {
  if (!step?.asset_url) return false
  return step.type === 'slide' || step.type === 'video'
}

export function stepPullsUsers(snapshot: TrainingSnapshot): boolean {
  if (snapshot.pull_users === false) return false
  const step = snapshot.step
  if (step?.type === 'slide' || step?.type === 'video') return false
  if (step?.page_key) return true
  return Boolean(snapshot.diagram_type || step?.diagram_type)
}

export function shouldBypassTrainingLeaveConfirm(state: TrainingSnapshot['state']): boolean {
  return state === 'live' || state === 'paused' || state === 'ended'
}

export function shouldForceNavigate(snapshot: TrainingSnapshot, lastAppliedSeq: number): boolean {
  if (snapshot.state !== 'live' || snapshot.seq <= lastAppliedSeq) {
    return false
  }
  if (!stepPullsUsers(snapshot)) {
    return false
  }
  if (snapshot.step?.page_key) {
    return true
  }
  return Boolean(snapshot.diagram_type)
}

export function trainingCanvasLocation(
  routePath: string,
  diagramType: string
): { path: '/canvas' | '/m/canvas'; query: { type: string } } | null {
  const typeKey = diagramType === 'mind_map' ? 'mindmap' : diagramType
  if (!VALID_DIAGRAM_TYPES.includes(typeKey as DiagramType)) {
    return null
  }
  return {
    path: canvasEditorPathForRoute(routePath),
    query: { type: typeKey },
  }
}

export function trainingStepLocation(
  routePath: string,
  snapshot: TrainingSnapshot
): { path: string; query?: Record<string, string> } | null {
  const pageKey = snapshot.step?.page_key
  const diagramType = snapshot.diagram_type || snapshot.step?.diagram_type || ''
  if (pageKey === 'canvas' || (!pageKey && diagramType)) {
    return trainingCanvasLocation(routePath, diagramType)
  }
  const path = trainingPagePath(routePath, pageKey)
  if (!path) return null
  if (pageKey === 'auth') {
    return { path, query: { training: '1' } }
  }
  return { path }
}

function sameTrainingQuery(
  currentQuery: Record<string, unknown>,
  targetQuery?: Record<string, string>
): boolean {
  if (!targetQuery) return true
  return Object.entries(targetQuery).every(
    ([key, value]) => String(currentQuery[key] || '') === value
  )
}

export async function applyTrainingNavigate(
  router: Router,
  routePath: string,
  snapshot: TrainingSnapshot
): Promise<boolean> {
  if (snapshot.state !== 'live') return false
  const target = trainingStepLocation(routePath, snapshot)
  if (!target) return false
  const current = router.currentRoute.value
  const samePath = current.path === target.path
  if (samePath && sameTrainingQuery(current.query, target.query)) {
    return true
  }
  await router.push(target)
  return true
}

export function chipTopicOverride(option: TrainingTopicOption): string {
  const left = (option.item_a || '').trim()
  const right = (option.item_b || '').trim()
  if (left && right) {
    return `${left} vs ${right}`
  }
  return (option.prompt || option.label || '').trim()
}
