/**
 * Unified Kitty pipeline error catalog — errorCode → module/step/i18n.
 */
import type { UseLanguageTranslate } from '@/composables/core/useLanguage'
import type { KittyErrorCode, KittyModule, KittyStep } from '@/composables/kitty/pipeline/types'

export type KittyTranslateFn = (
  key: string,
  fallbackOrParams?: string | Record<string, string>
) => string

export function adaptKittyTranslate(translate: UseLanguageTranslate): KittyTranslateFn {
  return (key, fallbackOrParams) => {
    if (fallbackOrParams === undefined) {
      return translate(key)
    }
    if (typeof fallbackOrParams === 'string') {
      return translate(key, fallbackOrParams)
    }
    return translate(key, fallbackOrParams)
  }
}

export type KittyErrorCatalogEntry = {
  errorCode: KittyErrorCode
  module: KittyModule
  step: KittyStep
  /** i18n key under canvas.mindMapOneSentence or mobile.* */
  messageKey: string
  /** Fallback English when i18n missing */
  fallback: string
  /** Soft failures do not fail the whole turn for canvas */
  soft?: boolean
}

const CATALOG: Record<KittyErrorCode, KittyErrorCatalogEntry> = {
  mic_denied: {
    errorCode: 'mic_denied',
    module: 'adapter',
    step: 'S01_gesture',
    messageKey: 'mobile.kittyMicDenied',
    fallback: 'Microphone access was denied. Check browser permissions.',
  },
  gesture_aborted: {
    errorCode: 'gesture_aborted',
    module: 'adapter',
    step: 'S01_gesture',
    messageKey: 'mobile.kittyGestureAborted',
    fallback: 'Voice hold was cancelled.',
    soft: true,
  },
  not_connected: {
    errorCode: 'not_connected',
    module: 'session',
    step: 'S02_session_ready',
    messageKey: 'canvas.mindMapOneSentence.kittyUnavailable',
    fallback: 'Kitty is unavailable. Check your connection and try again.',
  },
  connect_timeout: {
    errorCode: 'connect_timeout',
    module: 'session',
    step: 'S02_session_ready',
    messageKey: 'mobile.kittyConnectFailed',
    fallback: 'Connection timed out. Please try again.',
  },
  scope_missing: {
    errorCode: 'scope_missing',
    module: 'session',
    step: 'S02_session_ready',
    messageKey: 'mobile.kittyPickDiagramToEdit',
    fallback: 'Open or pick a saved diagram first, then hold to speak or type to edit it.',
  },
  asr_start_failed: {
    errorCode: 'asr_start_failed',
    module: 'asr',
    step: 'S03_asr_start',
    messageKey: 'mobile.kittyAsrStartFailed',
    fallback: 'Could not start voice recognition. Please try again.',
  },
  asr_no_audio: {
    errorCode: 'asr_no_audio',
    module: 'asr',
    step: 'S04_asr_audio',
    messageKey: 'mobile.kittyAsrNoAudio',
    fallback: 'No audio was captured. Please try again.',
  },
  asr_ws_drop: {
    errorCode: 'asr_ws_drop',
    module: 'asr',
    step: 'S04_asr_audio',
    messageKey: 'mobile.kittyConnectFailed',
    fallback: 'Voice connection dropped. Please try again.',
  },
  empty_transcript: {
    errorCode: 'empty_transcript',
    module: 'asr',
    step: 'S05_asr_commit',
    messageKey: 'mobile.kittyEmptyTranscript',
    fallback: 'No speech was recognized.',
    soft: true,
  },
  stale_utterance: {
    errorCode: 'stale_utterance',
    module: 'asr',
    step: 'S05_asr_commit',
    messageKey: 'mobile.kittyStaleUtterance',
    fallback: 'Ignored a stale voice result.',
    soft: true,
  },
  deduped: {
    errorCode: 'deduped',
    module: 'asr',
    step: 'S05_asr_commit',
    messageKey: 'mobile.kittyDeduped',
    fallback: 'Duplicate voice commit skipped.',
    soft: true,
  },
  history_append_failed: {
    errorCode: 'history_append_failed',
    module: 'history',
    step: 'S06_history_user',
    messageKey: 'canvas.mindMapOneSentence.historyAppendFailed',
    fallback: 'Could not save the chat turn. Please try again.',
  },
  hub_persist_timeout: {
    errorCode: 'hub_persist_timeout',
    module: 'hub_sync',
    step: 'S07_hub_sync',
    messageKey: 'canvas.mindMapOneSentence.kittyContextSyncFailed',
    fallback: 'Could not sync the canvas. Please try again in a moment.',
  },
  hub_persist_skipped: {
    errorCode: 'hub_persist_skipped',
    module: 'hub_sync',
    step: 'S07_hub_sync',
    messageKey: 'canvas.mindMapOneSentence.kittyContextSyncFailed',
    fallback: 'Could not sync the canvas. Please try again in a moment.',
  },
  stale_revision: {
    errorCode: 'stale_revision',
    module: 'hub_sync',
    step: 'S07_hub_sync',
    messageKey: 'canvas.mindMapOneSentence.kittyContextSyncFailed',
    fallback: 'Could not sync the canvas. Please try again in a moment.',
  },
  context_mutation_rejected: {
    errorCode: 'context_mutation_rejected',
    module: 'hub_sync',
    step: 'S07_hub_sync',
    messageKey: 'canvas.mindMapOneSentence.kittyContextSyncFailed',
    fallback: 'Could not sync the canvas. Please try again in a moment.',
  },
  text_send_failed: {
    errorCode: 'text_send_failed',
    module: 'edit_pipeline',
    step: 'S08_text_send',
    messageKey: 'mobile.kittyConnectFailed',
    fallback: 'Connection failed. Please check the network and try again.',
  },
  ws_closed: {
    errorCode: 'ws_closed',
    module: 'edit_pipeline',
    step: 'S08_text_send',
    messageKey: 'mobile.kittyConnectFailed',
    fallback: 'Connection failed. Please check the network and try again.',
  },
  server_error: {
    errorCode: 'server_error',
    module: 'server',
    step: 'S09_server_llm',
    messageKey: 'canvas.mindMapOneSentence.kittyUnavailable',
    fallback: 'Kitty is unavailable. Check your connection and try again.',
  },
  llm_timeout: {
    errorCode: 'llm_timeout',
    module: 'server',
    step: 'S09_server_llm',
    messageKey: 'canvas.mindMapOneSentence.kittyUnavailable',
    fallback: 'Kitty is unavailable. Check your connection and try again.',
  },
  apply_noop: {
    errorCode: 'apply_noop',
    module: 'mutation',
    step: 'S10_mutation_apply',
    messageKey: 'canvas.mindMapOneSentence.editFailed',
    fallback: 'The diagram could not be updated.',
  },
  apply_failed: {
    errorCode: 'apply_failed',
    module: 'mutation',
    step: 'S10_mutation_apply',
    messageKey: 'canvas.mindMapOneSentence.editFailed',
    fallback: 'The diagram could not be updated.',
  },
  verify_failed: {
    errorCode: 'verify_failed',
    module: 'mutation',
    step: 'S11_mutation_verify',
    messageKey: 'canvas.mindMapOneSentence.editFailed',
    fallback: 'The diagram update could not be verified.',
  },
  post_hub_persist_failed: {
    errorCode: 'post_hub_persist_failed',
    module: 'hub_sync',
    step: 'S12_post_hub_persist',
    messageKey: 'canvas.mindMapOneSentence.kittyContextSyncFailed',
    fallback: 'Could not sync the canvas. Please try again in a moment.',
  },
  ack_send_failed: {
    errorCode: 'ack_send_failed',
    module: 'mutation',
    step: 'S13_mutation_ack',
    messageKey: 'canvas.mindMapOneSentence.editFailed',
    fallback: 'The diagram could not be updated.',
  },
  library_snapshot_failed: {
    errorCode: 'library_snapshot_failed',
    module: 'library',
    step: 'S15_library_persist',
    messageKey: 'mobile.kittyLibraryPersistFailed',
    fallback: 'Could not save the diagram to the library.',
    soft: true,
  },
  unknown: {
    errorCode: 'unknown',
    module: 'edit_pipeline',
    step: 'S08_text_send',
    messageKey: 'canvas.mindMapOneSentence.kittyUnavailable',
    fallback: 'Something went wrong. Please try again.',
  },
}

export function getKittyErrorCatalogEntry(errorCode: KittyErrorCode): KittyErrorCatalogEntry {
  return CATALOG[errorCode] ?? CATALOG.unknown
}

export function resolveKittyErrorCode(raw: string | undefined | null): KittyErrorCode {
  if (!raw || !raw.trim()) {
    return 'unknown'
  }
  const code = raw.trim() as KittyErrorCode
  return CATALOG[code] ? code : 'unknown'
}

export function resolveKittyFailMessage(
  errorCode: KittyErrorCode,
  t: KittyTranslateFn,
  detail?: string
): string {
  const entry = getKittyErrorCatalogEntry(errorCode)
  const extra = detail?.trim()
  if (extra && entry.messageKey.includes('kittyContextSyncFailed')) {
    return t('canvas.mindMapOneSentence.kittyContextSyncFailedDetail', { detail: extra })
  }
  return t(entry.messageKey, entry.fallback)
}
