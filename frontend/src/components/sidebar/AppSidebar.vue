<script setup lang="ts">
/**
 * AppSidebar - Collapsible sidebar with inline accordion panels
 * Each module can expand its history panel below; only one panel open at a time.
 * Workshop mode hides admin items and fills remaining space.
 */
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import {
  ChatDotRound,
  ChatLineSquare,
  Connection,
  Document,
  Files,
  MagicStick,
  OfficeBuilding,
  Reading,
  Share,
  Tools,
  TrendCharts,
  VideoPlay,
} from '@element-plus/icons-vue'

import {
  ChevronDown,
  KeyRound,
  LogIn,
  LogOut,
  Menu,
  MessageSquare,
  Settings,
  UserRound,
  Watch,
} from 'lucide-vue-next'

import { AccountInfoModal, ChangePasswordModal, LoginModal } from '@/components/auth'
import { useFeatureFlags } from '@/composables/useFeatureFlags'
import { useLanguage } from '@/composables/useLanguage'
import { useAuthStore, useMindMateStore, useUIStore } from '@/stores'
import { useAskOnceStore } from '@/stores/askonce'
import { type SavedDiagram } from '@/stores/savedDiagrams'
import { userCanAccessWorkshopChat } from '@/utils/workshopAccess'

import AskOnceHistory from './AskOnceHistory.vue'
import ChatHistory from './ChatHistory.vue'
import ChunkTestHistory from './ChunkTestHistory.vue'
import DebateHistory from './DebateHistory.vue'
import DiagramHistory from './DiagramHistory.vue'
import KnowledgeSpaceHistory from './KnowledgeSpaceHistory.vue'
import LibraryCommentsHistory from './LibraryCommentsHistory.vue'
import WorkshopChatHistory from './WorkshopChatHistory.vue'

const { t, isZh } = useLanguage()

const router = useRouter()
const uiStore = useUIStore()
const authStore = useAuthStore()
const mindMateStore = useMindMateStore()
const askOnceStore = useAskOnceStore()
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
  featureGewe,
  featureSmartResponse,
  featureTeacherUsage,
  featureWorkshopChat,
  workshopChatPreviewOrgIds,
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
  if (path.startsWith('/school-dashboard')) return 'school-dashboard'
  if (path.startsWith('/admin')) return 'admin'
  if (path.startsWith('/smart-response')) return 'smart-response'
  if (path.startsWith('/teacher-usage')) return 'teacher-usage'
  if (path.startsWith('/workshop-chat')) return 'workshop-chat'
  return 'mindmate' // Default
})

// Check if user belongs to an organization (for school zone visibility)
const hasOrganization = computed(() => {
  return isAuthenticated.value && authStore.user?.schoolId
})

const isAuthenticated = computed(() => authStore.isAuthenticated)
const isAdminOrManager = computed(() => authStore.isAdminOrManager)
const isAdmin = computed(() => authStore.isAdmin)

const canAccessWorkshopChat = computed(() => {
  if (!featureWorkshopChat.value) {
    return false
  }
  return userCanAccessWorkshopChat(
    authStore.isAdminOrManager,
    authStore.user?.schoolId,
    workshopChatPreviewOrgIds.value
  )
})

// User info
const userName = computed(() => authStore.user?.username || '')
const userSubtitle = computed(() => {
  const schoolName = authStore.user?.schoolName
  return schoolName && schoolName.trim() ? schoolName : 'MindGraph专业版'
})
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

const routeMap: Record<string, string> = {
  mindmate: '/mindmate',
  mindgraph: '/mindgraph',
  'knowledge-space': '/knowledge-space',
  'chunk-test': '/chunk-test',
  askonce: '/askonce',
  debateverse: '/debateverse',
  'school-zone': '/school-zone',
  template: '/template',
  course: '/course',
  community: '/community',
  library: '/library',
  gewe: '/gewe',
  'school-dashboard': '/school-dashboard',
  admin: '/admin',
  'smart-response': '/smart-response',
  'teacher-usage': '/teacher-usage',
  'workshop-chat': '/workshop-chat',
}

