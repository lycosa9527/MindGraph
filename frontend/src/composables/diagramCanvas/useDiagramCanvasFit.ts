import type { Ref } from 'vue'
import { ref, watch } from 'vue'

import { useVueFlow } from '@vue-flow/core'

import { eventBus } from '@/composables/core/useEventBus'
import { useMindMapSideToolbarState } from '@/composables/canvasToolbar/useMindMapSideToolbarState'
import { useMindMapV2Chrome } from '@/composables/mindMap/useMindMapV2Chrome'
import { ANIMATION, CANVAS, FIT_PADDING, PANEL, ZOOM } from '@/config/uiConfig'
import { animateViewportTransition, cancelViewportTransition } from '@/utils/viewportTransition'
import type { useDiagramStore } from '@/stores/diagram'
import type { usePanelsStore } from '@/stores/panels'
import { useUIStore } from '@/stores/ui'
import {
  isDesktopConceptMapManualViewport,
  isMindMapDiagramType,
} from '@/utils/conceptMapDesktopViewport'
import {
  parseFitPaddingPx,
  resolveMindMapSideToolbarLeftReservePx,
} from '@/utils/mindMapSideToolbarFitReserve'

type DiagramStore = ReturnType<typeof useDiagramStore>
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
    presentationToolIsNotTimer,
    nodesLength,
  } = options

  const uiStore = useUIStore()
  const useMindMapV2 = useMindMapV2Chrome()
  const { sidebarExpanded, sidebarVisible } = useMindMapSideToolbarState()
  const isFittedForPanel = ref(false)
  const hasInitialFitDoneForDiagram = ref(false)
  let fitFromNodesChangeTimeoutId: ReturnType<typeof setTimeout> | null = null

  watch(
    () => [diagramStore.type, diagramStore.data] as const,
    () => {
      hasInitialFitDoneForDiagram.value = false
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
    eventBus.emit('view:zoom_changed', {
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
    const railVisible = presentationRailOpen.value && presentationToolIsNotTimer.value
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

    eventBus.emit('view:fit_completed', {
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

    eventBus.emit('view:fit_completed', {
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
      eventBus.emit('view:fit_completed', { mode: 'nodes', animate: false })
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

    eventBus.emit('view:fit_completed', { mode: 'nodes', animate: true })
  }

  type FlowNodeLike = {
    position?: { x?: number; y?: number }
    dimensions?: { width?: number; height?: number }
    measured?: { width?: number; height?: number }
    width?: number
    height?: number
  }

  function getNodeWidthHeight(
    node: FlowNodeLike,
    defaultW = 120,
    defaultH = 40
  ): { width: number; height: number } {
    const w = node.dimensions?.width ?? node.measured?.width ?? node.width ?? defaultW
    const h = node.dimensions?.height ?? node.measured?.height ?? node.height ?? defaultH
    return { width: Number(w) || defaultW, height: Number(h) || defaultH }
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
        hasInitialFitDoneForDiagram.value = true
        setTimeout(() => {
          if (useMindMapV2.value) {
            fitToFullCanvas(true)
          } else {
            centerDiagramAtDefaultZoom(false)
            eventBus.emit('view:fit_completed', { mode: 'mind_map_centered', animate: false })
          }
        }, Math.max(ANIMATION.FIT_VIEWPORT_DELAY, 450))
        return
      }
      if (diagramStore.type === 'concept_map') {
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
              eventBus.emit('view:fit_completed', { mode: 'cmap_import_hull', animate: true })
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
              eventBus.emit('view:fit_completed', { mode: 'concept_map_topic', animate: true })
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
    hasInitialFitDoneForDiagram.value = true
    setTimeout(() => {
      eventBus.emit('view:fit_to_canvas_requested', { animate: true })
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
      eventBus.emit('view:fit_to_canvas_requested', { animate: true })
    }, ANIMATION.FIT_DELAY)
  }

  function clearFitTimersOnUnmount(): void {
    if (fitFromNodesChangeTimeoutId) {
      clearTimeout(fitFromNodesChangeTimeoutId)
      fitFromNodesChangeTimeoutId = null
    }
  }

  watch(
    () => nodesLength.value,
    (newLength, oldLength) => {
      if (!fitViewOnInit.value || newLength === 0) return
      if (oldLength === undefined) return
      if (diagramStore.type === 'concept_map') return
      setTimeout(() => {
        eventBus.emit('view:fit_to_canvas_requested', { animate: true })
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
        eventBus.emit('view:fit_to_canvas_requested', { animate: true })
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
    scheduleFitAfterStructuralNodeChange,
    clearFitTimersOnUnmount,
  }
}
