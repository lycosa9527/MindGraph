<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useLanguage } from '@/composables'
import { applyTrainingNavigate } from '@/composables/training/applyTrainingSnapshot'
import {
  trainingFriendJumpSnapshot,
  trainingFriendLine,
  trainingFriendName,
  trainingFriendPageLabel,
  trainingFriendTopic,
} from '@/composables/training/trainingFriendLine'
import { useTrainingHeartbeat } from '@/composables/training/useTrainingHeartbeat'
import { useAuthStore } from '@/stores/auth'
import { useTrainingStore } from '@/stores/training'
import type { TrainingRosterRow } from '@/types/training'
import {
  isTrainingOwnerHeartbeat,
  isTrainingRailVisible,
  shouldHideTrainingDesktopChrome,
  TRAINING_RAIL_VISIBLE_ROWS,
} from '@/utils/trainingClient'

const { t } = useLanguage()
const training = useTrainingStore()
const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()

const visible = computed(
  () =>
    !shouldHideTrainingDesktopChrome(route.path) &&
    isTrainingRailVisible(authStore.isPlatformLevel, training.isActive) &&
    Boolean(training.snapshot.session_id && training.snapshot.org_id)
)
const canLoadMore = computed(() => training.rosterRows.length < training.rosterTotal)
const listStyle = computed(() => ({
  '--rail-visible-rows': String(TRAINING_RAIL_VISIBLE_ROWS),
}))

useTrainingHeartbeat(() =>
  isTrainingOwnerHeartbeat(
    authStore.isPlatformLevel,
    training.isActive,
    Number(authStore.user?.id),
    training.snapshot.instructor_id
  )
)

watch(
  () => [training.snapshot.session_id, visible.value],
  () => {
    if (visible.value) void training.fetchRoster()
  },
  { immediate: true }
)

function translate(key: string): string {
  return t(key)
}

function line(row: TrainingRosterRow): string {
  return trainingFriendLine(row, translate)
}

function pageLabel(row: TrainingRosterRow): string {
  return trainingFriendPageLabel(row, translate)
}

async function jump(row: TrainingRosterRow): Promise<void> {
  const target = trainingFriendJumpSnapshot(training.snapshot, row)
  if (!target) return
  if (row.option_label) {
    training.setPendingJump({
      id: row.option_id || `jump-${row.user_id}`,
      label: row.option_label,
    })
  }
  await applyTrainingNavigate(router, route.path, target)
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
      <p>{{ training.rosterSummary.online }}</p>
    </header>
    <ul
      class="training-rail__list"
      :style="listStyle"
    >
      <li
        v-for="row in training.rosterRows"
        :key="row.user_id"
      >
        <button
          type="button"
          class="training-rail__row"
          :title="line(row)"
          @click="jump(row)"
        >
          <span
            class="training-rail__dot"
            aria-hidden="true"
          />
          <span class="training-rail__copy">
            <span class="training-rail__name">{{ trainingFriendName(row) }}</span>
            <span class="training-rail__meta">
              {{ pageLabel(row) }}
              <span class="training-rail__sep">/</span>
              {{ trainingFriendTopic(row) }}
            </span>
          </span>
        </button>
      </li>
    </ul>
    <button
      v-if="canLoadMore"
      type="button"
      class="training-rail__more"
      @click="training.fetchRoster(true)"
    >
      {{ t('training.loadMore') }}
    </button>
    <p
      v-if="training.rosterLoading && !training.rosterRows.length"
      class="training-rail__empty"
    >
      {{ t('training.rosterLoading') }}
    </p>
    <p
      v-else-if="!training.rosterLoading && !training.rosterRows.length"
      class="training-rail__empty"
    >
      {{ t('training.noTeachersOnline') }}
    </p>
  </aside>
</template>

<style scoped>
.training-rail {
  --rail-row-height: 2.7rem;
  position: fixed;
  top: 4.5rem;
  right: 0.75rem;
  z-index: 35;
  display: flex;
  width: 18rem;
  max-height: calc(100vh - 6rem);
  flex-direction: column;
  overflow: hidden;
  padding: 0.7rem 0.65rem;
  border: 1px solid #e7e5e4;
  border-radius: 0.75rem;
  background: #fff;
  box-shadow: 0 8px 24px rgb(28 25 23 / 0.08);
}
@media (max-width: 768px) {
  .training-rail {
    top: auto;
    right: 0.5rem;
    bottom: 5.5rem;
    width: min(18rem, calc(100vw - 1rem));
    max-height: 40vh;
  }
}
.training-rail__head {
  display: flex;
  flex-shrink: 0;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0 0.25rem 0.45rem;
  border-bottom: 1px solid #f5f5f4;
}
.training-rail__head h2 {
  margin: 0;
  color: #57534e;
  font-size: 0.7rem;
  font-weight: 650;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.training-rail__head p,
.training-rail__empty {
  margin: 0;
  color: #a8a29e;
  font-size: 0.7rem;
}
.training-rail__empty {
  padding: 0.65rem 0.25rem 0.15rem;
  text-align: center;
}
.training-rail__list {
  list-style: none;
  min-height: 0;
  max-height: calc(var(--rail-row-height) * var(--rail-visible-rows, 15));
  margin: 0.35rem 0 0;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 0;
  scrollbar-width: thin;
}
.training-rail__row {
  display: flex;
  box-sizing: border-box;
  width: 100%;
  min-height: var(--rail-row-height);
  align-items: flex-start;
  gap: 0.55rem;
  margin: 0;
  border: 0;
  border-radius: 0.5rem;
  background: transparent;
  padding: 0.35rem 0.4rem;
  cursor: pointer;
  text-align: left;
}
.training-rail__row:hover {
  background: #f5f5f4;
}
.training-rail__dot {
  flex-shrink: 0;
  width: 0.5rem;
  height: 0.5rem;
  margin-top: 0.35rem;
  border-radius: 999px;
  background: #22c55e;
  box-shadow: 0 0 0 2px rgb(34 197 94 / 0.18);
}
.training-rail__copy {
  min-width: 0;
  flex: 1;
}
.training-rail__name {
  display: block;
  overflow: hidden;
  color: #44403c;
  font-size: 0.8125rem;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.training-rail__meta {
  display: block;
  overflow: hidden;
  margin-top: 0.1rem;
  color: #78716c;
  font-size: 0.7rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.training-rail__sep {
  color: #a8a29e;
}
.training-rail__more {
  flex-shrink: 0;
  margin-top: 0.45rem;
  border: 1px solid #e7e5e4;
  border-radius: 0.4rem;
  background: #fafaf9;
  padding: 0.25rem 0.5rem;
  color: #57534e;
  cursor: pointer;
}
</style>
