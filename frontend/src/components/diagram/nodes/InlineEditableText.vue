<script setup lang="ts">
/**
 * InlineEditableText - Inline text editing component for diagram nodes
 *
 * Features:
 * - Double-click to enter edit mode
 * - Text is highlighted/selected on edit start
 * - Enter to save, Escape to cancel
 * - Tab: emits node_editor:tab_pressed (draftText); optional syncBaselineOnTab for concept map focus
 * - Click outside to save
 * - Seamless transition between display and edit modes
 */
import { computed, inject, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'

import { useLanguage, useNotifications } from '@/composables'
import { joinLabelAndMathSnippet } from '@/composables/core/markdownKatexDelimiter'
import { eventBus } from '@/composables/core/useEventBus'
import {
  isLearningSheetCustomPickActive,
} from '@/composables/mindMap/useLearningSheetCustomMode'
import { isMindMapDiagramType } from '@/composables/mindMap/mindMapArrowNavigation'
import { useDiagramNodeMarkdownDisplay } from '@/composables/diagram/useDiagramNodeMarkdownDisplay'
import { useDiagramStore } from '@/stores'
import {
  isNodeDisplayPlaceholderLabel,
  shouldReplaceLabelWithMathInsert,
  stripConceptMapFocusQuestionPrefix,
} from '@/stores/diagram/diagramDefaultLabels'
import { shouldPreferSingleLineNoWrap } from '@/stores/specLoader/textMeasurement'
import {
  isWhitespaceOnlyNodeText,
  resolveInlineNodeTextForSave,
} from '@/utils/nodeEditableText'

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
    /**
     * When true, Tab updates the saved baseline to the current draft without closing edit mode
     * (used for concept map focus question: Tab commits draft then triggers validation in CanvasPage).
     */
    syncBaselineOnTab?: boolean
    /** When true, disable editing (e.g. learning sheet knocked-out nodes) */
    readonly?: boolean
    /** Text decoration (underline, line-through). Must be passed explicitly - CSS does not inherit to form controls. */
    textDecoration?: 'none' | 'underline' | 'line-through' | 'underline line-through'
    /** When text equals prefix+suffix, display suffix with muted color (e.g. concept map focus placeholder) */
    mutedTailSplit?: { prefix: string; suffix: string } | null
    /**
     * Concept map focus-question: fixed i18n prefix, editable body (suffix is placeholder for empty).
     * When set, only the body is edited; the saved value is prefix + body.
     */
    focusQuestionEditableSplit?: { prefix: string; body: string; defaultSuffix: string } | null
    /**
     * When true, display mode renders Markdown + KaTeX (sanitized). Ignored when mutedTailSplit
     * is active or truncate is true. noWrap does not disable rendering so inline math works in
     * circle/bubble-style nodes.
     */
    renderMarkdown?: boolean
    /**
     * When true, use normal CSS wrapping at maxWidth instead of the
     * JS-based shouldPreferSingleLineNoWrap heuristic.
     */
    autoWrap?: boolean
  }>(),
  {
    isEditing: false,
    maxWidth: '150px',
    textAlign: 'center',
    textClass: '',
    multiline: false,
    placeholder: undefined,
    minLength: 1,
    maxLength: 200,
    truncate: false,
    noWrap: false,
    fullWidth: false,
    centerBlockInCircle: false,
    syncBaselineOnTab: false,
    readonly: false,
    textDecoration: 'none',
    mutedTailSplit: null,
    focusQuestionEditableSplit: null,
    renderMarkdown: false,
    autoWrap: false,
  }
)

const emit = defineEmits<{
  (e: 'save', newText: string): void
  (e: 'cancel'): void
  (e: 'close'): void
  (e: 'editStart'): void
  (e: 'widthChange', width: number): void
}>()

const collabCanvas = inject<{ isNodeLockedByOther?: (nodeId: string) => boolean } | undefined>(
  'collabCanvas',
  undefined
)
const notifyCollab = useNotifications()
const { t } = useLanguage()
const diagramStore = useDiagramStore()

const resolvedPlaceholder = computed(() => {
  if (props.placeholder != null && props.placeholder !== '') {
    return props.placeholder
  }
  return String(t('diagram.editable.placeholder'))
})

