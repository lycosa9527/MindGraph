<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import TrainingSlidePreview from '@/components/training/TrainingSlidePreview.vue'
import { useLanguage, useNotifications } from '@/composables'
import { applyTrainingUiLock, releaseTrainingUiLock } from '@/composables/training/trainingUiLock'
import type { TrainingCourse, TrainingCourseStep } from '@/types/training'
import {
  clearRequiredTrainingCache,
  noteRequiredTrainingFinished,
} from '@/utils/requiredTrainingGate'
import { completeRequiredTraining, fetchRequiredTraining } from '@/utils/trainingVodApi'

const router = useRouter()
const { t } = useLanguage()
const notify = useNotifications()
const course = ref<TrainingCourse | null>(null)
const index = ref(0)
const finishing = ref(false)

const steps = computed(() => course.value?.steps || [])
const step = computed<TrainingCourseStep | null>(() => steps.value[index.value] || null)
const last = computed(() => index.value >= steps.value.length - 1)

watch(
  () => step.value?.ui_lock ?? null,
  (key) => {
    applyTrainingUiLock(key)
  }
)

onUnmounted(() => {
  releaseTrainingUiLock()
})

function onNext(): void {
  if (last.value) {
    void finish()
    return
  }
  index.value += 1
}

function leave(): void {
  clearRequiredTrainingCache()
  void router.replace({ name: 'MindMate' })
}

async function finish(): Promise<void> {
  const id = course.value?.id
  if (!id || finishing.value) return
  finishing.value = true
  try {
    await completeRequiredTraining(id)
    noteRequiredTrainingFinished(id)
    const body = await fetchRequiredTraining()
    const next = body.course
    if (next?.id && next.id !== id && next.steps?.length) {
      course.value = next
      index.value = 0
      finishing.value = false
      return
    }
    leave()
  } catch {
    notify.error(t('training.required.doneFailed'))
    finishing.value = false
  }
}

onMounted(async () => {
  try {
    const body = await fetchRequiredTraining()
    if (!body.course?.steps?.length) {
      leave()
      return
    }
    course.value = body.course
  } catch {
    leave()
  }
})
</script>

<template>
  <section
    v-if="course && step"
    class="required-course"
  >
    <header class="required-course__bar">
      <h1>
        <template v-if="course.title">{{ course.title }}</template
        ><I18nText
          v-else
          k="training.required.title"
        />
      </h1>
      <p>
        <I18nText
          k="training.required.progress"
          :params="{ n: index + 1, total: steps.length }"
        />
      </p>
    </header>
    <div class="required-course__stage">
      <TrainingSlidePreview
        :step="step"
        :index="index"
        interactive
        @next="onNext"
      />
    </div>
    <p
      v-if="step.notes"
      class="required-course__notes"
    >
      {{ step.notes }}
    </p>
    <footer class="required-course__actions">
      <button
        type="button"
        :disabled="index === 0"
        @click="index -= 1"
      >
        <I18nText k="training.required.prev" />
      </button>
      <button
        v-if="!last"
        type="button"
        @click="index += 1"
      >
        <I18nText k="training.required.next" />
      </button>
      <button
        v-else
        type="button"
        :disabled="finishing"
        @click="finish"
      >
        <I18nText k="training.required.finish" />
      </button>
    </footer>
  </section>
</template>

<style scoped>
.required-course {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-height: calc(100vh - 4rem);
  padding: 1.25rem;
}
.required-course__bar h1 {
  margin: 0;
  font-size: 1.25rem;
}
.required-course__bar p {
  margin: 0.25rem 0 0;
  color: #57534e;
  font-size: 0.85rem;
}
.required-course__stage {
  position: relative;
}
.required-course__notes {
  margin: 0;
  color: #44403c;
  line-height: 1.5;
}
.required-course__actions {
  display: flex;
  gap: 0.5rem;
}
.required-course__actions button {
  border: none;
  border-radius: 0.375rem;
  padding: 0.45rem 0.9rem;
  background: #1c1917;
  color: #fff;
}
.required-course__actions button:disabled {
  opacity: 0.45;
}
</style>
