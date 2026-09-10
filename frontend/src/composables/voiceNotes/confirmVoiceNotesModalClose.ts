/**
 * Confirm hiding the Voice Notes modal while capture is still live.
 */
import { swissGlassConfirm } from '@/composables/common/useSwissGlassConfirm'

export async function confirmHideVoiceNotesWhileRecording(
  translate: (key: string) => string
): Promise<boolean> {
  try {
    await swissGlassConfirm(
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
