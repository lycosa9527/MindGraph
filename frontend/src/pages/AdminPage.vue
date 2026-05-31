<script setup lang="ts">
/**
 * Admin Page — unified management panel; tab navigation lives in the sidebar.
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { Plus } from '@element-plus/icons-vue'

import SchoolDashboardOrgPicker from '@/components/school/SchoolDashboardOrgPicker.vue'
import AdminDataCenterTab from '@/components/admin/AdminDataCenterTab.vue'
import AdminInviteUsersTab from '@/components/admin/AdminInviteUsersTab.vue'
import AdminMarketsTab from '@/components/admin/AdminMarketsTab.vue'
import AdminSchoolsTab from '@/components/admin/AdminSchoolsTab.vue'
import AdminFeatureDevTab from '@/components/admin/AdminFeatureDevTab.vue'
import AdminSystemSettingsTab from '@/components/admin/AdminSystemSettingsTab.vue'
import AdminFeaturesHeaderToolbar from '@/components/admin/AdminFeaturesHeaderToolbar.vue'
import AdminRolesHeaderToolbar from '@/components/admin/AdminRolesHeaderToolbar.vue'
import AdminUsersHeaderToolbar from '@/components/admin/AdminUsersHeaderToolbar.vue'
import AdminUsersPanel from '@/components/admin/AdminUsersPanel.vue'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import {
  defaultDataCenterView,
  isDataCenterView,
} from '@/composables/admin/adminDataCenterViews'
import { LEGACY_FEATURE_DEV_SETTINGS_SUBTABS } from '@/composables/admin/adminFeatureDevNav'
import { requestOpenSchoolAddMemberDialog } from '@/composables/school/useSchoolDashboardAddMemberHeader'
import { useSchoolDashboardOrgPicker } from '@/composables/school/useSchoolDashboardOrgPicker'
import { useAdminHeaderBreadcrumb } from '@/composables/admin/useAdminHeaderBreadcrumb'
import { useAdminPanelTabs } from '@/composables/admin/useAdminPanelTabs'
import { useLanguage } from '@/composables'
import { useAuthStore } from '@/stores'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { t } = useLanguage()
const { can, canEditTab, isTabReadOnly, loadCapabilities, isReadOnly } = useAdminAccess()
const {
  effectiveOrgId: schoolDashboardOrgId,
  loadOrganizations: loadSchoolDashboardOrganizations,
  syncSelectedOrgFromUser: syncSchoolDashboardOrg,
} = useSchoolDashboardOrgPicker()
const { tabs } = useAdminPanelTabs({ loadOnMount: false })

const activeTab = ref((route.query.tab as string) || 'data_center')
const invitesTabRef = ref<InstanceType<typeof AdminInviteUsersTab> | null>(null)

const hasGlobalScope = computed(() => can('scope.global'))

const headerBreadcrumb = useAdminHeaderBreadcrumb({
  activeTab,
  route,
  tabs,
  hasGlobalScope,
})

const showSchoolDashboardPicker = computed(
  () =>
    activeTab.value === 'data_center' &&
    route.query.view === 'school_dashboard' &&
    can('scope.global')
)

const showSchoolAddMemberButton = computed(
  () =>
    activeTab.value === 'data_center' &&
    route.query.view === 'school_dashboard' &&
    schoolDashboardOrgId.value != null &&
    !isReadOnly.value &&
    (can('tab.users.edit') ||
      (can('scope.org') && (can('tab.school_dashboard.view') || can('tab.data_center.view'))))
)

const showSchoolsCreateButton = computed(
  () =>
    activeTab.value === 'invites' &&
    canEditTab('invites') &&
    (can('scope.global') || can('scope.invited_orgs'))
)

const showFeaturesApplyButton = computed(
  () =>
    activeTab.value === 'settings' &&
    route.query.subtab === 'features' &&
    canEditTab('settings')
)

const showRolesHeaderToolbar = computed(
  () => activeTab.value === 'settings' && route.query.subtab === 'roles' && can('tab.settings.roles')
)

const showTabReadOnlyBadge = computed(() => isTabReadOnly(activeTab.value))

function onHeaderCreateSchool(): void {
  invitesTabRef.value?.openCreateModal()
}

function onHeaderAddSchoolMember(): void {
  requestOpenSchoolAddMemberDialog()
}

watch(
  () => [activeTab.value, route.query.view] as const,
  ([tab, view]) => {
    if (tab === 'data_center' && view === 'school_dashboard') {
      syncSchoolDashboardOrg()
      void loadSchoolDashboardOrganizations()
    }
  },
  { immediate: true }
)

watch(
  () => route.query.tab,
  (tab) => {
    if (tab && typeof tab === 'string') {
      activeTab.value = tab
    }
  }
)

watch(
  () => [route.query.tab, route.query.subtab] as const,
  ([tab, subtab]) => {
    if (
      tab === 'settings' &&
      typeof subtab === 'string' &&
      LEGACY_FEATURE_DEV_SETTINGS_SUBTABS.includes(subtab)
    ) {
      void router.replace({
        query: { ...route.query, tab: 'feature_dev', subtab },
      })
      return
    }
    if (tab === 'feature_dev' && subtab === 'features') {
      void router.replace({
        query: { ...route.query, tab: 'settings', subtab: 'features' },
      })
    }
  },
  { immediate: true }
)

watch(activeTab, (tab) => {
  const current = route.query.tab as string
  const query: Record<string, string | string[]> = { ...route.query, tab }
  if (tab !== 'settings' && tab !== 'feature_dev') {
    delete query.subtab
    delete query.role_tab
  }
  if (tab !== 'data_center') {
    delete query.view
  } else if (typeof query.view !== 'string' || !isDataCenterView(query.view)) {
    query.view = defaultDataCenterView(can('scope.global') && can('tab.data_center.view'))
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
      <nav
        aria-label="breadcrumb"
        class="admin-breadcrumb flex-1 text-sm truncate min-w-0"
      >
        <template
          v-for="(segment, index) in headerBreadcrumb"
          :key="index"
        >
          <span
            v-if="index > 0"
            class="admin-breadcrumb-sep"
            aria-hidden="true"
          >
            /
          </span>
          <span
            :class="
              index === headerBreadcrumb.length - 1
                ? 'admin-breadcrumb-current font-semibold text-gray-900'
                : 'admin-breadcrumb-parent text-gray-500'
            "
          >
            {{ segment.label }}
          </span>
        </template>
        <span
          v-if="showTabReadOnlyBadge"
          class="text-gray-400 font-normal ml-2"
        >
          ({{ t('admin.readOnly') }})
        </span>
      </nav>
      <div class="admin-header-actions flex flex-1 items-center justify-end gap-3 min-w-0">
        <AdminFeaturesHeaderToolbar v-if="showFeaturesApplyButton" />
        <AdminRolesHeaderToolbar v-if="showRolesHeaderToolbar" />
        <AdminUsersHeaderToolbar v-if="activeTab === 'users'" />
        <SchoolDashboardOrgPicker
          v-if="showSchoolDashboardPicker"
          compact
        />
        <el-button
          v-if="showSchoolAddMemberButton"
          type="primary"
          size="small"
          class="admin-add-member-btn shrink-0"
          @click="onHeaderAddSchoolMember"
        >
          <el-icon class="mr-1"><Plus /></el-icon>
          {{ t('admin.schoolAddMemberButton') }}
        </el-button>
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
    </div>

    <div class="admin-body flex-1 overflow-y-auto">
      <div class="admin-content px-6 py-6">
        <AdminDataCenterTab
          v-if="activeTab === 'data_center'"
          :read-only="isTabReadOnly('data_center')"
        />
        <AdminUsersPanel v-else-if="activeTab === 'users'" :read-only="isTabReadOnly('users')" />
        <AdminSchoolsTab
          v-else-if="activeTab === 'organizations'"
          :read-only="isTabReadOnly('organizations')"
        />
        <AdminInviteUsersTab
          v-else-if="activeTab === 'invites'"
          ref="invitesTabRef"
        />
        <AdminMarketsTab v-else-if="activeTab === 'billing'" />
        <AdminFeatureDevTab v-else-if="activeTab === 'feature_dev'" />
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

.admin-breadcrumb {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  gap: 6px;
}

.admin-breadcrumb-sep {
  color: #d6d3d1;
  font-weight: 300;
  user-select: none;
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

.admin-add-member-btn {
  --el-button-bg-color: #1c1917;
  --el-button-border-color: #1c1917;
  --el-button-text-color: #fafaf9;
  --el-button-hover-bg-color: #292524;
  --el-button-hover-border-color: #292524;
  --el-button-hover-text-color: #fafaf9;
  --el-button-active-bg-color: #44403c;
  --el-button-active-border-color: #44403c;
  font-weight: 500;
  border-radius: 9999px;
}
</style>
