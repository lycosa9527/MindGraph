<script setup lang="ts">
/**
 * Admin Layout - Sidebar navigation with main content area
 */
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useLanguage } from '@/composables'
import { useAuthStore, useUIStore } from '@/stores'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const uiStore = useUIStore()
const { t } = useLanguage()

const sidebarCollapsed = ref(false)

const menuItems = computed(() => [
  { key: 'dashboard', icon: 'DataAnalysis', label: 'Dashboard', path: '/admin' },
  { key: 'users', icon: 'User', label: 'Users', path: '/admin/users' },
  { key: 'schools', icon: 'School', label: 'Schools', path: '/admin/schools' },
  { key: 'tokens', icon: 'Ticket', label: 'Tokens', path: '/admin/tokens' },
  { key: 'apikeys', icon: 'Key', label: 'API Keys', path: '/admin/apikeys' },
  { key: 'logs', icon: 'Document', label: 'Logs', path: '/admin/logs' },
  { key: 'announcements', icon: 'Bell', label: 'Announcements', path: '/admin/announcements' },
])

const activeMenu = computed(() => route.path)

function handleMenuSelect(path: string) {
  router.push(path)
}

function goToHome() {
  router.push('/')
}

async function handleLogout() {
  await authStore.logout()
  router.push('/login')
}

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}
</script>

<template>
  <div class="admin-layout h-screen flex overflow-hidden">
    <!-- Sidebar -->
    <aside
      class="sidebar flex flex-col bg-gray-800 dark:bg-gray-900 text-white transition-all duration-300"
      :class="sidebarCollapsed ? 'w-16' : 'w-60'"
    >
      <!-- Logo -->
      <div class="h-14 flex items-center justify-center border-b border-gray-700">
        <h1
          v-if="!sidebarCollapsed"
          class="text-lg font-semibold"
        >
          MindGraph Admin
        </h1>
        <span
          v-else
          class="text-xl font-bold"
          >MG</span
        >
      </div>

      <!-- Navigation -->
      <nav class="flex-1 py-4 overflow-y-auto">
        <ul class="space-y-1 px-2">
          <li
            v-for="item in menuItems"
            :key="item.key"
          >
            <button
              class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors"
              :class="
                activeMenu === item.path
                  ? 'bg-primary-600 text-white'
                  : 'text-gray-300 hover:bg-gray-700 hover:text-white'
              "
              @click="handleMenuSelect(item.path)"
            >
              <el-icon :size="20">
                <component :is="item.icon" />
              </el-icon>
              <span
                v-if="!sidebarCollapsed"
                class="text-sm"
                >{{ item.label }}</span
              >
            </button>
          </li>
        </ul>
      </nav>

      <!-- Bottom Actions -->
      <div class="p-4 border-t border-gray-700 space-y-2">
        <button
          class="w-full flex items-center gap-3 px-3 py-2 text-gray-300 hover:text-white hover:bg-gray-700 rounded-lg transition-colors"
          @click="goToHome"
        >
          <el-icon :size="18"><Edit /></el-icon>
          <span
            v-if="!sidebarCollapsed"
            class="text-sm"
            >Back to Editor</span
          >
        </button>
        <button
          class="w-full flex items-center gap-3 px-3 py-2 text-gray-300 hover:text-white hover:bg-gray-700 rounded-lg transition-colors"
          @click="toggleSidebar"
        >
          <el-icon :size="18">
            <Fold v-if="!sidebarCollapsed" />
            <Expand v-else />
          </el-icon>
          <span
            v-if="!sidebarCollapsed"
            class="text-sm"
            >Collapse</span
          >
        </button>
      </div>
    </aside>

    <!-- Main Content -->
    <div class="flex-1 flex flex-col overflow-hidden">
      <!-- Header -->
      <header
        class="h-14 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 flex items-center justify-between"
      >
        <div class="flex items-center gap-4">
          <h2 class="text-lg font-medium text-gray-800 dark:text-white">Admin Panel</h2>
        </div>

        <div class="flex items-center gap-3">
          <!-- Theme Toggle -->
          <el-button
            circle
            @click="uiStore.toggleTheme"
          >
            <el-icon>
              <Sunny v-if="uiStore.isDark" />
              <Moon v-else />
            </el-icon>
          </el-button>

          <!-- Language Toggle -->
          <el-button
            circle
            @click="uiStore.toggleLanguage"
          >
            {{ uiStore.language === 'zh' ? 'EN' : '中' }}
          </el-button>

          <!-- User Menu -->
          <el-dropdown trigger="click">
            <el-button>
              {{ authStore.user?.username || 'Admin' }}
              <el-icon class="ml-1"><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="goToHome">
                  <el-icon><Edit /></el-icon>
                  Editor
                </el-dropdown-item>
                <el-dropdown-item
                  divided
                  @click="handleLogout"
                >
                  <el-icon><SwitchButton /></el-icon>
                  {{ t('auth.logout') }}
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <!-- Page Content -->
      <main class="flex-1 overflow-auto bg-gray-50 dark:bg-gray-900 p-6">
        <slot />
      </main>
    </div>
  </div>
</template>

<style scoped>
.admin-layout {
  --sidebar-width: 240px;
  --header-height: 56px;
}

.sidebar {
  flex-shrink: 0;
}
</style>