/** Stable id/name for autofill and label association (Lighthouse / a11y). */
const fieldHtmlId = computed(() => `diagram-inline-edit-${props.nodeId}`)
const fieldAriaLabel = computed(() => resolvedPlaceholder.value)

// Local editing state
const localIsEditing = ref(false)
const rootRef = ref<HTMLElement | null>(null)
const editText = ref(props.text)
const originalText = ref(props.text)
/** Concept map focus-question: editable segment only; full snapshot at edit start is originalComposed */
const editBody = ref('')
const originalComposed = ref('')
const inputRef = ref<HTMLInputElement | HTMLTextAreaElement | null>(null)
const displayRef = ref<HTMLElement | null>(null)
const wrapperRef = ref<HTMLDivElement | null>(null)
const inputWidth = ref<string | undefined>(undefined)
/** When autoWrap: lock edit box to display size so wrapped labels don't expand to single-line width. */
const editLockedWidthPx = ref<number | null>(null)
const editLockedMinHeightPx = ref<number | null>(null)
/** autoWrap: textarea only when display already wraps; single-line labels use input. */
const editUsesMultilineControl = ref(false)
/** When user inserts a manual line break on a single-line input control. */
const forceMultilineEdit = ref(false)
const measureRef = ref<HTMLSpanElement | null>(null) // Hidden span for measuring text width

/** Matches computed font on display/edit for measureTextWidth (multiscript stack). */
const displayFontSizePx = ref(14)
const displayFontWeight = ref('400')

function syncFontMetrics(): void {
  const el = displayRef.value || measureRef.value || inputRef.value
  if (!el) return
  const cs = getComputedStyle(el)
  displayFontSizePx.value = parseFloat(cs.fontSize) || 14
  displayFontWeight.value = cs.fontWeight || '400'
}

