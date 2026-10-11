/**
 * Tree-map category and leaf boxes.
 * A label that fits the script-aware column stays one line and the node hugs it.
 * A longer label wraps at that column and the box grows with the lines.
 */
import { NODE_MIN_DIMENSIONS } from '@/composables/diagrams/layoutConfig'
import { stackedTextBlock } from '@/diagramBilingual/measure'
import { measureTextWidth } from '@/stores/specLoader/textMeasurement'
import { measureThinkingMapLabelBlockPx } from '@/utils/mindMapTextWrap'

/** Category (L1) wrap cap. CJK scales this up via the shared column. */
export const TREE_MAP_BRANCH_TEXT_CAP_PX = 200
/** Leaf (L2) wrap cap. */
export const TREE_MAP_LEAF_TEXT_CAP_PX = 200
export const TREE_MAP_BRANCH_FONT_SIZE = 16
export const TREE_MAP_LEAF_FONT_SIZE = 14
/** Horizontal padding, both sides (12px each). */
export const TREE_MAP_NODE_PADDING_X = 24
/** Vertical padding, each side. */
export const TREE_MAP_NODE_PADDING_Y = 9
/** Category stroke. Added on both width and height (border-box). */
export const TREE_MAP_CATEGORY_BORDER = 1.5
/** Leaves use a left bar instead of a stroke. */
export const TREE_MAP_LEAF_BORDER = 0
/**
 * Rainbow leaf inset: 3px bar plus the extra 4px in BranchNodeDiagram paddingLeft.
 * Without it the text column is narrower than the measured line and balance-wraps.
 */
export const TREE_MAP_LEAF_ACCENT_INSET_PX = 7
/** Stops a 1px shortfall from splitting a line that otherwise fits. */
export const TREE_MAP_TEXT_FIT_SLACK_PX = 8

function treeMapNodeBorder(leaf: boolean, underline: boolean): number {
  if (underline) return 0
  return leaf ? TREE_MAP_LEAF_BORDER : TREE_MAP_CATEGORY_BORDER
}

export interface TreeMapNodeMeasureOptions {
  role: 'category' | 'leaf'
  fontSize: number
  fontWeight?: string
  fontFamily?: string
  secondary?: string
  underline?: boolean
}

export function measureTreeMapNodeBox(
  text: string,
  options: TreeMapNodeMeasureOptions
): { width: number; height: number } {
  const leaf = options.role === 'leaf'
  const underline = options.underline === true
  const border = treeMapNodeBorder(leaf, underline)
  const accent = !underline && leaf ? TREE_MAP_LEAF_ACCENT_INSET_PX : 0
  const cap = leaf ? TREE_MAP_LEAF_TEXT_CAP_PX : TREE_MAP_BRANCH_TEXT_CAP_PX
  const fontWeight = options.fontWeight ?? 'normal'
  const block = measureThinkingMapLabelBlockPx(text.trim() || ' ', options.fontSize, cap, {
    fontWeight,
    fontFamily: options.fontFamily,
  })
  const padY = underline ? 2 : TREE_MAP_NODE_PADDING_Y
  const width = Math.max(
    Math.ceil(block.width) +
      TREE_MAP_NODE_PADDING_X +
      accent +
      TREE_MAP_TEXT_FIT_SLACK_PX +
      border * 2,
    NODE_MIN_DIMENSIONS.branch.minWidth
  )
  const textHeight = Math.ceil(block.height) + padY * 2 + border * 2
  const height = underline ? textHeight : Math.max(textHeight, NODE_MIN_DIMENSIONS.branch.minHeight)
  return finishTreeMapSecondary(width, height, options)
}

function finishTreeMapSecondary(
  width: number,
  height: number,
  options: TreeMapNodeMeasureOptions
): { width: number; height: number } {
  const gloss = (options.secondary ?? '').trim()
  if (!gloss) return { width, height }
  const glossWidth =
    typeof document === 'undefined'
      ? Math.ceil(gloss.length * options.fontSize * 0.75 * 0.6)
      : measureTextWidth(gloss, options.fontSize * 0.75, {
          fontWeight: options.fontWeight,
          fontFamily: options.fontFamily,
        })
  const stacked = stackedTextBlock(
    width,
    height,
    glossWidth + TREE_MAP_NODE_PADDING_X,
    options.fontSize,
    gloss
  )
  if (options.underline) return stacked
  return {
    width: Math.max(stacked.width, NODE_MIN_DIMENSIONS.branch.minWidth),
    height: Math.max(stacked.height, NODE_MIN_DIMENSIONS.branch.minHeight),
  }
}
