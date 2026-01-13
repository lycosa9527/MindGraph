<script setup lang="ts">
/**
 * DebateVerseStage - Three-column stage layout (Affirmative | Judge | Negative)
 */
import { computed, ref } from 'vue'

import { ElButton } from 'element-plus'
import { Coins, Mic, MessageSquare, MessageCircleQuestion, CheckCircle, Gavel } from 'lucide-vue-next'

import { useLanguage } from '@/composables/useLanguage'
import { useDebateVerseStore } from '@/stores/debateverse'
import DebaterAvatar from './DebaterAvatar.vue'
import DebateSection from './DebateSection.vue'
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

const currentStage = computed(() => store.currentStage || 'setup')
const showCoinToss = computed(() => currentStage.value === 'coin_toss')

const canTriggerNext = computed(() => {
  // Can trigger if not currently streaming, not already triggering, and debate not completed
  // Include coin_toss stage so users can click next to advance
  const stage = currentStage.value
  return !store.isStreaming && !isTriggeringNext.value && stage !== 'completed' && stage !== 'setup'
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

const debateStages = [
  { key: 'coin_toss' as const, zh: '掷硬币', en: 'Coin Toss', icon: Coins },
  { key: 'opening' as const, zh: '立论发言', en: 'Opening', icon: Mic },
  { key: 'rebuttal' as const, zh: '驳论发言', en: 'Rebuttal', icon: MessageSquare },
  { key: 'cross_exam' as const, zh: '交叉质询', en: 'Cross-Exam', icon: MessageCircleQuestion },
  { key: 'closing' as const, zh: '总结陈词', en: 'Closing', icon: CheckCircle },
  { key: 'judgment' as const, zh: '评判', en: 'Judgment', icon: Gavel },
]

function getStageName(stage: string): string {
  const stageInfo = debateStages.find(s => s.key === stage)
  if (stageInfo) {
    return isZh.value ? stageInfo.zh : stageInfo.en
  }
  
  const names: Record<string, string> = {
    setup: '准备',
    completed: '已完成',
  }
  return isZh.value ? (names[stage] || stage) : stage
}

const currentStageIndex = computed(() => {
  const stage = currentStage.value
  const index = debateStages.findIndex(s => s.key === stage)
  // If stage not found in debateStages (e.g., 'setup'), return -1 to highlight nothing
  // If found, return index to highlight up to and including current stage
  return index >= 0 ? index : -1
})

async function handleNext() {
  if (!canTriggerNext.value) return

  isTriggeringNext.value = true
  try {
    if (currentStage.value === 'coin_toss') {
      // Execute coin toss and advance to opening
      await store.coinToss()
      await store.advanceStage('opening')
    } else {
      // Normal next action
      await store.triggerNext()
    }
  } catch (error) {
    console.error('Error triggering next:', error)
  } finally {
    isTriggeringNext.value = false
  }
}

function handleAdvanceStage() {
  const stageOrder = [
    'coin_toss',
    'opening',
    'rebuttal',
    'cross_exam',
    'closing',
    'judgment',
  ] as const
  const currentIndex = stageOrder.indexOf(currentStage.value as any)
  if (currentIndex < stageOrder.length - 1) {
    store.advanceStage(stageOrder[currentIndex + 1])
  }
}
</script>

<template>
  <div class="h-full flex flex-col bg-gray-50">
    <!-- Status Bar Section: Progress bar with stage icons and current speaker info -->
    <div class="flex-shrink-0 px-6 py-4 bg-white border-b border-gray-200">
      <div
        v-if="currentStage !== 'setup' && currentStage !== 'completed'"
        class="w-full"
      >
        <!-- Progress Bar with Stage Sections (Word Ribbon Style) -->
        <div class="flex items-stretch">
          <div
            v-for="(stage, index) in debateStages"
            :key="stage.key"
            class="stage-section flex flex-col items-center justify-center gap-2 px-4 py-3 flex-1 transition-all duration-200 border-r border-gray-200 last:border-r-0"
            :class="{
              'bg-blue-100 border-blue-300': index === currentStageIndex,
              'bg-blue-50': index < currentStageIndex,
              'bg-white': index > currentStageIndex,
              'ring-2 ring-blue-500 ring-offset-2': index === currentStageIndex,
            }"
          >
            <!-- Icon -->
            <div
              class="w-8 h-8 flex items-center justify-center transition-all duration-200 rounded-full"
              :class="{
                'text-blue-700 bg-blue-200': index === currentStageIndex,
                'text-blue-600': index < currentStageIndex,
                'text-gray-400': index > currentStageIndex,
              }"
            >
              <component
                :is="stage.icon"
                :size="20"
              />
            </div>
            
            <!-- Label -->
            <span
              class="text-xs text-center font-medium"
              :class="{
                'text-blue-800 font-bold': index === currentStageIndex,
                'text-blue-700': index < currentStageIndex,
                'text-gray-500': index > currentStageIndex,
              }"
            >
              {{ isZh ? stage.zh : stage.en }}
            </span>
          </div>
        </div>

        <!-- Current Speaker Info -->
        <div
          v-if="store.currentSpeaker"
          class="mt-3 text-center text-xs text-gray-500"
        >
          {{ isZh ? '发言中' : 'Speaking' }}:
          <span class="font-medium text-gray-700 ml-1">
            {{ store.participants.find(p => p.id === store.currentSpeaker)?.name || '' }}
          </span>
        </div>
      </div>

      <!-- Judge Advance Button -->
      <div
        v-if="store.userRole === 'judge' && !showCoinToss && currentStage !== 'setup' && currentStage !== 'completed'"
        class="mt-3 flex justify-end"
      >
        <ElButton
          size="small"
          @click="handleAdvanceStage"
        >
          {{ isZh ? '进入下一阶段' : 'Advance Stage' }}
        </ElButton>
      </div>
    </div>

    <!-- Coin Toss Display -->
    <CoinTossDisplay
      v-if="showCoinToss"
      class="flex-1"
    />

    <!-- Debate Section (Three-Column Layout: Avatars + Messages) -->
    <div
      v-else
      class="flex-1 flex flex-col min-h-0"
    >
      <!-- Avatar Section (Top - Shows participant avatars) -->
      <div class="flex-shrink-0 grid grid-cols-3 gap-4 px-4 pt-4 pb-6">
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
        <div class="flex flex-col items-center gap-4 bg-gray-100 rounded-lg p-4 mt-16">
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

      <!-- Debate Section (Messages) -->
      <DebateSection class="flex-1 min-h-0" />
    </div>

    <!-- Message Input Section (Always shown, includes input and Next button) -->
    <DebateInput
      v-if="!showCoinToss && currentStage !== 'setup' && currentStage !== 'completed'"
      :is-triggering-next="isTriggeringNext"
      :can-trigger-next="canTriggerNext"
      :next-button-text="nextButtonText"
      @next="handleNext"
    />
  </div>
</template>