function setMode(index: string) {
  if (currentMode.value === index) {
    expandedPanel.value = expandedPanel.value === index ? null : index
    return
  }

  expandedPanel.value = index
  const route = routeMap[index]
  if (route) {
    router.push(route)
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

const expandedPanel = ref<string | null>(null)
const workshopExpanded = computed(() => expandedPanel.value === 'workshop-chat')

function navItemClass(mode: string) {
  return {
    'nav-item--collapsed': isCollapsed.value,
    'is-active': currentMode.value === mode,
  }
}

function showPanel(mode: string): boolean {
  return !isCollapsed.value && expandedPanel.value === mode
}

watch(currentMode, () => {
  if (expandedPanel.value && expandedPanel.value !== currentMode.value) {
    expandedPanel.value = null
  }
})
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

    <!-- Navigation with inline accordion panels -->
    <div
      class="sidebar-nav-scroll"
      :class="{
        'sidebar-nav-scroll--collapsed': isCollapsed,
        'sidebar-nav-scroll--workshop': workshopExpanded && !isCollapsed,
      }"
    >
      <!-- MindMate -->
      <el-tooltip
        content="MindMate"
        placement="right"
        :disabled="!isCollapsed"
      >
        <div
          class="nav-item"
          :class="navItemClass('mindmate')"
          @click="setMode('mindmate')"
        >
          <el-icon><ChatLineSquare /></el-icon>
          <span
            v-if="!isCollapsed"
            class="nav-label"
            >MindMate</span
          >
        </div>
      </el-tooltip>
      <transition name="panel-slide">
        <div
          v-if="showPanel('mindmate')"
          class="sidebar-panel"
        >
          <ChatHistory :is-blurred="!isAuthenticated" />
        </div>
      </transition>

      <!-- MindGraph -->
      <el-tooltip
        content="MindGraph"
        placement="right"
        :disabled="!isCollapsed"
      >
        <div
          class="nav-item"
          :class="navItemClass('mindgraph')"
          @click="setMode('mindgraph')"
        >
          <el-icon><Connection /></el-icon>
          <span
            v-if="!isCollapsed"
            class="nav-label"
            >MindGraph</span
          >
        </div>
      </el-tooltip>
      <transition name="panel-slide">
        <div
          v-if="showPanel('mindgraph')"
          class="sidebar-panel"
        >
          <DiagramHistory
            :is-blurred="!isAuthenticated"
            @select="handleDiagramSelect"
          />
        </div>
      </transition>

      <!-- Knowledge Space -->
      <el-tooltip
        v-if="isAuthenticated && featureKnowledgeSpace"
        content="个人知识库"
        placement="right"
        :disabled="!isCollapsed"
      >
        <div
          class="nav-item"
          :class="navItemClass('knowledge-space')"
          @click="setMode('knowledge-space')"
        >
          <el-icon><Document /></el-icon>
          <span
            v-if="!isCollapsed"
            class="nav-label"
            >个人知识库</span
          >
        </div>
      </el-tooltip>
      <transition name="panel-slide">
        <div
          v-if="isAuthenticated && featureKnowledgeSpace && showPanel('knowledge-space')"
          class="sidebar-panel"
        >
          <KnowledgeSpaceHistory />
        </div>
      </transition>

      <!-- Chunk Test -->
      <el-tooltip
        v-if="isAuthenticated && featureRagChunkTest"
        content="RAG分块测试"
        placement="right"
        :disabled="!isCollapsed"
      >
        <div
          class="nav-item"
          :class="navItemClass('chunk-test')"
          @click="setMode('chunk-test')"
        >
          <el-icon><Tools /></el-icon>
          <span
            v-if="!isCollapsed"
            class="nav-label"
            >RAG分块测试</span
          >
        </div>
      </el-tooltip>
      <transition name="panel-slide">
        <div
          v-if="isAuthenticated && featureRagChunkTest && showPanel('chunk-test')"
          class="sidebar-panel"
        >
          <ChunkTestHistory :is-blurred="!isAuthenticated" />
        </div>
      </transition>

      <!-- AskOnce -->
      <el-tooltip
        v-if="featureAskOnce"
        :content="t('askonce.title')"
        placement="right"
        :disabled="!isCollapsed"
      >
        <div
          class="nav-item"
          :class="navItemClass('askonce')"
          @click="setMode('askonce')"
        >
          <el-icon><MagicStick /></el-icon>
          <span
            v-if="!isCollapsed"
            class="nav-label"
            >{{ t('askonce.title') }}</span
          >
        </div>
      </el-tooltip>
      <transition name="panel-slide">
        <div
          v-if="featureAskOnce && showPanel('askonce')"
          class="sidebar-panel"
        >
          <AskOnceHistory :is-blurred="!isAuthenticated" />
        </div>
      </transition>

      <!-- Debateverse -->
      <el-tooltip
        v-if="featureDebateverse"
        content="论境"
        placement="right"
        :disabled="!isCollapsed"
      >
        <div
          class="nav-item"
          :class="navItemClass('debateverse')"
          @click="setMode('debateverse')"
        >
          <el-icon><ChatDotRound /></el-icon>
          <span
            v-if="!isCollapsed"
            class="nav-label"
            >论境</span
          >
        </div>
      </el-tooltip>
      <transition name="panel-slide">
        <div
          v-if="featureDebateverse && showPanel('debateverse')"
          class="sidebar-panel"
        >
          <DebateHistory :is-blurred="!isAuthenticated" />
        </div>
      </transition>

      <!-- School Zone -->
      <el-tooltip
        v-if="hasOrganization && featureSchoolZone"
        content="学校专区"
        placement="right"
        :disabled="!isCollapsed"
      >
        <div
          class="nav-item"
          :class="navItemClass('school-zone')"
          @click="setMode('school-zone')"
        >
          <el-icon><OfficeBuilding /></el-icon>
          <span
            v-if="!isCollapsed"
            class="nav-label"
            >学校专区</span
          >
        </div>
      </el-tooltip>

      <!-- Templates -->
      <el-tooltip
        v-if="featureTemplate"
        content="模板资源"
        placement="right"
        :disabled="!isCollapsed"
      >
        <div
          class="nav-item"
          :class="navItemClass('template')"
          @click="setMode('template')"
        >
          <el-icon><Files /></el-icon>
          <span
            v-if="!isCollapsed"
            class="nav-label"
            >模板资源</span
          >
        </div>
      </el-tooltip>

      <!-- Courses -->
      <el-tooltip
        v-if="featureCourse"
        content="思维课程"
        placement="right"
        :disabled="!isCollapsed"
      >
        <div
          class="nav-item"
          :class="navItemClass('course')"
          @click="setMode('course')"
        >
          <el-icon><VideoPlay /></el-icon>
          <span
            v-if="!isCollapsed"
            class="nav-label"
            >思维课程</span
          >
        </div>
      </el-tooltip>

      <!-- Community -->
      <el-tooltip
        v-if="featureCommunity"
        content="社区分享"
        placement="right"
        :disabled="!isCollapsed"
      >
        <div
          class="nav-item"
          :class="navItemClass('community')"
          @click="setMode('community')"
        >
          <el-icon><Share /></el-icon>
          <span
            v-if="!isCollapsed"
            class="nav-label"
            >社区分享</span
          >
        </div>
      </el-tooltip>

      <!-- Library -->
      <el-tooltip
        v-if="featureLibrary"
        content="图书馆"
        placement="right"
        :disabled="!isCollapsed"
      >
        <div
          class="nav-item"
          :class="navItemClass('library')"
          @click="setMode('library')"
        >
          <el-icon><Reading /></el-icon>
          <span
            v-if="!isCollapsed"
            class="nav-label"
            >图书馆</span
          >
        </div>
      </el-tooltip>
      <transition name="panel-slide">
        <div
          v-if="featureLibrary && showPanel('library')"
          class="sidebar-panel"
        >
          <LibraryCommentsHistory :is-blurred="!isAuthenticated" />
        </div>
      </transition>

      <!-- Workshop Chat (admin & school managers) -->
      <el-tooltip
        v-if="canAccessWorkshopChat"
        :content="t('workshop.title')"
        placement="right"
        :disabled="!isCollapsed"
      >
        <div
          class="nav-item"
          :class="navItemClass('workshop-chat')"
          @click="setMode('workshop-chat')"
        >
          <el-icon><MessageSquare /></el-icon>
          <span
            v-if="!isCollapsed"
            class="nav-label ws-menu-title"
          >
            {{ t('workshop.title') }}
            <ChevronDown
              class="ws-expand-chevron"
              :class="{ 'ws-expand-chevron--open': workshopExpanded }"
            />
          </span>
        </div>
      </el-tooltip>
      <transition name="ws-slide">
        <div
          v-if="workshopExpanded && !isCollapsed && canAccessWorkshopChat"
          class="workshop-panel-host"
        >
          <WorkshopChatHistory :is-blurred="!isAuthenticated" />
        </div>
      </transition>

      <!-- Admin / management items (inline, hidden when workshop expanded) -->
      <template v-if="!workshopExpanded && (isAdminOrManager || isAdmin)">
        <div class="nav-divider" />

        <el-tooltip
          v-if="isAdmin && featureGewe"
          content="Gewe"
          placement="right"
          :disabled="!isCollapsed"
        >
          <div
            class="nav-item"
            :class="navItemClass('gewe')"
            @click="setMode('gewe')"
          >
            <el-icon><ChatDotRound /></el-icon>
            <span
              v-if="!isCollapsed"
              class="nav-label"
              >Gewe</span
            >
          </div>
        </el-tooltip>

        <el-tooltip
          v-if="isAdminOrManager && featureSmartResponse"
          :content="isZh ? 'Smart Response 智回' : 'Smart Response'"
          placement="right"
          :disabled="!isCollapsed"
        >
          <div
            class="nav-item"
            :class="navItemClass('smart-response')"
            @click="setMode('smart-response')"
          >
            <el-icon><Watch /></el-icon>
            <span
              v-if="!isCollapsed"
              class="nav-label"
              >{{ isZh ? 'Smart Response 智回' : 'Smart Response' }}</span
            >
          </div>
        </el-tooltip>

        <el-tooltip
          v-if="isAdmin && featureTeacherUsage"
          :content="isZh ? '教师使用度' : 'Teacher Usage'"
          placement="right"
          :disabled="!isCollapsed"
        >
          <div
            class="nav-item"
            :class="navItemClass('teacher-usage')"
            @click="setMode('teacher-usage')"
          >
            <el-icon><TrendCharts /></el-icon>
            <span
              v-if="!isCollapsed"
              class="nav-label"
              >{{ isZh ? '教师使用度' : 'Teacher Usage' }}</span
            >
          </div>
        </el-tooltip>

        <el-tooltip
          v-if="isAdminOrManager"
          :content="t('admin.schoolDashboard')"
          placement="right"
          :disabled="!isCollapsed"
        >
          <div
            class="nav-item"
            :class="navItemClass('school-dashboard')"
            @click="setMode('school-dashboard')"
          >
            <el-icon><OfficeBuilding /></el-icon>
            <span
              v-if="!isCollapsed"
              class="nav-label"
              >{{ t('admin.schoolDashboard') }}</span
            >
          </div>
        </el-tooltip>

        <el-tooltip
          v-if="isAdmin"
          :content="t('admin.title')"
          placement="right"
          :disabled="!isCollapsed"
        >
          <div
            class="nav-item"
            :class="navItemClass('admin')"
            @click="setMode('admin')"
          >
            <el-icon><Settings /></el-icon>
            <span
              v-if="!isCollapsed"
              class="nav-label"
              >{{ t('admin.title') }}</span
            >
          </div>
        </el-tooltip>
      </template>
    </div>

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
                <div class="org-subtitle-wrapper text-xs text-stone-500 leading-tight mt-0.5">
                  <div
                    class="org-subtitle-inner"
                    :class="{ 'org-subtitle-marquee': userSubtitle.length > 12 }"
                  >
                    <span class="org-subtitle-text">{{ userSubtitle }}</span>
                    <span
                      v-if="userSubtitle.length > 12"
                      class="org-subtitle-text org-subtitle-sep"
                    >
                      {{ userSubtitle }}
                    </span>
                  </div>
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

/* Navigation container (no scroll — only panels scroll internally) */
.sidebar-nav-scroll {
  flex: 1;
  overflow: hidden;
  min-height: 0;
  padding: 8px 12px;
}

.sidebar-nav-scroll--workshop {
  display: flex;
  flex-direction: column;
}

.sidebar-nav-scroll--collapsed {
  padding: 8px;
}

/* Custom nav items (replaces el-menu for inline accordion support) */
.nav-item {
  display: flex;
  align-items: center;
  height: 44px;
  padding: 0 16px;
  border-radius: 8px;
  margin-bottom: 4px;
  font-weight: 500;
  font-size: 14px;
  color: #57534e;
  cursor: pointer;
  transition:
    background-color 0.15s,
    color 0.15s;
  user-select: none;
  flex-shrink: 0;
}

.nav-item:hover {
  background-color: #f5f5f4;
  color: #1c1917;
}
.nav-item.is-active {
  background-color: #1c1917;
  color: white;
}
.nav-item.is-active .el-icon {
  color: white;
}
.nav-item .el-icon {
  margin-right: 8px;
  font-size: 18px;
  flex-shrink: 0;
}
.nav-item--collapsed {
  justify-content: center;
  padding: 0;
}
.nav-item--collapsed .el-icon {
  margin-right: 0;
}

.nav-label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.nav-divider {
  height: 1px;
  background-color: #e7e5e4;
  margin: 4px 0;
  flex-shrink: 0;
}

/* Inline history panels (accordion) */
.sidebar-panel {
  max-height: 40vh;
  overflow-y: auto;
  overflow-x: hidden;
  flex-shrink: 0;
}

.sidebar-panel::-webkit-scrollbar {
  width: 4px;
}
.sidebar-panel::-webkit-scrollbar-track {
  background: transparent;
}
.sidebar-panel::-webkit-scrollbar-thumb {
  background-color: #d6d3d1;
  border-radius: 2px;
}
.sidebar-panel::-webkit-scrollbar-thumb:hover {
  background-color: #a8a29e;
}

.workshop-panel-host {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* Panel slide transition (for accordion history panels) */
.panel-slide-enter-active {
  transition:
    max-height 0.3s ease,
    opacity 0.3s ease;
  overflow: hidden;
}
.panel-slide-leave-active {
  transition:
    max-height 0.25s ease,
    opacity 0.25s ease;
  overflow: hidden;
}
.panel-slide-enter-from,
.panel-slide-leave-to {
  max-height: 0;
  opacity: 0;
}
.panel-slide-enter-to,
.panel-slide-leave-from {
  max-height: 40vh;
  opacity: 1;
}

/* Workshop chevron indicator */
.ws-menu-title {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  flex: 1;
}

.ws-expand-chevron {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
  color: #a8a29e;
  transition: transform 0.2s ease;
  transform: rotate(-90deg);
}

.ws-expand-chevron--open {
  transform: rotate(0deg);
}
.nav-item.is-active .ws-expand-chevron {
  color: rgba(255, 255, 255, 0.7);
}

/* Workshop panel slide transition */
.ws-slide-enter-active {
  transition: all 0.3s ease;
  overflow: hidden;
}
.ws-slide-leave-active {
  transition: all 0.25s ease;
  overflow: hidden;
}
.ws-slide-enter-from,
.ws-slide-leave-to {
  max-height: 0;
  opacity: 0;
}
.ws-slide-enter-to,
.ws-slide-leave-from {
  max-height: 100vh;
  opacity: 1;
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

/* Organization name marquee for long names */
.org-subtitle-wrapper {
  overflow: hidden;
  min-width: 0;
}

.org-subtitle-inner {
  display: inline-flex;
  white-space: nowrap;
}

.org-subtitle-text {
  flex-shrink: 0;
}

.org-subtitle-sep {
  padding-left: 1.5em;
}

.org-subtitle-marquee {
  animation: org-subtitle-scroll 12s linear infinite;
}

.org-subtitle-marquee:hover {
  animation-play-state: paused;
}

@keyframes org-subtitle-scroll {
  0% {
    transform: translateX(0);
  }
  100% {
    transform: translateX(-50%);
  }
}
</style>

<style>
/* Global styles for user dropdown popper - arrow on right side */
.user-dropdown-popper .el-popper__arrow {
  left: auto !important;
  right: 16px !important;
}
</style>
