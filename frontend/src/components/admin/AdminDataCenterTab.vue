<script setup lang="ts">
/**
 * Data center tab — operations, usage, or school dashboard views.
 */
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import AdminDashboardTab from '@/components/admin/AdminDashboardTab.vue'
import AdminOrgDataCenterPanel from '@/components/admin/AdminOrgDataCenterPanel.vue'
import SchoolDashboardPage from '@/pages/SchoolDashboardPage.vue'
import {
  canViewDataCenterSubView,
  defaultDataCenterView,
  isDataCenterView,
  type DataCenterView,
} from '@/composables/admin/adminDataCenterViews'
import { useAdminOrgContext } from '@/composables/admin/useAdminOrgContext'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { useLanguage } from '@/composables'
import { useAuthStore } from '@/stores'

const props = defineProps<{
  readOnly?: boolean
}>()

const route = useRoute()
const { t } = useLanguage()
const authStore = useAuthStore()
const { can, capabilities, effectiveOrgId, isReadOnly } = useAdminAccess()
const { routeOrgId } = useAdminOrgContext()

const hasGlobalDataCenter = computed(
  () => can('scope.global') && can('tab.data_center.view')
)

const dataCenterViewQuery = computed((): DataCenterView | null => {
  const raw = route.query.view
  if (typeof raw === 'string' && isDataCenterView(raw)) {
    return raw
  }
  return null
})

const dataCenterView = computed((): DataCenterView => {
  const fromQuery = dataCenterViewQuery.value
  if (fromQuery != null && canViewDataCenterSubView(fromQuery, capabilities.value)) {
    return fromQuery
  }
  return defaultDataCenterView(hasGlobalDataCenter.value)
})

const showGlobalView = computed(() => {
  if (dataCenterView.value === 'school_dashboard') {
    return false
  }
  if (!can('tab.data_center.view')) {
    return false
  }
  if (can('scope.org')) {
    return false
  }
  if (dataCenterView.value === 'usage' && can('scope.global')) {
    return true
  }
  if (dataCenterViewQuery.value === 'operations' && can('scope.global')) {
    return true
  }
  if (can('scope.global') && authStore.isSuperAdmin && routeOrgId.value != null) {
    return false
  }
  return can('scope.global')
})

const activeOrgId = computed(() => {
  if (can('scope.org')) {
    return effectiveOrgId.value
  }
  if (authStore.isSuperAdmin && routeOrgId.value != null) {
    return routeOrgId.value
  }
  return effectiveOrgId.value
})

const panelReadOnly = computed(() => props.readOnly ?? isReadOnly.value)

const dashboardSection = computed((): 'operations' | 'usage' => {
  return dataCenterView.value === 'usage' ? 'usage' : 'operations'
})

</script>

<template>
  <div>
    <SchoolDashboardPage
      v-if="dataCenterView === 'school_dashboard'"
      embedded
      class="min-w-0"
    />

    <AdminDashboardTab
      v-else-if="showGlobalView"
      :section="dashboardSection"
    />

    <AdminOrgDataCenterPanel
      v-else-if="activeOrgId != null && can('tab.data_center.view')"
      :org-id="activeOrgId"
      :read-only="panelReadOnly"
      :section="dashboardSection"
    />

    <div v-else class="text-center py-16 text-gray-500">
      {{ t('admin.schoolDashboardNoOrg') }}
    </div>
  </div>
</template>
