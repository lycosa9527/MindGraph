/**
 * Lock the facilitator dialog (no overlay / Escape dismiss) and confirm before
 * revoking the live workshop channel.
 */
import { onBeforeUnmount, onMounted } from 'vue'

import { loadElMessageBox } from '@/composables/core/notifications'

type TranslateFn = (key: string, fallback?: string) => string

export function useQuickRegisterDialogClose(options: {
  t: TranslateFn
  token: { value: string }
  revokeKeepAlive: () => void
}): {
  dialogDismissLocked: true
  requestClose: (commit: () => void) => Promise<void>
} {
  const { t, token, revokeKeepAlive } = options

  function onPageHide(): void {
    if (token.value) {
      revokeKeepAlive()
    }
  }

  onMounted(() => {
    window.addEventListener('pagehide', onPageHide)
  })

  onBeforeUnmount(() => {
    window.removeEventListener('pagehide', onPageHide)
  })

  async function requestClose(commit: () => void): Promise<void> {
    try {
      const ElMessageBox = await loadElMessageBox()
      await ElMessageBox.confirm(
        t(
          'auth.quickRegCloseConfirm',
          'Closing this window stops new students from joining with the current QR and room code.'
        ),
        t('auth.quickRegCloseConfirmTitle', 'End quick registration?'),
        {
          confirmButtonText: t('common.close'),
          cancelButtonText: t('common.cancel'),
          distinguishCancelAndClose: true,
          autofocus: false,
        }
      )
    } catch {
      return
    }
    commit()
  }

  return {
    dialogDismissLocked: true,
    requestClose,
  }
}
