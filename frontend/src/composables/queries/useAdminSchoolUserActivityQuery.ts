/**
 * TanStack Query hook for school-dashboard user-activity analytics.
 */
import { computed, type MaybeRefOrGetter, toValue } from 'vue'

import { useQuery } from '@tanstack/vue-query'

import { fetchAdminSchoolUserActivity } from './adminSchoolUserActivityApi'
import { ADMIN_STALE_MS, adminKeys } from './adminKeys'

export function useAdminSchoolUserActivityQuery(
  organizationId: MaybeRefOrGetter<number | null | undefined>,
  year: MaybeRefOrGetter<number>,
  options?: { enabled?: MaybeRefOrGetter<boolean> }
) {
  return useQuery({
    queryKey: computed(() =>
      adminKeys.schoolUserActivity(toValue(organizationId) ?? 0, toValue(year))
    ),
    queryFn: ({ signal }) => {
      const id = toValue(organizationId)
      if (id == null) {
        throw new Error('Organization id is required')
      }
      return fetchAdminSchoolUserActivity(id, toValue(year), signal)
    },
    staleTime: ADMIN_STALE_MS.stats,
    enabled: computed(() => {
      const id = toValue(organizationId)
      const extraEnabled = options?.enabled == null ? true : toValue(options.enabled)
      return extraEnabled && id != null
    }),
  })
}
