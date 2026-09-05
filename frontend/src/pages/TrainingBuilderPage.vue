<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import TrainingBuilderHeader from '@/components/training/TrainingBuilderHeader.vue'
import { useLanguage, useNotifications } from '@/composables'
import type { TrainingCourse } from '@/types/training'
import { createTrainingCourse, fetchTrainingCourses } from '@/utils/trainingApi'

const { t } = useLanguage()
const notify = useNotifications()
const router = useRouter()
const courses = ref<TrainingCourse[]>([])
const busy = ref(false)

async function load(): Promise<void> {
  courses.value = await fetchTrainingCourses()
}

async function createCourse(): Promise<void> {
  busy.value = true
  try {
    const created = await createTrainingCourse()
    await router.push({ name: 'TrainingBuilderEditor', params: { courseId: created.id } })
  } catch {
    notify.error(t('training.startFailed'))
  } finally {
    busy.value = false
  }
}

function openCourse(course: TrainingCourse): void {
  void router.push({ name: 'TrainingBuilderEditor', params: { courseId: course.id } })
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
        v-if="!courses.length"
        class="training-page__hint"
      >
        {{ t('training.builder.empty') }}
      </p>
      <div class="builder-grid">
        <button
          v-for="course in courses"
          :key="course.id"
          type="button"
          class="builder-card"
          @click="openCourse(course)"
        >
          <img
            v-if="course.cover_url"
            class="builder-card__cover"
            :src="course.cover_url"
            alt=""
          >
          <div
            v-else
            class="builder-card__cover builder-card__cover--empty"
          />
          <h3>{{ course.title }}</h3>
          <p>{{ course.description }}</p>
        </button>
      </div>
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
.builder-grid {
  display: grid;
  max-width: 56rem;
  margin: 0 auto;
  grid-template-columns: repeat(auto-fill, minmax(14rem, 1fr));
  gap: 1.25rem;
}
.builder-card {
  display: flex;
  flex-direction: column;
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
}
.builder-card__cover {
  height: 8rem;
  width: 100%;
  border-radius: 0.75rem;
  object-fit: cover;
  background: #0d9488;
}
.builder-card__cover--empty {
  background: linear-gradient(135deg, #0d9488, #0f766e);
}
.builder-card h3 {
  margin: 0.75rem 0 0.25rem;
  font-size: 0.95rem;
  color: #1c1917;
}
.builder-card p {
  margin: 0;
  color: #78716c;
  font-size: 0.8rem;
}
</style>
