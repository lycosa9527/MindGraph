/**
 * useViewManager - Composable for zoom, pan, and fit operations
 *
 * Handles:
 * - Zoom in/out/reset operations
 * - Fit-to-canvas with panel space awareness
 * - Window resize handling
 * - EventBus integration for view commands
 *
 * Migrated from archive/static/js/managers/editor/view-manager.js
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'

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
}

// ============================================================================
// Composable
// ============================================================================

export function useViewManager(options: UseViewManagerOptions = {}) {
  const {
    ownerId = `ViewManager_${Date.now()}`,
    minZoom = 0.1,
    maxZoom = 10,
    zoomStep = 1.3,
    onZoomChange,
    onFit,
  } = options

  // =========================================================================
  // State
  // =========================================================================

  const zoom = ref(1)
  const panX = ref(0)
  const panY = ref(0)
  const isFittedForPanel = ref(false)

  // Container dimensions (updated on resize)
  const containerWidth = ref(0)
  const containerHeight = ref(0)

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
    const { reserveForPanel: _reserveForPanel = false, padding = 0.1 } = opts

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
    const viewBox = calculateFitViewBox({ padding: 0.02 }) // 2% padding for export

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
  // Panel Visibility Check
  // =========================================================================

  function checkPanelVisibility(): boolean {
    // This can be overridden by the component or use Pinia store
    // Default implementation checks DOM (for compatibility)
    if (typeof document === 'undefined') return false

    const propertyPanel = document.getElementById('property-panel')
    const isPropertyVisible = propertyPanel && propertyPanel.style.display !== 'none'

    const aiPanel = document.getElementById('ai-assistant-panel')
    const isAIVisible = aiPanel && !aiPanel.classList.contains('collapsed')

    return !!(isPropertyVisible || isAIVisible)
  }

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

  let resizeTimeout: ReturnType<typeof setTimeout> | null = null

  function handleWindowResize(): void {
    if (resizeTimeout) {
      clearTimeout(resizeTimeout)
    }

    resizeTimeout = setTimeout(() => {
      // Update container size (Vue Flow container)
      const container = document.querySelector('.vue-flow') as HTMLElement
      if (container) {
        updateContainerSize(container.clientWidth, container.clientHeight)
      }

      // Refit diagram (no animation for responsive feel)
      fitDiagram(false)
    }, 150)
  }

  // =========================================================================
  // Mobile Detection
  // =========================================================================

  function isMobileDevice(): boolean {
    return (
      /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
      window.innerWidth <= 768
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

  // =========================================================================
  // Lifecycle
  // =========================================================================

  onMounted(() => {
    // Initialize container size (Vue Flow container)
    const container = document.querySelector('.vue-flow') as HTMLElement
    if (container) {
      updateContainerSize(container.clientWidth, container.clientHeight)
    }

    // Add window resize listener
    window.addEventListener('resize', handleWindowResize)
  })

  onUnmounted(() => {
    // Cleanup
    eventBus.removeAllListenersForOwner(ownerId)

    if (resizeTimeout) {
      clearTimeout(resizeTimeout)
    }

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

    // Utilities
    isMobileDevice,
    checkPanelVisibility,
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
