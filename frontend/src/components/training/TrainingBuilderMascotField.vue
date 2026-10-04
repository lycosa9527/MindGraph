<script setup lang="ts">
/**
 * Upload a WebP mascot onto the current mark. It lands on the right of the slide.
 */
import { computed, ref } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useNotifications } from '@/composables/core/useNotifications'
import { currentMarkStep } from '@/composables/training/trainingMarkSteps'
import { uploadTrainingFile } from '@/composables/training/uploadTrainingFile'
import { useTrainingBuilderStore } from '@/stores/trainingBuilder'

const emit = defineEmits<{
  placed: [file: { id: string; url: string }]
}>()

const { t } = useLanguage()
const notify = useNotifications()
const builder = useTrainingBuilderStore()
const busy = ref(false)

const current = computed(() => {
  const step = builder.current
  if (!step) return null
  const at = currentMarkStep(step)
  const matches = (step.overlays || []).filter(
    (row) => row.kind === 'role' && row.asset_id && (row.step || 1) === at
  )
  return matches[matches.length - 1] || null
})

function clear(): void {
  const step = builder.current
  const placed = current.value
  if (!step || !placed) return
  builder.wake()
  step.overlays = (step.overlays || []).filter((row) => row !== placed)
}

async function onFile(event: Event): Promise<void> {
  const input = event.target
  if (!(input instanceof HTMLInputElement)) return
  const file = input.files?.[0]
  input.value = ''
  if (!file || !builder.courseId) return
  busy.value = true
  builder.wake()
  try {
    const uploaded = await uploadTrainingFile(builder.courseId, 'mascot', file)
    emit('placed', uploaded)
  } catch {
    notify.errorKey('training.builder.uploadFailed')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <label class="slide-mascot">
    <span class="slide-mascot__label"><I18nText k="training.builder.mascot" /></span>
    <input
      type="file"
      accept="image/webp,.webp"
      :disabled="busy"
      :aria-label="t('training.builder.mascot')"
      @change="onFile"
    />
    <img
      v-if="current?.src"
      class="slide-mascot__preview"
      :src="current.src"
      alt=""
    />
    <button
      v-if="current"
      type="button"
      class="slide-mascot__remove"
      :aria-label="t('training.builder.mascotRemove')"
      @click.prevent="clear"
    >
      <I18nText k="training.builder.mascotRemove" />
    </button>
  </label>
</template>

<style scoped>
.slide-mascot {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  color: #44403c;
  font-size: 0.75rem;
}
.slide-mascot__label {
  font-weight: 650;
}
.slide-mascot__preview {
  width: 1.7rem;
  height: 1.7rem;
  object-fit: contain;
}
.slide-mascot__remove {
  border: 0;
  background: transparent;
  color: #78716c;
  cursor: pointer;
  font-size: 0.72rem;
}
</style>
