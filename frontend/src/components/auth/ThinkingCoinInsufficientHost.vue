<script setup lang="ts">
/**
 * App-wide thinking-coin shortage toast and wallet.
 * Lives on the root layout so canvas, mobile, and MindMate all see it.
 */
import { defineAsyncComponent, nextTick, ref } from 'vue'

import { useThinkingCoinInsufficientListener } from '@/composables/auth/useThinkingCoinInsufficientListener'

const ThinkingCoinsModal = defineAsyncComponent(
  () => import('@/components/auth/ThinkingCoinsModal.vue')
)

const visible = ref(false)
const mounted = ref(false)
const initialTab = ref<'wallet' | 'subscription'>('wallet')

useThinkingCoinInsufficientListener((tab = 'wallet') => {
  initialTab.value = tab
  if (!mounted.value) {
    mounted.value = true
    void nextTick(() => {
      visible.value = true
    })
    return
  }
  visible.value = true
})
</script>

<template>
  <ThinkingCoinsModal
    v-if="mounted"
    v-model:visible="visible"
    :initial-tab="initialTab"
  />
</template>
