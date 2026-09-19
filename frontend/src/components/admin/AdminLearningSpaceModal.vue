<script setup lang="ts">
/**
 * Learning Space admin dialog — Wangyx813 overlay / card chrome.
 */
import { X } from '@lucide/vue'

import { useLanguage } from '@/composables'

const visible = defineModel<boolean>({ required: true })

defineProps<{
  title: string
  eyebrow?: string
  hint?: string
  wide?: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

const { t } = useLanguage()

function onClose(): void {
  visible.value = false
  emit('close')
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="ls-modal-overlay"
      @click.self="onClose"
    >
      <div
        class="ls-modal"
        :class="{ 'ls-modal--wide': wide }"
        role="dialog"
        aria-modal="true"
        :aria-label="title"
      >
        <header class="ls-modal__head">
          <div class="ls-modal__head-text">
            <p
              v-if="eyebrow"
              class="ls-modal__eyebrow"
            >
              {{ eyebrow }}
            </p>
            <h2 class="ls-modal__title">{{ title }}</h2>
            <p
              v-if="hint"
              class="ls-modal__hint"
            >
              {{ hint }}
            </p>
          </div>
          <button
            type="button"
            class="ls-modal__close"
            :aria-label="t('common.close')"
            @click="onClose"
          >
            <X :size="18" />
          </button>
        </header>
        <div class="ls-modal__body">
          <div class="ls-modal__pane">
            <slot />
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
