/**
 * usePanelCoordination - Composable for panel coordination and mutual exclusion
 *
 * Handles:
 * - Mutual exclusion (only one panel open at a time)
 * - EventBus subscriptions for panel requests
 * - Current panel tracking
 * - Panel toggle with coordination
 *
 * Migrated from archive/static/js/managers/panel-manager.js
 */
import { computed, onUnmounted, ref } from 'vue'

import { usePanelsStore } from '@/stores/panels'

import { eventBus } from './useEventBus'

// ============================================================================
// Types
// ============================================================================

export type PanelName = 'mindmate' | 'nodePalette' | 'property'

export interface PanelOpenOptions {
  /** Source of the open request (for debugging) */
  source?: string
  /** Additional data to pass to the panel */
  data?: Record<string, unknown>
  /** Skip mutual exclusion (keep other panels open) */
  skipExclusion?: boolean
}

export interface UsePanelCoordinationOptions {
  ownerId?: string
  /** Enable mutual exclusion (default: true) */
  mutualExclusion?: boolean
  /** Blocked sources for auto-open prevention */
  blockedSources?: string[]
}

// ============================================================================
// Composable
// ============================================================================

export function usePanelCoordination(options: UsePanelCoordinationOptions = {}) {
  const {
    ownerId = `PanelCoord_${Date.now()}`,
    mutualExclusion = true,
    blockedSources = ['keyboard', 'focus', 'tab_navigation'],
  } = options

  const panelsStore = usePanelsStore()

  // =========================================================================
  // State
  // =========================================================================

  const currentPanel = ref<PanelName | null>(null)

  // =========================================================================
  // Computed
  // =========================================================================

  const isPanelOpen = computed(() => ({
    mindmate: panelsStore.mindmate.open,
    nodePalette: panelsStore.nodePalette.open,
    property: panelsStore.property.open,
  }))

  const anyPanelOpen = computed(() => panelsStore.anyPanelOpen)

  const openPanelCount = computed(() => panelsStore.openPanelCount)

  // =========================================================================
  // Panel Operations with Coordination
  // =========================================================================

  /**
   * Open a panel with mutual exclusion
   */
  function openPanel(name: PanelName, opts: PanelOpenOptions = {}): boolean {
    const { source, data, skipExclusion } = opts

    // Block automatic opens from certain sources
    if (source && blockedSources.includes(source)) {
      console.warn(`[PanelCoordination] Blocked panel open from source: ${source}`)
      return false
    }

    // Close other panels first (mutual exclusion)
    if (mutualExclusion && !skipExclusion) {
      closeAllExcept(name)
    }

    // Open the requested panel
    switch (name) {
      case 'mindmate':
        panelsStore.openMindmate(data)
        break
      case 'nodePalette':
        panelsStore.openNodePalette(data)
        break
      case 'property':
        if (data?.nodeId && data?.nodeData) {
          panelsStore.openProperty(data.nodeId as string, data.nodeData as Record<string, unknown>)
        } else {
          console.warn('[PanelCoordination] Property panel requires nodeId and nodeData')
          return false
        }
        break
      default:
        console.warn(`[PanelCoordination] Unknown panel: ${name}`)
        return false
    }

    currentPanel.value = name

    // Emit coordinated open event
    eventBus.emit('panel:coordinated_open', {
      panel: name,
      source,
      previousPanel: currentPanel.value,
    })

    return true
  }

  /**
   * Close a specific panel
   */
  function closePanel(name: PanelName): boolean {
    switch (name) {
      case 'mindmate':
        panelsStore.closeMindmate()
        break
      case 'nodePalette':
        panelsStore.closeNodePalette()
        break
      case 'property':
        panelsStore.closeProperty()
        break
      default:
        return false
    }

    if (currentPanel.value === name) {
      currentPanel.value = null
    }

    return true
  }

  /**
   * Toggle a panel (open if closed, close if open)
   */
  function togglePanel(name: PanelName, opts: PanelOpenOptions = {}): boolean {
    if (isPanelOpen.value[name]) {
      return closePanel(name)
    } else {
      return openPanel(name, opts)
    }
  }

  /**
   * Close all panels
   */
  function closeAllPanels(): void {
    panelsStore.closeAllPanels()
    currentPanel.value = null
  }

  /**
   * Close all panels except the specified one
   */
  function closeAllExcept(name: PanelName): void {
    const panels: PanelName[] = ['mindmate', 'nodePalette', 'property']

    panels.forEach((panelName) => {
      if (panelName !== name && isPanelOpen.value[panelName]) {
        closePanel(panelName)
      }
    })
  }

  // =========================================================================
  // Convenience Methods
  // =========================================================================

  function openMindmate(opts?: PanelOpenOptions): boolean {
    return openPanel('mindmate', opts)
  }

  function closeMindmate(): boolean {
    return closePanel('mindmate')
  }

  function toggleMindmate(opts?: PanelOpenOptions): boolean {
    return togglePanel('mindmate', opts)
  }

  function openNodePalette(opts?: PanelOpenOptions): boolean {
    return openPanel('nodePalette', opts)
  }

  function closeNodePalette(): boolean {
    return closePanel('nodePalette')
  }

  function toggleNodePalette(opts?: PanelOpenOptions): boolean {
    return togglePanel('nodePalette', opts)
  }

  function openProperty(nodeId: string, nodeData: Record<string, unknown>): boolean {
    return openPanel('property', { data: { nodeId, nodeData } })
  }

  function closeProperty(): boolean {
    return closePanel('property')
  }

  function toggleProperty(nodeId?: string, nodeData?: Record<string, unknown>): boolean {
    if (isPanelOpen.value.property) {
      return closePanel('property')
    } else if (nodeId && nodeData) {
      return openProperty(nodeId, nodeData)
    }
    return false
  }

  // =========================================================================
  // EventBus Subscriptions
  // =========================================================================

  // Listen for panel open requests
  eventBus.onWithOwner(
    'panel:open_requested',
    (data) => {
      const panel = data.panel as PanelName
      const source = data.source as string | undefined
      const options = data.options as Record<string, unknown> | undefined

      if (panel) {
        openPanel(panel, { source, data: options })
      }
    },
    ownerId
  )

  // Listen for panel close requests
  eventBus.onWithOwner(
    'panel:close_requested',
    (data) => {
      const panel = data.panel as PanelName
      if (panel) {
        closePanel(panel)
      }
    },
    ownerId
  )

  // Listen for panel toggle requests
  eventBus.onWithOwner(
    'panel:toggle_requested',
    (data) => {
      const panel = data.panel as PanelName
      if (panel) {
        togglePanel(panel)
      }
    },
    ownerId
  )

  // Listen for close all requests
  eventBus.onWithOwner('panel:close_all_requested', () => closeAllPanels(), ownerId)

  // Listen for node selection to auto-open property panel
  eventBus.onWithOwner(
    'interaction:selection_changed',
    (data) => {
      const selectedNodes = data.selectedNodes as string[] | undefined

      if (selectedNodes && selectedNodes.length === 1) {
        // Single node selected - could auto-open property panel
        // This is optional behavior, uncomment if desired:
        // openProperty(selectedNodes[0], {})
      } else if (selectedNodes && selectedNodes.length === 0) {
        // No selection - close property panel
        if (isPanelOpen.value.property) {
          closeProperty()
        }
      }
    },
    ownerId
  )

  // =========================================================================
  // Cleanup
  // =========================================================================

  function destroy(): void {
    eventBus.removeAllListenersForOwner(ownerId)
  }

  onUnmounted(() => {
    destroy()
  })

  // =========================================================================
  // Return
  // =========================================================================

  return {
    // State
    currentPanel,

    // Computed
    isPanelOpen,
    anyPanelOpen,
    openPanelCount,

    // Generic panel operations
    openPanel,
    closePanel,
    togglePanel,
    closeAllPanels,
    closeAllExcept,

    // Convenience methods
    openMindmate,
    closeMindmate,
    toggleMindmate,
    openNodePalette,
    closeNodePalette,
    toggleNodePalette,
    openProperty,
    closeProperty,
    toggleProperty,

    // Store access
    panelsStore,

    // Cleanup
    destroy,
  }
}

// ============================================================================
// Singleton for global access
// ============================================================================

let _globalCoordinator: ReturnType<typeof usePanelCoordination> | null = null

export function getPanelCoordinator(): ReturnType<typeof usePanelCoordination> {
  if (!_globalCoordinator) {
    _globalCoordinator = usePanelCoordination({ ownerId: 'GlobalPanelCoordinator' })
  }
  return _globalCoordinator
}
