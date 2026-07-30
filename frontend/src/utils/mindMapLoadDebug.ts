/**
 * Opt-in mind-map load timing tracer.
 * Enable: localStorage.setItem('mindmap_load_debug', '1') then reload.
 */
const STORAGE_KEY = 'mindmap_load_debug'
const LOG_PREFIX = '[MindMapLoad]'

export type MindMapLoadStage =
  | 'library:fetch:start'
  | 'library:fetch:done'
  | 'spec:load:start'
  | 'spec:load:done'
  | 'measure:batch:arm'
  | 'shell:v2:mounted'
  | 'measure:first'
  | 'measure:batch:flush'
  | 'layout:recalc'
  | 'load:settle'

interface LoadSession {
  startedAt: number
  lastStageAt: number
  stages: Partial<Record<MindMapLoadStage, number>>
  recalcCount: number
  shellMounted: boolean
  firstMeasureLogged: boolean
  pendingSettleRaf: number
  active: boolean
}

let session: LoadSession | null = null

function nowMs(): number {
  if (typeof performance !== 'undefined' && typeof performance.now === 'function') {
    return performance.now()
  }
  return Date.now()
}

export function isMindMapLoadDebugEnabled(): boolean {
  if (typeof localStorage === 'undefined') return false
  return localStorage.getItem(STORAGE_KEY) === '1'
}

function ensureSession(): LoadSession | null {
  if (!isMindMapLoadDebugEnabled()) return null
  if (!session || !session.active) {
    const t = nowMs()
    session = {
      startedAt: t,
      lastStageAt: t,
      stages: {},
      recalcCount: 0,
      shellMounted: false,
      firstMeasureLogged: false,
      pendingSettleRaf: 0,
      active: true,
    }
  }
  return session
}

function roundMs(value: number): number {
  return Math.round(value * 10) / 10
}

export function beginMindMapLoadSession(reason: string): void {
  if (!isMindMapLoadDebugEnabled()) return
  const t = nowMs()
  if (session?.pendingSettleRaf && typeof cancelAnimationFrame === 'function') {
    cancelAnimationFrame(session.pendingSettleRaf)
  }
  session = {
    startedAt: t,
    lastStageAt: t,
    stages: {},
    recalcCount: 0,
    shellMounted: false,
    firstMeasureLogged: false,
    pendingSettleRaf: 0,
    active: true,
  }
  console.info(`${LOG_PREFIX} session:start reason=${reason}`)
}

/**
 * Start a loadFromSpec stage. Keeps an in-flight library session (fetch → load),
 * but restarts when a prior spec load is still open (rapid model switches).
 */
export function beginMindMapSpecLoadSession(): void {
  if (!isMindMapLoadDebugEnabled()) return
  if (!session?.active) {
    beginMindMapLoadSession('spec')
    return
  }
  if (session.stages['spec:load:start'] != null) {
    beginMindMapLoadSession('spec')
  }
}

export function markMindMapLoadStage(
  stage: MindMapLoadStage,
  payload: Record<string, unknown> = {}
): void {
  const active = ensureSession()
  if (!active) return

  if (stage === 'shell:v2:mounted' && active.shellMounted) return
  if (stage === 'measure:first' && active.firstMeasureLogged) return

  const t = nowMs()
  const sinceStart = t - active.startedAt
  const sincePrev = t - active.lastStageAt
  active.stages[stage] = sinceStart
  active.lastStageAt = t

  if (stage === 'layout:recalc') {
    active.recalcCount += 1
  }
  if (stage === 'shell:v2:mounted') {
    active.shellMounted = true
  }
  if (stage === 'measure:first') {
    active.firstMeasureLogged = true
  }

  console.info(`${LOG_PREFIX} ${stage}`, {
    t: roundMs(sinceStart),
    dt: roundMs(sincePrev),
    ...payload,
  })
}

export function markMindMapLoadShellMounted(kind: 'topic' | 'branch'): void {
  markMindMapLoadStage('shell:v2:mounted', { kind })
}

export function markMindMapLoadFirstMeasure(nodeId: string): void {
  markMindMapLoadStage('measure:first', { nodeId })
}

export function markMindMapLoadRecalc(): void {
  if (!session?.active || !isMindMapLoadDebugEnabled()) return
  markMindMapLoadStage('layout:recalc', { n: session.recalcCount + 1 })
}

export function scheduleMindMapLoadSettle(reason: string): void {
  const active = session
  if (!active?.active || !isMindMapLoadDebugEnabled()) return
  if (typeof requestAnimationFrame !== 'function') {
    finishMindMapLoadSession(reason)
    return
  }
  if (active.pendingSettleRaf !== 0) {
    cancelAnimationFrame(active.pendingSettleRaf)
  }
  active.pendingSettleRaf = requestAnimationFrame(() => {
    active.pendingSettleRaf = 0
    finishMindMapLoadSession(reason)
  })
}

export function finishMindMapLoadSession(reason: string): void {
  const active = session
  if (!active?.active || !isMindMapLoadDebugEnabled()) return

  const total = nowMs() - active.startedAt
  const fetchStart = active.stages['library:fetch:start']
  const fetchDone = active.stages['library:fetch:done']
  const specStart = active.stages['spec:load:start']
  const specDone = active.stages['spec:load:done']
  const shell = active.stages['shell:v2:mounted']
  const measureFirst = active.stages['measure:first']
  const flush = active.stages['measure:batch:flush']

  markMindMapLoadStage('load:settle', { reason })

  console.info(`${LOG_PREFIX} summary`, {
    total: roundMs(total),
    fetch:
      fetchStart != null && fetchDone != null ? roundMs(fetchDone - fetchStart) : undefined,
    spec: specStart != null && specDone != null ? roundMs(specDone - specStart) : undefined,
    shell: shell != null ? roundMs(shell) : undefined,
    measureFirst: measureFirst != null ? roundMs(measureFirst) : undefined,
    flush: flush != null ? roundMs(flush) : undefined,
    recalcs: active.recalcCount,
    reason,
  })

  active.active = false
  if (active.pendingSettleRaf && typeof cancelAnimationFrame === 'function') {
    cancelAnimationFrame(active.pendingSettleRaf)
    active.pendingSettleRaf = 0
  }
}

export function isMindMapLoadSessionActive(): boolean {
  return Boolean(session?.active && isMindMapLoadDebugEnabled())
}
