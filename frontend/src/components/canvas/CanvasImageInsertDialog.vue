<script setup lang="ts">
/**
 * Swiss glass dialog to attach an image URL or compressed file to the selected node.
 */
import { ref, watch } from 'vue'

import { Image } from '@lucide/vue'

import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import { sanitizeMindMapImageUrl } from '@/utils/mindMapAdornments'
import { mindMapNodeImageFileToDataUrl } from '@/utils/mindMapNodeImageDataUrl'

const open = defineModel<boolean>({ required: true })

const props = defineProps<{
  initialUrl?: string
}>()

const emit = defineEmits<{
  confirm: [imageUrl: string]
}>()

const { t } = useLanguage()
const url = ref('')
const error = ref('')
const busy = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

watch(open, (isOpen) => {
  if (isOpen) {
    url.value = props.initialUrl ?? ''
    error.value = ''
    busy.value = false
  }
})

function close(): void {
  open.value = false
}

function confirmUrl(): void {
  const sanitized = sanitizeMindMapImageUrl(url.value)
  if (!sanitized) {
    error.value = t('canvas.ribbon.imageInvalid')
    return
  }
  emit('confirm', sanitized)
  close()
}

async function onFile(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  busy.value = true
  error.value = ''
  const dataUrl = await mindMapNodeImageFileToDataUrl(file)
  busy.value = false
  if (!dataUrl) {
    error.value = t('canvas.ribbon.imageTooLarge')
    return
  }
  emit('confirm', dataUrl)
  close()
}
</script>

<template>
  <SwissGlassDialog
    v-model="open"
    :ribbon="t('canvas.hero.image.ribbon')"
    :title="t('canvas.hero.image.title')"
    :line1="t('canvas.hero.image.line1')"
    :icon="Image"
    width="min(420px, 92vw)"
  >
    <div class="swiss-glass-stack">
      <label class="swiss-glass-field">
        <span class="swiss-glass-field__kicker">{{ t('canvas.ribbon.imageUrl') }}</span>
        <input
          v-model="url"
          type="url"
          class="swiss-glass-field__input"
          :placeholder="t('canvas.ribbon.imageUrl')"
          :disabled="busy"
          autocomplete="off"
          @keydown.enter.prevent="confirmUrl"
        />
      </label>
      <div>
        <input
          ref="fileInput"
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif"
          class="hidden"
          @change="onFile"
        />
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--secondary"
          :disabled="busy"
          @click="fileInput?.click()"
        >
          {{ t('canvas.ribbon.imagePick') }}
        </button>
      </div>
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
          @click="close"
        >
          {{ t('common.cancel') }}
        </button>
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--primary min-w-22"
          :disabled="busy"
          @click="confirmUrl"
        >
          {{ t('canvas.ribbon.imageConfirm') }}
        </button>
      </div>
    </template>
  </SwissGlassDialog>
</template>

<style scoped>
.hidden {
  display: none;
}
</style>
