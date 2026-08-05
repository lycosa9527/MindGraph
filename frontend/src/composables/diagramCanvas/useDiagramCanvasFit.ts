import type { Ref } from 'vue'
import { ref, toValue, watch } from 'vue'

import { useVueFlow } from '@vue-flow/core'

import { useMindMapSideToolbarState } from '@/composables/canvasToolbar/useMindMapSideToolbarState'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { useMindMapV2Chrome } from '@/composables/mindMap/useMindMapV2Chrome'
import { ANIMATION, CANVAS, FIT_PADDING, PANEL, ZOOM } from '@/config/uiConfig'
import type { usePanelsStore } from '@/stores/panels'
import { animateViewportTransition, cancelViewportTransition } from '@/utils/viewportTransition'
import { useUIStore } from '@/stores/ui'
import {
  isDesktopConceptMapManualViewport,
  isMindMapDiagramType,
} from '@/utils/conceptMapDesktopViewport'
import {
  parseFitPaddingPx,
  resolveMindMapSideToolbarLeftReservePx,
} from '@/utils/mindMapSideToolbarFitReserve'
import { computePanToKeepNodeInSafeFraction } from '@/utils/mindMapEnsureNodeVisible'

type DiagramStore = ReturnType<typeof useDiagramSession>
type PanelsStore = ReturnType<typeof usePanelsStore>

type FitViewFn = ReturnType<typeof useVueFlow>['fitView']

