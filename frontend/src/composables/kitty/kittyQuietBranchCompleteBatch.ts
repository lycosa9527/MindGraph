/**
 * Coalesce Kitty quiet branch-auto-complete finishes into one short chat reply
 * (no dump of generated child texts; no per-branch spam).
 */
import { eventBus } from '@/composables/core/useEventBus'
import { i18n } from '@/i18n'

let inflight = 0
let successCount = 0
let failureCount = 0
let flushTimer: ReturnType<typeof setTimeout> | null = null

function t(key: string): string {
  return i18n.global.t(key) as string
}

function clearFlushTimer(): void {
  if (flushTimer != null) {
    clearTimeout(flushTimer)
    flushTimer = null
  }
}

function resetBatch(): void {
  inflight = 0
  successCount = 0
  failureCount = 0
  clearFlushTimer()
}

function buildDoneSummary(): string {
  if (successCount > 0 && failureCount > 0) {
    return t('canvas.mindMapOneSentence.kittyBranchesCompletePartial')
  }
  if (failureCount > 0 && successCount === 0) {
    return t('canvas.mindMapOneSentence.kittyEditBranchCompleteFailed')
  }
  if (successCount > 1) {
    return t('canvas.mindMapOneSentence.kittyBranchesCompleteDone')
  }
  return t('canvas.mindMapOneSentence.kittyBranchCompleteDone')
}

function scheduleFlush(): void {
  clearFlushTimer()
  flushTimer = setTimeout(flushBatchReply, 40)
}

function flushBatchReply(): void {
  flushTimer = null
  if (inflight > 0) {
    return
  }
  if (successCount === 0 && failureCount === 0) {
    return
  }
  const ok = successCount > 0
  const userSummary = buildDoneSummary()
  const errorCode = ok ? undefined : 'branch_complete_failed'
  successCount = 0
  failureCount = 0
  eventBus.emit('kitty:diagram_action_completed', {
    action: 'auto_complete_branch',
    ok,
    userSummary,
    ...(errorCode ? { errorCode } : {}),
  })
}

/** Call when a Kitty quiet branch-complete job starts. */
export function beginQuietBranchComplete(): void {
  inflight += 1
  clearFlushTimer()
}

/**
 * Call when a Kitty quiet branch-complete job ends.
 * When the wave finishes, emits one short chat summary (not the fill content).
 */
export function endQuietBranchComplete(ok: boolean): void {
  inflight = Math.max(0, inflight - 1)
  if (ok) {
    successCount += 1
  } else {
    failureCount += 1
  }
  if (inflight > 0) {
    return
  }
  scheduleFlush()
}

/** Abort/cancel: drop from the wave without counting success or failure. */
export function cancelQuietBranchComplete(): void {
  inflight = Math.max(0, inflight - 1)
  if (inflight > 0) {
    return
  }
  if (successCount > 0 || failureCount > 0) {
    scheduleFlush()
    return
  }
  clearFlushTimer()
}

/** Test helper. */
export function resetQuietBranchCompleteBatchForTests(): void {
  resetBatch()
}
