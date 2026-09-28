<script setup lang="ts">
/**
 * 系统设置 → 全国数据中心 — embeds the China-map dashboard in-panel.
 * Super-admin only (`tab.settings.public_dashboard`).
 */
import { computed } from 'vue'

import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import PublicDashboardPage from '@/pages/PublicDashboardPage.vue'

const { canViewSettingsSubtab } = useAdminAccess()

const canAccess = computed(() => canViewSettingsSubtab('public_dashboard'))
</script>

<template>
  <div
    v-if="!canAccess"
    class="public-dash-admin"
  >
    <el-alert
      type="error"
      :closable="false"
      show-icon
    >
      <template #title><I18nText k="admin.publicDashboard.accessDeniedTitle" /></template>
      <I18nText k="admin.publicDashboard.accessDeniedHint" />
    </el-alert>
  </div>
  <div
    v-else
    class="public-dash-embed"
  >
    <PublicDashboardPage />
  </div>
</template>

<style scoped>
.public-dash-admin {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.public-dash-embed {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
}
</style>
