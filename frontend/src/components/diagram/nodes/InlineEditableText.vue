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
  (e: 'widthChange', width: number): void
}>()

// Local editing state
const localIsEditing = ref(false)
const editText = ref(props.text)
const originalText = ref(props.text)
const inputRef = ref<HTMLInputElement | HTMLTextAreaElement | null>(null)
const displayRef = ref<HTMLSpanElement | null>(null)
const wrapperRef = ref<HTMLDivElement | null>(null)
const inputWidth = ref<string | undefined>(undefined)
const measureRef = ref<HTMLSpanElement | null>(null) // Hidden span for measuring text width

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
    // Dynamically adjust input width as user types
    if (localIsEditing.value) {
      updateInputWidth()
    }
  }
)

/**
 * Update input width based on current text content
 */
function updateInputWidth(): void {
  if (!measureRef.value || !localIsEditing.value) return

  // Use nextTick to ensure DOM is updated
  nextTick(() => {
    if (!measureRef.value) return

    // Measure the text width
    const textWidth = measureRef.value.offsetWidth || measureRef.value.scrollWidth
    
    // Get maxWidth constraint
    const maxWidthPx = parseInt(props.maxWidth) || 200
    
    // Calculate width: use measured width, but respect maxWidth
    // Add some padding (8px) to prevent text from touching edges
    const calculatedWidth = Math.min(textWidth + 8, maxWidthPx)
    
    // Ensure minimum width
    const finalWidth = Math.max(calculatedWidth, 40)
    
    inputWidth.value = `${finalWidth}px`
    
    // Emit width change so parent node can adapt its width
    emit('widthChange', finalWidth)
  })
}

/**
 * Count Chinese characters in text
 * Chinese characters are in Unicode ranges:
 * - CJK Unified Ideographs: \u4E00-\u9FFF
 * - CJK Extension A: \u3400-\u4DBF
 * - CJK Extension B: \u20000-\u2A6DF
 * - CJK Extension C: \u2A700-\u2B73F
 * - CJK Extension D: \u2B740-\u2B81F
 * - CJK Extension E: \u2B820-\u2CEAF
 * - CJK Compatibility Ideographs: \uF900-\uFAFF
 */
function countChineseCharacters(text: string): number {
  if (!text) return 0
  // Match Chinese characters using Unicode ranges
  const chineseRegex = /[\u4E00-\u9FFF\u3400-\u4DBF\uF900-\uFAFF]/g
  const matches = text.match(chineseRegex)
  return matches ? matches.length : 0
}

// Computed: should prevent wrapping (if less than 5 Chinese characters)
// Check editText when editing, props.text when displaying
const shouldPreventWrap = computed(() => {
  const textToCheck = localIsEditing.value ? editText.value : props.text
  const chineseCount = countChineseCharacters(textToCheck)
  return chineseCount > 0 && chineseCount < 5
})

// Computed styles
const inputStyle = computed(() => ({
  maxWidth: props.maxWidth,
  textAlign: props.textAlign,
}))

// Computed wrapper style for right-aligned text
const wrapperStyle = computed(() => {
  const baseStyle: Record<string, string> = {
    width: inputWidth.value || 'auto',
  }
  // For right-aligned text, ensure wrapper aligns to the right
  if (props.textAlign === 'right') {
    baseStyle.marginLeft = 'auto'
  }
  return baseStyle
})

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

  // Measure width before switching to edit mode
  // For right-aligned text, use parent container width or maxWidth to avoid empty space
  // For other alignments, use display text width
  if (displayRef.value) {
    const textWidth = displayRef.value.offsetWidth
    const parentElement = displayRef.value.parentElement
    
    if (props.textAlign === 'right') {
      // For right-aligned text, use parent container width if available, otherwise maxWidth
      // This prevents empty space on the left and allows text to expand properly
      const maxWidthPx = parseInt(props.maxWidth) || 180
      let calculatedWidth = maxWidthPx
      
      if (parentElement) {
        // Get parent container width (accounting for padding)
        const parentWidth = parentElement.offsetWidth || parentElement.clientWidth
        // Use parent width if it's reasonable, but cap at maxWidth
        // Ensure it's at least text width to avoid shrinking
        calculatedWidth = Math.max(textWidth, Math.min(parentWidth, maxWidthPx))
      } else {
        // Fallback: use maxWidth, but ensure it's at least text width
        calculatedWidth = Math.max(maxWidthPx, textWidth)
      }
      
      inputWidth.value = `${calculatedWidth}px`
    } else {
      // For left/center aligned, use measured text width
      inputWidth.value = `${textWidth}px`
    }
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
    // Initial width update
    updateInputWidth()
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

  // Emit event for workshop tracking (editing stopped)
  eventBus.emit('node_editor:closed', { nodeId: props.nodeId })

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
  
  // Emit event for workshop tracking (editing stopped)
  eventBus.emit('node_editor:closed', { nodeId: props.nodeId })
  
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
    <!-- Hidden span for measuring text width -->
    <span
      v-if="localIsEditing"
      ref="measureRef"
      class="inline-edit-measure"
      :style="{
        fontSize: 'inherit',
        fontFamily: 'inherit',
        fontWeight: 'inherit',
        fontStyle: 'inherit',
        letterSpacing: 'inherit',
        visibility: 'hidden',
        position: 'absolute',
        whiteSpace: 'pre',
        top: '-9999px',
        left: '-9999px',
        padding: '2px 4px',
      }"
    >
      {{ editText || 'M' }}
    </span>

    <!-- Edit mode: show input with ghost text -->
    <div
      v-if="localIsEditing"
      ref="wrapperRef"
      class="inline-edit-wrapper"
      :style="wrapperStyle"
    >
      <!-- Input container with ghost text overlay -->
      <div class="inline-edit-container">
        <textarea
          v-if="multiline"
          ref="inputRef"
          v-model="editText"
          class="inline-edit-input"
          :class="{ 'whitespace-nowrap': shouldPreventWrap }"
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
            :class="{ 'whitespace-nowrap': shouldPreventWrap }"
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
      :class="[
        textClass,
        truncate
          ? 'truncate-text'
          : shouldPreventWrap
            ? 'whitespace-nowrap'
            : 'whitespace-pre-wrap',
      ]"
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
  overflow: visible; /* Allow text to be visible while typing */
  min-width: fit-content; /* Allow wrapper to expand with content */
}

.inline-edit-container {
  position: relative;
  display: inline-block;
  width: 100%; /* Use full wrapper width */
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
  max-width: 100%; /* Respect wrapper width, which respects maxWidth prop */
  resize: none;
  position: relative;
  z-index: 2;
  box-sizing: border-box;
  overflow: visible; /* Allow text to be visible */
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
