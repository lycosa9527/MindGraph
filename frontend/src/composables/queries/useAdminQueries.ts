/**
 * Admin Query Composables
 *
 * Vue Query composables for admin panel read operations with domain stale times.
 */
import { computed, type MaybeRefOrGetter, toValue } from 'vue'

import { useQuery } from '@tanstack/vue-query'

import {
  fetchAdminAdmins,
  fetchAdminApiKeys,
  fetchAdminConfigFeatures,
  fetchAdminDatabaseOrphans,
  fetchAdminDatabaseStats,
  fetchAdminFeatureOrgAccess,
  fetchAdminKittyLlmopsArchitecture,
  fetchAdminManagers,
  fetchAdminMindbotConfigs,
  fetchAdminMindbotStreamingStatus,
  fetchAdminMindbotUsageEvents,
  fetchAdminMindbotUsageThreadEvents,
  fetchAdminMindmateDifyDefault,
  fetchAdminOrganization,
  fetchAdminOrganizationInvites,
  fetchAdminOrganizationManagers,
  fetchAdminOrganizationMindmateDifyHealth,
  fetchAdminOrganizations,
  fetchAdminOrganizationUsers,
  fetchAdminPerformanceLive,
  fetchAdminPlatformRoleMembers,
  fetchAdminSchoolStats,
  fetchAdminSchoolTokenStats,
  fetchAdminSchoolTrends,
  fetchAdminSchoolUsers,
  fetchAdminStats,
  fetchAdminStatsTrends,
  fetchAdminStatsTrendsOrganization,
  fetchAdminStatsTrendsUser,
  fetchAdminTeacherUsage,
  fetchAdminTeacherUsageConfig,
  fetchAdminTeacherUsageUserDetail,
  fetchAdminTeacherUsageUsers,
  fetchAdminTokenStats,
  fetchAdminUser,
  fetchAdminUsers,
  fetchAdminMarketsListings,
  fetchAdminMarketsOrders,
  fetchAdminMarketsStats,
  fetchAdminMarketsSubscriptions,
  type AdminUsersQuery,
} from './adminApi'
import { ADMIN_STALE_MS, adminKeys } from './adminKeys'

// ============================================================================
// Organizations
// ============================================================================

export function useAdminOrganizations(options?: { enabled?: MaybeRefOrGetter<boolean> }) {
  return useQuery({
    queryKey: adminKeys.organizations(),
    queryFn: fetchAdminOrganizations,
    staleTime: ADMIN_STALE_MS.organizations,
    enabled: options?.enabled,
  })
}

export function useAdminOrganization(
  orgId: MaybeRefOrGetter<number | null | undefined>,
  options?: { enabled?: MaybeRefOrGetter<boolean> }
) {
  return useQuery({
    queryKey: computed(() => adminKeys.organization(toValue(orgId) ?? 0)),
    queryFn: () => {
      const id = toValue(orgId)
      if (id == null) {
        throw new Error('Organization id is required')
      }
      return fetchAdminOrganization(id)
    },
    staleTime: ADMIN_STALE_MS.organizations,
    enabled: computed(() => {
      const id = toValue(orgId)
      const extraEnabled = options?.enabled == null ? true : toValue(options.enabled)
      return extraEnabled && id != null
    }),
  })
}

export function useAdminOrganizationManagers(
  orgId: MaybeRefOrGetter<number | null | undefined>,
  options?: { enabled?: MaybeRefOrGetter<boolean> }
) {
  return useQuery({
    queryKey: computed(() => adminKeys.organizationManagers(toValue(orgId) ?? 0)),
    queryFn: () => {
      const id = toValue(orgId)
      if (id == null) {
        throw new Error('Organization id is required')
      }
      return fetchAdminOrganizationManagers(id)
    },
    staleTime: ADMIN_STALE_MS.organizations,
    enabled: computed(() => {
      const id = toValue(orgId)
      const extraEnabled = options?.enabled == null ? true : toValue(options.enabled)
      return extraEnabled && id != null
    }),
  })
}

