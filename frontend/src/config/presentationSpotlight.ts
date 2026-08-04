/** Spotlight hole size presets for the presentation rail. */
export type PresentationSpotlightSize = 'small' | 'medium' | 'large'

export const PRESENTATION_SPOTLIGHT_SIZE_SCALE: Record<PresentationSpotlightSize, number> = {
  small: 0.7,
  medium: 1,
  large: 1.5,
}

export const PRESENTATION_SPOTLIGHT_SIZE_OPTIONS: PresentationSpotlightSize[] = [
  'small',
  'medium',
  'large',
]

export function spotlightSizeFromScale(scale: number): PresentationSpotlightSize {
  let best: PresentationSpotlightSize = 'medium'
  let bestDist = Infinity
  for (const size of PRESENTATION_SPOTLIGHT_SIZE_OPTIONS) {
    const dist = Math.abs(PRESENTATION_SPOTLIGHT_SIZE_SCALE[size] - scale)
    if (dist < bestDist) {
      bestDist = dist
      best = size
    }
  }
  return best
}
