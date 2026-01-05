/**
 * Session Lifecycle Manager Composable
 *
 * Centralized manager lifecycle tracking for memory leak prevention.
 * Ensures all managers/composables are properly destroyed during session cleanup.
 *
 * Migrated from archive/static/js/core/session-lifecycle.js
 */
import { ref, shallowRef } from 'vue'

import { eventBus } from './useEventBus'

// ============================================================================
// Types
// ============================================================================

/**
 * Interface for destroyable managers
 */
export interface Destroyable {
  destroy?: () => void
  cleanup?: () => void
  dispose?: () => void
}

interface ManagerEntry {
  manager: Destroyable
  name: string
  registeredAt: number
}

interface SessionInfo {
  sessionId: string | null
  diagramType: string | null
  managerCount: number
  managers: string[]
  startedAt: number | null
}

interface CleanupResult {
  success: number
  errors: number
  leaks: string[]
}

// ============================================================================
// Known Owners (for leak detection)
// ============================================================================

/**
 * Session-scoped owners that should be destroyed and have no listeners after cleanup
 */
const SESSION_SCOPED_OWNERS = [
  'InteractiveEditor',
  'ViewManager',
  'InteractionHandler',
  'CanvasController',
  'HistoryManager',
  'DiagramOperationsLoader',
  'MindMateManager',
  'LLMAutoCompleteManager',
  'SessionManager',
  'ToolbarManager',
  'PropertyPanelManager',
  'ExportManager',
  'AutoCompleteManager',
  'SmallOperationsManager',
  'TextToolbarStateManager',
  'VoiceAgentManager',
  'LLMValidationManager',
  'NodePropertyOperationsManager',
  'NodeCounterFeatureModeManager',
  'UIStateLLMManager',
]

/**
 * Global owners that persist across sessions (listeners are expected)
 */
const GLOBAL_OWNERS = ['PanelManager']

// ============================================================================
// Session Lifecycle Manager (Singleton)
// ============================================================================

class SessionLifecycleManager {
  private currentSessionId = ref<string | null>(null)
  private diagramType = ref<string | null>(null)
  private managers = shallowRef<ManagerEntry[]>([])
  private startedAt = ref<number | null>(null)
  private debugMode = ref(false)

  constructor() {
    if (this.debugMode.value) {
      console.log('[SessionLifecycle] Manager initialized')
    }
  }

  // ==========================================================================
  // Session Management
  // ==========================================================================

  /**
   * Start a new session
   */
  startSession(sessionId: string, diagramType: string): void {
    // Clean up previous session if any
    if (this.managers.value.length > 0) {
      console.warn('[SessionLifecycle] Starting new session with existing managers', {
        oldSession: this.currentSessionId.value?.slice(-8),
        newSession: sessionId.slice(-8),
        managerCount: this.managers.value.length,
      })
      this.cleanup()
    }

    this.currentSessionId.value = sessionId
    this.diagramType.value = diagramType
    this.startedAt.value = Date.now()

    if (this.debugMode.value) {
      console.log('[SessionLifecycle] Session started', {
        sessionId: sessionId.slice(-8),
        diagramType,
      })
    }
  }

  /**
   * Register a manager for lifecycle management
   * @returns The manager (for chaining)
   */
  register<T extends Destroyable>(manager: T, name: string): T {
    if (!manager) {
      console.error(`[SessionLifecycle] Cannot register null manager: ${name}`)
      return manager
    }

    // Check if manager has a cleanup method
    const hasDestroy = typeof manager.destroy === 'function'
    const hasCleanup = typeof manager.cleanup === 'function'
    const hasDispose = typeof manager.dispose === 'function'

    if (!hasDestroy && !hasCleanup && !hasDispose) {
      console.warn(`[SessionLifecycle] Manager "${name}" has no destroy/cleanup/dispose method`)
    }

    this.managers.value = [
      ...this.managers.value,
      {
        manager,
        name,
        registeredAt: Date.now(),
      },
    ]

    if (this.debugMode.value) {
      console.log(`[SessionLifecycle] Registered: ${name}`, {
        totalManagers: this.managers.value.length,
      })
    }

    return manager
  }