// Sync with parent's isEditing prop
watch(
  () => props.isEditing,
  (newVal) => {
    if (newVal && !localIsEditing.value) {
      startEditing()
    } else if (!newVal && localIsEditing.value) {
      localIsEditing.value = false
      clearEditLock()
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
  () => [props.text, props.focusQuestionEditableSplit] as const,
  () => {
    if (localIsEditing.value) return
    editText.value = props.text
    originalText.value = props.text
    if (props.focusQuestionEditableSplit) {
      editBody.value = props.focusQuestionEditableSplit.body
    }
  },
  { deep: true, immediate: true }
)

// Dynamically adjust input width as user types
watch(
  () => [editText.value, editBody.value] as const,
  () => {
    if (localIsEditing.value) {
      updateInputWidth()
    }
  }
)

function clearEditLock(): void {
  editLockedWidthPx.value = null
  editLockedMinHeightPx.value = null
  editUsesMultilineControl.value = false
  forceMultilineEdit.value = false
}

function usesMultilineEditControl(): boolean {
  return (
    props.multiline ||
    (props.autoWrap && editUsesMultilineControl.value) ||
    forceMultilineEdit.value
  )
}

function ensureMultilineEditControl(): void {
  if (props.focusQuestionEditableSplit) return
  if (props.multiline) return

  if (props.autoWrap && !editUsesMultilineControl.value) {
    editUsesMultilineControl.value = true
    const baseH =
      editLockedMinHeightPx.value ??
      inputRef.value?.offsetHeight ??
      displayRef.value?.offsetHeight ??
      20
    editLockedMinHeightPx.value = Math.max(baseH, 28)
  } else if (!props.autoWrap) {
    forceMultilineEdit.value = true
  }
}

function isDisplaySingleLine(el: HTMLElement): boolean {
  const cs = getComputedStyle(el)
  let lineHeight = parseFloat(cs.lineHeight)
  if (!Number.isFinite(lineHeight) || lineHeight <= 0) {
    lineHeight = (parseFloat(cs.fontSize) || 14) * 1.4
  }
  return el.offsetHeight <= lineHeight * 1.5
}

/**
 * Update input width based on current text content
 */
function updateInputWidth(): void {
  if (!localIsEditing.value) return

  // autoWrap display uses normal pre-wrap at maxWidth (no balanced line lengths).
  // Keep the edit box at the display width — do not re-measure as a single line.
  if (props.autoWrap) {
    if (editLockedWidthPx.value != null) {
      inputWidth.value = `${editLockedWidthPx.value}px`
    }
    return
  }

  if (!measureRef.value) return

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

watch(
  [() => props.text, () => editText.value, localIsEditing],
  () => {
    nextTick(syncFontMetrics)
  },
  { flush: 'post' }
)

onMounted(() => {
  nextTick(() => {
    syncFontMetrics()
    if (
      diagramStore.mindMapPendingEditNodeId === props.nodeId &&
      !props.readonly &&
      !localIsEditing.value
    ) {
      startEditing()
      diagramStore.mindMapPendingEditNodeId = null
    }
    requestAnimationFrame(() => {
      syncFontMetrics()
    })
  })
})

const isFocusQuestionSplitMode = computed(() => props.focusQuestionEditableSplit != null)

const shouldPreventWrap = computed(() => {
  if (props.noWrap || props.truncate) return false
  if (props.autoWrap) return false
  const split = props.focusQuestionEditableSplit
  const textToCheck = localIsEditing.value
    ? isFocusQuestionSplitMode.value
      ? editBody.value
      : editText.value
    : isFocusQuestionSplitMode.value && split
      ? split.prefix + split.body
      : props.text
  const maxWidthPx = parseInt(props.maxWidth, 10) || 200
  return shouldPreferSingleLineNoWrap(textToCheck || ' ', maxWidthPx, displayFontSizePx.value, {
    fontWeight: String(displayFontWeight.value),
    horizontalPaddingPx: 8,
  })
})

const stretchesToFillWidth = computed(() => props.fullWidth)

const rootAlignClass = computed(() => {
  if (props.textAlign === 'left') return 'inline-editable-text--align-left'
  if (props.textAlign === 'right') return 'inline-editable-text--align-right'
  return 'inline-editable-text--align-center'
})

const displayDecorationStyle = computed(() => ({
  textDecoration: props.textDecoration || 'none',
}))

const isDisplayPlaceholder = computed(
  () =>
    isWhitespaceOnlyNodeText(props.text) ||
    isNodeDisplayPlaceholderLabel(diagramStore.type, props.nodeId, props.text)
)

const showMutedTailSplit = computed(() => {
  if (isFocusQuestionSplitMode.value) return false
  const s = props.mutedTailSplit
  if (!s) return false
  return props.text === s.prefix + s.suffix
})

const markdownDisplayEnabled = computed(
  () =>
    props.renderMarkdown === true &&
    !isFocusQuestionSplitMode.value &&
    !showMutedTailSplit.value &&
    !props.truncate
)

const { richHtml: displayMarkdownHtml, needsRichMarkdown } = useDiagramNodeMarkdownDisplay(
  computed(() => props.text),
  markdownDisplayEnabled
)

// Computed styles - textDecoration must be explicit (CSS does not inherit to input/textarea)
const inputStyle = computed(() => ({
  maxWidth: props.maxWidth,
  width: stretchesToFillWidth.value ? '100%' : undefined,
  textAlign: props.textAlign,
  textDecoration: props.textDecoration || 'none',
  ...(props.autoWrap && editLockedMinHeightPx.value != null
    ? { minHeight: `${editLockedMinHeightPx.value}px` }
    : {}),
}))

// Computed wrapper style for right-aligned text
const wrapperStyle = computed(() => {
  const baseStyle: Record<string, string> = {
    width: stretchesToFillWidth.value ? '100%' : inputWidth.value || 'auto',
  }
  if (props.textAlign === 'right') {
    baseStyle.marginLeft = 'auto'
  } else if (props.textAlign === 'left') {
    baseStyle.marginRight = 'auto'
  }
  return baseStyle
})

/**
 * Start editing mode
 */
function startEditing(): void {
  if (localIsEditing.value || props.readonly) return

  if (collabCanvas?.isNodeLockedByOther?.(props.nodeId)) {
    notifyCollab.warning(t('collab.nodeLocked'))
    return
  }

  // Measure width before switching to edit mode
  if (displayRef.value) {
    const textWidth = Math.max(displayRef.value.offsetWidth, displayRef.value.scrollWidth)
    const textHeight = displayRef.value.offsetHeight
    if (props.autoWrap) {
      editUsesMultilineControl.value = !isDisplaySingleLine(displayRef.value)
      editLockedWidthPx.value = Math.max(textWidth, 40)
      editLockedMinHeightPx.value = editUsesMultilineControl.value
        ? Math.max(textHeight, 20)
        : null
      inputWidth.value = `${editLockedWidthPx.value}px`
    } else if (props.textAlign === 'right') {
      const maxWidthPx = parseInt(props.maxWidth, 10) || 180
      inputWidth.value = `${Math.max(textWidth, maxWidthPx)}px`
    } else {
      inputWidth.value = `${textWidth}px`
    }
  } else if (props.autoWrap) {
    editLockedWidthPx.value = null
    editLockedMinHeightPx.value = null
  }

  if (props.focusQuestionEditableSplit) {
    editBody.value = props.focusQuestionEditableSplit.body
    originalComposed.value = props.text
  } else {
    originalText.value = editText.value
  }

  localIsEditing.value = true

  if (diagramStore.mindMapPendingEditNodeId === props.nodeId) {
    diagramStore.mindMapPendingEditNodeId = null
  }

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
    syncFontMetrics()
  })
}

/**
 * Save the edited text
 */
function saveEdit(): void {
  if (!localIsEditing.value) return

  if (props.focusQuestionEditableSplit) {
    const { prefix, defaultSuffix } = props.focusQuestionEditableSplit
    const trimmed = editBody.value.trim()
    const bodyPart = trimmed === '' ? defaultSuffix : trimmed
    let finalText = prefix + bodyPart
    if (finalText.length < props.minLength) {
      editBody.value = stripConceptMapFocusQuestionPrefix(originalComposed.value)
      localIsEditing.value = false
      clearEditLock()
      eventBus.emit('node_editor:closed', { nodeId: props.nodeId })
      emit('cancel')
      return
    }
    if (finalText.length > props.maxLength) {
      finalText = finalText.slice(0, props.maxLength)
    }
    localIsEditing.value = false
    clearEditLock()
    eventBus.emit('node_editor:closed', { nodeId: props.nodeId })
    if (finalText !== originalComposed.value) {
      emit('save', finalText)
    } else {
      emit('close')
    }
    return
  }

  const resolved = resolveInlineNodeTextForSave(
    editText.value,
    props.minLength,
    props.maxLength
  )

  // Validate text length - revert if invalid
  if (resolved === null) {
    editText.value = originalText.value
    localIsEditing.value = false
    clearEditLock()
    eventBus.emit('node_editor:closed', { nodeId: props.nodeId })
    emit('cancel')
    return
  }

  const finalText = resolved
  editText.value = finalText
  localIsEditing.value = false
  clearEditLock()

  // Emit event for workshop tracking (editing stopped)
  eventBus.emit('node_editor:closed', { nodeId: props.nodeId })

  // Only emit save if text actually changed
  if (finalText !== originalText.value) {
    emit('save', finalText)
  } else {
    emit('close')
  }
}

/**
 * Cancel editing and revert
 */
function cancelEdit(): void {
  if (!localIsEditing.value) return

  if (props.focusQuestionEditableSplit) {
    editBody.value = stripConceptMapFocusQuestionPrefix(originalComposed.value)
  } else {
    editText.value = originalText.value
  }
  localIsEditing.value = false
  clearEditLock()

  // Emit event for workshop tracking (editing stopped)
  eventBus.emit('node_editor:closed', { nodeId: props.nodeId })

  emit('cancel')
}

function isMindMapInlineEditContext(): boolean {
  return isMindMapDiagramType(diagramStore.type)
}

/**
 * Handle keyboard events
 */
function handleKeydown(event: KeyboardEvent): void {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    event.stopPropagation()
    if (isMindMapInlineEditContext() && props.nodeId !== 'topic') {
      saveEdit()
      nextTick(() => {
        eventBus.emit('diagram:add_sibling_requested', {})
      })
      return
    }
    saveEdit()
  } else if (event.key === 'Escape') {
    event.preventDefault()
    event.stopPropagation()
    cancelEdit()
  } else if (
    event.key === 'Enter' &&
    event.shiftKey &&
    (event.ctrlKey || event.metaKey)
  ) {
    event.preventDefault()
    event.stopPropagation()
    insertLineBreakAtCaret()
  } else if (event.key === 'Tab') {
    event.preventDefault()
    event.stopPropagation()
    if (isMindMapInlineEditContext()) {
      saveEdit()
      nextTick(() => {
        eventBus.emit('diagram:add_child_requested', {})
      })
      return
    }
    if (props.focusQuestionEditableSplit) {
      const s = props.focusQuestionEditableSplit
      const t = editBody.value.trim()
      const bodyPart = t === '' ? s.defaultSuffix : t
      const draft = s.prefix + bodyPart
      eventBus.emit('node_editor:tab_pressed', {
        nodeId: props.nodeId,
        draftText: draft,
      })
      if (props.syncBaselineOnTab) {
        originalComposed.value = draft
      }
    } else {
      eventBus.emit('node_editor:tab_pressed', {
        nodeId: props.nodeId,
        draftText: editText.value,
      })
      if (props.syncBaselineOnTab) {
        originalText.value = editText.value
      }
    }
  }
}

