<script setup lang="ts">
/**
 * Full-page step-through of a course. The slide is the real page, not a preview dialog.
 */
import { computed, ref, watch } from 'vue'

import TrainingPageLiveFrame from '@/components/training/TrainingPageLiveFrame.vue'
import TrainingStepMarks from '@/components/training/TrainingStepMarks.vue'
import TrainingVodPlayer from '@/components/training/TrainingVodPlayer.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import { visibleMarkOverlays } from '@/composables/training/trainingMarkSteps'
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
const marks = computed(() => (step.value ? visibleMarkOverlays(step.value) : []))

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
  <Teleport to="body">
    <div
      v-if="visible"
      class="course-walkthrough"
      role="dialog"
      :aria-label="course?.title || t('admin.userDropdown.previewTitle')"
    >
      <header class="course-walkthrough__bar">
        <p class="course-walkthrough__title">
          <template v-if="course?.title">{{ course?.title }}</template>
          <I18nText
            v-else
            k="admin.userDropdown.previewTitle"
          />
        </p>
        <p
          v-if="step"
          class="course-walkthrough__progress"
        >
          <I18nText
            k="training.required.progress"
            :params="{ n: index + 1, total: steps.length }"
          />
        </p>
        <button
          type="button"
          class="course-walkthrough__close"
          @click="close"
        >
          <I18nText k="admin.userDropdown.previewClose" />
        </button>
      </header>
      <p
        v-if="loading"
        class="course-walkthrough__status"
      >
        <I18nText k="admin.loading" />
      </p>
      <p
        v-else-if="!course || steps.length === 0"
        class="course-walkthrough__status"
      >
        <I18nText k="admin.userDropdown.previewEmpty" />
      </p>
      <div
        v-else-if="step"
        class="course-walkthrough__stage"
      >
        <TrainingPageLiveFrame
          :page-key="step.page_key"
          :diagram-type="step.diagram_type"
          :step="step"
          interactive
        />
        <TrainingStepMarks
          :overlays="marks"
          :step="step"
          portaled
          remote-roles
        />
        <TrainingVodPlayer
          v-if="step.vod_media_id"
          class="course-walkthrough__player"
          :media-id="step.vod_media_id"
          :autoplay="Boolean(step.vod_autoplay)"
          :width="step.vod_width"
          :height="step.vod_height"
          :step-key="step.id || String(index)"
          :can-next="!last"
          @next="onNext"
        />
        <footer class="course-walkthrough__actions">
          <button
            type="button"
            :disabled="index === 0"
            @click="index -= 1"
          >
            <I18nText k="training.required.prev" />
          </button>
          <button
            type="button"
            @click="onNext"
          >
            <I18nText
              v-if="last"
              k="training.required.finish"
            />
            <I18nText
              v-else
              k="training.required.next"
            />
          </button>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.course-walkthrough {
  position: fixed;
  inset: 0;
  z-index: 1100;
  display: flex;
  flex-direction: column;
  background: #fafaf9;
}
.course-walkthrough__bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.45rem 0.85rem;
  background: #1c1917;
  color: #fafaf9;
}
.course-walkthrough__title,
.course-walkthrough__progress,
.course-walkthrough__status {
  margin: 0;
}
.course-walkthrough__title {
  font-size: 0.85rem;
  font-weight: 650;
}
.course-walkthrough__progress,
.course-walkthrough__status {
  color: #d6d3d1;
  font-size: 0.75rem;
}
.course-walkthrough__status {
  padding: 1.5rem;
}
.course-walkthrough__close {
  margin-left: auto;
  border: 0;
  border-radius: 0.25rem;
  background: transparent;
  color: #fafaf9;
  cursor: pointer;
}
.course-walkthrough__stage {
  position: relative;
  min-height: 0;
  flex: 1;
}
.course-walkthrough__player {
  position: absolute;
  left: 0.75rem;
  bottom: 3.5rem;
  z-index: 5;
}
.course-walkthrough__actions {
  position: absolute;
  right: max(1rem, env(safe-area-inset-right, 0px));
  bottom: max(1rem, env(safe-area-inset-bottom, 0px));
  z-index: 6;
  display: flex;
  gap: 0.45rem;
}
.course-walkthrough__actions button {
  border: 0;
  border-radius: 0.35rem;
  padding: 0.4rem 0.8rem;
  background: #1c1917;
  color: #fff;
  cursor: pointer;
}
.course-walkthrough__actions button:disabled {
  opacity: 0.45;
}
</style>
