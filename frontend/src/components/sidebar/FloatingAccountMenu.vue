<script setup lang="ts">
/**
 * Same account dropdown as the sidebar footer, for pages that do not mount
 * that sidebar (full-bleed admin views). A collapsed sidebar takes its chip
 * with it. Not used on canvas.
 */
import { provide } from 'vue'

import { LoginModal, ProductRoadmapModal } from '@/components/auth'
import UserSettingsModal from '@/components/settings/UserSettingsModal.vue'
import { appSidebarInjectionKey, useAppSidebar } from '@/composables/sidebar/useAppSidebar'

import AppSidebarAccountFooter from './AppSidebarAccountFooter.vue'

const sidebar = useAppSidebar()
provide(appSidebarInjectionKey, sidebar)

const { showUserSettingsModal, userSettingsTab, showLoginModal, showProductRoadmapModal, authStore } =
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
    <ProductRoadmapModal v-model:visible="showProductRoadmapModal" />
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
