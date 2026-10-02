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
