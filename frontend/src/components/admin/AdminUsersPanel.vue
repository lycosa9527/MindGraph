<script setup lang="ts">
/**
 * Users tab — global user management (superadmin / teaching researcher read-only).
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import AdminUsersTab from '@/components/admin/AdminUsersTab.vue'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { useLanguage } from '@/composables'

const props = defineProps<{
  readOnly?: boolean
}>()

const { t } = useLanguage()
const router = useRouter()
const { can } = useAdminAccess()

const canManageUsers = computed(() => can('tab.users.view') && can('scope.global'))
const showSchoolDashboardHint = computed(
  () => !canManageUsers.value && can('scope.org') && can('tab.school_dashboard.view')
)
const panelReadOnly = computed(() => props.readOnly ?? !can('tab.users.edit'))

function goToSchoolDashboard(): void {
  void router.push({ path: '/admin', query: { tab: 'data_center', view: 'school_dashboard' } })
}
</script>

<template>
  <AdminUsersTab
    v-if="canManageUsers"
    :read-only="panelReadOnly"
  />
  <div
    v-else-if="showSchoolDashboardHint"
    class="text-center py-12 px-4 text-gray-600 space-y-3"
  >
    <p>{{ t('admin.usersTabSchoolDashboardHint') }}</p>
    <el-button
      type="primary"
      plain
      @click="goToSchoolDashboard"
    >
      {{ t('admin.schoolDashboard') }}
    </el-button>
  </div>
  <div
    v-else
    class="text-center py-12 text-gray-500"
  >
    —
  </div>
</template>
