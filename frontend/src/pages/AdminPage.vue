<script setup lang="ts">
/**
 * Admin Page - Admin dashboard with tabs
 *
 * Access levels:
 * - Admin: Full access to all organizations' data
 * - Manager: Access to their organization's data only
 */
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import { useLanguage, useNotifications } from '@/composables'
import { useAuthStore } from '@/stores'
import GeweLoginComponent from '@/components/admin/GeweLoginComponent.vue'

const route = useRoute()
const authStore = useAuthStore()
const { isZh } = useLanguage()
const notify = useNotifications()

const activeTab = ref((route.query.tab as string) || 'dashboard')
const isLoading = ref(false)
const isLoadingTokens = ref(false)

// Role-based access
const isAdmin = computed(() => authStore.isAdmin)
const isManager = computed(() => authStore.isManager)
const userOrg = computed(() => authStore.user?.schoolName || 'Unknown Organization')

// Dashboard stats
const stats = ref({
  totalUsers: 0,
  activeToday: 0,
  totalDiagrams: 0,
  apiCalls: 0,
})

// Token stats with service breakdown
interface TokenPeriodStats {
  input_tokens: number
  output_tokens: number
  total_tokens: number
  request_count?: number
}

interface ServiceStats {
  today: TokenPeriodStats
  week: TokenPeriodStats
  month: TokenPeriodStats
  total: TokenPeriodStats
}

interface TokenStats {
  today: TokenPeriodStats
  past_week: TokenPeriodStats
  past_month: TokenPeriodStats
  total: TokenPeriodStats
  by_service: {
    mindgraph: ServiceStats
    mindmate: ServiceStats
  }
}

const tokenStats = ref<TokenStats | null>(null)

// Tabs configuration - managers see fewer tabs
const allTabs = [
  { name: 'dashboard', label: 'Dashboard', icon: 'DataAnalysis', adminOnly: false },
  { name: 'users', label: 'Users', icon: 'User', adminOnly: false },
  { name: 'schools', label: 'Schools', icon: 'School', adminOnly: true },
  { name: 'tokens', label: 'Tokens', icon: 'Ticket', adminOnly: true },
  { name: 'apikeys', label: 'API Keys', icon: 'Key', adminOnly: true },
  { name: 'gewe', label: 'Gewe WeChat', icon: 'ChatLineRound', adminOnly: true },
  { name: 'logs', label: 'Logs', icon: 'Document', adminOnly: false },
  { name: 'announcements', label: 'Announcements', icon: 'Bell', adminOnly: true },
]

// Filter tabs based on role
const tabs = computed(() => {
  if (isAdmin.value) {
    return allTabs
  }
  // Managers only see non-admin-only tabs
  return allTabs.filter((tab) => !tab.adminOnly)
})

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
    notify.error(
      isZh.value ? '网络错误，加载仪表盘统计失败' : 'Network error, failed to load dashboard stats'
    )
  } finally {
    isLoading.value = false
  }
}

async function loadTokenStats() {
  if (isLoadingTokens.value) return
  isLoadingTokens.value = true

  try {
    // Use credentials (token in httpOnly cookie)
    const response = await fetch('/auth/admin/token-stats', {
      credentials: 'same-origin',
    })
    if (response.ok) {
      tokenStats.value = await response.json()
    } else {
      const data = await response.json().catch(() => ({}))
      notify.error(data.detail || (isZh.value ? '加载Token统计失败' : 'Failed to load token stats'))
    }
  } catch (error) {
    console.error('Failed to load token stats:', error)
    notify.error(
      isZh.value ? '网络错误，加载Token统计失败' : 'Network error, failed to load token stats'
    )
  } finally {
    isLoadingTokens.value = false
  }
}

// Format large numbers with K/M suffix
function formatNumber(num: number): string {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M'
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K'
  }
  return num.toLocaleString()
}

// Watch for tab changes to load token stats
watch(activeTab, (newTab) => {
  if (newTab === 'tokens' && !tokenStats.value) {
    loadTokenStats()
  }
})

// Watch for route query changes to update active tab
watch(() => route.query.tab, (tab) => {
  if (tab && typeof tab === 'string') {
    activeTab.value = tab
  }
})

