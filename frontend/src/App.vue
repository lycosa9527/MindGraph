<script setup lang="ts">
/**
 * MindGraph App Component
 * Handles dynamic layout switching based on route meta
 */
import { computed, defineAsyncComponent, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { LoginModal } from '@/components/auth'
import VersionNotification from '@/components/common/VersionNotification.vue'
import { useLanguage, useNotifications } from '@/composables'
import { useAuthStore, useUIStore } from '@/stores'

const notify = useNotifications()

const route = useRoute()
const router = useRouter()
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
  // Restore body scroll first
  document.body.style.overflow = ''
  
  // Close the session expired modal
  authStore.closeSessionExpiredModal()
  
  // Check for pending redirect (set when user tries to access protected route)
  const redirectPath = authStore.getAndClearPendingRedirect()
  
  if (redirectPath) {
    // User was trying to access a protected route - navigate to it
    router.push(redirectPath).catch(() => {
      // If push fails, try replace
      router.replace(redirectPath).catch(() => {
        // If replace also fails, reload the page
        window.location.href = redirectPath
      })
    })
  } else {
    // No redirect - stay on current page and refresh to reload data with new auth state
    const currentPath = router.currentRoute.value.fullPath
    router.replace(currentPath).catch(() => {
      // If replace fails, just reload the page to ensure fresh state
      window.location.reload()
    })
  }
  
  // Note: notification is already shown in LoginModal.vue, no need to duplicate here
}

// Check auth status on mount (non-blocking, uses cached state if available)
// Router guard handles auth checks for protected routes
onMounted(async () => {
  // Silently check auth in background - uses cached user if available
  // This ensures user data is loaded for display but doesn't block navigation
  authStore.checkAuth().catch(() => {
    // Ignore errors - router guard will handle auth failures for protected routes
  })

  // Show AI content disclaimer
  setTimeout(() => {
    notify.info(
      isZh.value ? '内容由AI生成，请仔细甄别' : 'Content is AI-generated, please verify carefully'
    )
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
