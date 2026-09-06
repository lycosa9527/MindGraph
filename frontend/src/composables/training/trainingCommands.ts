/**
 * Training UI → engine commands. Pinia holds state; the session engine listens.
 */
import { eventBus } from '@/composables/core/useEventBus'
import type { TrainingTopicOption } from '@/types/training'

export function requestTrainingStart(): void {
  eventBus.emit('training:start_requested', {})
}

export function requestTrainingPlay(courseId: string): void {
  eventBus.emit('training:play_requested', { courseId })
}

export function requestTrainingPause(): void {
  eventBus.emit('training:pause_requested', {})
}

export function requestTrainingResume(): void {
  eventBus.emit('training:resume_requested', {})
}

export function requestTrainingEnd(confirmed = false): void {
  eventBus.emit('training:end_requested', { confirmed })
}

export function requestTrainingTakeover(): void {
  eventBus.emit('training:takeover_requested', {})
}

export function requestTrainingStep(delta: number): void {
  eventBus.emit('training:step_requested', { delta })
}

export function requestTrainingFree(free?: boolean): void {
  eventBus.emit('training:free_requested', { free })
}

export function requestTrainingSelectOrg(orgId: number | null): void {
  eventBus.emit('training:select_org_requested', { orgId })
}

export function requestTrainingSearchOrgs(query: string): void {
  eventBus.emit('training:search_orgs_requested', { query })
}

export function requestTrainingChipSelected(option: TrainingTopicOption): void {
  eventBus.emit('training:chip_selected', { option })
}

export function requestTrainingTopicApply(option: TrainingTopicOption): void {
  eventBus.emit('training:topic_apply_requested', { option })
}

export function requestTrainingModalOpen(key: string): void {
  if (key === 'export-community') {
    eventBus.emit('toolbar:export_requested', { format: 'community' })
    return
  }
  eventBus.emit('training:modal_open_requested', { key })
}

export function requestTrainingModalsClose(): void {
  eventBus.emit('training:modal_close_requested', {})
}

export function requestTrainingRosterInvalidate(): void {
  eventBus.emit('training:roster_invalidate', {})
}
