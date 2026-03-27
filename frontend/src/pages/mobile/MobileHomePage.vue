<script setup lang="ts">
/**
 * MobileHomePage — Landing page for mobile.
 * Shows MindMate + MindGraph feature cards, then account info at bottom.
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import { ChevronRight, MessageSquare, UserCog, Workflow } from 'lucide-vue-next'

import { useLanguage } from '@/composables'
import { useAuthStore } from '@/stores'

const router = useRouter()
const authStore = useAuthStore()
const { t } = useLanguage()

const displayName = computed(() => authStore.user?.username || '')

function goToMindMate() {
  router.push('/m/mindmate')
}

function goToMindGraph() {
  router.push('/m/mindgraph')
}

function goToAccount() {
  router.push('/m/account')
}
</script>

<template>
  <div class="mobile-home flex-1 overflow-y-auto">
    <div class="px-4 pt-6 pb-8 max-w-md mx-auto space-y-4">
      <!-- Welcome -->
      <div class="text-center mb-6">
        <div
          class="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-indigo-600 text-white text-2xl font-bold mb-3"
        >
          M
        </div>
        <h2 class="text-xl font-bold text-gray-900">
          {{ t('app.brandName') }}
        </h2>
        <p class="text-sm text-gray-500 mt-1">
          {{ t('mindmate.welcomeSubtitle', 'AI虚拟教研助手平台，随时随地激发思维') }}
        </p>
      </div>

      <!-- MindMate Card -->
      <button
        class="feature-card w-full flex items-center gap-4 p-5 bg-white rounded-2xl border border-gray-200 active:bg-gray-50 transition-colors text-left"
        @click="goToMindMate"
      >
        <div
          class="flex items-center justify-center w-12 h-12 rounded-xl bg-blue-50 text-blue-600 shrink-0"
        >
          <MessageSquare :size="24" />
        </div>
        <div class="flex-1 min-w-0">
          <div class="text-base font-semibold text-gray-900">MindMate</div>
          <div class="text-sm text-gray-500 mt-0.5">
            {{ t('mobile.mindmateDesc', 'AI智能对话助手') }}
          </div>
        </div>
        <ChevronRight
          :size="20"
          class="text-gray-400 shrink-0"
        />
      </button>

      <!-- MindGraph Card -->
      <button
        class="feature-card w-full flex items-center gap-4 p-5 bg-white rounded-2xl border border-gray-200 active:bg-gray-50 transition-colors text-left"
        @click="goToMindGraph"
      >
        <div
          class="flex items-center justify-center w-12 h-12 rounded-xl bg-purple-50 text-purple-600 shrink-0"
        >
          <Workflow :size="24" />
        </div>
        <div class="flex-1 min-w-0">
          <div class="text-base font-semibold text-gray-900">MindGraph</div>
          <div class="text-sm text-gray-500 mt-0.5">
            {{ t('mobile.mindgraphDesc', '思维图示工具') }}
          </div>
        </div>
        <ChevronRight
          :size="20"
          class="text-gray-400 shrink-0"
        />
      </button>

      <!-- Account Card -->
      <button
        class="feature-card w-full flex items-center gap-4 p-5 bg-white rounded-2xl border border-gray-200 active:bg-gray-50 transition-colors text-left"
        @click="goToAccount"
      >
        <div
          class="flex items-center justify-center w-12 h-12 rounded-xl bg-green-50 text-green-600 shrink-0"
        >
          <UserCog :size="24" />
        </div>
        <div class="flex-1 min-w-0">
          <div class="text-base font-semibold text-gray-900 truncate">
            {{ displayName }}
          </div>
          <div class="text-sm text-gray-500 mt-0.5 truncate">
            {{ t('mobile.accountDesc', '账号设置') }}
          </div>
        </div>
        <ChevronRight
          :size="20"
          class="text-gray-400 shrink-0"
        />
      </button>

      <!-- Footer -->
      <div class="text-center text-xs text-gray-400 pt-4">
        &copy; {{ new Date().getFullYear() }} MindSpring AI
      </div>
    </div>
  </div>
</template>

<style scoped>
.feature-card {
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
}

.feature-card:active {
  transform: scale(0.99);
}
</style>
