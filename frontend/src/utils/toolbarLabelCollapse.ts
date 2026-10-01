/** Horizontal slack before icon+text controls collapse. */
const LABEL_COLLAPSE_SLACK_PX = 1

export type LabelCollapseSnapshot = {
  collapsed: boolean
  /** Width of the strip when labels are visible. */
  fullLabelsWidth: number
}

export function createLabelCollapseSnapshot(): LabelCollapseSnapshot {
  return { collapsed: false, fullLabelsWidth: 0 }
}

/**
 * Collapse toolbar labels when they do not fit the slot.
 * While collapsed, `contentWidth` is the icon-only width and is ignored.
 * Labels return only when the slot can hold the last measured full width.
 * Pass a negative `clientWidth` when the strip has not been laid out yet.
 */
export function nextLabelCollapse(
  snapshot: LabelCollapseSnapshot,
  clientWidth: number,
  contentWidth: number
): LabelCollapseSnapshot {
  if (!Number.isFinite(clientWidth) || clientWidth < 0) return snapshot
  if (!snapshot.collapsed) {
    const fullLabelsWidth = Math.max(0, contentWidth)
    return {
      fullLabelsWidth,
      collapsed: fullLabelsWidth > clientWidth + LABEL_COLLAPSE_SLACK_PX,
    }
  }
  if (
    snapshot.fullLabelsWidth > 0 &&
    clientWidth + LABEL_COLLAPSE_SLACK_PX >= snapshot.fullLabelsWidth
  ) {
    return { collapsed: false, fullLabelsWidth: snapshot.fullLabelsWidth }
  }
  return snapshot
}
