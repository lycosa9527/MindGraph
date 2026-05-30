<script setup lang="ts">
/**
 * System settings — nested admin tools (legacy tabs).
 */
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AdminDatabaseTab from '@/components/admin/AdminDatabaseTab.vue'
import AdminFeaturesTab from '@/components/admin/AdminFeaturesTab.vue'
import AdminKittyLlmopsTab from '@/components/admin/AdminKittyLlmopsTab.vue'
import AdminLibraryTab from '@/components/admin/AdminLibraryTab.vue'
import AdminMindBotTab from '@/components/admin/AdminMindBotTab.vue'
import AdminPerformanceTab from '@/components/admin/AdminPerformanceTab.vue'
import AdminRolesTab from '@/components/admin/AdminRolesTab.vue'
import AdminTokensTab from '@/components/admin/AdminTokensTab.vue'
import GeweLoginComponent from '@/components/admin/GeweLoginComponent.vue'
import SmartResponsePanel from '@/components/admin/SmartResponsePanel.vue'
import TeacherUsagePanel from '@/components/admin/TeacherUsagePanel.vue'
import { ADMIN_SETTINGS_SUBTAB_CONFIG } from '@/composables/admin/adminSettingsSubtabs'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { useLanguage } from '@/composables'
import { useFeatureFlags } from '@/composables/core/useFeatureFlags'
import { userCanAccessMindbotAdmin } from '@/utils/mindbotAccess'
import { useAuthStore } from '@/stores'

const route = useRoute()
const router = useRouter()
const { t } = useLanguage()
const authStore = useAuthStore()
const { canViewSettingsSubtab } = useAdminAccess()
const { featureGewe, featureLibrary, featureMindbot, featureOrgAccess } = useFeatureFlags()

const activeSubtab = ref((route.query.subtab as string) || 'features')

const canMindbot = computed(() => {
  if (!featureMindbot.value) {
    return false
  }
  return userCanAccessMindbotAdmin(
    authStore.isAdmin,
    authStore.isManager,
    authStore.user?.schoolId,
    authStore.user?.id,
    featureOrgAccess.value?.feature_mindbot
  )
})

const subtabs = computed(() => {
  let list = ADMIN_SETTINGS_SUBTAB_CONFIG.filter((tab) => canViewSettingsSubtab(tab.name))
  if (!featureGewe.value) {
    list = list.filter((tab) => tab.name !== 'gewe')
  }
  if (!featureLibrary.value) {
    list = list.filter((tab) => tab.name !== 'library')
  }
  if (!canMindbot.value) {
    list = list.filter((tab) => tab.name !== 'mindbot')
  }
  return list.map((tab) => ({ ...tab, label: t(tab.labelKey) }))
})

watch(
  () => route.query.subtab,
  (sub) => {
    if (sub && typeof sub === 'string') {
      activeSubtab.value = sub
    }
  }
)

watch(activeSubtab, (sub) => {
  const current = route.query.subtab as string
  if (sub !== current) {
    router.replace({ query: { ...route.query, tab: 'settings', subtab: sub } })
  }
})

watch(
  () => subtabs.value.map((tab) => tab.name),
  (names) => {
    if (names.length > 0 && !names.includes(activeSubtab.value)) {
      activeSubtab.value = names[0]
    }
  },
  { immediate: true }
)
</script>

<template>
  <div>
    <el-tabs v-model="activeSubtab" class="admin-settings-tabs">
      <el-tab-pane
        v-for="tab in subtabs"
        :key="tab.name"
        :name="tab.name"
        :label="tab.label"
      />
    </el-tabs>

    <div class="mt-4 embedded-settings-body">
      <AdminFeaturesTab v-if="activeSubtab === 'features'" />
      <AdminRolesTab v-else-if="activeSubtab === 'roles'" />
      <AdminTokensTab v-else-if="activeSubtab === 'tokens'" />
      <AdminLibraryTab v-else-if="activeSubtab === 'library'" />
      <AdminDatabaseTab v-else-if="activeSubtab === 'database'" />
      <AdminPerformanceTab v-else-if="activeSubtab === 'performance'" />
      <GeweLoginComponent v-else-if="activeSubtab === 'gewe'" />
      <AdminKittyLlmopsTab v-else-if="activeSubtab === 'kitty_llmops'" />
      <AdminMindBotTab v-else-if="activeSubtab === 'mindbot'" />
      <SmartResponsePanel v-else-if="activeSubtab === 'smart_response'" />
      <TeacherUsagePanel v-else-if="activeSubtab === 'teacher_usage'" />
    </div>
  </div>
</template>

<style scoped>
.embedded-settings-body :deep(.smart-response-page),
.embedded-settings-body :deep(.teacher-usage-page) {
  padding: 0;
}
</style>
