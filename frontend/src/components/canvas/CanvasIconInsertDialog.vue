<script setup lang="ts">
/**
 * Swiss glass emoji picker for a mind-map node icon adornment.
 */
import { Smile } from '@lucide/vue'

import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import EmojiPicker from '@/components/workshop-chat/EmojiPicker.vue'
import { useLanguage } from '@/composables/core/useLanguage'

const open = defineModel<boolean>({ required: true })

const emit = defineEmits<{
  confirm: [icon: string]
  clear: []
}>()

const { t } = useLanguage()

function close(): void {
  open.value = false
}

function onSelect(_name: string, code: string): void {
  emit('confirm', code)
  close()
}

function clearAndClose(): void {
  emit('clear')
  close()
}
</script>

<template>
  <SwissGlassDialog
    v-model="open"
    :ribbon="t('canvas.hero.icon.ribbon')"
    :title="t('canvas.hero.icon.title')"
    :line1="t('canvas.hero.icon.line1')"
    :icon="Smile"
    width="min(380px, 92vw)"
  >
    <EmojiPicker
      hide-search
      lead-category="objects"
      @select="onSelect"
    />
    <template #footer>
      <div class="swiss-glass-footer">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--ghost min-w-22"
          @click="clearAndClose"
        >
          {{ t('canvas.ribbon.clearIcon') }}
        </button>
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary min-w-22"
          @click="close"
        >
          {{ t('common.cancel') }}
        </button>
      </div>
    </template>
  </SwissGlassDialog>
</template>