export function useAdminOrganizationUsers(
  orgId: MaybeRefOrGetter<number | null | undefined>,
  options?: { enabled?: MaybeRefOrGetter<boolean> }
) {
  return useQuery({
    queryKey: computed(() => adminKeys.organizationUsers(toValue(orgId) ?? 0)),
    queryFn: () => {
      const id = toValue(orgId)
      if (id == null) {
        throw new Error('Organization id is required')
      }
      return fetchAdminOrganizationUsers(id)
    },
    staleTime: ADMIN_STALE_MS.organizations,
    enabled: computed(() => {
      const id = toValue(orgId)
      const extraEnabled = options?.enabled == null ? true : toValue(options.enabled)
      return extraEnabled && id != null
    }),
  })
}

export function useAdminOrganizationMindmateDifyHealth(
  orgId: MaybeRefOrGetter<number | null | undefined>,
  options?: { enabled?: MaybeRefOrGetter<boolean> }
) {
  return useQuery({
    queryKey: computed(() => adminKeys.organizationMindmateDifyHealth(toValue(orgId) ?? 0)),
    queryFn: () => {
      const id = toValue(orgId)
      if (id == null) {
        throw new Error('Organization id is required')
      }
      return fetchAdminOrganizationMindmateDifyHealth(id)
    },
    staleTime: ADMIN_STALE_MS.default,
    enabled: computed(() => {
      const id = toValue(orgId)
      const extraEnabled = options?.enabled == null ? true : toValue(options.enabled)
      return extraEnabled && id != null
    }),
  })
}

export function useAdminMindmateDifyDefault(options?: { enabled?: MaybeRefOrGetter<boolean> }) {
  return useQuery({
    queryKey: adminKeys.mindmateDifyDefault(),
    queryFn: fetchAdminMindmateDifyDefault,
    staleTime: ADMIN_STALE_MS.default,
    enabled: options?.enabled,
  })
}

// ============================================================================
// Users
// ============================================================================

export function useAdminUsers(
  query: MaybeRefOrGetter<AdminUsersQuery> = {},
  options?: { enabled?: MaybeRefOrGetter<boolean> }
) {
  return useQuery({
    queryKey: computed(() => adminKeys.users(toValue(query) as Record<string, string | number>)),
    queryFn: () => fetchAdminUsers(toValue(query)),
    staleTime: ADMIN_STALE_MS.default,
    enabled: options?.enabled,
  })
}

export function useAdminUser(
  userId: MaybeRefOrGetter<number | null | undefined>,
  organizationId?: MaybeRefOrGetter<number | null | undefined>,
  options?: { enabled?: MaybeRefOrGetter<boolean> }
) {
  return useQuery({
    queryKey: computed(() =>
      adminKeys.user(toValue(userId) ?? 0, toValue(organizationId))
    ),
    queryFn: () => {
      const id = toValue(userId)
      if (id == null) {
        throw new Error('User id is required')
      }
      return fetchAdminUser(id, toValue(organizationId))
    },
    staleTime: ADMIN_STALE_MS.default,
    enabled: computed(() => {
      const id = toValue(userId)
      const extraEnabled = options?.enabled == null ? true : toValue(options.enabled)
      return extraEnabled && id != null
    }),
  })
}

export function useAdminSchoolUsers(
  query: MaybeRefOrGetter<Record<string, string | number | undefined>> = {},
  options?: { enabled?: MaybeRefOrGetter<boolean> }
) {
  return useQuery({
    queryKey: computed(() => adminKeys.schoolUsers(toValue(query))),
    queryFn: () => fetchAdminSchoolUsers(toValue(query)),
    staleTime: ADMIN_STALE_MS.default,
    enabled: options?.enabled,
  })
}

// ============================================================================
// Stats, trends, token stats
// ============================================================================

export function useAdminStats(options?: { enabled?: MaybeRefOrGetter<boolean> }) {
  return useQuery({
    queryKey: adminKeys.stats(),
    queryFn: ({ signal }) => fetchAdminStats(signal),
    staleTime: ADMIN_STALE_MS.stats,
    enabled: options?.enabled,
  })
}

