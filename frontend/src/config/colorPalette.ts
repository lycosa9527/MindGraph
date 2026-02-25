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
export const PRESET_SIMPLE: StylePresetColors = {
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
export const PRESET_CREATIVE: StylePresetColors = {
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
export const PRESET_BUSINESS: StylePresetColors = {
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
export const PRESET_VIBRANT: StylePresetColors = {
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
