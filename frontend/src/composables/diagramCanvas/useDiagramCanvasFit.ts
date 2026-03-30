import type { Ref } from 'vue'
import { ref, watch } from 'vue'

import { useVueFlow } from '@vue-flow/core'

import { eventBus } from '@/composables/core/useEventBus'
import { ANIMATION, FIT_PADDING, PANEL } from '@/config/uiConfig'
import type { useDiagramStore } from '@/stores/diagram'
import type { usePanelsStore } from '@/stores/panels'

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
    presentationRailOpen,
    presentationToolIsNotTimer,
    nodesLength,
  } = options

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
        left: `${FIT_PADDING.STANDARD_PX}px`,
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
          left: `${FIT_PADDING.STANDARD_PX}px`,
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
        left: adjustedPadding,
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

  function handleNodesInitialized(): void {
    if (!fitViewOnInit.value || getNodes().length === 0) return
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
      if (nodesLength.value > 0) {
        setTimeout(() => fitDiagram(true), ANIMATION.PANEL_DELAY)
      }
    }
  )

  watch(
    () => presentationRailOpen.value,
    (active, wasActive) => {
      if (active === wasActive) return
      if (active && getNodes().length > 0) {
        setTimeout(() => fitDiagram(true), ANIMATION.FIT_VIEWPORT_DELAY)
      }
    }
  )

  watch(
    () => Boolean(presentationRailOpen.value && presentationToolIsNotTimer.value),
    () => {
      if (!presentationRailOpen.value || getNodes().length === 0) return
      setTimeout(() => fitDiagram(true), ANIMATION.FIT_VIEWPORT_DELAY)
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
    scheduleFitAfterStructuralNodeChange,
    clearFitTimersOnUnmount,
  }
}