export function useAdminTokenStats(
  organizationId?: MaybeRefOrGetter<number | null | undefined>,
  options?: { enabled?: MaybeRefOrGetter<boolean> }
) {
  return useQuery({
    queryKey: computed(() => adminKeys.tokenStats(toValue(organizationId))),
    queryFn: ({ signal }) => fetchAdminTokenStats(toValue(organizationId), signal),
    staleTime: ADMIN_STALE_MS.stats,
    enabled: options?.enabled,
  })
}

export function useAdminStatsTrends(
  params: MaybeRefOrGetter<{
    metric?: string
    days?: number
    service?: string | null
  }> = {},
  options?: { enabled?: MaybeRefOrGetter<boolean> }
) {
  return useQuery({
    queryKey: computed(() => adminKeys.trends(toValue(params))),
    queryFn: ({ signal }) => fetchAdminStatsTrends(toValue(params), signal),
    staleTime: ADMIN_STALE_MS.stats,
    enabled: options?.enabled,
  })
}

export function useAdminStatsTrendsOrganization(
  params: MaybeRefOrGetter<{
    organization_id?: number
    organization_name?: string
    metric?: string
    days?: number
    hourly?: boolean
    service?: string | null
  }> = {},
  options?: { enabled?: MaybeRefOrGetter<boolean> }
) {
  return useQuery({
    queryKey: computed(() => adminKeys.trendsOrganization(toValue(params))),
    queryFn: ({ signal }) => fetchAdminStatsTrendsOrganization(toValue(params), signal),
    staleTime: ADMIN_STALE_MS.stats,
    enabled: options?.enabled,
  })
}

export function useAdminStatsTrendsUser(
  params: MaybeRefOrGetter<{
    user_id: number
    days?: number
    metric?: string
  }>,
  options?: { enabled?: MaybeRefOrGetter<boolean> }
) {
  return useQuery({
    queryKey: computed(() => adminKeys.trendsUser(toValue(params))),
    queryFn: ({ signal }) => fetchAdminStatsTrendsUser(toValue(params), signal),
    staleTime: ADMIN_STALE_MS.stats,
    enabled: computed(() => {
      const p = toValue(params)
      const extraEnabled = options?.enabled == null ? true : toValue(options.enabled)
      return extraEnabled && p.user_id > 0
    }),
  })
}

export function useAdminSchoolStats(
  organizationId: MaybeRefOrGetter<number | null | undefined>,
  options?: { enabled?: MaybeRefOrGetter<boolean> }
) {
  return useQuery({
    queryKey: computed(() => adminKeys.schoolStats(toValue(organizationId) ?? 0)),
    queryFn: ({ signal }) => {
      const id = toValue(organizationId)
      if (id == null) {
        throw new Error('Organization id is required')
      }
      return fetchAdminSchoolStats(id, signal)
    },
    staleTime: ADMIN_STALE_MS.stats,
    enabled: computed(() => {
      const id = toValue(organizationId)
      const extraEnabled = options?.enabled == null ? true : toValue(options.enabled)
      return extraEnabled && id != null
    }),
  })
}

export function useAdminSchoolTrends(
  params: MaybeRefOrGetter<{
    organization_id: number
    days?: number
    hourly?: boolean
  }>,
  options?: { enabled?: MaybeRefOrGetter<boolean> }
) {
  return useQuery({
    queryKey: computed(() => adminKeys.schoolTrends(toValue(params))),
    queryFn: ({ signal }) => fetchAdminSchoolTrends(toValue(params), signal),
    staleTime: ADMIN_STALE_MS.stats,
    enabled: computed(() => {
      const p = toValue(params)
      const extraEnabled = options?.enabled == null ? true : toValue(options.enabled)
      return extraEnabled && p.organization_id > 0
    }),
  })
}

