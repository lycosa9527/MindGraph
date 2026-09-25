<script setup lang="ts">
/**
 * Same account dropdown as the sidebar footer, for pages that do not show
 * that footer (canvas, collapsed sidebar, full-bleed admin views).
 */
import { provide } from 'vue'

import { AccountInfoModal, LoginModal, UpdateLogModal } from '@/components/auth'
import LanguageSettingsModal from '@/components/settings/LanguageSettingsModal.vue'
import { appSidebarInjectionKey, useAppSidebar } from '@/composables/sidebar/useAppSidebar'

import AppSidebarAccountFooter from './AppSidebarAccountFooter.vue'

const sidebar = useAppSidebar()
provide(appSidebarInjectionKey, sidebar)

const {
  showLanguageSettingsModal,
  showLoginModal,
  showAccountModal,
  showUpdateLogModal,
  authStore,
} = sidebar
</script>

<template>
  <div
    class="floating-account-menu"
    data-testid="floating-account-menu"
  >
    <AppSidebarAccountFooter menu-only />
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
.floating-account-menu {
  position: fixed;
  z-index: 40;
  left: 12px;
  bottom: 56px;
}
</style>
