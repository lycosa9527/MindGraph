<script setup lang="ts">
/**
 * Admin Page — unified management panel; tab navigation lives in the sidebar.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { Plus } from '@element-plus/icons-vue'

import AdminDataCenterTab from '@/components/admin/AdminDataCenterTab.vue'
import AdminInviteUsersTab from '@/components/admin/AdminInviteUsersTab.vue'
import AdminMarketsTab from '@/components/admin/AdminMarketsTab.vue'
import AdminSchoolsTab from '@/components/admin/AdminSchoolsTab.vue'
import AdminSystemSettingsTab from '@/components/admin/AdminSystemSettingsTab.vue'
import AdminUsersPanel from '@/components/admin/AdminUsersPanel.vue'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import {
  DATA_CENTER_VIEWS,
  defaultDataCenterView,
  isDataCenterView,
} from '@/composables/admin/adminDataCenterViews'
import { useAdminPanelTabs } from '@/composables/admin/useAdminPanelTabs'
import { useLanguage } from '@/composables'
import { useAuthStore } from '@/stores'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { t } = useLanguage()
const { can, loadCapabilities, isReadOnly } = useAdminAccess()
const { tabs } = useAdminPanelTabs({ loadOnMount: false })

const activeTab = ref((route.query.tab as string) || 'data_center')
const schoolsTabRef = ref<InstanceType<typeof AdminSchoolsTab> | null>(null)

const activeDataCenterViewLabel = computed(() => {
  if (activeTab.value !== 'data_center') {
    return null
  }
  const raw = route.query.view
  const viewKey =
    typeof raw === 'string' && isDataCenterView(raw)
      ? raw
      : defaultDataCenterView(can('scope.global'))
  const match = DATA_CENTER_VIEWS.find((view) => view.name === viewKey)
  return match ? t(match.labelKey) : null
})

const activeTabLabel = computed(() => {
  if (activeDataCenterViewLabel.value) {
    return activeDataCenterViewLabel.value
  }
  const match = tabs.value.find((tab) => tab.name === activeTab.value)
  return match?.label ?? t('admin.title')
})

const showSchoolsCreateButton = computed(
  () =>
    authStore.isAdmin &&
    activeTab.value === 'organizations' &&
    can('tab.organizations.edit')
)

function onHeaderCreateSchool(): void {
  schoolsTabRef.value?.openCreateModal()
}

watch(
  () => route.query.tab,
  (tab) => {
    if (tab && typeof tab === 'string') {
      activeTab.value = tab
    }
  }
)

watch(activeTab, (tab) => {
  const current = route.query.tab as string
  const query: Record<string, string | string[]> = { ...route.query, tab }
  if (tab !== 'settings') {
    delete query.subtab
  }
  if (tab !== 'data_center') {
    delete query.view
  } else if (typeof query.view !== 'string' || !isDataCenterView(query.view)) {
    query.view = defaultDataCenterView(can('scope.global'))
  }
  if (tab !== current || route.query.view !== query.view) {
    router.replace({ query })
  }
})

watch(
  () => tabs.value.map((tab) => tab.name),
  (names) => {
    if (names.length === 0) {
      return
    }
    if (!names.includes(activeTab.value)) {
      activeTab.value = names[0]
      void router.replace({ query: { ...route.query, tab: names[0] } })
    }
  },
  { immediate: true }
)

onMounted(async () => {
  await loadCapabilities()
})
</script>

<template>
  <div class="admin-page flex-1 flex flex-col bg-gray-50 overflow-hidden">
    <div
      class="admin-header h-14 px-4 flex items-center justify-between gap-3 bg-white border-b border-gray-200 shrink-0"
    >
      <h1 class="text-sm font-semibold text-gray-900 truncate min-w-0">
        {{ activeTabLabel }}
        <span v-if="isReadOnly" class="text-gray-400 font-normal ml-2">
          ({{ t('admin.readOnly') }})
        </span>
      </h1>
      <el-button
        v-if="showSchoolsCreateButton"
        size="small"
        class="admin-new-school-btn shrink-0"
        @click="onHeaderCreateSchool"
      >
        <el-icon class="mr-1"><Plus /></el-icon>
        {{ t('admin.createSchool') }}
      </el-button>
    </div>

    <div class="admin-body flex-1 overflow-y-auto">
      <div
        class="admin-content"
        :class="
          activeTab === 'data_center' && route.query.view === 'school_dashboard'
            ? 'px-0 py-0'
            : 'px-6 py-6'
        "
      >
        <AdminDataCenterTab v-if="activeTab === 'data_center'" :read-only="isReadOnly" />
        <AdminUsersPanel v-else-if="activeTab === 'users'" />
        <AdminSchoolsTab
          v-else-if="activeTab === 'organizations'"
          ref="schoolsTabRef"
        />
        <AdminInviteUsersTab v-else-if="activeTab === 'invites'" />
        <AdminMarketsTab v-else-if="activeTab === 'billing'" />
        <AdminSystemSettingsTab v-else-if="activeTab === 'settings'" />
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

.admin-new-school-btn {
  --el-button-bg-color: #e7e5e4;
  --el-button-border-color: #d6d3d1;
  --el-button-hover-bg-color: #d6d3d1;
  --el-button-hover-border-color: #a8a29e;
  --el-button-hover-text-color: #1c1917;
  --el-button-active-bg-color: #a8a29e;
  --el-button-active-border-color: #78716c;
  --el-button-text-color: #1c1917;
  font-weight: 500;
  border-radius: 9999px;
}
</style>
