/**
 * Classic mind-map sizing constants (pre-v2 canvas, baseline c2611060e).
 * Used for layout estimates and DOM alignment in legacy canvas mode only.
 */
export const MIND_MAP_LEGACY_GEOMETRY = {
  branchFontSize: 16,
  topicFontSize: 18,
  nodeHorizontalExtra: 38,
  minNodeWidth: 80,
  minNodeHeight: 36,
  branchPaddingY: 16,
  branchBorderY: 6,
  topicPaddingX: 48,
  topicBorderX: 6,
  topicMinWidth: 80,
  topicMinHeight: 36,
  topicLineHeight: 27,
} as const
