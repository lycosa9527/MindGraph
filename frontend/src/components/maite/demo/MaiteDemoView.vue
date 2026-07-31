<script setup lang="ts">
/**
 * MaiteDemoView — demo mode: input, stream decompose, follow-up chat.
 */
import { watch } from 'vue'

import MaiteDecomposeTables from '@/components/maite/demo/MaiteDecomposeTables.vue'
import MaiteMentorChat from '@/components/maite/demo/MaiteMentorChat.vue'
import MaiteProblemInput from '@/components/maite/shared/MaiteProblemInput.vue'
import MaiteStreamStatus from '@/components/maite/shared/MaiteStreamStatus.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import { useMaiteDemo } from '@/composables/maite/useMaiteDemo'
import { useMaiteStore } from '@/stores/maite'

const { t } = useLanguage()
const store = useMaiteStore()

const {
  messages,
  decomposition,
  replyDraft,
  errorMessage,
  canDecompose,
  canFollowUp,
  isStreaming,
  streamStatus,
  streamPreview,
  runDecompose,
  runFollowUp,
  stopStreaming,
  resetDemo,
} = useMaiteDemo()

watch(
  () => store.mode,
  (mode, prev) => {
    // Fresh demo tab only — do not wipe when reopening a saved practice session.
    if (mode === 'demo' && prev !== 'demo' && !store.activeSessionId) {
      resetDemo()
    }
  }
)

function onProblemUpdate(value: string): void {
  store.setCurrentProblemText(value)
}
</script>

<template>
  <div class="maite-demo-view">
    <section class="maite-demo-view__section">
      <h3 class="maite-demo-view__heading">{{ t('maite.demo.problemTitle') }}</h3>
      <MaiteProblemInput
        :model-value="store.currentProblemText"
        scene="demo"
        :disabled="isStreaming"
        @update:model-value="onProblemUpdate"
      />
      <div class="maite-demo-view__actions">
        <button
          type="button"
          class="maite-demo-view__btn"
          :disabled="!canDecompose"
          @click="() => runDecompose()"
        >
          {{ t('maite.demo.decompose') }}
        </button>
      </div>
      <MaiteStreamStatus
        :streaming="isStreaming"
        :status="streamStatus"
        :preview="streamPreview"
        @stop="stopStreaming"
      />
      <p v-if="errorMessage" class="maite-demo-view__error">
        {{ t(`maite.errors.${errorMessage}`, t('maite.errors.generic')) }}
      </p>
    </section>

    <section v-if="decomposition" class="maite-demo-view__section">
      <h3 class="maite-demo-view__heading">{{ t('maite.demo.tablesTitle') }}</h3>
      <MaiteDecomposeTables :tables="decomposition" />
    </section>

    <section v-if="messages.length > 0" class="maite-demo-view__section">
      <h3 class="maite-demo-view__heading">{{ t('maite.demo.chatTitle') }}</h3>
      <MaiteMentorChat :messages="messages" />
      <textarea
        v-model="replyDraft"
        class="maite-demo-view__reply"
        :placeholder="t('maite.demo.replyPlaceholder')"
        :disabled="isStreaming"
        rows="3"
      />
      <div class="maite-demo-view__actions">
        <button
          type="button"
          class="maite-demo-view__btn"
          :disabled="!canFollowUp"
          @click="runFollowUp"
        >
          {{ t('maite.demo.followUp') }}
        </button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.maite-demo-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.maite-demo-view__section {
  padding: 16px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid var(--el-border-color-lighter, #f5f5f4);
}

.maite-demo-view__heading {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 600;
}

.maite-demo-view__actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}

.maite-demo-view__btn {
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  background: #667eea;
  color: #fff;
  cursor: pointer;
  font-size: 13px;
}

.maite-demo-view__btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.maite-demo-view__reply {
  width: 100%;
  margin-top: 10px;
  padding: 10px;
  border: 1px solid var(--el-border-color, #e7e5e4);
  border-radius: 8px;
  font-family: inherit;
  font-size: 14px;
}

.maite-demo-view__error {
  margin: 8px 0 0;
  color: #dc2626;
  font-size: 13px;
}
</style>
