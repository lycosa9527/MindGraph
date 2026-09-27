/** ``autoSaveDiagram`` skip reasons that are not persistence failures. */
export const AUTO_SAVE_SKIP_EMPTY = 'Diagram is empty/unmodified'
export const AUTO_SAVE_SKIP_NO_SLOTS = 'No available slots'

export function saveFlushReasonForSkippedAutoSave(
  error: string | undefined
): 'skipped_empty' | 'skipped_slots_full' | null {
  if (error === AUTO_SAVE_SKIP_EMPTY) return 'skipped_empty'
  if (error === AUTO_SAVE_SKIP_NO_SLOTS) return 'skipped_slots_full'
  return null
}
