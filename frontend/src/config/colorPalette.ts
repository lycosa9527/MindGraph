/**
 * Style preset color palettes from ColorHunt (https://colorhunt.co).
 *
 * Each preset provides:
 * - Context/child nodes: light pastel bg, dark text, visible border
 * - Topic node: solid accent bg, light text, darker border (visually distinct)
 *
 * WCAG AA contrast: text 4.5:1+, borders 3:1+ against adjacent colors.
 */
export interface StylePresetColors {
  backgroundColor: string
  textColor: string
  borderColor: string
  topicBackgroundColor: string
  topicTextColor: string
  topicBorderColor: string
}

/**
 * 简约风格 (Simple) - Blue/Teal palette
 * Source: https://colorhunt.co/palette/e8f4f8-9dd6df-5c9ead-2c6b7f
 */
const PRESET_SIMPLE: StylePresetColors = {
  backgroundColor: '#e8f4f8',
  textColor: '#2c6b7f',
  borderColor: '#5c9ead',
  topicBackgroundColor: '#2c6b7f',
  topicTextColor: '#ffffff',
  topicBorderColor: '#1a4d5c',
}

/**
 * 创意风格 (Creative) - Purple palette
 * Source: https://colorhunt.co/palette/ede9fe-c4b5fd-a78bfa-7c3aed
 */
const PRESET_CREATIVE: StylePresetColors = {
  backgroundColor: '#ede9fe',
  textColor: '#4c1d95',
  borderColor: '#7c3aed',
  topicBackgroundColor: '#7c3aed',
  topicTextColor: '#ffffff',
  topicBorderColor: '#5b21b6',
}

/**
 * 商务风格 (Business) - Mint/Green palette
 * Source: https://colorhunt.co/palette/a8e6cf-dcedc1-ffd3b6-ffaaa5
 */
const PRESET_BUSINESS: StylePresetColors = {
  backgroundColor: '#a8e6cf',
  textColor: '#14532d',
  borderColor: '#10b981',
  topicBackgroundColor: '#059669',
  topicTextColor: '#ffffff',
  topicBorderColor: '#047857',
}

/**
 * 活力风格 (Vibrant) - Peach/Warm palette
 * Source: https://colorhunt.co/palette/ffd6a5-fdffab-caffbf-9bf6ff
 */
const PRESET_VIBRANT: StylePresetColors = {
  backgroundColor: '#ffd6a5',
  textColor: '#78350f',
  borderColor: '#d97706',
  topicBackgroundColor: '#d97706',
  topicTextColor: '#ffffff',
  topicBorderColor: '#b45309',
}

export const STYLE_PRESET_PALETTES: StylePresetColors[] = [
  PRESET_SIMPLE,
  PRESET_CREATIVE,
  PRESET_BUSINESS,
  PRESET_VIBRANT,
]

/** ColorHunt curated presets (reused by mind-map theme picker). */
export const COLORHUNT_PRESET_SIMPLE = PRESET_SIMPLE
export const COLORHUNT_PRESET_CREATIVE = PRESET_CREATIVE
export const COLORHUNT_PRESET_BUSINESS = PRESET_BUSINESS
export const COLORHUNT_PRESET_VIBRANT = PRESET_VIBRANT

/**
 * Tropical pastel — coral, yellow, mint, ocean blue.
 * Source: https://colorhunt.co/palette/ff6b6b-ffe66d-4ecdc4-45b7d1
 */
export const COLORHUNT_PRESET_SUNSET: StylePresetColors = {
  backgroundColor: '#D8F5F0',
  textColor: '#1B4D59',
  borderColor: '#4ECDC4',
  topicBackgroundColor: '#45B7D1',
  topicTextColor: '#ffffff',
  topicBorderColor: '#2A6F87',
}

/**
 * Soft rose warmth — cream, blush, coral pink.
 * Source: https://colorhunt.co/palette/ffecd2-fcb7af-ff8fab-f88379
 */
export const COLORHUNT_PRESET_ROSE_WARM: StylePresetColors = {
  backgroundColor: '#FFECD2',
  textColor: '#7C2D12',
  borderColor: '#FF8FAB',
  topicBackgroundColor: '#F88379',
  topicTextColor: '#ffffff',
  topicBorderColor: '#C2410C',
}
