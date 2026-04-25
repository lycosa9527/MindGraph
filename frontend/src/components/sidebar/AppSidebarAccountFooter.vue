<script setup lang="ts">
/**
 * Sidebar bottom: login CTA or user menu with account actions.
 */
import { computed, inject, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'

import {
  ChevronDown,
  Languages,
  LogIn,
  LogOut,
  ScrollText,
  Share2,
  Upload,
  UserRound,
} from 'lucide-vue-next'

import QuickRegisterModal from '@/components/mindgraph/QuickRegisterModal.vue'
import { useDiagramImport } from '@/composables/editor/useDiagramImport'
import { appSidebarInjectionKey } from '@/composables/sidebar/useAppSidebar'
import { isMindGraphLandingPath } from '@/utils/canvasBackNavigation'

const _raw = inject(appSidebarInjectionKey)
if (!_raw) {
  throw new Error('AppSidebarAccountFooter must be used inside AppSidebar')
}
const s = reactive(_raw)
const route = useRoute()
const orgSubtitle = computed(() => s.userSubtitle as string)
const showShareSiteModal = ref(false)
const { triggerImport } = useDiagramImport()
const showMindGraphGalleryImport = computed(() => isMindGraphLandingPath(route.path))
</script>

<template>
  <div class="border-t border-stone-200 relative">
    <!-- Not authenticated: Show login button -->
    <template v-if="!s.isAuthenticated">
      <div :class="s.isCollapsed ? 'p-2 flex flex-col gap-2' : 'p-4 flex flex-col gap-2'">
        <el-button
          v-if="!s.isCollapsed"
          type="primary"
          class="login-btn w-full"
          @click="s.openLoginModal"
        >
          {{ s.t('auth.loginRegister') }}
        </el-button>
        <el-button
          v-else
          type="primary"
          circle
          class="login-btn-collapsed w-full"
          @click="s.openLoginModal"
        >
          <LogIn class="w-4 h-4" />
        </el-button>
      </div>
    </template>

    <!-- Authenticated: Show user info with dropdown -->
    <template v-else>
      <el-dropdown
        v-if="!s.isCollapsed"
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
                {{ s.userAvatar }}
              </el-avatar>
            </el-badge>
            <div class="ml-3 min-w-0 flex-1">
              <div class="text-sm font-medium text-stone-900 truncate leading-tight">
                {{ s.userName }}
              </div>
              <div class="org-subtitle-wrapper text-xs text-stone-500 leading-tight mt-0.5">
                <div
                  class="org-subtitle-inner"
                  :class="{ 'org-subtitle-marquee': orgSubtitle.length > 12 }"
                >
                  <span class="org-subtitle-text">{{ orgSubtitle }}</span>
                  <span
                    v-if="orgSubtitle.length > 12"
                    class="org-subtitle-text org-subtitle-sep"
                  >
                    {{ orgSubtitle }}
                  </span>
                </div>
              </div>
            </div>
          </div>
          <ChevronDown class="w-4 h-4 text-stone-400 shrink-0 ml-2" />
        </div>
        <template #dropdown>
          <el-dropdown-menu class="user-menu">
            <el-dropdown-item
              v-if="showMindGraphGalleryImport"
              @click="triggerImport"
            >
              <Upload class="w-4 h-4 mr-2" />
              {{ s.t('mindgraphLanding.import') }}
            </el-dropdown-item>
            <el-dropdown-item
              v-if="s.isAdminOrManager"
              @click="showShareSiteModal = true"
            >
              <Share2 class="w-4 h-4 mr-2" />
              {{ s.t('landing.international.shareSite') }}
            </el-dropdown-item>
            <el-dropdown-item
              divided
              @click="s.openLanguageSettingsModal"
            >
              <Languages class="w-4 h-4 mr-2" />
              {{ s.t('sidebar.languageSettings') }}
            </el-dropdown-item>
            <el-dropdown-item @click="s.openAccountModal">
              <UserRound class="w-4 h-4 mr-2" />
              {{ s.t('auth.accountInfo') }}
            </el-dropdown-item>
            <el-dropdown-item @click="s.openUpdateLogModal">
              <ScrollText class="w-4 h-4 mr-2" />
              {{ s.t('auth.updateLog') }}
            </el-dropdown-item>
            <el-dropdown-item
              divided
              @click="s.handleLogout"
            >
              <LogOut class="w-4 h-4 mr-2" />
              {{ s.t('auth.logout') }}
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
              {{ s.userAvatar }}
            </el-avatar>
          </el-button>
        </el-badge>
        <template #dropdown>
          <el-dropdown-menu class="user-menu">
            <el-dropdown-item
              v-if="showMindGraphGalleryImport"
              @click="triggerImport"
            >
              <Upload class="w-4 h-4 mr-2" />
              {{ s.t('mindgraphLanding.import') }}
            </el-dropdown-item>
            <el-dropdown-item
              v-if="s.isAdminOrManager"
              @click="showShareSiteModal = true"
            >
              <Share2 class="w-4 h-4 mr-2" />
              {{ s.t('landing.international.shareSite') }}
            </el-dropdown-item>
            <el-dropdown-item
              divided
              @click="s.openLanguageSettingsModal"
            >
              <Languages class="w-4 h-4 mr-2" />
              {{ s.t('sidebar.languageSettings') }}
            </el-dropdown-item>
            <el-dropdown-item @click="s.openAccountModal">
              <UserRound class="w-4 h-4 mr-2" />
              {{ s.t('auth.accountInfo') }}
            </el-dropdown-item>
            <el-dropdown-item @click="s.openUpdateLogModal">
              <ScrollText class="w-4 h-4 mr-2" />
              {{ s.t('auth.updateLog') }}
            </el-dropdown-item>
            <el-dropdown-item
              divided
              @click="s.handleLogout"
            >
              <LogOut class="w-4 h-4 mr-2" />
              {{ s.t('auth.logout') }}
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </template>

    <QuickRegisterModal v-model="showShareSiteModal" />
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
