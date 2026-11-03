/**
 * Stand-in size for a flow pill before the browser reports a border box.
 * The label uses the same wrap as the other thinking maps. The result is
 * then clamped to the pill's CSS max-width. Centering uses the measured
 * width once that read exists.
 */
import {
  FLOW_MAP_PILL_HEIGHT,
  FLOW_MAP_PILL_WIDTH,
  FLOW_STEP_NODE_MAX_WIDTH,
  FLOW_SUBSTEP_NODE_MAX_WIDTH,
  FLOW_TOPIC_NODE_MAX_WIDTH,
} from '@/composables/diagrams/layoutConfig'
import { MIND_MAP_GEOMETRY } from '@/config/mindMapGeometry'
import { secondaryFontSize, secondaryLineBoxHeight } from '@/diagramBilingual/measure'
import {
  type MindMapTextMeasureOptions,
  measureThinkingMapLabelBlockPx,
} from '@/utils/mindMapTextWrap'

export const FLOW_TOPIC_FONT_SIZE = 18
export const FLOW_STEP_FONT_SIZE = 16
export const FLOW_SUBSTEP_FONT_SIZE = 14

export type FlowPillRole = 'topic' | 'step' | 'substep'

export interface FlowPillFont {
  fontSize?: number
  fontWeight?: string
  fontFamily?: string
}

const FLOW_PILL_ROLE = {
  topic: {
    fontSize: FLOW_TOPIC_FONT_SIZE,
    fontWeight: 'bold',
    textCap: 300,
    maxBox: FLOW_TOPIC_NODE_MAX_WIDTH,
  },
  step: {
    fontSize: FLOW_STEP_FONT_SIZE,
    fontWeight: 'normal',
    textCap: 250,
    maxBox: FLOW_STEP_NODE_MAX_WIDTH,
  },
  substep: {
    fontSize: FLOW_SUBSTEP_FONT_SIZE,
    fontWeight: 'normal',
    textCap: 180,
    maxBox: FLOW_SUBSTEP_NODE_MAX_WIDTH,
  },
} as const

/** Horizontal padding of a flow pill (oval padding, both sides). */
const FLOW_PILL_PADDING_X = MIND_MAP_GEOMETRY.paddingXOval * 2
const FLOW_PILL_PADDING_Y = MIND_MAP_GEOMETRY.paddingY * 2
const FLOW_PILL_BORDER = MIND_MAP_GEOMETRY.borderWidth * 2

export interface FlowPillBox {
  boxWidth: number
  boxHeight: number
}

/** Text column inside a flow pill: CSS max minus padding and border. */
export function flowPillContentMaxPx(maxBoxWidth: number): number {
  return Math.max(8, maxBoxWidth - FLOW_PILL_PADDING_X - FLOW_PILL_BORDER)
}

export function measureFlowPillBox(
  text: string,
  fontSize: number,
  textCap: number,
  maxBoxWidth: number,
  options: MindMapTextMeasureOptions = {}
): FlowPillBox {
  const block = measureThinkingMapLabelBlockPx((text || '').trim() || ' ', fontSize, textCap, {
    ...options,
    columnCeiling: options.columnCeiling ?? flowPillContentMaxPx(maxBoxWidth),
  })
  const rawWidth = Math.ceil(block.width) + FLOW_PILL_PADDING_X + FLOW_PILL_BORDER
  return {
    boxWidth: Math.min(maxBoxWidth, Math.max(FLOW_MAP_PILL_WIDTH, rawWidth)),
    boxHeight: Math.max(
      FLOW_MAP_PILL_HEIGHT,
      Math.ceil(block.height + FLOW_PILL_PADDING_Y + FLOW_PILL_BORDER)
    ),
  }
}

/** Width the primary label wraps at before the pill's CSS max-width clamps the box. */
export function flowPillTextCap(role: FlowPillRole): number {
  return FLOW_PILL_ROLE[role].textCap
}

/** Topic, step, and substep pills share one cap and one default font. */
export function measureFlowRolePill(
  text: string,
  role: FlowPillRole,
  font: FlowPillFont = {}
): FlowPillBox {
  const base = FLOW_PILL_ROLE[role]
  return measureFlowPillBox(text, font.fontSize ?? base.fontSize, base.textCap, base.maxBox, {
    fontWeight: font.fontWeight ?? base.fontWeight,
    fontFamily: font.fontFamily,
  })
}

/**
 * Extra height of a second-language line inside the pill.
 * The line wraps in the same column as the primary label. An empty gloss adds nothing.
 */
export function flowSecondaryExtraHeight(
  text: string,
  secondary: string | undefined,
  role: FlowPillRole,
  font: FlowPillFont = {}
): number {
  const gloss = (secondary ?? '').trim()
  if (!gloss) return 0
  const base = FLOW_PILL_ROLE[role]
  const fontSize = font.fontSize ?? base.fontSize
  const box = measureFlowRolePill(text, role, font)
  const column = flowPillContentMaxPx(box.boxWidth)
  const block = measureThinkingMapLabelBlockPx(gloss, secondaryFontSize(fontSize), column, {
    columnCeiling: column,
    fontWeight: 'normal',
    fontFamily: font.fontFamily,
  })
  return Math.max(block.lineCount, 1) * secondaryLineBoxHeight(fontSize)
}
