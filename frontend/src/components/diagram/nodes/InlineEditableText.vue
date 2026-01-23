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
 * - IME-style autocomplete (optional, requires enableIME prop)
 */
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'

import { eventBus } from '@/composables/useEventBus'
import { useIMEAutocomplete } from '@/composables/useIMEAutocomplete'

import IMEAutocompleteDropdown from '../IMEAutocompleteDropdown.vue'

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
    /** Whether to truncate text with ellipsis (single line) */
    truncate?: boolean
    /** Enable IME-style autocomplete */
    enableIME?: boolean
    /** Diagram type for IME context */
    diagramType?: string
    /** Main topics for IME context */
    mainTopics?: string[]
    /** Node category for IME context */
    nodeCategory?: string
    /** Existing nodes for IME context (to avoid duplicates) */
    existingNodes?: string[]
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
    truncate: false,
    enableIME: false,
    diagramType: 'mindmap',
    mainTopics: () => [],
    nodeCategory: 'general',
    existingNodes: () => [],
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
const displayRef = ref<HTMLSpanElement | null>(null)
const wrapperRef = ref<HTMLDivElement | null>(null)
const inputWidth = ref<string | undefined>(undefined)

// IME Autocomplete (only initialize if enabled)
const imeAutocomplete = props.enableIME
  ? useIMEAutocomplete({
      diagramType: props.diagramType,
      mainTopics: props.mainTopics,
      nodeCategory: props.nodeCategory,
      existingNodes: props.existingNodes,
    })
  : null

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

// Update IME when text changes during editing
watch(
  () => editText.value,
  (newText) => {
    if (localIsEditing.value && imeAutocomplete) {
      imeAutocomplete.updateInput(newText)
    }
  }
)

// Computed styles
const inputStyle = computed(() => ({
  maxWidth: props.maxWidth,
  textAlign: props.textAlign,
}))

// Computed: Ghost text from IME
const ghostText = computed(() => {
  if (!imeAutocomplete) return ''
  return imeAutocomplete.ghostText.value
})

// Computed: Show IME dropdown
const showIMEDropdown = computed(() => {
  if (!imeAutocomplete) return false
  return localIsEditing.value && imeAutocomplete.isVisible.value
})

/**
 * Start editing mode
 */
function startEditing(): void {
  if (localIsEditing.value) return

  // Measure display text width before switching to edit mode
  if (displayRef.value) {
    const width = displayRef.value.offsetWidth
    inputWidth.value = `${width}px`
  }

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
    // Trigger initial IME fetch if there's text
    if (imeAutocomplete && editText.value.trim()) {
      imeAutocomplete.updateInput(editText.value)
    }
  })
}

/**
 * Save the edited text
 */
function saveEdit(): void {
  if (!localIsEditing.value) return

  // Hide IME dropdown
  if (imeAutocomplete) {
    imeAutocomplete.hide()
  }

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

  // Hide IME dropdown
  if (imeAutocomplete) {
    imeAutocomplete.hide()
  }

  editText.value = originalText.value
  localIsEditing.value = false
  emit('cancel')
}

/**
 * Handle keyboard events
 */
