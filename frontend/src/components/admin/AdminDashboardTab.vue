<script setup lang="ts">
/**
 * Admin Dashboard Tab — stats from GET /api/auth/admin/stats.
 * School and user token rankings use today (Beijing time); stat cards open Chart.js trends.
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import AdminSwissKpiCard from '@/components/admin/swiss/AdminSwissKpiCard.vue'
import AdminSwissPeriodCard from '@/components/admin/swiss/AdminSwissPeriodCard.vue'
import AdminSwissServiceCard from '@/components/admin/swiss/AdminSwissServiceCard.vue'
import AdminTokenOverviewRow from '@/components/admin/AdminTokenOverviewRow.vue'
import AdminTokenUsageByServicePanel from '@/components/admin/AdminTokenUsageByServicePanel.vue'
import AdminOrgTokenTrendDialog from '@/components/admin/AdminOrgTokenTrendDialog.vue'
import { Connection, Document, Loading, TrendCharts, User } from '@element-plus/icons-vue'

import type { Chart as ChartInstance } from 'chart.js'

import { useAdminAccess } from '@/composables/admin/useAdminAccess'
import { useAdminEventBus } from '@/composables/admin/useAdminEventBus'
import {
  queryErrorMessage,
  useQueryErrorNotification,
} from '@/composables/admin/useQueryErrorNotification'
import { useScopedAbort } from '@/composables/core/useScopedAbort'
import { useLanguage, useNotifications } from '@/composables'
import { intlLocaleForUiCode } from '@/i18n/locales'
import { useUIStore } from '@/stores/ui'
import {
  fetchAdminStatsTrends,
  fetchAdminStatsTrendsUser,
  fetchAdminTokenStats,
  useAdminStats,
  useAdminTokenStats,
} from '@/composables/queries'
import { type ChartConfiguration, type TooltipItem, loadChartJs } from '@/utils/lazyChartJs'

const props = withDefaults(
  defineProps<{
    section?: 'operations' | 'usage' | 'all'
  }>(),
  { section: 'all' }
)

const showOperations = computed(
  () => props.section === 'all' || props.section === 'operations'
)
const showUsageByService = computed(() => props.section === 'usage')
const showTokenRankings = computed(() => showOperations.value || showUsageByService.value)

const { t } = useLanguage()
const uiStore = useUIStore()
const notify = useNotifications()
const { can } = useAdminAccess()
const { on: onAdminEvent } = useAdminEventBus('AdminDashboardTab')

const statsQuery = useAdminStats()
const tokenStatsQuery = useAdminTokenStats(undefined, {
  enabled: computed(() => showUsageByService.value),
})
const { beginRequest: beginTrendRequest, abort: abortTrendRequests } = useScopedAbort()

useQueryErrorNotification(statsQuery.error, () => t('admin.dashboardLoadError'))
useQueryErrorNotification(tokenStatsQuery.error, () => t('admin.dashboardLoadError'))

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

interface PlatformTokenStats {
  today: TokenPeriodStats
  past_week: TokenPeriodStats
  past_month: TokenPeriodStats
  total: TokenPeriodStats
  dingtalk_generations?: Record<string, number>
  by_service: {
    mindgraph: ServiceStats
    mindmate: ServiceStats
  }
}

type TokenTrendService = 'mindgraph' | 'mindmate' | null

const isLoading = computed(() => statsQuery.isFetching.value)
const platformTokenStats = ref<PlatformTokenStats | null>(null)
const showDingtalkOverview = computed(() => can('tab.settings.tokens'))
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
const tokenStatsByOrgMindgraph = ref<Record<string, OrgStats>>({})
const tokenStatsByOrgMindmate = ref<Record<string, OrgStats>>({})

function parseOrgTokenStats(byOrg: Record<string, unknown>): Record<string, OrgStats> {
  return Object.fromEntries(
    Object.entries(byOrg).map(([key, value]) => [
      key,
      {
        total_tokens: (value as { total_tokens?: number }).total_tokens ?? 0,
        org_id: (value as { org_id?: number }).org_id,
      },
    ])
  )
}

function topOrgsFromStats(byOrg: Record<string, OrgStats>) {
  return Object.entries(byOrg)
    .map(([name, entry]) => ({
      name,
      tokens: entry.total_tokens,
      orgId: entry.org_id,
    }))
    .sort((a, b) => b.tokens - a.tokens)
    .slice(0, 10)
}

const topOrgsByTokens = computed(() => topOrgsFromStats(tokenStatsByOrg.value))
const topOrgsByMindgraph = computed(() => topOrgsFromStats(tokenStatsByOrgMindgraph.value))
const topOrgsByMindmate = computed(() => topOrgsFromStats(tokenStatsByOrgMindmate.value))

const topUsersByTokens = ref<
  { id: number; name: string; phone: string; total_tokens: number; organization_name: string }[]
>([])

const trendModalVisible = ref(false)
const trendChartTitle = ref('')
const trendChartLoading = ref(false)
const trendChartHasData = ref(true)
const trendChartRef = ref<HTMLCanvasElement | null>(null)
let trendChartInstance: ChartInstance<'line'> | null = null

const periodCards = ref({
  today: '-',
  week: '-',
  month: '-',
  total: '-',
})
const trendContext = ref<{
  type: 'metric' | 'org' | 'user' | 'service'
  metric?: MetricKey
  service?: TokenTrendService
  orgName?: string
  orgId?: number
  userName?: string
  userId?: number
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

function applyStatsPayload(data: Record<string, unknown>): void {
  stats.value = {
    totalUsers: (data.total_users as number | undefined) ?? 0,
    totalOrganizations: (data.total_organizations as number | undefined) ?? 0,
    recentRegistrations: (data.recent_registrations as number | undefined) ?? 0,
    totalTokens:
      ((data.token_stats as { total_tokens?: number } | undefined)?.total_tokens) ?? 0,
  }
  tokenStatsByOrg.value = parseOrgTokenStats(
    (data.token_stats_by_org ?? {}) as Record<string, unknown>
  )
  tokenStatsByOrgMindgraph.value = parseOrgTokenStats(
    (data.token_stats_by_org_mindgraph ?? {}) as Record<string, unknown>
  )
  tokenStatsByOrgMindmate.value = parseOrgTokenStats(
    (data.token_stats_by_org_mindmate ?? {}) as Record<string, unknown>
  )
  const rawTop = data.top_users_by_tokens_today as
    | {
        id?: number
        name?: string
        phone?: string
        total_tokens?: number
        organization_name?: string
      }[]
    | undefined
  topUsersByTokens.value = (rawTop ?? []).map((u) => ({
    id: Number(u.id) || 0,
    name: String(u.name ?? ''),
    phone: String(u.phone ?? ''),
    total_tokens: Number(u.total_tokens ?? 0),
    organization_name: String(u.organization_name ?? ''),
  }))
}

watch(
  () => statsQuery.data.value,
  (data) => {
    if (data) {
      applyStatsPayload(data as Record<string, unknown>)
    }
  },
  { immediate: true }
)

watch(
  () => tokenStatsQuery.data.value,
  (data) => {
    if (!showUsageByService.value) {
      platformTokenStats.value = null
      return
    }
    platformTokenStats.value = (data as unknown as PlatformTokenStats | null) ?? null
  },
  { immediate: true }
)

async function loadPlatformTokenStats(): Promise<void> {
  if (!showUsageByService.value) {
    return
  }
  try {
    await tokenStatsQuery.refetch()
    platformTokenStats.value =
      (tokenStatsQuery.data.value as unknown as PlatformTokenStats | null) ?? null
  } catch {
    platformTokenStats.value = null
  }
}

async function loadStats() {
  const requests: Promise<unknown>[] = [statsQuery.refetch()]
  if (showUsageByService.value) {
    requests.push(tokenStatsQuery.refetch())
  }
  await Promise.all(requests)
}

function notifyTrendFetchError(err: unknown): void {
  const message = queryErrorMessage(err, t('admin.dashboardLoadError'))
  if (message) {
    notify.error(message)
  }
  trendChartLoading.value = false
}

type MetricKey = 'users' | 'organizations' | 'registrations' | 'tokens'

async function showTrendChart(
  metric: MetricKey,
  period: 'today' | 'week' | 'month' | 'total' = 'week'
) {
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
  const signal = beginTrendRequest()
  try {
    const [chartData, cardsData] = await Promise.all([
      fetchAdminStatsTrends(
        { metric, days, service: metric === 'tokens' ? null : undefined },
        signal
      ),
      metric === 'tokens'
        ? fetchAdminTokenStats(undefined, signal)
        : fetchAdminStatsTrends({ metric, days: 0 }, signal),
    ])
    trendChartLoading.value = false
    await nextTick()
    await new Promise((r) => setTimeout(r, 50))
    await renderTrendChart(chartData as { data: Array<{ date: string; value: number; input?: number; output?: number }> }, metric)
    if (metric === 'tokens') {
      const tokenData = cardsData as unknown as PlatformTokenStats
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
      const cardsResData = cardsData as { data?: Array<{ value: number }> }
      const arr = cardsResData?.data ?? []
      if (metric === 'registrations') {
        const sum = (n: number) =>
          arr.slice(-n).reduce((a: number, b: { value: number }) => a + (b.value ?? 0), 0)
        periodCards.value = {
          today: String(sum(1) || 0),
          week: String(sum(7) || 0),
          month: String(sum(30) || 0),
          total: String(arr.reduce((a: number, b: { value: number }) => a + (b.value ?? 0), 0)),
        }
      } else {
        const valAt = (idx: number) =>
          arr.length > idx ? (arr[arr.length - 1 - idx]?.value ?? '-') : '-'
        const final = arr.length ? (arr[arr.length - 1]?.value ?? '-') : '-'
        periodCards.value = {
          today: String(final),
          week: String(valAt(7)),
          month: String(valAt(30)),
          total: String(final),
        }
      }
    }
  } catch (err) {
    notifyTrendFetchError(err)
  }
}

const orgTrendDialogRef = ref<InstanceType<typeof AdminOrgTokenTrendDialog> | null>(null)

function showOrganizationTrendChart(
  orgName: string,
  orgId?: number,
  period: 'today' | 'week' | 'month' | 'total' = 'week',
  service: TokenTrendService = null
) {
  orgTrendDialogRef.value?.openTrend({
    orgName,
    orgId,
    period,
    service,
  })
}

function switchTrendPeriod(period: 'today' | 'week' | 'month' | 'total') {
  const ctx = trendContext.value
  if (ctx.type === 'org' && ctx.orgName) {
    showOrganizationTrendChart(ctx.orgName, ctx.orgId, period, ctx.service ?? null)
  } else if (ctx.type === 'user' && ctx.userId != null) {
    showUserTokenTrend(ctx.userName ?? '', ctx.userId, period)
  } else if (ctx.type === 'service') {
    showServiceTokenTrendChart(ctx.service ?? null, period)
  } else if (ctx.type === 'metric' && ctx.metric) {
    showTrendChart(ctx.metric, period)
  }
}

async function showServiceTokenTrendChart(
  service: TokenTrendService,
  period: 'today' | 'week' | 'month' | 'total' = 'week'
) {
  trendContext.value = { type: 'service', service, period }
  if (service === 'mindgraph') {
    trendChartTitle.value = `${t('admin.serviceMindGraph')} - ${t('admin.trendTokens')}`
  } else if (service === 'mindmate') {
    trendChartTitle.value = `${t('admin.serviceMindMate')} - ${t('admin.trendTokens')}`
  } else {
    trendChartTitle.value = t('admin.trendTokens')
  }
  trendModalVisible.value = true
  trendChartLoading.value = true

  const daysMap = { today: 1, week: 7, month: 30, total: 0 }
  const signal = beginTrendRequest()

  try {
    const [data, tokenStatsData] = await Promise.all([
      fetchAdminStatsTrends(
        {
          metric: 'tokens',
          days: daysMap[period],
          service,
        },
        signal
      ),
      fetchAdminTokenStats(undefined, signal),
    ])
    platformTokenStats.value = tokenStatsData as unknown as PlatformTokenStats
    trendChartLoading.value = false
    await nextTick()
    await new Promise((r) => setTimeout(r, 50))
    await renderTrendChart(data as { data: Array<{ date: string; value: number; input?: number; output?: number }> }, 'tokens')

    const fmt = (p: { input_tokens?: number; output_tokens?: number }) =>
      `${formatNumber(p?.input_tokens ?? 0)}+${formatNumber(p?.output_tokens ?? 0)}`

    const statsData = platformTokenStats.value
    if (statsData) {
      if (service === 'mindgraph' && statsData.by_service?.mindgraph) {
        const s = statsData.by_service.mindgraph
        periodCards.value = {
          today: fmt(s.today),
          week: fmt(s.week),
          month: fmt(s.month),
          total: fmt(s.total),
        }
      } else if (service === 'mindmate' && statsData.by_service?.mindmate) {
        const s = statsData.by_service.mindmate
        periodCards.value = {
          today: fmt(s.today),
          week: fmt(s.week),
          month: fmt(s.month),
          total: fmt(s.total),
        }
      } else {
        periodCards.value = {
          today: fmt(statsData.today),
          week: fmt(statsData.past_week),
          month: fmt(statsData.past_month),
          total: fmt(statsData.total),
        }
      }
    } else {
      periodCards.value = { today: '-', week: '-', month: '-', total: '-' }
    }
  } catch (err) {
    notifyTrendFetchError(err)
  }
}

async function showUserTokenTrend(
  userName: string,
  userId: number,
  period: 'today' | 'week' | 'month' | 'total' = 'week'
) {
  if (!Number.isFinite(userId) || userId <= 0) {
    return
  }
  trendContext.value = { type: 'user', userName, userId, period }
  trendChartTitle.value = `${t('admin.trendUserTokens')}: ${userName}`
  trendModalVisible.value = true
  trendChartLoading.value = true

  const daysMap = { today: 1, week: 7, month: 30, total: 0 }
  const days = daysMap[period]
  const daysParam = days === 0 ? 0 : days
  const hourly = period === 'today'
  const signal = beginTrendRequest()
  try {
    const data = await fetchAdminStatsTrendsUser(
      {
        user_id: userId,
        days: daysParam,
        hourly,
      },
      signal
    )
    trendChartLoading.value = false
    await nextTick()
    await new Promise((r) => setTimeout(r, 50))
    await renderTrendChart(data as { data: Array<{ date: string; value: number; input?: number; output?: number }> }, 'tokens')
    const cardsData = await fetchAdminStatsTrendsUser({ user_id: userId, days: 0 }, signal)
    const arr = (cardsData as { data?: Array<{ value?: number }> }).data ?? []
    const sum = (n: number) =>
      arr.slice(-n).reduce((a: number, b: { value?: number }) => a + (b.value ?? 0), 0)
    periodCards.value = {
      today: formatNumber(sum(1) || 0),
      week: formatNumber(sum(7) || 0),
      month: formatNumber(sum(30) || 0),
      total: formatNumber(
        arr.reduce((a: number, b: { value?: number }) => a + (b.value ?? 0), 0)
      ),
    }
  } catch (err) {
    notifyTrendFetchError(err)
  }
}

async function renderTrendChart(
  data: { data: Array<{ date: string; value: number; input?: number; output?: number }> },
  metric: MetricKey | 'tokens'
): Promise<void> {
  if (!trendChartRef.value) return

  const rawData = data?.data ?? []
  trendChartHasData.value = rawData.length > 0
  if (rawData.length === 0) {
    trendChartInstance?.destroy()
    trendChartInstance = null
    return
  }

  trendChartInstance?.destroy()
  trendChartInstance = null

  const intlLocale = intlLocaleForUiCode(uiStore.language)
  const labels = rawData.map((item) => {
    const dateStr = item.date.includes(' ') ? item.date.replace(' ', 'T') : item.date + 'T00:00:00'
    const date = new Date(dateStr)
    if (item.date.includes(':') && item.date.includes(' ')) {
      return date.toLocaleString(intlLocale, {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        hour12: false,
        timeZone: 'Asia/Shanghai',
      })
    }
    return date.toLocaleDateString(intlLocale, {
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

  const Chart = await loadChartJs()
  trendChartInstance = new Chart(trendChartRef.value, config)
}

function closeTrendModal() {
  abortTrendRequests()
  trendModalVisible.value = false
  trendChartInstance?.destroy()
  trendChartInstance = null
}

onMounted(() => {
  void loadStats()
})

onAdminEvent('admin:refresh_requested', ({ domain }) => {
  if (domain === 'stats' || domain === 'token-stats' || domain === 'all') {
    void loadStats()
  }
})
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
      <div
        v-if="showOperations"
        class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 pt-4"
      >
        <AdminSwissKpiCard
          :title="t('admin.totalUsers')"
          :value="stats.totalUsers"
          :icon="User"
          theme="members"
          clickable
          @click="showTrendChart('users')"
        />
        <AdminSwissKpiCard
          :title="t('admin.todayRegistrations')"
          :value="stats.recentRegistrations"
          :icon="TrendCharts"
          theme="success"
          clickable
          @click="showTrendChart('registrations')"
        />
        <AdminSwissKpiCard
          :title="t('admin.schools')"
          :value="stats.totalOrganizations"
          :icon="Document"
          theme="managers"
          clickable
          @click="showTrendChart('organizations')"
        />
        <AdminSwissKpiCard
          :title="`${t('admin.tokens')} (${t('admin.pastWeek')})`"
          :value="formatNumber(stats.totalTokens)"
          :icon="Connection"
          theme="storage"
          clickable
          @click="showTrendChart('tokens')"
        />
      </div>

      <AdminTokenUsageByServicePanel
        v-if="showUsageByService"
        class="pt-4"
        :stats="platformTokenStats ?? undefined"
        clickable
        @service-click="showServiceTokenTrendChart($event)"
        @overall-click="showServiceTokenTrendChart(null)"
        @period-click="(service, period) => showServiceTokenTrendChart(service, period)"
      />

      <AdminTokenOverviewRow
        v-if="showUsageByService && platformTokenStats"
        class="mt-6"
        :token-stats="platformTokenStats"
        :show-dingtalk="showDingtalkOverview"
        clickable
        @overall-click="showServiceTokenTrendChart(null)"
        @period-click="(period) => showServiceTokenTrendChart(null, period)"
        @refresh="loadPlatformTokenStats"
      />

      <div
        v-if="showTokenRankings"
        class="mt-6"
      >
        <div class="flex flex-wrap items-start justify-between gap-3 mb-3">
          <p class="text-sm text-gray-500 dark:text-gray-400 flex-1 min-w-[200px]">
            {{ t('admin.rankingBeijingTodayHint') }}
          </p>
          <el-button
            text
            size="small"
            type="primary"
            @click="loadStats"
          >
            {{ t('common.refresh') }}
          </el-button>
        </div>
        <div
          v-if="showUsageByService"
          class="grid grid-cols-1 xl:grid-cols-2 gap-6"
        >
          <AdminSwissServiceCard theme="mindgraph">
            <template #header>
              <span class="swiss-stat-card__service-title">{{
                t('admin.topSchoolsByMindGraphTokens')
              }}</span>
            </template>
            <el-table
              :data="topOrgsByMindgraph"
              stripe
              size="small"
              :empty-text="t('admin.listRangeEmpty')"
            >
              <el-table-column
                prop="name"
                :label="t('admin.schoolName')"
              >
                <template #default="{ row }">
                  <span
                    class="cursor-pointer hover:text-primary-500 hover:underline"
                    @click="showOrganizationTrendChart(row.name, row.orgId, 'today', 'mindgraph')"
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
                    @click="showOrganizationTrendChart(row.name, row.orgId, 'today', 'mindgraph')"
                  >
                    {{ formatNumber(row.tokens) }}
                  </span>
                </template>
              </el-table-column>
            </el-table>
          </AdminSwissServiceCard>

          <AdminSwissServiceCard theme="mindmate">
            <template #header>
              <span class="swiss-stat-card__service-title">{{
                t('admin.topSchoolsByMindMateTokens')
              }}</span>
            </template>
            <el-table
              :data="topOrgsByMindmate"
              stripe
              size="small"
              :empty-text="t('admin.listRangeEmpty')"
            >
              <el-table-column
                prop="name"
                :label="t('admin.schoolName')"
              >
                <template #default="{ row }">
                  <span
                    class="cursor-pointer hover:text-primary-500 hover:underline"
                    @click="showOrganizationTrendChart(row.name, row.orgId, 'today', 'mindmate')"
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
                    @click="showOrganizationTrendChart(row.name, row.orgId, 'today', 'mindmate')"
                  >
                    {{ formatNumber(row.tokens) }}
                  </span>
                </template>
              </el-table-column>
            </el-table>
          </AdminSwissServiceCard>
        </div>
        <div
          v-else-if="showOperations"
          class="grid grid-cols-1 xl:grid-cols-2 gap-6"
        >
          <el-card shadow="hover">
            <template #header>
              <span class="font-medium">{{ t('admin.topSchoolsByTokens') }}</span>
            </template>
            <el-table
              :data="topOrgsByTokens"
              stripe
              size="small"
              :empty-text="t('admin.listRangeEmpty')"
            >
              <el-table-column
                prop="name"
                :label="t('admin.schoolName')"
              >
                <template #default="{ row }">
                  <span
                    class="cursor-pointer hover:text-primary-500 hover:underline"
                    @click="showOrganizationTrendChart(row.name, row.orgId, 'today')"
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
                    @click="showOrganizationTrendChart(row.name, row.orgId, 'today')"
                  >
                    {{ formatNumber(row.tokens) }}
                  </span>
                </template>
              </el-table-column>
            </el-table>
          </el-card>

          <el-card shadow="hover">
            <template #header>
              <span class="font-medium">{{ t('admin.topUsersByTokens') }}</span>
            </template>
            <el-table
              :data="topUsersByTokens"
              stripe
              size="small"
              :empty-text="t('admin.listRangeEmpty')"
            >
              <el-table-column
                prop="name"
                :label="t('admin.users')"
                min-width="120"
              >
                <template #default="{ row }">
                  <span
                    class="cursor-pointer hover:text-primary-500 hover:underline"
                    @click="showUserTokenTrend(row.name, row.id, 'today')"
                  >
                    {{ row.name }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column
                prop="organization_name"
                :label="t('admin.schoolName')"
                min-width="100"
                show-overflow-tooltip
              >
                <template #default="{ row }">
                  {{ row.organization_name || '—' }}
                </template>
              </el-table-column>
              <el-table-column
                prop="phone"
                :label="t('admin.phone')"
                width="120"
              />
              <el-table-column
                prop="total_tokens"
                :label="t('admin.tokens')"
                width="120"
              >
                <template #default="{ row }">
                  <span
                    class="cursor-pointer hover:text-primary-500"
                    @click="showUserTokenTrend(row.name, row.id, 'today')"
                  >
                    {{ formatNumber(row.total_tokens) }}
                  </span>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </div>
      </div>
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
        <div
          v-if="!trendChartHasData"
          class="flex justify-center items-center h-64 text-gray-500 dark:text-gray-400"
        >
          {{ t('admin.trendChartNoData') }}
        </div>
        <div
          v-else
          class="relative h-64 min-h-[256px] w-full"
        >
          <canvas
            ref="trendChartRef"
            class="block w-full h-full"
          />
        </div>
        <div class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
          <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
            <AdminSwissPeriodCard
              :label="t('admin.today')"
              :value="periodCards.today"
              :active="trendContext.period === 'today'"
              theme="storage"
              @click="switchTrendPeriod('today')"
            />
            <AdminSwissPeriodCard
              :label="t('admin.pastWeek')"
              :value="periodCards.week"
              :active="trendContext.period === 'week'"
              theme="storage"
              @click="switchTrendPeriod('week')"
            />
            <AdminSwissPeriodCard
              :label="t('admin.pastMonth')"
              :value="periodCards.month"
              :active="trendContext.period === 'month'"
              theme="storage"
              @click="switchTrendPeriod('month')"
            />
            <AdminSwissPeriodCard
              :label="t('admin.allTime')"
              :value="periodCards.total"
              :active="trendContext.period === 'total'"
              theme="storage"
              @click="switchTrendPeriod('total')"
            />
          </div>
        </div>
      </template>
      <template #footer>
        <el-button @click="closeTrendModal">{{ t('common.close') }}</el-button>
      </template>
    </el-dialog>

    <AdminOrgTokenTrendDialog ref="orgTrendDialogRef" />
  </div>
</template>

