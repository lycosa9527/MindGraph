<script setup lang="ts">
import { computed, watch } from 'vue'

import { useLanguage } from '@/composables'
import {
  trainingFriendName,
  trainingFriendPageLabel,
  trainingFriendTopic,
} from '@/composables/training/trainingFriendLine'
import { useTrainingStore } from '@/stores/training'
import type { TrainingRosterRow } from '@/types/training'

const { t } = useLanguage()
const training = useTrainingStore()

const canLoadMore = computed(() => training.rosterRows.length < training.rosterTotal)

watch(
  () => [training.snapshot.session_id, training.isActive],
  () => {
    if (training.isActive && training.snapshot.session_id) {
      void training.fetchRoster()
    }
  },
  { immediate: true }
)

function pageLabel(row: TrainingRosterRow): string {
  return trainingFriendPageLabel(row, (key) => t(key))
}
</script>

<template>
  <section
    class="remote-roster"
    :aria-label="t('training.friends')"
  >
    <header class="remote-roster__head">
      <h2>{{ t('training.friends') }}</h2>
      <p>{{ training.rosterSummary.online }}</p>
    </header>
    <ul class="remote-roster__list">
      <li
        v-for="row in training.rosterRows"
        :key="row.user_id"
      >
        <div class="remote-roster__row">
          <span
            class="remote-roster__dot"
            aria-hidden="true"
          />
          <span class="remote-roster__copy">
            <span class="remote-roster__name">{{ trainingFriendName(row) }}</span>
            <span class="remote-roster__meta">
              {{ pageLabel(row) }}
              <span class="remote-roster__sep">/</span>
              {{ trainingFriendTopic(row) }}
            </span>
          </span>
        </div>
      </li>
    </ul>
    <button
      v-if="canLoadMore"
      type="button"
      class="remote-roster__more"
      @click="training.fetchRoster(true)"
    >
      {{ t('training.loadMore') }}
    </button>
    <p
      v-if="training.rosterLoading && !training.rosterRows.length"
      class="remote-roster__empty"
    >
      {{ t('training.rosterLoading') }}
    </p>
    <p
      v-else-if="!training.rosterLoading && !training.rosterRows.length"
      class="remote-roster__empty"
    >
      {{ t('training.noTeachersOnline') }}
    </p>
  </section>
</template>

<style scoped>
.remote-roster {
  display: flex;
  min-height: 0;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  background: #fff;
}
.remote-roster__head {
  display: flex;
  flex-shrink: 0;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.4rem;
  padding: 0.55rem 0.7rem 0.4rem;
  border-bottom: 1px solid #f5f5f4;
}
.remote-roster__head h2 {
  margin: 0;
  color: #57534e;
  font-size: 0.7rem;
  font-weight: 650;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.remote-roster__head p,
.remote-roster__empty {
  margin: 0;
  color: #a8a29e;
  font-size: 0.7rem;
}
.remote-roster__empty {
  padding: 0.65rem 0.7rem;
}
.remote-roster__list {
  list-style: none;
  min-height: 0;
  flex: 1;
  margin: 0;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 0.25rem 0;
  scrollbar-width: thin;
}
.remote-roster__row {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  padding: 0.4rem 0.7rem;
}
.remote-roster__dot {
  flex-shrink: 0;
  width: 0.5rem;
  height: 0.5rem;
  margin-top: 0.35rem;
  border-radius: 999px;
  background: #22c55e;
}
.remote-roster__copy {
  min-width: 0;
  flex: 1;
}
.remote-roster__name {
  display: block;
  overflow: hidden;
  color: #44403c;
  font-size: 0.8125rem;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.remote-roster__meta {
  display: block;
  overflow: hidden;
  margin-top: 0.1rem;
  color: #78716c;
  font-size: 0.7rem;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.remote-roster__sep {
  color: #a8a29e;
}
.remote-roster__more {
  flex-shrink: 0;
  margin: 0.35rem 0.55rem 0.55rem;
  border: 1px solid #e7e5e4;
  border-radius: 0.4rem;
  background: #fafaf9;
  padding: 0.35rem 0.5rem;
  color: #57534e;
  cursor: pointer;
}
</style>
