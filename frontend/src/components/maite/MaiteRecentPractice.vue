<script setup lang="ts">
/**
 * MaiteRecentPractice — recent inquiry sessions sidebar list.
 */
import { onMounted } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useMaitePracticeHistory } from '@/composables/maite/useMaitePracticeHistory'
import { useMaiteStore } from '@/stores/maite'
import { eventBus } from '@/composables/core/useEventBus'

const { t } = useLanguage()
const store = useMaiteStore()
const { recentPractice, loadSessions, loading } = useMaitePracticeHistory()

onMounted(() => {
  void loadSessions()
})

function openSession(sessionId: number): void {
  store.setActiveSessionId(sessionId)
  store.setMode('inquiry')
  eventBus.emit('maite:session_opened', { sessionId, mode: 'inquiry' })
  eventBus.emit('maite:mode_changed', { mode: 'inquiry' })
}
</script>

<template>
  <aside class="maite-recent-practice">
    <h3 class="maite-recent-practice__title">{{ t('maite.practice.title') }}</h3>
    <p v-if="loading" class="maite-recent-practice__empty">{{ t('maite.practice.loading') }}</p>
    <p v-else-if="recentPractice.length === 0" class="maite-recent-practice__empty">
      {{ t('maite.practice.empty') }}
    </p>
    <ul v-else class="maite-recent-practice__list">
      <li
        v-for="item in recentPractice"
        :key="item.id"
        class="maite-recent-practice__item"
        :class="{ 'maite-recent-practice__item--active': store.activeSessionId === item.id }"
        @click="openSession(item.id)"
      >
        <span class="maite-recent-practice__name">
          {{ item.title || t('maite.practice.untitled', { id: item.id }) }}
        </span>
        <span class="maite-recent-practice__stage">{{ t(`maite.stage.${item.current_stage}`) }}</span>
      </li>
    </ul>
  </aside>
</template>

<style scoped>
.maite-recent-practice {
  padding: 12px;
  border-radius: 10px;
  background: var(--el-fill-color-lighter, #fafaf9);
}

.maite-recent-practice__title {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary, #1c1917);
}

.maite-recent-practice__empty {
  margin: 0;
  font-size: 12px;
  color: var(--el-text-color-secondary, #78716c);
}

.maite-recent-practice__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.maite-recent-practice__item {
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.15s;
}

.maite-recent-practice__item:hover,
.maite-recent-practice__item--active {
  background: #fff;
}

.maite-recent-practice__name {
  display: block;
  font-size: 13px;
  color: var(--el-text-color-primary, #1c1917);
}

.maite-recent-practice__stage {
  display: block;
  margin-top: 2px;
  font-size: 11px;
  color: var(--el-text-color-secondary, #78716c);
}
</style>
