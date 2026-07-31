<script setup lang="ts">
/**
 * MaiteWorkspace — mode nav, recent practice, and mode content slot.
 */
import { computed, onMounted } from 'vue'

import MaiteDemoView from '@/components/maite/demo/MaiteDemoView.vue'
import MaiteInquiryView from '@/components/maite/inquiry/MaiteInquiryView.vue'
import MaiteLearningMapView from '@/components/maite/map/MaiteLearningMapView.vue'
import MaiteModeNav from '@/components/maite/MaiteModeNav.vue'
import MaiteRecentPractice from '@/components/maite/MaiteRecentPractice.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import {
  useMaiteOcrUpload,
  useMaitePracticeHistory,
  useMaiteWorkspace,
} from '@/composables/maite'

const { t } = useLanguage()
const { mode } = useMaiteWorkspace()
const { loadSessions } = useMaitePracticeHistory()
useMaiteOcrUpload()

onMounted(() => {
  void loadSessions()
})

const activeView = computed(() => {
  if (mode.value === 'inquiry') {
    return MaiteInquiryView
  }
  if (mode.value === 'map') {
    return MaiteLearningMapView
  }
  return MaiteDemoView
})
</script>

<template>
  <div class="maite-workspace">
    <header class="maite-workspace__header">
      <div>
        <h1 class="maite-workspace__title">{{ t('maite.title') }}</h1>
        <p class="maite-workspace__subtitle">{{ t('maite.subtitle') }}</p>
      </div>
      <MaiteModeNav />
    </header>

    <div class="maite-workspace__body">
      <MaiteRecentPractice class="maite-workspace__sidebar" />
      <main class="maite-workspace__content">
        <component :is="activeView" />
      </main>
    </div>
  </div>
</template>

<style scoped>
.maite-workspace {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--el-bg-color-page, #fafaf9);
}

.maite-workspace__header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--el-border-color-lighter, #f5f5f4);
  background: #fff;
}

.maite-workspace__title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--el-text-color-primary, #1c1917);
}

.maite-workspace__subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary, #78716c);
}

.maite-workspace__body {
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 16px;
  flex: 1;
  min-height: 0;
  padding: 16px 20px;
  overflow: hidden;
}

.maite-workspace__sidebar {
  overflow-y: auto;
}

.maite-workspace__content {
  overflow-y: auto;
  min-height: 0;
}

@media (max-width: 900px) {
  .maite-workspace__body {
    grid-template-columns: 1fr;
  }

  .maite-workspace__sidebar {
    order: 2;
  }
}
</style>
