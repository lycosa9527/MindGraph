/** Classroom chalk colors — high contrast for projection. */
export const PRESENTATION_BOARD_COLORS = [
  {
    id: 'red',
    swatch: '#e53935',
    stroke: 'rgba(229, 57, 53, 0.94)',
    labelKey: 'canvas.mindMapPresentationToolbar.colorRed',
  },
  {
    id: 'blue',
    swatch: '#1e88e5',
    stroke: 'rgba(30, 136, 229, 0.94)',
    labelKey: 'canvas.mindMapPresentationToolbar.colorBlue',
  },
  {
    id: 'green',
    swatch: '#43a047',
    stroke: 'rgba(67, 160, 71, 0.94)',
    labelKey: 'canvas.mindMapPresentationToolbar.colorGreen',
  },
  {
    id: 'orange',
    swatch: '#fb8c00',
    stroke: 'rgba(251, 140, 0, 0.94)',
    labelKey: 'canvas.mindMapPresentationToolbar.colorOrange',
  },
  {
    id: 'white',
    swatch: '#f5f5f5',
    stroke: 'rgba(245, 245, 245, 0.96)',
    labelKey: 'canvas.mindMapPresentationToolbar.colorWhite',
  },
] as const

/** Subset shown on the presentation rail (red / blue / green). */
export const PRESENTATION_BOARD_COLORS_TOOLBAR = PRESENTATION_BOARD_COLORS.slice(0, 3)

export type PresentationBoardColorId = (typeof PRESENTATION_BOARD_COLORS)[number]['id']

export type PresentationBoardThickness = 'thin' | 'medium' | 'thick'

export const PRESENTATION_BOARD_THICKNESS_SCALE: Record<PresentationBoardThickness, number> = {
  thin: 0.35,
  medium: 0.85,
  thick: 1.75,
}

export function presentationBoardColorStroke(id: PresentationBoardColorId): string {
  return PRESENTATION_BOARD_COLORS.find((c) => c.id === id)?.stroke ?? PRESENTATION_BOARD_COLORS[0].stroke
}
