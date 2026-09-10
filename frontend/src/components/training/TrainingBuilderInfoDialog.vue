<script setup lang="ts">
import { ElInput } from 'element-plus'

import { GraduationCap } from '@lucide/vue'

import SwissGlassDialog from '@/components/common/SwissGlassDialog.vue'
import { useLanguage } from '@/composables'

const title = defineModel<string>('title', { default: '' })
const description = defineModel<string>('description', { default: '' })
const open = defineModel<boolean>('open', { default: false })

defineProps<{
  busy?: boolean
  readonly?: boolean
}>()

const emit = defineEmits<{
  cover: [file: File]
  save: []
}>()

const { t } = useLanguage()

function onCover(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) emit('cover', file)
  input.value = ''
}
</script>

<template>
  <SwissGlassDialog
    v-model="open"
    :ribbon="t('swissGlass.hero.trainingInfo.ribbon')"
    :title="t('swissGlass.hero.trainingInfo.title')"
    :line1="t('swissGlass.hero.trainingInfo.line1')"
    :icon="GraduationCap"
    width="min(28rem, 92vw)"
    dialog-class="builder-info-dialog"
  >
    <div class="builder-info">
      <label>
        {{ t('training.builder.title') }}
        <ElInput
          v-model="title"
          size="small"
          :disabled="readonly"
        />
      </label>
      <label>
        {{ t('training.builder.desc') }}
        <ElInput
          v-model="description"
          type="textarea"
          :rows="3"
          size="small"
          :disabled="readonly"
        />
      </label>
      <label
        v-if="!readonly"
        class="builder-info__cover"
      >
        {{ t('training.builder.cover') }}
        <input
          type="file"
          accept="image/png,image/jpeg,image/webp"
          @change="onCover"
        />
      </label>
    </div>
    <template
      v-if="!readonly"
      #footer
    >
      <div class="swiss-glass-footer">
        <button
          type="button"
          class="mind-map-side-rail-btn mind-map-side-rail-btn--primary min-w-22"
          :disabled="busy"
          @click="emit('save')"
        >
          {{ t('training.builder.save') }}
        </button>
      </div>
    </template>
  </SwissGlassDialog>
</template>

<style scoped>
.builder-info {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.builder-info label {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  color: #57534e;
  font-size: 0.75rem;
}
.builder-info__cover input {
  font-size: 0.75rem;
}
</style>
