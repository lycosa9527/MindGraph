<script setup lang="ts">
/**
 * AppSidebar - Collapsible sidebar with inline accordion panels
 * Each module can expand its history panel below; only one panel open at a time.
 * Workshop mode hides admin items and fills remaining space.
 */
import { onBeforeUnmount, onMounted, provide, ref, watch } from 'vue'

import { ElButton } from 'element-plus'

import { PanelLeftClose } from '@lucide/vue'

import { AccountInfoModal, LoginModal, UpdateLogModal } from '@/components/auth'
import LanguageSettingsModal from '@/components/settings/LanguageSettingsModal.vue'
import { appSidebarInjectionKey, useAppSidebar } from '@/composables/sidebar/useAppSidebar'

import AppSidebarAccountFooter from './AppSidebarAccountFooter.vue'
import AppSidebarNav from './AppSidebarNav.vue'
import LogoQrScanModal from './LogoQrScanModal.vue'

const sidebar = useAppSidebar()
provide(appSidebarInjectionKey, sidebar)

const {
  isCollapsed,
  showLanguageSettingsModal,
  showLoginModal,
  showAccountModal,
  showUpdateLogModal,
  authStore,
  isAuthenticated,
  orgEditionLabel,
  orgEditionTooltip,
} = sidebar

const showLogoQrScan = ref(false)
const prefersHover = ref(false)
let hoverOpenTimer: ReturnType<typeof setTimeout> | null = null
let hoverCloseTimer: ReturnType<typeof setTimeout> | null = null

const HOVER_OPEN_DELAY_MS = 1500
const HOVER_CLOSE_DELAY_MS = 250

function clearHoverOpenTimer(): void {
  if (hoverOpenTimer !== null) {
    clearTimeout(hoverOpenTimer)
    hoverOpenTimer = null
  }
}

function clearHoverCloseTimer(): void {
  if (hoverCloseTimer !== null) {
    clearTimeout(hoverCloseTimer)
    hoverCloseTimer = null
  }
}

function scheduleHoverClose(): void {
  if (!prefersHover.value) {
    return
  }
  clearHoverCloseTimer()
  hoverCloseTimer = setTimeout(() => {
    showLogoQrScan.value = false
    hoverCloseTimer = null
  }, HOVER_CLOSE_DELAY_MS)
}

function onLogoPointerEnter(): void {
  if (!prefersHover.value || isCollapsed.value) {
    return
  }
  clearHoverCloseTimer()
  clearHoverOpenTimer()
  hoverOpenTimer = setTimeout(() => {
    showLogoQrScan.value = true
    hoverOpenTimer = null
  }, HOVER_OPEN_DELAY_MS)
}

function onLogoPointerLeave(): void {
  clearHoverOpenTimer()
  if (showLogoQrScan.value) {
    scheduleHoverClose()
  }
}

function closeLogoQrScan(): void {
  clearHoverOpenTimer()
  clearHoverCloseTimer()
  showLogoQrScan.value = false
}

function onLogoClick(): void {
  if (showLogoQrScan.value) {
    return
  }
  sidebar.handleLogoClick()
}

onMounted(() => {
  prefersHover.value = window.matchMedia('(hover: hover) and (pointer: fine)').matches
})

watch(isCollapsed, (collapsed) => {
  if (collapsed) {
    closeLogoQrScan()
  }
})

onBeforeUnmount(() => {
  clearHoverOpenTimer()
  clearHoverCloseTimer()
})
</script>

<template>
  <div
    class="app-sidebar bg-stone-50 flex flex-col h-full shrink-0 overflow-hidden"
    :class="
      isCollapsed
        ? 'w-0 min-w-0 max-w-0 border-transparent pointer-events-none'
        : 'w-[var(--mg-sidebar-width)] border-r border-stone-200'
    "
    :aria-hidden="isCollapsed"
  >
    <!-- Header: brand + collapse (expand when hidden is on the active page) -->
    <div class="sidebar-header px-4 py-2.5 flex items-center justify-between gap-2 border-b border-stone-200 min-w-0">
      <div class="brand-block min-w-0 flex-1">
        <div
          class="logo-link flex items-center gap-2.5 min-w-0 cursor-pointer hover:opacity-80 transition-opacity"
          @pointerenter="onLogoPointerEnter"
          @pointerleave="onLogoPointerLeave"
          @click="onLogoClick"
        >
          <div
            class="brand-logo w-10 h-10 bg-stone-900 rounded-xl flex items-center justify-center text-white font-semibold text-lg shrink-0"
            aria-hidden="true"
          >
            M
          </div>
          <div class="brand-text flex flex-col items-start justify-center min-w-0 flex-1 text-left leading-none gap-0">
            <span class="brand-title font-semibold text-lg text-stone-900 tracking-tight truncate max-w-full">{{
              sidebar.t('sidebar.brandTitle')
            }}</span>
            <span
              v-if="isAuthenticated && orgEditionLabel"
              class="brand-subtitle text-xs text-stone-500 truncate max-w-full -mt-px"
              :title="orgEditionTooltip || undefined"
            >
              {{ orgEditionLabel }}
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
        @click.stop="sidebar.toggleSidebar()"
      >
        <PanelLeftClose class="w-[18px] h-[18px]" />
      </el-button>
    </div>

    <AppSidebarNav />
    <AppSidebarAccountFooter />

    <!-- Modals -->
    <LanguageSettingsModal v-model="showLanguageSettingsModal" />
    <LoginModal v-model:visible="showLoginModal" />
    <AccountInfoModal
      v-model:visible="showAccountModal"
      @success="authStore.checkAuth()"
    />
    <UpdateLogModal v-model:visible="showUpdateLogModal" />
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
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
