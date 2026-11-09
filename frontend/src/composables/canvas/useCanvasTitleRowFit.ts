/**
 * Collapse the mind-map title row when the ribbon tabs would overlap the
 * filename, save status, or collab control.
 */
import {
  type ComputedRef,
  type Ref,
  nextTick,
  onMounted,
  onUnmounted,
  shallowRef,
  watch,
} from 'vue'

import {
  TITLE_ROW_FIT_CUSHION_PX,
  type TitleRowFitMetrics,
  type TitleRowFitSnapshot,
  createTitleRowFitSnapshot,
  nextTitleRowFit,
} from '@/utils/canvasTitleRowFit'

type TitleRowFitRefs = {
  topBarRoot: Ref<HTMLElement | null>
  titleRow: Ref<HTMLElement | null>
  docCluster: Ref<HTMLElement | null>
  backCluster: Ref<HTMLElement | null>
  docMeta: Ref<HTMLElement | null>
  tabsHost: Ref<HTMLElement | null>
  collabCluster: Ref<HTMLElement | null>
  enabled: ComputedRef<boolean>
  resetKey: ComputedRef<readonly unknown[]>
  onBarWidth: (width: number) => void
}

function horizontalMargin(el: HTMLElement): number {
  const style = getComputedStyle(el)
  return (parseFloat(style.marginLeft) || 0) + (parseFloat(style.marginRight) || 0)
}

/** Border-box width of text that cannot shrink, capped by max-width. */
function visibleTextWidth(el: HTMLElement): number {
  const style = getComputedStyle(el)
  const margin = horizontalMargin(el)
  const range = document.createRange()
  range.selectNodeContents(el)
  const text = range.getBoundingClientRect().width
  if (text <= 0) return el.offsetWidth + margin
  const pad = (parseFloat(style.paddingLeft) || 0) + (parseFloat(style.paddingRight) || 0)
  const border =
    (parseFloat(style.borderLeftWidth) || 0) + (parseFloat(style.borderRightWidth) || 0)
  let box = Math.ceil(text) + pad + border
  const maxWidth = parseFloat(style.maxWidth)
  if (Number.isFinite(maxWidth) && maxWidth > 0) box = Math.min(box, maxWidth)
  return box + margin
}

function canShrinkAway(el: HTMLElement): boolean {
  const style = getComputedStyle(el)
  const shrink = parseFloat(style.flexShrink)
  if (!Number.isFinite(shrink) || shrink <= 0) return false
  return (
    style.overflowX === 'hidden' || style.overflowX === 'clip' || style.textOverflow === 'ellipsis'
  )
}

/** Minimum width that still collides with the tabs. Truncated names can shrink to nothing. */
function minChromeWidth(el: HTMLElement): number {
  if (el.getClientRects().length === 0) return 0
  if (el.querySelector('input, textarea')) return el.offsetWidth + horizontalMargin(el)
  const kids = [...el.children].filter(
    (node): node is HTMLElement => node instanceof HTMLElement && node.getClientRects().length > 0
  )
  if (kids.length === 0) {
    if (canShrinkAway(el)) return horizontalMargin(el)
    return visibleTextWidth(el)
  }
  const style = getComputedStyle(el)
  const gap = style.display.includes('flex') ? parseFloat(style.columnGap) || 0 : 0
  const widths = kids.map((child) => minChromeWidth(child)).filter((width) => width > 0)
  const inner = widths.reduce((sum, width) => sum + width, 0)
  return inner + gap * Math.max(0, widths.length - 1) + horizontalMargin(el)
}

function rectsHit(a: DOMRect, b: DOMRect): boolean {
  if (a.width <= 0 || a.height <= 0 || b.width <= 0 || b.height <= 0) return false
  return a.left < b.right - 1 && a.right > b.left + 1
}

function tabsOverlapChrome(refs: TitleRowFitRefs, tabs: HTMLElement): boolean {
  const tabsRect = tabs.getBoundingClientRect()
  const nodes: HTMLElement[] = []
  refs.docMeta.value
    ?.querySelectorAll('.file-name-label, .file-name-input, .auto-saved-status')
    .forEach((node) => {
      if (node instanceof HTMLElement) nodes.push(node)
    })
  const collabButton = refs.collabCluster.value?.querySelector('button')
  if (collabButton instanceof HTMLElement) nodes.push(collabButton)
  return nodes.some((node) => rectsHit(tabsRect, node.getBoundingClientRect()))
}

function collabButtonWidth(cluster: HTMLElement | null): number {
  if (!cluster || cluster.getClientRects().length === 0) return 0
  const button = cluster.querySelector('button')
  if (!(button instanceof HTMLElement)) return 0
  return button.offsetWidth
}

