/**
 * useViewManager - Composable for zoom, pan, and fit operations
 *
 * Handles:
 * - Zoom in/out/reset operations
 * - Fit-to-canvas with panel space awareness (two-view zoom system)
 * - Window resize handling
 * - EventBus integration for view commands
 *
 * Two-View Zoom System:
 * - fitToFullCanvas(): Fits diagram to full canvas width
 * - fitWithPanel(): Fits diagram with space reserved for right-side panels
 * - Uses Pinia panels store for reactive panel state (not DOM queries)
 *
 * Migrated from archive/static/js/managers/editor/view-manager.js
 */
import { computed, onMounted, onUnmounted, ref, watch, type Ref } from 'vue'

import { useDebounceFn, useElementSize } from '@vueuse/core'

import { ANIMATION, BREAKPOINTS, FIT_PADDING, PANEL, ZOOM } from '@/config/uiConfig'
import { usePanelsStore } from '@/stores'

import { eventBus } from './useEventBus'

// ============================================================================
// Types
// ============================================================================

export interface ViewState {
  zoom: number
  panX: number
  panY: number
}

export interface ViewBounds {
  x: number
  y: number
  width: number
  height: number
}

export interface FitOptions {
  animate?: boolean
  reserveForPanel?: boolean
  padding?: number
}

export interface UseViewManagerOptions {
  ownerId?: string
  minZoom?: number
  maxZoom?: number
  zoomStep?: number
  onZoomChange?: (zoom: number) => void
  onFit?: (bounds: ViewBounds) => void
  /** Optional ref to container element for reactive size tracking via VueUse */
  containerRef?: Ref<HTMLElement | null>
}

// ============================================================================
// Composable
// ============================================================================

