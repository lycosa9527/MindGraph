<script setup lang="ts">
/**
 * Step-through of a training course, the same shape as an in-product tour.
 */
import { computed, ref, watch } from 'vue'

import TrainingSlidePreview from '@/components/training/TrainingSlidePreview.vue'
import { useLanguage } from '@/composables'
import type { TrainingCourse, TrainingCourseStep } from '@/types/training'

const visible = defineModel<boolean>({ default: false })

const props = defineProps<{
  course: TrainingCourse | null
  loading?: boolean
}>()

const { t } = useLanguage()
const index = ref(0)

const steps = computed(() => props.course?.steps || [])
const step = computed<TrainingCourseStep | null>(() => steps.value[index.value] || null)
const last = computed(() => steps.value.length > 0 && index.value >= steps.value.length - 1)

watch(
  () => props.course?.id,
  () => {
    index.value = 0
  }
)

watch(visible, (open) => {
  if (open) index.value = 0
})

function close(): void {
  visible.value = false
}

function onNext(): void {
  if (last.value) {
    close()
    return
  }
  index.value += 1
}
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="course?.title || t('admin.userDropdown.previewTitle')"
    width="min(960px, 94vw)"
    top="4vh"
    append-to-body
    destroy-on-close
    class="course-walkthrough-dialog"
  >
    <p
      v-if="loading"
      class="course-walkthrough__status"
    >
      {{ t('admin.loading') }}
    </p>
    <p
      v-else-if="!course || steps.length === 0"
      class="course-walkthrough__status"
    >
      {{ t('admin.userDropdown.previewEmpty') }}
    </p>
    <template v-else-if="step">
      <p class="course-walkthrough__progress">
        {{ t('training.required.progress', { n: index + 1, total: steps.length }) }}
      </p>
      <TrainingSlidePreview
        :step="step"
        :index="index"
        interactive
        @next="onNext"
      />
      <p
        v-if="step.notes"
        class="course-walkthrough__notes"
      >
        {{ step.notes }}
      </p>
    </template>
    <template #footer>
      <el-button @click="close">
        {{ t('admin.userDropdown.previewClose') }}
      </el-button>
      <el-button
        :disabled="!step || index === 0"
        @click="index -= 1"
      >
        {{ t('training.required.prev') }}
      </el-button>
      <el-button
        type="primary"
        :disabled="!step"
        @click="onNext"
      >
        {{ last ? t('training.required.finish') : t('training.required.next') }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.course-walkthrough__status,
.course-walkthrough__progress,
.course-walkthrough__notes {
  margin: 0 0 0.75rem;
  color: #57534e;
  font-size: 0.875rem;
  line-height: 1.5;
}
.course-walkthrough__notes {
  margin-top: 0.75rem;
  margin-bottom: 0;
  color: #44403c;
}
</style>