export function useAdminSchoolTokenStats(
  organizationId: MaybeRefOrGetter<number | null | undefined>,
  options?: { enabled?: MaybeRefOrGetter<boolean> }
) {
  return useQuery({
    queryKey: computed(() => adminKeys.schoolTokenStats(toValue(organizationId) ?? 0)),
    queryFn: ({ signal }) => {
      const id = toValue(organizationId)
      if (id == null) {
        throw new Error('Organization id is required')
      }
      return fetchAdminSchoolTokenStats(id, signal)
    },
    staleTime: ADMIN_STALE_MS.stats,
    enabled: computed(() => {
      const id = toValue(organizationId)
      const extraEnabled = options?.enabled == null ? true : toValue(options.enabled)
      return extraEnabled && id != null
    }),
  })
}

// ============================================================================
// API keys
// ============================================================================

export function useAdminApiKeys(options?: { enabled?: MaybeRefOrGetter<boolean> }) {
  return useQuery({
    queryKey: adminKeys.apiKeys(),
    queryFn: fetchAdminApiKeys,
    staleTime: ADMIN_STALE_MS.default,
    enabled: options?.enabled,
  })
}

// ============================================================================
// MindBot
// ============================================================================

export function useAdminMindbotConfigs(
  params: MaybeRefOrGetter<{ limit?: number; after_id?: number }> = {},
  options?: { enabled?: MaybeRefOrGetter<boolean> }
) {
  return useQuery({
    queryKey: computed(() => adminKeys.mindbot.configs(toValue(params))),
    queryFn: () => fetchAdminMindbotConfigs(toValue(params)),
    staleTime: ADMIN_STALE_MS.default,
    enabled: options?.enabled,
  })
}

export function useAdminMindbotStreamingStatus(
  configId: MaybeRefOrGetter<number | null | undefined>,
  query?: MaybeRefOrGetter<string>,
  options?: { enabled?: MaybeRefOrGetter<boolean> }
) {
  return useQuery({
    queryKey: computed(() =>
      adminKeys.mindbot.streamingStatus(toValue(configId) ?? 0, toValue(query))
    ),
    queryFn: () => {
      const id = toValue(configId)
      if (id == null) {
        throw new Error('Config id is required')
      }
      return fetchAdminMindbotStreamingStatus(id, toValue(query))
    },
    staleTime: ADMIN_STALE_MS.default,
    enabled: computed(() => {
      const id = toValue(configId)
      const extraEnabled = options?.enabled == null ? true : toValue(options.enabled)
      return extraEnabled && id != null
    }),
  })
}

export function useAdminMindbotUsageEvents(
  orgId: MaybeRefOrGetter<number | null | undefined>,
  params: MaybeRefOrGetter<Record<string, string | number | undefined>> = {},
  options?: { enabled?: MaybeRefOrGetter<boolean> }
) {
  return useQuery({
    queryKey: computed(() =>
      adminKeys.mindbot.usageEvents(toValue(orgId) ?? 0, toValue(params))
    ),
    queryFn: () => {
      const id = toValue(orgId)
      if (id == null) {
        throw new Error('Organization id is required')
      }
      return fetchAdminMindbotUsageEvents(id, toValue(params))
    },
    staleTime: ADMIN_STALE_MS.default,
    enabled: computed(() => {
      const id = toValue(orgId)
      const extraEnabled = options?.enabled == null ? true : toValue(options.enabled)
      return extraEnabled && id != null
    }),
  })
}

export function useAdminMindbotUsageThreadEvents(
  orgId: MaybeRefOrGetter<number | null | undefined>,
  params: MaybeRefOrGetter<Record<string, string | number | undefined>> = {},
  options?: { enabled?: MaybeRefOrGetter<boolean> }
) {
  return useQuery({
    queryKey: computed(() =>
      adminKeys.mindbot.usageThreadEvents(toValue(orgId) ?? 0, toValue(params))
    ),
    queryFn: () => {
      const id = toValue(orgId)
      if (id == null) {
        throw new Error('Organization id is required')
      }
      return fetchAdminMindbotUsageThreadEvents(id, toValue(params))
    },
    staleTime: ADMIN_STALE_MS.default,
    enabled: computed(() => {
      const id = toValue(orgId)
      const extraEnabled = options?.enabled == null ? true : toValue(options.enabled)
      return extraEnabled && id != null
    }),
  })
}

