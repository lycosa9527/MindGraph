/**
 * Keep the current route on the shell locked for this device.
 * Rotation changes the viewport; it does not change the lock, so this only
 * runs when the user or the server sets a shell.
 */
import { watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { useFeatureFlagsStore } from '@/stores/featureFlags'
import { clientShellLock } from '@/utils/clientShellLock'
import type { ClientShell } from '@/utils/clientShellLock'
import { pathForLockedClientShell } from '@/utils/mobileRouteRedirect'
import { isOfficeEmbedDesktop } from '@/utils/officeEmbed'

async function lockedShellTarget(path: string, shell: ClientShell): Promise<string | null> {
  if (shell === 'mobile' && (path === '/training' || path.startsWith('/training/'))) {
    const flags = useFeatureFlagsStore()
    await flags.fetchFlags()
    const isTrainingLead = flags.getFeatureTraining() && useAuthStore().isPlatformLevel
    return pathForLockedClientShell(path, shell, { isTrainingLead })
  }
  return pathForLockedClientShell(path, shell)
}

export function useLockedClientShellRoute(): void {
  const route = useRoute()
  const router = useRouter()

  watch(
    clientShellLock,
    (shell) => {
      if (shell !== 'mobile' && shell !== 'desktop') return
      if (isOfficeEmbedDesktop()) return
      const path = route.path
      const query = route.query
      const hash = route.hash
      void lockedShellTarget(path, shell)
        .then((next) => {
          if (!next || next === router.currentRoute.value.path) return
          if (router.currentRoute.value.path !== path) return
          return router.replace({ path: next, query, hash })
        })
        .catch(() => undefined)
    },
    { immediate: true }
  )
}
