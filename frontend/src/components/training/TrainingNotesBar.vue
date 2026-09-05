<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import { useLanguage } from '@/composables'
import { canSeeTrainingSpeakerNotes } from '@/composables/training/applyTrainingSnapshot'
import { useAuthStore } from '@/stores/auth'
import { useTrainingStore } from '@/stores/training'

const { t } = useLanguage()
const authStore = useAuthStore()
const training = useTrainingStore()
const route = useRoute()

const text = computed(() => (training.snapshot.step?.notes || '').trim())
const padClear = computed(() => {
  const mine = Number(authStore.user?.id)
  return (
    training.isActive &&
    Boolean(training.snapshot.course_id) &&
    mine > 0 &&
    Number(training.snapshot.instructor_id) === mine
  )
})
const visible = computed(() => {
  if (route.path.startsWith('/training/builder')) return false
  if (!text.value) return false
  return canSeeTrainingSpeakerNotes(training.snapshot, Number(authStore.user?.id) || null)
})
</script>

<template>
  <aside
    v-if="visible"
    class="training-notes"
    :class="{ 'training-notes--pad': padClear }"
    :aria-label="t('training.builder.notes')"
  >
    <p class="training-notes__kicker">{{ t('training.builder.notes') }}</p>
    <p class="training-notes__body">{{ text }}</p>
  </aside>
</template>

<style scoped>
.training-notes {
  position: fixed;
  right: 1rem;
  bottom: 1rem;
  left: 1rem;
  z-index: 4250;
  max-width: 42rem;
  margin: 0 auto;
  border: 1px solid #e7e5e4;
  background: rgb(255 255 255 / 0.96);
  padding: 0.7rem 0.9rem;
  box-shadow: 0 8px 24px rgb(28 25 23 / 0.08);
}
.training-notes--pad {
  right: 11.5rem;
}
@media (max-height: 780px) {
  .training-notes--pad {
    right: 1rem;
    bottom: 7.25rem;
  }
}
.training-notes__kicker {
  margin: 0 0 0.25rem;
  color: #78716c;
  font-size: 0.7rem;
  font-weight: 650;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.training-notes__body {
  margin: 0;
  color: #1c1917;
  font-size: 0.88rem;
  line-height: 1.45;
  white-space: pre-wrap;
}
</style>
