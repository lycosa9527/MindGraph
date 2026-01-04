<script setup lang="ts">
/**
 * AppSidebar - Collapsible sidebar with mode switching, history, and user profile
 * Migrated from prototype MindMateChatPage sidebar
 */
import { computed } from 'vue'

import { ChevronDown, Menu, MessageSquare, MoreHorizontal, Network } from 'lucide-vue-next'

import { useAuthStore, useUIStore } from '@/stores'

import ChatHistory from './ChatHistory.vue'
import UpgradeCard from './UpgradeCard.vue'

const uiStore = useUIStore()
const authStore = useAuthStore()

const isCollapsed = computed(() => uiStore.sidebarCollapsed)
const currentMode = computed(() => uiStore.currentMode)

// User info
const userName = computed(() => authStore.user?.username || 'MOMO')
const userOrg = computed(() => '学校/组织')
const userAvatarUrl =
  'https://images.unsplash.com/photo-1494790108377-be9c29b29330?ixlib=rb-1.2.1&auto=format&fit=facearea&facepad=2&w=256&h=256&q=80'

function toggleSidebar() {
  uiStore.toggleSidebar()
}

function setMode(mode: 'mindmate' | 'mindgraph') {
  uiStore.setCurrentMode(mode)
}
</script>

<template>
  <div
    class="app-sidebar bg-gray-50 border-r border-gray-200 flex flex-col transition-all duration-300 ease-in-out h-full"
    :class="isCollapsed ? 'w-16' : 'w-64'"
  >
    <!-- Header with logo and toggle -->
    <div class="p-4 flex items-center justify-between border-b border-gray-200">
      <div class="flex items-center space-x-2">
        <div
          class="w-6 h-6 bg-indigo-600 rounded-md flex items-center justify-center text-white font-bold text-sm"
        >
          M
        </div>
        <span
          v-if="!isCollapsed"
          class="font-bold text-lg text-gray-800"
          >MindSpring</span
        >
      </div>
      <button
        class="p-2 rounded-md hover:bg-gray-200 transition-colors"
        :title="isCollapsed ? '展开侧边栏' : '收起侧边栏'"
        @click="toggleSidebar"
      >
        <Menu class="w-4.5 h-4.5 text-gray-600" />
      </button>
    </div>

    <!-- Mode buttons -->
    <div class="p-4">
      <div class="space-y-2">
        <!-- MindMate mode -->
        <button
          class="flex items-center w-full px-3 py-2.5 rounded-lg transition-colors"
          :class="
            currentMode === 'mindmate'
              ? 'bg-blue-50 text-gray-800'
              : 'text-gray-800 hover:bg-gray-200'
          "
          @click="setMode('mindmate')"
        >
          <MessageSquare
            class="w-4.5 h-4.5 text-blue-600"
            :class="isCollapsed ? '' : 'mr-2'"
          />
          <span v-if="!isCollapsed">MindMate</span>
        </button>

        <!-- MindGraph mode -->
        <button
          class="flex items-center w-full px-3 py-2.5 rounded-lg transition-colors"
          :class="
            currentMode === 'mindgraph'
              ? 'bg-blue-50 text-gray-800'
              : 'text-gray-800 hover:bg-gray-200'
          "
          title="点击展开MindGraph"
          @click="setMode('mindgraph')"
        >
          <Network
            class="w-4.5 h-4.5 text-gray-600"
            :class="isCollapsed ? '' : 'mr-2'"
          />
          <span v-if="!isCollapsed">MindGraph</span>
        </button>

        <!-- More apps -->
        <button
          class="flex items-center w-full px-3 py-2.5 rounded-lg text-gray-800 hover:bg-gray-200 transition-colors"
        >
          <MoreHorizontal
            class="w-4.5 h-4.5 text-gray-600"
            :class="isCollapsed ? '' : 'mr-2'"
          />
          <span v-if="!isCollapsed">更多应用</span>
        </button>
      </div>
    </div>

    <!-- Chat history (only in expanded mode) -->
    <ChatHistory
      v-if="!isCollapsed"
      class="flex-shrink-0"
    />

    <!-- Upgrade card (only in expanded mode) -->
    <UpgradeCard
      v-if="!isCollapsed"
      class="flex-shrink-0"
    />

    <!-- Spacer -->
    <div class="flex-1" />

    <!-- User profile at bottom -->
    <div class="p-4 border-t border-gray-200">
      <div class="flex items-center justify-between">
        <div class="flex items-center">
          <img
            :src="userAvatarUrl"
            alt="用户头像"
            class="w-8 h-8 rounded-full object-cover"
          />
          <div
            v-if="!isCollapsed"
            class="ml-2"
          >
            <div class="text-sm font-medium text-gray-800">{{ userName }}</div>
            <div class="text-xs text-gray-500">{{ userOrg }}</div>
          </div>
        </div>
        <button class="p-1.5 rounded-md hover:bg-gray-200">
          <ChevronDown class="w-4 h-4 text-gray-600" />
        </button>
      </div>
    </div>
  </div>
</template>
