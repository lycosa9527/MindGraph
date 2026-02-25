/**
 * Keyboard Composable - Keyboard shortcuts
 *
 * Provides two approaches:
 * 1. Traditional: useKeyboard() with manual event listeners
 * 2. VueUse + VueFlow: useVueFlowKeyboard() with useMagicKeys integration
 */
import { onMounted, onUnmounted, watch } from 'vue'

import { useVueFlow } from '@vue-flow/core'
import { useMagicKeys } from '@vueuse/core'

import { eventBus } from './useEventBus'

export interface KeyboardShortcut {
  key: string
  ctrl?: boolean
  shift?: boolean
  alt?: boolean
  meta?: boolean
  handler: (event: KeyboardEvent) => void
  preventDefault?: boolean
}

export function useKeyboard(shortcuts: KeyboardShortcut[]) {
  function handleKeydown(event: KeyboardEvent): void {
    for (const shortcut of shortcuts) {
      const keyMatch = event.key.toLowerCase() === shortcut.key.toLowerCase()
      const ctrlMatch = !!shortcut.ctrl === (event.ctrlKey || event.metaKey)
      const shiftMatch = !!shortcut.shift === event.shiftKey
      const altMatch = !!shortcut.alt === event.altKey

      if (keyMatch && ctrlMatch && shiftMatch && altMatch) {
        if (shortcut.preventDefault !== false) {
          event.preventDefault()
        }
        shortcut.handler(event)
        return
      }
    }
  }

  onMounted(() => {
    window.addEventListener('keydown', handleKeydown)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', handleKeydown)
  })
}

/**
 * Common editor shortcuts
 */
export function useEditorShortcuts(handlers: {
  undo?: () => void
  redo?: () => void
  save?: () => void
  delete?: () => void
  selectAll?: () => void
  copy?: () => void
  paste?: () => void
  escape?: () => void
  addNode?: () => void
  clearNodeText?: () => void
}) {
  const shortcuts: KeyboardShortcut[] = []

  if (handlers.undo) {
    shortcuts.push({ key: 'z', ctrl: true, handler: handlers.undo })
  }

  if (handlers.redo) {
    shortcuts.push({ key: 'z', ctrl: true, shift: true, handler: handlers.redo })
    shortcuts.push({ key: 'y', ctrl: true, handler: handlers.redo })
  }

  if (handlers.save) {
    shortcuts.push({ key: 's', ctrl: true, handler: handlers.save })
  }

  if (handlers.delete) {
    shortcuts.push({ key: 'Delete', handler: handlers.delete, preventDefault: false })
    shortcuts.push({ key: 'Backspace', handler: handlers.delete, preventDefault: false })
  }

  if (handlers.selectAll) {
    shortcuts.push({ key: 'a', ctrl: true, handler: handlers.selectAll })
  }

  if (handlers.copy) {
    shortcuts.push({ key: 'c', ctrl: true, handler: handlers.copy, preventDefault: false })
  }

  if (handlers.paste) {
    shortcuts.push({ key: 'v', ctrl: true, handler: handlers.paste, preventDefault: false })
  }

  if (handlers.escape) {
    shortcuts.push({ key: 'Escape', handler: handlers.escape })
  }

  if (handlers.addNode) {
    shortcuts.push({ key: '=', handler: handlers.addNode })
  }

  if (handlers.clearNodeText) {
    shortcuts.push({ key: '-', handler: handlers.clearNodeText })
  }

  useKeyboard(shortcuts)
}

// ============================================================================
// VueFlow + VueUse Integration (New)
// ============================================================================

export interface UseVueFlowKeyboardOptions {
  /** Enable delete key for removing selected nodes/edges */
  enableDelete?: boolean
  /** Enable Ctrl+Z/Ctrl+Y for undo/redo via EventBus */
  enableUndoRedo?: boolean
  /** Enable Escape to clear selection */
  enableEscape?: boolean
  /** Enable Ctrl+A to select all */
  enableSelectAll?: boolean
  /** Custom delete handler (overrides default) */
  onDelete?: () => void
  /** Custom escape handler (overrides default) */
  onEscape?: () => void
}

/**
 * VueFlow keyboard shortcuts using VueUse's useMagicKeys
 *
 * Provides reactive keyboard handling integrated with VueFlow:
 * - Delete/Backspace: Remove selected nodes and edges
 * - Ctrl+Z: Undo (via EventBus)
 * - Ctrl+Shift+Z / Ctrl+Y: Redo (via EventBus)
 * - Escape: Clear selection
 *
 * Usage:
 *   useVueFlowKeyboard() // Enable all defaults
 *   useVueFlowKeyboard({ enableDelete: true, enableUndoRedo: false })
 */
