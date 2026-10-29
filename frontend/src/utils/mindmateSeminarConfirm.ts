import { swissGlassConfirm } from '@/composables/common/useSwissGlassConfirm'

type TranslateFn = (key: string) => string

/** Swiss-styled confirm before ending a MindMate collab session for all participants. */
export async function confirmMindmateSeminarStop(t: TranslateFn): Promise<boolean> {
  try {
    await swissGlassConfirm(
      t('sidebar.mindmateSeminarHistory.stopConfirm'),
      t('sidebar.mindmateSeminarHistory.stopConfirmTitle'),
      {
        confirmButtonText: t('mindmate.collabEndSeminar'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
        distinguishCancelAndClose: true,
      }
    )
    return true
  } catch {
    return false
  }
}

/** Confirm before one person leaves a seminar that stays open for everyone else. */
export async function confirmMindmateSeminarLeave(t: TranslateFn): Promise<boolean> {
  try {
    await swissGlassConfirm(
      t('sidebar.mindmateSeminarHistory.leaveConfirm'),
      t('sidebar.mindmateSeminarHistory.leaveConfirmTitle'),
      {
        confirmButtonText: t('mindmate.collabLeaveSeminar'),
        cancelButtonText: t('common.cancel'),
        type: 'warning',
        distinguishCancelAndClose: true,
      }
    )
    return true
  } catch {
    return false
  }
}
