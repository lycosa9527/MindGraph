/**
 * Bridge pair section.
 * The section is as wide as the wider of the primary line and the gloss under it.
 * A line that passes the cap wraps, and each wrapped line adds height.
 */
import { MIND_MAP_GEOMETRY } from '@/config/mindMapGeometry'
import { BILINGUAL_SECONDARY_LINE_HEIGHT, secondaryFontSize } from '@/diagramBilingual/measure'
import { MIND_MAP_TEXT_LINE_HEIGHT, measureThinkingMapLabelBlockPx } from '@/utils/mindMapTextWrap'

/** Same cap the pair node paints: `min(420px, 88vw)`, before the viewport clamp. */
export const BRIDGE_PAIR_TEXT_CAP = 420

/** Matches `.branch-node` min-height. A shorter line still occupies this box. */
export const BRIDGE_PAIR_MIN_HEIGHT = 36

/** Branch default. A stored node font size replaces it. */
export const BRIDGE_PAIR_FONT = MIND_MAP_GEOMETRY.branchFontSize

export type BridgePairBox = {
  width: number
  height: number
}

function lineBlock(text: string, fontSize: number, lineHeight: number): BridgePairBox {
  const block = measureThinkingMapLabelBlockPx(text, fontSize, BRIDGE_PAIR_TEXT_CAP)
  return {
    width: block.width,
    height: Math.max(block.lineCount, 1) * fontSize * lineHeight,
  }
}

/**
 * Content box for one pair word.
 * The primary line is on top. The gloss, when present, stacks under it and can
 * widen the section until the wrap cap.
 */
export function bridgePairContentBox(
  text: string,
  textSecondary?: string,
  fontSize: number = BRIDGE_PAIR_FONT
): BridgePairBox {
  const size = fontSize > 0 ? fontSize : BRIDGE_PAIR_FONT
  const primary = lineBlock((text ?? '').trim() || ' ', size, MIND_MAP_TEXT_LINE_HEIGHT)
  const gloss = (textSecondary ?? '').trim()
  if (!gloss) {
    return { width: primary.width, height: Math.max(BRIDGE_PAIR_MIN_HEIGHT, primary.height) }
  }
  const secondary = lineBlock(gloss, secondaryFontSize(size), BILINGUAL_SECONDARY_LINE_HEIGHT)
  return {
    width: Math.max(primary.width, secondary.width),
    height: Math.max(BRIDGE_PAIR_MIN_HEIGHT, primary.height + secondary.height),
  }
}

/** Right edge of a section. The separator sits after the wider word. */
export function bridgeSectionRight(
  upperX: number,
  upperWidth: number,
  lowerX: number,
  lowerWidth: number
): number {
  return Math.max(upperX + Math.max(0, upperWidth), lowerX + Math.max(0, lowerWidth))
}
