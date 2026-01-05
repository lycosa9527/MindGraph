<script setup lang="ts">
/**
 * AppSidebar - Collapsible sidebar with mode switching, history, and user profile
 * Migrated from prototype MindMateChatPage sidebar
 */
import { computed, ref } from 'vue'

import { ChatLineSquare, Connection, Grid, Plus } from '@element-plus/icons-vue'

import { ChevronDown, KeyRound, LogIn, LogOut, Menu, UserRound } from 'lucide-vue-next'

import { AccountInfoModal, ChangePasswordModal, LoginModal } from '@/components/auth'
import { useAuthStore, useMindMateStore, useUIStore } from '@/stores'

import ChatHistory from './ChatHistory.vue'

const uiStore = useUIStore()
const authStore = useAuthStore()
const mindMateStore = useMindMateStore()

const isCollapsed = computed(() => uiStore.sidebarCollapsed)
const currentMode = computed(() => uiStore.currentMode)
const isAuthenticated = computed(() => authStore.isAuthenticated)

// User info
const userName = computed(() => authStore.user?.username || '')
const userOrg = computed(() => authStore.user?.schoolName || '')
const userAvatar = computed(() => {
  const avatar = authStore.user?.avatar || '🐈‍⬛'
  // Handle legacy avatar_01 format
  if (avatar.startsWith('avatar_')) {
    return '🐈‍⬛'
  }
  return avatar
})

// Modal states
const showLoginModal = ref(false)
const showAccountModal = ref(false)
const showPasswordModal = ref(false)

function toggleSidebar() {
  uiStore.toggleSidebar()
}

function setMode(index: string) {
  if (index === 'mindmate' || index === 'mindgraph') {
    uiStore.setCurrentMode(index)
  }
}

function openLoginModal() {
  showLoginModal.value = true
}

function openPasswordModal() {
  showPasswordModal.value = true
}

function openAccountModal() {
  showAccountModal.value = true
}

async function handleLogout() {
  await authStore.logout()
}

// Start new MindMate conversation
function startNewChat() {
  mindMateStore.startNewConversation()
  // Switch to MindMate mode if not already
  if (currentMode.value !== 'mindmate') {
    uiStore.setCurrentMode('mindmate')
  }
}
</script>

