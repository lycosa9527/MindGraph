<script setup lang="ts">
/**
 * AppSidebar - Collapsible sidebar with inline accordion panels
 * Each module can expand its history panel below; only one panel open at a time.
 * Workshop mode hides admin items and fills remaining space.
 */
import { computed, inject, onBeforeUnmount, provide, ref, watch } from 'vue'

import { ElButton } from 'element-plus'

import { PanelLeftClose } from '@lucide/vue'

import LoginModal from '@/components/auth/LoginModal.vue'
import ThinkingCoinsModal from '@/components/auth/ThinkingCoinsModal.vue'
import UpdateLogModal from '@/components/auth/UpdateLogModal.vue'
import I18nText from '@/components/common/I18nText.vue'
import UserSettingsModal from '@/components/settings/UserSettingsModal.vue'
import OctoberUpdateModal from '@/components/training/OctoberUpdateModal.vue'
import { useThinkingCoinInsufficientListener } from '@/composables/auth/useThinkingCoinInsufficientListener'
import { eventBus } from '@/composables/core/useEventBus'
import { appSidebarInjectionKey, useAppSidebar } from '@/composables/sidebar/useAppSidebar'
import { useLogoSiteQrHover } from '@/composables/sidebar/useLogoSiteQrHover'
import { isTrainingInlineHost } from '@/composables/training/trainingInlineHost'
import { TRAINING_LOCK_SCOPE, registerTrainingUiLock } from '@/composables/training/trainingUiLock'
import type { TrainingModalKey } from '@/config/trainingUiTargets'

import AppSidebarAccountFooter from './AppSidebarAccountFooter.vue'
import AppSidebarNav from './AppSidebarNav.vue'
import LogoQrScanModal from './LogoQrScanModal.vue'

const sidebar = useAppSidebar()
const inline = isTrainingInlineHost()
const lockScope = inject(TRAINING_LOCK_SCOPE, '')
const localCollapsed = ref(false)
const collapsed = computed(() => (inline ? localCollapsed.value : sidebar.isCollapsed.value))

function toggleCollapsed(): void {
  if (inline) {
    localCollapsed.value = !localCollapsed.value
    return
  }
  sidebar.toggleSidebar()
}

const providedSidebar = inline
  ? {
      ...sidebar,
      isCollapsed: collapsed,
      toggleSidebar: toggleCollapsed,
    }
  : sidebar
provide(appSidebarInjectionKey, providedSidebar)

useThinkingCoinInsufficientListener(() => sidebar.openThinkingCoinsUpgrade())

const {
  showUserSettingsModal,
  userSettingsTab,
  showLoginModal,
  showThinkingCoinsModal,
  thinkingCoinsModalTab,
  showUpdateLogModal,
  authStore,
  isAuthenticated,
  brandHeaderLayout,
  brandSubtitleKind,
  orgEditionLabel,
  orgEditionParams,
  orgEditionTooltip,
} = sidebar
const showOctoberUpdate = ref(false)

function openTrainingModal(key: TrainingModalKey): void {
  if (key === 'language-settings') {
    sidebar.openLanguageSettingsModal()
    return
  }
  if (key === 'account') {
    sidebar.openAccountModal()
    return
  }
  if (key === 'thinking-coins') {
    sidebar.openThinkingCoinsModal()
    return
  }
  if (key === 'login') {
    sidebar.openLoginModal()
    return
  }
  if (key === 'update-log') {
    sidebar.openUpdateLogModal()
    return
  }
  if (key === 'october-update') {
    showOctoberUpdate.value = true
  }
}

const TRAINING_HOST_MODALS = new Set<TrainingModalKey>([
  'language-settings',
  'account',
  'thinking-coins',
  'update-log',
  'october-update',
  'login',
])
const TRAINING_MODAL_OWNER = 'AppSidebarTrainingModals'

