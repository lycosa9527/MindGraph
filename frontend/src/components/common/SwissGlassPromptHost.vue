<script setup lang="ts">
/**
 * Global host for swissGlassPrompt.
 */
import { computed, nextTick, ref, watch } from 'vue'

import { Folder } from '@lucide/vue'

import I18nText from '@/components/common/I18nText.vue'
import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import {
  cancelSwissGlassPrompt,
  getSwissGlassPromptState,
  trySettleSwissGlassPrompt,
} from '@/composables/common/useSwissGlassPrompt'
import { useLanguage } from '@/composables/core/useLanguage'

const state = getSwissGlassPromptState()
const { t } = useLanguage()

const draft = ref('')
const error = ref('')
const inputEl = ref<HTMLInputElement | null>(null)

const ribbon = computed(() => state.ribbon || t('swissGlass.confirm.ribbon'))
const confirmLabel = computed(() => state.confirmLabel || t('common.ok'))
const cancelLabel = computed(() => state.cancelLabel || t('common.cancel'))
const plateIcon = computed(() => state.icon ?? Folder)
const placeholder = computed(() => state.inputPlaceholder || state.line1)

watch(
  () => state.session,
  () => {
    if (!state.open) return
    draft.value = state.inputValue
    error.value = ''
    void focusInput()
  }
)

async function focusInput(): Promise<void> {
  await nextTick()
  await nextTick()
  inputEl.value?.focus()
  inputEl.value?.select()
}

function onConfirm(): void {
  error.value = trySettleSwissGlassPrompt(draft.value)
}

function onCancel(): void {
  cancelSwissGlassPrompt()
}
</script>

<template>
  <SwissGlassDialog
    v-model="state.open"
    :ribbon="ribbon"
    :ribbon-key="state.ribbonKey || 'swissGlass.confirm.ribbon'"
    :title="state.title"
    :title-key="state.titleKey"
    :line1="state.line1"
    :line1-key="state.line1Key"
    :icon="plateIcon"
    width="min(440px, 92vw)"
    :close-on-click-modal="false"
    @close="onCancel"
  >
    <div class="swiss-glass-stack">
      <label class="swiss-glass-field">
        <input
          ref="inputEl"
          v-model="draft"
          type="text"
          class="swiss-glass-field__input"
          :placeholder="placeholder"
          :maxlength="state.inputMaxLength > 0 ? state.inputMaxLength : undefined"
          :aria-invalid="error ? 'true' : undefined"
          :aria-label="state.line1 || state.title"
          autocomplete="off"
          @input="error = ''"
          @keydown.enter.prevent="onConfirm"
        />
      </label>
      <p
        v-if="error"
        class="swiss-glass-error"
      >
        {{ error }}
      </p>
    </div>
    <template #footer>
      <div class="swiss-glass-footer">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary min-w-22"
          @click="onCancel"
        >
          <I18nText
            v-if="!state.cancelLabel || state.cancelLabelKey"
            :k="state.cancelLabelKey || 'common.cancel'"
          />
          <template v-else>{{ cancelLabel }}</template>
        </button>
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--primary min-w-22"
          @click="onConfirm"
        >
          <I18nText
            v-if="!state.confirmLabel || state.confirmLabelKey"
            :k="state.confirmLabelKey || 'common.ok'"
          />
          <template v-else>{{ confirmLabel }}</template>
        </button>
      </div>
    </template>
  </SwissGlassDialog>
</template>