<template>
  <div
    class="app-sidebar bg-stone-50 border-r border-stone-200 flex flex-col transition-all duration-300 ease-in-out h-full"
    :class="isCollapsed ? 'w-16' : 'w-64'"
  >
    <!-- Header with logo and toggle -->
    <div class="p-4 flex items-center justify-between border-b border-stone-200">
      <div class="flex items-center space-x-2">
        <div
          class="w-7 h-7 bg-stone-900 rounded-lg flex items-center justify-center text-white font-semibold text-sm"
        >
          M
        </div>
        <span
          v-if="!isCollapsed"
          class="font-semibold text-lg text-stone-900 tracking-tight"
          >MindSpring</span
        >
      </div>
      <el-button
        text
        circle
        class="toggle-btn"
        :title="isCollapsed ? '展开侧边栏' : '收起侧边栏'"
        @click="toggleSidebar"
      >
        <Menu class="w-4 h-4" />
      </el-button>
    </div>

    <!-- New Chat Button -->
    <div :class="isCollapsed ? 'px-2 py-3' : 'px-3 py-3'">
      <el-button
        type="primary"
        class="new-chat-btn w-full"
        @click="startNewChat"
      >
        <el-icon :class="isCollapsed ? '' : 'mr-2'"><Plus /></el-icon>
        <span v-if="!isCollapsed">新建对话</span>
      </el-button>
    </div>

    <!-- Mode menu -->
    <el-menu
      :default-active="currentMode"
      :collapse="isCollapsed"
      class="sidebar-menu"
      @select="setMode"
    >
      <el-menu-item index="mindmate">
        <el-icon><ChatLineSquare /></el-icon>
        <template #title>MindMate</template>
      </el-menu-item>
      <el-menu-item index="mindgraph">
        <el-icon><Connection /></el-icon>
        <template #title>MindGraph</template>
      </el-menu-item>
      <el-menu-item
        index="more"
        disabled
      >
        <el-icon><Grid /></el-icon>
        <template #title>更多应用</template>
      </el-menu-item>
    </el-menu>

    <!-- Chat history (only in expanded mode) -->
    <ChatHistory
      v-if="!isCollapsed"
      :is-blurred="!isAuthenticated"
      class="flex-1 overflow-hidden"
    />

    <!-- Spacer (only when collapsed) -->
    <div
      v-if="isCollapsed"
      class="flex-1"
    />

    <!-- User profile / Login at bottom -->
    <div
      ref="userMenuRef"
      class="border-t border-stone-200 relative"
    >
      <!-- Not authenticated: Show login button -->
      <template v-if="!isAuthenticated">
        <div :class="isCollapsed ? 'p-2' : 'p-4'">
          <el-button
            v-if="!isCollapsed"
            type="primary"
            class="login-btn w-full"
            @click="openLoginModal"
          >
            登录 / 注册
          </el-button>
          <el-button
            v-else
            type="primary"
            circle
            class="login-btn-collapsed w-full"
            @click="openLoginModal"
          >
            <LogIn class="w-4 h-4" />
          </el-button>
        </div>
      </template>

      <!-- Authenticated: Show user info with dropdown -->
      <template v-else>
        <el-dropdown
          v-if="!isCollapsed"
          trigger="click"
          placement="top-end"
          popper-class="user-dropdown-popper"
          :popper-options="{
            modifiers: [
              { name: 'offset', options: { offset: [0, 8] } },
              { name: 'flip', options: { fallbackPlacements: [] } },
            ],
          }"
          class="user-dropdown w-full"
        >
          <div
            class="flex items-center justify-between cursor-pointer hover:bg-stone-100 transition-colors px-4 py-3 w-full"
          >
            <div class="flex items-center min-w-0 flex-1">
              <el-badge
                :value="0"
                :hidden="true"
                class="flex-shrink-0"
              >
                <el-avatar
                  :size="40"
                  class="bg-stone-200 text-2xl"
                >
                  {{ userAvatar }}
                </el-avatar>
              </el-badge>
              <div class="ml-3 min-w-0 flex-1">
                <div class="text-sm font-medium text-stone-900 truncate leading-tight">
                  {{ userName }}
                </div>
                <div class="text-xs text-stone-500 truncate leading-tight mt-0.5">
                  {{ userOrg || '未设置组织' }}
                </div>
              </div>
            </div>
            <ChevronDown class="w-4 h-4 text-stone-400 flex-shrink-0 ml-2" />
          </div>
          <template #dropdown>
            <el-dropdown-menu class="user-menu">
              <el-dropdown-item @click="openAccountModal">
                <UserRound class="w-4 h-4 mr-2" />
                账户信息
              </el-dropdown-item>
              <el-dropdown-item @click="openPasswordModal">
                <KeyRound class="w-4 h-4 mr-2" />
                修改密码
              </el-dropdown-item>
              <el-dropdown-item
                divided
                @click="handleLogout"
              >
                <LogOut class="w-4 h-4 mr-2" />
                退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>

        <!-- Collapsed mode: show avatar button with dropdown -->
        <el-dropdown
          v-else
          trigger="click"
          placement="top-end"
          :popper-options="{
            modifiers: [{ name: 'offset', options: { offset: [0, 8] } }],
          }"
          class="user-dropdown-collapsed"
        >
          <el-badge
            :value="0"
            :hidden="true"
          >
            <el-button
              text
              circle
              class="toggle-btn"
            >
              <el-avatar
                :size="32"
                class="bg-stone-200 text-xl"
              >
                {{ userAvatar }}
              </el-avatar>
            </el-button>
          </el-badge>
          <template #dropdown>
            <el-dropdown-menu class="user-menu">
              <el-dropdown-item @click="openAccountModal">
                <UserRound class="w-4 h-4 mr-2" />
                账户信息
              </el-dropdown-item>
              <el-dropdown-item @click="openPasswordModal">
                <KeyRound class="w-4 h-4 mr-2" />
                修改密码
              </el-dropdown-item>
              <el-dropdown-item
                divided
                @click="handleLogout"
              >
                <LogOut class="w-4 h-4 mr-2" />
                退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </template>
    </div>

    <!-- Modals -->
    <LoginModal v-model:visible="showLoginModal" />
    <AccountInfoModal
      v-model:visible="showAccountModal"
      @success="authStore.checkAuth()"
    />
    <ChangePasswordModal v-model:visible="showPasswordModal" />
  </div>