function closeTrainingHostModals(): void {
  showUserSettingsModal.value = false
  showThinkingCoinsModal.value = false
  showUpdateLogModal.value = false
  showOctoberUpdate.value = false
  showLoginModal.value = false
}

if (!inline) {
  eventBus.onWithOwner(
    'training:modal_open_requested',
    ({ key }) => {
      if (TRAINING_HOST_MODALS.has(key as TrainingModalKey)) {
        openTrainingModal(key as TrainingModalKey)
      }
    },
    TRAINING_MODAL_OWNER
  )
  eventBus.onWithOwner(
    'training:modal_close_requested',
    () => {
      closeTrainingHostModals()
    },
    TRAINING_MODAL_OWNER
  )
}

const {
  visible: showLogoQrScan,
  onPointerEnter: onLogoPointerEnter,
  onPointerLeave: onLogoPointerLeave,
  close: closeLogoQrScan,
  clearHoverCloseTimer,
  scheduleHoverClose,
} = useLogoSiteQrHover(() => !collapsed.value)

function onLogoClick(): void {
  if (showLogoQrScan.value) {
    return
  }
  sidebar.handleLogoClick()
}

watch(collapsed, (isClosed) => {
  if (isClosed) {
    closeLogoQrScan()
  }
})

const releaseModalLocks = [
  registerTrainingUiLock({
    key: 'account',
    scope: lockScope,
    isOpen: () => showUserSettingsModal.value && userSettingsTab.value === 'account',
    setOpen: (open: boolean) => {
      if (open) sidebar.openAccountModal()
      else showUserSettingsModal.value = false
    },
  }),
  registerTrainingUiLock({
    key: 'language-settings',
    scope: lockScope,
    isOpen: () => showUserSettingsModal.value && userSettingsTab.value === 'language',
    setOpen: (open: boolean) => {
      if (open) sidebar.openLanguageSettingsModal()
      else showUserSettingsModal.value = false
    },
  }),
  registerTrainingUiLock({
    key: 'update-log',
    scope: lockScope,
    isOpen: () => showUpdateLogModal.value,
    setOpen: (open: boolean) => {
      showUpdateLogModal.value = open
    },
  }),
  registerTrainingUiLock({
    key: 'october-update',
    scope: lockScope,
    isOpen: () => showOctoberUpdate.value,
    setOpen: (open: boolean) => {
      showOctoberUpdate.value = open
    },
  }),
  registerTrainingUiLock({
    key: 'thinking-coins',
    scope: lockScope,
    isOpen: () => showThinkingCoinsModal.value,
    setOpen: (open: boolean) => {
      if (open) sidebar.openThinkingCoinsModal()
      else showThinkingCoinsModal.value = false
    },
  }),
  registerTrainingUiLock({
    key: 'login',
    scope: lockScope,
    isOpen: () => showLoginModal.value,
    setOpen: (open: boolean) => {
      if (open) sidebar.openLoginModal()
      else showLoginModal.value = false
    },
  }),
]

onBeforeUnmount(() => {
  if (!inline) eventBus.removeAllListenersForOwner(TRAINING_MODAL_OWNER)
  for (const release of releaseModalLocks) release()
})
</script>

