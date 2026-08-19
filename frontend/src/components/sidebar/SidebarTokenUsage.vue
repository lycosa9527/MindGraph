<script setup lang="ts">
/**
 * Daily token usage under the sidebar user name when the poem is off.
 */
import { computed, onMounted } from 'vue'

import { useLanguage } from '@/composables/core/useLanguage'
import { useAuthStore } from '@/stores/auth'
import { formatSidebarDailyTokens } from '@/utils/formatSidebarDailyTokens'

const authStore = useAuthStore()
const { t } = useLanguage()

onMounted(() => {
  void authStore.refreshUserProfile({ bypassThrottle: true })
})

const usageLine = computed(() => {
  const tokens = authStore.user?.dailyTokens
  const usage = formatSidebarDailyTokens(tokens?.usedToday ?? 0, tokens?.cap ?? 0)
  return t('sidebar.tokenUsageToday', { usage })
})
</script>

<template>
  <div
    class="sidebar-token-usage mt-0.5 min-w-0 max-w-full truncate"
    :title="usageLine"
  >
    {{ usageLine }}
  </div>
</template>

<style scoped>
.sidebar-token-usage {
  font-size: 0.75rem;
  line-height: 1.125rem;
  color: #78716c;
}
</style>
