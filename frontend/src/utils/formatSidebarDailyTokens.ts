/**
 * Compact daily token usage for the sidebar line under the user name.
 */

export function formatCompactTokenCount(value: number): string {
  const n = Math.max(0, value)
  if (n >= 1_000_000) {
    return `${(n / 1_000_000).toFixed(1)}M`
  }
  if (n >= 1_000) {
    return `${(n / 1_000).toFixed(1)}K`
  }
  return n.toLocaleString()
}

export function formatSidebarDailyTokens(usedToday: number, cap: number): string {
  const usedLabel = formatCompactTokenCount(usedToday)
  if (cap <= 0) {
    return usedLabel
  }
  return `${usedLabel} / ${formatCompactTokenCount(cap)}`
}
