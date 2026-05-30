<script setup lang="ts">
/**
 * Users tab — superadmin global user management only.
 */
import { computed } from 'vue'

import AdminUsersTab from '@/components/admin/AdminUsersTab.vue'
import { useAdminAccess } from '@/composables/admin/useAdminAccess'

const { can } = useAdminAccess()

const canManageUsers = computed(() => can('tab.users.view') && can('scope.global'))
</script>

<template>
  <AdminUsersTab v-if="canManageUsers" />
  <div
    v-else
    class="text-center py-12 text-gray-500"
  >
    —
  </div>
</template>
