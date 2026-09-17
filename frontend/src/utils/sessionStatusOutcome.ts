/**
 * Interpret GET /api/auth/session-status without treating generic 401
 * as a five-device kick.
 */

export type SessionStatusBody = {
  status?: string
  message?: string
  reason?: string
}

export type SessionStatusOutcome =
  | { kind: 'noop' }
  | { kind: 'invalidated'; message?: string; reason?: string }
  | { kind: 'expired' }

export function interpretSessionStatusResponse(
  httpStatus: number,
  body: SessionStatusBody | null
): SessionStatusOutcome {
  if (httpStatus === 401) {
    return { kind: 'expired' }
  }
  if (httpStatus === 200 && body?.status === 'invalidated') {
    return {
      kind: 'invalidated',
      message: body.message,
      reason: body.reason,
    }
  }
  return { kind: 'noop' }
}
