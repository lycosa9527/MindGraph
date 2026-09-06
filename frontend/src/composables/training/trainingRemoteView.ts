import type { TrainingSnapshot } from '@/types/training'

export type TrainingRemotePhase = 'waiting' | 'foreign' | 'live'

export function trainingRemotePhase(
  snapshot: TrainingSnapshot,
  userId: number | null | undefined
): TrainingRemotePhase {
  const mine = Number(userId)
  const host = Number(snapshot.instructor_id)
  const active = snapshot.state === 'live' || snapshot.state === 'paused'
  if (active && mine > 0 && host > 0 && mine !== host) {
    return 'foreign'
  }
  if (active && mine > 0 && mine === host && snapshot.course_id) {
    return 'live'
  }
  return 'waiting'
}

export function trainingRemotePrompterKey(snapshot: TrainingSnapshot): string {
  return `${snapshot.session_id || 'none'}:${snapshot.seq}:${snapshot.step_index || 0}`
}

export function trainingRemoteShouldPollHost(
  phase: TrainingRemotePhase,
  leadingOrgId: number | null
): boolean {
  return phase === 'waiting' || leadingOrgId == null
}
