<script setup lang="ts">
import { useLanguage } from '@/composables'
import type { TrainingCourseStep } from '@/types/training'

const NOTES_MAX = 4000

const props = defineProps<{
  step: TrainingCourseStep
}>()

const { t } = useLanguage()

function onInput(event: Event): void {
  const field = event.target
  if (!(field instanceof HTMLTextAreaElement)) return
  props.step.notes = field.value
}
</script>

<template>
  <label class="builder-notes">
    <span class="builder-notes__label">{{ t('training.builder.notes') }}</span>
    <textarea
      class="builder-notes__field"
      :value="step.notes || ''"
      :maxlength="NOTES_MAX"
      :placeholder="t('training.builder.notesHint')"
      rows="4"
      @input="onInput"
    />
  </label>
</template>

<style scoped>
.builder-notes {
  display: flex;
  flex-shrink: 0;
  flex-direction: column;
  gap: 0.4rem;
  border: 1px solid #e7e5e4;
  background: #fff;
  padding: 0.7rem 0.85rem 0.8rem;
}
.builder-notes__label {
  color: #1c1917;
  font-size: 0.78rem;
  font-weight: 650;
}
.builder-notes__field {
  width: 100%;
  min-height: 6.5rem;
  resize: vertical;
  border: 1px solid #e7e5e4;
  background: #fafaf9;
  color: #1c1917;
  padding: 0.55rem 0.7rem;
  font-size: 0.85rem;
  line-height: 1.45;
}
.builder-notes__field:focus {
  border-color: #1c1917;
  background: #fff;
  outline: none;
}
</style>
