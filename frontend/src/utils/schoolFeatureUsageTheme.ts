/**
 * Swiss theme cycling for school feature-usage module cards.
 */
import type { AdminSwissStatTheme } from '@/constants/adminSwissStatTheme'

const MODULE_THEMES: Record<string, AdminSwissStatTheme> = {
  canvas: 'mindgraph',
  mindmate: 'mindmate',
  kitty: 'platform',
  voice_notes: 'integration',
  knowledge: 'storage',
  doc_summary: 'members',
  workshop: 'managers',
  markets: 'neutral',
  library: 'storage',
  showcase: 'success',
  dingtalk: 'integration',
  zhihui: 'platform',
}

export function moduleUsageTheme(key: string): AdminSwissStatTheme {
  return MODULE_THEMES[key] ?? 'members'
}
