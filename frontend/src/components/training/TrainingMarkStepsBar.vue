<script setup lang="ts">
import { computed } from 'vue'

import { ElButton } from 'element-plus'

import AdminSwissSegmented from '@/components/admin/swiss/AdminSwissSegmented.vue'
import { useLanguage } from '@/composables'
import {
  TRAINING_MARK_STEPS_MAX,
  TRAINING_MARK_STEPS_MIN,
  addMarkStep,
  currentMarkStep,
  markStepCount,
  removeMarkStep,
  setCurrentMarkStep,
} from '@/composables/training/trainingMarkSteps'
import type { TrainingCourseStep } from '@/types/training'

const props = defineProps<{
  step: TrainingCourseStep
}>()

const emit = defineEmits<{
  awake: []
}>()

const { t } = useLanguage()

const count = computed(() => markStepCount(props.step))
const current = computed({
  get: () => currentMarkStep(props.step),
  set: (next: number) => {
    emit('awake')
    setCurrentMarkStep(props.step, next)
  },
})
const options = computed(() =>
  Array.from({ length: count.value }, (_, index) => ({
    value: index + 1,
    label: t('training.builder.markStep', { n: index + 1 }),
  }))
)

function onAdd(): void {
  emit('awake')
  addMarkStep(props.step)
}

function onRemove(): void {
  emit('awake')
  removeMarkStep(props.step)
}
</script>

<template>
  <div class="builder-toolbar__row">
    <span class="builder-toolbar__label">{{ t('training.builder.groupSteps') }}</span>
    <AdminSwissSegmented
      v-model="current"
      :equal="count <= 4"
      :options="options"
      :ariaLabel="t('training.builder.groupSteps')"
    />
    <ElButton
      size="small"
      class="admin-swiss-btn"
      :disabled="count >= TRAINING_MARK_STEPS_MAX"
      :aria-label="t('training.builder.markStepAdd')"
      @click="onAdd"
    >
      +
    </ElButton>
    <ElButton
      size="small"
      class="admin-swiss-btn"
      :disabled="current <= TRAINING_MARK_STEPS_MIN"
      :aria-label="t('training.builder.markStepRemove')"
      @click="onRemove"
    >
      −
    </ElButton>
  </div>
</template>

<style scoped src="@/styles/admin-swiss-controls.css"></style>
<style scoped>
.builder-toolbar__row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
}
.builder-toolbar__label {
  min-width: 2.5rem;
  color: #78716c;
  font-size: 0.7rem;
  font-weight: 650;
  letter-spacing: 0.04em;
}
</style>