function handleKeydown(event: KeyboardEvent): void {
  // First, let IME handle the event if it's visible
  if (imeAutocomplete && imeAutocomplete.isVisible.value) {
    const handled = imeAutocomplete.handleKeydown(event)
    if (handled) {
      // If Tab was pressed and ghost text was accepted, update editText
      if (event.key === 'Tab' && ghostText.value) {
        editText.value = editText.value + ghostText.value
      }
      // If a number was pressed, get the selected suggestion
      if (event.key >= '1' && event.key <= '5') {
        const index = parseInt(event.key) - 1
        const suggestions = imeAutocomplete.currentSuggestions.value
        if (index < suggestions.length) {
          editText.value = suggestions[index].text
        }
      }
      return
    }
  }

  // Standard keyboard handling
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    event.stopPropagation()
    saveEdit()
  } else if (event.key === 'Escape') {
    event.preventDefault()
    event.stopPropagation()
    // If IME is visible, just hide it; otherwise cancel edit
    if (imeAutocomplete && imeAutocomplete.isVisible.value) {
      imeAutocomplete.hide()
    } else {
      cancelEdit()
    }
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

/**
 * Handle IME suggestion selection
 */
function handleIMESelect(index: number): void {
  if (!imeAutocomplete) return
  const suggestions = imeAutocomplete.currentSuggestions.value
  if (index < suggestions.length) {
    editText.value = suggestions[index].text
    imeAutocomplete.hide()
    // Re-focus input
    nextTick(() => {
      if (inputRef.value) {
        inputRef.value.focus()
      }
    })
  }
}

/**
 * Handle IME next page
 */
function handleIMENextPage(): void {
  if (imeAutocomplete) {
    imeAutocomplete.nextPage()
  }
}

/**
 * Handle IME previous page
 */
function handleIMEPrevPage(): void {
  if (imeAutocomplete) {
    imeAutocomplete.prevPage()
  }
}

/**
 * Handle IME close
 */
function handleIMEClose(): void {
  if (imeAutocomplete) {
    imeAutocomplete.hide()
  }
}

// Cleanup on unmount
onUnmounted(() => {
  if (imeAutocomplete) {
    imeAutocomplete.reset()
  }
})
</script>

<template>
  <div
    class="inline-editable-text"
    @dblclick="handleDoubleClick"
    @mousedown="handleMouseDown"
  >
    <!-- Edit mode: show input with ghost text -->
    <div
      v-if="localIsEditing"
      ref="wrapperRef"
      class="inline-edit-wrapper"
      :style="{ width: inputWidth }"
    >
      <!-- Input container with ghost text overlay -->
      <div class="inline-edit-container">
        <textarea
          v-if="multiline"
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
        <template v-else>
          <input
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
          <!-- Ghost text overlay -->
          <span
            v-if="enableIME && ghostText"
            class="inline-edit-ghost"
            :style="inputStyle"
          >
            <span class="ghost-prefix">{{ editText }}</span>
            <span class="ghost-suffix">{{ ghostText }}</span>
          </span>
        </template>
      </div>

      <!-- IME Autocomplete Dropdown -->
      <IMEAutocompleteDropdown
        v-if="enableIME && showIMEDropdown"
        :suggestions="imeAutocomplete?.currentSuggestions.value || []"
        :is-loading="imeAutocomplete?.isLoading.value || false"
        :current-page="(imeAutocomplete?.state.value.currentPage || 0) + 1"
        :has-next-page="imeAutocomplete?.hasNextPage.value || false"
        :has-prev-page="imeAutocomplete?.hasPrevPage.value || false"
        :error="imeAutocomplete?.error.value || null"
        @select="handleIMESelect"
        @next-page="handleIMENextPage"
        @prev-page="handleIMEPrevPage"
        @close="handleIMEClose"
      />
    </div>

    <!-- Display mode: show text -->
    <span
      v-else
      ref="displayRef"
      class="inline-edit-display"
      :class="[textClass, truncate ? 'truncate-text' : 'whitespace-pre-wrap']"
      :style="{ maxWidth: maxWidth, textAlign: textAlign }"
      :title="truncate ? text : undefined"
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
  width: fit-content;
  max-width: 100%;
  min-height: 1.5em;
  position: relative;
}

.inline-edit-wrapper {
  position: relative;
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
}

.inline-edit-container {
  position: relative;
  display: inline-block;
  width: fit-content;
  max-width: 100%;
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
  min-width: 20px;
  max-width: 100%;
  resize: none;
  position: relative;
  z-index: 2;
  box-sizing: border-box;
}

.inline-edit-input:focus {
  box-shadow: none;
  background: transparent;
}

/* Dark mode support */
:root.dark .inline-edit-input:focus {
  background: transparent;
}

/* Ghost text overlay */
.inline-edit-ghost {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  padding: 2px 4px;
  margin: -2px -4px;
  font: inherit;
  pointer-events: none;
  z-index: 1;
  white-space: nowrap;
  overflow: hidden;
}

.ghost-prefix {
  visibility: hidden;
}

.ghost-suffix {
  color: var(--mg-text-secondary, #909399);
  opacity: 0.7;
}

.dark .ghost-suffix {
  color: var(--mg-text-placeholder, #606266);
}

.inline-edit-display {
  cursor: text;
  user-select: none;
}

/* Truncate mode: single line with ellipsis */
.truncate-text {
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Textarea specific styles */
textarea.inline-edit-input {
  min-height: 2.5em;
  line-height: 1.4;
}
</style>
