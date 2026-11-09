/** Horizontal slack so the title row collapses before tabs touch the filename. */
export const TITLE_ROW_FIT_CUSHION_PX = 8

export type TitleRowFitMode = 'full' | 'textOnly' | 'shortText'

export type TitleRowFitSnapshot = {
  mode: TitleRowFitMode
  /** Row width that fits the back button, filename, save, icon tabs, and collab. */
  fullChromeWidth: number
  /** Tab strip width with icons hidden and full labels. */
  textOnlyTabsWidth: number
}

export type TitleRowFitMetrics = {
  rowWidth: number
  /** Width of the tab strip as currently rendered. */
  tabsWidth: number
  /**
   * Padding, the back button, and the single gap that stay when the filename,
   * save status, and collab control are hidden.
   */
  fixedWidth: number
  /**
   * Row width that fits the back button, filename, save, current tab strip,
   * and collab without the side columns painting over the tabs.
   * Read only while the row is still showing full chrome.
   */
  fullChromeWidth: number
}

export function createTitleRowFitSnapshot(): TitleRowFitSnapshot {
  return { mode: 'full', fullChromeWidth: 0, textOnlyTabsWidth: 0 }
}

/**
 * Hide the filename, save status, and collab control, and drop tab icons,
 * when that chrome does not fit the title row. Shorten tab text only if the
 * text-only strip still overflows the row that remains.
 *
 * The title row centers the tabs between two equal columns, so each side needs
 * as much width as the wider of the collab control and the filename block that
 * cannot shrink (back, divider, save).
 */
export function nextTitleRowFit(
  snapshot: TitleRowFitSnapshot,
  metrics: TitleRowFitMetrics
): TitleRowFitSnapshot {
  const { rowWidth, tabsWidth, fixedWidth } = metrics
  if (!Number.isFinite(rowWidth) || rowWidth <= 0) return snapshot
  if (!Number.isFinite(tabsWidth) || tabsWidth <= 0) return snapshot

  if (snapshot.mode === 'full') {
    const needed = metrics.fullChromeWidth
    if (!Number.isFinite(needed) || needed <= 0) return snapshot
    if (needed + TITLE_ROW_FIT_CUSHION_PX <= rowWidth) {
      if (snapshot.fullChromeWidth === 0 && snapshot.textOnlyTabsWidth === 0) return snapshot
      return createTitleRowFitSnapshot()
    }
    return { mode: 'textOnly', fullChromeWidth: needed, textOnlyTabsWidth: 0 }
  }

  if (
    snapshot.fullChromeWidth > 0 &&
    rowWidth >= snapshot.fullChromeWidth + TITLE_ROW_FIT_CUSHION_PX
  ) {
    return createTitleRowFitSnapshot()
  }

  const room = rowWidth - fixedWidth
  if (snapshot.mode === 'textOnly') {
    if (tabsWidth + TITLE_ROW_FIT_CUSHION_PX <= room) {
      if (snapshot.textOnlyTabsWidth === tabsWidth) return snapshot
      return { ...snapshot, textOnlyTabsWidth: tabsWidth }
    }
    return { ...snapshot, mode: 'shortText', textOnlyTabsWidth: tabsWidth }
  }

  if (
    snapshot.textOnlyTabsWidth > 0 &&
    room >= snapshot.textOnlyTabsWidth + TITLE_ROW_FIT_CUSHION_PX
  ) {
    return { ...snapshot, mode: 'textOnly' }
  }
  return snapshot
}
