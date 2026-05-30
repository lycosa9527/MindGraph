<script setup lang="ts">
/**
 * Users tab — global user management (superadmin / platform_bd read-only).
 */
import { computed } from 'vue'

import AdminUsersTab from '@/components/admin/AdminUsersTab.vue'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'

const props = defineProps<{
  readOnly?: boolean
}>()

const { can } = useAdminAccess()

const canManageUsers = computed(() => can('tab.users.view') && can('scope.global'))
const panelReadOnly = computed(() => props.readOnly ?? !can('tab.users.edit'))
</script>

<template>
  <AdminUsersTab v-if="canManageUsers" :read-only="panelReadOnly" />
  <div
    v-else
    class="text-center py-12 text-gray-500"
  >
    —
  </div>
</template>
