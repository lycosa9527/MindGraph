/**
 * MindMate collab WebSocket error codes → i18n keys and disconnect policy.
 */

export type MindmateCollabConnectionStatus =
  | 'idle'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'failed'

export const MINDMATE_COLLAB_MAX_WS_RECONNECT = 5

/** Locale key for a server `type: error` frame `code` field. */
export function mindmateCollabWsErrorLocaleKey(errorCode: string): string | null {
  switch (errorCode) {
    case 'room_closed':
      return 'mindmate.collabErrorRoomClosed'
    case 'rate_limit':
      return 'mindmate.collabErrorRateLimit'
    case 'content_too_long':
      return 'mindmate.collabErrorContentTooLong'
    case 'message_too_large':
      return 'mindmate.collabErrorMessageTooLarge'
    case 'dify_error':
      return 'mindmate.collabErrorDify'
    case 'invalid_payload':
      return 'mindmate.collabErrorInvalidPayload'
    case 'mindmate_responding':
      return 'mindmate.collabMindmateResponding'
    default:
      return null
  }
}

/** Error codes where the optimistic user message was not persisted. */
export function mindmateCollabWsErrorRollsBackSend(errorCode: string): boolean {
  return (
    errorCode === 'room_closed'
    || errorCode === 'rate_limit'
    || errorCode === 'content_too_long'
    || errorCode === 'message_too_large'
    || errorCode === 'invalid_payload'
  )
}

/** Whether a WS close code should trigger client auto-reconnect. */
export function mindmateCollabDisconnectShouldNotify(
  closeCode: number,
  suppressReconnect: boolean,
  reconnectExhausted: boolean,
): 'none' | 'reconnecting' | 'closed_reason' | 'reconnect_failed' {
  if (closeCode === 4010 || closeCode === 4011 || closeCode === 4003 || closeCode === 1008 || closeCode === 4029) {
    return 'none'
  }
  if (closeCode === 1000 || closeCode === 1001) {
    return 'none'
  }
  if (reconnectExhausted) {
    return 'reconnect_failed'
  }
  if (suppressReconnect) {
    return 'closed_reason'
  }
  return 'reconnecting'
}
