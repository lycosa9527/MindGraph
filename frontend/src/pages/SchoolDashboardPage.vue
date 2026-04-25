<script setup lang="ts">
/**
 * School Dashboard - Org-scoped dashboard for managers (principals)
 * Admins can use dropdown to preview any school's dashboard
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import {
  ChatDotRound,
  Connection,
  Loading,
  Refresh,
  TrendCharts,
  User,
  Warning,
} from '@element-plus/icons-vue'

import { Chart, type ChartConfiguration, type TooltipItem, registerables } from 'chart.js'

import SchoolDashboardUsersTab from '@/components/school/SchoolDashboardUsersTab.vue'
import { useLanguage, useNotifications } from '@/composables'
import { useAuthStore } from '@/stores'
import { apiRequest } from '@/utils/apiClient'
import { httpErrorDetail } from '@/utils/httpErrorDetail'

Chart.register(...registerables)

const { t, isZh } = useLanguage()
const notify = useNotifications()
const authStore = useAuthStore()

const isAdmin = computed(() => authStore.isAdmin)
const userSchoolId = computed(() =>
  authStore.user?.schoolId ? Number(authStore.user.schoolId) : null
)

const selectedOrgId = ref<number | null>(null)
const organizations = ref<{ id: number; name: string; code: string }[]>([])

const effectiveOrgId = computed(() => {
  if (isAdmin.value && selectedOrgId.value != null) return selectedOrgId.value
  return userSchoolId.value
})

const isLoading = ref(true)
const stats = ref({
  totalUsers: 0,
  recentRegistrations: 0,
  totalTokens: 0,
  organization: { id: 0, name: '', code: '' },
})
const topUsers = ref<{ id: number; name: string; phone: string; total_tokens: number }[]>([])

const trendModalVisible = ref(false)
const trendChartTitle = ref('')
const trendChartLoading = ref(false)
const trendChartRef = ref<HTMLCanvasElement | null>(null)
let trendChartInstance: Chart<'line'> | null = null
const periodCards = ref({ today: '-', week: '-', month: '-', total: '-' })
const trendPeriod = ref<'today' | 'week' | 'month' | 'total'>('week')

const activeTab = ref<'overview' | 'tokens' | 'users'>('overview')
const isLoadingTokens = ref(false)
const tokenStats = ref<{
  today?: { input_tokens: number; output_tokens: number; total_tokens: number }
  past_week?: { input_tokens: number; output_tokens: number; total_tokens: number }
  past_month?: { input_tokens: number; output_tokens: number; total_tokens: number }
  total?: { input_tokens: number; output_tokens: number; total_tokens: number }
  by_service?: {
    mindgraph: {
      today: { total_tokens: number; request_count?: number }
      week: { total_tokens: number; request_count?: number }
      month: { total_tokens: number; request_count?: number }
      total: {
        total_tokens: number
        input_tokens: number
        output_tokens: number
        request_count?: number
      }
    }
    mindmate: {
      today: { total_tokens: number; request_count?: number }
      week: { total_tokens: number; request_count?: number }
      month: { total_tokens: number; request_count?: number }
      total: {
        total_tokens: number
        input_tokens: number
        output_tokens: number
        request_count?: number
      }
    }
  }
} | null>(null)

function formatNumber(num: number): string {
  if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M'
  if (num >= 1000) return (num / 1000).toFixed(1) + 'K'
  return num.toLocaleString()
}

function formatChartLabel(value: number): string {
  if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M'
  if (value >= 1000) return (value / 1000).toFixed(1) + 'K'
  return String(value)
}

async function loadOrganizations() {
  if (!isAdmin.value) return
  const res = await apiRequest('/api/auth/admin/organizations')
  if (!res.ok) return
  const data = await res.json()
  organizations.value = data.map((o: { id: number; name: string; code: string }) => ({
    id: o.id,
    name: o.name,
    code: o.code,
  }))
  if (organizations.value.length > 0 && selectedOrgId.value == null) {
    selectedOrgId.value = organizations.value[0].id
  }
}

async function loadStats() {
  const orgId = effectiveOrgId.value
  if (orgId == null) {
    isLoading.value = false
    return
  }
  isLoading.value = true
  try {
    const res = await apiRequest(`/api/auth/admin/stats/school?organization_id=${orgId}`)
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      notify.error(httpErrorDetail(data) || t('admin.dashboardLoadError'))
      return
    }
    const data = await res.json()
    stats.value = {
      totalUsers: data.total_users ?? 0,
      recentRegistrations: data.recent_registrations ?? 0,
      totalTokens: data.token_stats?.total_tokens ?? 0,
      organization: data.organization ?? { id: 0, name: '', code: '' },
    }
    topUsers.value = data.top_users ?? []
  } catch {
    notify.error(t('admin.dashboardLoadError'))
  } finally {
    isLoading.value = false
  }
}

async function showTrendChart(period: 'today' | 'week' | 'month' | 'total' = 'week') {
  const orgId = effectiveOrgId.value
  if (orgId == null) return
  trendPeriod.value = period
  trendChartTitle.value = `${t('admin.trendOrgTokens')}: ${stats.value.organization?.name ?? ''}`
  trendModalVisible.value = true
  trendChartLoading.value = true

  const daysMap = { today: 1, week: 7, month: 30, total: 0 }
  const days = daysMap[period]
  const hourly = period === 'today'
  try {
    const [chartRes, tokenRes] = await Promise.all([
      apiRequest(
        `/api/auth/admin/stats/school/trends?organization_id=${orgId}&days=${days}&hourly=${hourly}`
      ),
      apiRequest(`/api/auth/admin/stats/school/token-stats?organization_id=${orgId}`),
    ])
    if (!chartRes.ok) {
      const errBody = await chartRes.json().catch(() => ({}))
      notify.error(httpErrorDetail(errBody) || t('admin.dashboardLoadError'))
      trendChartLoading.value = false
      return
    }
    const chartData = await chartRes.json()
    trendChartLoading.value = false
    await nextTick()
    await new Promise((r) => setTimeout(r, 50))
    renderTrendChart(chartData)
    if (tokenRes.ok) {
      const tokenData = await tokenRes.json()
      const fmt = (p: { input_tokens?: number; output_tokens?: number }) => {
        const i = p?.input_tokens ?? 0
        const o = p?.output_tokens ?? 0
        return `${formatNumber(i)}+${formatNumber(o)}`
      }
      periodCards.value = {
        today: fmt(tokenData.today),
        week: fmt(tokenData.past_week),
        month: fmt(tokenData.past_month),
        total: fmt(tokenData.total),
      }
    }
  } catch {
    notify.error(t('admin.dashboardLoadError'))
    trendChartLoading.value = false
  }
}

function renderTrendChart(data: {
  data: Array<{ date: string; value: number; input?: number; output?: number }>
}) {
  if (!trendChartRef.value) return
  const rawData = data?.data ?? []
  if (rawData.length === 0) return

  trendChartInstance?.destroy()
  trendChartInstance = null

  const chartLocale = isZh.value ? 'zh-CN' : 'en-US'
  const labels = rawData.map((item) => {
    const dateStr = item.date.includes(' ') ? item.date.replace(' ', 'T') : item.date + 'T00:00:00'
    const date = new Date(dateStr)
    if (item.date.includes(':') && item.date.includes(' ')) {
      return date.toLocaleString(chartLocale, {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        hour12: false,
        timeZone: 'Asia/Shanghai',
      })
    }
    return date.toLocaleDateString(chartLocale, {
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
    rawData[0] && (rawData[0].input !== undefined || rawData[0].output !== undefined)

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

function switchTrendPeriod(period: 'today' | 'week' | 'month' | 'total') {
  showTrendChart(period)
}

function closeTrendModal() {
  trendModalVisible.value = false
  trendChartInstance?.destroy()
  trendChartInstance = null
}

async function loadTokenStats() {
  const orgId = effectiveOrgId.value
  if (orgId == null) return
  if (isLoadingTokens.value) return
  isLoadingTokens.value = true
  try {
    const res = await apiRequest(
      `/api/auth/admin/stats/school/token-stats?organization_id=${orgId}`
    )
    if (res.ok) {
      tokenStats.value = await res.json()
    } else {
      const data = await res.json().catch(() => ({}))
      notify.error(httpErrorDetail(data) || t('admin.tokenStatsLoadError'))
    }
  } catch {
    notify.error(t('admin.tokenStatsNetworkError'))
  } finally {
    isLoadingTokens.value = false
  }
}

watch(activeTab, (tab) => {
  if (tab === 'tokens' && !tokenStats.value && effectiveOrgId.value != null) {
    loadTokenStats()
  }
})

watch(effectiveOrgId, () => {
  if (effectiveOrgId.value != null) {
    loadStats()
    if (activeTab.value === 'tokens') {
      tokenStats.value = null
      loadTokenStats()
    }
  }
})

onMounted(async () => {
  await loadOrganizations()
  loadStats()
})

onBeforeUnmount(() => {
  trendChartInstance?.destroy()
  trendChartInstance = null
})
</script>

<template>
  <div class="school-dashboard-page flex-1 flex flex-col bg-stone-50 overflow-hidden">
    <div
      class="school-header h-14 px-4 flex items-center justify-between bg-white border-b border-stone-200"
    >
      <h1 class="text-sm font-semibold text-stone-900">
        {{ t('admin.schoolDashboard') }}
      </h1>
      <div
        v-if="isAdmin && organizations.length > 0"
        class="flex items-center gap-2"
      >
        <span class="text-gray-500 text-sm">{{ t('admin.viewSchool') }}:</span>
        <el-select
          v-model="selectedOrgId"
          :placeholder="t('admin.selectSchool')"
          size="small"
          style="width: 220px"
        >
          <el-option
            v-for="org in organizations"
            :key="org.id"
            :label="org.name"
            :value="org.id"
          />
        </el-select>
      </div>
    </div>

    <div class="school-body flex-1 overflow-y-auto p-6">
      <div
        v-if="effectiveOrgId == null && !isLoading"
        class="text-center py-20 text-gray-500"
      >
        <p>{{ t('admin.schoolDashboardNoOrg') }}</p>
      </div>

      <template v-else-if="effectiveOrgId != null">
        <el-tabs
          v-model="activeTab"
          class="school-tabs"
        >
          <el-tab-pane
            :label="t('admin.dashboard')"
            name="overview"
          />
          <el-tab-pane
            :label="t('admin.tokens')"
            name="tokens"
          />
          <el-tab-pane
            :label="t('admin.schoolUsersTab')"
            name="users"
          />
        </el-tabs>

        <div
          v-if="activeTab === 'overview' && isLoading"
          class="flex justify-center py-20"
        >
          <el-icon
            class="is-loading"
            :size="32"
          >
            <Loading />
          </el-icon>
        </div>

        <template v-else-if="activeTab === 'overview'">
          <div class="grid grid-cols-1 md:grid-cols-3 gap-6 pt-4">
            <el-card
              shadow="hover"
              class="stat-card stat-card-clickable"
              @click="showTrendChart('total')"
            >
              <div class="flex items-center gap-4">
                <div
                  class="w-12 h-12 bg-primary-100 dark:bg-primary-900 rounded-lg flex items-center justify-center"
                >
                  <el-icon
                    :size="24"
                    class="text-primary-500"
                  >
                    <User />
                  </el-icon>
                </div>
                <div>
                  <p class="text-sm text-gray-500 dark:text-gray-400">
                    {{ t('admin.totalUsers') }}
                  </p>
                  <p class="text-2xl font-bold text-gray-800 dark:text-white">
                    {{ stats.totalUsers.toLocaleString() }}
                  </p>
                </div>
              </div>
            </el-card>

            <el-card
              shadow="hover"
              class="stat-card stat-card-clickable"
              @click="showTrendChart('today')"
            >
              <div class="flex items-center gap-4">
                <div
                  class="w-12 h-12 bg-green-100 dark:bg-green-900 rounded-lg flex items-center justify-center"
                >
                  <el-icon
                    :size="24"
                    class="text-green-500"
                  >
                    <TrendCharts />
                  </el-icon>
                </div>
                <div>
                  <p class="text-sm text-gray-500 dark:text-gray-400">
                    {{ t('admin.todayRegistrations') }}
                  </p>
                  <p class="text-2xl font-bold text-gray-800 dark:text-white">
                    {{ stats.recentRegistrations }}
                  </p>
                </div>
              </div>
            </el-card>

            <el-card
              shadow="hover"
              class="stat-card stat-card-clickable"
              @click="showTrendChart('week')"
            >
              <div class="flex items-center gap-4">
                <div
                  class="w-12 h-12 bg-orange-100 dark:bg-orange-900 rounded-lg flex items-center justify-center"
                >
                  <el-icon
                    :size="24"
                    class="text-orange-500"
                  >
                    <Connection />
                  </el-icon>
                </div>
                <div>
                  <p class="text-sm text-gray-500 dark:text-gray-400">
                    {{ t('admin.tokens') }} ({{ t('admin.pastWeek') }})
                  </p>
                  <p class="text-2xl font-bold text-gray-800 dark:text-white">
                    {{ formatNumber(stats.totalTokens) }}
                  </p>
                </div>
              </div>
            </el-card>
          </div>

          <el-card
            v-if="topUsers.length > 0"
            shadow="hover"
            class="mt-6"
          >
            <template #header>
              <span class="font-medium">{{ t('admin.topUsersByTokens') }}</span>
              <el-button
                text
                size="small"
                @click="loadStats"
              >
                {{ t('common.refresh') }}
              </el-button>
            </template>
            <el-table
              :data="topUsers"
              stripe
              size="small"
            >
              <el-table-column
                prop="name"
                :label="t('admin.name')"
              />
              <el-table-column
                prop="phone"
                :label="t('admin.phone')"
                width="140"
              />
              <el-table-column
                prop="total_tokens"
                :label="t('admin.tokensUsed')"
                width="120"
              >
                <template #default="{ row }">
                  {{ formatNumber(row.total_tokens) }}
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </template>

        <!-- Token Usage Tab -->
        <template v-else-if="activeTab === 'tokens'">
          <div
            v-if="isLoadingTokens"
            class="text-center py-12"
          >
            <el-icon
              class="is-loading"
              :size="32"
            >
              <Loading />
            </el-icon>
            <p class="mt-4 text-gray-500">{{ t('admin.loadingTokenStats') }}</p>
          </div>

          <div
            v-else-if="tokenStats"
            class="mt-4"
          >
            <div class="mb-6">
              <h2 class="text-lg font-semibold text-gray-800 dark:text-white mb-2">
                {{ t('admin.tokenUsageByService') }} - {{ stats.organization?.name }}
              </h2>
              <p class="text-sm text-gray-500">
                {{ t('admin.tokenUsageCompare') }}
              </p>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
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
                      >
                        <Connection />
                      </el-icon>
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
                        (
                          tokenStats.by_service?.mindgraph?.today?.request_count || 0
                        ).toLocaleString()
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
                        (
                          tokenStats.by_service?.mindgraph?.week?.request_count || 0
                        ).toLocaleString()
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
                        (
                          tokenStats.by_service?.mindgraph?.month?.request_count || 0
                        ).toLocaleString()
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
                        (
                          tokenStats.by_service?.mindgraph?.total?.request_count || 0
                        ).toLocaleString()
                      }}
                      {{ t('admin.requests') }}
                    </p>
                  </div>
                </div>
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
                      {{
                        formatNumber(tokenStats.by_service?.mindgraph?.total?.output_tokens || 0)
                      }}
                    </span>
                  </div>
                </div>
              </el-card>

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
                      >
                        <ChatDotRound />
                      </el-icon>
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
                        (
                          tokenStats.by_service?.mindmate?.today?.request_count || 0
                        ).toLocaleString()
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
                        (
                          tokenStats.by_service?.mindmate?.month?.request_count || 0
                        ).toLocaleString()
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
                        (
                          tokenStats.by_service?.mindmate?.total?.request_count || 0
                        ).toLocaleString()
                      }}
                      {{ t('admin.requests') }}
                    </p>
                  </div>
                </div>
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

            <el-card shadow="hover">
              <template #header>
                <div class="flex items-center justify-between">
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
                    <span
                      >{{ t('admin.inShort') }}:
                      {{ formatNumber(tokenStats.today?.input_tokens || 0) }}</span
                    >
                    <span
                      >{{ t('admin.outShort') }}:
                      {{ formatNumber(tokenStats.today?.output_tokens || 0) }}</span
                    >
                  </div>
                </div>
                <div class="text-center">
                  <p class="text-sm text-gray-500 mb-2">{{ t('admin.pastWeek') }}</p>
                  <p class="text-2xl font-bold text-gray-800 dark:text-white">
                    {{ formatNumber(tokenStats.past_week?.total_tokens || 0) }}
                  </p>
                  <div class="flex justify-center gap-2 mt-1 text-xs text-gray-400">
                    <span
                      >{{ t('admin.inShort') }}:
                      {{ formatNumber(tokenStats.past_week?.input_tokens || 0) }}</span
                    >
                    <span
                      >{{ t('admin.outShort') }}:
                      {{ formatNumber(tokenStats.past_week?.output_tokens || 0) }}</span
                    >
                  </div>
                </div>
                <div class="text-center">
                  <p class="text-sm text-gray-500 mb-2">{{ t('admin.pastMonth') }}</p>
                  <p class="text-2xl font-bold text-gray-800 dark:text-white">
                    {{ formatNumber(tokenStats.past_month?.total_tokens || 0) }}
                  </p>
                  <div class="flex justify-center gap-2 mt-1 text-xs text-gray-400">
                    <span
                      >{{ t('admin.inShort') }}:
                      {{ formatNumber(tokenStats.past_month?.input_tokens || 0) }}</span
                    >
                    <span
                      >{{ t('admin.outShort') }}:
                      {{ formatNumber(tokenStats.past_month?.output_tokens || 0) }}</span
                    >
                  </div>
                </div>
                <div class="text-center">
                  <p class="text-sm text-gray-500 mb-2">{{ t('admin.allTime') }}</p>
                  <p class="text-2xl font-bold text-gray-800 dark:text-white">
                    {{ formatNumber(tokenStats.total?.total_tokens || 0) }}
                  </p>
                  <div class="flex justify-center gap-2 mt-1 text-xs text-gray-400">
                    <span
                      >{{ t('admin.inShort') }}:
                      {{ formatNumber(tokenStats.total?.input_tokens || 0) }}</span
                    >
                    <span
                      >{{ t('admin.outShort') }}:
                      {{ formatNumber(tokenStats.total?.output_tokens || 0) }}</span
                    >
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

        <template v-else-if="activeTab === 'users'">
          <SchoolDashboardUsersTab
            v-if="effectiveOrgId != null"
            :org-id="effectiveOrgId"
          />
        </template>
      </template>
    </div>

    <el-dialog
      v-model="trendModalVisible"
      :title="trendChartTitle"
      width="640px"
      destroy-on-close
      @close="closeTrendModal"
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
              :class="{ 'ring-2 ring-primary-500': trendPeriod === 'today' }"
              @click="switchTrendPeriod('today')"
            >
              <p class="text-xs text-gray-500 dark:text-gray-400 mb-1">{{ t('admin.today') }}</p>
              <p class="text-lg font-bold text-gray-800 dark:text-white">{{ periodCards.today }}</p>
            </el-card>
            <el-card
              shadow="hover"
              class="token-period-card cursor-pointer"
              :class="{ 'ring-2 ring-primary-500': trendPeriod === 'week' }"
              @click="switchTrendPeriod('week')"
            >
              <p class="text-xs text-gray-500 dark:text-gray-400 mb-1">{{ t('admin.pastWeek') }}</p>
              <p class="text-lg font-bold text-gray-800 dark:text-white">{{ periodCards.week }}</p>
            </el-card>
            <el-card
              shadow="hover"
              class="token-period-card cursor-pointer"
              :class="{ 'ring-2 ring-primary-500': trendPeriod === 'month' }"
              @click="switchTrendPeriod('month')"
            >
              <p class="text-xs text-gray-500 dark:text-gray-400 mb-1">
                {{ t('admin.pastMonth') }}
              </p>
              <p class="text-lg font-bold text-gray-800 dark:text-white">{{ periodCards.month }}</p>
            </el-card>
            <el-card
              shadow="hover"
              class="token-period-card cursor-pointer"
              :class="{ 'ring-2 ring-primary-500': trendPeriod === 'total' }"
              @click="switchTrendPeriod('total')"
            >
              <p class="text-xs text-gray-500 dark:text-gray-400 mb-1">{{ t('admin.allTime') }}</p>
              <p class="text-lg font-bold text-gray-800 dark:text-white">{{ periodCards.total }}</p>
            </el-card>
          </div>
        </div>
      </template>
      <template #footer>
        <el-button @click="closeTrendModal">{{ t('common.close') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.stat-card :deep(.el-card__body) {
  padding: 20px;
}

.stat-card-clickable {
  cursor: pointer;
}

.stat-card-clickable:hover {
  transform: translateY(-1px);
}

.token-period-card :deep(.el-card__body) {
  padding: 12px 16px;
}

.school-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
}

.stat-item {
  padding: 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
}

.dark .stat-item {
  background: var(--el-fill-color-dark);
}

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
</style>
