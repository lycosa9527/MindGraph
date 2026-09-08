/** Spotlight hole size presets for the presentation rail. */
export type PresentationSpotlightSize = 'small' | 'medium' | 'large'

/** Soft hole used by the canvas presentation overlay. */
export const SPOTLIGHT_INNER_RADIUS_PX = 150
export const SPOTLIGHT_OUTER_RADIUS_PX = 195
export const SPOTLIGHT_RECT_HALF_WIDTH_PX = 190
export const SPOTLIGHT_RECT_HALF_HEIGHT_PX = 120
export const SPOTLIGHT_DIM = 'rgba(0,0,0,0.62)'
export const SPOTLIGHT_COMPACT_MIN_PX = 280
export const SPOTLIGHT_STAGE_REF_PX = 720

function spotlightSize(scale: number): number {
  return Number.isFinite(scale) && scale > 0 ? scale : 1
}

export function presentationSpotlightBackground(
  xPx: number,
  yPx: number,
  scale: number
): string {
  const size = spotlightSize(scale)
  const inner = SPOTLIGHT_INNER_RADIUS_PX * size
  const outer = SPOTLIGHT_OUTER_RADIUS_PX * size
  return `radial-gradient(circle at ${xPx}px ${yPx}px, transparent 0%, transparent ${inner}px, ${SPOTLIGHT_DIM} ${outer}px)`
}

export function presentationSpotlightHoleSize(
  scale: number,
  shape: 'circle' | 'rect'
): { halfW: number; halfH: number } {
  const size = spotlightSize(scale)
  if (shape === 'rect') {
    return {
      halfW: SPOTLIGHT_RECT_HALF_WIDTH_PX * size,
      halfH: SPOTLIGHT_RECT_HALF_HEIGHT_PX * size,
    }
  }
  const radius = SPOTLIGHT_INNER_RADIUS_PX * size
  return { halfW: radius, halfH: radius }
}

export function presentationRectSpotlightStyle(
  xPx: number,
  yPx: number,
  scale: number
): Record<string, string> {
  const size = spotlightSize(scale)
  const { halfW, halfH } = presentationSpotlightHoleSize(size, 'rect')
  const feather = (SPOTLIGHT_OUTER_RADIUS_PX - SPOTLIGHT_INNER_RADIUS_PX) * size
  const xMask = [
    'linear-gradient(to right,',
    `#000 0, #000 ${xPx - halfW - feather}px,`,
    `transparent ${xPx - halfW}px, transparent ${xPx + halfW}px,`,
    `#000 ${xPx + halfW + feather}px)`,
  ].join(' ')
  const yMask = [
    'linear-gradient(to bottom,',
    `#000 0, #000 ${yPx - halfH - feather}px,`,
    `transparent ${yPx - halfH}px, transparent ${yPx + halfH}px,`,
    `#000 ${yPx + halfH + feather}px)`,
  ].join(' ')
  return {
    background: SPOTLIGHT_DIM,
    maskImage: `${xMask}, ${yMask}`,
    WebkitMaskImage: `${xMask}, ${yMask}`,
    maskSize: '100% 100%',
    WebkitMaskSize: '100% 100%',
    maskRepeat: 'no-repeat',
    WebkitMaskRepeat: 'no-repeat',
    maskComposite: 'add',
    WebkitMaskComposite: 'source-over',
  }
}

export function presentationSpotlightVisualScale(
  scale: number,
  width: number,
  height: number
): number {
  const size = Number.isFinite(scale) && scale > 0 ? scale : 1
  const minSide = Math.min(width, height)
  if (minSide < SPOTLIGHT_COMPACT_MIN_PX) {
    return size * (minSide / SPOTLIGHT_STAGE_REF_PX)
  }
  return size
}

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
