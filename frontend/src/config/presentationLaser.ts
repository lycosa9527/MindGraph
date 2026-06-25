/** Laser pointer size presets for the presentation rail. */
export type PresentationLaserSize = 'small' | 'medium' | 'large'

export const PRESENTATION_LASER_SIZE_SCALE: Record<PresentationLaserSize, number> = {
  small: 0.55,
  medium: 0.75,
  large: 1.15,
}

export const PRESENTATION_LASER_SIZE_OPTIONS: PresentationLaserSize[] = ['small', 'medium', 'large']

export function laserSizeFromScale(scale: number): PresentationLaserSize {
  let best: PresentationLaserSize = 'medium'
  let bestDist = Infinity
  for (const size of PRESENTATION_LASER_SIZE_OPTIONS) {
    const dist = Math.abs(PRESENTATION_LASER_SIZE_SCALE[size] - scale)
    if (dist < bestDist) {
      bestDist = dist
      best = size
    }
  }
  return best
}
