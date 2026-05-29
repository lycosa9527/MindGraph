<script setup lang="ts">
/**
 * Users tab — global admin list or org-scoped school users.
 */
import { computed } from 'vue'

import AdminUsersTab from '@/components/admin/AdminUsersTab.vue'
import SchoolDashboardUsersTab from '@/components/school/SchoolDashboardUsersTab.vue'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { useAuthStore } from '@/stores'

const { can, effectiveOrgId, isReadOnly } = useAdminAccess()
const authStore = useAuthStore()

const useOrgUsers = computed(
  () =>
    can('scope.org') ||
    authStore.isSchoolAdmin ||
    (authStore.isSuperAdmin && effectiveOrgId.value != null)
)

const orgId = computed(() => effectiveOrgId.value)
</script>

<template>
  <SchoolDashboardUsersTab
    v-if="useOrgUsers && orgId != null"
    :org-id="orgId"
  />
  <AdminUsersTab v-else-if="can('tab.users.view')" />
  <div v-else class="text-center py-12 text-gray-500">—</div>
</template>
