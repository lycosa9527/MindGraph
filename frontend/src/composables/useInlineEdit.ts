/**
 * useInlineEdit - Composable for inline text editing on nodes
 *
 * Provides reactive state and handlers for inline text editing:
 * - Double-click to enter edit mode
 * - Enter to save, Escape to cancel
 * - Click outside to save
 * - Auto-select text on edit start
 */
import { nextTick, ref, watch } from 'vue'

import { eventBus } from './useEventBus'

export interface InlineEditOptions {
  /** Initial text value */
  initialText?: string
  /** Callback when text is saved */
  onSave?: (newText: string) => void
  /** Callback when editing is cancelled */
  onCancel?: () => void
  /** Node ID for tracking which node is being edited */
  nodeId?: string
  /** Minimum text length required */
  minLength?: number
  /** Maximum text length allowed */
  maxLength?: number
}

export function useInlineEdit(options: InlineEditOptions = {}) {
  const {
    initialText = '',
    onSave,
    onCancel,
    nodeId = '',
    minLength = 1,
    maxLength = 200,
  } = options

  // State
  const isEditing = ref(false)
  const editText = ref(initialText)
  const originalText = ref(initialText)
  const inputRef = ref<HTMLInputElement | HTMLTextAreaElement | null>(null)

  // Watch for external text changes
  watch(
    () => initialText,
    (newText) => {
      if (!isEditing.value) {
        editText.value = newText
        originalText.value = newText
      }
    }
  )

  /**
   * Start editing mode
   */
  function startEditing(): void {
    if (isEditing.value) return

    isEditing.value = true
    originalText.value = editText.value

    // Emit event for tracking
    if (nodeId) {
      eventBus.emit('node_editor:opening', { nodeId })
    }

    // Focus and select text after DOM update
    nextTick(() => {
      if (inputRef.value) {
        inputRef.value.focus()
        inputRef.value.select()
      }
    })
  }

  /**
   * Save the edited text
   */
  function saveEdit(): void {
    if (!isEditing.value) return

    const trimmedText = editText.value.trim()

    // Validate text length
    if (trimmedText.length < minLength) {
      // Revert to original if too short
      editText.value = originalText.value
      cancelEdit()
      return
    }

    // Truncate if too long
    const finalText = trimmedText.slice(0, maxLength)
    editText.value = finalText

    isEditing.value = false

    // Only call onSave if text actually changed
    if (finalText !== originalText.value && onSave) {
      onSave(finalText)
    }
  }

  /**
   * Cancel editing and revert to original text
   */
  function cancelEdit(): void {
    if (!isEditing.value) return

    editText.value = originalText.value
    isEditing.value = false

    if (onCancel) {
      onCancel()
    }
  }

  /**
   * Handle keyboard events in the input
   */
  function handleKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      event.stopPropagation()
      saveEdit()
    } else if (event.key === 'Escape') {
      event.preventDefault()
      event.stopPropagation()
      cancelEdit()
    }
  }

  /**
   * Handle blur event (click outside)
   */
  function handleBlur(): void {
    // Small delay to allow click events to fire first
    setTimeout(() => {
      if (isEditing.value) {
        saveEdit()
      }
    }, 100)
  }

  /**
   * Handle double-click to start editing
   */
  function handleDoubleClick(event: MouseEvent): void {
    event.preventDefault()
    event.stopPropagation()
    startEditing()
  }

  /**
   * Set the input reference
   */
  function setInputRef(el: HTMLInputElement | HTMLTextAreaElement | null): void {
    inputRef.value = el
  }

  return {
    // State
    isEditing,
    editText,
    originalText,
    inputRef,

    // Methods
    startEditing,
    saveEdit,
    cancelEdit,
    handleKeydown,
    handleBlur,
    handleDoubleClick,
    setInputRef,
  }
}
