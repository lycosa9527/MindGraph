<script setup lang="ts">
import { ref, watch } from 'vue'

import { useLanguage } from '@/composables'
import type { TrainingCourseStep } from '@/types/training'

const NOTES_MAX = 4000

const props = defineProps<{
  step: TrainingCourseStep
  readonly?: boolean
}>()

const { t } = useLanguage()
const open = ref(false)

watch(
  () => props.step.id,
  () => {
    open.value = Boolean((props.step.notes || '').trim())
  },
  { immediate: true }
)

function toggle(): void {
  open.value = !open.value
}

function onInput(event: Event): void {
  const field = event.target
  if (!(field instanceof HTMLTextAreaElement) || props.readonly) return
  props.step.notes = field.value
}
</script>

<template>
  <section class="builder-notes">
    <button
      type="button"
      class="builder-notes__toggle"
      :aria-expanded="open"
      :aria-label="t('training.builder.notes')"
      @click="toggle"
    >
      <span
        class="builder-notes__chevron"
        :class="{ 'is-open': open }"
      />
      <span><I18nText k="training.builder.notes" /></span>
    </button>
    <textarea
      v-show="open"
      class="builder-notes__field"
      :value="step.notes || ''"
      :maxlength="NOTES_MAX"
      :placeholder="t('training.builder.notesHint')"
      :readonly="readonly"
      rows="4"
      @input="onInput"
    />
  </section>
</template>

<style scoped>
.builder-notes {
  display: flex;
  flex-shrink: 0;
  flex-direction: column;
  gap: 0.4rem;
  border: 1px solid #e7e5e4;
  background: #fff;
  padding: 0.45rem 0.85rem;
}
.builder-notes__toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  width: 100%;
  border: none;
  background: transparent;
  padding: 0.15rem 0;
  color: #1c1917;
  font-size: 0.78rem;
  font-weight: 650;
  text-align: left;
  cursor: pointer;
}
.builder-notes__chevron {
  width: 0.4rem;
  height: 0.4rem;
  border-right: 1.5px solid #44403c;
  border-bottom: 1.5px solid #44403c;
  transform: rotate(-45deg);
}
.builder-notes__chevron.is-open {
  transform: rotate(45deg);
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
