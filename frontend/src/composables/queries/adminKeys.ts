/**
 * Admin Query Keys Factory
 *
 * Centralized query keys for Vue Query cache management across admin domains.
 */
export const ADMIN_STALE_MS = {
  organizations: 5 * 60 * 1000,
  stats: 60 * 1000,
  performance: 0,
  default: 60 * 1000,
} as const

export const adminKeys = {
  all: ['admin'] as const,

  organizations: () => [...adminKeys.all, 'organizations'] as const,
  organization: (orgId: number) => [...adminKeys.all, 'organization', orgId] as const,
  organizationManagers: (orgId: number) =>
    [...adminKeys.all, 'organization-managers', orgId] as const,
  organizationUsers: (orgId: number) =>
    [...adminKeys.all, 'organization-users', orgId] as const,
  organizationMindmateDifyHealth: (orgId: number) =>
    [...adminKeys.all, 'organization-mindmate-dify-health', orgId] as const,
  mindmateDifyDefault: () => [...adminKeys.all, 'mindmate-dify-default'] as const,

  users: (params?: Record<string, string | number | undefined>) =>
    [...adminKeys.all, 'users', params ?? {}] as const,
  user: (userId: number, orgId?: number | null) =>
    [...adminKeys.all, 'user', userId, orgId ?? null] as const,
  schoolUsers: (params?: Record<string, string | number | undefined>) =>
    [...adminKeys.all, 'school-users', params ?? {}] as const,

  stats: () => [...adminKeys.all, 'stats'] as const,
  tokenStats: (organizationId?: number | null) =>
    [...adminKeys.all, 'token-stats', organizationId ?? null] as const,
  trends: (params?: Record<string, string | number | boolean | null | undefined>) =>
    [...adminKeys.all, 'trends', params ?? {}] as const,
  trendsOrganization: (params?: Record<string, string | number | boolean | null | undefined>) =>
    [...adminKeys.all, 'trends-organization', params ?? {}] as const,
  trendsUser: (params?: Record<string, string | number | boolean | null | undefined>) =>
    [...adminKeys.all, 'trends-user', params ?? {}] as const,

  schoolStats: (organizationId: number) =>
    [...adminKeys.all, 'school-stats', organizationId] as const,
  schoolTrends: (params?: Record<string, string | number | boolean | undefined>) =>
    [...adminKeys.all, 'school-trends', params ?? {}] as const,
  schoolTokenStats: (organizationId: number) =>
    [...adminKeys.all, 'school-token-stats', organizationId] as const,

  apiKeys: () => [...adminKeys.all, 'api-keys'] as const,

  mindbot: {
    all: () => [...adminKeys.all, 'mindbot'] as const,
    configs: (params?: Record<string, string | number | undefined>) =>
      [...adminKeys.all, 'mindbot', 'configs', params ?? {}] as const,
    streamingStatus: (configId: number, query?: string) =>
      [...adminKeys.all, 'mindbot', 'streaming-status', configId, query ?? ''] as const,
    usageEvents: (orgId: number, params?: Record<string, string | number | undefined>) =>
      [...adminKeys.all, 'mindbot', 'usage-events', orgId, params ?? {}] as const,
    usageThreadEvents: (orgId: number, params?: Record<string, string | number | undefined>) =>
      [...adminKeys.all, 'mindbot', 'usage-thread-events', orgId, params ?? {}] as const,
  },

  markets: {
    all: () => [...adminKeys.all, 'markets'] as const,
    stats: () => [...adminKeys.all, 'markets', 'stats'] as const,
    orders: (limit?: number) => [...adminKeys.all, 'markets', 'orders', limit ?? 200] as const,
    listings: (limit?: number) =>
      [...adminKeys.all, 'markets', 'listings', limit ?? 500] as const,
    subscriptions: (limit?: number) =>
      [...adminKeys.all, 'markets', 'subscriptions', limit ?? 200] as const,
  },

  roles: {
    all: () => [...adminKeys.all, 'roles'] as const,
    admins: () => [...adminKeys.all, 'roles', 'admins'] as const,
    platformMembers: (role: string) =>
      [...adminKeys.all, 'roles', 'platform-members', role] as const,
    managers: () => [...adminKeys.all, 'roles', 'managers'] as const,
  },

  invites: {
    all: () => [...adminKeys.all, 'invites'] as const,
    organizations: () => [...adminKeys.all, 'invites', 'organizations'] as const,
  },

  teacherUsage: {
    all: () => [...adminKeys.all, 'teacher-usage'] as const,
    overview: () => [...adminKeys.all, 'teacher-usage', 'overview'] as const,
    users: (page: number, pageSize: number) =>
      [...adminKeys.all, 'teacher-usage', 'users', page, pageSize] as const,
    userDetail: (userId: number) =>
      [...adminKeys.all, 'teacher-usage', 'user-detail', userId] as const,
    config: () => [...adminKeys.all, 'teacher-usage', 'config'] as const,
  },

  database: {
    all: () => [...adminKeys.all, 'database'] as const,
    stats: () => [...adminKeys.all, 'database', 'stats'] as const,
    orphans: () => [...adminKeys.all, 'database', 'orphans'] as const,
  },

  performance: {
    all: () => [...adminKeys.all, 'performance'] as const,
    live: () => [...adminKeys.all, 'performance', 'live'] as const,
  },

  kittyLlmops: {
    all: () => [...adminKeys.all, 'kitty-llmops'] as const,
    architecture: () => [...adminKeys.all, 'kitty-llmops', 'architecture'] as const,
  },
}
