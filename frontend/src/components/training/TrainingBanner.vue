<script setup lang="ts">
import { computed } from 'vue'

import { useLanguage } from '@/composables'
import { teachersSeeTrainingBanner } from '@/composables/training/applyTrainingSnapshot'
import { requestTrainingChipSelected } from '@/composables/training/trainingCommands'
import { useAuthStore } from '@/stores/auth'
import { useTrainingStore } from '@/stores/training'
import type { TrainingTopicOption } from '@/types/training'

const { t } = useLanguage()
const training = useTrainingStore()
const authStore = useAuthStore()

const visible = computed(
  () => teachersSeeTrainingBanner(training.snapshot) && !authStore.isPlatformLevel
)
const typeLabel = computed(() => training.snapshot.diagram_type || '')
const title = computed(() => {
  if (training.isPaused) return t('training.bannerPaused')
  if (training.isFree) return t('training.bannerFree')
  return t('training.bannerLive', { type: typeLabel.value })
})

function pick(option: TrainingTopicOption): void {
  if (!training.isLive) return
  requestTrainingChipSelected(option)
}
</script>

<template>
  <div
    v-if="visible"
    class="training-banner"
    role="status"
  >
    <p class="training-banner__title">{{ title }}</p>
    <div
      v-if="training.isLive && training.snapshot.topic_options.length"
      class="training-banner__chips"
    >
      <button
        v-for="option in training.snapshot.topic_options"
        :key="option.id"
        type="button"
        class="training-banner__chip"
        @click="pick(option)"
      >
        {{ option.label }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.training-banner {
  position: fixed;
  top: 0.75rem;
  left: 50%;
  z-index: 40;
  max-width: min(36rem, calc(100vw - 2rem));
  transform: translateX(-50%);
  padding: 0.65rem 0.9rem;
  border-radius: 0.75rem;
  background: var(--el-bg-color-overlay, #fff);
  box-shadow: 0 8px 24px rgb(0 0 0 / 12%);
}
.training-banner__title {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 600;
}
.training-banner__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-top: 0.45rem;
}
.training-banner__chip {
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 999px;
  background: transparent;
  padding: 0.2rem 0.7rem;
  cursor: pointer;
}
</style>
