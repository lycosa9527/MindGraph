<script setup lang="ts">
/**
 * AppSidebar - Collapsible sidebar with mode switching, history, and user profile
 * Migrated from prototype MindMateChatPage sidebar
 */
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import {
  ChatDotRound,
  ChatLineSquare,
  Connection,
  Document,
  Files,
  MagicStick,
  OfficeBuilding,
  Share,
  Tools,
  TrendCharts,
  VideoPlay,
  Reading,
} from '@element-plus/icons-vue'

import { ChevronDown, KeyRound, LogIn, LogOut, Menu, Settings, UserRound } from 'lucide-vue-next'
import { Watch } from 'lucide-vue-next'

import { AccountInfoModal, ChangePasswordModal, LoginModal } from '@/components/auth'
import { useLanguage } from '@/composables/useLanguage'
import { useFeatureFlags } from '@/composables/useFeatureFlags'
import { useAuthStore, useMindMateStore, useUIStore } from '@/stores'
import { useAskOnceStore } from '@/stores/askonce'
import { type SavedDiagram, useSavedDiagramsStore } from '@/stores/savedDiagrams'

import AskOnceHistory from './AskOnceHistory.vue'
import ChatHistory from './ChatHistory.vue'
import ChunkTestHistory from './ChunkTestHistory.vue'
import DebateHistory from './DebateHistory.vue'
import DiagramHistory from './DiagramHistory.vue'
import KnowledgeSpaceHistory from './KnowledgeSpaceHistory.vue'
import LibraryCommentsHistory from './LibraryCommentsHistory.vue'

const { t, isZh } = useLanguage()

const router = useRouter()
const uiStore = useUIStore()
const authStore = useAuthStore()
const mindMateStore = useMindMateStore()
const askOnceStore = useAskOnceStore()
const _savedDiagramsStore = useSavedDiagramsStore()
const {
  featureRagChunkTest,
  featureCourse,
  featureTemplate,
  featureCommunity,
  featureAskOnce,
  featureSchoolZone,
  featureDebateverse,
  featureKnowledgeSpace,
  featureLibrary,
  featureSmartResponse,
  featureTeacherUsage,
} = useFeatureFlags()

const isCollapsed = computed(() => uiStore.sidebarCollapsed)

// Derive current mode from route path
const currentMode = computed(() => {
  const path = router.currentRoute.value.path
  if (path.startsWith('/mindmate')) return 'mindmate'
  if (path.startsWith('/mindgraph') || path.startsWith('/canvas')) return 'mindgraph'
  if (path.startsWith('/knowledge-space')) return 'knowledge-space'
  if (path.startsWith('/chunk-test')) return 'chunk-test'
  if (path.startsWith('/askonce')) return 'askonce'
  if (path.startsWith('/debateverse')) return 'debateverse'
  if (path.startsWith('/school-zone')) return 'school-zone'
  if (path.startsWith('/template')) return 'template'
  if (path.startsWith('/course')) return 'course'
  if (path.startsWith('/community')) return 'community'
  if (path.startsWith('/library')) return 'library'
  if (path.startsWith('/gewe')) return 'gewe'
  if (path.startsWith('/smart-response')) return 'smart-response'
  if (path.startsWith('/teacher-usage')) return 'teacher-usage'
  return 'mindmate' // Default
})

// Check if user belongs to an organization (for school zone visibility)
const hasOrganization = computed(() => {
  return isAuthenticated.value && authStore.user?.schoolId
})

const isAuthenticated = computed(() => authStore.isAuthenticated)
const isAdminOrManager = computed(() => authStore.isAdminOrManager)
const isAdmin = computed(() => authStore.isAdmin)

