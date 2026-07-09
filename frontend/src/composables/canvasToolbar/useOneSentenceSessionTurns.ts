/**
 * Persist and restore 一句话生成 chat turns via Kitty REST (Redis-backed).
 */
export type OneSentenceTurnRole = 'user' | 'kitty'

export type OneSentenceTurnRecord = {
  turn_id: string
  ts: number
  role: OneSentenceTurnRole | 'meta'
  content: string
  phase: 'create' | 'edit'
  source: string
  action?: string
  outcome?: string
  diagram_type?: string
}

export type OneSentenceTurnInput = {
  role: OneSentenceTurnRole
  content: string
  phase: 'create' | 'edit'
  source: string
  diagram_type?: string
}

function turnsUrl(scope: string): string {
  return `/api/kitty/one_sentence/${encodeURIComponent(scope)}/turns`
}

function logTurnApiFailure(action: string, scope: string, status: number): void {
  if (import.meta.env.DEV) {
    console.warn(`[oneSentenceTurns] ${action} failed scope=${scope.slice(0, 8)} status=${status}`)
  }
}

export async function fetchOneSentenceTurns(
  scope: string
): Promise<OneSentenceTurnRecord[]> {
  const res = await fetch(turnsUrl(scope), { credentials: 'same-origin' })
  if (!res.ok) {
    logTurnApiFailure('fetch', scope, res.status)
    return []
  }
  const data = (await res.json()) as { ok?: boolean; turns?: OneSentenceTurnRecord[] }
  if (!data.ok || !Array.isArray(data.turns)) return []
  return data.turns.filter((row) => row.role === 'user' || row.role === 'kitty')
}

export async function appendOneSentenceTurn(
  scope: string,
  turn: OneSentenceTurnInput
): Promise<boolean> {
  const res = await fetch(turnsUrl(scope), {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ turn }),
  })
  if (!res.ok) {
    logTurnApiFailure('append', scope, res.status)
    return false
  }
  const data = (await res.json()) as { ok?: boolean }
  return data.ok === true
}

export async function appendOneSentenceTurns(
  scope: string,
  turns: OneSentenceTurnInput[]
): Promise<boolean> {
  if (turns.length === 0) return true
  const res = await fetch(turnsUrl(scope), {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ turns }),
  })
  if (!res.ok) {
    logTurnApiFailure('appendBatch', scope, res.status)
    return false
  }
  const data = (await res.json()) as { ok?: boolean }
  return data.ok === true
}

export async function migrateOneSentenceScope(
  fromScope: string,
  toScope: string
): Promise<boolean> {
  if (!fromScope || !toScope || fromScope === toScope) return true
  const res = await fetch('/api/kitty/one_sentence/migrate_scope', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ from_scope: fromScope, to_scope: toScope }),
  })
  if (!res.ok) {
    logTurnApiFailure('migrate', fromScope, res.status)
    return false
  }
  const data = (await res.json()) as { ok?: boolean }
  return data.ok === true
}