/**
 * Handle blur (click outside) — pointerdown on the document also commits (see below).
 */
function handleBlur(): void {
  setTimeout(() => {
    if (localIsEditing.value) {
      saveEdit()
    }
  }, 150)
}

function isEventInsideEditor(event: Event): boolean {
  const root = rootRef.value
  const target = event.target
  if (!root || !(target instanceof Node)) return false
  return root.contains(target)
}

function commitEditOnOutsidePointer(event?: Event): void {
  if (!localIsEditing.value) return
  if (event != null && isEventInsideEditor(event)) return
  saveEdit()
}

function syncDocumentOutsideEditListeners(editing: boolean): void {
  if (editing) {
    document.addEventListener('pointerdown', commitEditOnOutsidePointer, true)
    eventBus.on('canvas:pane_clicked', commitEditOnOutsidePointer)
  } else {
    document.removeEventListener('pointerdown', commitEditOnOutsidePointer, true)
    eventBus.off('canvas:pane_clicked', commitEditOnOutsidePointer)
  }
}

watch(localIsEditing, (editing) => {
  syncDocumentOutsideEditListeners(editing)
})

/**
 * Handle double-click to start editing
 */
function handleDoubleClick(event: MouseEvent): void {
  if (isLearningSheetCustomPickActive()) return
  if (props.readonly) return
  event.preventDefault()
  event.stopPropagation()
  startEditing()
}

