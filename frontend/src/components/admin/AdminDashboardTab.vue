<script setup lang="ts">
/**
 * Admin Dashboard Tab - Real stats from /api/auth/admin/stats
 * Clickable stat cards open Chart.js trend charts (like archive admin)
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

import { Connection, Document, Loading, TrendCharts, User } from '@element-plus/icons-vue'

import {
  Chart,
  registerables,
  type ChartConfiguration,
  type TooltipItem,
} from 'chart.js'

Chart.register(...registerables)

import { useLanguage, useNotifications } from '@/composables'
import { apiRequest } from '@/utils/apiClient'

const { t } = useLanguage()
const notify = useNotifications()

const isLoading = ref(true)
const stats = ref({
  totalUsers: 0,
  totalOrganizations: 0,
  recentRegistrations: 0,
  totalTokens: 0,
})
interface OrgStats {
  total_tokens: number
  org_id?: number
}
const tokenStatsByOrg = ref<Record<string, OrgStats>>({})
const usersByOrg = ref<Record<string, number>>({})

const topOrgsByTokens = computed(() =>
  Object.entries(tokenStatsByOrg.value)
    .map(([name, v]) => ({
      name,
      tokens: v.total_tokens,
      orgId: v.org_id,
    }))
    .sort((a, b) => b.tokens - a.tokens)
    .slice(0, 10)
)

const trendModalVisible = ref(false)
const trendChartTitle = ref('')
const trendChartLoading = ref(false)
const trendChartRef = ref<HTMLCanvasElement | null>(null)
let trendChartInstance: Chart<'line'> | null = null

const periodCards = ref({
  today: '-',
  week: '-',
  month: '-',
  total: '-',
})
const trendContext = ref<{
  type: 'metric' | 'org'
  metric?: MetricKey
  orgName?: string
  orgId?: number
  period: 'today' | 'week' | 'month' | 'total'
}>({ type: 'metric', period: 'week' })

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

async function loadStats() {
  isLoading.value = true
  try {
    const response = await apiRequest('/api/auth/admin/stats')
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      notify.error(data.detail || t('admin.dashboardLoadError'))
      return
    }
    const data = await response.json()
    stats.value = {
      totalUsers: data.total_users ?? 0,
      totalOrganizations: data.total_organizations ?? 0,
      recentRegistrations: data.recent_registrations ?? 0,
      totalTokens: data.token_stats?.total_tokens ?? 0,
    }
    const byOrg = data.token_stats_by_org ?? {}
    tokenStatsByOrg.value = Object.fromEntries(
      Object.entries(byOrg).map(([k, v]) => [
        k,
        {
          total_tokens: (v as { total_tokens?: number }).total_tokens ?? 0,
          org_id: (v as { org_id?: number }).org_id,
        },
      ])
    )
    usersByOrg.value = data.users_by_org ?? {}
  } catch {
    notify.error(t('admin.dashboardLoadError'))
  } finally {
    isLoading.value = false
  }
}

type MetricKey =
  | 'users'
  | 'organizations'
  | 'registrations'
  | 'tokens'

async function showTrendChart(metric: MetricKey, period: 'today' | 'week' | 'month' | 'total' = 'week') {
  trendContext.value = { type: 'metric', metric, period }
  trendChartTitle.value =
    metric === 'users'
      ? t('admin.trendUsers')
      : metric === 'organizations'
        ? t('admin.trendOrganizations')
        : metric === 'registrations'
          ? t('admin.trendRegistrations')
          : t('admin.trendTokens')
  trendModalVisible.value = true
  trendChartLoading.value = true

  const daysMap = { today: 1, week: 7, month: 30, total: 0 }
  const days = daysMap[period]
  try {
    const [chartRes, cardsRes] = await Promise.all([
      apiRequest(`/api/auth/admin/stats/trends?metric=${metric}&days=${days}`),
      metric === 'tokens'
        ? apiRequest('/api/auth/admin/token-stats')
        : apiRequest(`/api/auth/admin/stats/trends?metric=${metric}&days=0`),
    ])
    if (!chartRes.ok) {
      notify.error(t('admin.dashboardLoadError'))
      trendChartLoading.value = false
      return
    }
    const data = await chartRes.json()
    trendChartLoading.value = false
    await nextTick()
    await new Promise((r) => setTimeout(r, 50))
    renderTrendChart(data, metric)
    if (metric === 'tokens' && cardsRes.ok) {
      const tokenData = await cardsRes.json()
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
    } else if (cardsRes.ok && metric !== 'tokens') {
      const cardsData = await cardsRes.json()
      const arr = cardsData?.data ?? []
      if (metric === 'registrations') {
        const sum = (n: number) => arr.slice(-n).reduce((a: number, b: { value: number }) => a + (b.value ?? 0), 0)
        periodCards.value = {
          today: String(sum(1) || 0),
          week: String(sum(7) || 0),
          month: String(sum(30) || 0),
          total: String(arr.reduce((a: number, b: { value: number }) => a + (b.value ?? 0), 0)),
        }
      } else {
        const valAt = (idx: number) => (arr.length > idx ? arr[arr.length - 1 - idx]?.value ?? '-' : '-')
        const final = arr.length ? arr[arr.length - 1]?.value ?? '-' : '-'
        periodCards.value = {
          today: String(final),
          week: String(valAt(7)),
          month: String(valAt(30)),
          total: String(final),
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

async function showOrganizationTrendChart(
  orgName: string,
  orgId?: number,
  period: 'today' | 'week' | 'month' | 'total' = 'week'
) {
  trendContext.value = { type: 'org', orgName, orgId, period }
  trendChartTitle.value = `${t('admin.trendOrgTokens')}: ${orgName}`
  trendModalVisible.value = true
  trendChartLoading.value = true

  const daysMap = { today: 1, week: 7, month: 30, total: 0 }
  const days = daysMap[period]
  const hourly = period === 'today'
  try {
    let params = `days=${days}&hourly=${hourly}`
    if (orgId) {
      params += `&organization_id=${orgId}`
    } else {
      params += `&organization_name=${encodeURIComponent(orgName)}`
    }
    const chartRes = await apiRequest(
      `/api/auth/admin/stats/trends/organization?${params}`
    )
    if (!chartRes.ok) {
      notify.error(t('admin.dashboardLoadError'))
      trendChartLoading.value = false
      return
    }
    const data = await chartRes.json()
    trendChartLoading.value = false
    await nextTick()
    await new Promise((r) => setTimeout(r, 50))
    renderTrendChart(data, 'tokens')
    if (orgId != null) {
      const statsRes = await apiRequest(`/api/auth/admin/token-stats?organization_id=${orgId}`)
      if (statsRes.ok) {
        const tokenData = await statsRes.json()
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
      } else {
        periodCards.value = { today: '-', week: '-', month: '-', total: '-' }
      }
    } else {
      periodCards.value = { today: '-', week: '-', month: '-', total: '-' }
    }
  } catch {
    notify.error(t('admin.dashboardLoadError'))
    trendChartLoading.value = false
  }
}

function switchTrendPeriod(period: 'today' | 'week' | 'month' | 'total') {
  const ctx = trendContext.value
  if (ctx.type === 'org' && ctx.orgName) {
    showOrganizationTrendChart(ctx.orgName, ctx.orgId, period)
  } else if (ctx.type === 'metric' && ctx.metric) {
    showTrendChart(ctx.metric, period)
  }
}

function renderTrendChart(
  data: { data: Array<{ date: string; value: number; input?: number; output?: number }> },
  metric: MetricKey | 'tokens'
) {
  if (!trendChartRef.value) return

  const rawData = data?.data ?? []
  if (rawData.length === 0) return

  trendChartInstance?.destroy()
  trendChartInstance = null

  const labels = rawData.map((item) => {
    const dateStr = item.date.includes(' ') ? item.date.replace(' ', 'T') : item.date + 'T00:00:00'
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

  const hasInputOutput =
    metric === 'tokens' &&
    rawData[0] &&
    (rawData[0].input !== undefined || rawData[0].output !== undefined)

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
        legend: {
          display: hasInputOutput,
          position: 'top',
        },
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
          ticks: {
            callback: (val: string | number) => formatChartLabel(Number(val)),
          },
        },
        x: {
          ticks: {
            maxRotation: 45,
            minRotation: 45,
          },
        },
      },
    },
  }

  trendChartInstance = new Chart(trendChartRef.value, config)
}

function closeTrendModal() {
  trendModalVisible.value = false
  trendChartInstance?.destroy()
  trendChartInstance = null
}

onMounted(loadStats)
onBeforeUnmount(() => {
  trendChartInstance?.destroy()
  trendChartInstance = null
})
</script>

<template>
  <div class="admin-dashboard-tab">
    <div
      v-if="isLoading"
      class="flex justify-center py-20"
    >
      <el-icon
        class="is-loading"
        :size="32"
      >
        <Loading />
      </el-icon>
    </div>

    <template v-else>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 pt-4">
        <el-card
          shadow="hover"
          class="stat-card stat-card-clickable"
          @click="showTrendChart('users')"
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
          @click="showTrendChart('registrations')"
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
          @click="showTrendChart('organizations')"
        >
          <div class="flex items-center gap-4">
            <div
              class="w-12 h-12 bg-purple-100 dark:bg-purple-900 rounded-lg flex items-center justify-center"
            >
              <el-icon
                :size="24"
                class="text-purple-500"
              >
                <Document />
              </el-icon>
            </div>
            <div>
              <p class="text-sm text-gray-500 dark:text-gray-400">
                {{ t('admin.schools') }}
              </p>
              <p class="text-2xl font-bold text-gray-800 dark:text-white">
                {{ stats.totalOrganizations.toLocaleString() }}
              </p>
            </div>
          </div>
        </el-card>

        <el-card
          shadow="hover"
          class="stat-card stat-card-clickable"
          @click="showTrendChart('tokens')"
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
        v-if="topOrgsByTokens.length > 0"
        shadow="hover"
        class="mt-6"
      >
        <template #header>
          <span class="font-medium">{{ t('admin.topSchoolsByTokens') }}</span>
          <el-button
            text
            size="small"
            @click="loadStats"
          >
            {{ t('common.refresh') }}
          </el-button>
        </template>
        <el-table
          :data="topOrgsByTokens"
          stripe
          size="small"
        >
          <el-table-column
            prop="name"
            :label="t('admin.schoolName')"
          >
            <template #default="{ row }">
              <span
                class="cursor-pointer hover:text-primary-500 hover:underline"
                @click="showOrganizationTrendChart(row.name, row.orgId)"
              >
                {{ row.name }}
              </span>
            </template>
          </el-table-column>
          <el-table-column
            prop="tokens"
            :label="t('admin.tokens')"
            width="140"
          >
            <template #default="{ row }">
              <span
                class="cursor-pointer hover:text-primary-500"
                @click="showOrganizationTrendChart(row.name, row.orgId)"
              >
                {{ formatNumber(row.tokens) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column
            :label="t('admin.usersCount')"
            width="100"
          >
            <template #default="{ row }">
              {{ usersByOrg[row.name] ?? 0 }}
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </template>

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
              :class="{ 'ring-2 ring-primary-500': trendContext.period === 'today' }"
              @click="switchTrendPeriod('today')"
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
              @click="switchTrendPeriod('week')"
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
              @click="switchTrendPeriod('month')"
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
              @click="switchTrendPeriod('total')"
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
</style>