  /**
   * Unregister a specific manager (if it needs early cleanup)
   */
  unregister(name: string): boolean {
    const index = this.managers.value.findIndex((m) => m.name === name)
    if (index === -1) {
      return false
    }

    const newManagers = [...this.managers.value]
    newManagers.splice(index, 1)
    this.managers.value = newManagers

    if (this.debugMode.value) {
      console.log(`[SessionLifecycle] Unregistered: ${name}`, {
        totalManagers: this.managers.value.length,
      })
    }

    return true
  }

  // ==========================================================================
  // Cleanup
  // ==========================================================================

  /**
   * Clean up all registered managers
   */
  cleanup(): CleanupResult {
    const result: CleanupResult = {
      success: 0,
      errors: 0,
      leaks: [],
    }

    if (this.managers.value.length === 0) {
      if (this.debugMode.value) {
        console.log('[SessionLifecycle] No managers to clean up')
      }
      return result
    }

    // Store session ID before clearing (for event emission)
    const sessionIdToCleanup = this.currentSessionId.value

    console.log('[SessionLifecycle] Cleaning up session', {
      sessionId: sessionIdToCleanup?.slice(-8),
      diagramType: this.diagramType.value,
      managerCount: this.managers.value.length,
    })

    // Emit lifecycle event BEFORE destroying managers
    // This allows managers to cancel operations before destruction
    eventBus.emit('lifecycle:session_ending', {
      sessionId: sessionIdToCleanup || undefined,
      diagramType: this.diagramType.value || undefined,
      managerCount: this.managers.value.length,
    })

    // Destroy in reverse order (LIFO - Last In First Out)
    const managers = [...this.managers.value]
    for (let i = managers.length - 1; i >= 0; i--) {
      const { manager, name } = managers[i]

      try {
        if (typeof manager.destroy === 'function') {
          if (this.debugMode.value) {
            console.log(`[SessionLifecycle] Destroying: ${name}`)
          }
          manager.destroy()
          result.success++
        } else if (typeof manager.cleanup === 'function') {
          if (this.debugMode.value) {
            console.log(`[SessionLifecycle] Cleaning up: ${name}`)
          }
          manager.cleanup()
          result.success++
        } else if (typeof manager.dispose === 'function') {
          if (this.debugMode.value) {
            console.log(`[SessionLifecycle] Disposing: ${name}`)
          }
          manager.dispose()
          result.success++
        } else {
          console.warn(`[SessionLifecycle] Skipping ${name} (no cleanup method)`)
        }
      } catch (error) {
        result.errors++
        console.error(`[SessionLifecycle] Error destroying ${name}:`, error)
      }
    }

    // Clear registry
    this.managers.value = []
    this.currentSessionId.value = null
    this.diagramType.value = null
    this.startedAt.value = null

    // Check for listener leaks
    result.leaks = this.detectListenerLeaks()

    console.log('[SessionLifecycle] Session cleanup complete', {
      success: result.success,
      errors: result.errors,
      leaks: result.leaks.length,
    })

    // Emit cleanup completed event
    eventBus.emit('session:cleanup_completed', {
      cleanedCount: result.success,
    })

    return result
  }

  /**
   * Detect listener leaks after cleanup
   */
  private detectListenerLeaks(): string[] {
    const leaks: string[] = []

    try {
      const remainingListeners = eventBus.getAllListeners()

      SESSION_SCOPED_OWNERS.forEach((owner) => {
        const ownerListeners = remainingListeners[owner]
        if (ownerListeners && ownerListeners.length > 0) {
          leaks.push(owner)
          console.warn(`[SessionLifecycle] Listener leak detected for ${owner}`, {
            count: ownerListeners.length,
            events: ownerListeners.map((l) => l.event),
          })
        }
      })

      // Log global owners for debugging (not a leak, just informational)
      if (this.debugMode.value) {
        GLOBAL_OWNERS.forEach((owner) => {
          const ownerListeners = remainingListeners[owner]
          if (ownerListeners && ownerListeners.length > 0) {
            console.log(
              `[SessionLifecycle] Global manager ${owner} has ${ownerListeners.length} listeners (expected)`
            )
          }
        })
      }
    } catch {
      // EventBus might not have getAllListeners in all cases
    }

    return leaks
  }

