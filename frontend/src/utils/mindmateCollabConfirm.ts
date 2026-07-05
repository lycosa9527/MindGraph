import { ElMessageBox } from 'element-plus'

import '@/styles/mindmate-swiss-messagebox.css'

type TranslateFn = (key: string) => string

/** Swiss-styled confirm before ending a MindMate collab session for all participants. */
export async function confirmMindmateCollabStop(t: TranslateFn): Promise<boolean> {
  try {
    await ElMessageBox.confirm(
      t('sidebar.mindmateCollabHistory.stopConfirm'),
      t('sidebar.mindmateCollabHistory.stopConfirmTitle'),
      {
        confirmButtonText: t('mindmate.collabEndSeminar'),
        cancelButtonText: t('common.cancel'),
        customClass: 'mindmate-swiss-message-box mindmate-swiss-message-box--destructive',
        cancelButtonClass: 'mindmate-swiss-msg-btn mindmate-swiss-msg-btn--cancel',
        confirmButtonClass: 'mindmate-swiss-msg-btn mindmate-swiss-msg-btn--confirm',
        showClose: true,
        distinguishCancelAndClose: true,
        autofocus: false,
      },
    )
    return true
  } catch {
    return false
  }
}
