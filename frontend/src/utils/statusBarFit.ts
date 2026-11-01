import { flexRowSparePx } from '@/utils/proLevelTagFit'

/**
 * Width the status bar needs for its clusters.
 * Empty space in a stretched center does not count. A cluster that has
 * not been laid out does not add a gap.
 * Returns 0 before the bar has been laid out.
 */
export function statusBarUsedWidth(bar: HTMLElement): number {
  if (bar.clientWidth <= 0) return 0
  const style = getComputedStyle(bar)
  const pad =
    (Number.parseFloat(style.paddingLeft) || 0) + (Number.parseFloat(style.paddingRight) || 0)
  const gapRaw = style.columnGap
  const gap = gapRaw.endsWith('px') ? Number.parseFloat(gapRaw) : 0
  const clusters = [...bar.children].filter((kid): kid is HTMLElement => kid instanceof HTMLElement)
  let used = pad
  let measured = 0
  for (const cluster of clusters) {
    if (cluster.clientWidth <= 0) continue
    measured += 1
    used += cluster.clientWidth - flexRowSparePx(cluster)
  }
  if (measured > 1 && gap > 0) used += gap * (measured - 1)
  return used
}
