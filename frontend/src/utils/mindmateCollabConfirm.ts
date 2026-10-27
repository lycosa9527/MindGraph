import { swissGlassConfirm } from '@/composables/common/useSwissGlassConfirm'

type TranslateFn = (key: string) => string

/** Swiss-styled confirm before ending a MindMate collab session for all participants. */
export async function confirmMindmateCollabStop(t: TranslateFn): Promise<boolean> {
  try {
    await swissGlassConfirm(
      t('sidebar.mindmateCollabHistory.stopConfirm'),
      t('sidebar.mindmateCollabHistory.stopConfirmTitle'),
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
export async function confirmMindmateCollabLeave(t: TranslateFn): Promise<boolean> {
  try {
    await swissGlassConfirm(
      t('sidebar.mindmateCollabHistory.leaveConfirm'),
      t('sidebar.mindmateCollabHistory.leaveConfirmTitle'),
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
