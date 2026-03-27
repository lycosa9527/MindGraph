<script setup lang="ts">
/**
 * JudgeArea - Center area with judge avatar and controls
 */
import { computed } from 'vue'

import { ElButton } from 'element-plus'

import { useLanguage } from '@/composables/core/useLanguage'
import { useDebateVerseStore } from '@/stores/debateverse'

import DebaterAvatar from './DebaterAvatar.vue'

const { t } = useLanguage()
const store = useDebateVerseStore()

// ============================================================================
// Computed
// ============================================================================

const judge = computed(() => store.judgeParticipant)

const judgeMessages = computed(() => {
  const j = judge.value
  if (!j) return []
  return store.messages.filter((msg) => msg.participant_id === j.id)
})

function handleAdvanceStage() {
  const stageOrder: Array<typeof store.currentStage> = [
    'coin_toss',
    'opening',
    'rebuttal',
    'cross_exam',
    'closing',
    'judgment',
  ]
  const currentIndex = stageOrder.indexOf(store.currentStage)
  if (currentIndex < stageOrder.length - 1) {
    store.advanceStage(stageOrder[currentIndex + 1])
  }
}
</script>

<template>
  <div class="judge-area flex flex-col items-center gap-4">
    <!-- Judge Avatar -->
    <DebaterAvatar
      v-if="judge"
      :participant="judge"
      :is-speaking="store.currentSpeaker === judge.id"
    />

    <!-- Judge Messages -->
    <div class="w-full space-y-2">
      <div
        v-for="msg in judgeMessages"
        :key="msg.id"
        class="text-xs text-gray-600 p-2 bg-white rounded border border-gray-200"
      >
        {{ msg.content }}
      </div>
    </div>

    <!-- Judge Controls -->
    <div
      v-if="store.userRole === 'judge'"
      class="flex flex-col gap-2 w-full"
    >
      <ElButton
        v-if="store.currentStage === 'coin_toss'"
        type="primary"
        size="small"
        @click="store.coinToss()"
      >
        {{ t('debateverse.executeCoinToss') }}
      </ElButton>
      <ElButton
        v-else-if="store.currentStage !== 'completed'"
        type="primary"
        size="small"
        @click="handleAdvanceStage"
      >
        {{ t('debateverse.advanceStage') }}
      </ElButton>
    </div>
  </div>
</template>
