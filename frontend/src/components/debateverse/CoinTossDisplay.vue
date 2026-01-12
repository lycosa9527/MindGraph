<script setup lang="ts">
/**
 * CoinTossDisplay - Coin toss animation and result
 */
import { ref, computed, onMounted } from 'vue'

import { ElButton } from 'element-plus'

import { useLanguage } from '@/composables/useLanguage'
import { useDebateVerseStore } from '@/stores/debateverse'

const { isZh } = useLanguage()
const store = useDebateVerseStore()

// ============================================================================
// State
// ============================================================================

const isFlipping = ref(false)
const showResult = ref(false)

// ============================================================================
// Computed
// ============================================================================

const result = computed(() => store.currentSession?.session.coin_toss_result)

const resultText = computed(() => {
  if (!result.value) return ''
  return result.value === 'affirmative_first'
    ? (isZh ? '正方先发言' : 'Affirmative speaks first')
    : (isZh ? '反方先发言' : 'Negative speaks first')
})

// ============================================================================
// Actions
// ============================================================================

async function executeCoinToss() {
  if (isFlipping.value) return

  isFlipping.value = true
  showResult.value = false

  try {
    await store.coinToss()
    
    // Show result after animation
    setTimeout(() => {
      showResult.value = true
      isFlipping.value = false
    }, 2000)
  } catch (error) {
    console.error('Error executing coin toss:', error)
    isFlipping.value = false
  }
}
</script>

<template>
  <div class="flex items-center justify-center h-full">
    <div class="text-center">
      <h2 class="text-2xl font-semibold text-gray-900 mb-8">
        {{ isZh ? '掷硬币决定发言顺序' : 'Coin Toss to Determine Speaking Order' }}
      </h2>

      <!-- Coin Animation -->
      <div class="mb-8">
        <div
          class="coin w-32 h-32 mx-auto rounded-full bg-gradient-to-br from-yellow-400 to-yellow-600 shadow-lg flex items-center justify-center text-white text-4xl font-bold"
          :class="{ 'flipping': isFlipping }"
        >
          <span v-if="!isFlipping && !showResult">?</span>
          <span v-else-if="isFlipping">🪙</span>
          <span v-else>{{ result === 'affirmative_first' ? '正' : '反' }}</span>
        </div>
      </div>

      <!-- Result -->
      <div
        v-if="showResult"
        class="mb-8"
      >
        <p class="text-xl font-medium text-gray-900">
          {{ resultText }}
        </p>
      </div>

      <!-- Button -->
      <ElButton
        v-if="!result"
        type="primary"
        size="large"
        :loading="isFlipping"
        @click="executeCoinToss"
      >
        {{ isZh ? '执行掷硬币' : 'Execute Coin Toss' }}
      </ElButton>
      <ElButton
        v-else
        type="primary"
        size="large"
        @click="store.advanceStage('opening')"
      >
        {{ isZh ? '开始辩论' : 'Start Debate' }}
      </ElButton>
    </div>
  </div>
</template>

<style scoped>
.coin {
  transition: transform 0.6s ease-in-out;
}

.coin.flipping {
  animation: flip 2s ease-in-out;
}

@keyframes flip {
  0% {
    transform: rotateY(0deg);
  }
  50% {
    transform: rotateY(1800deg);
  }
  100% {
    transform: rotateY(3600deg);
  }
}
</style>
