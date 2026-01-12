<script setup lang="ts">
/**
 * DebateVerseStage - Three-column stage layout (Affirmative | Judge | Negative)
 */
import { computed, ref } from 'vue'

import { ElButton, ElIcon } from 'element-plus'
import { ArrowRight } from '@element-plus/icons-vue'

import { useLanguage } from '@/composables/useLanguage'
import { useDebateVerseStore } from '@/stores/debateverse'
import DebaterAvatar from './DebaterAvatar.vue'
import DebateMessages from './DebateMessages.vue'
import JudgeArea from './JudgeArea.vue'
import DebateInput from './DebateInput.vue'
import CoinTossDisplay from './CoinTossDisplay.vue'

const { isZh } = useLanguage()
const store = useDebateVerseStore()

// ============================================================================
// State
// ============================================================================

const isTriggeringNext = ref(false)

// ============================================================================
// Computed
// ============================================================================

const showCoinToss = computed(() => store.currentStage === 'coin_toss')

const canTriggerNext = computed(() => {
  // Can trigger if not currently streaming, not already triggering, and debate not completed
  return !store.isStreaming && !isTriggeringNext.value && store.currentStage !== 'completed' && store.currentStage !== 'setup'
})

const nextButtonText = computed(() => {
  if (isTriggeringNext.value) {
    return isZh.value ? '触发中...' : 'Triggering...'
  }
  if (store.isStreaming) {
    return isZh.value ? '进行中...' : 'In Progress...'
  }
  return isZh.value ? '下一步' : 'Next'
})

function getStageName(stage: string): string {
  const names: Record<string, string> = {
    setup: '准备',
    coin_toss: '掷硬币',
    opening: '立论发言',
    rebuttal: '驳论发言',
    cross_exam: '交叉质询',
    closing: '总结陈词',
    judgment: '评判',
    completed: '已完成',
  }
  return names[stage] || stage
}

async function handleNext() {
  if (!canTriggerNext.value) return

  isTriggeringNext.value = true
  try {
    await store.triggerNext()
  } catch (error) {
    console.error('Error triggering next:', error)
  } finally {
    isTriggeringNext.value = false
  }
}

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
  <div class="h-full flex flex-col bg-gray-50">
    <!-- Stage Header -->
    <div class="px-6 py-3 bg-white border-b border-gray-200">
      <div class="flex items-center justify-between">
        <div>
          <span class="text-sm font-medium text-gray-700">
            {{ isZh ? '当前阶段' : 'Current Stage' }}:
          </span>
          <span class="ml-2 text-sm text-gray-900">
            {{ isZh ? getStageName(store.currentStage) : store.currentStage }}
          </span>
        </div>
        <div
          v-if="store.userRole === 'judge'"
          class="flex items-center gap-2"
        >
          <ElButton
            size="small"
            @click="handleAdvanceStage"
          >
            {{ isZh ? '进入下一阶段' : 'Advance Stage' }}
          </ElButton>
        </div>
      </div>
    </div>

    <!-- Coin Toss Display -->
    <CoinTossDisplay
      v-if="showCoinToss"
      class="flex-1"
    />

    <!-- Three-Column Stage -->
    <div
      v-else
      class="flex-1 flex flex-col"
    >
      <!-- Avatar Panels (Stops at avatar level) -->
      <div class="grid grid-cols-3 gap-4 px-4 pt-4 pb-6">
        <!-- Affirmative Side -->
        <div class="flex flex-col items-center gap-4">
          <h3 class="text-sm font-semibold text-green-700">
            {{ isZh ? '正方' : 'Affirmative' }}
          </h3>
          <div class="flex flex-col gap-4 w-full">
            <DebaterAvatar
              v-for="participant in store.affirmativeParticipants"
              :key="participant.id"
              :participant="participant"
              :is-speaking="store.currentSpeaker === participant.id"
            />
          </div>
        </div>

        <!-- Judge Area (Center) -->
        <div class="flex flex-col items-center gap-4 bg-gray-100 rounded-lg p-4">
          <h3 class="text-sm font-semibold text-gray-700">
            {{ isZh ? '裁判' : 'Judge' }}
          </h3>
          <div class="flex flex-col gap-4 w-full">
            <DebaterAvatar
              v-if="store.judgeParticipant"
              :participant="store.judgeParticipant"
              :is-speaking="store.currentSpeaker === store.judgeParticipant.id"
            />
          </div>
        </div>

        <!-- Negative Side -->
        <div class="flex flex-col items-center gap-4">
          <h3 class="text-sm font-semibold text-red-700">
            {{ isZh ? '反方' : 'Negative' }}
          </h3>
          <div class="flex flex-col gap-4 w-full">
            <DebaterAvatar
              v-for="participant in store.negativeParticipants"
              :key="participant.id"
              :participant="participant"
              :is-speaking="store.currentSpeaker === participant.id"
            />
          </div>
        </div>
      </div>

      <!-- Messages Area (Below avatars) -->
      <div class="flex-1 grid grid-cols-3 gap-4 px-4 pb-4 min-h-0">
        <!-- Affirmative Messages -->
        <div class="overflow-y-auto">
          <DebateMessages
            :side="'affirmative'"
            class="w-full"
          />
        </div>

        <!-- Judge Messages -->
        <div class="overflow-y-auto">
          <DebateMessages
            :side="'judge'"
            class="w-full"
          />
        </div>

        <!-- Negative Messages -->
        <div class="overflow-y-auto">
          <DebateMessages
            :side="'negative'"
            class="w-full"
          />
        </div>
      </div>

      <!-- Status Bar (Space below) -->
      <div class="px-4 py-3 bg-white border-t border-gray-200 flex-shrink-0">
        <div class="flex items-center justify-center gap-6 text-sm text-gray-600">
          <span
            v-if="store.currentSpeaker"
            class="font-medium"
          >
            {{ isZh ? '当前发言' : 'Speaking' }}:
            <span class="text-gray-900">
              {{ store.participants.find(p => p.id === store.currentSpeaker)?.name || '' }}
            </span>
          </span>
          <span
            v-else
            class="text-gray-400"
          >
            {{ isZh ? '等待开始...' : 'Waiting to start...' }}
          </span>
        </div>
      </div>
    </div>

    <!-- User Input (if debater) -->
    <DebateInput
      v-if="store.canUserSpeak"
      class="border-t border-gray-200 bg-white"
    />

    <!-- Next Button (Fixed bottom right) -->
    <div class="fixed bottom-6 right-6 z-10">
      <ElButton
        type="primary"
        size="large"
        :disabled="!canTriggerNext"
        :loading="isTriggeringNext || store.isStreaming"
        class="next-button"
        @click="handleNext"
      >
        <ElIcon class="mr-1"><ArrowRight /></ElIcon>
        {{ nextButtonText }}
      </ElButton>
    </div>
  </div>
</template>

<style scoped>
.next-button {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  border-radius: 12px;
  padding: 12px 24px;
  font-weight: 500;
  transition: all 0.2s;
}

.next-button:hover:not(:disabled) {
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.2);
  transform: translateY(-1px);
}

.next-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
