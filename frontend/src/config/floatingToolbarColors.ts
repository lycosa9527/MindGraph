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

/**
 * Compact document-editor palette (Word / WPS style, trimmed).
 * Columns = hue families; rows = light → dark. Grid renders row-major.
 */
export const FLOATING_TOOLBAR_COLOR_COLUMNS = 8
export const FLOATING_TOOLBAR_THEME_ROWS = 4

/** Gray, Red, Orange, Yellow, Green, Teal, Blue, Purple — each light→dark. */
const DOCUMENT_THEME_COLUMNS: readonly (readonly string[])[] = [
  ['#FFFFFF', '#D1D5DB', '#6B7280', '#111827'],
  ['#FEE2E2', '#F87171', '#DC2626', '#7F1D1D'],
  ['#FFEDD5', '#FB923C', '#EA580C', '#7C2D12'],
  ['#FEF9C3', '#FACC15', '#CA8A04', '#713F12'],
  ['#DCFCE7', '#4ADE80', '#16A34A', '#14532D'],
  ['#CFFAFE', '#22D3EE', '#0891B2', '#164E63'],
  ['#DBEAFE', '#60A5FA', '#2563EB', '#1E3A8A'],
  ['#F3E8FF', '#C084FC', '#9333EA', '#581C87'],
]

function flattenThemeMatrix(columns: readonly (readonly string[])[]): string[] {
  const rowCount = columns[0]?.length ?? 0
  const out: string[] = []
  for (let row = 0; row < rowCount; row += 1) {
    for (const column of columns) {
      const hex = column[row]
      if (hex) out.push(hex)
    }
  }
  return out
}

function uniqueHexAppend(base: string[], extras: readonly string[]): string[] {
  const seen = new Set(base.map((hex) => hex.toLowerCase()))
  const next = [...base]
  for (const hex of extras) {
    const key = hex.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    next.push(hex)
  }
  return next
}

/** Diagram node pickers: compact theme matrix + mind-map rainbow tokens. */
export const FLOATING_TOOLBAR_COLORS: string[] = uniqueHexAppend(
  flattenThemeMatrix(DOCUMENT_THEME_COLUMNS),
  [
    MIND_MAP_RAINBOW_TOPIC_COLORS.topicBackgroundColor,
    ...MIND_MAP_RAINBOW_FAMILIES.map((family) => family.fill),
    ...MIND_MAP_RAINBOW_FAMILIES.map((family) => family.line),
  ]
)

export const FLOATING_TOOLBAR_FONT_SIZES = [12, 13, 14, 15, 16, 18, 20, 24, 28, 32] as const
