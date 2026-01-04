<script setup lang="ts">
/**
 * Admin Page - Admin dashboard with tabs
 */
import { onMounted, ref } from 'vue'

import { useNotifications } from '@/composables'

const _authStore = undefined // Reserved for future admin auth checks
const notify = useNotifications()

const activeTab = ref('dashboard')
const isLoading = ref(false)

// Dashboard stats
const stats = ref({
  totalUsers: 0,
  activeToday: 0,
  totalDiagrams: 0,
  apiCalls: 0,
})

// Tabs configuration
const tabs = [
  { name: 'dashboard', label: 'Dashboard', icon: 'DataAnalysis' },
  { name: 'users', label: 'Users', icon: 'User' },
  { name: 'schools', label: 'Schools', icon: 'School' },
  { name: 'tokens', label: 'Tokens', icon: 'Ticket' },
  { name: 'apikeys', label: 'API Keys', icon: 'Key' },
  { name: 'logs', label: 'Logs', icon: 'Document' },
  { name: 'announcements', label: 'Announcements', icon: 'Bell' },
]

async function loadDashboardStats() {
  isLoading.value = true
  try {
    // TODO: Fetch real stats from API
    stats.value = {
      totalUsers: 1250,
      activeToday: 89,
      totalDiagrams: 15420,
      apiCalls: 45678,
    }
  } catch {
    notify.error('Failed to load dashboard stats')
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  loadDashboardStats()
})
</script>

<template>
  <div class="admin-page">
    <!-- Tabs -->
    <el-tabs
      v-model="activeTab"
      class="admin-tabs"
    >
      <el-tab-pane
        v-for="tab in tabs"
        :key="tab.name"
        :name="tab.name"
        :label="tab.label"
      >
        <template #label>
          <span class="flex items-center gap-2">
            <el-icon><component :is="tab.icon" /></el-icon>
            <span>{{ tab.label }}</span>
          </span>
        </template>
      </el-tab-pane>
    </el-tabs>

    <!-- Content -->
    <div class="admin-content mt-6">
      <!-- Dashboard Tab -->
      <template v-if="activeTab === 'dashboard'">
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <!-- Total Users -->
          <el-card
            shadow="hover"
            class="stat-card"
          >
            <div class="flex items-center gap-4">
              <div
                class="w-12 h-12 bg-primary-100 dark:bg-primary-900 rounded-lg flex items-center justify-center"
              >
                <el-icon
                  :size="24"
                  class="text-primary-500"
                  ><User
                /></el-icon>
              </div>
              <div>
                <p class="text-sm text-gray-500 dark:text-gray-400">Total Users</p>
                <p class="text-2xl font-bold text-gray-800 dark:text-white">
                  {{ stats.totalUsers.toLocaleString() }}
                </p>
              </div>
            </div>
          </el-card>

          <!-- Active Today -->
          <el-card
            shadow="hover"
            class="stat-card"
          >
            <div class="flex items-center gap-4">
              <div
                class="w-12 h-12 bg-green-100 dark:bg-green-900 rounded-lg flex items-center justify-center"
              >
                <el-icon
                  :size="24"
                  class="text-green-500"
                  ><TrendCharts
                /></el-icon>
              </div>
              <div>
                <p class="text-sm text-gray-500 dark:text-gray-400">Active Today</p>
                <p class="text-2xl font-bold text-gray-800 dark:text-white">
                  {{ stats.activeToday }}
                </p>
              </div>
            </div>
          </el-card>

          <!-- Total Diagrams -->
          <el-card
            shadow="hover"
            class="stat-card"
          >
            <div class="flex items-center gap-4">
              <div
                class="w-12 h-12 bg-purple-100 dark:bg-purple-900 rounded-lg flex items-center justify-center"
              >
                <el-icon
                  :size="24"
                  class="text-purple-500"
                  ><Document
                /></el-icon>
              </div>
              <div>
                <p class="text-sm text-gray-500 dark:text-gray-400">Total Diagrams</p>
                <p class="text-2xl font-bold text-gray-800 dark:text-white">
                  {{ stats.totalDiagrams.toLocaleString() }}
                </p>
              </div>
            </div>
          </el-card>

          <!-- API Calls -->
          <el-card
            shadow="hover"
            class="stat-card"
          >
            <div class="flex items-center gap-4">
              <div
                class="w-12 h-12 bg-orange-100 dark:bg-orange-900 rounded-lg flex items-center justify-center"
              >
                <el-icon
                  :size="24"
                  class="text-orange-500"
                  ><Connection
                /></el-icon>
              </div>
              <div>
                <p class="text-sm text-gray-500 dark:text-gray-400">API Calls</p>
                <p class="text-2xl font-bold text-gray-800 dark:text-white">
                  {{ stats.apiCalls.toLocaleString() }}
                </p>
              </div>
            </div>
          </el-card>
        </div>

        <!-- Charts placeholder -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
          <el-card shadow="hover">
            <template #header>
              <div class="flex items-center justify-between">
                <span class="font-medium">User Activity</span>
                <el-button text>View All</el-button>
              </div>
            </template>
            <div class="h-64 flex items-center justify-center text-gray-400">
              <p>Chart placeholder - User activity over time</p>
            </div>
          </el-card>

          <el-card shadow="hover">
            <template #header>
              <div class="flex items-center justify-between">
                <span class="font-medium">Diagram Types</span>
                <el-button text>View All</el-button>
              </div>
            </template>
            <div class="h-64 flex items-center justify-center text-gray-400">
              <p>Chart placeholder - Diagram type distribution</p>
            </div>
          </el-card>
        </div>
      </template>

      <!-- Users Tab -->
      <template v-else-if="activeTab === 'users'">
        <el-card shadow="never">
          <template #header>
            <div class="flex items-center justify-between">
              <span class="font-medium">User Management</span>
              <el-button
                type="primary"
                size="small"
              >
                <el-icon class="mr-1"><Plus /></el-icon>
                Add User
              </el-button>
            </div>
          </template>
          <div class="text-center py-12 text-gray-400">
            <el-icon :size="48"><User /></el-icon>
            <p class="mt-4">User management interface will be implemented here</p>
          </div>
        </el-card>
      </template>

      <!-- Other tabs placeholder -->
      <template v-else>
        <el-card shadow="never">
          <div class="text-center py-12 text-gray-400">
            <el-icon :size="48"><Setting /></el-icon>
            <p class="mt-4">{{ activeTab }} management interface</p>
          </div>
        </el-card>
      </template>
    </div>
  </div>
</template>

<style scoped>
.admin-page {
  max-width: 1400px;
  margin: 0 auto;
}

.stat-card :deep(.el-card__body) {
  padding: 20px;
}

.admin-tabs :deep(.el-tabs__header) {
  margin-bottom: 0;
}

.admin-tabs :deep(.el-tabs__nav-wrap::after) {
  display: none;
}
</style>
