/**
 * Admin API Helpers
 *
 * Typed fetch helpers for admin panel endpoints using apiRequest.
 */
import type { MindbotConfigRow } from '@/components/admin/mindbotConfigTypes'
import type { MindbotUsageEventRow } from '@/components/admin/mindbotUsageTypes'
import type {
  AdminUser,
  EnvAdmin,
  ManagerUser,
  PlatformRoleMember,
} from '@/composables/admin/useAdminRoleControl'
import type {
  GroupStats,
  Teacher,
  UserDetailData,
} from '@/composables/teacherUsage/teacherUsageTypes'
import type { FeatureOrgAccessEntry } from '@/stores/featureFlags'
import { apiRequest, apiUpload } from '@/utils/apiClient'
import { httpErrorDetail } from '@/utils/httpErrorDetail'

// ============================================================================
// Core helper
// ============================================================================

export async function adminFetchJson<T>(
  endpoint: string,
  options: RequestInit = {},
  fallbackMessage = 'Request failed'
): Promise<T> {
  const res = await apiRequest(endpoint, options)
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(httpErrorDetail(data) || fallbackMessage)
  }
  if (res.status === 204) {
    return undefined as T
  }
  const text = await res.text()
  if (!text.trim()) {
    return undefined as T
  }
  return JSON.parse(text) as T
}

function buildQuery(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') {
      continue
    }
    search.set(key, String(value))
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

// ============================================================================
// Shared types
// ============================================================================

export interface AdminPagination {
  page: number
  page_size: number
  total: number
  total_pages: number
}

export interface AdminUsersResponse {
  users: Record<string, unknown>[]
  pagination: AdminPagination
}

export interface AdminUsersQuery {
  page?: number
  page_size?: number
  search?: string
  organization_id?: number | string
}

export interface AdminStatsResponse {
  total_users?: number
  total_organizations?: number
  recent_registrations?: number
  token_stats?: { total_tokens?: number }
  token_stats_by_org?: Record<string, unknown>
  token_stats_by_org_mindgraph?: Record<string, unknown>
  token_stats_by_org_mindmate?: Record<string, unknown>
  top_users?: Array<Record<string, unknown>>
}

export interface AdminTokenPeriodStats {
  input_tokens: number
  output_tokens: number
  total_tokens: number
  request_count?: number
}

export interface AdminPlatformTokenStats {
  today: AdminTokenPeriodStats
  past_week: AdminTokenPeriodStats
  past_month: AdminTokenPeriodStats
  total: AdminTokenPeriodStats
  by_service: Record<string, Record<string, AdminTokenPeriodStats>>
}

export interface AdminTrendPoint {
  date: string
  value: number
}

export interface AdminTrendsResponse {
  labels?: string[]
  values?: number[]
  points?: AdminTrendPoint[]
  data?: Array<{ date: string; value: number; input?: number; output?: number }>
  [key: string]: unknown
}

export interface AdminApiKeyRow {
  id: number
  key: string
  name: string
  description: string | null
  quota_limit: number | null
  usage_count: number
  is_active: boolean
  created_at: string | null
  last_used_at: string | null
  expires_at: string | null
  token_stats: AdminTokenPeriodStats
}

export interface AdminMarketsStats {
  orders_total: number
  orders_paid: number
  orders_pending: number
}

export interface AdminMarketOrderRow {
  id: number
  user_id: number
  user_email_or_phone: string | null
  listing_id: number
  listing_title: string
  out_trade_no: string
  status: string
  amount_minor: number
  currency: string
  alipay_trade_no: string | null
  created_at: string
  paid_at: string | null
}

export interface AdminMarketListingRow {
  id: number
  slug: string
  listing_kind: string
  title: string
  price_minor: number
  currency: string
  is_active: boolean
}

export interface AdminMarketSubscriptionRow {
  id: number
  user_id: number
  user_email_or_phone: string | null
  listing_id: number
  listing_title: string
  alipay_agreement_id: string | null
  status: string
  current_period_end: string | null
}

export interface AdminSchoolStatsResponse {
  organization?: Record<string, unknown>
  token_stats?: { total_tokens?: number }
  quotas?: Record<string, unknown>
  top_users?: Array<Record<string, unknown>>
}

export interface AdminTeacherUsageOverview {
  stats?: Record<string, number>
  groupStats?: Record<string, GroupStats>
}

