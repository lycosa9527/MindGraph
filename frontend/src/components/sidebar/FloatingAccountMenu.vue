<script setup lang="ts">
/**
 * Same account dropdown as the sidebar footer, for pages that do not show
 * that footer (collapsed sidebar, full-bleed admin views). Not used on canvas.
 */
import { provide } from 'vue'

import { LoginModal, UpdateLogModal } from '@/components/auth'
import UserSettingsModal from '@/components/settings/UserSettingsModal.vue'
import { appSidebarInjectionKey, useAppSidebar } from '@/composables/sidebar/useAppSidebar'

import AppSidebarAccountFooter from './AppSidebarAccountFooter.vue'

const sidebar = useAppSidebar()
provide(appSidebarInjectionKey, sidebar)

const { showUserSettingsModal, userSettingsTab, showLoginModal, showUpdateLogModal, authStore } =
  sidebar
</script>

<template>
  <div
    class="floating-account-menu"
    data-testid="floating-account-menu"
  >
    <AppSidebarAccountFooter menu-only />
    <UserSettingsModal
      v-model:visible="showUserSettingsModal"
      :initial-tab="userSettingsTab"
      @success="authStore.checkAuth()"
    />
    <LoginModal v-model:visible="showLoginModal" />
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
