/**
 * Org-scoped token trend modal — chart + synced period summary cards.
 */
import { nextTick, onBeforeUnmount, ref } from 'vue'

import type { Chart as ChartInstance } from 'chart.js'

import {
  ADMIN_TREND_CHART_MOUNT_DELAY_MS,
  ADMIN_TREND_DAYS_MAP,
  formatAdminTrendNumber,
  renderAdminTrendLineChart,
} from '@/composables/admin/useAdminTrendChart'
import { queryErrorMessage } from '@/composables/admin/useQueryErrorNotification'
import { useScopedAbort } from '@/composables/core/useScopedAbort'
import { useLanguage, useNotifications } from '@/composables'
import {
  fetchAdminSchoolTokenStats,
  fetchAdminSchoolTrends,
  fetchAdminStatsTrendsOrganization,
  fetchAdminTokenStats,
  type AdminPlatformTokenStats,
} from '@/composables/queries'
import { intlLocaleForUiCode } from '@/i18n/locales'
import { useUIStore } from '@/stores/ui'

export type TokenTrendPeriod = 'today' | 'week' | 'month' | 'total'
export type TokenTrendService = 'mindgraph' | 'mindmate' | null

interface TokenPeriodStats {
  input_tokens?: number
  output_tokens?: number
  total_tokens?: number
}

interface PeriodCardValues {
  today: string
  week: string
  month: string
  total: string
}

interface ShowTrendOptions {
  orgId?: number
  orgName: string
  period?: TokenTrendPeriod
  service?: TokenTrendService
  useSchoolStatsEndpoint?: boolean
}

function formatPeriodStats(p: TokenPeriodStats | undefined): string {
  const input = p?.input_tokens ?? 0
  const output = p?.output_tokens ?? 0
  return `${formatAdminTrendNumber(input)}+${formatAdminTrendNumber(output)}`
}

function periodCardsFromTokenStats(
  tokenData: AdminPlatformTokenStats,
  service: TokenTrendService
): PeriodCardValues {
  if (service === 'mindgraph' && tokenData.by_service?.mindgraph) {
    const stats = tokenData.by_service.mindgraph
    return {
      today: formatPeriodStats(stats.today),
      week: formatPeriodStats(stats.week),
      month: formatPeriodStats(stats.month),
      total: formatPeriodStats(stats.total),
    }
  }
  if (service === 'mindmate' && tokenData.by_service?.mindmate) {
    const stats = tokenData.by_service.mindmate
    return {
      today: formatPeriodStats(stats.today),
      week: formatPeriodStats(stats.week),
      month: formatPeriodStats(stats.month),
      total: formatPeriodStats(stats.total),
    }
  }
  return {
    today: formatPeriodStats(tokenData.today),
    week: formatPeriodStats(tokenData.past_week),
    month: formatPeriodStats(tokenData.past_month),
    total: formatPeriodStats(tokenData.total),
  }
}

