import {
  allocateOverlayStep,
  overlayMarkStep,
  visibleMarkOverlays,
} from '@/composables/training/trainingMarkSteps'
import type { TrainingPageKey } from '@/config/trainingPages'
import { TRAINING_ROLE_WIDTH_DEFAULT, isTrainingRoleId } from '@/config/trainingRoles'
import {
  TRAINING_TEXT_HEIGHT_DEFAULT,
  TRAINING_TEXT_SIZE_DEFAULT,
  TRAINING_TEXT_WIDTH_DEFAULT,
} from '@/config/trainingTextBubbles'
import { isTrainingModalForPage, trainingFocusOptions } from '@/config/trainingUiTargets'
import type { TrainingCourseStep, TrainingStepOverlay } from '@/types/training'

export function blankPageStep(position: number): TrainingCourseStep {
  return {
    position,
    type: 'page',
    page_key: 'mindgraph',
    pull_users: true,
    diagram_type: null,
    topic_options: [],
    overlays: [],
    notes: '',
    mark_step: 1,
    mark_steps: 1,
  }
}

export function blankSlideStep(position: number): TrainingCourseStep {
  return {
    position,
    type: 'slide',
    page_key: null,
    pull_users: true,
    diagram_type: null,
    topic_options: [],
    overlays: [],
    notes: '',
    mark_step: 1,
    mark_steps: 1,
  }
}

export function insertStepsAt(
  steps: TrainingCourseStep[],
  index: number,
  incoming: TrainingCourseStep[]
): number {
  if (!incoming.length) return index
  const at = Math.max(0, Math.min(index, steps.length))
  steps.splice(at, 0, ...incoming)
  for (let position = 0; position < steps.length; position += 1) {
    steps[position].position = position
  }
  return at
}

export function pruneTrainingFocus(step: TrainingCourseStep): void {
  if (step.modal_key && !isTrainingModalForPage(step.page_key, step.modal_key)) {
    step.modal_key = null
  }
  const options = trainingFocusOptions(step.page_key, step.modal_key)
  if (step.focus_key && !options.some((item) => item.key === step.focus_key)) {
    step.focus_key = null
  }
}

export function applyPageKey(step: TrainingCourseStep, key: TrainingPageKey): void {
  step.page_key = key
  if (key === 'canvas') {
    step.type = 'canvas'
    step.diagram_type = step.diagram_type || 'double_bubble_map'
  } else if (step.type === 'canvas') {
    step.type = 'page'
    step.diagram_type = null
  }
  pruneTrainingFocus(step)
}

export function applyModalKey(step: TrainingCourseStep, key: string | null): void {
  step.modal_key = key || null
  pruneTrainingFocus(step)
}

export function applyFocusKey(step: TrainingCourseStep, key: string | null): void {
  step.focus_key = key || null
}

export function canvasDiagramTypeFromFocusKey(key: string): string | null {
  if (!key.startsWith('diagram-')) return null
  const type = key.slice('diagram-'.length)
  return type === 'mind_map' ? 'mindmap' : type
}

export function applyDiagramCardStep(step: TrainingCourseStep, focusKey: string): boolean {
  const type = canvasDiagramTypeFromFocusKey(focusKey)
  if (!type) return false
  applyPageKey(step, 'canvas')
  step.diagram_type = type
  return true
}

export function addOverlay(
  step: TrainingCourseStep,
  kind: TrainingStepOverlay['kind'],
  extra: Partial<TrainingStepOverlay> = {}
): void {
  const overlays = step.overlays || []
  if (kind === 'topics') {
    placeTopicsOverlay(step, extra)
    return
  }
  const at = extra.step ?? allocateOverlayStep(step)
  if (kind === 'arrow') {
    overlays.push({
      ...extra,
      kind: 'arrow',
      x: extra.x ?? 20,
      y: extra.y ?? 24,
      x2: extra.x2 ?? 72,
      y2: extra.y2 ?? 68,
      color: extra.color || 'red',
      line: extra.line || 'solid',
      step: at,
    })
  } else if (kind === 'emoji') {
    overlays.push({
      kind: 'emoji',
      x: 50,
      y: 48,
      glyph: extra.glyph || '⭐',
      ...extra,
      step: at,
    })
  } else if (kind === 'spotlight') {
    overlays.push({
      ...extra,
      kind: 'spotlight',
      x: extra.x ?? 50,
      y: extra.y ?? 50,
      r: extra.r ?? 1,
      shape: extra.shape ?? 'circle',
      step: at,
    })
  } else if (kind === 'role') {
    const roleId = extra.role || extra.glyph || ''
    overlays.push({
      ...extra,
      kind: 'role',
      x: extra.x ?? 82,
      y: extra.y ?? 74,
      w: extra.w ?? TRAINING_ROLE_WIDTH_DEFAULT,
      role: isTrainingRoleId(roleId) ? roleId : '01-look-here',
      step: at,
    })
  } else {
    overlays.push({
      ...extra,
      kind: 'text',
      x: extra.x ?? 50,
      y: extra.y ?? 42,
      w: extra.w ?? TRAINING_TEXT_WIDTH_DEFAULT,
      h: extra.h ?? TRAINING_TEXT_HEIGHT_DEFAULT,
      size: extra.size ?? TRAINING_TEXT_SIZE_DEFAULT,
      text: extra.text || '',
      step: at,
    })
  }
  step.overlays = overlays
}

function placeTopicsOverlay(step: TrainingCourseStep, extra: Partial<TrainingStepOverlay>): void {
  const overlays = step.overlays || []
  const keep = overlays.find((row) => row.kind === 'topics')
  const at = extra.step ?? (keep ? overlayMarkStep(keep) : allocateOverlayStep(step))
  step.overlays = overlays.filter((row) => row.kind !== 'topics')
  step.overlays.push({
    ...keep,
    ...extra,
    kind: 'topics',
    x: extra.x ?? keep?.x ?? 50,
    y: extra.y ?? keep?.y ?? 50,
    step: at,
  })
}

export function selectedIndexAfterRemove(
  selected: number,
  removed: number,
  lengthAfter: number
): number {
  if (lengthAfter <= 0) return 0
  if (selected > removed) return selected - 1
  if (selected >= lengthAfter) return lengthAfter - 1
  return selected
}

export function stepSpotlight(step: TrainingCourseStep): TrainingStepOverlay | undefined {
  return visibleMarkOverlays(step).find((overlay) => overlay.kind === 'spotlight')
}

export function trainingCourseWriteBody(
  title: string,
  description: string,
  steps: TrainingCourseStep[],
  status = 'ready'
): {
  title: string
  description: string
  status: string
  steps: TrainingCourseStep[]
} {
  return {
    title,
    description,
    status,
    steps: steps.map((step, index) => {
      const next = { ...step, position: index }
      const overlays = next.overlays || []
      let lastTopics = -1
      for (let i = 0; i < overlays.length; i += 1) {
        if (overlays[i].kind === 'topics') lastTopics = i
      }
      if (lastTopics >= 0) {
        next.overlays = overlays.filter(
          (row, rowIndex) => row.kind !== 'topics' || rowIndex === lastTopics
        )
      }
      delete next.asset_url
      delete next.thumb_url
      return next
    }),
  }
}