  // ==========================================================================
  // State Accessors
  // ==========================================================================

  /**
   * Get current session info
   */
  getSessionInfo(): SessionInfo {
    return {
      sessionId: this.currentSessionId.value,
      diagramType: this.diagramType.value,
      managerCount: this.managers.value.length,
      managers: this.managers.value.map((m) => m.name),
      startedAt: this.startedAt.value,
    }
  }

  /**
   * Check if a session is active
   */
  hasActiveSession(): boolean {
    return this.currentSessionId.value !== null
  }

  /**
   * Get current session ID
   */
  getSessionId(): string | null {
    return this.currentSessionId.value
  }

  /**
   * Get current diagram type
   */
  getDiagramType(): string | null {
    return this.diagramType.value
  }

  /**
   * Get registered manager count
   */
  getManagerCount(): number {
    return this.managers.value.length
  }

  /**
   * Get registered manager names
   */
  getManagerNames(): string[] {
    return this.managers.value.map((m) => m.name)
  }

  // ==========================================================================
  // Debug
  // ==========================================================================

  /**
   * Enable/disable debug mode
   */
  setDebugMode(enabled: boolean): void {
    this.debugMode.value = enabled
    console.log(`[SessionLifecycle] Debug mode ${enabled ? 'enabled' : 'disabled'}`)
  }
}

// ============================================================================
// Singleton Instance
// ============================================================================

const sessionLifecycle = new SessionLifecycleManager()

// Expose debug tools on window in development
if (typeof window !== 'undefined' && import.meta.env.DEV) {
  ;(window as unknown as Record<string, unknown>).debugSessionLifecycle = {
    info: () => sessionLifecycle.getSessionInfo(),
    managers: () => sessionLifecycle.getManagerNames(),
    cleanup: () => sessionLifecycle.cleanup(),
    debug: (enabled: boolean) => sessionLifecycle.setDebugMode(enabled),
  }

  console.log('%c[SessionLifecycle] Debug tools available:', 'color: #2196f3; font-weight: bold;')
  console.log('  window.debugSessionLifecycle.info()    - View session info')
  console.log('  window.debugSessionLifecycle.managers() - List registered managers')
  console.log('  window.debugSessionLifecycle.cleanup()  - Force cleanup')
  console.log('  window.debugSessionLifecycle.debug(true/false) - Toggle debug mode')
}

// ============================================================================
// Vue Composable
// ============================================================================

/**
 * Session Lifecycle composable for Vue components
 *
 * Usage:
 * ```typescript
 * const { startSession, register, cleanup, getSessionInfo } = useSessionLifecycle()
 *
 * // Start a new session
 * startSession('session-123', 'bubble_map')
 *
 * // Register managers for lifecycle tracking
 * register(historyManager, 'HistoryManager')
 * register(viewManager, 'ViewManager')
 *
 * // Cleanup when done (or it happens automatically on component unmount)
 * cleanup()
 * ```
 */
export function useSessionLifecycle() {
  return {
    // Session management
    startSession: sessionLifecycle.startSession.bind(sessionLifecycle),
    register: sessionLifecycle.register.bind(sessionLifecycle),
    unregister: sessionLifecycle.unregister.bind(sessionLifecycle),
    cleanup: sessionLifecycle.cleanup.bind(sessionLifecycle),

    // State accessors
    getSessionInfo: sessionLifecycle.getSessionInfo.bind(sessionLifecycle),
    hasActiveSession: sessionLifecycle.hasActiveSession.bind(sessionLifecycle),
    getSessionId: sessionLifecycle.getSessionId.bind(sessionLifecycle),
    getDiagramType: sessionLifecycle.getDiagramType.bind(sessionLifecycle),
    getManagerCount: sessionLifecycle.getManagerCount.bind(sessionLifecycle),
    getManagerNames: sessionLifecycle.getManagerNames.bind(sessionLifecycle),

    // Debug
    setDebugMode: sessionLifecycle.setDebugMode.bind(sessionLifecycle),
  }
}

// ============================================================================
// Direct Access (for use outside components)
// ============================================================================

export { sessionLifecycle }

// Types are already exported at definition
// SessionInfo and CleanupResult can be re-exported if not already exported
export type { SessionInfo, CleanupResult }
