<script setup lang="ts">
/**
 * MindGraph App Component
 * Handles dynamic layout switching based on route meta
 */
import { computed, defineAsyncComponent, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'

import { ElMessage } from 'element-plus'

import { LoginModal } from '@/components/auth'
import VersionNotification from '@/components/common/VersionNotification.vue'
import { useLanguage } from '@/composables'
import { useAuthStore, useUIStore } from '@/stores'

const route = useRoute()
const uiStore = useUIStore()
const authStore = useAuthStore()
const { isZh } = useLanguage()

// Dynamically import layouts
const layouts = {
  default: defineAsyncComponent(() => import('@/layouts/DefaultLayout.vue')),
  editor: defineAsyncComponent(() => import('@/layouts/EditorLayout.vue')),
  admin: defineAsyncComponent(() => import('@/layouts/AdminLayout.vue')),
  auth: defineAsyncComponent(() => import('@/layouts/AuthLayout.vue')),
  main: defineAsyncComponent(() => import('@/layouts/MainLayout.vue')),
  canvas: defineAsyncComponent(() => import('@/layouts/CanvasLayout.vue')),
}

// Get current layout based on route meta
const currentLayout = computed(() => {
  const layoutName = (route.meta.layout as keyof typeof layouts) || 'default'
  return layouts[layoutName] || layouts.default
})

// Apply theme class to document
watch(
  () => uiStore.isDark,
  (isDark) => {
    document.documentElement.classList.toggle('dark', isDark)
  },
  { immediate: true }
)

// Handle successful login after session expired
function handleSessionExpiredLoginSuccess() {
  authStore.closeSessionExpiredModal()
  ElMessage.success(isZh.value ? '登录成功' : 'Login successful')
}

// Check auth status on mount and show AI disclaimer
onMounted(async () => {
  await authStore.checkAuth()

  // Show AI content disclaimer
  setTimeout(() => {
    ElMessage({
      message: isZh.value
        ? '内容由AI生成，请仔细甄别'
        : 'Content is AI-generated, please verify carefully',
      type: 'info',
      duration: 3000,
      showClose: true,
    })
  }, 500)
})
</script>

<template>
  <component :is="currentLayout">
    <router-view v-slot="{ Component }">
      <transition
        name="fade"
        mode="out-in"
      >
        <component :is="Component" />
      </transition>
    </router-view>
  </component>

  <!-- Global version update notification -->
  <VersionNotification />

  <!-- Global session expired login modal -->
  <LoginModal
    v-model:visible="authStore.showSessionExpiredModal"
    @success="handleSessionExpiredLoginSuccess"
  />
</template>

<style>
/* Global styles */
html,
body {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family:
    'Inter',
    system-ui,
    -apple-system,
    sans-serif;
}

#app {
  height: 100%;
}

/* Page transition */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

/* Dark mode support */
.dark {
  color-scheme: dark;
}
</style>
