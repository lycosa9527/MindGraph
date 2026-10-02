import {
  MIND_MAP_RAINBOW_FAMILIES,
  MIND_MAP_RAINBOW_TOPIC_COLORS,
} from '@/config/mindMapVibrantThemes'

/** Previous Morandi grid. Training text color keeps this list. */
export const FLOATING_TOOLBAR_MORANDI_COLORS: string[] = [
  '#ffffff',
  '#f8fafc',
  '#e2e8f0',
  '#94a3b8',
  '#475569',
  '#1e293b',
  '#dbeafe',
  '#93c5fd',
  '#3b82f6',
  '#1d4ed8',
  '#dcfce7',
  '#86efac',
  '#22c55e',
  '#166534',
  '#fef3c7',
  '#fcd34d',
  '#f59e0b',
  '#b45309',
  '#fce7f3',
  '#f9a8d4',
  '#ec4899',
  '#9d174d',
  '#ede9fe',
  '#a78bfa',
]

/** Diagram node pickers: neutrals, topic blue, then each rainbow family fill and line. */
export const FLOATING_TOOLBAR_COLORS: string[] = [
  '#ffffff',
  '#f8fafc',
  '#e2e8f0',
  '#94a3b8',
  '#475569',
  '#334155',
  '#1e293b',
  MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor,
  ...MIND_MAP_RAINBOW_FAMILIES.map((family) => family.fill),
  ...MIND_MAP_RAINBOW_FAMILIES.map((family) => family.line),
]

export const FLOATING_TOOLBAR_FONT_SIZES = [12, 13, 14, 15, 16, 18, 20, 24, 28, 32] as const