export interface AdminTeacherUsageUsersResponse {
  users: Teacher[]
  total: number
  page: number
}

export interface AdminTeacherUsageConfig {
  continuous: Record<string, number>
  rejection: Record<string, number>
  stopped: Record<string, number>
  intermittent: Record<string, number>
}

export interface AdminMindbotConfigsResponse {
  items: MindbotConfigRow[]
  has_more?: boolean
  next_after_id?: number | null
}

export interface AdminFeatureFlagsPayload {
  feature_rag_chunk_test?: boolean
  feature_course?: boolean
  feature_template?: boolean
  feature_community?: boolean
  feature_askonce?: boolean
  feature_school_zone?: boolean
  feature_debateverse?: boolean
  feature_knowledge_space?: boolean
  feature_library?: boolean
  feature_gewe?: boolean
  feature_smart_response?: boolean
  feature_teacher_usage?: boolean
  feature_workshop_chat?: boolean
  feature_markets?: boolean
  feature_mindbot?: boolean
  feature_kitty_agent?: boolean
  feature_org_access?: Record<string, FeatureOrgAccessEntry>
}

// ============================================================================
// Organizations
// ============================================================================

export interface AdminOrganizationOption {
  id: number
  name: string
  code: string
}

export async function fetchAdminOrganizations(): Promise<AdminOrganizationOption[]> {
  return adminFetchJson<AdminOrganizationOption[]>('/api/auth/admin/organizations')
}

export async function fetchAdminOrganization(orgId: number): Promise<Record<string, unknown>> {
  return adminFetchJson(`/api/auth/admin/organizations/${orgId}`)
}

export async function fetchAdminOrganizationManagers(orgId: number): Promise<AdminUser[]> {
  const data = await adminFetchJson<{ managers?: AdminUser[] }>(
    `/api/auth/admin/organizations/${orgId}/managers`
  )
  return data.managers ?? []
}

export async function fetchAdminOrganizationUsers(orgId: number): Promise<AdminUser[]> {
  const data = await adminFetchJson<{ users?: AdminUser[] }>(
    `/api/auth/admin/organizations/${orgId}/users`
  )
  return data.users ?? []
}

export async function fetchAdminOrganizationMindmateDifyHealth(
  orgId: number
): Promise<Record<string, unknown>> {
  return adminFetchJson(`/api/auth/admin/organizations/${orgId}/mindmate-dify-health`)
}

export async function fetchAdminMindmateDifyDefault(): Promise<Record<string, unknown>> {
  return adminFetchJson('/api/auth/admin/mindmate/dify-default')
}

