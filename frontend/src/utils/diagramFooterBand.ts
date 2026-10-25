/**
 * Suggested analogy / classification footer under brace, bridge, and tree maps.
 * Learning-sheet mode does not paint this footer; the reference answers use the slot.
 */

export const DIAGRAM_FOOTER_SEPARATOR_OFFSET_Y = 15
export const DIAGRAM_FOOTER_LABEL_OFFSET_Y = 15
export const DIAGRAM_FOOTER_LABEL_TO_CHIPS = 8

export type DiagramFooterKind = 'bridge' | 'brace' | 'tree'

const FOOTER_FONTS: Record<DiagramFooterKind, { label: number; chip: number }> = {
  bridge: { label: 14, chip: 12 },
  brace: { label: 14, chip: 13 },
  tree: { label: 13, chip: 12 },
}

export function diagramFooterFonts(kind: DiagramFooterKind): { label: number; chip: number } {
  return FOOTER_FONTS[kind]
}

export function diagramFooterChipY(
  separatorY: number,
  kind: DiagramFooterKind
): { labelY: number; chipsY: number } {
  const fonts = FOOTER_FONTS[kind]
  const labelY = separatorY + DIAGRAM_FOOTER_LABEL_OFFSET_Y
  const chipsY = labelY + fonts.label + DIAGRAM_FOOTER_LABEL_TO_CHIPS
  return { labelY, chipsY }
}
