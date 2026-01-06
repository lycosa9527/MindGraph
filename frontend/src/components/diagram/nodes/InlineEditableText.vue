<script setup lang="ts">
/**
 * InlineEditableText - Inline text editing component for diagram nodes
 *
 * Features:
 * - Double-click to enter edit mode
 * - Text is highlighted/selected on edit start
 * - Enter to save, Escape to cancel
 * - Click outside to save
 * - Seamless transition between display and edit modes
 */
import { computed, nextTick, ref, watch } from 'vue'

import { eventBus } from '@/composables/useEventBus'

const props = withDefaults(
  defineProps<{
    /** Current text to display/edit */
    text: string
    /** Node ID for event tracking */
    nodeId: string
    /** Whether editing is currently active (controlled from parent) */
    isEditing?: boolean
    /** Maximum width for the text display */
    maxWidth?: string
    /** Text alignment */
    textAlign?: 'left' | 'center' | 'right'
    /** Additional CSS classes for the text span */
    textClass?: string
    /** Whether to use textarea (for multiline) or input */
    multiline?: boolean
    /** Placeholder text when empty */
    placeholder?: string
    /** Minimum length required */
    minLength?: number
    /** Maximum length allowed */
    maxLength?: number
  }>(),
  {
    isEditing: false,
    maxWidth: '150px',
    textAlign: 'center',
    textClass: '',
    multiline: false,
    placeholder: 'Enter text...',
    minLength: 1,
    maxLength: 200,
  }
)

const emit = defineEmits<{
  (e: 'save', newText: string): void
  (e: 'cancel'): void
  (e: 'editStart'): void
}>()

// Local editing state
const localIsEditing = ref(false)
const editText = ref(props.text)
const originalText = ref(props.text)
const inputRef = ref<HTMLInputElement | HTMLTextAreaElement | null>(null)

// Sync with parent's isEditing prop
watch(
  () => props.isEditing,
  (newVal) => {
    if (newVal && !localIsEditing.value) {
      startEditing()
    } else if (!newVal && localIsEditing.value) {
      localIsEditing.value = false
    }
  }
)

// Update text when prop changes (and not editing)
watch(
  () => props.text,
  (newText) => {
    if (!localIsEditing.value) {
      editText.value = newText
      originalText.value = newText
    }
  }
)

// Computed styles
const inputStyle = computed(() => ({
  maxWidth: props.maxWidth,
  textAlign: props.textAlign,
}))

/**
 * Start editing mode
 */
function startEditing(): void {
  if (localIsEditing.value) return

  localIsEditing.value = true
  originalText.value = editText.value

  // Emit event for tracking
  eventBus.emit('node_editor:opening', { nodeId: props.nodeId })
  emit('editStart')

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
  if (!localIsEditing.value) return

  const trimmedText = editText.value.trim()

  // Validate text length - revert if invalid
  if (trimmedText.length < props.minLength) {
    editText.value = originalText.value
    localIsEditing.value = false
    emit('cancel')
    return
  }

  // Truncate if too long
  const finalText = trimmedText.slice(0, props.maxLength)
  editText.value = finalText
  localIsEditing.value = false

  // Only emit save if text actually changed
  if (finalText !== originalText.value) {
    emit('save', finalText)
  }
}

/**
 * Cancel editing and revert
 */
function cancelEdit(): void {
  if (!localIsEditing.value) return

  editText.value = originalText.value
  localIsEditing.value = false
  emit('cancel')
}

/**
 * Handle keyboard events
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
 * Handle blur (click outside)
 */
function handleBlur(): void {
  // Small delay to allow click events to process
  setTimeout(() => {
    if (localIsEditing.value) {
      saveEdit()
    }
  }, 150)
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
 * Prevent node dragging when clicking on input
 */
function handleMouseDown(event: MouseEvent): void {
  if (localIsEditing.value) {
    event.stopPropagation()
  }
}
</script>

<template>
  <div
    class="inline-editable-text"
    @dblclick="handleDoubleClick"
    @mousedown="handleMouseDown"
  >
    <!-- Edit mode: show input -->
    <textarea
      v-if="localIsEditing && multiline"
      ref="inputRef"
      v-model="editText"
      class="inline-edit-input"
      :style="inputStyle"
      :placeholder="placeholder"
      :maxlength="maxLength"
      rows="2"
      @keydown="handleKeydown"
      @blur="handleBlur"
      @mousedown.stop
      @click.stop
    />
    <input
      v-else-if="localIsEditing"
      ref="inputRef"
      v-model="editText"
      type="text"
      class="inline-edit-input"
      :style="inputStyle"
      :placeholder="placeholder"
      :maxlength="maxLength"
      @keydown="handleKeydown"
      @blur="handleBlur"
      @mousedown.stop
      @click.stop
    />

    <!-- Display mode: show text -->
    <span
      v-else
      class="inline-edit-display whitespace-pre-wrap"
      :class="textClass"
      :style="{ maxWidth: maxWidth, textAlign: textAlign }"
    >
      {{ text || placeholder }}
    </span>
  </div>
</template>

<style scoped>
.inline-editable-text {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-height: 1.5em;
}

.inline-edit-input {
  background: transparent;
  border: none;
  outline: none;
  font: inherit;
  color: inherit;
  padding: 2px 4px;
  margin: -2px -4px;
  border-radius: 4px;
  box-shadow: none;
  width: 100%;
  resize: none;
}

.inline-edit-input:focus {
  box-shadow: none;
  background: transparent;
}

/* Dark mode support */
:root.dark .inline-edit-input:focus {
  background: transparent;
}

.inline-edit-display {
  cursor: text;
  user-select: none;
}

/* Textarea specific styles */
textarea.inline-edit-input {
  min-height: 2.5em;
  line-height: 1.4;
}
</style>