let lastTapTime = 0
let wasMultiTouch = false
const DOUBLE_TAP_THRESHOLD = 350

function handleTouchStart(event: TouchEvent): void {
  if (event.touches.length > 1) {
    wasMultiTouch = true
  }
}

function handleTouchEnd(event: TouchEvent): void {
  if (props.readonly || localIsEditing.value) return

  if (wasMultiTouch) {
    if (event.touches.length === 0) {
      wasMultiTouch = false
    }
    lastTapTime = 0
    return
  }

  const now = Date.now()
  if (now - lastTapTime < DOUBLE_TAP_THRESHOLD) {
    event.preventDefault()
    event.stopPropagation()
    lastTapTime = 0
    startEditing()
  } else {
    lastTapTime = now
  }
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
function handleRecommendationApplied(payload: {
  nodeId?: string
  text?: string
  appliedToConnectionId?: string
}): void {
  if (payload?.appliedToConnectionId) {
    if (payload.nodeId !== props.nodeId || !localIsEditing.value) return
    localIsEditing.value = false
    eventBus.emit('node_editor:closed', { nodeId: props.nodeId })
    emit('cancel')
    return
  }
  if (payload?.nodeId !== props.nodeId || !payload?.text) return
  if (!localIsEditing.value) return
  if (props.focusQuestionEditableSplit) {
    editBody.value = stripConceptMapFocusQuestionPrefix(payload.text)
  } else {
    editText.value = payload.text
    originalText.value = payload.text
  }
  localIsEditing.value = false
  eventBus.emit('node_editor:closed', { nodeId: props.nodeId })
  emit('cancel')
}
const unsubRecommendationApplied = eventBus.on(
  'inline_recommendation:applied',
  handleRecommendationApplied
)

function insertSnippetAtCaret(snippet: string): boolean {
  const el = inputRef.value
  if (!el || props.readonly) return false
  const split = props.focusQuestionEditableSplit
  const effective = split ? split.prefix + editBody.value : editText.value
  if (
    diagramStore.type &&
    shouldReplaceLabelWithMathInsert(diagramStore.type, props.nodeId, effective)
  ) {
    if (split) {
      editBody.value = snippet
    } else {
      editText.value = snippet
    }
    const lenField = split ? editBody : editText
    nextTick(() => {
      el.focus()
      const len = lenField.value.length
      el.setSelectionRange(len, len)
      updateInputWidth()
    })
    return true
  }
  const start = el.selectionStart ?? 0
  const end = el.selectionEnd ?? 0
  const cur = split ? editBody.value : editText.value
  const before = cur.slice(0, start)
  const after = cur.slice(end)
  const middle = joinLabelAndMathSnippet(before, snippet)
  let merged = middle + after
  if (merged.length > props.maxLength) {
    merged = merged.slice(0, props.maxLength)
  }
  if (split) {
    editBody.value = merged
  } else {
    editText.value = merged
  }
  const newPos = Math.min(start + (middle.length - before.length), merged.length)
  nextTick(() => {
    el.focus()
    el.setSelectionRange(newPos, newPos)
    updateInputWidth()
  })
  return true
}

function insertLineBreakAtCaret(): boolean {
  if (props.readonly || !localIsEditing.value || props.focusQuestionEditableSplit) return false

  const wasMultiline = usesMultilineEditControl()
  ensureMultilineEditControl()

  const apply = (): boolean => insertSnippetAtCaret('\n')

  if (!wasMultiline) {
    nextTick(() => {
      nextTick(() => apply())
    })
    return true
  }
  return apply()
}

const INSERT_LINE_BREAK_AFTER_EDIT_MS = 80

function handleInsertLineBreak(payload: { nodeId?: string }): void {
  if (payload?.nodeId !== props.nodeId || props.readonly) return
  if (props.focusQuestionEditableSplit) return

  if (!localIsEditing.value) {
    startEditing()
    nextTick(() => {
      setTimeout(() => {
        const el = inputRef.value
        if (el) {
          const len = props.focusQuestionEditableSplit
            ? editBody.value.length
            : editText.value.length
          el.setSelectionRange(len, len)
        }
        insertLineBreakAtCaret()
      }, INSERT_LINE_BREAK_AFTER_EDIT_MS)
    })
    return
  }
  insertLineBreakAtCaret()
}

function handleNodeEditorInsertText(payload: { nodeId?: string; snippet?: string }): void {
  if (payload?.nodeId !== props.nodeId || !payload.snippet) return
  if (!localIsEditing.value) return
  if (props.readonly) return
  const ok = insertSnippetAtCaret(payload.snippet)
  if (ok) {
    eventBus.emit('node_editor:insert_text_consumed', { nodeId: props.nodeId })
  }
}

const unsubInsertText = eventBus.on('node_editor:insert_text', handleNodeEditorInsertText)
const unsubInsertLineBreak = eventBus.on('node_editor:insert_line_break', handleInsertLineBreak)

function handleNodeEditDenied(payload: { nodeId: string; heldByUsername: string }): void {
  if (payload.nodeId !== props.nodeId || !localIsEditing.value) return
  cancelEdit()
  notifyCollab.warning(t('collab.nodeLocked'))
}

const unsubNodeEditDenied = eventBus.on('workshop:node-edit-denied', handleNodeEditDenied)

// Cleanup on unmount
onUnmounted(() => {
  syncDocumentOutsideEditListeners(false)
  unsubEditRequested()
  unsubRecommendationApplied()
  unsubInsertText()
  unsubInsertLineBreak()
  unsubNodeEditDenied()
})
</script>

<template>
  <div
    ref="rootRef"
    class="inline-editable-text"
    :class="[
      rootAlignClass,
      { 'inline-editable-text--full-width': fullWidth },
    ]"
    @dblclick="handleDoubleClick"
    @touchstart="handleTouchStart"
    @touchend="handleTouchEnd"
    @mousedown="handleMouseDown"
  >
    <!-- Hidden span for measuring text width -->
    <span
      v-if="localIsEditing && !autoWrap"
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
      {{ (focusQuestionEditableSplit && localIsEditing ? editBody : editText) || 'M' }}
    </span>

    <!-- Edit mode: show input with ghost text -->
    <div
      v-if="localIsEditing"
      ref="wrapperRef"
      class="inline-edit-wrapper"
      :class="{ 'inline-edit-wrapper--auto-wrap': autoWrap }"
      :style="wrapperStyle"
    >
      <div
        v-if="focusQuestionEditableSplit"
        class="inline-edit-container inline-edit-container--focus-question"
      >
        <span
          class="inline-edit-focus-question-prefix"
          aria-hidden="true"
          >{{ focusQuestionEditableSplit.prefix }}</span
        >
        <input
          :id="fieldHtmlId"
          ref="inputRef"
          v-model="editBody"
          dir="auto"
          type="text"
          class="inline-edit-input"
          :class="{ 'whitespace-nowrap': noWrap || shouldPreventWrap }"
          :style="inputStyle"
          :name="fieldHtmlId"
          :placeholder="focusQuestionEditableSplit.defaultSuffix"
          :aria-label="fieldAriaLabel"
          :maxlength="maxLength"
          @keydown="handleKeydown"
          @blur="handleBlur"
          @mousedown.stop
          @click.stop
        />
      </div>
      <div
        v-else
        class="inline-edit-container"
      >
        <textarea
          v-if="usesMultilineEditControl()"
          :id="fieldHtmlId"
          ref="inputRef"
          v-model="editText"
          dir="auto"
          class="inline-edit-input"
          :class="{
            'whitespace-nowrap': !autoWrap && (noWrap || shouldPreventWrap),
            'inline-edit-input--auto-wrap': autoWrap && editUsesMultilineControl,
          }"
          :style="inputStyle"
          :name="fieldHtmlId"
          :placeholder="resolvedPlaceholder"
          :aria-label="fieldAriaLabel"
          :maxlength="maxLength"
          :rows="autoWrap ? 1 : 2"
          @keydown="handleKeydown"
          @blur="handleBlur"
          @mousedown.stop
          @click.stop
        />
        <template v-else>
          <input
            :id="fieldHtmlId"
            ref="inputRef"
            v-model="editText"
            dir="auto"
            type="text"
            class="inline-edit-input"
            :class="{
              'whitespace-nowrap': noWrap || shouldPreventWrap || autoWrap,
            }"
            :style="inputStyle"
            :name="fieldHtmlId"
            :placeholder="resolvedPlaceholder"
            :aria-label="fieldAriaLabel"
            :maxlength="maxLength"
            @keydown="handleKeydown"
            @blur="handleBlur"
            @mousedown.stop
            @click.stop
          />
        </template>
      </div>
    </div>

    <!-- Display mode: use div so markdown `<p>` + KaTeX stay inside `.diagram-node-md` (invalid inside span). -->
    <div
      v-else
      ref="displayRef"
      dir="auto"
      class="inline-edit-display"
      :class="[
        textClass,
        isDisplayPlaceholder ? 'inline-edit-placeholder-display' : '',
        fullWidth && textAlign === 'center' ? 'inline-edit-display--center-block' : '',
        centerBlockInCircle ? 'inline-edit-display--center-in-circle' : '',
        noWrap
          ? 'whitespace-nowrap'
          : truncate
            ? 'truncate-text'
            : shouldPreventWrap
              ? 'whitespace-nowrap'
              : 'inline-edit-display--wrap',
      ]"
      :style="{
        maxWidth: maxWidth,
        width: stretchesToFillWidth ? '100%' : undefined,
        textAlign: textAlign,
        textDecoration: textDecoration || 'none',
      }"
      :title="truncate ? text : undefined"
    >
      <template v-if="showMutedTailSplit && mutedTailSplit">
        <span>{{ mutedTailSplit.prefix }}</span>
        <span class="inline-edit-muted-suffix">{{ mutedTailSplit.suffix }}</span>
      </template>
      <template v-else-if="isFocusQuestionSplitMode && focusQuestionEditableSplit">
        <span
          class="inline-edit-focus-question-prefix"
          aria-hidden="true"
          >{{ focusQuestionEditableSplit.prefix }}</span
        >
        <span
          :class="
            focusQuestionEditableSplit.body === focusQuestionEditableSplit.defaultSuffix
              ? 'inline-edit-muted-suffix'
              : ''
          "
          >{{ focusQuestionEditableSplit.body }}</span
        >
      </template>
      <!-- eslint-disable vue/no-v-html -- Sanitized via useMarkdown + DOMPurify (KaTeX HTML allowlist) -->
      <div
        v-else-if="markdownDisplayEnabled && needsRichMarkdown"
        class="diagram-node-md inline-block min-w-0 max-w-full text-inherit"
        :style="displayDecorationStyle"
        v-html="displayMarkdownHtml"
      />
      <template v-else>
        <span
          class="inline-edit-plain"
          :class="{ 'inline-edit-plain--whitespace': isWhitespaceOnlyNodeText(text) }"
          :style="displayDecorationStyle"
        >{{ text }}</span>
      </template>
    </div>
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