// ============================================================================
// Markets
// ============================================================================

export function useAdminMarketsStats(options?: { enabled?: MaybeRefOrGetter<boolean> }) {
  return useQuery({
    queryKey: adminKeys.markets.stats(),
    queryFn: fetchAdminMarketsStats,
    staleTime: ADMIN_STALE_MS.default,
    enabled: options?.enabled,
  })
}

export function useAdminMarketsOrders(
  limit = 200,
  options?: { enabled?: MaybeRefOrGetter<boolean> }
) {
  return useQuery({
    queryKey: adminKeys.markets.orders(limit),
    queryFn: () => fetchAdminMarketsOrders(limit),
    staleTime: ADMIN_STALE_MS.default,
    enabled: options?.enabled,
  })
}

export function useAdminMarketsListings(
  limit = 500,
  options?: { enabled?: MaybeRefOrGetter<boolean> }
) {
  return useQuery({
    queryKey: adminKeys.markets.listings(limit),
    queryFn: () => fetchAdminMarketsListings(limit),
    staleTime: ADMIN_STALE_MS.default,
    enabled: options?.enabled,
  })
}

export function useAdminMarketsSubscriptions(
  limit = 200,
  options?: { enabled?: MaybeRefOrGetter<boolean> }
) {
  return useQuery({
    queryKey: adminKeys.markets.subscriptions(limit),
    queryFn: () => fetchAdminMarketsSubscriptions(limit),
    staleTime: ADMIN_STALE_MS.default,
    enabled: options?.enabled,
  })
}

// ============================================================================
// Roles
// ============================================================================

export function useAdminAdmins(options?: { enabled?: MaybeRefOrGetter<boolean> }) {
  return useQuery({
    queryKey: adminKeys.roles.admins(),
    queryFn: fetchAdminAdmins,
    staleTime: ADMIN_STALE_MS.default,
    enabled: options?.enabled,
  })
}

export function useAdminPlatformRoleMembers(
  role: MaybeRefOrGetter<string>,
  options?: { enabled?: MaybeRefOrGetter<boolean> }
) {
  return useQuery({
    queryKey: computed(() => adminKeys.roles.platformMembers(toValue(role))),
    queryFn: () => fetchAdminPlatformRoleMembers(toValue(role)),
    staleTime: ADMIN_STALE_MS.default,
    enabled: computed(() => {
      const roleValue = toValue(role)
      const extraEnabled = options?.enabled == null ? true : toValue(options.enabled)
      return extraEnabled && roleValue.length > 0
    }),
  })
}

export function useAdminManagers(options?: { enabled?: MaybeRefOrGetter<boolean> }) {
  return useQuery({
    queryKey: adminKeys.roles.managers(),
    queryFn: fetchAdminManagers,
    staleTime: ADMIN_STALE_MS.default,
    enabled: options?.enabled,
  })
}

// ============================================================================
// Invites
// ============================================================================

export function useAdminOrganizationInvites(options?: { enabled?: MaybeRefOrGetter<boolean> }) {
  return useQuery({
    queryKey: adminKeys.invites.organizations(),
    queryFn: fetchAdminOrganizationInvites,
    staleTime: ADMIN_STALE_MS.default,
    enabled: options?.enabled,
  })
}

// ============================================================================
// Teacher usage
// ============================================================================

export function useAdminTeacherUsage(options?: { enabled?: MaybeRefOrGetter<boolean> }) {
  return useQuery({
    queryKey: adminKeys.teacherUsage.overview(),
    queryFn: fetchAdminTeacherUsage,
    staleTime: ADMIN_STALE_MS.stats,
    enabled: options?.enabled,
  })
}