export function useViewManager(options: UseViewManagerOptions = {}) {
  const {
    ownerId = `ViewManager_${Date.now()}`,
    minZoom = ZOOM.MIN,
    maxZoom = ZOOM.MAX,
    zoomStep = ZOOM.STEP,
    onZoomChange,
    onFit,
    containerRef,
  } = options

  // =========================================================================
  // State
  // =========================================================================

  const zoom = ref(1)
  const panX = ref(0)
  const panY = ref(0)
  const isFittedForPanel = ref(false)

  // Container dimensions - use VueUse's useElementSize if containerRef provided
  // This provides reactive, auto-updating dimensions with automatic cleanup
  const { width: vueUseWidth, height: vueUseHeight } = containerRef
    ? useElementSize(containerRef)
    : { width: ref(0), height: ref(0) }

  // Use VueUse dimensions if containerRef provided, otherwise fall back to manual tracking
  const containerWidth = containerRef ? vueUseWidth : ref(0)
  const containerHeight = containerRef ? vueUseHeight : ref(0)

  // Content bounds (set by renderer)
  const contentBounds = ref<ViewBounds | null>(null)

  // =========================================================================
  // Computed
  // =========================================================================

  const zoomPercent = computed(() => Math.round(zoom.value * 100))
  const canZoomIn = computed(() => zoom.value < maxZoom)
  const canZoomOut = computed(() => zoom.value > minZoom)

  const viewState = computed<ViewState>(() => ({
    zoom: zoom.value,
    panX: panX.value,
    panY: panY.value,
  }))

  // =========================================================================
  // Zoom Operations
  // =========================================================================

  function zoomIn(): void {
    const newZoom = Math.min(zoom.value * zoomStep, maxZoom)
    setZoom(newZoom)
    eventBus.emit('view:zoomed', { direction: 'in', level: newZoom })
  }

  function zoomOut(): void {
    const newZoom = Math.max(zoom.value / zoomStep, minZoom)
    setZoom(newZoom)
    eventBus.emit('view:zoomed', { direction: 'out', level: newZoom })
  }

  function resetZoom(): void {
    setZoom(1)
    setPan(0, 0)
    eventBus.emit('view:zoomed', { direction: 'reset', level: 1 })
  }

  function setZoom(newZoom: number): void {
    zoom.value = Math.max(minZoom, Math.min(maxZoom, newZoom))
    onZoomChange?.(zoom.value)

    eventBus.emit('view:zoom_changed', {
      zoom: zoom.value,
      zoomPercent: zoomPercent.value,
    })
  }

  function setPan(x: number, y: number): void {
    panX.value = x
    panY.value = y

    eventBus.emit('view:pan_changed', {
      panX: x,
      panY: y,
    })
  }

  // =========================================================================
  // Fit Operations
  // =========================================================================

  /**
   * Calculate viewBox for fit-to-canvas
   */
  function calculateFitViewBox(opts: FitOptions = {}): ViewBounds | null {
    const { reserveForPanel: _reserveForPanel = false, padding = FIT_PADDING.STANDARD } = opts

    if (!contentBounds.value) return null

    const bounds = contentBounds.value
    const paddingAmount = Math.min(bounds.width, bounds.height) * padding

    // Calculate viewBox with padding
    const viewBox: ViewBounds = {
      x: bounds.x - paddingAmount,
      y: bounds.y - paddingAmount,
      width: bounds.width + paddingAmount * 2,
      height: bounds.height + paddingAmount * 2,
    }

    return viewBox
  }

  /**
   * Fit diagram to full canvas (no panel space reserved)
   */
  function fitToFullCanvas(animate = true): ViewBounds | null {
    const viewBox = calculateFitViewBox({ reserveForPanel: false })

    if (viewBox) {
      isFittedForPanel.value = false
      resetZoom()

      eventBus.emit('view:fit_completed', {
        mode: 'full_canvas',
        viewBox,
        animate,
      })

      onFit?.(viewBox)
    }

    return viewBox
  }

  /**
   * Fit diagram with panel space reserved
   */
  function fitWithPanel(animate = true): ViewBounds | null {
    const viewBox = calculateFitViewBox({ reserveForPanel: true })

    if (viewBox) {
      isFittedForPanel.value = true
      resetZoom()

      eventBus.emit('view:fit_completed', {
        mode: 'with_panel',
        viewBox,
        animate,
      })

      onFit?.(viewBox)
    }

    return viewBox
  }

  /**
   * Smart fit based on current panel visibility
   */
  function fitDiagram(animate = true): ViewBounds | null {
    // Check if any panel is visible
    const isPanelVisible = checkPanelVisibility()

    if (isPanelVisible) {
      return fitWithPanel(animate)
    } else {
      return fitToFullCanvas(animate)
    }
  }

  /**
   * Fit for export (no animation, minimal padding)
   */
  function fitForExport(): ViewBounds | null {
    const viewBox = calculateFitViewBox({ padding: FIT_PADDING.MINIMAL }) // Minimal padding for export

    if (viewBox) {
      resetZoom()

      eventBus.emit('view:fit_completed', {
        mode: 'export',
        viewBox,
        animate: false,
      })
    }

    return viewBox
  }

  // =========================================================================
  // Panel Visibility Check (using Pinia store)
  // =========================================================================

  // Get panels store for reactive panel state
  const panelsStore = usePanelsStore()

  /**
   * Check if any panel is currently visible
   * Uses Pinia store instead of DOM queries for better reactivity
   */
  function checkPanelVisibility(): boolean {
    return panelsStore.anyPanelOpen
  }

  /**
   * Get the total width of open panels (right-side panels)
   */
  function getRightPanelWidth(): number {
    let width = 0
    if (panelsStore.propertyPanel.isOpen) {
      width = PANEL.PROPERTY_WIDTH
    } else if (panelsStore.mindmatePanel.isOpen) {
      width = PANEL.MINDMATE_WIDTH
    }
    return width
  }

  /**
   * Get the width of left-side panels
   */
  function getLeftPanelWidth(): number {
    if (panelsStore.nodePalettePanel.isOpen) {
      return PANEL.NODE_PALETTE_WIDTH
    }
    return 0
  }

  /**
   * Get total panel width (left + right)
   */
  function getTotalPanelWidth(): number {
    return getRightPanelWidth() + getLeftPanelWidth()
  }

  // Computed for reactive panel state
  const isAnyPanelOpen = computed(() => panelsStore.anyPanelOpen)
  const totalPanelWidth = computed(() => getTotalPanelWidth())

  // =========================================================================
  // Content Bounds Management
  // =========================================================================

  function setContentBounds(bounds: ViewBounds): void {
    contentBounds.value = bounds
  }

  function updateContainerSize(width: number, height: number): void {
    containerWidth.value = width
    containerHeight.value = height
  }

  // =========================================================================
  // Window Resize Handling
  // =========================================================================

  // Debounced resize handler using VueUse
  const handleWindowResize = useDebounceFn(() => {
    // If using VueUse's useElementSize (containerRef provided), dimensions update automatically
    // Otherwise, manually query the container
    if (!containerRef) {
      const container = document.querySelector('.vue-flow') as HTMLElement
      if (container) {
        updateContainerSize(container.clientWidth, container.clientHeight)
      }
    }

    // Refit diagram (no animation for responsive feel)
    fitDiagram(false)
  }, ANIMATION.RESIZE_DEBOUNCE)

  // =========================================================================
  // Mobile Detection
  // =========================================================================

  function isMobileDevice(): boolean {
    return (
      /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
      window.innerWidth <= BREAKPOINTS.MOBILE
    )
  }

  // =========================================================================
  // EventBus Subscriptions
  // =========================================================================

  eventBus.onWithOwner('view:zoom_in_requested', () => zoomIn(), ownerId)
  eventBus.onWithOwner('view:zoom_out_requested', () => zoomOut(), ownerId)
  eventBus.onWithOwner('view:zoom_reset_requested', () => resetZoom(), ownerId)

  eventBus.onWithOwner(
    'view:fit_to_window_requested',
    (data) => {
      const animate = data?.animate !== false
      fitToFullCanvas(animate)
    },
    ownerId
  )

  eventBus.onWithOwner(
    'view:fit_to_canvas_requested',
    (data) => {
      const animate = data?.animate !== false
      fitWithPanel(animate)
    },
    ownerId
  )

  eventBus.onWithOwner('view:fit_diagram_requested', () => fitDiagram(true), ownerId)

  eventBus.onWithOwner(
    'diagram:rendered',
    () => {
      // Auto-fit on render if needed
      if (contentBounds.value) {
        const bounds = contentBounds.value
        const exceedsContainer =
          bounds.width > containerWidth.value * 0.9 || bounds.height > containerHeight.value * 0.9

        if (exceedsContainer) {
          fitDiagram(true)
        }
      }
    },
    ownerId
  )

  eventBus.onWithOwner('window:resized', () => handleWindowResize(), ownerId)

  eventBus.onWithOwner('view:fit_for_export_requested', () => fitForExport(), ownerId)

  // =========================================================================
  // Panel State Watcher
  // =========================================================================

  // Watch panel state changes and re-fit diagram when panels open/close
  watch(
    () => panelsStore.anyPanelOpen,
    (isOpen, wasOpen) => {
      // Only re-fit if panel state actually changed and we have content
      if (isOpen !== wasOpen && contentBounds.value) {
        // Delay to allow panel animation to start
        setTimeout(() => fitDiagram(true), 50)
      }
    }
  )

  // =========================================================================
  // VueUse Container Size Watcher
  // =========================================================================

  // When using VueUse's useElementSize (containerRef provided), watch for size changes
  // and refit diagram automatically
  if (containerRef) {
    watch(
      [containerWidth, containerHeight],
      ([newWidth, newHeight], [oldWidth, oldHeight]) => {
        // Only refit if size actually changed significantly (avoid initial 0 -> value triggers)
        if (
          oldWidth > 0 &&
          oldHeight > 0 &&
          (Math.abs(newWidth - oldWidth) > 10 || Math.abs(newHeight - oldHeight) > 10)
        ) {
          fitDiagram(false)
        }
      }
    )
  }

  // =========================================================================
  // Lifecycle
  // =========================================================================

  onMounted(() => {
    // If not using containerRef (VueUse), manually initialize container size
    if (!containerRef) {
      const container = document.querySelector('.vue-flow') as HTMLElement
      if (container) {
        updateContainerSize(container.clientWidth, container.clientHeight)
      }
    }

    // Add window resize listener (still needed for orientation changes, etc.)
    window.addEventListener('resize', handleWindowResize)
  })

  onUnmounted(() => {
    // Cleanup event bus listeners
    eventBus.removeAllListenersForOwner(ownerId)

    // VueUse automatically cleans up useElementSize, no manual cleanup needed
    window.removeEventListener('resize', handleWindowResize)
  })

  // =========================================================================
  // Return
  // =========================================================================

  return {
    // State
    zoom,
    panX,
    panY,
    isFittedForPanel,
    containerWidth,
    containerHeight,
    contentBounds,

    // Computed
    zoomPercent,
    canZoomIn,
    canZoomOut,
    viewState,
    isAnyPanelOpen,
    totalPanelWidth,

    // Zoom actions
    zoomIn,
    zoomOut,
    resetZoom,
    setZoom,
    setPan,

    // Fit actions
    fitToFullCanvas,
    fitWithPanel,
    fitDiagram,
    fitForExport,
    calculateFitViewBox,

    // Content management
    setContentBounds,
    updateContainerSize,

    // Panel utilities
    checkPanelVisibility,
    getRightPanelWidth,
    getLeftPanelWidth,
    getTotalPanelWidth,

    // Utilities
    isMobileDevice,
  }
}

// ============================================================================
// Vue Flow Integration Helper
// ============================================================================

/**
 * Create Vue Flow viewport handlers
 */
export function createVueFlowViewport(viewManager: ReturnType<typeof useViewManager>) {
  return {
    onViewportChange: (viewport: { x: number; y: number; zoom: number }) => {
      viewManager.setZoom(viewport.zoom)
      viewManager.setPan(viewport.x, viewport.y)
    },

    getViewport: () => ({
      x: viewManager.panX.value,
      y: viewManager.panY.value,
      zoom: viewManager.zoom.value,
    }),

    fitView: () => {
      viewManager.fitDiagram(true)
    },

    zoomIn: () => viewManager.zoomIn(),
    zoomOut: () => viewManager.zoomOut(),
    resetZoom: () => viewManager.resetZoom(),
  }
}