</template>

<style scoped>
/* New Chat button - Swiss Design style (grey, round) */
.new-chat-btn {
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

/* Login button - Swiss Design style */
.login-btn {
  --el-button-bg-color: #1c1917;
  --el-button-border-color: #1c1917;
  --el-button-hover-bg-color: #292524;
  --el-button-hover-border-color: #292524;
  --el-button-active-bg-color: #0c0a09;
  --el-button-active-border-color: #0c0a09;
  font-weight: 500;
}

.login-btn-collapsed {
  --el-button-bg-color: #1c1917;
  --el-button-border-color: #1c1917;
  --el-button-hover-bg-color: #292524;
  --el-button-hover-border-color: #292524;
}

/* Sidebar menu - Swiss Design style */
.sidebar-menu {
  border-right: none;
  background-color: transparent;
  --el-menu-bg-color: transparent;
  --el-menu-hover-bg-color: #f5f5f4;
  --el-menu-active-color: #1c1917;
  --el-menu-text-color: #57534e;
  --el-menu-hover-text-color: #1c1917;
  --el-menu-item-height: 44px;
  padding: 8px 12px;
}

.sidebar-menu:not(.el-menu--collapse) {
  width: 100%;
}

.sidebar-menu :deep(.el-menu-item) {
  border-radius: 8px;
  margin-bottom: 4px;
  font-weight: 500;
  font-size: 14px;
}

.sidebar-menu :deep(.el-menu-item.is-active) {
  background-color: #1c1917;
  color: white;
}

.sidebar-menu :deep(.el-menu-item.is-active .el-icon) {
  color: white;
}

.sidebar-menu :deep(.el-menu-item.is-disabled) {
  opacity: 0.5;
}

.sidebar-menu.el-menu--collapse {
  width: 100%;
  padding: 8px;
}

.sidebar-menu.el-menu--collapse :deep(.el-menu-item) {
  padding: 0 !important;
  justify-content: center;
}

/* Toggle buttons */
.toggle-btn {
  --el-button-text-color: #78716c;
  --el-button-hover-text-color: #1c1917;
  --el-button-hover-bg-color: #e7e5e4;
}

/* Avatar styling - Swiss Design style */
.user-dropdown :deep(.el-avatar) {
  --el-avatar-bg-color: #e7e5e4;
  color: #1c1917;
  font-weight: normal;
}

.user-dropdown-collapsed :deep(.el-avatar) {
  --el-avatar-bg-color: #e7e5e4;
  color: #1c1917;
  font-weight: normal;
}

.user-dropdown-collapsed :deep(.el-dropdown-menu__item) {
  display: flex;
  align-items: center;
}

.user-dropdown-collapsed :deep(.el-dropdown-menu__item svg) {
  flex-shrink: 0;
}

/* User dropdown - Swiss Design style */
.user-dropdown {
  width: 100%;
}

.user-dropdown :deep(.el-dropdown-menu) {
  --el-dropdown-menu-box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  border: 1px solid #e7e5e4;
  border-radius: 8px;
  padding: 4px;
  min-width: 160px;
}

.user-dropdown :deep(.el-dropdown-menu__item) {
  font-size: 14px;
  padding: 8px 12px;
  color: #57534e;
  border-radius: 6px;
  display: flex;
  align-items: center;
}

.user-dropdown :deep(.el-dropdown-menu__item:hover) {
  background-color: #f5f5f4;
  color: #1c1917;
}

.user-dropdown :deep(.el-dropdown-menu__item svg) {
  flex-shrink: 0;
}

.user-dropdown :deep(.el-dropdown-menu__item.is-divided) {
  border-top: 1px solid #e7e5e4;
  margin-top: 4px;
  padding-top: 8px;
}
</style>

<style>
/* Global styles for user dropdown popper - arrow on right side */
.user-dropdown-popper .el-popper__arrow {
  left: auto !important;
  right: 16px !important;
}
</style>
