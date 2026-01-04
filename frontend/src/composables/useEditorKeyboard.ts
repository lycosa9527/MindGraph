/**
 * useEditorKeyboard - Composable for Vue Flow editor keyboard shortcuts
 * Extends useKeyboard with Vue Flow-specific commands
 */
import { onMounted, onUnmounted, ref } from 'vue'

import type { MindGraphEdge, MindGraphNode } from '@/types'

import { useSelection } from './useSelection'

export interface EditorKeyboardHandlers {
  // Node operations
  deleteSelected?: () => void
  duplicateSelected?: () => void
  addNode?: () => void
  editSelectedNode?: () => void

  // History
  undo?: () => void
  redo?: () => void

  // Selection
  selectAll?: () => void
  clearSelection?: () => void
  invertSelection?: () => void

  // View
  zoomIn?: () => void
  zoomOut?: () => void
  fitView?: () => void
  resetView?: () => void

  // File operations
  save?: () => void
  exportImage?: () => void

  // Clipboard
  copy?: () => void
  paste?: () => void
  cut?: () => void

  // Misc
  escape?: () => void
  toggleGrid?: () => void
  toggleMinimap?: () => void
}

export interface UseEditorKeyboardOptions {
  handlers: EditorKeyboardHandlers
  enabled?: boolean
  preventDefaultOnInput?: boolean
}

