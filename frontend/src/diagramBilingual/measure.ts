/**
 * Stacked primary + secondary label size.
 * An empty secondary line returns the primary box unchanged.
 */

export const BILINGUAL_SECONDARY_EM = 0.75
export const BILINGUAL_SECONDARY_LINE_HEIGHT = 1.2

export function secondaryFontSize(fontSize: number): number {
  return fontSize * BILINGUAL_SECONDARY_EM
}

export function secondaryLineBoxHeight(fontSize: number): number {
  return Math.ceil(secondaryFontSize(fontSize) * BILINGUAL_SECONDARY_LINE_HEIGHT)
}

/** Add the second-line box when there is a gloss. An empty gloss returns `height`. */
export function heightWithSecondaryLine(
  height: number,
  secondary: string | undefined,
  fontSize: number
): number {
  const gloss = (secondary ?? '').trim()
  if (!gloss) return height
  return height + secondaryLineBoxHeight(fontSize)
}

export function stackedTextBlock(
  primaryWidth: number,
  primaryHeight: number,
  secondaryWidth: number,
  fontSize: number,
  secondary?: string
): { width: number; height: number } {
  const gloss = (secondary ?? '').trim()
  if (!gloss) {
    return { width: primaryWidth, height: primaryHeight }
  }
  return {
    width: Math.max(primaryWidth, secondaryWidth),
    height: primaryHeight + secondaryLineBoxHeight(fontSize),
  }
}
