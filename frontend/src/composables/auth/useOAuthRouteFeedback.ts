/**
 * Global OAuth redirect feedback: ?error= and ?oauth_bind= query params.
 */
import { watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useLanguage, useNotifications } from '@/composables'
import {
  isOAuthRedirectError,
  notifyOAuthError,
  oauthBindFromRouteQuery,
  oauthErrorFromRouteQuery,
} from '@/utils/oauthLoginUi'

export function useOAuthRouteFeedback(): void {
  const route = useRoute()
  const router = useRouter()
  const notify = useNotifications()
  const { t } = useLanguage()

  function stripOAuthQuery(): void {
    const nextQuery = { ...route.query }
    let changed = false
    const errorCode = oauthErrorFromRouteQuery(nextQuery.error)
    if (nextQuery.error !== undefined && isOAuthRedirectError(errorCode)) {
      delete nextQuery.error
      changed = true
    }
    if (nextQuery.oauth_bind !== undefined) {
      delete nextQuery.oauth_bind
      changed = true
    }
    if (!changed) {
      return
    }
    void router.replace({ path: route.path, query: nextQuery, hash: route.hash })
  }

  watch(
    () => [route.query.error, route.query.oauth_bind] as const,
    () => {
      const error = oauthErrorFromRouteQuery(route.query.error)
      if (error && isOAuthRedirectError(error)) {
        notifyOAuthError(error, notify, t)
        stripOAuthQuery()
        return
      }
      const bindProvider = oauthBindFromRouteQuery(route.query.oauth_bind)
      if (bindProvider) {
        notify.success(t('auth.oauthBindSuccess'))
        stripOAuthQuery()
      }
    },
    { immediate: true }
  )
}
