/**
 * Shared PWA install action for sidebar and mobile account menus.
 */
import { computed } from 'vue'

import { useNotifications } from '@/composables'
import {
  canShowPwaInstallUi,
  getPwaInstallFeedback,
  promptPwaInstall,
  pwaInstallAvailable,
} from '@/utils/pwaInstall'

export function usePwaInstall(translate: (key: string) => string) {
  const notify = useNotifications()

  const showPwaInstall = computed(() => {
    void pwaInstallAvailable.value
    return canShowPwaInstallUi()
  })

  async function handlePwaInstall(): Promise<void> {
    const result = await promptPwaInstall()
    const feedback = getPwaInstallFeedback(result)
    if (!feedback) {
      return
    }
    const message = translate(feedback.messageKey)
    if (feedback.kind === 'success') {
      notify.success(message)
      return
    }
    notify.info(message)
  }

  return {
    showPwaInstall,
    handlePwaInstall,
  }
}
