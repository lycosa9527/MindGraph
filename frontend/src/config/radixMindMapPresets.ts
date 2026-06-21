import type { StylePresetColors } from '@/config/colorPalette'

/**
 * Radix UI Colors light scales (MIT) — https://www.radix-ui.com/colors
 *
 * Mind-map mapping follows Radix palette composition:
 * step 2 canvas bg, step 8 branch borders, step 9 topic accent,
 * step 10 topic border, step 12 body text on light surfaces.
 */
export const RADIX_COLORS_URL = 'https://www.radix-ui.com/colors'

export type RadixLightScaleSteps = {
  step2: string
  step8: string
  step9: string
  step10: string
  step11: string
  step12: string
}

export type RadixMindMapAccentOverride = {
  topicBackgroundColor?: string
  topicTextColor?: string
  topicBorderColor?: string
  textColor?: string
}

export function radixMindMapSourceNote(scaleName: string): string {
  return `Radix UI ${scaleName} light scale (${RADIX_COLORS_URL})`
}

export function mindMapColorsFromRadixScale(
  steps: RadixLightScaleSteps,
  override?: RadixMindMapAccentOverride
): StylePresetColors {
  return {
    backgroundColor: steps.step2,
    textColor: override?.textColor ?? steps.step12,
    borderColor: steps.step8,
    topicBackgroundColor: override?.topicBackgroundColor ?? steps.step9,
    topicTextColor: override?.topicTextColor ?? '#ffffff',
    topicBorderColor: override?.topicBorderColor ?? steps.step10,
  }
}

/** Committed hex from @radix-ui/colors v3 light scales (no runtime package dependency). */
export const RADIX_LIGHT_MAUVE: RadixLightScaleSteps = {
  step2: '#faf9fb',
  step8: '#bcbac7',
  step9: '#8e8c99',
  step10: '#84828e',
  step11: '#65636d',
  step12: '#211f26',
}

export const RADIX_LIGHT_VIOLET: RadixLightScaleSteps = {
  step2: '#faf8ff',
  step8: '#aa99ec',
  step9: '#6e56cf',
  step10: '#654dc4',
  step11: '#6550b9',
  step12: '#2f265f',
}

export const RADIX_LIGHT_JADE: RadixLightScaleSteps = {
  step2: '#f4fbf7',
  step8: '#56ba9f',
  step9: '#29a383',
  step10: '#26997b',
  step11: '#208368',
  step12: '#1d3b31',
}

export const RADIX_LIGHT_AMBER: RadixLightScaleSteps = {
  step2: '#fefbe9',
  step8: '#e2a336',
  step9: '#ffc53d',
  step10: '#ffba18',
  step11: '#ab6400',
  step12: '#4f3422',
}

export const RADIX_LIGHT_CYAN: RadixLightScaleSteps = {
  step2: '#f2fafb',
  step8: '#3db9cf',
  step9: '#00a2c7',
  step10: '#0797b9',
  step11: '#107d98',
  step12: '#0d3c48',
}

export const RADIX_LIGHT_TEAL: RadixLightScaleSteps = {
  step2: '#f3fbf9',
  step8: '#53b9ab',
  step9: '#12a594',
  step10: '#0d9b8a',
  step11: '#008573',
  step12: '#0d3d38',
}

export const RADIX_LIGHT_CRIMSON: RadixLightScaleSteps = {
  step2: '#fef7f9',
  step8: '#e093b2',
  step9: '#e93d82',
  step10: '#df3478',
  step11: '#cb1d63',
  step12: '#621639',
}
