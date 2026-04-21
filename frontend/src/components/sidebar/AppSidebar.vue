<script setup lang="ts">
/**
 * AppSidebar - Collapsible sidebar with inline accordion panels
 * Each module can expand its history panel below; only one panel open at a time.
 * Workshop mode hides admin items and fills remaining space.
 */
import { provide } from 'vue'

import { ElButton } from 'element-plus'
import { PanelLeftClose } from 'lucide-vue-next'

import { AccountInfoModal, LoginModal, UpdateLogModal } from '@/components/auth'
import LanguageSettingsModal from '@/components/settings/LanguageSettingsModal.vue'
import { appSidebarInjectionKey, useAppSidebar } from '@/composables/sidebar/useAppSidebar'

import AppSidebarAccountFooter from './AppSidebarAccountFooter.vue'
import AppSidebarNav from './AppSidebarNav.vue'

const sidebar = useAppSidebar()
provide(appSidebarInjectionKey, sidebar)

const {
  isCollapsed,
  showLanguageSettingsModal,
  showLoginModal,
  showAccountModal,
  showUpdateLogModal,
  authStore,
} = sidebar
</script>

<template>
  <div
    class="app-sidebar bg-stone-50 flex flex-col h-full shrink-0 overflow-hidden"
    :class="
      isCollapsed
        ? 'w-0 min-w-0 max-w-0 border-transparent pointer-events-none'
        : 'w-64 border-r border-stone-200'
    "
    :aria-hidden="isCollapsed"
  >
    <!-- Header: brand + collapse (expand when hidden is on the active page) -->
    <div class="p-4 flex items-center justify-between gap-2 border-b border-stone-200">
      <div
        class="logo-link flex items-center space-x-2 min-w-0 cursor-pointer hover:opacity-80 transition-opacity"
        @click="sidebar.handleLogoClick"
      >
        <div
          class="w-7 h-7 bg-stone-900 rounded-lg flex items-center justify-center text-white font-semibold text-sm shrink-0"
        >
          M
        </div>
        <span class="font-semibold text-lg text-stone-900 tracking-tight truncate">{{
          sidebar.t('sidebar.brandTitle')
        }}</span>
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

</style>

<style>
/* Global styles for user dropdown popper - arrow on right side */
.user-dropdown-popper .el-popper__arrow {
  left: auto !important;
  right: 16px !important;
}
</style>
