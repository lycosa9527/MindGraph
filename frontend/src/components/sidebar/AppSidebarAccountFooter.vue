<script setup lang="ts">
/**
 * Sidebar bottom: login CTA or user menu with account actions.
 */
import { computed, inject, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'

import {
  ChevronDown,
  Languages,
  Link2,
  LogIn,
  LogOut,
  ScrollText,
  Share2,
  Upload,
  UserRound,
} from '@lucide/vue'

import QuickRegisterModal from '@/components/mindgraph/QuickRegisterModal.vue'
import { useDiagramImport } from '@/composables/editor/useDiagramImport'
import { useNotifications } from '@/composables'
import { appSidebarInjectionKey } from '@/composables/sidebar/useAppSidebar'
import { isMindGraphLandingPath } from '@/utils/canvasBackNavigation'
import {
  canShowPwaInstallUi,
  promptPwaInstall,
  pwaInstallAvailable,
} from '@/utils/pwaInstall'

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
const showPwaInstall = computed(() => {
  void pwaInstallAvailable.value
  return canShowPwaInstallUi()
})
const notify = useNotifications()

async function handlePwaInstall(): Promise<void> {
  const result = await promptPwaInstall()
  if (result === 'installed') {
    notify.success(s.t('auth.pwaInstallSuccess'))
    return
  }
  if (result === 'ios-hint') {
    notify.info(s.t('auth.pwaIosInstallHint'))
    return
  }
  if (result === 'dev-hint') {
    notify.info(s.t('auth.pwaDevInstallHint'))
    return
  }
  if (result === 'desktop-hint') {
    notify.info(s.t('auth.pwaDesktopInstallHint'))
  }
}
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
          class="user-dropdown-trigger flex items-center justify-between cursor-pointer hover:bg-[#f5f5f4] transition-colors px-4 py-3 w-full"
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
              <div class="flex items-center gap-1.5 min-w-0">
                <div class="text-sm font-medium text-stone-900 truncate leading-tight min-w-0">
                  {{ s.userName }}
                </div>
                <span
                  v-if="s.userRolePill"
                  class="role-pill shrink-0 inline-flex items-center rounded-full border px-1.5 py-0 text-[10px] font-medium leading-4"
                  :class="[
                    s.userRolePill.bgClass,
                    s.userRolePill.textClass,
                    s.userRolePill.borderClass,
                  ]"
                >
                  {{ s.userRolePill.label }}
                </span>
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
          <el-dropdown-menu class="user-dropdown-menu max-h-[min(420px,70vh)] overflow-y-auto">
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
              v-if="showPwaInstall"
              @click="handlePwaInstall"
            >
              <Link2 class="w-4 h-4 mr-2" />
              {{ s.t('auth.downloadDesktopShortcut') }}
            </el-dropdown-item>
            <el-dropdown-item
              divided
              class="user-dropdown-item--logout"
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
        popper-class="user-dropdown-popper"
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
          <el-dropdown-menu class="user-dropdown-menu max-h-[min(420px,70vh)] overflow-y-auto">
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
              v-if="showPwaInstall"
              @click="handlePwaInstall"
            >
              <Link2 class="w-4 h-4 mr-2" />
              {{ s.t('auth.downloadDesktopShortcut') }}
            </el-dropdown-item>
            <el-dropdown-item
              divided
              class="user-dropdown-item--logout"
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

.user-dropdown {
  width: 100%;
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

<!-- Teleported popper — Swiss (matches MindGraphLanguageSwitcher / canvas-more-apps) -->
<style>
.user-dropdown-popper.el-popper {
  box-sizing: border-box !important;
  width: max-content !important;
  max-width: min(280px, calc(100vw - 24px)) !important;
  min-width: 0 !important;
  padding: 4px !important;
  border: 1px solid #e7e5e4 !important;
  border-radius: 10px !important;
  box-shadow:
    0 4px 6px -1px rgba(0, 0, 0, 0.07),
    0 2px 4px -2px rgba(0, 0, 0, 0.05) !important;
  overflow: hidden !important;
}

.dark .user-dropdown-popper.el-popper {
  border-color: #374151 !important;
  box-shadow:
    0 4px 6px -1px rgba(0, 0, 0, 0.25),
    0 2px 4px -2px rgba(0, 0, 0, 0.18) !important;
}

.user-dropdown-popper .el-popper__arrow {
  left: auto !important;
  right: 16px !important;
}

.user-dropdown-popper .user-dropdown-menu.el-dropdown-menu {
  width: max-content !important;
  max-width: 100% !important;
  box-sizing: border-box !important;
  padding: 0 !important;
  margin: 0 !important;
  border: none !important;
  background: transparent !important;
  overflow-x: hidden !important;
  scrollbar-gutter: stable;
}

.user-dropdown-popper .el-dropdown-menu__item {
  display: flex !important;
  align-items: center;
  padding: 8px 14px !important;
  font-size: 13px;
  font-weight: 500;
  color: #44403c;
  border-radius: 6px;
  line-height: 1.4;
  letter-spacing: 0.01em;
  max-width: 100%;
  box-sizing: border-box;
  overflow-wrap: anywhere;
  transition:
    background 0.12s,
    color 0.12s;
}

.user-dropdown-popper .el-dropdown-menu__item:hover,
.user-dropdown-popper .el-dropdown-menu__item:focus {
  background: #f5f5f4 !important;
  color: #1c1917 !important;
}

.user-dropdown-popper .el-dropdown-menu__item:active {
  background: #e7e5e4 !important;
}

.user-dropdown-popper .el-dropdown-menu__item svg {
  flex-shrink: 0;
}

.dark .user-dropdown-popper .el-dropdown-menu__item {
  color: #d6d3d1;
}

.dark .user-dropdown-popper .el-dropdown-menu__item:hover,
.dark .user-dropdown-popper .el-dropdown-menu__item:focus {
  background: #374151 !important;
  color: #f9fafb !important;
}

.dark .user-dropdown-popper .el-dropdown-menu__item:active {
  background: #4b5563 !important;
}

.user-dropdown-popper .el-dropdown-menu__item.is-divided {
  border-top: 1px solid #f3f4f6;
  margin-top: 2px;
  padding-top: 10px;
}

.dark .user-dropdown-popper .el-dropdown-menu__item.is-divided {
  border-top-color: #4b5563;
}

.user-dropdown-popper .user-dropdown-item--logout {
  color: #dc2626;
}

.user-dropdown-popper .user-dropdown-item--logout:hover,
.user-dropdown-popper .user-dropdown-item--logout:focus {
  background: #fef2f2 !important;
  color: #b91c1c !important;
}

.dark .user-dropdown-popper .user-dropdown-item--logout {
  color: #f87171;
}

.dark .user-dropdown-popper .user-dropdown-item--logout:hover,
.dark .user-dropdown-popper .user-dropdown-item--logout:focus {
  background: rgba(127, 29, 29, 0.35) !important;
  color: #fecaca !important;
}
</style>
