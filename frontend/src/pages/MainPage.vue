<script setup lang="ts">
/**
 * MainPage - Unified MindMate/MindGraph main page
 * Combines chat interface and diagram selection based on current mode
 */
import { computed } from 'vue'

import { PlusCircle } from 'lucide-vue-next'

import { ChatContainer } from '@/components/chat'
import { MindGraphContainer } from '@/components/mindgraph'
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
    <!-- Top header (only for MindMate mode) -->
    <div
      v-if="isMindMateMode"
      class="p-4 border-b border-gray-200 flex justify-between items-center"
    >
      <div class="font-semibold text-gray-800">MindMate</div>
      <button
        class="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 transition-colors text-sm font-medium flex items-center"
      >
        <PlusCircle class="w-4 h-4 mr-1" />
        新建对话
      </button>
    </div>

    <!-- MindMate Chat Mode -->
    <ChatContainer
      v-if="isMindMateMode"
      class="flex-1"
    />

    <!-- MindGraph Mode -->
    <MindGraphContainer
      v-if="isMindGraphMode"
      class="flex-1"
    />
  </div>
</template>