export function useOrgTokenTrendModal() {
  const { t } = useLanguage()
  const notify = useNotifications()
  const uiStore = useUIStore()
  const { beginRequest: beginTrendRequest, abort: abortTrendRequests } = useScopedAbort()

  const trendModalVisible = ref(false)
  const trendChartTitle = ref('')
  const trendChartLoading = ref(false)
  const trendChartHasData = ref(true)
  const trendChartRef = ref<HTMLCanvasElement | null>(null)
  const periodCards = ref<PeriodCardValues>({ today: '-', week: '-', month: '-', total: '-' })
  const trendPeriod = ref<TokenTrendPeriod>('week')
  const trendService = ref<TokenTrendService>(null)
  const trendOrgId = ref<number | null>(null)
  const trendOrgName = ref('')
  const useSchoolEndpoint = ref(false)

  let trendChartInstance: ChartInstance<'line'> | null = null

  async function fetchTrendChart(
    orgId: number | undefined,
    orgName: string,
    period: TokenTrendPeriod,
    service: TokenTrendService,
    schoolEndpoint: boolean,
    signal: AbortSignal
  ) {
    const days = ADMIN_TREND_DAYS_MAP[period]
    const hourly = period === 'today'
    const serviceParam = service ?? undefined

    if (schoolEndpoint) {
      if (orgId == null) {
        throw new Error('organization_id required for school trends')
      }
      return fetchAdminSchoolTrends(
        { organization_id: orgId, days, hourly, service: serviceParam },
        signal
      )
    }
    return fetchAdminStatsTrendsOrganization(
      {
        organization_id: orgId,
        organization_name: orgId == null ? orgName : undefined,
        days,
        hourly,
        service: serviceParam,
      },
      signal
    )
  }

  async function fetchTokenStats(orgId: number, schoolEndpoint: boolean, signal: AbortSignal) {
    if (schoolEndpoint) {
      return fetchAdminSchoolTokenStats(orgId, signal)
    }
    return fetchAdminTokenStats(orgId, signal)
  }

  function trendTitle(orgName: string, service: TokenTrendService): string {
    if (service === 'mindgraph') {
      return `${t('admin.serviceMindGraph')} - ${t('admin.trendOrgTokens')}: ${orgName}`
    }
    if (service === 'mindmate') {
      return `${t('admin.serviceMindMate')} - ${t('admin.trendOrgTokens')}: ${orgName}`
    }
    return `${t('admin.trendOrgTokens')}: ${orgName}`
  }

  async function renderTrendChart(data: {
    data: Array<{ date: string; value: number; input?: number; output?: number }>
  }): Promise<void> {
    if (!trendChartRef.value) {
      return
    }
    const rawData = data?.data ?? []
    const intlLocale = intlLocaleForUiCode(uiStore.language)
    const result = await renderAdminTrendLineChart({
      canvas: trendChartRef.value,
      title: trendChartTitle.value,
      rawData,
      intlLocale,
      inputLabel: t('admin.inputTokens'),
      outputLabel: t('admin.outputTokens'),
      existingInstance: trendChartInstance,
    })
    trendChartInstance = result.instance
    trendChartHasData.value = result.hasData
  }

  async function showTrendChart(options: ShowTrendOptions): Promise<void> {
    const period = options.period ?? 'week'
    const service = options.service ?? null

    trendOrgId.value = options.orgId ?? null
    trendOrgName.value = options.orgName
    trendPeriod.value = period
    trendService.value = service
    useSchoolEndpoint.value = options.useSchoolStatsEndpoint === true
    trendChartTitle.value = trendTitle(options.orgName, service)
    trendModalVisible.value = true
    trendChartLoading.value = true

    const signal = beginTrendRequest()
    try {
      const chartData = await fetchTrendChart(
        options.orgId,
        options.orgName,
        period,
        service,
        useSchoolEndpoint.value,
        signal
      )
      const resolvedOrgId =
        options.orgId ??
        (chartData as { organization_id?: number }).organization_id ??
        null
      if (resolvedOrgId != null) {
        trendOrgId.value = resolvedOrgId
      }
      const statsOrgId = trendOrgId.value
      const tokenDataPromise =
        statsOrgId != null
          ? fetchTokenStats(statsOrgId, useSchoolEndpoint.value, signal)
          : Promise.resolve(null)
      trendChartLoading.value = false
      await nextTick()
      await new Promise((resolve) => setTimeout(resolve, ADMIN_TREND_CHART_MOUNT_DELAY_MS))
      await renderTrendChart({ data: chartData.data ?? [] })
      if (tokenDataPromise) {
        const tokenData = await tokenDataPromise
        if (tokenData) {
          periodCards.value = periodCardsFromTokenStats(tokenData, service)
        }
      }
    } catch (err) {
      const message = queryErrorMessage(err, t('admin.dashboardLoadError'))
      if (message) {
        notify.error(message)
      }
      trendChartLoading.value = false
    }
  }

  function switchTrendPeriod(period: TokenTrendPeriod): void {
    void showTrendChart({
      orgId: trendOrgId.value ?? undefined,
      orgName: trendOrgName.value,
      period,
      service: trendService.value,
      useSchoolStatsEndpoint: useSchoolEndpoint.value,
    })
  }

  function closeTrendModal(): void {
    abortTrendRequests()
    trendModalVisible.value = false
    trendChartInstance?.destroy()
    trendChartInstance = null
  }

  onBeforeUnmount(() => {
    trendChartInstance?.destroy()
    trendChartInstance = null
  })

  return {
    trendModalVisible,
    trendChartTitle,
    trendChartLoading,
    trendChartHasData,
    trendChartRef,
    periodCards,
    trendPeriod,
    showTrendChart,
    switchTrendPeriod,
    closeTrendModal,
  }
}
