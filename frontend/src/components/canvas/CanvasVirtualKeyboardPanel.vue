<script setup lang="ts">
/**
 * On-screen keyboard (simple-keyboard) for canvas / focused inputs.
 * Custom keys are always English QWERTY. CJK and other IME languages use
 * System IME (physical / platform keyboard) — browsers cannot feed the OS IME
 * from synthetic key taps.
 * Selected node + first printable key: enter edit, clear label, insert that key.
 * Already-open inline edit keeps the current draft (append / caret).
 * Scope: plain input/textarea focus (e.g. node labels, top bar title). MathLive / contenteditable not integrated.
 */
import { nextTick, onUnmounted, ref, watch } from 'vue'

import { storeToRefs } from 'pinia'

import { X } from '@lucide/vue'

import { eventBus } from '@/composables/core/useEventBus'
import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { useDiagramSession } from '@/composables/diagram/useDiagramSession'
import { CANVAS_OVERLAY_Z } from '@/config/uiConfig'
import { loadLayoutForPreset } from '@/i18n/keyboardLayoutForUiLocale'
import { useUIStore } from '@/stores/ui'
import { isEditableTextField } from '@/utils/virtualKeyboardChrome'
import {
  hideSystemVirtualKeyboard,
  prepareFieldForSystemIme,
  showSystemVirtualKeyboard,
} from '@/utils/virtualKeyboardIme'
import {
  isLiveNodeInlineEditField,
  virtualKeyboardButtonToReplaceInsert,
  waitForNodeInlineEditField,
} from '@/utils/virtualKeyboardTyping'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const { t } = useLanguage()
const notify = useNotifications()
const diagramStore = useDiagramSession()
const { language: uiLanguage } = storeToRefs(useUIStore())

const keyboardMountRef = ref<HTMLDivElement | null>(null)
const imeMode = ref(false)

/** Narrow surface used from simple-keyboard (avoids eager typing import). */
interface SimpleKeyboardApi {
  destroy(): void
  setInput(input: string, inputName?: string, skipSync?: boolean): void
  setOptions(options: Record<string, unknown>): void
  clearInput(inputName?: string): void
}

let keyboardInstance: SimpleKeyboardApi | null = null
let focusInHandler: ((ev: FocusEvent) => void) | null = null
let escapeHandler: ((ev: KeyboardEvent) => void) | null = null

let hintShownThisOpen = false
let replaceEditInFlight = false
let imeCompositionActive = false
let compositionStartHandler: ((ev: CompositionEvent) => void) | null = null
let compositionEndHandler: ((ev: CompositionEvent) => void) | null = null
/** Survives key taps that move document.activeElement off the node <input>. */
let lastEditableField: HTMLInputElement | HTMLTextAreaElement | null = null

function resolveTargetField(): HTMLInputElement | HTMLTextAreaElement | null {
  if (isEditableTextField(document.activeElement)) {
    lastEditableField = document.activeElement
    return document.activeElement
  }
  if (isLiveNodeInlineEditField(lastEditableField) && document.contains(lastEditableField)) {
    return lastEditableField
  }
  return null
}

function hasLiveNodeEditor(): boolean {
  return isLiveNodeInlineEditField(resolveTargetField())
}

function applyInputToActiveField(input: string): void {
  if (imeMode.value || imeCompositionActive) {
    return
  }
  const el = resolveTargetField()
  if (!el) {
    return
  }
  let next = input
  if (el.maxLength >= 0 && next.length > el.maxLength) {
    next = next.slice(0, el.maxLength)
  }
  el.value = next
  el.dispatchEvent(new Event('input', { bubbles: true }))
  if (document.activeElement !== el) {
    el.focus({ preventScroll: true })
  }
}

function syncKeyboardFromFocusTarget(): void {
  if (!keyboardInstance) return
  const el = resolveTargetField()
  if (el) {
    keyboardInstance.setInput(el.value)
  }
}

function onKeyboardChange(input: string): void {
  if (replaceEditInFlight || imeMode.value || imeCompositionActive) return
  applyInputToActiveField(input)
}

async function ensureEditableFieldForIme(): Promise<HTMLInputElement | HTMLTextAreaElement | null> {
  const existing = resolveTargetField()
  if (existing) {
    return existing
  }
  const nodeId = diagramStore.selectedNodes[0]
  if (!nodeId) {
    if (!hintShownThisOpen) {
      hintShownThisOpen = true
      notify.info(t('canvas.toolbar.virtualKeyboardFocusHint'))
    }
    return null
  }
  eventBus.emit('node:edit_requested', { nodeId })
  const el = await waitForNodeInlineEditField(nodeId)
  if (el) {
    lastEditableField = el
  }
  return el
}

