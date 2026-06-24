<script setup lang="ts">
/**
 * Thinking coins upgrade landing page — wallet + subscription reference.
 * Route: /thinking-coins/upgrade
 */
import { onMounted } from 'vue'

import ThinkingCoinsUpgradePanel from '@/components/auth/ThinkingCoinsUpgradePanel.vue'
import { useLanguage } from '@/composables'
import { useAuthStore } from '@/stores'

const { t } = useLanguage()
const authStore = useAuthStore()

onMounted(() => {
  void authStore.checkAuth(true)
})
</script>

<template>
  <div class="thinking-coins-upgrade-page flex min-h-0 flex-1 flex-col overflow-hidden bg-stone-50">
    <header
      class="thinking-coins-upgrade-header flex h-14 shrink-0 items-center border-b border-stone-200 bg-white px-4"
    >
      <h1 class="text-sm font-semibold text-stone-900">
        {{ t('thinkingCoins.upgradePageTitle') }}
      </h1>
    </header>

    <div class="min-h-0 flex-1 overflow-y-auto">
      <ThinkingCoinsUpgradePanel />
    </div>
  </div>
</template>
