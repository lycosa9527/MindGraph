<script setup lang="ts">
/**
 * Admin Page - Admin dashboard with tabs
 *
 * Access levels:
 * - Admin: Full access to all organizations' data
 * - Manager: Access to their organization's data only
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import {
  Chart,
  registerables,
  type ChartConfiguration,
  type TooltipItem,
} from 'chart.js'

Chart.register(...registerables)

import AdminDashboardTab from '@/components/admin/AdminDashboardTab.vue'
import AdminRolesTab from '@/components/admin/AdminRolesTab.vue'
import AdminSchoolsTab from '@/components/admin/AdminSchoolsTab.vue'
import AdminUsersTab from '@/components/admin/AdminUsersTab.vue'
import GeweLoginComponent from '@/components/admin/GeweLoginComponent.vue'
import { useLanguage, useNotifications } from '@/composables'
import { useFeatureFlags } from '@/composables/useFeatureFlags'
import { useAuthStore } from '@/stores'
import { apiRequest } from '@/utils/apiClient'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const { featureGewe } = useFeatureFlags()
const { t } = useLanguage()
const notify = useNotifications()

const activeTab = ref((route.query.tab as string) || 'dashboard')
const isLoadingTokens = ref(false)

// Role-based access
const isAdmin = computed(() => authStore.isAdmin)
const isManager = computed(() => authStore.isManager)

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
const allTabsConfig = [
  { name: 'dashboard', labelKey: 'admin.dashboard', icon: 'DataAnalysis', adminOnly: false },
  { name: 'users', labelKey: 'admin.users', icon: 'User', adminOnly: false },
  { name: 'schools', labelKey: 'admin.schools', icon: 'School', adminOnly: true },
  { name: 'roles', labelKey: 'admin.roleControl', icon: 'UserFilled', adminOnly: true },
  { name: 'tokens', labelKey: 'admin.tokens', icon: 'Ticket', adminOnly: true },
  { name: 'gewe', labelKey: 'admin.geweWechat', icon: 'ChatLineRound', adminOnly: true },
]

// Filter tabs based on role and feature flags, with translated labels
const tabs = computed(() => {
  let visible = allTabsConfig
  if (!isAdmin.value) {
    visible = visible.filter((tab) => !tab.adminOnly)
  }
  if (!featureGewe.value) {
    visible = visible.filter((tab) => tab.name !== 'gewe')
  }
  return visible.map((tab) => ({ ...tab, label: t(tab.labelKey) }))
})

async function loadTokenStats() {
  if (isLoadingTokens.value) return
  isLoadingTokens.value = true

  try {
    const response = await apiRequest('/api/auth/admin/token-stats')
    if (response.ok) {
      tokenStats.value = await response.json()
    } else {
      const data = await response.json().catch(() => ({}))
      notify.error(data.detail || t('admin.tokenStatsLoadError'))
    }
  } catch (error) {
    console.error('Failed to load token stats:', error)
    notify.error(t('admin.tokenStatsNetworkError'))
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

function formatChartLabel(value: number): string {
  if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M'
  if (value >= 1000) return (value / 1000).toFixed(1) + 'K'
  return String(value)
}

// Token trend chart modal (clickable cards)
type TokenTrendService = 'mindgraph' | 'mindmate' | null
const trendModalVisible = ref(false)
const trendChartTitle = ref('')
const trendChartLoading = ref(false)
const trendChartRef = ref<HTMLCanvasElement | null>(null)
let trendChartInstance: Chart<'line'> | null = null
const periodCards = ref({ today: '-', week: '-', month: '-', total: '-' })
const trendContext = ref<{
  service: TokenTrendService
  period: 'today' | 'week' | 'month' | 'total'
}>({ service: null, period: 'week' })

async function showTokenTrendChart(
  service: TokenTrendService,
  period: 'today' | 'week' | 'month' | 'total' = 'week'
) {
  trendContext.value = { service, period }
  if (service === 'mindgraph') {
    trendChartTitle.value = `MindGraph - ${t('admin.trendTokens')}`
  } else if (service === 'mindmate') {
    trendChartTitle.value = `MindMate - ${t('admin.trendTokens')}`
  } else {
    trendChartTitle.value = t('admin.trendTokens')
  }
  trendModalVisible.value = true
  trendChartLoading.value = true

  const daysMap = { today: 1, week: 7, month: 30, total: 0 }
  const days = daysMap[period]
  const params = new URLSearchParams({
    metric: 'tokens',
    days: String(days),
  })
  if (service) {
    params.set('service', service)
  }

  try {
    const chartRes = await apiRequest(`/api/auth/admin/stats/trends?${params}`)
    if (!chartRes.ok) {
      notify.error(t('admin.dashboardLoadError'))
      trendChartLoading.value = false
      return
    }
    const data = await chartRes.json()
    trendChartLoading.value = false
    await nextTick()
    await new Promise((r) => setTimeout(r, 50))
    renderTokenTrendChart(data)

    const fmt = (p: { input_tokens?: number; output_tokens?: number }) => {
      const i = p?.input_tokens ?? 0
      const o = p?.output_tokens ?? 0
      return `${formatNumber(i)}+${formatNumber(o)}`
    }
    const stats = tokenStats.value
    if (stats) {
      if (service === 'mindgraph' && stats.by_service?.mindgraph) {
        const s = stats.by_service.mindgraph
        periodCards.value = {
          today: fmt(s.today),
          week: fmt(s.week),
          month: fmt(s.month),
          total: fmt(s.total),
        }
      } else if (service === 'mindmate' && stats.by_service?.mindmate) {
        const s = stats.by_service.mindmate
        periodCards.value = {
          today: fmt(s.today),
          week: fmt(s.week),
          month: fmt(s.month),
          total: fmt(s.total),
        }
      } else {
        periodCards.value = {
          today: fmt(stats.today),
          week: fmt(stats.past_week),
          month: fmt(stats.past_month),
          total: fmt(stats.total),
        }
      }
    } else {
      periodCards.value = { today: '-', week: '-', month: '-', total: '-' }
    }
  } catch {
    notify.error(t('admin.dashboardLoadError'))
    trendChartLoading.value = false
  }
}

function switchTokenTrendPeriod(period: 'today' | 'week' | 'month' | 'total') {
  showTokenTrendChart(trendContext.value.service, period)
}

function renderTokenTrendChart(
  data: { data: Array<{ date: string; value: number; input?: number; output?: number }> }
) {
  if (!trendChartRef.value) return
  const rawData = data?.data ?? []
  if (rawData.length === 0) return

  trendChartInstance?.destroy()
  trendChartInstance = null

  const labels = rawData.map((item) => {
    const dateStr = item.date.includes(' ')
      ? item.date.replace(' ', 'T')
      : item.date + 'T00:00:00'
    const date = new Date(dateStr)
    if (item.date.includes(':') && item.date.includes(' ')) {
      return date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        hour12: false,
        timeZone: 'Asia/Shanghai',
      })
    }
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      timeZone: 'Asia/Shanghai',
    })
  })

  const values = rawData.map((item) => item.value)
  const maxVal = Math.max(...values, 0)
  const minVal = Math.min(...values, 0)
  const range = maxVal - minVal
  const padding = range === 0 ? maxVal * 0.1 : range * 0.1
  const yMin = Math.max(0, minVal - padding)
  const yMax = maxVal + padding

  const hasInputOutput =
    rawData[0] &&
    (rawData[0].input !== undefined || rawData[0].output !== undefined)

  const datasets: ChartConfiguration<'line'>['data']['datasets'] = [
    {
      label: trendChartTitle.value,
      data: values,
      borderColor: '#667eea',
      backgroundColor: 'rgba(102, 126, 234, 0.1)',
      borderWidth: 2,
      fill: true,
      tension: 0.4,
      pointRadius: 3,
      pointHoverRadius: 5,
    },
  ]
  if (hasInputOutput) {
    datasets.push({
      label: t('admin.inputTokens'),
      data: rawData.map((item) => item.input ?? 0),
      borderColor: '#10b981',
      backgroundColor: 'rgba(16, 185, 129, 0.1)',
      borderWidth: 2,
      fill: false,
      tension: 0.4,
      pointRadius: 2,
      pointHoverRadius: 4,
    })
    datasets.push({
      label: t('admin.outputTokens'),
      data: rawData.map((item) => item.output ?? 0),
      borderColor: '#f59e0b',
      backgroundColor: 'rgba(245, 158, 11, 0.1)',
      borderWidth: 2,
      fill: false,
      tension: 0.4,
      pointRadius: 2,
      pointHoverRadius: 4,
    })
  }

  const config: ChartConfiguration<'line'> = {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: hasInputOutput, position: 'top' },
        tooltip: {
          callbacks: {
            label: (ctx: TooltipItem<'line'>) =>
              `${ctx.dataset.label}: ${formatChartLabel(Number(ctx.raw))}`,
          },
        },
      },
      scales: {
        y: {
          beginAtZero: false,
          min: yMin,
          max: yMax,
          ticks: { callback: (val: string | number) => formatChartLabel(Number(val)) },
        },
        x: { ticks: { maxRotation: 45, minRotation: 45 } },
      },
    },
  }
  trendChartInstance = new Chart(trendChartRef.value, config)
}

function closeTokenTrendModal() {
  trendModalVisible.value = false
  trendChartInstance?.destroy()
  trendChartInstance = null
}

onBeforeUnmount(() => {
  trendChartInstance?.destroy()
  trendChartInstance = null
})

// Watch for tab changes to load token stats
watch(activeTab, (newTab) => {
  if (newTab === 'tokens' && !tokenStats.value) {
    loadTokenStats()
  }
})

// Watch for route query changes to update active tab
watch(
  () => route.query.tab,
  (tab) => {
    if (tab && typeof tab === 'string') {
      activeTab.value = tab
    }
  }
)

// Sync active tab to URL for bookmarkable tabs
watch(activeTab, (tab) => {
  const current = route.query.tab as string
  if (tab !== current) {
    router.replace({ query: { ...route.query, tab } })
  }
})

</script>

<template>
  <div class="admin-page flex-1 flex flex-col bg-stone-50 overflow-hidden">
    <!-- Header (same as Teacher Usage, Gewe modules) -->
    <div
      class="admin-header h-14 px-4 flex items-center justify-between bg-white border-b border-stone-200"
    >
      <h1 class="text-sm font-semibold text-stone-900">
        {{ isAdmin ? t('admin.title') : t('admin.orgManagement') }}
      </h1>
    </div>

    <!-- Tabs + Content (scrollable, tabs visible on landing) -->
    <div class="admin-body flex-1 overflow-y-auto">
      <div class="px-6 pt-4 pb-6">
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
            <AdminDashboardTab />
          </template>

          <!-- Users Tab -->
          <template v-else-if="activeTab === 'users'">
            <AdminUsersTab />
          </template>

          <!-- Schools Tab -->
          <template v-else-if="activeTab === 'schools'">
            <AdminSchoolsTab />
          </template>

          <!-- Roles Tab -->
          <template v-else-if="activeTab === 'roles'">
            <AdminRolesTab />
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
          <p class="mt-4 text-gray-500">{{ t('admin.loadingTokenStats') }}</p>
        </div>

        <div v-else-if="tokenStats">
          <!-- Service Breakdown Header -->
          <div class="mb-6">
            <h2 class="text-lg font-semibold text-gray-800 dark:text-white mb-2">
              {{ t('admin.tokenUsageByService') }}
            </h2>
            <p class="text-sm text-gray-500">
              {{ t('admin.tokenUsageCompare') }}
            </p>
          </div>

          <!-- Service Cards Grid -->
          <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
            <!-- MindGraph Card -->
            <el-card
              shadow="hover"
              class="service-card mindgraph-card service-card-clickable"
              @click="showTokenTrendChart('mindgraph')"
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
                    <p class="text-xs text-gray-500">{{ t('admin.diagramGeneration') }}</p>
                  </div>
                </div>
              </template>

              <div class="grid grid-cols-2 gap-4">
                <div class="stat-item">
                  <p class="text-xs text-gray-500 mb-1">{{ t('admin.today') }}</p>
                  <p class="text-xl font-bold text-blue-600 dark:text-blue-400">
                    {{ formatNumber(tokenStats.by_service?.mindgraph?.today?.total_tokens || 0) }}
                  </p>
                  <p class="text-xs text-gray-400">
                    {{
                      (tokenStats.by_service?.mindgraph?.today?.request_count || 0).toLocaleString()
                    }}
                    {{ t('admin.requests') }}
                  </p>
                </div>
                <div class="stat-item">
                  <p class="text-xs text-gray-500 mb-1">{{ t('admin.thisWeek') }}</p>
                  <p class="text-xl font-bold text-blue-600 dark:text-blue-400">
                    {{ formatNumber(tokenStats.by_service?.mindgraph?.week?.total_tokens || 0) }}
                  </p>
                  <p class="text-xs text-gray-400">
                    {{
                      (tokenStats.by_service?.mindgraph?.week?.request_count || 0).toLocaleString()
                    }}
                    {{ t('admin.requests') }}
                  </p>
                </div>
                <div class="stat-item">
                  <p class="text-xs text-gray-500 mb-1">{{ t('admin.thisMonth') }}</p>
                  <p class="text-xl font-bold text-blue-600 dark:text-blue-400">
                    {{ formatNumber(tokenStats.by_service?.mindgraph?.month?.total_tokens || 0) }}
                  </p>
                  <p class="text-xs text-gray-400">
                    {{
                      (tokenStats.by_service?.mindgraph?.month?.request_count || 0).toLocaleString()
                    }}
                    {{ t('admin.requests') }}
                  </p>
                </div>
                <div class="stat-item">
                  <p class="text-xs text-gray-500 mb-1">{{ t('admin.allTime') }}</p>
                  <p class="text-xl font-bold text-blue-600 dark:text-blue-400">
                    {{ formatNumber(tokenStats.by_service?.mindgraph?.total?.total_tokens || 0) }}
                  </p>
                  <p class="text-xs text-gray-400">
                    {{
                      (tokenStats.by_service?.mindgraph?.total?.request_count || 0).toLocaleString()
                    }}
                    {{ t('admin.requests') }}
                  </p>
                </div>
              </div>

              <!-- Input/Output breakdown -->
              <div class="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700">
                <div class="flex justify-between text-sm">
                  <span class="text-gray-500">{{ t('admin.inputTokens') }}</span>
                  <span class="font-medium text-gray-700 dark:text-gray-300">
                    {{ formatNumber(tokenStats.by_service?.mindgraph?.total?.input_tokens || 0) }}
                  </span>
                </div>
                <div class="flex justify-between text-sm mt-1">
                  <span class="text-gray-500">{{ t('admin.outputTokens') }}</span>
                  <span class="font-medium text-gray-700 dark:text-gray-300">
                    {{ formatNumber(tokenStats.by_service?.mindgraph?.total?.output_tokens || 0) }}
                  </span>
                </div>
              </div>
            </el-card>

            <!-- MindMate Card -->
            <el-card
              shadow="hover"
              class="service-card mindmate-card service-card-clickable"
              @click="showTokenTrendChart('mindmate')"
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
                    <p class="text-xs text-gray-500">{{ t('admin.aiAssistant') }}</p>
                  </div>
                </div>
              </template>

              <div class="grid grid-cols-2 gap-4">
                <div class="stat-item">
                  <p class="text-xs text-gray-500 mb-1">{{ t('admin.today') }}</p>
                  <p class="text-xl font-bold text-purple-600 dark:text-purple-400">
                    {{ formatNumber(tokenStats.by_service?.mindmate?.today?.total_tokens || 0) }}
                  </p>
                  <p class="text-xs text-gray-400">
                    {{
                      (tokenStats.by_service?.mindmate?.today?.request_count || 0).toLocaleString()
                    }}
                    {{ t('admin.requests') }}
                  </p>
                </div>
                <div class="stat-item">
                  <p class="text-xs text-gray-500 mb-1">{{ t('admin.thisWeek') }}</p>
                  <p class="text-xl font-bold text-purple-600 dark:text-purple-400">
                    {{ formatNumber(tokenStats.by_service?.mindmate?.week?.total_tokens || 0) }}
                  </p>
                  <p class="text-xs text-gray-400">
                    {{
                      (tokenStats.by_service?.mindmate?.week?.request_count || 0).toLocaleString()
                    }}
                    {{ t('admin.requests') }}
                  </p>
                </div>
                <div class="stat-item">
                  <p class="text-xs text-gray-500 mb-1">{{ t('admin.thisMonth') }}</p>
                  <p class="text-xl font-bold text-purple-600 dark:text-purple-400">
                    {{ formatNumber(tokenStats.by_service?.mindmate?.month?.total_tokens || 0) }}
                  </p>
                  <p class="text-xs text-gray-400">
                    {{
                      (tokenStats.by_service?.mindmate?.month?.request_count || 0).toLocaleString()
                    }}
                    {{ t('admin.requests') }}
                  </p>
                </div>
                <div class="stat-item">
                  <p class="text-xs text-gray-500 mb-1">{{ t('admin.allTime') }}</p>
                  <p class="text-xl font-bold text-purple-600 dark:text-purple-400">
                    {{ formatNumber(tokenStats.by_service?.mindmate?.total?.total_tokens || 0) }}
                  </p>
                  <p class="text-xs text-gray-400">
                    {{
                      (tokenStats.by_service?.mindmate?.total?.request_count || 0).toLocaleString()
                    }}
                    {{ t('admin.requests') }}
                  </p>
                </div>
              </div>

              <!-- Input/Output breakdown -->
              <div class="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700">
                <div class="flex justify-between text-sm">
                  <span class="text-gray-500">{{ t('admin.inputTokens') }}</span>
                  <span class="font-medium text-gray-700 dark:text-gray-300">
                    {{ formatNumber(tokenStats.by_service?.mindmate?.total?.input_tokens || 0) }}
                  </span>
                </div>
                <div class="flex justify-between text-sm mt-1">
                  <span class="text-gray-500">{{ t('admin.outputTokens') }}</span>
                  <span class="font-medium text-gray-700 dark:text-gray-300">
                    {{ formatNumber(tokenStats.by_service?.mindmate?.total?.output_tokens || 0) }}
                  </span>
                </div>
              </div>
            </el-card>
          </div>

          <!-- Overall Summary -->
          <el-card
            shadow="hover"
            class="service-card-clickable"
            @click="showTokenTrendChart(null)"
          >
            <template #header>
              <div
                class="flex items-center justify-between"
                @click.stop
              >
                <span class="font-medium">{{ t('admin.overallTokenSummary') }}</span>
                <el-button
                  text
                  size="small"
                  @click="loadTokenStats"
                >
                  <el-icon class="mr-1"><Refresh /></el-icon>
                  {{ t('common.refresh') }}
                </el-button>
              </div>
            </template>

            <div class="grid grid-cols-2 md:grid-cols-4 gap-6">
              <div class="text-center">
                <p class="text-sm text-gray-500 mb-2">{{ t('admin.today') }}</p>
                <p class="text-2xl font-bold text-gray-800 dark:text-white">
                  {{ formatNumber(tokenStats.today?.total_tokens || 0) }}
                </p>
                <div class="flex justify-center gap-2 mt-1 text-xs text-gray-400">
                  <span>{{ t('admin.inShort') }}: {{ formatNumber(tokenStats.today?.input_tokens || 0) }}</span>
                  <span>{{ t('admin.outShort') }}: {{ formatNumber(tokenStats.today?.output_tokens || 0) }}</span>
                </div>
              </div>
              <div class="text-center">
                <p class="text-sm text-gray-500 mb-2">{{ t('admin.pastWeek') }}</p>
                <p class="text-2xl font-bold text-gray-800 dark:text-white">
                  {{ formatNumber(tokenStats.past_week?.total_tokens || 0) }}
                </p>
                <div class="flex justify-center gap-2 mt-1 text-xs text-gray-400">
                  <span>{{ t('admin.inShort') }}: {{ formatNumber(tokenStats.past_week?.input_tokens || 0) }}</span>
                  <span>{{ t('admin.outShort') }}: {{ formatNumber(tokenStats.past_week?.output_tokens || 0) }}</span>
                </div>
              </div>
              <div class="text-center">
                <p class="text-sm text-gray-500 mb-2">{{ t('admin.pastMonth') }}</p>
                <p class="text-2xl font-bold text-gray-800 dark:text-white">
                  {{ formatNumber(tokenStats.past_month?.total_tokens || 0) }}
                </p>
                <div class="flex justify-center gap-2 mt-1 text-xs text-gray-400">
                  <span>{{ t('admin.inShort') }}: {{ formatNumber(tokenStats.past_month?.input_tokens || 0) }}</span>
                  <span>{{ t('admin.outShort') }}: {{ formatNumber(tokenStats.past_month?.output_tokens || 0) }}</span>
                </div>
              </div>
              <div class="text-center">
                <p class="text-sm text-gray-500 mb-2">{{ t('admin.allTime') }}</p>
                <p class="text-2xl font-bold text-gray-800 dark:text-white">
                  {{ formatNumber(tokenStats.total?.total_tokens || 0) }}
                </p>
                <div class="flex justify-center gap-2 mt-1 text-xs text-gray-400">
                  <span>{{ t('admin.inShort') }}: {{ formatNumber(tokenStats.total?.input_tokens || 0) }}</span>
                  <span>{{ t('admin.outShort') }}: {{ formatNumber(tokenStats.total?.output_tokens || 0) }}</span>
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
          <p class="mt-4">{{ t('admin.noTokenStats') }}</p>
          <el-button
            type="primary"
            class="mt-4"
            @click="loadTokenStats"
          >
            {{ t('admin.loadStatistics') }}
          </el-button>
        </div>
      </template>

          <!-- Gewe WeChat Tab -->
          <template v-else-if="activeTab === 'gewe'">
            <GeweLoginComponent />
          </template>

        </div>
      </div>
    </div>

    <!-- Token trend chart modal -->
    <el-dialog
      v-model="trendModalVisible"
      :title="trendChartTitle"
      width="640px"
      destroy-on-close
      @close="closeTokenTrendModal"
    >
      <div
        v-if="trendChartLoading"
        class="flex justify-center items-center h-64"
      >
        <el-icon
          class="is-loading"
          :size="32"
        >
          <Loading />
        </el-icon>
      </div>
      <template v-else>
        <div class="relative h-64 min-h-[256px] w-full">
          <canvas
            ref="trendChartRef"
            class="block w-full h-full"
          />
        </div>
        <div class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <el-card
              shadow="hover"
              class="token-period-card cursor-pointer"
              :class="{ 'ring-2 ring-primary-500': trendContext.period === 'today' }"
              @click="switchTokenTrendPeriod('today')"
            >
              <p class="text-xs text-gray-500 dark:text-gray-400 mb-1">
                {{ t('admin.today') }}
              </p>
              <p class="text-lg font-bold text-gray-800 dark:text-white">
                {{ periodCards.today }}
              </p>
            </el-card>
            <el-card
              shadow="hover"
              class="token-period-card cursor-pointer"
              :class="{ 'ring-2 ring-primary-500': trendContext.period === 'week' }"
              @click="switchTokenTrendPeriod('week')"
            >
              <p class="text-xs text-gray-500 dark:text-gray-400 mb-1">
                {{ t('admin.pastWeek') }}
              </p>
              <p class="text-lg font-bold text-gray-800 dark:text-white">
                {{ periodCards.week }}
              </p>
            </el-card>
            <el-card
              shadow="hover"
              class="token-period-card cursor-pointer"
              :class="{ 'ring-2 ring-primary-500': trendContext.period === 'month' }"
              @click="switchTokenTrendPeriod('month')"
            >
              <p class="text-xs text-gray-500 dark:text-gray-400 mb-1">
                {{ t('admin.pastMonth') }}
              </p>
              <p class="text-lg font-bold text-gray-800 dark:text-white">
                {{ periodCards.month }}
              </p>
            </el-card>
            <el-card
              shadow="hover"
              class="token-period-card cursor-pointer"
              :class="{ 'ring-2 ring-primary-500': trendContext.period === 'total' }"
              @click="switchTokenTrendPeriod('total')"
            >
              <p class="text-xs text-gray-500 dark:text-gray-400 mb-1">
                {{ t('admin.allTime') }}
              </p>
              <p class="text-lg font-bold text-gray-800 dark:text-white">
                {{ periodCards.total }}
              </p>
            </el-card>
          </div>
        </div>
      </template>
      <template #footer>
        <el-button @click="closeTokenTrendModal">{{ t('common.close') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.admin-page {
  min-height: 0;
}

.admin-body {
  min-height: 0;
}

.admin-page .admin-content {
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

.service-card-clickable {
  cursor: pointer;
}

.service-card-clickable:hover {
  transform: translateY(-1px);
}

.token-period-card :deep(.el-card__body) {
  padding: 12px 16px;
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
