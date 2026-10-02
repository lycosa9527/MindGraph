/**
 * Thinking-map connectors stay on the per-branch palette for the default
 * rainbow theme. Any other theme paints every connector with that theme's accent.
 * Palette strokes stay stored so returning to rainbow restores them.
 */
import { getMindMapThemeById, resolveMindMapThemeId } from '@/config/mindMapThemes'
import { isRainbowMindMapTheme } from '@/config/mindMapVibrantThemes'

/** Accent for a solid theme. Rainbow and an unset theme keep the palette. */
export function thinkingMapSolidThemeStroke(themeId: string | null | undefined): string | null {
  if (!themeId || isRainbowMindMapTheme(themeId)) return null
  const resolved = resolveMindMapThemeId(themeId)
  if (resolved !== themeId || isRainbowMindMapTheme(resolved)) return null
  return getMindMapThemeById(resolved).borderColor
}

/** Theme accent when one is active; otherwise the stored palette stroke. */
export function resolveThinkingMapConnectorStroke(
  themeId: string | null | undefined,
  paletteStroke: string | null | undefined,
  fallback: string
): string {
  return thinkingMapSolidThemeStroke(themeId) ?? paletteStroke ?? fallback
}
