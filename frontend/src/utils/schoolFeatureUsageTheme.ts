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
  askonce: 'success',
  debateverse: 'warn',
  markets: 'neutral',
  library: 'storage',
  showcase: 'success',
  dingtalk: 'integration',
  zhihui: 'platform',
  maite: 'mindgraph',
}

export function moduleUsageTheme(key: string): AdminSwissStatTheme {
  return MODULE_THEMES[key] ?? 'members'
}
