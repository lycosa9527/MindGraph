<script setup lang="ts">
/**
 * AppSidebar - Collapsible sidebar with inline accordion panels
 * Each module can expand its history panel below; only one panel open at a time.
 * Workshop mode hides admin items and fills remaining space.
 */
import { provide } from 'vue'

import { Menu } from 'lucide-vue-next'

import { AccountInfoModal, ChangePasswordModal, LoginModal } from '@/components/auth'
import LanguageSettingsModal from '@/components/settings/LanguageSettingsModal.vue'
import { appSidebarInjectionKey, useAppSidebar } from '@/composables/sidebar/useAppSidebar'

import AppSidebarAccountFooter from './AppSidebarAccountFooter.vue'
import AppSidebarNav from './AppSidebarNav.vue'

const sidebar = useAppSidebar()
provide(appSidebarInjectionKey, sidebar)

const {
  showLanguageSettingsModal,
  showLoginModal,
  showAccountModal,
  showPasswordModal,
  authStore,
} = sidebar
</script>

<template>
  <div
    class="app-sidebar bg-stone-50 border-r border-stone-200 flex flex-col transition-all duration-300 ease-in-out h-full"
    :class="sidebar.isCollapsed ? 'w-16' : 'w-64'"
  >
    <!-- Header with logo and toggle -->
    <div class="p-4 flex items-center justify-between border-b border-stone-200">
      <div
        class="logo-link flex items-center space-x-2 cursor-pointer hover:opacity-80 transition-opacity"
        @click="sidebar.handleLogoClick"
      >
        <div
          class="w-7 h-7 bg-stone-900 rounded-lg flex items-center justify-center text-white font-semibold text-sm"
        >
          M
        </div>
        <span
          v-if="!sidebar.isCollapsed"
          class="font-semibold text-lg text-stone-900 tracking-tight"
          >{{ sidebar.t('sidebar.brandTitle') }}</span
        >
      </div>
      <el-button
        text
        circle
        class="toggle-btn"
        :title="
          sidebar.isCollapsed
            ? sidebar.t('sidebar.expandSidebar')
            : sidebar.t('sidebar.collapseSidebar')
        "
        @click="sidebar.toggleSidebar"
      >
        <Menu class="w-4 h-4" />
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
    <ChangePasswordModal v-model:visible="showPasswordModal" />
  </div>
</template>

<style scoped>
.logo-link {
  text-decoration: none;
}

.logo-link:hover {
  text-decoration: none;
}

/* Toggle buttons */
.toggle-btn {
  --el-button-text-color: #78716c;
  --el-button-hover-text-color: #1c1917;
  --el-button-hover-bg-color: #e7e5e4;
}
</style>

<style>
/* Global styles for user dropdown popper - arrow on right side */
.user-dropdown-popper .el-popper__arrow {
  left: auto !important;
  right: 16px !important;
}
</style>
