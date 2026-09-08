<script setup lang="ts">
import type { TrainingCourse } from '@/types/training'

defineProps<{
  courses: TrainingCourse[]
  activeCourseId: string | null
}>()

const emit = defineEmits<{
  select: [course: TrainingCourse]
}>()
</script>

<template>
  <section class="training-courses">
    <div class="training-courses__grid">
      <button
        v-for="course in courses"
        :key="course.id"
        type="button"
        class="training-course-card"
        :class="{ 'is-active': activeCourseId === course.id }"
        @click="emit('select', course)"
      >
        <div
          class="training-course-card__thumb"
          aria-hidden="true"
        >
          <img
            v-if="course.cover_url"
            class="training-course-card__cover"
            :src="course.cover_url"
            alt=""
          >
        </div>
        <h3>{{ course.title }}</h3>
        <p>{{ course.description }}</p>
      </button>
    </div>
  </section>
</template>

<style scoped>
.training-courses {
  max-width: 56rem;
  margin: 0 auto;
}
.training-courses__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(14rem, 1fr));
  gap: 1.25rem;
}
.training-course-card {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
}
.training-course-card__thumb {
  display: flex;
  aspect-ratio: 16 / 10;
  align-items: center;
  justify-content: center;
  margin-bottom: 0.7rem;
  overflow: hidden;
  border-radius: 0.75rem;
  background: linear-gradient(135deg, #0d9488, #0f766e);
}
.training-course-card.is-active .training-course-card__thumb {
  box-shadow: 0 0 0 2px #1c1917;
}
.training-course-card__cover {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.training-course-card h3 {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: #1c1917;
}
.training-course-card p {
  margin: 0.25rem 0 0;
  font-size: 0.8rem;
  color: #78716c;
}
</style>
