/**
 * National data-center stat helpers.
 *
 * SSE frames only carry live connected-user ticks. Token / registered
 * totals come from GET /api/public/stats — applying SSE placeholder
 * zeros used to wipe those totals after every reconnect.
 */

export interface DashboardStats {
  connected_users: number
  registered_users: number
  tokens_used_today: number
  total_tokens_used: number
}

export const EMPTY_DASHBOARD_STATS: DashboardStats = {
  connected_users: 0,
  registered_users: 0,
  tokens_used_today: 0,
  total_tokens_used: 0,
}

export function formatCompactNumber(num: number): string {
  if (num >= 1_000_000) {
    return `${(num / 1_000_000).toFixed(1)}M`
  }
  if (num >= 1_000) {
    return `${(num / 1_000).toFixed(1)}K`
  }
  return num.toLocaleString()
}

function asOptionalCount(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined
}

export function applyDashboardStats(
  current: DashboardStats,
  partial: Partial<DashboardStats> | Record<string, unknown>
): DashboardStats {
  return {
    connected_users: asOptionalCount(partial.connected_users) ?? current.connected_users,
    registered_users: asOptionalCount(partial.registered_users) ?? current.registered_users,
    tokens_used_today: asOptionalCount(partial.tokens_used_today) ?? current.tokens_used_today,
    total_tokens_used: asOptionalCount(partial.total_tokens_used) ?? current.total_tokens_used,
  }
}