export function useAdminTeacherUsageUsers(
  page: MaybeRefOrGetter<number> = 1,
  pageSize = 50,
  options?: { enabled?: MaybeRefOrGetter<boolean> }
) {
  return useQuery({
    queryKey: computed(() => adminKeys.teacherUsage.users(toValue(page), pageSize)),
    queryFn: () => fetchAdminTeacherUsageUsers(toValue(page), pageSize),
    staleTime: ADMIN_STALE_MS.stats,
    enabled: options?.enabled,
  })
}

export function useAdminTeacherUsageUserDetail(
  userId: MaybeRefOrGetter<number | null | undefined>,
  options?: { enabled?: MaybeRefOrGetter<boolean> }
) {
  return useQuery({
    queryKey: computed(() => adminKeys.teacherUsage.userDetail(toValue(userId) ?? 0)),
    queryFn: () => {
      const id = toValue(userId)
      if (id == null) {
        throw new Error('User id is required')
      }
      return fetchAdminTeacherUsageUserDetail(id)
    },
    staleTime: ADMIN_STALE_MS.stats,
    enabled: computed(() => {
      const id = toValue(userId)
      const extraEnabled = options?.enabled == null ? true : toValue(options.enabled)
      return extraEnabled && id != null
    }),
  })
}

export function useAdminTeacherUsageConfig(options?: { enabled?: MaybeRefOrGetter<boolean> }) {
  return useQuery({
    queryKey: adminKeys.teacherUsage.config(),
    queryFn: fetchAdminTeacherUsageConfig,
    staleTime: ADMIN_STALE_MS.default,
    enabled: options?.enabled,
  })
}

// ============================================================================
// Database
// ============================================================================

export function useAdminDatabaseStats(options?: { enabled?: MaybeRefOrGetter<boolean> }) {
  return useQuery({
    queryKey: adminKeys.database.stats(),
    queryFn: fetchAdminDatabaseStats,
    staleTime: ADMIN_STALE_MS.default,
    enabled: options?.enabled,
  })
}

export function useAdminDatabaseOrphans(options?: { enabled?: MaybeRefOrGetter<boolean> }) {
  return useQuery({
    queryKey: adminKeys.database.orphans(),
    queryFn: fetchAdminDatabaseOrphans,
    staleTime: ADMIN_STALE_MS.default,
    enabled: options?.enabled,
  })
}

// ============================================================================
// Performance
// ============================================================================

export function useAdminPerformanceLive(options?: {
  enabled?: MaybeRefOrGetter<boolean>
  refetchInterval?: number | false
}) {
  return useQuery({
    queryKey: adminKeys.performance.live(),
    queryFn: ({ signal }) => fetchAdminPerformanceLive(signal),
    staleTime: ADMIN_STALE_MS.performance,
    refetchInterval: options?.refetchInterval ?? false,
    enabled: options?.enabled,
  })
}

// ============================================================================
// Kitty LLMOps
// ============================================================================

export function useAdminKittyLlmopsArchitecture(options?: {
  enabled?: MaybeRefOrGetter<boolean>
}) {
  return useQuery({
    queryKey: adminKeys.kittyLlmops.architecture(),
    queryFn: fetchAdminKittyLlmopsArchitecture,
    staleTime: ADMIN_STALE_MS.default,
    enabled: options?.enabled,
  })
}

// ============================================================================
// Features (admin settings tab reads)
// ============================================================================

export function useAdminFeatureOrgAccess(options?: { enabled?: MaybeRefOrGetter<boolean> }) {
  return useQuery({
    queryKey: [...adminKeys.all, 'feature-org-access'] as const,
    queryFn: fetchAdminFeatureOrgAccess,
    staleTime: ADMIN_STALE_MS.default,
    enabled: options?.enabled,
  })
}

export function useAdminConfigFeatures(options?: { enabled?: MaybeRefOrGetter<boolean> }) {
  return useQuery({
    queryKey: [...adminKeys.all, 'config-features'] as const,
    queryFn: fetchAdminConfigFeatures,
    staleTime: ADMIN_STALE_MS.default,
    enabled: options?.enabled,
  })
}
