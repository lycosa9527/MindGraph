<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useLanguage } from '@/composables'
import { applyTrainingNavigate } from '@/composables/training/applyTrainingSnapshot'
import { useTrainingHeartbeat } from '@/composables/training/useTrainingHeartbeat'
import { useAuthStore } from '@/stores/auth'
import { useTrainingStore } from '@/stores/training'
import type { TrainingRosterRow, TrainingRosterSummary } from '@/types/training'
import { fetchTrainingRoster, fetchTrainingRosterSummary } from '@/utils/trainingApi'
import {
  TRAINING_RAIL_PAGE_SIZE,
  isTrainingRailVisible,
  windowedRosterRows,
} from '@/utils/trainingClient'

const { t } = useLanguage()
const training = useTrainingStore()
const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()

const rows = ref<TrainingRosterRow[]>([])
const total = ref(0)
const summary = ref<TrainingRosterSummary>({ online: 0, generating: 0, done: 0 })
const loading = ref(false)

const visible = computed(
  () =>
    isTrainingRailVisible(authStore.isPlatformLevel, training.isActive) &&
    Boolean(training.snapshot.session_id && training.snapshot.org_id)
)
const windowed = computed(() => windowedRosterRows(rows.value))
const overflowCount = computed(() => Math.max(total.value - windowed.value.length, 0))
const canLoadMore = computed(() => rows.value.length < total.value)

useTrainingHeartbeat(() => visible.value)

async function reload(): Promise<void> {
  const snap = training.snapshot
  if (!visible.value || !snap.session_id || snap.org_id == null) return
  loading.value = true
  try {
    const [list, counts] = await Promise.all([
      fetchTrainingRoster(snap.session_id, snap.org_id, 0),
      fetchTrainingRosterSummary(snap.session_id, snap.org_id),
    ])
    rows.value = list.items
    total.value = list.total
    summary.value = counts
  } finally {
    loading.value = false
  }
}

async function loadMore(): Promise<void> {
  const snap = training.snapshot
  if (!visible.value || !snap.session_id || snap.org_id == null || loading.value) return
  loading.value = true
  try {
    const list = await fetchTrainingRoster(
      snap.session_id,
      snap.org_id,
      rows.value.length,
      TRAINING_RAIL_PAGE_SIZE
    )
    rows.value = [...rows.value, ...list.items]
    total.value = list.total
  } finally {
    loading.value = false
  }
}

watch(
  () => [training.snapshot.session_id, training.snapshot.seq, training.activityTick, visible.value],
  () => {
    void reload()
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
      <p>{{ summary.online }} · {{ summary.generating }} / {{ summary.done }}</p>
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
      @click="loadMore"
    >
      {{ t('training.loadMore') }}
    </button>
    <p
      v-if="!loading && !rows.length"
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