function readMetrics(refs: TitleRowFitRefs): TitleRowFitMetrics | null {
  const row = refs.titleRow.value
  const tabs = refs.tabsHost.value
  if (!row || !tabs) return null
  const rowWidth = row.clientWidth
  const tabsWidth = tabs.offsetWidth
  if (rowWidth <= 0 || tabsWidth <= 0) return null
  const style = getComputedStyle(row)
  const padX = (parseFloat(style.paddingLeft) || 0) + (parseFloat(style.paddingRight) || 0)
  const columnGap = parseFloat(style.columnGap) || 0
  const backWidth = refs.backCluster.value?.offsetWidth ?? 0
  const doc = refs.docCluster.value
  const meta = refs.docMeta.value
  const docGap =
    doc && meta && meta.getClientRects().length > 0
      ? parseFloat(getComputedStyle(doc).columnGap) || 0
      : 0
  const docMetaWidth = meta ? minChromeWidth(meta) : 0
  const docCap = finiteMaxWidth(doc)
  const docIntrinsic = Math.min(backWidth + docGap + docMetaWidth, docCap)
  const sideWidth = Math.max(docIntrinsic, collabButtonWidth(refs.collabCluster.value))
  let fullChromeWidth = padX + columnGap * 2 + tabsWidth + sideWidth * 2
  if (tabsOverlapChrome(refs, tabs)) {
    fullChromeWidth = Math.max(fullChromeWidth, rowWidth + TITLE_ROW_FIT_CUSHION_PX)
  }
  return {
    rowWidth,
    tabsWidth,
    fixedWidth: padX + columnGap + backWidth,
    fullChromeWidth,
  }
}

function finiteMaxWidth(el: HTMLElement | null): number {
  if (!el) return Number.POSITIVE_INFINITY
  const maxWidth = parseFloat(getComputedStyle(el).maxWidth)
  if (!Number.isFinite(maxWidth) || maxWidth <= 0) return Number.POSITIVE_INFINITY
  return maxWidth
}

export function useCanvasTitleRowFit(refs: TitleRowFitRefs) {
  const titleRowTight = shallowRef(false)
  const titleRowShortLabels = shallowRef(false)
  let snapshot: TitleRowFitSnapshot = createTitleRowFitSnapshot()
  let observer: ResizeObserver | null = null

  function resetToFull(): void {
    snapshot = createTitleRowFitSnapshot()
    titleRowTight.value = false
    titleRowShortLabels.value = false
  }

  function updateFit(): void {
    if (!refs.enabled.value) {
      if (snapshot.mode !== 'full') resetToFull()
      return
    }
    const metrics = readMetrics(refs)
    if (!metrics) return
    const next = nextTitleRowFit(snapshot, metrics)
    snapshot = next
    const tight = next.mode !== 'full'
    const short = next.mode === 'shortText'
    const changed = tight !== titleRowTight.value || short !== titleRowShortLabels.value
    titleRowTight.value = tight
    titleRowShortLabels.value = short
    if (changed) void nextTick(() => updateFit())
  }

  function onResize(): void {
    const width = refs.topBarRoot.value?.getBoundingClientRect().width ?? 0
    refs.onBarWidth(width)
    updateFit()
  }

  function bindObserver(): void {
    observer?.disconnect()
    if (typeof ResizeObserver === 'undefined') return
    observer = new ResizeObserver(() => {
      onResize()
    })
    const nodes = [
      refs.topBarRoot.value,
      refs.titleRow.value,
      refs.docCluster.value,
      refs.backCluster.value,
      refs.docMeta.value,
      refs.tabsHost.value,
      refs.collabCluster.value,
    ]
    for (const node of nodes) {
      if (node) observer.observe(node)
    }
  }

  watch(refs.resetKey, () => {
    resetToFull()
    void nextTick(() => updateFit())
  })

  watch(refs.enabled, (on) => {
    if (!on) {
      resetToFull()
      return
    }
    void nextTick(() => updateFit())
  })

  watch(
    () =>
      [
        refs.topBarRoot.value,
        refs.titleRow.value,
        refs.docCluster.value,
        refs.backCluster.value,
        refs.docMeta.value,
        refs.tabsHost.value,
        refs.collabCluster.value,
      ] as const,
    () => {
      bindObserver()
      updateFit()
    }
  )

  onMounted(() => {
    bindObserver()
    onResize()
    void nextTick(() => updateFit())
  })

  onUnmounted(() => {
    observer?.disconnect()
    observer = null
  })

  return { titleRowTight, titleRowShortLabels }
}