.inline-editable-text--align-left {
  justify-content: flex-start;
}

.inline-editable-text--align-right {
  justify-content: flex-end;
}

.inline-editable-text--align-center {
  justify-content: center;
}

.inline-edit-wrapper {
  position: relative;
  display: inline-block;
  max-width: 100%;
  overflow: visible; /* Allow text to be visible while typing */
  min-width: fit-content; /* Allow wrapper to expand with content */
}

.inline-edit-wrapper--auto-wrap {
  min-width: 0;
  flex-shrink: 0;
}

.inline-edit-container {
  position: relative;
  display: inline-block;
  width: 100%; /* Use full wrapper width */
  max-width: 100%;
}

.inline-edit-container--focus-question {
  display: inline-flex;
  flex-direction: row;
  flex-wrap: wrap;
  align-items: center;
  justify-content: center;
  gap: 2px;
  width: auto;
  max-width: 100%;
}

.inline-edit-focus-question-prefix {
  user-select: none;
  flex-shrink: 0;
  cursor: default;
  pointer-events: none;
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
  display: inline-block;
  max-width: 100%;
  box-sizing: border-box;
  vertical-align: middle;
  cursor: text;
  user-select: none;
  line-height: 1.4;
}

.inline-edit-plain {
  text-decoration: inherit;
}

