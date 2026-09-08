<script setup lang="ts">
import { computed, ref } from 'vue'

import TrainingPlayControls from '@/components/training/TrainingPlayControls.vue'
import TrainingRemotePrompter from '@/components/training/TrainingRemotePrompter.vue'
import TrainingRemoteRoster from '@/components/training/TrainingRemoteRoster.vue'
import { useLanguage } from '@/composables'
import {
  trainingSteerMode,
  type TrainingSteerMode,
} from '@/composables/training/applyTrainingSnapshot'
import {
  requestTrainingEnd,
  requestTrainingFree,
  requestTrainingStep,
} from '@/composables/training/trainingCommands'
import { canSteerLiveSnapshot } from '@/composables/training/trainingMarkSteps'
import {
  trainingRemotePhase,
  trainingRemotePrompterKey,
} from '@/composables/training/trainingRemoteView'
import { useTrainingRemoteChrome } from '@/composables/training/useTrainingRemoteChrome'
import { useTrainingRemoteSync } from '@/composables/training/useTrainingRemoteSync'
import { useAuthStore } from '@/stores/auth'
import { useTrainingStore } from '@/stores/training'

const { t } = useLanguage()
const authStore = useAuthStore()
const training = useTrainingStore()
const stopOpen = ref(false)

const myUserId = computed(() => Number(authStore.user?.id) || null)
const phase = computed(() => trainingRemotePhase(training.snapshot, myUserId.value))
const notes = computed(() => (training.snapshot.step?.notes || '').trim())
const prompterKey = computed(() => trainingRemotePrompterKey(training.snapshot))
const canPrev = computed(() => canSteerLiveSnapshot(training.snapshot, -1))
const canNext = computed(() => canSteerLiveSnapshot(training.snapshot, 1))
const hostName = computed(() => (training.snapshot.instructor_name || '').trim() || '—')
const padBusy = computed(() => training.busy || stopOpen.value)

useTrainingRemoteSync()
const { isPortrait } = useTrainingRemoteChrome(() => phase.value === 'live')

function onMode(next: TrainingSteerMode): void {
  if (next === trainingSteerMode(training.snapshot)) return
  requestTrainingFree(next === 'free')
}

function askStop(): void {
  if (padBusy.value) return
  stopOpen.value = true
}

function cancelStop(): void {
  stopOpen.value = false
}

function confirmStop(): void {
  stopOpen.value = false
  requestTrainingEnd(true)
}
</script>

<template>
  <div class="remote">
    <div
      v-if="phase === 'live' && isPortrait"
      class="remote__rotate"
    >
      <p>{{ t('training.remoteRotate') }}</p>
    </div>
    <div
      v-else-if="phase === 'live'"
      class="remote__grid"
    >
      <div class="remote__col remote__col--pad">
        <TrainingPlayControls
          layout="stack"
          :can-prev="canPrev"
          :can-next="canNext"
          :busy="padBusy"
          :mode="trainingSteerMode(training.snapshot)"
          @prev="requestTrainingStep(-1)"
          @next="requestTrainingStep(1)"
          @stop="askStop"
          @mode="onMode"
        />
      </div>
      <div class="remote__col remote__col--list">
        <TrainingRemoteRoster />
      </div>
      <div class="remote__col remote__col--notes">
        <TrainingRemotePrompter
          :text="notes"
          :reset-key="prompterKey"
        />
      </div>
    </div>
    <div
      v-else
      class="remote__wait"
    >
      <h1>{{ t('training.title') }}</h1>
      <p v-if="phase === 'foreign'">
        {{ t('training.remoteForeign', { name: hostName }) }}
      </p>
      <p v-else>
        {{ t('training.remoteWaiting') }}
      </p>
    </div>
    <div
      v-if="stopOpen"
      class="remote__confirm"
      role="dialog"
      aria-modal="true"
      :aria-label="t('training.stop')"
    >
      <div class="remote__confirm-card">
        <h2>{{ t('training.stop') }}</h2>
        <p>{{ t('training.confirmStop') }}</p>
        <div class="remote__confirm-actions">
          <button
            type="button"
            class="remote__confirm-btn"
            @click="cancelStop"
          >
            {{ t('common.cancel') }}
          </button>
          <button
            type="button"
            class="remote__confirm-btn remote__confirm-btn--go"
            @click="confirmStop"
          >
            {{ t('training.stop') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.remote {
  position: relative;
  display: flex;
  width: 100%;
  height: 100%;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  background: #0c0a09;
}
.remote__grid {
  display: grid;
  min-height: 0;
  flex: 1;
  grid-template-columns: minmax(8.5rem, 22%) minmax(10rem, 28%) minmax(0, 1fr);
  padding: 0.4rem max(0.4rem, env(safe-area-inset-right, 0px))
    max(0.4rem, env(safe-area-inset-bottom, 0px)) max(0.4rem, env(safe-area-inset-left, 0px));
  gap: 0.35rem;
}
.remote__col {
  display: flex;
  min-height: 0;
  min-width: 0;
  overflow: hidden;
  border-radius: 0.55rem;
}
.remote__col--pad {
  align-items: stretch;
  overflow-x: hidden;
  overflow-y: auto;
  background: #1c1917;
}
.remote__wait,
.remote__rotate {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
  color: #e7e5e4;
  text-align: center;
}
.remote__wait h1 {
  margin: 0 0 0.6rem;
  font-size: 1.25rem;
}
.remote__wait p,
.remote__rotate p {
  max-width: 22rem;
  margin: 0;
  color: #a8a29e;
  font-size: 0.95rem;
  line-height: 1.5;
}
.remote__confirm {
  position: absolute;
  inset: 0;
  z-index: 8;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgb(12 10 9 / 0.72);
  padding: 1rem;
}
.remote__confirm-card {
  width: min(22rem, 100%);
  border-radius: 0.7rem;
  background: #1c1917;
  padding: 1rem 1.05rem 0.9rem;
  color: #fafaf9;
}
.remote__confirm-card h2 {
  margin: 0 0 0.4rem;
  font-size: 1.05rem;
}
.remote__confirm-card p {
  margin: 0 0 0.85rem;
  color: #a8a29e;
  font-size: 0.9rem;
  line-height: 1.45;
}
.remote__confirm-actions {
  display: flex;
  gap: 0.45rem;
}
.remote__confirm-btn {
  min-height: 44px;
  flex: 1;
  border: 1px solid #57534e;
  border-radius: 0.45rem;
  background: #292524;
  color: #fafaf9;
  font-weight: 650;
  cursor: pointer;
}
.remote__confirm-btn--go {
  border-color: #b91c1c;
  background: #dc2626;
}
</style>
