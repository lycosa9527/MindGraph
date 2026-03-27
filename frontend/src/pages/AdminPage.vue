<script setup lang="ts">
/**
 * Admin Page - Admin dashboard with tabs
 *
 * Access levels:
 * - Admin: Full access to all organizations' data
 * - Manager: Access to their organization's data only
 */
import type { Component } from 'vue'
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import type { TabsInstance } from 'element-plus'

import {
  ChatLineRound,
  Coin,
  DataAnalysis,
  Reading,
  School,
  Setting,
  Ticket,
  User,
  UserFilled,
} from '@element-plus/icons-vue'

import AdminDashboardTab from '@/components/admin/AdminDashboardTab.vue'
import AdminDatabaseTab from '@/components/admin/AdminDatabaseTab.vue'
import AdminFeaturesTab from '@/components/admin/AdminFeaturesTab.vue'
import AdminLibraryTab from '@/components/admin/AdminLibraryTab.vue'
import AdminRolesTab from '@/components/admin/AdminRolesTab.vue'
import AdminSchoolsTab from '@/components/admin/AdminSchoolsTab.vue'
import AdminTokensTab from '@/components/admin/AdminTokensTab.vue'
import AdminUsersTab from '@/components/admin/AdminUsersTab.vue'
import GeweLoginComponent from '@/components/admin/GeweLoginComponent.vue'
import { useLanguage } from '@/composables'
import { useFeatureFlags } from '@/composables/core/useFeatureFlags'
import { useAuthStore } from '@/stores'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { featureGewe, featureLibrary } = useFeatureFlags()
const { t } = useLanguage()

const activeTab = ref((route.query.tab as string) || 'dashboard')
const tabsRef = ref<TabsInstance>()

const isAdmin = computed(() => authStore.isAdmin)

const allTabsConfig: ReadonlyArray<{
  name: string
  labelKey: string
  icon: Component
  adminOnly: boolean
}> = [
  { name: 'dashboard', labelKey: 'admin.dashboard', icon: DataAnalysis, adminOnly: false },
  { name: 'users', labelKey: 'admin.users', icon: User, adminOnly: false },
  { name: 'schools', labelKey: 'admin.schools', icon: School, adminOnly: true },
  { name: 'roles', labelKey: 'admin.roleControl', icon: UserFilled, adminOnly: true },
  { name: 'tokens', labelKey: 'admin.tokens', icon: Ticket, adminOnly: true },
  { name: 'features', labelKey: 'admin.featuresTab', icon: Setting, adminOnly: true },
  { name: 'library', labelKey: 'admin.library', icon: Reading, adminOnly: true },
  { name: 'database', labelKey: 'admin.database.tab', icon: Coin, adminOnly: true },
  { name: 'gewe', labelKey: 'admin.geweWechat', icon: ChatLineRound, adminOnly: true },
]

const tabs = computed(() => {
  let visible = allTabsConfig
  if (!isAdmin.value) {
    visible = visible.filter((tab) => !tab.adminOnly)
  }
  if (!featureGewe.value) {
    visible = visible.filter((tab) => tab.name !== 'gewe')
  }
  if (!featureLibrary.value) {
    visible = visible.filter((tab) => tab.name !== 'library')
  }
  return visible.map((tab) => ({ ...tab, label: t(tab.labelKey) }))
})

watch(
  () => route.query.tab,
  (tab) => {
    if (tab && typeof tab === 'string') {
      activeTab.value = tab
    }
  }
)

function scheduleTabBarUpdate(): void {
  void nextTick(() => {
    tabsRef.value?.tabNavRef?.tabBarRef?.update()
  })
}

watch(activeTab, (tab) => {
  const current = route.query.tab as string
  if (tab !== current) {
    router.replace({ query: { ...route.query, tab } })
  }
  scheduleTabBarUpdate()
})

watch(() => tabs.value.map((tab) => `${tab.name}:${tab.label}`).join('|'), scheduleTabBarUpdate)

watch(
  () => tabs.value.map((tab) => tab.name),
  (names) => {
    if (!names.includes(activeTab.value)) {
      activeTab.value = 'dashboard'
      void router.replace({ query: { ...route.query, tab: 'dashboard' } })
    }
  },
  { immediate: true }
)

onMounted(scheduleTabBarUpdate)
</script>

<template>
  <div class="admin-page flex-1 flex flex-col bg-gray-50 overflow-hidden">
    <div
      class="admin-header h-14 px-4 flex items-center justify-between bg-white border-b border-gray-200"
    >
      <h1 class="text-sm font-semibold text-gray-900">
        {{ isAdmin ? t('admin.title') : t('admin.orgManagement') }}
      </h1>
    </div>

    <div class="admin-body flex-1 overflow-y-auto">
      <div class="px-6 pt-4 pb-6">
        <el-tabs
          ref="tabsRef"
          v-model="activeTab"
          class="admin-tabs"
        >
          <el-tab-pane
            v-for="tab in tabs"
            :key="tab.name"
            :name="tab.name"
          >
            <template #label>
              <span class="flex items-center gap-2">
                <el-icon><component :is="tab.icon" /></el-icon>
                <span>{{ tab.label }}</span>
              </span>
            </template>
          </el-tab-pane>
        </el-tabs>

        <div class="admin-content mt-6">
          <template v-if="activeTab === 'dashboard'">
            <AdminDashboardTab />
          </template>

          <template v-else-if="activeTab === 'users'">
            <AdminUsersTab />
          </template>

          <template v-else-if="activeTab === 'schools'">
            <AdminSchoolsTab />
          </template>

          <template v-else-if="activeTab === 'roles'">
            <AdminRolesTab />
          </template>

          <template v-else-if="activeTab === 'tokens'">
            <AdminTokensTab />
          </template>

          <template v-else-if="activeTab === 'features'">
            <AdminFeaturesTab />
          </template>

          <template v-else-if="activeTab === 'library'">
            <AdminLibraryTab />
          </template>

          <template v-else-if="activeTab === 'database'">
            <AdminDatabaseTab />
          </template>

          <template v-else-if="activeTab === 'gewe'">
            <GeweLoginComponent />
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.admin-page {
  min-height: 0;
}

.admin-body {
  min-height: 0;
}

.admin-page .admin-content {
  max-width: 1400px;
  margin: 0 auto;
}

.admin-tabs :deep(.el-tabs__header) {
  margin-bottom: 0;
}

.admin-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}
</style>
