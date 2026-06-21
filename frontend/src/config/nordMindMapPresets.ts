import type { StylePresetColors } from '@/config/colorPalette'

/**
 * Nord palette (MIT) — https://www.nordtheme.com
 *
 * Polar Night, Snow Storm, Frost, and Aurora scales as published by Nord.
 */
export const NORD_URL = 'https://www.nordtheme.com'

export const NORD = {
  polarNight0: '#2E3440',
  polarNight1: '#3B4252',
  polarNight2: '#434C5E',
  polarNight3: '#4C566A',
  snowStorm4: '#D8DEE9',
  snowStorm5: '#E5E9F0',
  snowStorm6: '#ECEFF4',
  frost7: '#8FBCBB',
  frost8: '#88C0D0',
  frost9: '#81A1C1',
  frost10: '#5E81AC',
  aurora11: '#BF616A',
  aurora12: '#D08770',
  aurora13: '#EBCB8B',
  aurora14: '#A3BE8C',
  aurora15: '#B48EAD',
} as const

export type NordMindMapRoles = {
  backgroundColor: string
  textColor: string
  borderColor: string
  topicBackgroundColor: string
  topicTextColor: string
  topicBorderColor: string
}

export function nordMindMapSourceNote(scaleIds: string): string {
  return `Nord ${scaleIds} (${NORD_URL})`
}

export function mindMapColorsFromNord(roles: NordMindMapRoles): StylePresetColors {
  return { ...roles }
}
