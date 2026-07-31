<script setup lang="ts">
/**
 * MaiteProblemInput — problem textarea with OCR upload trigger.
 */
import { ref } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { eventBus } from '@/composables/core/useEventBus'

import ocrUploadIcon from '@/assets/maite/ocr-upload.svg'

const props = defineProps<{
  modelValue: string
  scene?: 'demo' | 'question'
  disabled?: boolean
  placeholder?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const { t } = useLanguage()
const fileInput = ref<HTMLInputElement | null>(null)

function onInput(event: Event): void {
  const target = event.target as HTMLTextAreaElement
  emit('update:modelValue', target.value)
}

function openFilePicker(): void {
  fileInput.value?.click()
}

function onFileSelected(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) {
    return
  }
  eventBus.emit('maite:ocr_requested', {
    file,
    scene: props.scene ?? 'demo',
  })
  input.value = ''
}
</script>

<template>
  <div class="maite-problem-input">
    <textarea
      class="maite-problem-input__textarea"
      :value="modelValue"
      :disabled="disabled"
      :placeholder="placeholder ?? t('maite.problem.placeholder')"
      rows="4"
      @input="onInput"
    />
    <div class="maite-problem-input__actions">
      <button
        type="button"
        class="maite-problem-input__ocr"
        :disabled="disabled"
        @click="openFilePicker"
      >
        <img :src="ocrUploadIcon" alt="" class="maite-problem-input__ocr-icon" />
        {{ t('maite.problem.ocr') }}
      </button>
      <input
        ref="fileInput"
        type="file"
        accept="image/png,image/jpeg,image/webp"
        class="maite-problem-input__file"
        @change="onFileSelected"
      />
    </div>
  </div>
</template>

<style scoped>
.maite-problem-input {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.maite-problem-input__textarea {
  width: 100%;
  min-height: 96px;
  padding: 12px;
  border: 1px solid var(--el-border-color, #e7e5e4);
  border-radius: 10px;
  resize: vertical;
  font-size: 14px;
  line-height: 1.5;
  font-family: inherit;
}

.maite-problem-input__actions {
  display: flex;
  justify-content: flex-end;
}

.maite-problem-input__ocr {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border: 1px solid var(--el-border-color, #e7e5e4);
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
}

.maite-problem-input__ocr:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.maite-problem-input__ocr-icon {
  width: 16px;
  height: 16px;
}

.maite-problem-input__file {
  display: none;
}
</style>
