/** Semantic Swiss stat card themes — shared across admin management panel. */
export type AdminSwissStatTheme =
  | 'members'
  | 'managers'
  | 'storage'
  | 'mindgraph'
  | 'mindmate'
  | 'integration'
  | 'success'
  | 'platform'
  | 'warn'
  | 'danger'
  | 'neutral'

export const ADMIN_SWISS_STAT_THEMES: readonly AdminSwissStatTheme[] = [
  'members',
  'managers',
  'storage',
  'mindgraph',
  'mindmate',
  'integration',
  'success',
  'platform',
  'warn',
  'danger',
  'neutral',
] as const

/** Legacy quota accent slugs mapped to semantic themes. */
export type AdminSwissQuotaAccent = 'blue' | 'purple' | 'orange'

export function quotaAccentToTheme(accent: AdminSwissQuotaAccent): AdminSwissStatTheme {
  if (accent === 'purple') {
    return 'managers'
  }
  if (accent === 'orange') {
    return 'storage'
  }
  return 'members'
}