export function useEditorKeyboard(options: UseEditorKeyboardOptions) {
  const { handlers, enabled = true, preventDefaultOnInput = true } = options

  const isEnabled = ref(enabled)
  const selection = useSelection()

  // Check if the event target is an input element
  function isInputElement(target: EventTarget | null): boolean {
    if (!target || !(target instanceof HTMLElement)) return false

    const tagName = target.tagName.toLowerCase()
    if (tagName === 'input' || tagName === 'textarea' || tagName === 'select') {
      return true
    }

    if (target.isContentEditable) {
      return true
    }

    return false
  }

  // Main keydown handler
  function handleKeydown(event: KeyboardEvent): void {
    if (!isEnabled.value) return

    // Skip if focus is on an input element (unless we want to capture anyway)
    if (preventDefaultOnInput && isInputElement(event.target)) {
      // Allow Escape to still work in inputs
      if (event.key !== 'Escape') return
    }

    const { key, ctrlKey, metaKey, shiftKey } = event
    const cmdOrCtrl = ctrlKey || metaKey

    // Delete/Backspace - Delete selected
    if ((key === 'Delete' || key === 'Backspace') && handlers.deleteSelected) {
      if (!isInputElement(event.target)) {
        handlers.deleteSelected()
        event.preventDefault()
      }
      return
    }

    // Ctrl/Cmd + Z - Undo
    if (cmdOrCtrl && key === 'z' && !shiftKey && handlers.undo) {
      handlers.undo()
      event.preventDefault()
      return
    }

    // Ctrl/Cmd + Shift + Z or Ctrl/Cmd + Y - Redo
    if ((cmdOrCtrl && key === 'z' && shiftKey) || (cmdOrCtrl && key === 'y')) {
      if (handlers.redo) {
        handlers.redo()
        event.preventDefault()
      }
      return
    }

    // Ctrl/Cmd + A - Select all
    if (cmdOrCtrl && key === 'a' && handlers.selectAll) {
      handlers.selectAll()
      event.preventDefault()
      return
    }

    // Ctrl/Cmd + D - Duplicate
    if (cmdOrCtrl && key === 'd' && handlers.duplicateSelected) {
      handlers.duplicateSelected()
      event.preventDefault()
      return
    }

    // Ctrl/Cmd + S - Save
    if (cmdOrCtrl && key === 's' && handlers.save) {
      handlers.save()
      event.preventDefault()
      return
    }

    // Ctrl/Cmd + E - Export
    if (cmdOrCtrl && key === 'e' && handlers.exportImage) {
      handlers.exportImage()
      event.preventDefault()
      return
    }

    // Ctrl/Cmd + C - Copy
    if (cmdOrCtrl && key === 'c' && handlers.copy) {
      if (!isInputElement(event.target)) {
        handlers.copy()
        // Don't prevent default to allow native copy in inputs
      }
      return
    }

    // Ctrl/Cmd + V - Paste
    if (cmdOrCtrl && key === 'v' && handlers.paste) {
      if (!isInputElement(event.target)) {
        handlers.paste()
      }
      return
    }

    // Ctrl/Cmd + X - Cut
    if (cmdOrCtrl && key === 'x' && handlers.cut) {
      if (!isInputElement(event.target)) {
        handlers.cut()
      }
      return
    }

    // Ctrl/Cmd + + or = - Zoom in
    if (cmdOrCtrl && (key === '+' || key === '=') && handlers.zoomIn) {
      handlers.zoomIn()
      event.preventDefault()
      return
    }

    // Ctrl/Cmd + - - Zoom out
    if (cmdOrCtrl && key === '-' && handlers.zoomOut) {
      handlers.zoomOut()
      event.preventDefault()
      return
    }

    // Ctrl/Cmd + 0 - Reset view / Fit view
    if (cmdOrCtrl && key === '0' && handlers.fitView) {
      handlers.fitView()
      event.preventDefault()
      return
    }

    // Escape - Clear selection / Cancel
    if (key === 'Escape' && handlers.escape) {
      handlers.escape()
      return
    }

    // F2 or Enter - Edit selected node
    if ((key === 'F2' || key === 'Enter') && handlers.editSelectedNode) {
      if (!isInputElement(event.target)) {
        handlers.editSelectedNode()
        event.preventDefault()
      }
      return
    }

    // N - Add new node
    if (key === 'n' && !cmdOrCtrl && handlers.addNode) {
      if (!isInputElement(event.target)) {
        handlers.addNode()
        event.preventDefault()
      }
      return
    }

    // G - Toggle grid
    if (key === 'g' && !cmdOrCtrl && handlers.toggleGrid) {
      if (!isInputElement(event.target)) {
        handlers.toggleGrid()
        event.preventDefault()
      }
      return
    }

    // M - Toggle minimap
    if (key === 'm' && !cmdOrCtrl && handlers.toggleMinimap) {
      if (!isInputElement(event.target)) {
        handlers.toggleMinimap()
        event.preventDefault()
      }
      return
    }

    // Ctrl/Cmd + I - Invert selection
    if (cmdOrCtrl && key === 'i' && handlers.invertSelection) {
      handlers.invertSelection()
      event.preventDefault()
      return
    }
  }

  // Enable/disable keyboard shortcuts
  function enable() {
    isEnabled.value = true
  }

  function disable() {
    isEnabled.value = false
  }

  function toggle() {
    isEnabled.value = !isEnabled.value
  }

  // Lifecycle
  onMounted(() => {
    window.addEventListener('keydown', handleKeydown)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', handleKeydown)
  })

  return {
    isEnabled,
    enable,
    disable,
    toggle,
    selection,
  }
}

/**
 * Create default editor keyboard handlers with common operations
 */
export function createDefaultEditorHandlers(config: {
  getSelectedNodes: () => MindGraphNode[]
  getSelectedEdges: () => MindGraphEdge[]
  getAllNodes: () => MindGraphNode[]
  deleteNodes: (ids: string[]) => void
  deleteEdges: (ids: string[]) => void
  selectAll: () => void
  clearSelection: () => void
  undo?: () => void
  redo?: () => void
  fitView?: () => void
  zoomIn?: () => void
  zoomOut?: () => void
  save?: () => void
}): EditorKeyboardHandlers {
  return {
    deleteSelected: () => {
      const nodeIds = config.getSelectedNodes().map((n) => n.id)
      const edgeIds = config.getSelectedEdges().map((e) => e.id)
      if (nodeIds.length > 0) config.deleteNodes(nodeIds)
      if (edgeIds.length > 0) config.deleteEdges(edgeIds)
    },
    selectAll: config.selectAll,
    clearSelection: config.clearSelection,
    escape: config.clearSelection,
    undo: config.undo,
    redo: config.redo,
    fitView: config.fitView,
    zoomIn: config.zoomIn,
    zoomOut: config.zoomOut,
    save: config.save,
  }
}