<template>
  <div
    class="app-sidebar bg-stone-50 flex flex-col h-full min-h-0 shrink-0 overflow-hidden"
    :class="
      collapsed
        ? 'w-0 min-w-0 max-w-0 border-transparent pointer-events-none'
        : 'w-[var(--mg-sidebar-width)] border-r border-stone-200'
    "
    :aria-hidden="collapsed"
  >
    <!-- Header: brand + collapse (expand when hidden is on the active page) -->
    <div
      class="sidebar-header flex items-center justify-between gap-2 border-b border-stone-200 min-w-0"
      :class="brandHeaderLayout === 'compact' ? 'px-4 py-3' : 'px-4 py-2.5'"
    >
      <div class="brand-block min-w-0 flex-1">
        <div
          class="logo-link flex items-center min-w-0 cursor-pointer hover:opacity-80 transition-opacity"
          :class="brandHeaderLayout === 'compact' ? 'gap-2' : 'gap-2.5'"
          @pointerenter="onLogoPointerEnter"
          @pointerleave="onLogoPointerLeave"
          @click="onLogoClick"
        >
          <div
            class="brand-logo bg-stone-900 flex items-center justify-center text-white font-semibold shrink-0"
            :class="
              brandHeaderLayout === 'compact'
                ? 'w-7 h-7 rounded-lg text-sm'
                : 'w-10 h-10 rounded-xl text-lg'
            "
            aria-hidden="true"
          >
            M
          </div>
          <span
            v-if="brandHeaderLayout === 'compact'"
            class="brand-title font-semibold text-lg text-stone-900 tracking-tight max-w-full"
          >
            <I18nText k="sidebar.brandTitle" />
          </span>
          <div
            v-else
            class="brand-text flex flex-col items-start justify-center min-w-0 flex-1 text-left leading-none gap-0"
          >
            <span
              class="brand-title font-semibold text-lg text-stone-900 tracking-tight max-w-full"
            >
              <I18nText k="sidebar.brandTitle" />
            </span>
            <span
              v-if="isAuthenticated && orgEditionLabel"
              class="brand-subtitle text-xs text-stone-500 max-w-full -mt-px"
              :title="orgEditionTooltip || undefined"
            >
              <I18nText
                v-if="brandSubtitleKind === 'org_edition' && orgEditionParams"
                k="sidebar.orgEdition"
                :params="orgEditionParams"
              />
              <I18nText
                v-else
                k="sidebar.personalEdition"
              />
            </span>
          </div>
        </div>
      </div>
      <el-button
        text
        circle
        size="small"
        class="sidebar-header-collapse shrink-0"
        :title="sidebar.t('sidebar.collapseSidebar')"
        :aria-label="sidebar.t('sidebar.collapseSidebar')"
        @click.stop="toggleCollapsed()"
      >
        <PanelLeftClose class="w-[18px] h-[18px]" />
      </el-button>
    </div>

    <AppSidebarNav />
    <AppSidebarAccountFooter />

    <!-- Modals -->
    <UserSettingsModal
      v-model:visible="showUserSettingsModal"
      :initial-tab="userSettingsTab"
      @success="authStore.checkAuth()"
    />
    <LoginModal v-model:visible="showLoginModal" />
    <UpdateLogModal v-model:visible="showUpdateLogModal" />
    <OctoberUpdateModal v-model:visible="showOctoberUpdate" />
    <ThinkingCoinsModal
      v-model:visible="showThinkingCoinsModal"
      :initial-tab="thinkingCoinsModalTab"
    />
    <LogoQrScanModal
      :visible="showLogoQrScan"
      @close="closeLogoQrScan"
      @hover-enter="clearHoverCloseTimer"
      @hover-leave="scheduleHoverClose"
    />
  </div>
</template>

<style scoped>
.app-sidebar {
  transition:
    width 300ms ease-in-out,
    min-width 300ms ease-in-out,
    max-width 300ms ease-in-out,
    border-color 300ms ease-in-out;
}

.logo-link {
  text-decoration: none;
}

.logo-link:hover {
  text-decoration: none;
}

.sidebar-header-collapse {
  --el-button-text-color: #57534e;
  --el-button-hover-text-color: #1c1917;
  --el-button-hover-bg-color: #f5f5f4;
}

.brand-title,
.brand-subtitle {
  overflow: hidden;
  max-width: 100%;
}

.brand-title :deep(.i18n-label),
.brand-subtitle :deep(.i18n-label) {
  max-width: 100%;
}

.brand-title :deep(.i18n-label__primary),
.brand-title :deep(.i18n-label__secondary),
.brand-subtitle :deep(.i18n-label__primary),
.brand-subtitle :deep(.i18n-label__secondary) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
