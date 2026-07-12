/**
 * Kitty voice→node pipeline protocol types — shared envelope for logging, errors, status.
 */
export type KittyModule =
  | 'adapter'
  | 'session'
  | 'asr'
  | 'history'
  | 'hub_sync'
  | 'edit_pipeline'
  | 'mutation'
  | 'journal'
  | 'library'
  | 'server'

export type KittyStep =
  | 'S01_gesture'
  | 'S02_session_ready'
  | 'S03_asr_start'
  | 'S04_asr_audio'
  | 'S05_asr_commit'
  | 'S06_history_user'
  | 'S07_hub_sync'
  | 'S08_text_send'
  | 'S09_server_llm'
  | 'S10_mutation_apply'
  | 'S11_mutation_verify'
  | 'S12_post_hub_persist'
  | 'S13_mutation_ack'
  | 'S14_history_reply'
  | 'S15_library_persist'

export type KittyErrorCode =
  | 'mic_denied'
  | 'gesture_aborted'
  | 'not_connected'
  | 'connect_timeout'
  | 'scope_missing'
  | 'asr_start_failed'
  | 'asr_no_audio'
  | 'asr_ws_drop'
  | 'empty_transcript'
  | 'stale_utterance'
  | 'deduped'
  | 'history_append_failed'
  | 'hub_persist_timeout'
  | 'hub_persist_skipped'
  | 'stale_revision'
  | 'context_mutation_rejected'
  | 'text_send_failed'
  | 'ws_closed'
  | 'server_error'
  | 'llm_timeout'
  | 'apply_noop'
  | 'apply_failed'
  | 'verify_failed'
  | 'post_hub_persist_failed'
  | 'ack_send_failed'
  | 'library_snapshot_failed'
  | 'unknown'

export type KittyPipelinePhase =
  | 'idle'
  | 'committing'
  | 'hub_syncing'
  | 'sending'
  | 'awaiting_result'
  | 'completed'
  | 'failed'

export type KittyPipelineEventStatus = 'started' | 'ok' | 'fail' | 'skip'

export type KittyLane = 'mobile' | 'desktop'

export type KittyTurnContext = {
  requestId: string
  utteranceId?: string
  scope: string
  lane: KittyLane
  voiceSessionId?: string
}

export type KittyPipelineEvent = {
  ctx: KittyTurnContext
  module: KittyModule
  step: KittyStep
  status: KittyPipelineEventStatus
  errorCode?: KittyErrorCode
  detail?: string
  at: number
  durationMs?: number
}

export type KittyTurnFail = {
  requestId: string
  module: KittyModule
  step: KittyStep
  errorCode: KittyErrorCode
  detail?: string
  at: number
}

export type KittyTurnStatus = {
  phase: KittyPipelinePhase
  module: KittyModule | null
  step: KittyStep | null
  completedSteps: KittyStep[]
  fail?: KittyTurnFail
}

export type KittyActionJournalRecord = {
  requestId: string
  scope: string
  action: string
  ok: boolean
  summary?: string
  errorCode?: string
  nodeIds?: string[]
  at: number
}

export const KITTY_STEP_ORDER: KittyStep[] = [
  'S01_gesture',
  'S02_session_ready',
  'S03_asr_start',
  'S04_asr_audio',
  'S05_asr_commit',
  'S06_history_user',
  'S07_hub_sync',
  'S08_text_send',
  'S09_server_llm',
  'S10_mutation_apply',
  'S11_mutation_verify',
  'S12_post_hub_persist',
  'S13_mutation_ack',
  'S14_history_reply',
  'S15_library_persist',
]
