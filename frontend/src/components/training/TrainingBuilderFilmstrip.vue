<script setup lang="ts">
import { ref } from 'vue'

import { ElButton } from 'element-plus'

import TrainingSlidePreview from '@/components/training/TrainingSlidePreview.vue'
import { useLanguage } from '@/composables'
import type { TrainingCourseStep } from '@/types/training'

defineProps<{
  steps: TrainingCourseStep[]
  selected: number
  thumbs?: (string | null)[]
  busy?: boolean
  readonly?: boolean
}>()

const emit = defineEmits<{
  select: [index: number]
  add: []
  images: [files: File[]]
  remove: [index: number]
}>()

const { t } = useLanguage()
const imageInput = ref<HTMLInputElement | null>(null)

function pickImages(): void {
  imageInput.value?.click()
}

function onImages(event: Event): void {
  const input = event.target
  if (!(input instanceof HTMLInputElement)) return
  const files = Array.from(input.files || [])
  input.value = ''
  if (files.length) emit('images', files)
}
</script>

<template>
  <aside class="filmstrip">
    <div
      v-if="!readonly"
      class="filmstrip__actions"
    >
      <ElButton
        size="small"
        class="admin-swiss-btn filmstrip__add"
        @click="emit('add')"
      >
        {{ t('training.builder.addSlide') }}
      </ElButton>
      <ElButton
        size="small"
        class="admin-swiss-btn filmstrip__add"
        :disabled="busy"
        @click="pickImages"
      >
        {{ t('training.builder.addImage') }}
      </ElButton>
    </div>
    <input
      ref="imageInput"
      class="filmstrip__file"
      type="file"
      accept="image/png,image/jpeg,image/webp"
      multiple
      :aria-label="t('training.builder.addImage')"
      @change="onImages"
    >
    <div
      v-for="(step, index) in steps"
      :key="`${step.type}-${index}`"
      class="filmstrip__item"
      :class="{ 'is-active': index === selected }"
    >
      <button
        type="button"
        class="filmstrip__pick"
        @click="emit('select', index)"
      >
        <TrainingSlidePreview
          :step="step"
          :index="index"
          :thumb="thumbs?.[index]"
          compact
        />
      </button>
      <button
        v-if="!readonly"
        type="button"
        class="filmstrip__delete"
        :aria-label="t('training.builder.deleteSlide')"
        @click.stop="emit('remove', index)"
      >
        ×
      </button>
    </div>
  </aside>
</template>

<style scoped src="@/styles/admin-swiss-controls.css"></style>
<style scoped>
.filmstrip {
  display: flex;
  width: 11.5rem;
  flex-shrink: 0;
  flex-direction: column;
  gap: 0.65rem;
  overflow: auto;
  border-right: 1px solid #e7e5e4;
  background: #fff;
  padding: 0.75rem;
}
@media (max-width: 768px) {
  .filmstrip {
    width: 100%;
    max-height: 8.5rem;
    flex-direction: row;
    overflow: auto;
    border-right: 0;
    border-bottom: 1px solid #e7e5e4;
  }
  .filmstrip__actions {
    flex-direction: row;
    align-items: center;
  }
}
.filmstrip__actions {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0.5rem;
}
.filmstrip__actions :deep(.filmstrip__add.el-button) {
  display: flex;
  width: 100%;
  margin: 0;
  box-sizing: border-box;
  justify-content: center;
}
.filmstrip__file {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
}
.filmstrip__item {
  position: relative;
  padding: 0;
  border: 2px solid transparent;
  background: transparent;
}
.filmstrip__item.is-active {
  border-color: #1c1917;
}
.filmstrip__pick {
  display: block;
  width: 100%;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
}
.filmstrip__delete {
  position: absolute;
  top: 0.2rem;
  right: 0.2rem;
  z-index: 5;
  display: flex;
  width: 1.15rem;
  height: 1.15rem;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 999px;
  background: rgb(28 25 23 / 0.78);
  color: #fafaf9;
  font-size: 0.85rem;
  line-height: 1;
  cursor: pointer;
  opacity: 0;
  pointer-events: none;
}
.filmstrip__item:hover .filmstrip__delete,
.filmstrip__delete:focus-visible {
  opacity: 1;
  pointer-events: auto;
}
.filmstrip__delete:hover {
  background: #1c1917;
}
</style>
