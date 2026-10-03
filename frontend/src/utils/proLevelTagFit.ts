/** Spare pixels required before the status-bar level tag drops its ellipsis. */
export const PRO_LEVEL_TAG_FIT_SLACK_PX = 4

/**
 * Width left in a horizontal flex row after its children and column gap.
 * Returns 0 when the row has not been laid out.
 */
export function flexRowSparePx(slot: HTMLElement): number {
  if (slot.clientWidth <= 0) return 0
  const gapRaw = getComputedStyle(slot).columnGap
  const gap = gapRaw.endsWith('px') ? Number.parseFloat(gapRaw) : 0
  const kids = [...slot.children]
  let used = 0
  for (const kid of kids) {
    if (kid instanceof HTMLElement) used += kid.offsetWidth
  }
  if (kids.length > 1 && gap > 0) used += gap * (kids.length - 1)
  return slot.clientWidth - used
}

/**
 * Show the full 专业程度 name when the status-bar center can hold the
 * unclipped tag. While expanded, a few pixels of overflow collapse it again.
 * `overflowPx` is the tag's hidden text (`scrollWidth - clientWidth`).
 */
export function nextProLevelTagExpanded(
  expanded: boolean,
  sparePx: number,
  overflowPx: number
): boolean {
  if (!Number.isFinite(sparePx) || !Number.isFinite(overflowPx)) return expanded
  if (expanded) return sparePx >= -PRO_LEVEL_TAG_FIT_SLACK_PX
  if (overflowPx <= 1) return false
  return sparePx >= overflowPx + PRO_LEVEL_TAG_FIT_SLACK_PX
}
