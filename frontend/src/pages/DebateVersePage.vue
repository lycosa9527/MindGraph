<script setup lang="ts">
/**
 * DebateVersePage - US-style debate interface
 * Route: /debateverse
 *
 * Chinese name: 论境
 * English name: DebateVerse
 */
import { computed, onMounted, onUnmounted, ref } from 'vue'

import { ElButton, ElDialog, ElIcon, ElInput, ElOption, ElSelect } from 'element-plus'

import { Plus } from '@element-plus/icons-vue'

import { useLanguage } from '@/composables/useLanguage'
import { useDebateVerseStore } from '@/stores/debateverse'
import DebateVerseStage from '@/components/debateverse/DebateVerseStage.vue'
import DebateSetup from '@/components/debateverse/DebateSetup.vue'

const { t, isZh } = useLanguage()
const store = useDebateVerseStore()

// ============================================================================
// State
// ============================================================================

const showSetup = computed(() => store.currentStage === 'setup')

// ============================================================================
// Lifecycle
// ============================================================================

onMounted(() => {
  // Load user's recent sessions if any
})

onUnmounted(() => {
  store.abortAllStreams()
})
</script>

<template>
  <div class="flex flex-col h-full bg-gray-50">
    <!-- Header - Only show when not in setup mode -->
    <header
      v-if="!showSetup"
      class="h-14 px-4 flex items-center justify-between bg-white border-b border-gray-200"
    >
      <div class="flex items-center gap-3">
        <h1 class="text-sm font-semibold text-gray-800">{{ isZh ? '论境' : 'DebateVerse' }}</h1>
        <span
          v-if="store.currentSession"
          class="text-gray-300"
        >|</span>
        <span
          v-if="store.currentSession"
          class="text-sm text-gray-500 truncate max-w-xs"
          :title="store.currentSession.session.topic"
        >
          {{ store.currentSession.session.topic }}
        </span>
      </div>
      <div class="flex items-center gap-2">
        <ElButton
          class="new-debate-btn"
          size="small"
          @click="store.createSession('', store.llmAssignments)"
        >
          <ElIcon class="mr-1"><Plus /></ElIcon>
          {{ isZh ? '新建辩论' : 'New Debate' }}
        </ElButton>
      </div>
    </header>

    <!-- Main Content -->
    <main class="flex-1 overflow-hidden">
      <!-- Stage 1: Setup -->
      <DebateSetup
        v-if="showSetup"
        class="h-full"
      />

      <!-- Stage 2-3: Debate Stage -->
      <DebateVerseStage
        v-else-if="store.currentSession"
        class="h-full"
      />

      <!-- Empty State -->
      <div
        v-else
        class="flex items-center justify-center h-full"
      >
        <div class="text-center text-gray-500">
          <p class="text-lg mb-2">{{ isZh ? '还没有辩论' : 'No debate yet' }}</p>
          <ElButton
            type="primary"
            @click="store.createSession('', store.llmAssignments)"
          >
            {{ isZh ? '创建新辩论' : 'Create New Debate' }}
          </ElButton>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
/* New Debate button - Swiss Design style */
.new-debate-btn {
  --el-button-bg-color: #e7e5e4;
  --el-button-border-color: #d6d3d1;
  --el-button-hover-bg-color: #d6d3d1;
  --el-button-hover-border-color: #a8a29e;
  --el-button-active-bg-color: #a8a29e;
  --el-button-active-border-color: #78716c;
  --el-button-text-color: #1c1917;
  font-weight: 500;
  border-radius: 9999px;
}
</style>
