<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { Key, Loading, Refresh, Warning } from '@element-plus/icons-vue'

import type { Chart as ChartInstance } from 'chart.js'

import AdminDingtalkGenerationApiKeysDialog from '@/components/admin/AdminDingtalkGenerationApiKeysDialog.vue'
import AdminSwissPeriodCard from '@/components/admin/swiss/AdminSwissPeriodCard.vue'
import AdminSwissServiceCard from '@/components/admin/swiss/AdminSwissServiceCard.vue'
import AdminTokenUsageByServicePanel from '@/components/admin/AdminTokenUsageByServicePanel.vue'
import { useLanguage, useNotifications } from '@/composables'
import { apiRequest } from '@/utils/apiClient'
import { type ChartConfiguration, type TooltipItem, loadChartJs } from '@/utils/lazyChartJs'

const { t } = useLanguage()
const notify = useNotifications()

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

const isLoadingTokens = ref(false)
const tokenStats = ref<TokenStats | null>(null)

type TokenTrendService = 'mindgraph' | 'mindmate' | null
const trendModalVisible = ref(false)
const trendChartTitle = ref('')
const trendChartLoading = ref(false)
const trendChartRef = ref<HTMLCanvasElement | null>(null)
let trendChartInstance: ChartInstance<'line'> | null = null
const periodCards = ref({ today: '-', week: '-', month: '-', total: '-' })
const trendContext = ref<{
  service: TokenTrendService
  period: 'today' | 'week' | 'month' | 'total'
}>({ service: null, period: 'week' })

const dingtalkApiKeysDialogVisible = ref(false)
/** Cumulative X-API-Key usage (sum of per-key `usage_count`). */
const dingtalkKeyUsesTotal = ref<number | null>(null)

function openDingtalkApiKeysDialog(): void {
  dingtalkApiKeysDialogVisible.value = true
}

async function loadDingtalkKeyUsesTotal(): Promise<void> {
  try {
    const res = await apiRequest('/api/auth/admin/api_keys')
    if (!res.ok) {
      dingtalkKeyUsesTotal.value = null
      return
    }
    const raw: unknown = await res.json()
    const list: Array<{ usage_count?: number }> = Array.isArray(raw) ? raw : []
    const sum = list.reduce((acc, row) => acc + (row.usage_count ?? 0), 0)
    dingtalkKeyUsesTotal.value = sum
  } catch {
    dingtalkKeyUsesTotal.value = null
  }
}

function onDingtalkCardKeydown(e: KeyboardEvent): void {
  if (e.key !== 'Enter' && e.key !== ' ') {
    return
  }
  e.preventDefault()
  openDingtalkApiKeysDialog()
}

watch(dingtalkApiKeysDialogVisible, (open) => {
  if (!open) {
    void loadDingtalkKeyUsesTotal()
  }
})

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

const overallPeriods = [
  { key: 'today' as const, label: () => t('admin.today'), statsKey: 'today' as const },
  { key: 'week' as const, label: () => t('admin.pastWeek'), statsKey: 'past_week' as const },
  { key: 'month' as const, label: () => t('admin.pastMonth'), statsKey: 'past_month' as const },
  { key: 'total' as const, label: () => t('admin.allTime'), statsKey: 'total' as const },
]

async function loadTokenStats() {
  if (isLoadingTokens.value) return
  isLoadingTokens.value = true
  try {
    const response = await apiRequest('/api/auth/admin/token-stats')
    if (response.ok) {
      tokenStats.value = await response.json()
      void loadDingtalkKeyUsesTotal()
    } else {
      const data = await response.json().catch(() => ({}))
      notify.error(data.detail || t('admin.tokenStatsLoadError'))
    }
  } catch {
    notify.error(t('admin.tokenStatsNetworkError'))
  } finally {
    isLoadingTokens.value = false
  }
}

async function renderTokenTrendChart(data: {
  data: Array<{ date: string; value: number; input?: number; output?: number }>
}) {
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
    datasets.push(
      {
        label: t('admin.inputTokens'),
        data: rawData.map((item) => item.input ?? 0),
        borderColor: '#10b981',
        backgroundColor: 'rgba(16, 185, 129, 0.1)',
        borderWidth: 2,
        fill: false,
        tension: 0.4,
        pointRadius: 2,
        pointHoverRadius: 4,
      },
      {
        label: t('admin.outputTokens'),
        data: rawData.map((item) => item.output ?? 0),
        borderColor: '#f59e0b',
        backgroundColor: 'rgba(245, 158, 11, 0.1)',
        borderWidth: 2,
        fill: false,
        tension: 0.4,
        pointRadius: 2,
        pointHoverRadius: 4,
      }
    )
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
          min: Math.max(0, minVal - padding),
          max: maxVal + padding,
          ticks: { callback: (val: string | number) => formatChartLabel(Number(val)) },
        },
        x: { ticks: { maxRotation: 45, minRotation: 45 } },
      },
    },
  }
  const Chart = await loadChartJs()
  trendChartInstance = new Chart(trendChartRef.value, config)
}

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
  const params = new URLSearchParams({ metric: 'tokens', days: String(daysMap[period]) })
  if (service) params.set('service', service)

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
    await renderTokenTrendChart(data)

    const fmt = (p: { input_tokens?: number; output_tokens?: number }) =>
      `${formatNumber(p?.input_tokens ?? 0)}+${formatNumber(p?.output_tokens ?? 0)}`

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

