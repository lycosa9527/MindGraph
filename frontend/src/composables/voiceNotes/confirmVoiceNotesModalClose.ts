/**
 * Confirm hiding the Voice Notes modal while capture is still live.
 */
import { loadElMessageBox } from '@/composables/core/notifications'

export async function confirmHideVoiceNotesWhileRecording(
  translate: (key: string) => string
): Promise<boolean> {
  try {
    const ElMessageBox = await loadElMessageBox()
    await ElMessageBox.confirm(
      translate('auth.voiceNotes.closeWhileRecordingBody'),
      translate('auth.voiceNotes.closeWhileRecordingTitle'),
      {
        confirmButtonText: translate('auth.voiceNotes.closeWhileRecordingConfirm'),
        cancelButtonText: translate('common.cancel'),
        type: 'warning',
      }
    )
    return true
  } catch {
    return false
  }
}