// User info
const userName = computed(() => authStore.user?.username || '')
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
  // All modes now use routing
  if (index === 'mindmate') {
    router.push('/mindmate')
  } else if (index === 'mindgraph') {
    router.push('/mindgraph')
  } else if (index === 'knowledge-space') {
    router.push('/knowledge-space')
  } else if (index === 'chunk-test') {
    router.push('/chunk-test')
  } else if (index === 'askonce') {
    router.push('/askonce')
  } else if (index === 'debateverse') {
    router.push('/debateverse')
  } else if (index === 'school-zone') {
    router.push('/school-zone')
  } else if (index === 'template') {
    router.push('/template')
  } else if (index === 'course') {
    router.push('/course')
  } else if (index === 'community') {
    router.push('/community')
  } else if (index === 'library') {
    router.push('/library')
  } else if (index === 'gewe') {
    router.push('/gewe')
  } else if (index === 'smart-response') {
    router.push('/smart-response')
  } else if (index === 'teacher-usage') {
    router.push('/teacher-usage')
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

function goToAdmin() {
  router.push('/admin')
}

// Start new MindMate conversation
function startNewChat() {
  mindMateStore.startNewConversation()
  // Navigate to MindMate if not already there
  if (currentMode.value !== 'mindmate') {
    router.push('/mindmate')
  }
}

// Start new AskOnce conversation
function startNewAskOnce() {
  if (!isAuthenticated.value) {
    openLoginModal()
    return
  }
  askOnceStore.startNewConversation()
  // Navigate to AskOnce if not already there
  if (currentMode.value !== 'askonce') {
    router.push('/askonce')
  }
}

// Handle logo click based on current mode
function handleLogoClick() {
  if (currentMode.value === 'askonce') {
    startNewAskOnce()
  } else {
    startNewChat()
  }
}

// Handle diagram selection from history
async function handleDiagramSelect(diagram: SavedDiagram) {
  // Navigate to canvas with the diagram
  router.push({
    path: '/canvas',
    query: { diagramId: diagram.id.toString() },
  })
}
</script>

<template>
  <div
    class="app-sidebar bg-stone-50 border-r border-stone-200 flex flex-col transition-all duration-300 ease-in-out h-full"
    :class="isCollapsed ? 'w-16' : 'w-64'"
  >
    <!-- Header with logo and toggle -->
    <div class="p-4 flex items-center justify-between border-b border-stone-200">
      <div
        class="logo-link flex items-center space-x-2 cursor-pointer hover:opacity-80 transition-opacity"
        @click="handleLogoClick"
      >
        <div
          class="w-7 h-7 bg-stone-900 rounded-lg flex items-center justify-center text-white font-semibold text-sm"
        >
          M
        </div>
        <span
          v-if="!isCollapsed"
          class="font-semibold text-lg text-stone-900 tracking-tight"
          >Mind思维平台</span
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
        v-if="isAuthenticated && featureKnowledgeSpace"
        index="knowledge-space"
      >
        <el-icon><Document /></el-icon>
        <template #title>个人知识库</template>
      </el-menu-item>
      <el-menu-item
        v-if="isAuthenticated && featureRagChunkTest"
        index="chunk-test"
      >
        <el-icon><Tools /></el-icon>
        <template #title>RAG分块测试</template>
      </el-menu-item>
      <el-menu-item
        v-if="featureAskOnce"
        index="askonce"
      >
        <el-icon><MagicStick /></el-icon>
        <template #title>{{ t('askonce.title') }}</template>
      </el-menu-item>
      <el-menu-item
        v-if="featureDebateverse"
        index="debateverse"
      >
        <el-icon><ChatDotRound /></el-icon>
        <template #title>论境</template>
      </el-menu-item>
      <el-menu-item
        v-if="hasOrganization && featureSchoolZone"
        index="school-zone"
      >
        <el-icon><OfficeBuilding /></el-icon>
        <template #title>学校专区</template>
      </el-menu-item>
      <el-menu-item
        v-if="featureTemplate"
        index="template"
      >
        <el-icon><Files /></el-icon>
        <template #title>模板资源</template>
      </el-menu-item>
      <el-menu-item
        v-if="featureCourse"
        index="course"
      >
        <el-icon><VideoPlay /></el-icon>
        <template #title>思维课程</template>
      </el-menu-item>
      <el-menu-item
        v-if="featureCommunity"
        index="community"
      >
        <el-icon><Share /></el-icon>
        <template #title>社区分享</template>
      </el-menu-item>
      <el-menu-item
        v-if="featureLibrary"
        index="library"
      >
        <el-icon><Reading /></el-icon>
        <template #title>图书馆</template>
      </el-menu-item>
      <el-menu-item
        v-if="isAdmin"
        index="gewe"
      >
        <el-icon><ChatDotRound /></el-icon>
        <template #title>Gewe</template>
      </el-menu-item>
      <el-menu-item
        v-if="isAdminOrManager && featureSmartResponse"
        index="smart-response"
      >
        <el-icon><Watch /></el-icon>
        <template #title>{{ isZh ? 'Smart Response 智回' : 'Smart Response' }}</template>
      </el-menu-item>
      <el-menu-item
        v-if="isAdmin && featureTeacherUsage"
        index="teacher-usage"
      >
        <el-icon><TrendCharts /></el-icon>
        <template #title>{{ isZh ? '教师使用度' : 'Teacher Usage' }}</template>
      </el-menu-item>
    </el-menu>

    <!-- History section (only in expanded mode) -->
    <!-- MindMate: Show chat history -->
    <ChatHistory
      v-if="!isCollapsed && currentMode === 'mindmate'"
      :is-blurred="!isAuthenticated"
      class="flex-1 overflow-hidden"
    />
    <!-- MindGraph: Show diagram history -->
    <DiagramHistory
      v-else-if="!isCollapsed && currentMode === 'mindgraph'"
      :is-blurred="!isAuthenticated"
      class="flex-1 overflow-hidden"
      @select="handleDiagramSelect"
    />
    <!-- AskOnce: Show conversation history -->
    <AskOnceHistory
      v-else-if="!isCollapsed && currentMode === 'askonce'"
      :is-blurred="!isAuthenticated"
      class="flex-1 overflow-hidden"
    />
    <!-- Debateverse: Show recent debates -->
    <DebateHistory
      v-else-if="!isCollapsed && currentMode === 'debateverse'"
      :is-blurred="!isAuthenticated"
      class="flex-1 overflow-hidden"
    />
    <!-- Knowledge Space: Show document history -->
    <KnowledgeSpaceHistory
      v-else-if="!isCollapsed && currentMode === 'knowledge-space' && featureKnowledgeSpace"
      class="flex-1 overflow-hidden"
    />
    <!-- Chunk Test: Show test history -->
    <ChunkTestHistory
      v-else-if="!isCollapsed && currentMode === 'chunk-test' && featureRagChunkTest"
      :is-blurred="!isAuthenticated"
      class="flex-1 overflow-hidden"
    />
    <!-- Library: Show recent comments -->
    <LibraryCommentsHistory
      v-else-if="!isCollapsed && currentMode === 'library' && featureLibrary"
      :is-blurred="!isAuthenticated"
      class="flex-1 overflow-hidden"
    />

    <!-- Spacer to push user section to bottom (when no history shown) -->
    <div
      v-if="
        isCollapsed ||
        !(currentMode === 'mindmate' || currentMode === 'mindgraph' || (featureKnowledgeSpace && currentMode === 'knowledge-space') || (featureRagChunkTest && currentMode === 'chunk-test') || (featureAskOnce && currentMode === 'askonce') || (featureDebateverse && currentMode === 'debateverse'))
      "
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
                class="shrink-0"
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
                  MindGraph专业版
                </div>
              </div>
            </div>
            <ChevronDown class="w-4 h-4 text-stone-400 shrink-0 ml-2" />
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
              <!-- Admin option -->
              <el-dropdown-item
                v-if="isAdminOrManager"
                divided
                @click="goToAdmin"
              >
                <Settings class="w-4 h-4 mr-2" />
                管理面板
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
              <!-- Admin option -->
              <el-dropdown-item
                v-if="isAdminOrManager"
                divided
                @click="goToAdmin"
              >
                <Settings class="w-4 h-4 mr-2" />
                管理面板
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

.logo-link {
  text-decoration: none;
}

.logo-link:hover {
  text-decoration: none;
}
</style>

<style>
/* Global styles for user dropdown popper - arrow on right side */
.user-dropdown-popper .el-popper__arrow {
  left: auto !important;
  right: 16px !important;
}
</style>
