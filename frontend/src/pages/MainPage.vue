<script setup lang="ts">
/**
 * MainPage - Unified MindMate/MindGraph main page
 * Combines chat interface and diagram selection based on current mode
 */
import { computed } from 'vue'

import { MindGraphContainer } from '@/components/mindgraph'
import { MindmatePanel } from '@/components/panels'
import { useAuthStore, useUIStore } from '@/stores'

const uiStore = useUIStore()
// authStore reserved for future user-specific features
const _authStore = useAuthStore()

const currentMode = computed(() => uiStore.currentMode)
const isMindMateMode = computed(() => currentMode.value === 'mindmate')
const isMindGraphMode = computed(() => currentMode.value === 'mindgraph')
</script>

<template>
  <div
    class="main-page flex-1 flex flex-col transition-all duration-300 ease-in-out"
    :style="{ backgroundColor: isMindGraphMode ? '#f9fafb' : 'white' }"
  >
    <!-- MindMate Chat Mode (Full-featured) -->
    <MindmatePanel
      v-if="isMindMateMode"
      mode="fullpage"
      class="flex-1"
    />

    <!-- MindGraph Mode -->
    <MindGraphContainer
      v-if="isMindGraphMode"
      class="flex-1"
    />
  </div>
</template>
