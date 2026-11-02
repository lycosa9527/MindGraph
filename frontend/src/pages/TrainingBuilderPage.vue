<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import TrainingBuilderHeader from '@/components/training/TrainingBuilderHeader.vue'
import TrainingCourseGrid from '@/components/training/TrainingCourseGrid.vue'
import { useLanguage, useNotifications } from '@/composables'
import { mergeSavedCourseCard } from '@/composables/training/trainingCourseTitle'
import type { TrainingCourse } from '@/types/training'
import { createTrainingCourse, fetchTrainingCourses } from '@/utils/trainingApi'

const { t } = useLanguage()
const notify = useNotifications()
const router = useRouter()
const courses = ref<TrainingCourse[]>([])
const busy = ref(false)
const loading = ref(true)

async function load(): Promise<void> {
  try {
    courses.value = await fetchTrainingCourses()
  } finally {
    loading.value = false
  }
}

async function createCourse(): Promise<void> {
  busy.value = true
  try {
    const created = await createTrainingCourse()
    await router.push({ name: 'TrainingBuilderEditor', params: { courseId: created.id } })
  } catch {
    notify.errorKey('training.builder.createFailed')
  } finally {
    busy.value = false
  }
}

function openCourse(course: TrainingCourse): void {
  void router.push({ name: 'TrainingBuilderEditor', params: { courseId: course.id } })
}

function onCourseRenamed(saved: TrainingCourse): void {
  courses.value = courses.value.map((row) =>
    row.id === saved.id ? mergeSavedCourseCard(row, saved) : row
  )
}

function onCourseDeleted(courseId: string): void {
  courses.value = courses.value.filter((row) => row.id !== courseId)
}

onMounted(() => {
  void load()
})
</script>

<template>
  <div class="training-page">
    <TrainingBuilderHeader
      :current="t('training.builder')"
      show-new
      :busy="busy"
      @create="createCourse"
    />
    <div class="training-page__body">
      <p
        v-if="loading"
        class="training-page__hint"
      >
        <I18nText k="training.catalogLoading" />
      </p>
      <p
        v-else-if="!courses.length"
        class="training-page__hint"
      >
        <I18nText k="training.builder.empty" />
      </p>
      <TrainingCourseGrid
        :courses="courses"
        @select="openCourse"
        @renamed="onCourseRenamed"
        @deleted="onCourseDeleted"
      />
    </div>
  </div>
</template>

<style scoped>
.training-page {
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  background: #fafaf9;
}
.training-page__body {
  flex: 1;
  overflow: auto;
  padding: 1.25rem 1.5rem 2rem;
}
.training-page__hint {
  max-width: 56rem;
  margin: 0 auto 1.25rem;
  color: #78716c;
  font-size: 0.85rem;
}
</style>