async function enableSystemIme(): Promise<void> {
  const el = await ensureEditableFieldForIme()
  if (!el) {
    imeMode.value = false
    return
  }
  imeMode.value = true
  const shown = showSystemVirtualKeyboard(el, uiLanguage.value)
  if (!shown) {
    prepareFieldForSystemIme(el, uiLanguage.value)
  }
}

function disableSystemIme(): void {
  imeMode.value = false
  hideSystemVirtualKeyboard()
  const el = resolveTargetField()
  if (el) {
    el.focus({ preventScroll: true })
  }
}

function toggleSystemIme(): void {
  if (imeMode.value) {
    disableSystemIme()
    return
  }
  void enableSystemIme()
}

async function beginReplaceEditOnSelectedNode(insert: string): Promise<void> {
  const nodeId = diagramStore.selectedNodes[0]
  if (!nodeId) {
    replaceEditInFlight = false
    if (!hintShownThisOpen) {
      hintShownThisOpen = true
      notify.info(t('canvas.toolbar.virtualKeyboardFocusHint'))
    }
    return
  }
  try {
    eventBus.emit('node:edit_requested', { nodeId, replaceContent: true })
    const el = await waitForNodeInlineEditField(nodeId)
    if (!el) {
      if (!hintShownThisOpen) {
        hintShownThisOpen = true
        notify.info(t('canvas.toolbar.virtualKeyboardFocusHint'))
      }
      return
    }
    lastEditableField = el
    keyboardInstance?.setInput(insert)
    applyInputToActiveField(insert)
  } finally {
    replaceEditInFlight = false
  }
}

function onKeyboardKeyPress(button: string): void {
  if (imeMode.value || imeCompositionActive) {
    return
  }
  if (hasLiveNodeEditor() || isEditableTextField(document.activeElement)) {
    return
  }
  const insert = virtualKeyboardButtonToReplaceInsert(button)
  if (insert == null) {
    return
  }
  replaceEditInFlight = true
  void beginReplaceEditOnSelectedNode(insert)
}

async function buildKeyboardOptions(): Promise<Record<string, unknown>> {
  const layoutBundle = await loadLayoutForPreset('english')
  return {
    layout: layoutBundle.layout,
    preventMouseDownDefault: true,
    rtl: false,
    theme: 'hg-theme-default hg-layout-default',
    onChange: onKeyboardChange,
    onKeyPress: onKeyboardKeyPress,
  }
}

async function initKeyboard(): Promise<void> {
  await import('simple-keyboard/build/css/index.css')
  const [{ SimpleKeyboard: KeyboardCtor }, opts] = await Promise.all([
    import('simple-keyboard'),
    buildKeyboardOptions(),
  ])
  const mount = keyboardMountRef.value
  if (!mount) return
  mount.replaceChildren()
  keyboardInstance = new KeyboardCtor(mount, opts) as SimpleKeyboardApi
  focusInHandler = () => {
    syncKeyboardFromFocusTarget()
  }
  window.addEventListener('focusin', focusInHandler)
  compositionStartHandler = () => {
    imeCompositionActive = true
  }
  compositionEndHandler = () => {
    imeCompositionActive = false
    syncKeyboardFromFocusTarget()
  }
  window.addEventListener('compositionstart', compositionStartHandler)
  window.addEventListener('compositionend', compositionEndHandler)
  escapeHandler = (ev: KeyboardEvent) => {
    if (ev.key === 'Escape') {
      emit('update:modelValue', false)
    }
  }
  window.addEventListener('keydown', escapeHandler)
}

function destroyKeyboard(): void {
  if (focusInHandler) {
    window.removeEventListener('focusin', focusInHandler)
    focusInHandler = null
  }
  if (compositionStartHandler) {
    window.removeEventListener('compositionstart', compositionStartHandler)
    compositionStartHandler = null
  }
  if (compositionEndHandler) {
    window.removeEventListener('compositionend', compositionEndHandler)
    compositionEndHandler = null
  }
  imeCompositionActive = false
  if (escapeHandler) {
    window.removeEventListener('keydown', escapeHandler)
    escapeHandler = null
  }
  if (keyboardInstance) {
    keyboardInstance.destroy()
    keyboardInstance = null
  }
}

