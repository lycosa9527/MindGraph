<script setup lang="ts">
import { computed } from 'vue'

import TrainingBuilderFilmstrip from '@/components/training/TrainingBuilderFilmstrip.vue'
import TrainingTeacherPreview from '@/components/training/TrainingTeacherPreview.vue'
import {
  advancePlayCursor,
  canAdvancePlayCursor,
} from '@/composables/training/trainingMarkSteps'
import type { TrainingCourse } from '@/types/training'

const props = defineProps<{
  course: TrainingCourse
  index: number
}>()

const emit = defineEmits<{
  close: []
  index: [value: number]
}>()

const steps = computed(() => props.course.steps || [])
const current = computed(() => steps.value[props.index] || null)
const thumbs = computed(() =>
  steps.value.map((step) => step.thumb_url || step.asset_url || null)
)
const canPrev = computed(() => canAdvancePlayCursor(steps.value, props.index, -1))
const canNext = computed(() => canAdvancePlayCursor(steps.value, props.index, 1))

function move(delta: number): void {
  emit('index', advancePlayCursor(steps.value, props.index, delta))
}
</script>

<template>
  <div
    class="landing-preview"
    role="dialog"
  >
    <TrainingBuilderFilmstrip
      :steps="steps"
      :selected="index"
      :thumbs="thumbs"
      readonly
      @select="emit('index', $event)"
    />
    <div class="landing-preview__stage">
      <TrainingTeacherPreview
        v-if="current"
        :step="current"
        :can-prev="canPrev"
        :can-next="canNext"
        :show-mode="false"
        @close="emit('close')"
        @prev="move(-1)"
        @next="move(1)"
      />
    </div>
  </div>
</template>

<style scoped>
.landing-preview {
  position: fixed;
  inset: 0;
  z-index: 80;
  display: flex;
  background: #111827;
}
.landing-preview__stage {
  position: relative;
  min-width: 0;
  flex: 1;
}
</style>