onMounted(() => {
  loadDashboardStats()
})
</script>

<template>
  <div class="admin-page">
    <!-- Header with role indicator -->
    <div class="admin-header mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold text-gray-800 dark:text-white">
          {{ isAdmin ? '管理面板' : '组织管理' }}
        </h1>
        <p class="text-sm text-gray-500 mt-1">
          <template v-if="isManager">
            <el-tag
              size="small"
              type="warning"
            >
              Manager
            </el-tag>
            <span class="ml-2">数据范围: {{ userOrg }}</span>
          </template>
          <template v-else>
            <el-tag
              size="small"
              type="danger"
            >
              Admin
            </el-tag>
            <span class="ml-2">数据范围: 全部组织</span>
          </template>
        </p>
      </div>
    </div>

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

      <!-- Tokens Tab -->
      <template v-else-if="activeTab === 'tokens'">
        <div
          v-if="isLoadingTokens"
          class="text-center py-12"
        >
          <el-icon
            class="is-loading"
            :size="32"
            ><Loading
          /></el-icon>
          <p class="mt-4 text-gray-500">Loading token statistics...</p>
        </div>

        <div v-else-if="tokenStats">
          <!-- Service Breakdown Header -->
          <div class="mb-6">
            <h2 class="text-lg font-semibold text-gray-800 dark:text-white mb-2">
              Token Usage by Service
            </h2>
            <p class="text-sm text-gray-500">
              Compare token usage between MindGraph (diagrams) and MindMate (AI assistant)
            </p>
          </div>

          <!-- Service Cards Grid -->
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            <!-- MindGraph Card -->
            <el-card
              shadow="hover"
              class="service-card mindgraph-card"
            >
              <template #header>
                <div class="flex items-center gap-3">
                  <div
                    class="w-10 h-10 bg-blue-100 dark:bg-blue-900 rounded-lg flex items-center justify-center"
                  >
                    <el-icon
                      :size="20"
                      class="text-blue-500"
                      ><Connection
                    /></el-icon>
                  </div>
                  <div>
                    <h3 class="font-semibold text-gray-800 dark:text-white">MindGraph</h3>
                    <p class="text-xs text-gray-500">Diagram Generation</p>
                  </div>
                </div>
              </template>

              <div class="grid grid-cols-2 gap-4">
                <div class="stat-item">
                  <p class="text-xs text-gray-500 mb-1">Today</p>
                  <p class="text-xl font-bold text-blue-600 dark:text-blue-400">
                    {{ formatNumber(tokenStats.by_service?.mindgraph?.today?.total_tokens || 0) }}
                  </p>
                  <p class="text-xs text-gray-400">
                    {{
                      (tokenStats.by_service?.mindgraph?.today?.request_count || 0).toLocaleString()
                    }}
                    requests
                  </p>
                </div>
                <div class="stat-item">
                  <p class="text-xs text-gray-500 mb-1">This Week</p>
                  <p class="text-xl font-bold text-blue-600 dark:text-blue-400">
                    {{ formatNumber(tokenStats.by_service?.mindgraph?.week?.total_tokens || 0) }}
                  </p>
                  <p class="text-xs text-gray-400">
                    {{
                      (tokenStats.by_service?.mindgraph?.week?.request_count || 0).toLocaleString()
                    }}
                    requests
                  </p>
                </div>
                <div class="stat-item">
                  <p class="text-xs text-gray-500 mb-1">This Month</p>
                  <p class="text-xl font-bold text-blue-600 dark:text-blue-400">
                    {{ formatNumber(tokenStats.by_service?.mindgraph?.month?.total_tokens || 0) }}
                  </p>
                  <p class="text-xs text-gray-400">
                    {{
                      (tokenStats.by_service?.mindgraph?.month?.request_count || 0).toLocaleString()
                    }}
                    requests
                  </p>
                </div>
                <div class="stat-item">
                  <p class="text-xs text-gray-500 mb-1">All Time</p>
                  <p class="text-xl font-bold text-blue-600 dark:text-blue-400">
                    {{ formatNumber(tokenStats.by_service?.mindgraph?.total?.total_tokens || 0) }}
                  </p>
                  <p class="text-xs text-gray-400">
                    {{
                      (tokenStats.by_service?.mindgraph?.total?.request_count || 0).toLocaleString()
                    }}
                    requests
                  </p>
                </div>
              </div>

              <!-- Input/Output breakdown -->
              <div class="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700">
                <div class="flex justify-between text-sm">
                  <span class="text-gray-500">Input Tokens (All Time)</span>
                  <span class="font-medium text-gray-700 dark:text-gray-300">
                    {{ formatNumber(tokenStats.by_service?.mindgraph?.total?.input_tokens || 0) }}
                  </span>
                </div>
                <div class="flex justify-between text-sm mt-1">
                  <span class="text-gray-500">Output Tokens (All Time)</span>
                  <span class="font-medium text-gray-700 dark:text-gray-300">
                    {{ formatNumber(tokenStats.by_service?.mindgraph?.total?.output_tokens || 0) }}
                  </span>
                </div>
              </div>
            </el-card>

            <!-- MindMate Card -->
            <el-card
              shadow="hover"
              class="service-card mindmate-card"
            >
              <template #header>
                <div class="flex items-center gap-3">
                  <div
                    class="w-10 h-10 bg-purple-100 dark:bg-purple-900 rounded-lg flex items-center justify-center"
                  >
                    <el-icon
                      :size="20"
                      class="text-purple-500"
                      ><ChatDotRound
                    /></el-icon>
                  </div>
                  <div>
                    <h3 class="font-semibold text-gray-800 dark:text-white">MindMate</h3>
                    <p class="text-xs text-gray-500">AI Assistant (Dify)</p>
                  </div>
                </div>
              </template>

              <div class="grid grid-cols-2 gap-4">
                <div class="stat-item">
                  <p class="text-xs text-gray-500 mb-1">Today</p>
                  <p class="text-xl font-bold text-purple-600 dark:text-purple-400">
                    {{ formatNumber(tokenStats.by_service?.mindmate?.today?.total_tokens || 0) }}
                  </p>
                  <p class="text-xs text-gray-400">
                    {{
                      (tokenStats.by_service?.mindmate?.today?.request_count || 0).toLocaleString()
                    }}
                    requests
                  </p>
                </div>
                <div class="stat-item">
                  <p class="text-xs text-gray-500 mb-1">This Week</p>
                  <p class="text-xl font-bold text-purple-600 dark:text-purple-400">
                    {{ formatNumber(tokenStats.by_service?.mindmate?.week?.total_tokens || 0) }}
                  </p>
                  <p class="text-xs text-gray-400">
                    {{
                      (tokenStats.by_service?.mindmate?.week?.request_count || 0).toLocaleString()
                    }}
                    requests
                  </p>
                </div>
                <div class="stat-item">
                  <p class="text-xs text-gray-500 mb-1">This Month</p>
                  <p class="text-xl font-bold text-purple-600 dark:text-purple-400">
                    {{ formatNumber(tokenStats.by_service?.mindmate?.month?.total_tokens || 0) }}
                  </p>
                  <p class="text-xs text-gray-400">
                    {{
                      (tokenStats.by_service?.mindmate?.month?.request_count || 0).toLocaleString()
                    }}
                    requests
                  </p>
                </div>
                <div class="stat-item">
                  <p class="text-xs text-gray-500 mb-1">All Time</p>
                  <p class="text-xl font-bold text-purple-600 dark:text-purple-400">
                    {{ formatNumber(tokenStats.by_service?.mindmate?.total?.total_tokens || 0) }}
                  </p>
                  <p class="text-xs text-gray-400">
                    {{
                      (tokenStats.by_service?.mindmate?.total?.request_count || 0).toLocaleString()
                    }}
                    requests
                  </p>
                </div>
              </div>

              <!-- Input/Output breakdown -->
              <div class="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700">
                <div class="flex justify-between text-sm">
                  <span class="text-gray-500">Input Tokens (All Time)</span>
                  <span class="font-medium text-gray-700 dark:text-gray-300">
                    {{ formatNumber(tokenStats.by_service?.mindmate?.total?.input_tokens || 0) }}
                  </span>
                </div>
                <div class="flex justify-between text-sm mt-1">
                  <span class="text-gray-500">Output Tokens (All Time)</span>
                  <span class="font-medium text-gray-700 dark:text-gray-300">
                    {{ formatNumber(tokenStats.by_service?.mindmate?.total?.output_tokens || 0) }}
                  </span>
                </div>
              </div>
            </el-card>
          </div>

          <!-- Overall Summary -->
          <el-card shadow="hover">
            <template #header>
              <div class="flex items-center justify-between">
                <span class="font-medium">Overall Token Usage Summary</span>
                <el-button
                  text
                  size="small"
                  @click="loadTokenStats"
                >
                  <el-icon class="mr-1"><Refresh /></el-icon>
                  Refresh
                </el-button>
              </div>
            </template>

            <div class="grid grid-cols-2 md:grid-cols-4 gap-6">
              <div class="text-center">
                <p class="text-sm text-gray-500 mb-2">Today</p>
                <p class="text-2xl font-bold text-gray-800 dark:text-white">
                  {{ formatNumber(tokenStats.today?.total_tokens || 0) }}
                </p>
                <div class="flex justify-center gap-2 mt-1 text-xs text-gray-400">
                  <span>In: {{ formatNumber(tokenStats.today?.input_tokens || 0) }}</span>
                  <span>Out: {{ formatNumber(tokenStats.today?.output_tokens || 0) }}</span>
                </div>
              </div>
              <div class="text-center">
                <p class="text-sm text-gray-500 mb-2">Past Week</p>
                <p class="text-2xl font-bold text-gray-800 dark:text-white">
                  {{ formatNumber(tokenStats.past_week?.total_tokens || 0) }}
                </p>
                <div class="flex justify-center gap-2 mt-1 text-xs text-gray-400">
                  <span>In: {{ formatNumber(tokenStats.past_week?.input_tokens || 0) }}</span>
                  <span>Out: {{ formatNumber(tokenStats.past_week?.output_tokens || 0) }}</span>
                </div>
              </div>
              <div class="text-center">
                <p class="text-sm text-gray-500 mb-2">Past Month</p>
                <p class="text-2xl font-bold text-gray-800 dark:text-white">
                  {{ formatNumber(tokenStats.past_month?.total_tokens || 0) }}
                </p>
                <div class="flex justify-center gap-2 mt-1 text-xs text-gray-400">
                  <span>In: {{ formatNumber(tokenStats.past_month?.input_tokens || 0) }}</span>
                  <span>Out: {{ formatNumber(tokenStats.past_month?.output_tokens || 0) }}</span>
                </div>
              </div>
              <div class="text-center">
                <p class="text-sm text-gray-500 mb-2">All Time</p>
                <p class="text-2xl font-bold text-gray-800 dark:text-white">
                  {{ formatNumber(tokenStats.total?.total_tokens || 0) }}
                </p>
                <div class="flex justify-center gap-2 mt-1 text-xs text-gray-400">
                  <span>In: {{ formatNumber(tokenStats.total?.input_tokens || 0) }}</span>
                  <span>Out: {{ formatNumber(tokenStats.total?.output_tokens || 0) }}</span>
                </div>
              </div>
            </div>
          </el-card>
        </div>

        <div
          v-else
          class="text-center py-12 text-gray-400"
        >
          <el-icon :size="48"><Warning /></el-icon>
          <p class="mt-4">No token statistics available</p>
          <el-button
            type="primary"
            class="mt-4"
            @click="loadTokenStats"
          >
            Load Statistics
          </el-button>
        </div>
      </template>

      <!-- Gewe WeChat Tab -->
      <template v-else-if="activeTab === 'gewe'">
        <GeweLoginComponent />
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

/* Service cards */
.service-card :deep(.el-card__header) {
  padding: 16px 20px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.service-card :deep(.el-card__body) {
  padding: 20px;
}

.mindgraph-card {
  border-top: 3px solid #3b82f6;
}

.mindmate-card {
  border-top: 3px solid #8b5cf6;
}

.stat-item {
  padding: 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
}

.dark .stat-item {
  background: var(--el-fill-color-dark);
}
</style>
