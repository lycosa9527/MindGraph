/**
 * 思维讲堂 UI → engine commands. Pinia holds state; the lecture engine listens.
 */
import { eventBus } from '@/composables/core/useEventBus'

export function requestClassroomStart(reuse = true): void {
  eventBus.emit('classroom:start_requested', { reuse })
}

export function requestClassroomRestart(): void {
  eventBus.emit('classroom:restart_requested', {})
}

export function requestClassroomStop(restoreViewport = true): void {
  eventBus.emit('classroom:stop_requested', { restoreViewport })
}

export function requestClassroomTogglePause(): void {
  eventBus.emit('classroom:toggle_pause_requested', {})
}

export function requestClassroomNext(): void {
  eventBus.emit('classroom:next_requested', {})
}

export function requestClassroomPrev(): void {
  eventBus.emit('classroom:prev_requested', {})
}

export function requestClassroomSetVoice(enabled: boolean): void {
  eventBus.emit('classroom:set_voice_requested', { enabled })
}

export function requestClassroomRestorePrepared(): void {
  eventBus.emit('classroom:restore_prepared_requested', {})
}
