/**
 * Kitty pipeline public barrel.
 */
export {
  beginKittyTurn,
  catalogEntryForCode,
  completeKittyTurn,
  dumpTurnTrace,
  failKittyTurn,
  getLastFail,
  getTurnStatus,
  kittyPipelineTraceEnabled,
  messageForKittyFail,
  recordPipelineEvent,
} from '@/composables/kitty/pipeline/trace'
export type {
  KittyActionJournalRecord,
  KittyErrorCode,
  KittyLane,
  KittyModule,
  KittyPipelineEvent,
  KittyPipelineEventStatus,
  KittyPipelinePhase,
  KittyStep,
  KittyTurnContext,
  KittyTurnFail,
  KittyTurnStatus,
} from '@/composables/kitty/pipeline/types'
export { KITTY_STEP_ORDER } from '@/composables/kitty/pipeline/types'
export {
  getKittyErrorCatalogEntry,
  resolveKittyErrorCode,
  resolveKittyFailMessage,
} from '@/composables/kitty/pipeline/errorCatalog'
export { runKittyEditTurn } from '@/composables/kitty/pipeline/editTurn'
export { runKittyHubSync, scheduleKittyHubContextSync } from '@/composables/kitty/pipeline/hubSyncWorker'
export { ensureKittySessionConnected } from '@/composables/kitty/pipeline/session'