.inline-edit-plain--whitespace {
  white-space: pre;
}

.inline-edit-muted-suffix {
  color: rgb(163 163 163);
}

.inline-edit-placeholder-display,
.inline-edit-placeholder-display .inline-edit-plain,
.inline-edit-placeholder-display.diagram-node-md,
.inline-edit-placeholder-display.diagram-node-md :deep(*) {
  color: rgb(107 114 128 / 0.55);
}

:root.dark .inline-edit-muted-suffix {
  color: rgb(115 115 115);
}

:root.dark .inline-edit-placeholder-display,
:root.dark .inline-edit-placeholder-display .inline-edit-plain,
:root.dark .inline-edit-placeholder-display.diagram-node-md,
:root.dark .inline-edit-placeholder-display.diagram-node-md :deep(*) {
  color: rgb(156 163 175 / 0.5);
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

/* Wrap mode: matches measurement element for consistent layout.
   word-break:normal keeps Latin words intact and lets CJK break between characters naturally.
   overflow-wrap:break-word only splits a word when it alone exceeds the line.
   line-break:auto applies language-aware rules (e.g. CJK punctuation kinsoku). */
.inline-edit-display--wrap {
  white-space: pre-wrap;
  word-break: normal;
  overflow-wrap: break-word;
  line-break: auto;
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

textarea.inline-edit-input--auto-wrap {
  min-height: 0;
  line-height: 1.4;
  white-space: pre-wrap;
  word-break: normal;
  overflow-wrap: break-word;
  line-break: auto;
  overflow: hidden;
  resize: none;
  field-sizing: content;
}
</style>
