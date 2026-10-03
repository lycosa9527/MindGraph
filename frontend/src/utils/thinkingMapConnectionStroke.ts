/**
 * Thinking-map connectors follow the active color theme.
 * Rainbow maps a Material border onto the matching family line.
 * Any other theme paints every connector with that theme's accent.
 */
import { getMindMapThemeById, resolveMindMapThemeId } from '@/config/mindMapThemes'
import { MIND_MAP_RAINBOW_TOPIC_COLORS, isRainbowMindMapTheme } from '@/config/mindMapVibrantThemes'
import { isLegacyConnectorFallback, rainbowLineForLegacyStroke } from '@/utils/thinkingMapChrome'

/** Accent for a solid theme. Rainbow and an unset theme keep the palette. */
export function thinkingMapSolidThemeStroke(themeId: string | null | undefined): string | null {
  if (!themeId || isRainbowMindMapTheme(themeId)) return null
  const resolved = resolveMindMapThemeId(themeId)
  if (resolved !== themeId || isRainbowMindMapTheme(resolved)) return null
  return getMindMapThemeById(resolved).borderColor
}

function rainbowTheme(themeId: string | null | undefined): boolean {
  if (!themeId || isRainbowMindMapTheme(themeId)) return true
  const resolved = resolveMindMapThemeId(themeId)
  return resolved === themeId && isRainbowMindMapTheme(resolved)
}

/**
 * Theme accent when one is active.
 * On rainbow, a Material border becomes that family's line.
 * An old gray fallback becomes the topic border. A custom color stays.
 */
export function resolveThinkingMapConnectorStroke(
  themeId: string | null | undefined,
  paletteStroke: string | null | undefined,
  fallback: string
): string {
  const solid = thinkingMapSolidThemeStroke(themeId)
  if (solid) return solid
  if (!rainbowTheme(themeId)) return paletteStroke ?? fallback
  const familyLine = rainbowLineForLegacyStroke(paletteStroke)
  if (familyLine) return familyLine
  if (paletteStroke && !isLegacyConnectorFallback(paletteStroke)) return paletteStroke
  if (!isLegacyConnectorFallback(fallback)) return fallback
  return MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor
}

/**
 * Outer rings and annotation rules.
 * Rainbow keeps the topic border. A solid theme uses that theme's topic stroke,
 * which stays readable when the accent itself is light.
 */
export function thinkingMapStructureColor(themeId: string | null | undefined): string {
  if (thinkingMapSolidThemeStroke(themeId)) {
    return getMindMapThemeById(resolveMindMapThemeId(themeId)).topicBorderColor
  }
  return MIND_MAP_RAINBOW_TOPIC_COLORS.topicBorderColor
}

const CANVAS_INK = '#1e293b'

function channelLuminance(value: number): number {
  const scaled = value / 255
  return scaled <= 0.03928 ? scaled / 12.92 : ((scaled + 0.055) / 1.055) ** 2.4
}

function hexLuminance(hex: string): number {
  const raw = hex.trim().replace('#', '')
  const full = raw.length === 3 ? [...raw].map((ch) => `${ch}${ch}`).join('') : raw
  if (!/^[0-9a-fA-F]{6}$/.test(full)) return 0
  const packed = Number.parseInt(full, 16)
  return (
    0.2126 * channelLuminance((packed >> 16) & 255) +
    0.7152 * channelLuminance((packed >> 8) & 255) +
    0.0722 * channelLuminance(packed & 255)
  )
}

function contrast(ink: string, surface: string): number {
  const left = hexLuminance(ink)
  const right = hexLuminance(surface)
  const lighter = Math.max(left, right)
  const darker = Math.min(left, right)
  return (lighter + 0.05) / (darker + 0.05)
}

/** Dark-theme text ink is light. Labels sit on the light canvas, so prefer a dark theme color. */
function canvasInk(textColor: string, topicBorderColor: string): string {
  if (hexLuminance(textColor) < 0.45) return textColor
  if (hexLuminance(topicBorderColor) < 0.45) return topicBorderColor
  return CANVAS_INK
}

/** Annotation text. A solid theme stays readable on the light canvas. */
export function thinkingMapAdaptiveTextColor(
  themeId: string | null | undefined,
  rainbowFallback: string
): string {
  if (thinkingMapSolidThemeStroke(themeId)) {
    const theme = getMindMapThemeById(resolveMindMapThemeId(themeId))
    return canvasInk(theme.textColor, theme.topicBorderColor)
  }
  return rainbowFallback
}

/** Text drawn on a topic-colored chip. Rainbow keeps the caller fallback (usually white). */
export function thinkingMapAdaptiveTopicTextColor(
  themeId: string | null | undefined,
  rainbowFallback: string
): string {
  if (!thinkingMapSolidThemeStroke(themeId)) return rainbowFallback
  const theme = getMindMapThemeById(resolveMindMapThemeId(themeId))
  const dark = canvasInk(theme.textColor, theme.topicBorderColor)
  const fill = theme.topicBorderColor
  return contrast('#ffffff', fill) > contrast(dark, fill) ? '#ffffff' : dark
}
