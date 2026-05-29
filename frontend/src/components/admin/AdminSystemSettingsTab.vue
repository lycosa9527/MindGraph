<script setup lang="ts">
/**
 * System settings — nested admin tools (legacy tabs).
 */
import type { Component } from 'vue'
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  ChatLineRound,
  Coin,
  Microphone,
  Odometer,
  Reading,
  Setting,
  Ticket,
  UserFilled,
} from '@element-plus/icons-vue'

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

const allSubtabs: ReadonlyArray<{
  name: string
  labelKey: string
  icon: Component
}> = [
  { name: 'features', labelKey: 'admin.featuresTab', icon: Setting },
  { name: 'roles', labelKey: 'admin.roleControl', icon: UserFilled },
  { name: 'tokens', labelKey: 'admin.tokens', icon: Ticket },
  { name: 'library', labelKey: 'admin.library', icon: Reading },
  { name: 'database', labelKey: 'admin.database.tab', icon: Coin },
  { name: 'performance', labelKey: 'admin.performance.tab', icon: Odometer },
  { name: 'gewe', labelKey: 'admin.geweWechat', icon: ChatLineRound },
  { name: 'kitty_llmops', labelKey: 'admin.kittyLlmopsTab', icon: Microphone },
  { name: 'mindbot', labelKey: 'admin.mindbot', icon: Setting },
  { name: 'smart_response', labelKey: 'sidebar.smartResponse', icon: Setting },
  { name: 'teacher_usage', labelKey: 'sidebar.teacherUsage', icon: Setting },
]

const canMindbot = computed(() =>
  userCanAccessMindbotAdmin(
    authStore.isAdmin,
    authStore.isManager,
    authStore.user?.schoolId,
    authStore.user?.id,
    featureMindbot.value,
    featureOrgAccess.value?.feature_mindbot
  )
)

const subtabs = computed(() => {
  let list = allSubtabs.filter((tab) => canViewSettingsSubtab(tab.name))
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
