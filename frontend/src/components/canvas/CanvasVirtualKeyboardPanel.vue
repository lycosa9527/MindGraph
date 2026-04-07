<script setup lang="ts">
/**
 * On-screen keyboard (simple-keyboard) for canvas / focused inputs.
 * Does not open node edit; user double-taps/clicks labels first per InlineEditableText.
 * Scope: plain input/textarea focus (e.g. node labels, top bar title). MathLive / contenteditable not integrated.
 */
import { nextTick, onUnmounted, ref, watch } from 'vue'

import { X } from 'lucide-vue-next'

import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { CANVAS_OVERLAY_Z } from '@/config/uiConfig'
import {
  type LayoutPresetName,
  getLayoutPresetKeyForUiLocale,
  loadLayoutForPreset,
} from '@/i18n/keyboardLayoutForUiLocale'
import { isRtlUiLocale } from '@/i18n/locales'
import type { LocaleCode } from '@/i18n/supportedUiLocales'
import { useUIStore } from '@/stores/ui'

const props = defineProps<{
  modelValue: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const { t } = useLanguage()
const notify = useNotifications()
const uiStore = useUIStore()

const keyboardMountRef = ref<HTMLDivElement | null>(null)

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

const lastPreset = ref<LayoutPresetName | null>(null)
let hintShownThisOpen = false

function isTextField(el: EventTarget | null): el is HTMLInputElement | HTMLTextAreaElement {
  return el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement
}

function isEditableTextField(el: HTMLInputElement | HTMLTextAreaElement): boolean {
  return !el.readOnly && !el.disabled
}

function applyInputToActiveField(input: string): void {
  const el = document.activeElement
  if (!isTextField(el) || !isEditableTextField(el)) {
    return
  }
  let next = input
  if (el.maxLength >= 0 && next.length > el.maxLength) {
    next = next.slice(0, el.maxLength)
  }
  el.value = next
  el.dispatchEvent(new Event('input', { bubbles: true }))
}

function syncKeyboardFromFocusTarget(): void {
  if (!keyboardInstance) return
  const el = document.activeElement
  if (isTextField(el) && isEditableTextField(el)) {
    keyboardInstance.setInput(el.value)
  }
}

function onKeyboardChange(input: string): void {
  applyInputToActiveField(input)
}

function onKeyboardKeyPress(): void {
  const el = document.activeElement
  if (isTextField(el) && isEditableTextField(el)) {
    return
  }
  if (!hintShownThisOpen) {
    hintShownThisOpen = true
    notify.info(t('canvas.toolbar.virtualKeyboardFocusHint'))
  }
}

async function buildKeyboardOptions(locale: LocaleCode): Promise<Record<string, unknown>> {
  const preset = getLayoutPresetKeyForUiLocale(locale)
  lastPreset.value = preset
  const layoutBundle = await loadLayoutForPreset(preset)
  const opts: Record<string, unknown> = {
    layout: layoutBundle.layout,
    preventMouseDownDefault: true,
    rtl: isRtlUiLocale(locale),
    theme: 'hg-theme-default hg-layout-default',
    onChange: onKeyboardChange,
    onKeyPress: onKeyboardKeyPress,
  }
  if (layoutBundle.layoutCandidates) {
    opts.layoutCandidates = layoutBundle.layoutCandidates
    opts.enableLayoutCandidates = true
  }
  return opts
}

async function initKeyboard(): Promise<void> {
  await import('simple-keyboard/build/css/index.css')
  const [{ SimpleKeyboard: KeyboardCtor }, opts] = await Promise.all([
    import('simple-keyboard'),
    buildKeyboardOptions(uiStore.language as LocaleCode),
  ])
  const mount = keyboardMountRef.value
  if (!mount) return
  keyboardInstance = new KeyboardCtor(mount, opts) as SimpleKeyboardApi
  focusInHandler = () => {
    syncKeyboardFromFocusTarget()
  }
  window.addEventListener('focusin', focusInHandler)
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
  if (escapeHandler) {
    window.removeEventListener('keydown', escapeHandler)
    escapeHandler = null
  }
  if (keyboardInstance) {
    keyboardInstance.destroy()
    keyboardInstance = null
  }
  lastPreset.value = null
}

async function applyLocaleLayout(locale: LocaleCode): Promise<void> {
  if (!keyboardInstance) return
  const preset = getLayoutPresetKeyForUiLocale(locale)
  if (lastPreset.value === preset) {
    keyboardInstance.setOptions({ rtl: isRtlUiLocale(locale) })
    return
  }
  const layoutBundle = await loadLayoutForPreset(preset)
  lastPreset.value = preset
  keyboardInstance.clearInput()
  keyboardInstance.setOptions({
    layout: layoutBundle.layout,
    rtl: isRtlUiLocale(locale),
    layoutCandidates: layoutBundle.layoutCandidates ?? null,
    enableLayoutCandidates: Boolean(layoutBundle.layoutCandidates),
  })
  syncKeyboardFromFocusTarget()
}

watch(
  () => props.modelValue,
  async (open) => {
    if (open) {
      hintShownThisOpen = false
      await nextTick()
      await initKeyboard()
      syncKeyboardFromFocusTarget()
    } else {
      destroyKeyboard()
    }
  }
)

watch(
  () => uiStore.language,
  async () => {
    if (props.modelValue && keyboardInstance) {
      await applyLocaleLayout(uiStore.language as LocaleCode)
    }
  }
)

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
          <button
            type="button"
            class="rounded p-1 text-gray-500 hover:bg-gray-100 hover:text-gray-800 dark:hover:bg-gray-800 dark:hover:text-gray-100"
            :aria-label="t('canvas.toolbar.virtualKeyboardClose')"
            @click="closePanel"
          >
            <X class="h-4 w-4" />
          </button>
        </div>
        <div
          ref="keyboardMountRef"
          class="simple-keyboard-host p-2"
        />
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
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