watch(
  () => props.modelValue,
  async (open) => {
    if (open) {
      hintShownThisOpen = false
      replaceEditInFlight = false
      lastEditableField = isEditableTextField(document.activeElement)
        ? document.activeElement
        : null
      await nextTick()
      await initKeyboard()
      syncKeyboardFromFocusTarget()
    } else {
      lastEditableField = null
      disableSystemIme()
      destroyKeyboard()
    }
  }
)

watch(uiLanguage, () => {
  if (!props.modelValue || !imeMode.value) return
  const el = resolveTargetField()
  if (el) {
    prepareFieldForSystemIme(el, uiLanguage.value)
  }
})

onUnmounted(() => {
  destroyKeyboard()
})

function closePanel(): void {
  emit('update:modelValue', false)
}
</script>

<template>
  <Teleport to="body">
    <div
      v-show="modelValue"
      class="virtual-keyboard-dock pointer-events-none fixed inset-x-0 bottom-0 flex justify-center pb-[env(safe-area-inset-bottom,0px)] px-2"
      :style="{ zIndex: CANVAS_OVERLAY_Z.VIRTUAL_KEYBOARD }"
      :aria-hidden="!modelValue"
    >
      <div
        class="virtual-keyboard-panel pointer-events-auto mb-2 w-full max-w-4xl rounded-t-lg border border-gray-200 bg-white shadow-xl dark:border-gray-600 dark:bg-gray-900"
        role="dialog"
        :aria-label="t('canvas.toolbar.moreAppVirtualKeyboard')"
      >
        <div
          class="flex items-center justify-between gap-2 border-b border-gray-200 px-2 py-1.5 dark:border-gray-600"
        >
          <span class="text-xs font-medium text-gray-600 dark:text-gray-300">{{
            t('canvas.toolbar.moreAppVirtualKeyboard')
          }}</span>
          <div class="flex items-center gap-1">
            <button
              type="button"
              class="virtual-keyboard-ime-btn"
              :class="{ 'is-active': imeMode }"
              data-testid="virtual-keyboard-ime"
              data-virtual-keyboard-chrome
              :title="t('canvas.toolbar.virtualKeyboardIme')"
              :aria-label="t('canvas.toolbar.virtualKeyboardIme')"
              :aria-pressed="imeMode"
              @mousedown.prevent
              @click="toggleSystemIme"
            >
              {{ t('canvas.toolbar.virtualKeyboardIme') }}
            </button>
            <button
              type="button"
              class="rounded p-1 text-gray-500 hover:bg-gray-100 hover:text-gray-800 dark:hover:bg-gray-800 dark:hover:text-gray-100"
              :aria-label="t('canvas.toolbar.virtualKeyboardClose')"
              @mousedown.prevent
              @click="closePanel"
            >
              <X class="h-4 w-4" />
            </button>
          </div>
        </div>
        <p
          v-if="imeMode"
          class="virtual-keyboard-ime-hint px-3 py-2 text-xs text-gray-500 dark:text-gray-400"
        >
          {{ t('canvas.toolbar.virtualKeyboardImeHint') }}
        </p>
        <div
          v-show="!imeMode"
          ref="keyboardMountRef"
          class="simple-keyboard-host p-2"
        />
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.virtual-keyboard-ime-btn {
  margin: 0;
  padding: 2px 8px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #4b5563;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.2;
  cursor: pointer;
}

.virtual-keyboard-ime-btn:hover {
  background: #f3f4f6;
  color: #111827;
}

.virtual-keyboard-ime-btn.is-active {
  background: #e0e7ff;
  color: #3730a3;
}

.dark .virtual-keyboard-ime-btn {
  color: #d1d5db;
}

.dark .virtual-keyboard-ime-btn:hover {
  background: #374151;
  color: #f9fafb;
}

.dark .virtual-keyboard-ime-btn.is-active {
  background: #312e81;
  color: #c7d2fe;
}

.simple-keyboard-host :deep(.hg-theme-default) {
  background-color: #f3f4f6;
}
.dark .simple-keyboard-host :deep(.hg-theme-default) {
  background-color: #1f2937;
}
.dark .simple-keyboard-host :deep(.hg-button) {
  background: #374151;
  border-bottom-color: #4b5563;
  color: #f3f4f6;
  box-shadow: 0 0 3px -1px rgba(0, 0, 0, 0.5);
}
.dark .simple-keyboard-host :deep(.hg-button.hg-activeButton) {
  background: #4b5563;
}
</style>
