<script setup lang="ts">
/**
 * System settings — roles, database, performance, and integrations.
 */
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AdminCosTab from '@/components/admin/AdminCosTab.vue'
import AdminDatabaseTab from '@/components/admin/AdminDatabaseTab.vue'
import AdminErrorsTab from '@/components/admin/AdminErrorsTab.vue'
import AdminFeaturesTab from '@/components/admin/AdminFeaturesTab.vue'
import AdminLibraryTab from '@/components/admin/AdminLibraryTab.vue'
import AdminPerformanceTab from '@/components/admin/AdminPerformanceTab.vue'
import AdminPublicDashboardTab from '@/components/admin/AdminPublicDashboardTab.vue'
import AdminRolesTab from '@/components/admin/AdminRolesTab.vue'
import AdminThinkingCoinsTab from '@/components/admin/AdminThinkingCoinsTab.vue'
import GeweLoginComponent from '@/components/admin/GeweLoginComponent.vue'
import {
  type SettingsSubtab,
  defaultSettingsSubtab,
  isSettingsSubtab,
  visibleSettingsSubtabs,
} from '@/composables/admin/adminSettingsNav'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { useFeatureFlags } from '@/composables/core/useFeatureFlags'

const route = useRoute()
const router = useRouter()
const { canViewSettingsSubtab } = useAdminAccess()
const { featureGewe, featureLibrary } = useFeatureFlags()

const activeSubtab = ref<SettingsSubtab>(
  isSettingsSubtab(route.query.subtab as string)
    ? (route.query.subtab as SettingsSubtab)
    : defaultSettingsSubtab()
)

const allowedSubtabs = computed(() =>
  visibleSettingsSubtabs({
    canViewSettingsSubtab,
    featureGewe: featureGewe.value,
    featureLibrary: featureLibrary.value,
  })
)

watch(
  () => route.query.subtab,
  (sub) => {
    if (sub && typeof sub === 'string' && isSettingsSubtab(sub)) {
      activeSubtab.value = sub
    }
  }
)

watch(activeSubtab, (sub) => {
  const current = route.query.subtab as string
  if (sub !== current) {
    const query: Record<string, string | string[]> = {
      ...route.query,
      tab: 'settings',
      subtab: sub,
    }
    if (sub !== 'roles') {
      delete query.role_tab
    }
    router.replace({ query })
  }
})

watch(
  allowedSubtabs,
  (names) => {
    if (names.length > 0 && !names.includes(activeSubtab.value)) {
      activeSubtab.value = names[0]
    }
  },
  { immediate: true }
)
</script>

<template>
  <div
    class="embedded-settings-body"
    :class="{ 'embedded-settings-body--fullscreen': activeSubtab === 'public_dashboard' }"
  >
    <AdminFeaturesTab v-if="activeSubtab === 'features'" />
    <AdminRolesTab v-else-if="activeSubtab === 'roles'" />
    <AdminLibraryTab v-else-if="activeSubtab === 'library'" />
    <AdminDatabaseTab v-else-if="activeSubtab === 'database'" />
    <AdminCosTab v-else-if="activeSubtab === 'cos'" />
    <AdminPerformanceTab v-else-if="activeSubtab === 'performance'" />
    <AdminErrorsTab v-else-if="activeSubtab === 'errors'" />
    <AdminThinkingCoinsTab v-else-if="activeSubtab === 'thinking_coins'" />
    <AdminPublicDashboardTab v-else-if="activeSubtab === 'public_dashboard'" />
    <GeweLoginComponent v-else-if="activeSubtab === 'gewe'" />
  </div>
</template>

<style scoped>
.embedded-settings-body--fullscreen {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 0;
}
</style>
