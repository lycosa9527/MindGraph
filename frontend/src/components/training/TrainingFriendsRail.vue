<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useLanguage } from '@/composables'
import { applyTrainingNavigate } from '@/composables/training/applyTrainingSnapshot'
import { useTrainingHeartbeat } from '@/composables/training/useTrainingHeartbeat'
import { useAuthStore } from '@/stores/auth'
import { useTrainingStore } from '@/stores/training'
import type { TrainingRosterRow } from '@/types/training'
import { isTrainingRailVisible, windowedRosterRows } from '@/utils/trainingClient'

const { t } = useLanguage()
const training = useTrainingStore()
const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()

const visible = computed(
  () =>
    isTrainingRailVisible(authStore.isPlatformLevel, training.isActive) &&
    Boolean(training.snapshot.session_id && training.snapshot.org_id)
)
const windowed = computed(() => windowedRosterRows(training.rosterRows))
const overflowCount = computed(() => Math.max(training.rosterTotal - windowed.value.length, 0))
const canLoadMore = computed(() => training.rosterRows.length < training.rosterTotal)

useTrainingHeartbeat(() => visible.value)

watch(
  () => [training.snapshot.session_id, visible.value],
  () => {
    if (visible.value) void training.fetchRoster()
  },
  { immediate: true }
)

function statusLabel(row: TrainingRosterRow): string {
  if (row.generate_state === 'generating') return t('training.statusGenerating')
  if (row.generate_state === 'done') return t('training.statusDone')
  return t('training.statusIdle')
}

async function jump(row: TrainingRosterRow): Promise<void> {
  const type = row.diagram_type || training.snapshot.diagram_type
  if (!type) return
  if (row.option_label) {
    training.setPendingJump({
      id: row.option_id || `jump-${row.user_id}`,
      label: row.option_label,
    })
  }
  await applyTrainingNavigate(router, route.path, {
    ...training.snapshot,
    diagram_type: type,
    seq: training.snapshot.seq,
    state: 'live',
  })
}
</script>

<template>
  <aside
    v-if="visible"
    class="training-rail"
    :aria-label="t('training.friends')"
  >
    <header class="training-rail__head">
      <h2>{{ t('training.friends') }}</h2>
      <p>{{ training.rosterSummary.online }} · {{ training.rosterSummary.generating }} / {{ training.rosterSummary.done }}</p>
    </header>
    <ul class="training-rail__list">
      <li
        v-for="row in windowed"
        :key="row.user_id"
      >
        <button
          type="button"
          class="training-rail__row"
          :title="t('training.jump')"
          @click="jump(row)"
        >
          <span class="training-rail__name">{{ row.name || row.user_id }}</span>
          <span class="training-rail__meta">
            {{ row.option_label || row.diagram_type || '—' }} · {{ statusLabel(row) }}
          </span>
        </button>
      </li>
    </ul>
    <p
      v-if="overflowCount"
      class="training-rail__empty"
    >
      {{ t('training.moreTeachers', { n: overflowCount }) }}
    </p>
    <button
      v-if="canLoadMore"
      type="button"
      class="training-rail__more"
      @click="training.fetchRoster(true)"
    >
      {{ t('training.loadMore') }}
    </button>
    <p
      v-if="!training.rosterLoading && !training.rosterRows.length"
      class="training-rail__empty"
    >
      {{ t('training.noTeachersOnline') }}
    </p>
  </aside>
</template>

<style scoped>
.training-rail {
  position: fixed;
  top: 4.5rem;
  right: 0.75rem;
  z-index: 35;
  width: 16rem;
  max-height: calc(100vh - 6rem);
  overflow: auto;
  padding: 0.75rem;
  border-radius: 0.75rem;
  background: var(--el-bg-color-overlay, #fff);
  box-shadow: 0 8px 24px rgb(0 0 0 / 10%);
}
.training-rail__head h2 {
  margin: 0;
  font-size: 0.95rem;
}
.training-rail__head p,
.training-rail__empty,
.training-rail__meta {
  margin: 0.2rem 0 0;
  color: var(--el-text-color-secondary, #909399);
  font-size: 0.75rem;
}
.training-rail__list {
  list-style: none;
  margin: 0.5rem 0 0;
  padding: 0;
}
.training-rail__row {
  display: flex;
  width: 100%;
  flex-direction: column;
  align-items: flex-start;
  margin-bottom: 0.35rem;
  border: 0;
  background: transparent;
  cursor: pointer;
  text-align: left;
}
.training-rail__name {
  font-size: 0.85rem;
  font-weight: 600;
}
.training-rail__more {
  margin-top: 0.45rem;
  border: 1px solid var(--el-border-color, #dcdfe6);
  border-radius: 0.4rem;
  background: transparent;
  padding: 0.2rem 0.5rem;
  cursor: pointer;
}
</style>
