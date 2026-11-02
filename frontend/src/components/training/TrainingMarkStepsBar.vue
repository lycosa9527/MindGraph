<script setup lang="ts">
import { computed } from 'vue'

import { ElButton } from 'element-plus'

import { Minus, Plus } from '@lucide/vue'

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
    labelKey: 'training.builder.markStep',
    labelParams: { n: index + 1 },
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
  <div class="builder-steps">
    <AdminSwissSegmented
      v-model="current"
      fit
      :options="options"
      :aria-label="t('training.builder.groupSteps')"
    />
    <ElButton
      size="small"
      class="admin-swiss-btn"
      :disabled="count >= TRAINING_MARK_STEPS_MAX"
      :aria-label="t('training.builder.markStepAdd')"
      @click="onAdd"
    >
      <Plus
        class="builder-steps__icon"
        aria-hidden="true"
      />
    </ElButton>
    <ElButton
      size="small"
      class="admin-swiss-btn"
      :disabled="current <= TRAINING_MARK_STEPS_MIN"
      :aria-label="t('training.builder.markStepRemove')"
      @click="onRemove"
    >
      <Minus
        class="builder-steps__icon"
        aria-hidden="true"
      />
    </ElButton>
  </div>
</template>

<style scoped src="@/styles/admin-swiss-controls.css"></style>
<style scoped>
.builder-steps {
  display: inline-flex;
  flex-wrap: nowrap;
  align-items: center;
  gap: 0.5rem;
}
.builder-steps :deep(.admin-swiss-segment) {
  white-space: nowrap;
}
.builder-steps__icon {
  width: 15px;
  height: 15px;
}
</style>
