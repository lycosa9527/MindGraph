<script setup lang="ts">
/**
 * System settings — roles, database, performance, and integrations.
 */
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AdminErrorsTab from '@/components/admin/AdminErrorsTab.vue'
import AdminDatabaseTab from '@/components/admin/AdminDatabaseTab.vue'
import AdminFeaturesTab from '@/components/admin/AdminFeaturesTab.vue'
import AdminLibraryTab from '@/components/admin/AdminLibraryTab.vue'
import AdminPerformanceTab from '@/components/admin/AdminPerformanceTab.vue'
import AdminRolesTab from '@/components/admin/AdminRolesTab.vue'
import GeweLoginComponent from '@/components/admin/GeweLoginComponent.vue'
import {
  defaultSettingsSubtab,
  isSettingsSubtab,
  type SettingsSubtab,
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
    const query: Record<string, string | string[]> = { ...route.query, tab: 'settings', subtab: sub }
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
  <div class="embedded-settings-body">
    <AdminFeaturesTab v-if="activeSubtab === 'features'" />
    <AdminRolesTab v-else-if="activeSubtab === 'roles'" />
    <AdminLibraryTab v-else-if="activeSubtab === 'library'" />
    <AdminDatabaseTab v-else-if="activeSubtab === 'database'" />
    <AdminPerformanceTab v-else-if="activeSubtab === 'performance'" />
    <AdminErrorsTab v-else-if="activeSubtab === 'errors'" />
    <GeweLoginComponent v-else-if="activeSubtab === 'gewe'" />
  </div>
</template>