export async function createAdminOrganization(
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  return adminFetchJson('/api/auth/admin/organizations', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function updateAdminOrganization(
  orgId: number,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  return adminFetchJson(`/api/auth/admin/organizations/${orgId}`, {
    method: 'PUT',
    body: JSON.stringify(body),
  })
}

export async function deleteAdminOrganization(
  orgId: number,
  deleteUsers = false
): Promise<void> {
  const qs = deleteUsers ? '?delete_users=true' : ''
  await adminFetchJson(`/api/auth/admin/organizations/${orgId}${qs}`, { method: 'DELETE' })
}

export async function addAdminOrganizationManager(orgId: number, userId: number): Promise<void> {
  await adminFetchJson(`/api/auth/admin/organizations/${orgId}/managers/${userId}`, {
    method: 'PUT',
  })
}

export async function removeAdminOrganizationManager(orgId: number, userId: number): Promise<void> {
  await adminFetchJson(`/api/auth/admin/organizations/${orgId}/managers/${userId}`, {
    method: 'DELETE',
  })
}

export async function uploadAdminOrganizationMindmateAvatar(
  orgId: number,
  formData: FormData
): Promise<Record<string, unknown>> {
  const res = await apiUpload(`/api/auth/admin/organizations/${orgId}/mindmate-avatar`, formData)
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(httpErrorDetail(data) || 'Avatar upload failed')
  }
  return res.json()
}

export async function probeAdminMindmateDifyHealthDraft(
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  return adminFetchJson('/api/auth/admin/mindmate-dify-health-draft', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function probeAdminOrganizationMindmateDifyHealth(
  orgId: number,
  body: Record<string, string> = {}
): Promise<Record<string, unknown>> {
  return adminFetchJson(`/api/auth/admin/organizations/${orgId}/mindmate-dify-health`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

// ============================================================================
// Users
// ============================================================================

export async function fetchAdminUsers(query: AdminUsersQuery = {}): Promise<AdminUsersResponse> {
  const qs = buildQuery({
    page: query.page ?? 1,
    page_size: query.page_size ?? 20,
    search: query.search ?? '',
    organization_id: query.organization_id,
  })
  return adminFetchJson(`/api/auth/admin/users${qs}`)
}

export async function fetchAdminUser(
  userId: number,
  organizationId?: number | null
): Promise<Record<string, unknown>> {
  const qs =
    organizationId != null ? buildQuery({ organization_id: organizationId }) : ''
  const base =
    organizationId != null
      ? `/api/auth/admin/school/users/${userId}`
      : `/api/auth/admin/users/${userId}`
  return adminFetchJson(`${base}${qs}`)
}

export async function updateAdminUser(
  userId: number,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  return adminFetchJson(`/api/auth/admin/users/${userId}`, {
    method: 'PUT',
    body: JSON.stringify(body),
  })
}

export async function deleteAdminUser(userId: number): Promise<void> {
  await adminFetchJson(`/api/auth/admin/users/${userId}`, { method: 'DELETE' })
}

export async function updateAdminUserRole(userId: number, role: string): Promise<void> {
  await adminFetchJson(
    `/api/auth/admin/users/${userId}/role?role=${encodeURIComponent(role)}`,
    { method: 'PUT' }
  )
}

export async function fetchAdminSchoolUsers(
  query: Record<string, string | number | undefined>
): Promise<AdminUsersResponse> {
  return adminFetchJson(`/api/auth/admin/school/users${buildQuery(query)}`)
}

export async function createAdminSchoolUser(
  body: Record<string, unknown>,
  organizationId: number
): Promise<Record<string, unknown>> {
  return adminFetchJson(
    `/api/auth/admin/school/users${buildQuery({ organization_id: organizationId })}`,
    { method: 'POST', body: JSON.stringify(body) }
  )
}

export async function createAdminSchoolUsersBatch(
  body: Record<string, unknown>,
  organizationId: number
): Promise<Record<string, unknown>> {
  return adminFetchJson(
    `/api/auth/admin/school/users/batch${buildQuery({ organization_id: organizationId })}`,
    { method: 'POST', body: JSON.stringify(body) }
  )
}

export async function updateAdminSchoolUser(
  userId: number,
  organizationId: number,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  return adminFetchJson(
    `/api/auth/admin/school/users/${userId}${buildQuery({ organization_id: organizationId })}`,
    { method: 'PUT', body: JSON.stringify(body) }
  )
}

export async function deleteAdminSchoolUser(userId: number, organizationId: number): Promise<void> {
  await adminFetchJson(
    `/api/auth/admin/school/users/${userId}${buildQuery({ organization_id: organizationId })}`,
    { method: 'DELETE' }
  )
}

// ============================================================================
// Stats, trends, token stats
// ============================================================================

export async function fetchAdminStats(signal?: AbortSignal): Promise<AdminStatsResponse> {
  return adminFetchJson('/api/auth/admin/stats', { signal })
}

export async function fetchAdminTokenStats(
  organizationId?: number | null,
  signal?: AbortSignal
): Promise<AdminPlatformTokenStats> {
  const qs =
    organizationId != null ? buildQuery({ organization_id: organizationId }) : ''
  return adminFetchJson(`/api/auth/admin/token-stats${qs}`, { signal })
}

export async function fetchAdminStatsTrends(
  params: {
    metric?: string
    days?: number
    service?: string | null
  },
  signal?: AbortSignal
): Promise<AdminTrendsResponse> {
  return adminFetchJson(`/api/auth/admin/stats/trends${buildQuery(params)}`, { signal })
}

export async function fetchAdminStatsTrendsOrganization(
  params: {
    organization_id?: number
    organization_name?: string
    metric?: string
    days?: number
    hourly?: boolean
    service?: string | null
  },
  signal?: AbortSignal
): Promise<AdminTrendsResponse> {
  return adminFetchJson(
    `/api/auth/admin/stats/trends/organization${buildQuery(params)}`,
    { signal }
  )
}

export async function fetchAdminStatsTrendsUser(
  params: {
    user_id: number
    days?: number
    metric?: string
  },
  signal?: AbortSignal
): Promise<AdminTrendsResponse> {
  return adminFetchJson(`/api/auth/admin/stats/trends/user${buildQuery(params)}`, { signal })
}

export async function fetchAdminSchoolStats(
  organizationId: number,
  signal?: AbortSignal
): Promise<AdminSchoolStatsResponse> {
  return adminFetchJson(
    `/api/auth/admin/stats/school${buildQuery({ organization_id: organizationId })}`,
    { signal }
  )
}

export async function fetchAdminSchoolTrends(
  params: {
    organization_id: number
    days?: number
    hourly?: boolean
  },
  signal?: AbortSignal
): Promise<AdminTrendsResponse> {
  return adminFetchJson(
    `/api/auth/admin/stats/school/trends${buildQuery(params)}`,
    { signal }
  )
}

export async function fetchAdminSchoolTokenStats(
  organizationId: number,
  signal?: AbortSignal
): Promise<AdminPlatformTokenStats> {
  return adminFetchJson(
    `/api/auth/admin/stats/school/token-stats${buildQuery({ organization_id: organizationId })}`,
    { signal }
  )
}

// ============================================================================
// Roles
// ============================================================================

export async function fetchAdminAdmins(): Promise<{ admins: AdminUser[]; env_admins: EnvAdmin[] }> {
  return adminFetchJson('/api/auth/admin/admins')
}

export async function fetchAdminPlatformRoleMembers(
  role: string
): Promise<PlatformRoleMember[]> {
  const data = await adminFetchJson<{ members?: PlatformRoleMember[] }>(
    `/api/auth/admin/platform-role-members${buildQuery({ role })}`
  )
  return data.members ?? []
}

export async function fetchAdminManagers(): Promise<ManagerUser[]> {
  const data = await adminFetchJson<{ managers?: ManagerUser[] }>(
    '/api/auth/admin/managers'
  )
  return data.managers ?? []
}

// ============================================================================
// API keys
// ============================================================================

export async function fetchAdminApiKeys(): Promise<AdminApiKeyRow[]> {
  return adminFetchJson('/api/auth/admin/api_keys')
}

export async function createAdminApiKey(
  body: Record<string, unknown>
): Promise<{ key?: string } & Record<string, unknown>> {
  return adminFetchJson('/api/auth/admin/api_keys', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function deleteAdminApiKey(id: number): Promise<void> {
  await adminFetchJson(`/api/auth/admin/api_keys/${id}`, { method: 'DELETE' })
}

// ============================================================================
// Invites
// ============================================================================

export async function fetchAdminOrganizationInvites(): Promise<Record<string, unknown>> {
  return adminFetchJson('/api/auth/admin/invites/organizations')
}

// ============================================================================
// MindBot
// ============================================================================

export async function fetchAdminMindbotConfigs(params: {
  limit?: number
  after_id?: number
} = {}): Promise<AdminMindbotConfigsResponse | MindbotConfigRow[]> {
  const limit = params.limit ?? 50
  const qs = buildQuery({
    limit,
    after_id: params.after_id,
  })
  return adminFetchJson(`/api/mindbot/admin/configs${qs}`)
}

export async function fetchAllAdminMindbotConfigs(): Promise<{
  configs: MindbotConfigRow[]
  featureDisabled: boolean
}> {
  const pageSize = 200
  const all: MindbotConfigRow[] = []
  let afterId: number | null = null
  for (;;) {
    const qs = buildQuery({ limit: pageSize, after_id: afterId ?? undefined })
    const res = await apiRequest(`/api/mindbot/admin/configs${qs}`)
    if (res.status === 404) {
      return { configs: [], featureDisabled: true }
    }
    if (!res.ok) {
      throw new Error('configs_fetch_failed')
    }
    const page = (await res.json()) as MindbotConfigRow[] | AdminMindbotConfigsResponse
    const items = Array.isArray(page) ? page : (page.items ?? [])
    all.push(...items)
    if (items.length < pageSize) {
      break
    }
    afterId = items[items.length - 1].id
  }
  return { configs: all, featureDisabled: false }
}

export async function fetchAdminMindbotStreamingStatus(
  configId: number,
  query = ''
): Promise<Record<string, unknown>> {
  return adminFetchJson(
    `/api/mindbot/admin/configs/${configId}/ai-card-streaming-status${query}`
  )
}

export async function fetchAdminMindbotUsageEvents(
  orgId: number,
  params: Record<string, string | number | undefined> = {}
): Promise<MindbotUsageEventRow[]> {
  return adminFetchJson(
    `/api/mindbot/admin/configs/${orgId}/usage-events${buildQuery(params)}`
  )
}

export async function fetchAdminMindbotUsageThreadEvents(
  orgId: number,
  params: Record<string, string | number | undefined> = {}
): Promise<MindbotUsageEventRow[]> {
  return adminFetchJson(
    `/api/mindbot/admin/configs/${orgId}/usage-thread-events${buildQuery(params)}`
  )
}

export async function createAdminMindbotConfig(
  body: Record<string, unknown>
): Promise<MindbotConfigRow> {
  return adminFetchJson('/api/mindbot/admin/configs', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function updateAdminMindbotConfig(
  configId: number,
  body: Record<string, unknown>
): Promise<MindbotConfigRow> {
  return adminFetchJson(`/api/mindbot/admin/configs/${configId}`, {
    method: 'PUT',
    body: JSON.stringify(body),
  })
}

export async function deleteAdminMindbotConfig(configId: number): Promise<void> {
  await adminFetchJson(`/api/mindbot/admin/configs/${configId}`, { method: 'DELETE' })
}

export async function moveAdminMindbotConfig(
  configId: number,
  body: Record<string, unknown>
): Promise<MindbotConfigRow> {
  return adminFetchJson(`/api/mindbot/admin/configs/${configId}/move`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function rotateAdminMindbotCallbackToken(
  configId: number
): Promise<Record<string, unknown>> {
  return adminFetchJson(`/api/mindbot/admin/configs/${configId}/rotate-callback-token`, {
    method: 'POST',
  })
}

// ============================================================================
// Markets
// ============================================================================

export async function fetchAdminMarketsStats(): Promise<AdminMarketsStats> {
  return adminFetchJson('/api/markets/admin/stats')
}

export async function fetchAdminMarketsOrders(
  limit = 200
): Promise<AdminMarketOrderRow[]> {
  return adminFetchJson(`/api/markets/admin/orders${buildQuery({ limit })}`)
}

export async function fetchAdminMarketsListings(
  limit = 500
): Promise<AdminMarketListingRow[]> {
  return adminFetchJson(`/api/markets/admin/listings${buildQuery({ limit })}`)
}

export async function fetchAdminMarketsSubscriptions(
  limit = 200
): Promise<AdminMarketSubscriptionRow[]> {
  return adminFetchJson(`/api/markets/admin/subscriptions${buildQuery({ limit })}`)
}

// ============================================================================
// Features / env (admin settings tab)
// ============================================================================

export async function fetchAdminFeatureOrgAccess(): Promise<Record<string, FeatureOrgAccessEntry>> {
  return adminFetchJson('/api/auth/admin/feature-org-access')
}

export async function fetchAdminConfigFeatures(): Promise<AdminFeatureFlagsPayload> {
  return adminFetchJson('/api/config/features')
}

export async function updateAdminFeatureOrgAccess(
  body: Record<string, FeatureOrgAccessEntry>
): Promise<void> {
  await adminFetchJson('/api/auth/admin/feature-org-access', {
    method: 'PUT',
    body: JSON.stringify(body),
  })
}

export async function updateAdminEnvSettings(
  body: Record<string, unknown>
): Promise<void> {
  await adminFetchJson('/api/auth/admin/env/settings', {
    method: 'PUT',
    body: JSON.stringify(body),
  })
}

export async function reloadAdminEnvRuntime(): Promise<void> {
  await adminFetchJson('/api/auth/admin/env/reload-runtime', { method: 'POST' })
}

// ============================================================================
// Database
// ============================================================================

export async function fetchAdminDatabaseStats(): Promise<Record<string, unknown>> {
  return adminFetchJson('/api/auth/admin/database/stats')
}

export async function scanAdminDatabase(): Promise<Record<string, unknown>> {
  return adminFetchJson('/api/auth/admin/database/scan')
}

export async function fetchAdminDatabaseOrphans(): Promise<Record<string, unknown>> {
  return adminFetchJson('/api/auth/admin/database/orphans')
}

export async function analyzeAdminDatabase(
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  return adminFetchJson('/api/auth/admin/database/analyze', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function cleanupAdminSqliteOrphans(
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  return adminFetchJson('/api/auth/admin/database/cleanup-sqlite-orphans', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function mergeAdminDatabase(
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  return adminFetchJson('/api/auth/admin/database/merge', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function exportAdminDatabase(): Promise<Record<string, unknown>> {
  return adminFetchJson('/api/auth/admin/database/export', { method: 'POST' })
}

export async function importAdminDatabaseDump(
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  return adminFetchJson('/api/auth/admin/database/import-dump', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function analyzeAdminDatabaseDump(
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  return adminFetchJson('/api/auth/admin/database/analyze-dump', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function mergeAdminDatabaseDump(
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  return adminFetchJson('/api/auth/admin/database/merge-dump', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function cleanupAdminDatabaseOrphans(
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  return adminFetchJson('/api/auth/admin/database/cleanup-orphans', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

// ============================================================================
// Performance
// ============================================================================

export async function fetchAdminPerformanceLive(
  signal?: AbortSignal
): Promise<Record<string, unknown>> {
  return adminFetchJson('/api/auth/admin/performance/live', { signal })
}

// ============================================================================
// Kitty LLMOps
// ============================================================================

export async function fetchAdminKittyLlmopsArchitecture(): Promise<Record<string, unknown>> {
  return adminFetchJson('/api/auth/admin/kitty-llmops/architecture')
}

// ============================================================================
// Teacher usage
// ============================================================================

export async function fetchAdminTeacherUsage(): Promise<AdminTeacherUsageOverview> {
  return adminFetchJson('/api/auth/admin/teacher-usage')
}

export async function fetchAdminTeacherUsageUsers(
  page = 1,
  pageSize = 50
): Promise<AdminTeacherUsageUsersResponse> {
  return adminFetchJson(
    `/api/auth/admin/teacher-usage/users${buildQuery({ page, page_size: pageSize })}`
  )
}

export async function fetchAdminTeacherUsageUserDetail(
  userId: number
): Promise<UserDetailData> {
  return adminFetchJson(`/api/auth/admin/teacher-usage/user/${userId}/detail`)
}

export async function fetchAdminTeacherUsageConfig(): Promise<AdminTeacherUsageConfig> {
  return adminFetchJson('/api/auth/admin/teacher-usage/config')
}

export async function updateAdminTeacherUsageConfig(
  body: AdminTeacherUsageConfig
): Promise<void> {
  await adminFetchJson('/api/auth/admin/teacher-usage/config', {
    method: 'PUT',
    body: JSON.stringify(body),
  })
}

export async function recomputeAdminTeacherUsage(): Promise<{ recomputed?: number }> {
  return adminFetchJson('/api/auth/admin/teacher-usage/recompute', { method: 'POST' })
}

// ============================================================================
// Library (admin library tab)
// ============================================================================

export async function scanAdminLibrary(): Promise<Record<string, unknown>> {
  return adminFetchJson('/api/library/admin/scan')
}

export async function registerAdminLibraryBook(
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  return adminFetchJson('/api/library/books/register', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function registerAdminLibraryBooksBatch(
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  return adminFetchJson('/api/library/books/register-batch', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export async function repairAdminLibrary(): Promise<Record<string, unknown>> {
  return adminFetchJson('/api/library/admin/repair', { method: 'POST' })
}

export async function updateAdminLibraryDocumentVisibility(
  docId: number,
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  return adminFetchJson(`/api/library/documents/${docId}/visibility`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

export async function generateAdminLibraryDocumentCover(
  docId: number
): Promise<Record<string, unknown>> {
  return adminFetchJson(`/api/library/admin/documents/${docId}/generate-cover`, {
    method: 'POST',
  })
}

export async function deleteAdminLibraryDocument(
  docId: number,
  deleteFiles = false
): Promise<void> {
  const path = deleteFiles
    ? `/api/library/admin/documents/${docId}?delete_files=true`
    : `/api/library/admin/documents/${docId}`
  await adminFetchJson(path, { method: 'DELETE' })
}

export async function renameAdminLibraryPages(
  body: Record<string, unknown>
): Promise<Record<string, unknown>> {
  return adminFetchJson('/api/library/admin/rename-pages', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}