export function useDiagramCanvasFit(options: {
  fitView: FitViewFn
  getNodes: () => { length: number }
  setViewport: (
    viewport: { x: number; y: number; zoom: number },
    opts?: { duration?: number }
  ) => void
  getViewport: () => { x: number; y: number; zoom: number }
  canvasContainer: Ref<HTMLElement | null>
  diagramStore: DiagramStore
  panelsStore: PanelsStore
  fitViewOnInit: Ref<boolean>
  /**
   * When true (mobile canvas), run fitView to the topic node once on init for concept_map.
   * Desktop keeps this false so the viewport stays at default zoom/center.
   */
  conceptMapInitialTopicFit: Ref<boolean>
  presentationRailOpen: Ref<boolean>
  presentationSideToolbarVisible: Ref<boolean>
  presentationToolIsNotTimer: Ref<boolean>
  nodesLength: Ref<number>
}): {
  isFittedForPanel: Ref<boolean>
  hasInitialFitDoneForDiagram: Ref<boolean>
  handleViewportChange: (viewport: { x: number; y: number; zoom: number }) => void
  handleNodesInitialized: () => void
  fitToFullCanvas: (animate?: boolean) => void
  fitWithPanel: (animate?: boolean) => void
  fitDiagram: (animate?: boolean) => void
  fitForExport: () => void
  fitToNodes: (
    nodeIds: string[],
    options?: { animate?: boolean; duration?: number; padding?: number }
  ) => Promise<void>
  ensureNodeVisibleInSafeFraction: (
    nodeId: string,
    options?: { safeFraction?: number; animate?: boolean }
  ) => void
  scheduleFitAfterStructuralNodeChange: (hasFitTriggeringChange: boolean) => void
  clearFitTimersOnUnmount: () => void
} {
  const {
    fitView,
    getNodes,
    setViewport,
    getViewport,
    canvasContainer,
    diagramStore,
    panelsStore,
    fitViewOnInit,
    conceptMapInitialTopicFit,
    presentationRailOpen,
    presentationSideToolbarVisible,
    presentationToolIsNotTimer,
    nodesLength,
  } = options

  const viewBus = diagramStore.viewBus
  const uiStore = useUIStore()
  const useMindMapV2 = useMindMapV2Chrome()
  const { sidebarExpanded, sidebarVisible } = useMindMapSideToolbarState()
  const isFittedForPanel = ref(false)
  const hasInitialFitDoneForDiagram = ref(false)
  let fitFromNodesChangeTimeoutId: ReturnType<typeof setTimeout> | null = null
  let fitAfterLoadTimeoutId: ReturnType<typeof setTimeout> | null = null
  let pendingFitAfterMindMapBulk = false
  const fitEventUnsubscribers: Array<() => void> = []

  function clearFitAfterLoadTimer(): void {
    if (fitAfterLoadTimeoutId != null) {
      clearTimeout(fitAfterLoadTimeoutId)
      fitAfterLoadTimeoutId = null
    }
  }

  function runMindMapFitAfterLoad(): void {
    if (getNodes().length === 0) return
    hasInitialFitDoneForDiagram.value = true
    // Run on the next frame so fitView is not inside a long setTimeout task
    // (Chrome "[Violation] setTimeout handler took …ms").
    const apply = (): void => {
      // Showcase reader always wants true zoom-fit (including mind-map v1).
      // Editor v1 keeps center-at-default-zoom after load.
      if (useMindMapV2.value || toValue(diagramStore.isReadonly)) {
        fitToFullCanvas(true)
        return
      }
      centerDiagramAtDefaultZoom(false)
      viewBus.emit('view:fit_completed', { mode: 'mind_map_centered', animate: false })
    }
    if (typeof requestAnimationFrame === 'function') {
      requestAnimationFrame(() => {
        requestAnimationFrame(apply)
      })
      return
    }
    apply()
  }

  function scheduleMindMapFitAfterLoad(): void {
    clearFitAfterLoadTimer()
    if (diagramStore.mindMapBulkLoading) {
      pendingFitAfterMindMapBulk = true
      return
    }
    // After measure settle, two rAFs are enough — avoid the 350ms init delay.
    runMindMapFitAfterLoad()
  }

  /** One-shot initial fit resets only when a new diagram is loaded, not on edits. */
  fitEventUnsubscribers.push(
    viewBus.on('diagram:loaded', (payload) => {
      if (payload?.skipFit) {
        pendingFitAfterMindMapBulk = false
        clearFitAfterLoadTimer()
        hasInitialFitDoneForDiagram.value = true
        return
      }
      hasInitialFitDoneForDiagram.value = false
      // Soft reloads often reuse Vue Flow node ids — nodes-initialized may not
      // re-fire. Mind maps wait for measure-batch; other types fit shortly.
      if (isMindMapDiagramType(diagramStore.type)) {
        scheduleMindMapFitAfterLoad()
      } else if (diagramStore.type !== 'concept_map') {
        clearFitAfterLoadTimer()
        fitAfterLoadTimeoutId = setTimeout(() => {
          fitAfterLoadTimeoutId = null
          if (hasInitialFitDoneForDiagram.value) return
          hasInitialFitDoneForDiagram.value = true
          viewBus.emit('view:fit_to_canvas_requested', { animate: true })
        }, ANIMATION.FIT_VIEWPORT_DELAY)
      }
    }),
    viewBus.on('diagram:loaded_from_library', () => {
      hasInitialFitDoneForDiagram.value = false
    })
  )

  watch(
    () => diagramStore.mindMapBulkLoading,
    (loading, wasLoading) => {
      if (!pendingFitAfterMindMapBulk || wasLoading !== true || loading !== false) {
        return
      }
      pendingFitAfterMindMapBulk = false
      clearFitAfterLoadTimer()
      runMindMapFitAfterLoad()
    }
  )

  function getRightPanelWidth(): number {
    let width = 0
    if (panelsStore.propertyPanel.isOpen) {
      width = PANEL.PROPERTY_WIDTH
    } else if (panelsStore.mindmatePanel.isOpen) {
      width = PANEL.MINDMATE_WIDTH
    }
    return width
  }

  function getLeftPanelWidth(): number {
    return 0
  }

  function isAnyPanelOpen(): boolean {
    return panelsStore.anyPanelOpen
  }

  function handleViewportChange(viewport: { x: number; y: number; zoom: number }): void {
    viewBus.emit('view:zoom_changed', {
      zoom: viewport.zoom,
      zoomPercent: Math.round(viewport.zoom * 100),
    })
  }

  function getFitViewTopPx(): number {
    return diagramStore.type === 'concept_map'
      ? FIT_PADDING.TOP_UI_HEIGHT_PX + FIT_PADDING.MAIN_TOPIC_MENU_ICON_PX
      : FIT_PADDING.TOP_UI_HEIGHT_PX
  }

  function getFitViewBottomPx(): number {
    if (diagramStore.type !== 'tree_map') return FIT_PADDING.BOTTOM_UI_HEIGHT_PX
    const data = diagramStore.data
    if (!data || typeof data !== 'object' || !('alternative_dimensions' in data)) {
      return FIT_PADDING.BOTTOM_UI_HEIGHT_PX
    }
    const altDims = (data as { alternative_dimensions?: unknown }).alternative_dimensions
    const hasAltDims =
      Array.isArray(altDims) && altDims.some((d) => typeof d === 'string' && d.trim())
    return hasAltDims
      ? FIT_PADDING.BOTTOM_UI_HEIGHT_PX + FIT_PADDING.TREE_MAP_ALTERNATIVE_DIMENSIONS_EXTRA_PX
      : FIT_PADDING.BOTTOM_UI_HEIGHT_PX
  }

  function isMindMapSideToolbarAffectingFit(): boolean {
    return (
      isMindMapDiagramType(diagramStore.type) &&
      useMindMapV2.value &&
      !presentationRailOpen.value &&
      sidebarVisible.value
    )
  }

  function getFitViewLeftPx(): string {
    return `${resolveMindMapSideToolbarLeftReservePx({
      active: isMindMapSideToolbarAffectingFit(),
      expanded: sidebarExpanded.value,
    })}px`
  }

  function getFitViewRightPx(): string {
    const railVisible =
      presentationRailOpen.value &&
      presentationToolIsNotTimer.value &&
      presentationSideToolbarVisible.value
    const px = railVisible
      ? Math.max(FIT_PADDING.STANDARD_PX, FIT_PADDING.PRESENTATION_SIDE_TOOLBAR_RIGHT_PX)
      : FIT_PADDING.STANDARD_PX
    return `${px}px`
  }

  function fitToFullCanvas(animate = true): void {
    if (getNodes().length === 0) return

    isFittedForPanel.value = false

    fitView({
      padding: {
        ...FIT_PADDING.STANDARD_WITH_BOTTOM_UI,
        top: `${getFitViewTopPx()}px`,
        bottom: `${getFitViewBottomPx()}px`,
        right: getFitViewRightPx(),
        left: getFitViewLeftPx(),
      },
      duration: animate ? ANIMATION.DURATION_NORMAL : 0,
    } as Parameters<FitViewFn>[0])

    viewBus.emit('view:fit_completed', {
      mode: 'full_canvas',
      animate,
    })
  }

  function fitWithPanel(animate = true): void {
    if (getNodes().length === 0) return

    const rightPanelWidth = getRightPanelWidth()
    const leftPanelWidth = getLeftPanelWidth()
    const totalPanelWidth = rightPanelWidth + leftPanelWidth

    if (totalPanelWidth === 0) {
      fitToFullCanvas(animate)
      return
    }

    isFittedForPanel.value = true

    const container = canvasContainer.value
    if (!container) {
      fitView({
        padding: {
          ...FIT_PADDING.STANDARD_WITH_BOTTOM_UI,
          top: `${getFitViewTopPx()}px`,
          bottom: `${getFitViewBottomPx()}px`,
          right: getFitViewRightPx(),
          left: getFitViewLeftPx(),
        },
        duration: animate ? ANIMATION.DURATION_NORMAL : 0,
      } as Parameters<FitViewFn>[0])
      return
    }

    const containerWidth = container.clientWidth
    const basePadding = FIT_PADDING.STANDARD
    const panelPaddingRatio = totalPanelWidth / containerWidth
    const adjustedPadding = basePadding + panelPaddingRatio * 0.3

    fitView({
      padding: {
        top: `${getFitViewTopPx()}px`,
        right: presentationRailOpen.value ? getFitViewRightPx() : adjustedPadding,
        bottom: `${getFitViewBottomPx()}px`,
        left: isMindMapSideToolbarAffectingFit() ? getFitViewLeftPx() : adjustedPadding,
      },
      duration: animate ? ANIMATION.DURATION_NORMAL : 0,
    } as Parameters<FitViewFn>[0])

    const delay = animate ? ANIMATION.FIT_VIEWPORT_DELAY : ANIMATION.PANEL_DELAY
    setTimeout(() => {
      const currentViewport = getViewport()
      const rightOffset = rightPanelWidth / 2
      const leftOffset = leftPanelWidth / 2
      const netOffset = leftOffset - rightOffset

      setViewport(
        {
          x: currentViewport.x + netOffset,
          y: currentViewport.y,
          zoom: currentViewport.zoom,
        },
        { duration: animate ? ANIMATION.DURATION_FAST : 0 }
      )
    }, delay)

    viewBus.emit('view:fit_completed', {
      mode: 'with_panel',
      animate,
      panelWidth: totalPanelWidth,
    })
  }

  function fitDiagram(animate = true): void {
    if (isAnyPanelOpen()) {
      fitWithPanel(animate)
    } else {
      fitToFullCanvas(animate)
    }
  }

  function fitForExport(): void {
    fitView({
      padding: FIT_PADDING.EXPORT,
      duration: 0,
    } as Parameters<FitViewFn>[0])
  }

  async function fitToNodes(
    nodeIds: string[],
    options?: { animate?: boolean; duration?: number; padding?: number }
  ): Promise<void> {
    if (!nodeIds.length || getNodes().length === 0) return

    const animate = options?.animate !== false
    const duration = options?.duration ?? 900
    const padding = options?.padding ?? 0.38

    const fitOptions = {
      nodes: nodeIds,
      padding,
      duration: 0,
      minZoom: ZOOM.MIN,
      maxZoom: ZOOM.MAX,
      includeHiddenNodes: false,
    } as Parameters<FitViewFn>[0]

    if (!animate) {
      cancelViewportTransition()
      void fitView({ ...fitOptions, duration: 0 })
      viewBus.emit('view:fit_completed', { mode: 'nodes', animate: false })
      return
    }

    const from = getViewport()
    cancelViewportTransition()
    await fitView(fitOptions)
    const to = getViewport()
    setViewport(from, { duration: 0 })

    await animateViewportTransition(from, to, duration, (vp) => {
      setViewport(vp, { duration: 0 })
    })

    viewBus.emit('view:fit_completed', { mode: 'nodes', animate: true })
  }

  type FlowNodeLike = {
    position?: { x?: number; y?: number }
    dimensions?: { width?: number; height?: number }
    measured?: { width?: number; height?: number }
    width?: number
    height?: number
  }

  type EnsureVisibleNode = FlowNodeLike & { id?: string }

  function getNodeWidthHeight(
    node: FlowNodeLike,
    defaultW = 120,
    defaultH = 40
  ): { width: number; height: number } {
    const w = node.dimensions?.width ?? node.measured?.width ?? node.width ?? defaultW
    const h = node.dimensions?.height ?? node.measured?.height ?? node.height ?? defaultH
    return { width: Number(w) || defaultW, height: Number(h) || defaultH }
  }

  /**
   * Pan only (keep zoom): if `nodeId` sits outside the central safeFraction of
   * the usable canvas, shift the viewport so it enters that zone.
   * Retries briefly so Tab-child layout/measure can settle first.
   */
  function ensureNodeVisibleInSafeFraction(
    nodeId: string,
    options?: { safeFraction?: number; animate?: boolean }
  ): void {
    if (!nodeId) return
    const animate = options?.animate !== false
    const safeFraction =
      options?.safeFraction ?? FIT_PADDING.MIND_MAP_KEEP_VISIBLE_SAFE_FRACTION
    const maxAttempts = 12

    const tryApply = (attempt: number): void => {
      const list = getNodes() as EnsureVisibleNode[]
      const node = Array.isArray(list) ? list.find((n) => n.id === nodeId) : undefined
      if (!node) {
        if (attempt < maxAttempts) {
          requestAnimationFrame(() => tryApply(attempt + 1))
        }
        return
      }

      const { width, height } = getNodeWidthHeight(node)
      const container = canvasContainer.value
      const viewWidth = container?.clientWidth ?? CANVAS.DEFAULT_WIDTH
      const viewHeight = container?.clientHeight ?? CANVAS.DEFAULT_HEIGHT
      const result = computePanToKeepNodeInSafeFraction({
        viewport: getViewport(),
        node: {
          x: node.position?.x ?? 0,
          y: node.position?.y ?? 0,
          width,
          height,
        },
        viewWidth,
        viewHeight,
        safeFraction,
        chromeInsets: {
          top: getFitViewTopPx(),
          bottom: getFitViewBottomPx(),
          left: parseFitPaddingPx(getFitViewLeftPx()),
          right: parseFitPaddingPx(getFitViewRightPx()),
        },
      })
      if (!result.changed) return

      setViewport(result.viewport, {
        duration: animate ? ANIMATION.DURATION_NORMAL : 0,
      })
    }

    // Double rAF: wait for Vue Flow write-back after child reload.
    if (typeof requestAnimationFrame === 'function') {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => tryApply(0))
      })
      return
    }
    tryApply(0)
  }

  /** Center diagram bounding box in viewport at default zoom (no scale-to-fit). */
  function centerDiagramAtDefaultZoom(animate = false): void {
    const list = getNodes() as FlowNodeLike[]
    if (!Array.isArray(list) || list.length === 0) return

    let minX = Infinity
    let minY = Infinity
    let maxX = -Infinity
    let maxY = -Infinity
    for (const node of list) {
      const x = node.position?.x ?? 0
      const y = node.position?.y ?? 0
      const { width, height } = getNodeWidthHeight(node)
      minX = Math.min(minX, x)
      minY = Math.min(minY, y)
      maxX = Math.max(maxX, x + width)
      maxY = Math.max(maxY, y + height)
    }
    if (!Number.isFinite(minX)) return

    const centerX = (minX + maxX) / 2
    const centerY = (minY + maxY) / 2
    const zoom = ZOOM.DEFAULT

    const container = canvasContainer.value
    const viewW = container?.clientWidth ?? CANVAS.DEFAULT_WIDTH
    const viewH = container?.clientHeight ?? CANVAS.DEFAULT_HEIGHT
    const topPad = getFitViewTopPx()
    const bottomPad = getFitViewBottomPx()
    const leftPad = parseFitPaddingPx(getFitViewLeftPx())
    const rightPad = parseFitPaddingPx(getFitViewRightPx())
    const visibleCenterX = leftPad + (viewW - leftPad - rightPad) / 2
    const visibleCenterY = topPad + (viewH - topPad - bottomPad) / 2

    setViewport(
      {
        x: visibleCenterX - centerX * zoom,
        y: visibleCenterY - centerY * zoom,
        zoom,
      },
      { duration: animate ? ANIMATION.DURATION_NORMAL : 0 }
    )
  }

  function getConceptMapFocusNodeIdForFit(): string | null {
    const list = getNodes() as unknown
    if (!Array.isArray(list) || list.length === 0) return null
    const nodes = list as { id: string; data?: unknown }[]
    const byId = nodes.find((n) => n.id === 'topic')
    if (byId) return 'topic'
    const byType = nodes.find(
      (n) =>
        n.data &&
        typeof n.data === 'object' &&
        (n.data as { nodeType?: string }).nodeType === 'topic'
    )
    return byType?.id ?? null
  }

  function handleNodesInitialized(): void {
    if (getNodes().length === 0) return
    if (!fitViewOnInit.value) {
      if (isMindMapDiagramType(diagramStore.type)) {
        // Primary fit path is diagram:loaded → scheduleMindMapFitAfterLoad.
        // Fallback only when that path did not arm (e.g. emitLoaded: false).
        if (
          hasInitialFitDoneForDiagram.value ||
          pendingFitAfterMindMapBulk ||
          fitAfterLoadTimeoutId != null
        ) {
          return
        }
        hasInitialFitDoneForDiagram.value = true
        setTimeout(() => {
          if (useMindMapV2.value) {
            fitToFullCanvas(true)
          } else {
            centerDiagramAtDefaultZoom(false)
            viewBus.emit('view:fit_completed', { mode: 'mind_map_centered', animate: false })
          }
        }, Math.max(ANIMATION.FIT_VIEWPORT_DELAY, 450))
        return
      }
      if (diagramStore.type === 'concept_map') {
        if (hasInitialFitDoneForDiagram.value) return
        hasInitialFitDoneForDiagram.value = true
        const dv = diagramStore.data as Record<string, unknown> | null | undefined
        const cmapImportFitPending = dv?.['_import_cmap_fit_view_pending'] === true
        const isDesktopManual = isDesktopConceptMapManualViewport(diagramStore, uiStore)
        if (isDesktopManual && !cmapImportFitPending) {
          return
        }
        setTimeout(
          () => {
            if (dv && typeof dv === 'object' && cmapImportFitPending) {
              delete dv['_import_cmap_fit_view_pending']
              fitDiagram(true)
              viewBus.emit('view:fit_completed', { mode: 'cmap_import_hull', animate: true })
              return
            }
            if (!conceptMapInitialTopicFit.value) {
              setViewport({ x: 0, y: 0, zoom: ZOOM.DEFAULT }, { duration: 0 })
              return
            }
            const focusId = getConceptMapFocusNodeIdForFit()
            if (focusId) {
              const fitOptions = {
                nodes: [focusId],
                padding: 0.42,
                duration: ANIMATION.DURATION_NORMAL,
                minZoom: ZOOM.MIN,
                maxZoom: ZOOM.MAX,
                includeHiddenNodes: false,
              } as Parameters<FitViewFn>[0]
              void fitView(fitOptions)
              viewBus.emit('view:fit_completed', { mode: 'concept_map_topic', animate: true })
              return
            }
            setViewport({ x: 0, y: 0, zoom: ZOOM.DEFAULT }, { duration: 0 })
          },
          Math.max(ANIMATION.FIT_VIEWPORT_DELAY, 450)
        )
      }
      return
    }
    if (hasInitialFitDoneForDiagram.value) return
    // Mind maps: reuse diagram:loaded settle path (covers emitLoaded:false readers
    // such as Showcase, where measure-batch must finish before fit).
    if (isMindMapDiagramType(diagramStore.type)) {
      if (pendingFitAfterMindMapBulk || fitAfterLoadTimeoutId != null) return
      scheduleMindMapFitAfterLoad()
      return
    }
    hasInitialFitDoneForDiagram.value = true
    setTimeout(() => {
      viewBus.emit('view:fit_to_canvas_requested', { animate: true })
    }, ANIMATION.FIT_VIEWPORT_DELAY)
  }

  function scheduleFitAfterStructuralNodeChange(hasFitTriggeringChange: boolean): void {
    if (
      !hasFitTriggeringChange ||
      diagramStore.type === 'concept_map' ||
      isMindMapDiagramType(diagramStore.type) ||
      !fitViewOnInit.value ||
      getNodes().length === 0
    ) {
      return
    }
    if (fitFromNodesChangeTimeoutId) clearTimeout(fitFromNodesChangeTimeoutId)
    fitFromNodesChangeTimeoutId = setTimeout(() => {
      fitFromNodesChangeTimeoutId = null
      viewBus.emit('view:fit_to_canvas_requested', { animate: true })
    }, ANIMATION.FIT_DELAY)
  }

  function clearFitTimersOnUnmount(): void {
    if (fitFromNodesChangeTimeoutId) {
      clearTimeout(fitFromNodesChangeTimeoutId)
      fitFromNodesChangeTimeoutId = null
    }
    pendingFitAfterMindMapBulk = false
    clearFitAfterLoadTimer()
    fitEventUnsubscribers.forEach((unsub) => unsub())
    fitEventUnsubscribers.length = 0
  }

  watch(
    () => nodesLength.value,
    (newLength, oldLength) => {
      if (!fitViewOnInit.value || newLength === 0) return
      if (oldLength === undefined) return
      if (diagramStore.type === 'concept_map') return
      setTimeout(() => {
        viewBus.emit('view:fit_to_canvas_requested', { animate: true })
      }, ANIMATION.FIT_DELAY)
    }
  )

  watch(
    () => panelsStore.anyPanelOpen,
    (isOpen, wasOpen) => {
      if (!fitViewOnInit.value) return
      if (diagramStore.type === 'concept_map') return
      if (nodesLength.value > 0 && isOpen !== wasOpen) {
        setTimeout(() => fitDiagram(true), ANIMATION.PANEL_DELAY)
      }
    }
  )

  watch(
    () => [
      panelsStore.mindmatePanel.isOpen,
      panelsStore.propertyPanel.isOpen,
      panelsStore.nodePalettePanel.isOpen,
    ],
    () => {
      if (!fitViewOnInit.value) return
      if (diagramStore.type === 'concept_map') return
      if (nodesLength.value > 0) {
        setTimeout(() => fitDiagram(true), ANIMATION.PANEL_DELAY)
      }
    }
  )

  watch(
    () => presentationRailOpen.value,
    (active, wasActive) => {
      if (!fitViewOnInit.value) return
      if (diagramStore.type === 'concept_map') return
      if (active === wasActive) return
      if (active && getNodes().length > 0) {
        setTimeout(() => fitDiagram(true), ANIMATION.FIT_VIEWPORT_DELAY)
      }
    }
  )

  watch(
    () => Boolean(presentationRailOpen.value && presentationToolIsNotTimer.value),
    () => {
      if (!fitViewOnInit.value) return
      if (diagramStore.type === 'concept_map') return
      if (!presentationRailOpen.value || getNodes().length === 0) return
      setTimeout(() => fitDiagram(true), ANIMATION.FIT_VIEWPORT_DELAY)
    }
  )

  watch(
    () => useMindMapV2.value,
    (isV2, wasV2) => {
      if (wasV2 === undefined) return
      if (!isMindMapDiagramType(diagramStore.type)) return
      if (getNodes().length === 0) return
      setTimeout(() => {
        if (isV2) {
          fitToFullCanvas(true)
          return
        }
        viewBus.emit('view:fit_to_canvas_requested', { animate: true })
      }, ANIMATION.FIT_VIEWPORT_DELAY)
    }
  )

  return {
    isFittedForPanel,
    hasInitialFitDoneForDiagram,
    handleViewportChange,
    handleNodesInitialized,
    fitToFullCanvas,
    fitWithPanel,
    fitDiagram,
    fitForExport,
    fitToNodes,
    ensureNodeVisibleInSafeFraction,
    scheduleFitAfterStructuralNodeChange,
    clearFitTimersOnUnmount,
  }
}