function closeTokenTrendModal() {
  trendModalVisible.value = false
  trendChartInstance?.destroy()
  trendChartInstance = null
}

onMounted(() => {
  loadTokenStats()
})

onBeforeUnmount(() => {
  trendChartInstance?.destroy()
  trendChartInstance = null
})
</script>

<template>
  <div>
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

    <div v-else-if="tokenStats">
      <div class="mb-6">
        <h2 class="text-lg font-semibold text-gray-800 dark:text-white mb-2">
          {{ t('admin.tokenUsageByService') }}
        </h2>
        <p class="text-sm text-gray-500">{{ t('admin.tokenUsageCompare') }}</p>
      </div>

      <AdminTokenUsageByServicePanel
        :stats="tokenStats"
        clickable
        @service-click="showTokenTrendChart($event)"
      />

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-2 items-stretch">
        <AdminSwissServiceCard
          theme="platform"
          class="overall-token-row lg:col-span-2 h-full min-h-0"
          clickable
          @click="showTokenTrendChart(null)"
        >
          <template #header>
            <div
              class="flex items-center justify-between w-full"
              @click.stop
            >
              <span class="swiss-stat-card__service-title">{{ t('admin.overallTokenSummary') }}</span>
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
          <div class="swiss-stat-card__stat-item-grid">
            <div
              v-for="period in overallPeriods"
              :key="period.key"
              class="swiss-stat-card__stat-item text-center"
            >
              <p class="swiss-stat-card__stat-item-k">{{ period.label() }}</p>
              <p class="swiss-stat-card__stat-item-v">
                {{ formatNumber(tokenStats[period.statsKey]?.total_tokens || 0) }}
              </p>
              <p class="swiss-stat-card__stat-item-sub">
                {{ t('admin.inShort') }}:
                {{ formatNumber(tokenStats[period.statsKey]?.input_tokens || 0) }}
                · {{ t('admin.outShort') }}:
                {{ formatNumber(tokenStats[period.statsKey]?.output_tokens || 0) }}
              </p>
            </div>
          </div>
        </AdminSwissServiceCard>

        <AdminSwissServiceCard
          theme="integration"
          class="h-full min-h-0"
          clickable
          focusable
          :aria-label="`${t('admin.dingtalkGenerationCard')}. ${t('admin.dingtalkCardClickToEditApiKeys')}`"
          @click="openDingtalkApiKeysDialog"
          @keydown="onDingtalkCardKeydown"
        >
          <template #header>
            <div class="flex min-h-0 items-center gap-2">
              <div class="swiss-stat-card__icon">
                <el-icon :size="16">
                  <Key />
                </el-icon>
              </div>
              <p class="swiss-stat-card__service-title">
                {{ t('admin.dingtalkGenerationCard') }}
              </p>
            </div>
          </template>
          <div class="dingtalk-generation-body">
            <p class="text-xl font-semibold tabular-nums sm:text-2xl" style="color: var(--stat-accent)">
              <template v-if="dingtalkKeyUsesTotal !== null">
                {{ t('admin.dingtalkCardTotalUses', { count: dingtalkKeyUsesTotal }) }}
              </template>
              <template v-else>—</template>
            </p>
            <p class="text-center text-xs leading-snug text-[var(--swiss-muted)]">
              {{ t('admin.dingtalkCardClickToEditApiKeys') }}
            </p>
          </div>
        </AdminSwissServiceCard>
      </div>
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

    <AdminDingtalkGenerationApiKeysDialog v-model="dingtalkApiKeysDialogVisible" />

    <!-- Trend chart modal -->
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
            <AdminSwissPeriodCard
              v-for="(cardPeriod, key) in {
                today: 'today',
                week: 'week',
                month: 'month',
                total: 'total',
              } as const"
              :key="key"
              :label="
                key === 'today'
                  ? t('admin.today')
                  : key === 'week'
                    ? t('admin.pastWeek')
                    : key === 'month'
                      ? t('admin.pastMonth')
                      : t('admin.allTime')
              "
              :value="periodCards[key]"
              :active="trendContext.period === key"
              theme="storage"
              @click="switchTokenTrendPeriod(key as 'today' | 'week' | 'month' | 'total')"
            />
          </div>
        </div>
      </template>
      <template #footer>
        <el-button @click="closeTokenTrendModal">{{ t('common.close') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped src="@/styles/admin-token-by-service.css"></style>
