import { isMindMapConnectorVerboseDebugEnabled } from '@/utils/mindMapConnectorDebugLevel'

export type MindMapProcessStage =
  | 'layout:recalc:start'
  | 'layout:recalc:done'
  | 'layout:y-correct:start'
  | 'layout:y-correct:result'
  | 'edge:resolve'
  | 'path:build'
  | 'debug:dump'
  | 'pipeline:start'
  | 'pipeline:end'

let activeRecalcGen = 0
let lastPipelineRecalcGen = -1
let pipelineOpen = false

export function setMindMapVerboseRecalcGen(recalcGen: number): void {
  activeRecalcGen = recalcGen
}

export function logMindMapProcess(stage: MindMapProcessStage, payload: Record<string, unknown>): void {
  if (!isMindMapConnectorVerboseDebugEnabled()) return
  console.info(`[MindMap:${stage}]`, {
    recalcGen: activeRecalcGen,
    runtime: 'frontend',
    ...payload,
  })
}

/** Open one pipeline group per recalc generation (dump pass only). */
export function beginMindMapConnectorPipeline(recalcGen: number, reason?: string): void {
  if (!isMindMapConnectorVerboseDebugEnabled()) return
  activeRecalcGen = recalcGen
  if (lastPipelineRecalcGen === recalcGen && pipelineOpen) return
  if (pipelineOpen && typeof console.groupEnd === 'function') {
    console.groupEnd()
  }
  lastPipelineRecalcGen = recalcGen
  pipelineOpen = true
  console.groupCollapsed(
    `[MindMap pipeline] recalc=${recalcGen}${reason ? ` reason=${reason}` : ''}`
  )
  logMindMapProcess('pipeline:start', { reason: reason ?? 'recalc' })
}

export function endMindMapConnectorPipeline(): void {
  if (!pipelineOpen || typeof console.groupEnd !== 'function') return
  logMindMapProcess('pipeline:end', {})
  console.groupEnd()
  pipelineOpen = false
}
