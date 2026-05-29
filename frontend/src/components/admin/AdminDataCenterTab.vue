<script setup lang="ts">
/**
 * Data center tab — operations, usage, or school dashboard views.
 */
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import AdminDashboardTab from '@/components/admin/AdminDashboardTab.vue'
import AdminOrgDataCenterPanel from '@/components/admin/AdminOrgDataCenterPanel.vue'
import SchoolDashboardPage from '@/pages/SchoolDashboardPage.vue'
import {
  defaultDataCenterView,
  isDataCenterView,
  type DataCenterView,
} from '@/composables/admin/adminDataCenterViews'
import { useAdminOrgContext } from '@/composables/admin/useAdminOrgContext'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { useLanguage } from '@/composables'
import { useAuthStore } from '@/stores'
import { apiRequest } from '@/utils/apiClient'

const props = defineProps<{
  readOnly?: boolean
}>()

const route = useRoute()
const { t } = useLanguage()
const authStore = useAuthStore()
const { can, effectiveOrgId, isReadOnly } = useAdminAccess()
const { selectedOrgId, routeOrgId, GLOBAL_ORG_SENTINEL } = useAdminOrgContext()

const organizations = ref<{ id: number; name: string; code: string }[]>([])

const dataCenterViewQuery = computed((): DataCenterView | null => {
  const raw = route.query.view
  if (typeof raw === 'string' && isDataCenterView(raw)) {
    return raw
  }
  return null
})

const showGlobalView = computed(() => {
  if (can('scope.org')) {
    return false
  }
  if (dataCenterViewQuery.value === 'operations' && can('scope.global')) {
    return true
  }
  if (can('scope.global') && authStore.isSuperAdmin && routeOrgId.value != null) {
    return false
  }
  return can('scope.global')
})

const dataCenterView = computed((): DataCenterView => {
  if (dataCenterViewQuery.value != null) {
    return dataCenterViewQuery.value
  }
  return defaultDataCenterView(showGlobalView.value)
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

const showOrgPicker = computed(
  () =>
    authStore.isSuperAdmin &&
    organizations.value.length > 0 &&
    dataCenterView.value === 'usage'
)

async function loadOrganizations(): Promise<void> {
  if (!authStore.isSuperAdmin) {
    return
  }
  const res = await apiRequest('/api/auth/admin/organizations')
  if (!res.ok) {
    return
  }
  const data = await res.json()
  organizations.value = data.map((o: { id: number; name: string; code: string }) => ({
    id: o.id,
    name: o.name,
    code: o.code,
  }))
}

onMounted(() => {
  void loadOrganizations()
})
</script>

<template>
  <div>
    <div
      v-if="showOrgPicker"
      class="mb-4 flex items-center gap-2"
    >
      <span class="text-sm text-gray-500">{{ t('admin.viewSchool') }}:</span>
      <el-select
        v-model="selectedOrgId"
        filterable
        :placeholder="t('admin.selectSchool')"
        size="small"
        style="width: 280px"
      >
        <el-option
          :label="t('admin.dataCenterGlobal')"
          :value="GLOBAL_ORG_SENTINEL"
        />
        <el-option
          v-for="org in organizations"
          :key="org.id"
          :label="org.name"
          :value="org.id"
        />
      </el-select>
    </div>

    <SchoolDashboardPage
      v-if="dataCenterView === 'school_dashboard'"
      embedded
    />

    <AdminDashboardTab
      v-else-if="showGlobalView"
      :section="dashboardSection"
    />

    <AdminOrgDataCenterPanel
      v-else-if="activeOrgId != null"
      :org-id="activeOrgId"
      :read-only="panelReadOnly"
      :section="dashboardSection"
    />

    <div v-else class="text-center py-16 text-gray-500">
      {{ t('admin.schoolDashboardNoOrg') }}
    </div>
  </div>
</template>
