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
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'

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
    /** Whether to truncate text with ellipsis (single line) */
    truncate?: boolean
    /** Force single line (no wrap); when true, display uses whitespace-nowrap and no truncate. Used by circle/bubble maps. */
    noWrap?: boolean
    /** When true, root takes width 100% and display text is centered in full width (for circle/bubble topic). */
    fullWidth?: boolean
    /** When true, display span is content-sized and centered by parent (reduces font-metric shift in circle topic). */
    centerBlockInCircle?: boolean
    /** When true, disable editing (e.g. learning sheet knocked-out nodes) */
    readonly?: boolean
    /** Text decoration (underline, line-through). Must be passed explicitly - CSS does not inherit to form controls. */
    textDecoration?: 'none' | 'underline' | 'line-through' | 'underline line-through'
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
    noWrap: false,
    fullWidth: false,
    centerBlockInCircle: false,
    readonly: false,
    textDecoration: 'none',
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

// Listen for edit request from context menu (right-click → 编辑)
// Reuse same handler as double-click so both paths share identical behavior.
// Defer so the menu closes and DOM settles before focus/select (ensures selection animation shows).
const CONTEXT_MENU_EDIT_DELAY_MS = 50

function handleEditRequested(payload: { nodeId?: string }): void {
  if (props.readonly) return
  if (payload?.nodeId === props.nodeId && !localIsEditing.value) {
    const noopEvent = { preventDefault: () => {}, stopPropagation: () => {} } as MouseEvent
    setTimeout(() => handleDoubleClick(noopEvent), CONTEXT_MENU_EDIT_DELAY_MS)
  }
}

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

// Dynamically adjust input width as user types
watch(
  () => editText.value,
  () => {
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

// Computed styles - textDecoration must be explicit (CSS does not inherit to input/textarea)
const inputStyle = computed(() => ({
  maxWidth: props.maxWidth,
  textAlign: props.textAlign,
  textDecoration: props.textDecoration || 'none',
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

/**
 * Start editing mode
 */
function startEditing(): void {
  if (localIsEditing.value || props.readonly) return

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
    updateInputWidth()
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
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    event.stopPropagation()
    saveEdit()
  } else if (event.key === 'Escape') {
    event.preventDefault()
    event.stopPropagation()
    cancelEdit()
  } else if (event.key === 'Tab') {
    event.preventDefault()
    event.stopPropagation()
    eventBus.emit('node_editor:tab_pressed', { nodeId: props.nodeId })
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
  if (props.readonly) return
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

// Subscribe to edit request from context menu
const unsubEditRequested = eventBus.on('node:edit_requested', handleEditRequested)

// When user selects an inline recommendation (number key), apply text and exit edit mode
// so we don't overwrite with stale editText on blur
function handleRecommendationApplied(payload: { nodeId?: string; text?: string }): void {
  if (payload?.nodeId !== props.nodeId || !payload?.text) return
  if (!localIsEditing.value) return
  editText.value = payload.text
  originalText.value = payload.text
  localIsEditing.value = false
  eventBus.emit('node_editor:closed', { nodeId: props.nodeId })
}
const unsubRecommendationApplied = eventBus.on(
  'inline_recommendation:applied',
  handleRecommendationApplied
)

// Cleanup on unmount
onUnmounted(() => {
  unsubEditRequested()
  unsubRecommendationApplied()
})
</script>

<template>
  <div
    class="inline-editable-text"
    :class="{ 'inline-editable-text--full-width': fullWidth }"
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
          :class="{ 'whitespace-nowrap': noWrap || shouldPreventWrap }"
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
            :class="{ 'whitespace-nowrap': noWrap || shouldPreventWrap }"
            :style="inputStyle"
            :placeholder="placeholder"
            :maxlength="maxLength"
            @keydown="handleKeydown"
            @blur="handleBlur"
            @mousedown.stop
            @click.stop
          />
        </template>
      </div>
    </div>

    <!-- Display mode: show text -->
    <span
      v-else
      ref="displayRef"
      class="inline-edit-display"
      :class="[
        textClass,
        fullWidth && textAlign === 'center' ? 'inline-edit-display--center-block' : '',
        centerBlockInCircle ? 'inline-edit-display--center-in-circle' : '',
        noWrap
          ? 'whitespace-nowrap'
          : truncate
            ? 'truncate-text'
            : shouldPreventWrap
              ? 'whitespace-nowrap'
              : 'whitespace-pre-wrap',
      ]"
      :style="{
        maxWidth: maxWidth,
        textAlign: textAlign,
        textDecoration: textDecoration || 'none',
      }"
      :title="truncate ? text : undefined"
    >
      {{ text }}
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

.inline-editable-text--full-width {
  width: 100%;
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
  text-decoration: inherit;
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
  /* Override parent node's select-none so text can be selected when editing */
  user-select: text;
}

.inline-edit-input::selection {
  background: var(--mg-primary, #3b82f6);
  color: white;
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
  text-decoration: inherit;
}

/* Center text in full width (circle/bubble topic) so text is visually centered in the circle */
.inline-edit-display--center-block {
  display: block;
  width: 100%;
  box-sizing: border-box;
}

/* Circle/bubble topic: block width = content width, parent flex centers it; no asymmetric padding */
.inline-edit-display--center-in-circle {
  display: block;
  width: fit-content;
  max-width: 100%;
  margin: 0 auto;
  padding-left: 0;
  padding-right: 0;
  box-sizing: border-box;
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
