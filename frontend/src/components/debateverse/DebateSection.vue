<script setup lang="ts">
/**
 * DebateSection - Shared message area with messages aligned by side
 * Affirmative messages on left, negative messages on right (like ChatGPT)
 */
import { ElScrollbar } from 'element-plus'

import CoinTossCard from './CoinTossCard.vue'
import DebateMessages from './DebateMessages.vue'
</script>

<template>
  <!-- Debate Messages Section (Shared area with side-aligned messages) -->
  <div class="debate-section flex-1 min-h-0 flex flex-col">
    <ElScrollbar class="flex-1">
      <div class="debate-messages-container">
        <!-- Coin Toss Info Card -->
        <CoinTossCard />

        <DebateMessages :side="'all'" />
      </div>
    </ElScrollbar>
  </div>
</template>

<style scoped>
.debate-section {
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

.debate-messages-container {
  padding: 16px;
  max-width: 70%;
  margin: 0 auto;
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
}
</style>
