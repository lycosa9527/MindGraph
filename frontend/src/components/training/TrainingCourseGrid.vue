<script setup lang="ts">
import TrainingCourseCardMenu from '@/components/training/TrainingCourseCardMenu.vue'
import type { TrainingCourse } from '@/types/training'

defineProps<{
  courses: TrainingCourse[]
  activeCourseId?: string | null
}>()

const emit = defineEmits<{
  select: [course: TrainingCourse]
  renamed: [course: TrainingCourse]
  deleted: [courseId: string]
}>()
</script>

<template>
  <section class="training-courses">
    <div class="training-courses__grid">
      <article
        v-for="course in courses"
        :key="course.id"
        class="training-course-card"
        :class="{ 'is-active': activeCourseId === course.id }"
      >
        <div class="training-course-card__thumb">
          <button
            type="button"
            class="training-course-card__hit"
            tabindex="-1"
            aria-hidden="true"
            @click="emit('select', course)"
          />
          <img
            v-if="course.cover_url"
            class="training-course-card__cover"
            :src="course.cover_url"
            alt=""
          />
          <TrainingCourseCardMenu
            class="training-course-card__menu"
            :course="course"
            @renamed="emit('renamed', $event)"
            @deleted="emit('deleted', $event)"
          />
        </div>
        <button
          type="button"
          class="training-course-card__body"
          @click="emit('select', course)"
        >
          <h3>
            {{ course.title }}
            <span
              v-if="course.is_system"
              class="training-course-card__badge"
            >
              <I18nText k="training.builder.systemBadge" />
            </span>
          </h3>
          <p>{{ course.description }}</p>
        </button>
      </article>
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
  text-align: left;
}
.training-course-card__thumb {
  position: relative;
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
.training-course-card__hit {
  position: absolute;
  inset: 0;
  z-index: 0;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
}
.training-course-card__cover {
  width: 100%;
  height: 100%;
  object-fit: cover;
  pointer-events: none;
}
.training-course-card__menu {
  position: absolute;
  right: 0.4rem;
  bottom: 0.4rem;
  z-index: 1;
}
.training-course-card__body {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.training-course-card h3 {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: #1c1917;
}
.training-course-card__badge {
  border: 1px solid #d6d3d1;
  border-radius: 999px;
  padding: 0.05rem 0.4rem;
  color: #78716c;
  font-size: 0.68rem;
  font-weight: 600;
}
.training-course-card p {
  margin: 0.25rem 0 0;
  font-size: 0.8rem;
  color: #78716c;
}
</style>
