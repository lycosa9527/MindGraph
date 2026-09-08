import { trainingPageDef, trainingPageKeyFromPath } from '@/config/trainingPages'
import type { TrainingRosterRow, TrainingSnapshot } from '@/types/training'

export const TRAINING_FRIEND_EMPTY = '—'

export function trainingActivityPageKey(
  routePath: string,
  snapshot: TrainingSnapshot
): string | null {
  const pulled = snapshot.pull_users !== false
  const step = snapshot.step
  if (pulled && step) {
    if (step.type === 'slide' || step.type === 'video') return step.type
    if (step.page_key) return step.page_key
  }
  return trainingPageKeyFromPath(routePath)
}

export function trainingFriendPageKey(row: TrainingRosterRow): string | null {
  const key = row.page_key?.trim()
  return key || null
}

export function trainingFriendTopic(row: TrainingRosterRow): string {
  const topic = row.option_label?.trim()
  return topic || TRAINING_FRIEND_EMPTY
}

export function trainingFriendName(row: TrainingRosterRow): string {
  const name = row.name?.trim()
  return name || String(row.user_id)
}

export function trainingFriendPageLabel(
  row: TrainingRosterRow,
  translate: (key: string) => string
): string {
  const key = trainingFriendPageKey(row)
  if (key === 'slide') return translate('training.pageSlide')
  if (key === 'video') return translate('training.pageVideo')
  const page = trainingPageDef(key)
  if (page) return translate(page.labelKey)
  return TRAINING_FRIEND_EMPTY
}

export function trainingFriendLine(
  row: TrainingRosterRow,
  translate: (key: string) => string
): string {
  return `${trainingFriendName(row)} / ${trainingFriendPageLabel(row, translate)} / ${trainingFriendTopic(row)}`
}

export function trainingFriendJumpSnapshot(
  snapshot: TrainingSnapshot,
  row: TrainingRosterRow
): TrainingSnapshot | null {
  const pageKey = trainingFriendPageKey(row)
  const type = row.diagram_type || snapshot.diagram_type || null
  if (pageKey === 'slide' || pageKey === 'video') return null
  if (!pageKey && !type) return null
  return {
    ...snapshot,
    diagram_type: type,
    step: pageKey
      ? { position: snapshot.step?.position ?? 0, type: 'page', page_key: pageKey }
      : snapshot.step,
  }
}
