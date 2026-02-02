<script setup lang="ts">
/**
 * GewePage - Gewe WeChat Integration Panel
 * Admin-only page for managing Gewe WeChat login and settings
 *
 * Security: Backend verification ensures only admins can access this page.
 * Frontend checks are for UX only - backend will reject unauthorized requests.
 */
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import GeweLoginComponent from '@/components/admin/GeweLoginComponent.vue'
import { useNotifications } from '@/composables'
import { useAuthStore } from '@/stores'
import apiClient from '@/utils/apiClient'

const router = useRouter()
const authStore = useAuthStore()
const notify = useNotifications()

const isVerifying = ref(true)
const hasAccess = ref(false)

// Verify admin access with backend on mount
onMounted(async () => {
  // Frontend check (can be bypassed, but provides immediate feedback)
  if (!authStore.isAdmin) {
    router.push({ name: 'MindMate' })
    return
  }

  // Backend verification (cannot be bypassed)
  try {
    const response = await apiClient.get('/api/gewe/config/status')
    if (response.ok) {
      hasAccess.value = true
    } else {
      // Backend rejected - user is not admin
      notify.error('访问被拒绝：需要管理员权限')
      router.push({ name: 'MindMate' })
    }
  } catch (error) {
    // Network error or unauthorized
    console.error('Failed to verify admin access:', error)
    notify.error('无法验证管理员权限')
    router.push({ name: 'MindMate' })
  } finally {
    isVerifying.value = false
  }
})
</script>

<template>
  <div class="gewe-page flex-1 flex flex-col bg-stone-50 overflow-hidden">
    <div class="gewe-header h-14 px-4 flex items-center bg-white border-b border-stone-200">
      <h1 class="text-sm font-semibold text-stone-900">Gewe</h1>
    </div>
    <div
      v-if="isVerifying"
      class="gewe-content flex-1 flex items-center justify-center"
    >
      <div class="text-center text-gray-500">
        <div class="text-lg mb-2">验证权限中...</div>
        <div class="text-sm">正在确认管理员访问权限</div>
      </div>
    </div>
    <div
      v-else-if="hasAccess"
      class="gewe-content flex-1 overflow-y-auto px-6 pt-6 pb-6"
    >
      <GeweLoginComponent />
    </div>
  </div>
</template>

<style scoped>
.gewe-page {
  min-height: 0;
}

.gewe-content {
  min-height: 0;
}
</style>
