<script setup lang="ts">
/**
 * Organization name under the sidebar user name.
 */
import { computed } from 'vue'

import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

const orgName = computed(() => authStore.user?.schoolName?.trim() ?? '')
</script>

<template>
  <div
    v-if="orgName"
    class="sidebar-org-name mt-0.5 min-w-0 max-w-full truncate"
    :title="orgName"
  >
    {{ orgName }}
  </div>
</template>

<style scoped>
.sidebar-org-name {
  font-size: 0.75rem;
  line-height: 1.125rem;
  color: #78716c;
}
</style>
