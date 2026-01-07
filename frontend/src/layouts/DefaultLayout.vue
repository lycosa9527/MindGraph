<script setup lang="ts">
/**
 * Default Layout - Header + main content
 */
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import { useLanguage } from '@/composables'
import { useAuthStore, useUIStore } from '@/stores'

const router = useRouter()
const authStore = useAuthStore()
const uiStore = useUIStore()
const { t } = useLanguage()

const isAuthenticated = computed(() => authStore.isAuthenticated)
const userName = computed(() => authStore.user?.username || '')

async function handleLogout(): Promise<void> {
  await authStore.logout()
}

function goToHome(): void {
  router.push('/')
}

function goToAdmin(): void {
  router.push('/admin')
}
</script>

<template>
  <div class="default-layout min-h-screen flex flex-col">
    <!-- Header -->
    <header
      class="header h-14 bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-4 flex items-center justify-between"
    >
      <div class="flex items-center gap-4">
        <h1 class="text-xl font-semibold text-gray-800 dark:text-white">MindGraph Pro</h1>
      </div>

      <div class="flex items-center gap-4">
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
        <template v-if="isAuthenticated">
          <el-dropdown trigger="click">
            <el-button>
              {{ userName }}
              <el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="goToHome">
                  {{ t('editor.newDiagram') }}
                </el-dropdown-item>
                <el-dropdown-item
                  v-if="authStore.isAdmin"
                  @click="goToAdmin"
                >
                  Admin
                </el-dropdown-item>
                <el-dropdown-item
                  divided
                  @click="handleLogout"
                >
                  {{ t('auth.logout') }}
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
        <template v-else>
          <el-button
            type="primary"
            @click="router.push('/login')"
          >
            {{ t('auth.login') }}
          </el-button>
        </template>
      </div>
    </header>

    <!-- Main Content -->
    <main class="flex-1 bg-gray-50 dark:bg-gray-900">
      <slot />
    </main>
  </div>
</template>

<style scoped>
.default-layout {
  --header-height: 56px;
}

.header {
  position: sticky;
  top: 0;
  z-index: 100;
}
</style>
