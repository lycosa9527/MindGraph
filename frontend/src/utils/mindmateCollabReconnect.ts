/**
 * Pure reconnect helpers for MindMate collab WebSocket client.
 */

export const MINDMATE_COLLAB_RECONNECT = {
  MAX_ATTEMPTS: 5,
  BASE_DELAY_MS: 1000,
  MAX_DELAY_MS: 30000,
  JITTER_MS: 1000,
  NO_RECONNECT_CLOSE_CODES: new Set<number>([
    1000,
    1008,
    4003,
    4010,
    4011,
    4029,
  ]),
} as const

export function computeMindmateCollabReconnectDelayMs(attempt: number): number {
  if (attempt < 0) {
    return MINDMATE_COLLAB_RECONNECT.BASE_DELAY_MS
  }
  const raw = MINDMATE_COLLAB_RECONNECT.BASE_DELAY_MS * Math.pow(2, attempt)
  return Math.min(MINDMATE_COLLAB_RECONNECT.MAX_DELAY_MS, raw)
}

export function shouldScheduleMindmateCollabReconnect(attempts: number, closeCode: number): boolean {
  if (attempts >= MINDMATE_COLLAB_RECONNECT.MAX_ATTEMPTS) {
    return false
  }
  if (MINDMATE_COLLAB_RECONNECT.NO_RECONNECT_CLOSE_CODES.has(closeCode)) {
    return false
  }
  return true
}

export function mindmateCollabPermanentFailureLocaleKey(
  closeCode: number,
  reason: string,
): string | null {
  if (closeCode === 4029) {
    return 'mindmate.collabConnectionLimit'
  }
  if (closeCode !== 1008) {
    return null
  }
  const normalized = reason.trim().toLowerCase()
  if (
    normalized.includes('unauthorized')
    || normalized.includes('invalid token')
    || normalized.includes('authentication')
    || normalized.includes('no authentication')
  ) {
    return 'mindmate.collabConnectionAuthFailed'
  }
  if (
    normalized.includes('invalid room')
    || normalized.includes('access denied')
    || normalized.includes('room closing')
    || normalized.includes('feature')
  ) {
    return 'mindmate.collabConnectionDenied'
  }
  return 'mindmate.collabConnectionDenied'
}