export function useVueFlowKeyboard(options: UseVueFlowKeyboardOptions = {}): void {
  const {
    enableDelete = true,
    enableUndoRedo = true,
    enableEscape = true,
    enableSelectAll = false, // VueFlow handles this by default
    onDelete,
    onEscape,
  } = options

  // VueFlow instance
  const { removeNodes, removeEdges, getSelectedNodes, getSelectedEdges, nodes: allNodes } =
    useVueFlow()

  // VueUse magic keys - reactive keyboard state
  const keys = useMagicKeys({
    passive: false,
    onEventFired(e) {
      // Prevent default for handled shortcuts
      if (e.type === 'keydown') {
        const isDelete = e.key === 'Delete' || e.key === 'Backspace'
        const isUndo = (e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey
        const isRedo =
          ((e.ctrlKey || e.metaKey) && e.key === 'z' && e.shiftKey) ||
          ((e.ctrlKey || e.metaKey) && e.key === 'y')

        // Don't prevent default if user is typing in an input
        const target = e.target as HTMLElement
        const isInput =
          target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.isContentEditable

        if (isInput) return

        if ((enableDelete && isDelete) || (enableUndoRedo && (isUndo || isRedo))) {
          e.preventDefault()
        }
      }
    },
  })

  // =========================================================================
  // Delete Handler
  // =========================================================================

  if (enableDelete) {
    watch(
      () => keys.delete.value || keys.backspace.value,
      (pressed) => {
        if (!pressed) return

        // Check if user is in an editable element
        const activeElement = document.activeElement as HTMLElement
        if (
          activeElement?.tagName === 'INPUT' ||
          activeElement?.tagName === 'TEXTAREA' ||
          activeElement?.isContentEditable
        ) {
          return
        }

        if (onDelete) {
          onDelete()
        } else {
          // Default: remove selected nodes and edges
          const selectedNodes = getSelectedNodes.value
          const selectedEdges = getSelectedEdges.value

          if (selectedNodes.length > 0) {
            removeNodes(selectedNodes.map((n) => n.id))
          }
          if (selectedEdges.length > 0) {
            removeEdges(selectedEdges.map((e) => e.id))
          }

          // Emit event for history tracking
          if (selectedNodes.length > 0 || selectedEdges.length > 0) {
            eventBus.emit('keyboard:delete_executed', {
              nodeCount: selectedNodes.length,
              edgeCount: selectedEdges.length,
            })
          }
        }
      }
    )
  }

  // =========================================================================
  // Undo/Redo Handler
  // =========================================================================

  if (enableUndoRedo) {
    // Ctrl+Z - Undo
    watch(
      () => keys.ctrl_z.value || keys.cmd_z.value,
      (pressed) => {
        if (!pressed) return
        if (keys.shift.value) return // Shift+Ctrl+Z is redo

        eventBus.emit('history:undo_requested', {})
      }
    )

    // Ctrl+Shift+Z or Ctrl+Y - Redo
    watch(
      () => keys.ctrl_shift_z.value || keys.cmd_shift_z.value || keys.ctrl_y.value || keys.cmd_y.value,
      (pressed) => {
        if (!pressed) return

        eventBus.emit('history:redo_requested', {})
      }
    )
  }

  // =========================================================================
  // Escape Handler
  // =========================================================================

  if (enableEscape) {
    watch(
      () => keys.escape.value,
      (pressed) => {
        if (!pressed) return

        if (onEscape) {
          onEscape()
        } else {
          // Default: clear selection (VueFlow handles this, but emit event)
          eventBus.emit('keyboard:escape_pressed', {})
        }
      }
    )
  }

  // =========================================================================
  // Select All Handler
  // =========================================================================

  if (enableSelectAll) {
    watch(
      () => keys.ctrl_a.value || keys.cmd_a.value,
      (pressed) => {
        if (!pressed) return

        // Check if user is in an editable element
        const activeElement = document.activeElement as HTMLElement
        if (
          activeElement?.tagName === 'INPUT' ||
          activeElement?.tagName === 'TEXTAREA' ||
          activeElement?.isContentEditable
        ) {
          return
        }

        // Select all nodes
        allNodes.value.forEach((node) => {
          node.selected = true
        })

        eventBus.emit('keyboard:select_all_executed', {
          nodeCount: allNodes.value.length,
        })
      }
    )
  }
}
