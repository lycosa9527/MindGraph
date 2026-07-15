/**
 * Public China-map dashboard: stats, map data, activity history, SSE.
 */
import { nextTick, onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import { useRouter } from 'vue-router'

import { MapChart, ScatterChart } from 'echarts/charts'
import { GeoComponent, TooltipComponent, VisualMapComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import type { EChartsType } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'

import { useLanguage, useNotifications } from '@/composables'
import { useUIStore } from '@/stores/ui'

echarts.use([
  MapChart,
  ScatterChart,
  GeoComponent,
  TooltipComponent,
  VisualMapComponent,
  CanvasRenderer,
])

export interface DashboardStats {
  connected_users: number
  registered_users: number
  tokens_used_today: number
  total_tokens_used: number
}

export interface DashboardActivity {
  type?: string
  timestamp: string
  user: string
  action?: string
  diagram_type?: string
}

interface MapDatum {
  name: string
  value: number
}

interface FlagDatum {
  name: string
  value: [number, number] | number[]
}

const GEO_JSON_URL = '/data/china-geo.json'
const MAX_ACTIVITIES = 100
const SERIES_USERS = 'users'
const SERIES_SESSIONS = 'sessions'

let chinaMapRegistered = false

export function formatCompactNumber(num: number): string {
  if (num >= 1_000_000) {
    return `${(num / 1_000_000).toFixed(1)}M`
  }
  if (num >= 1_000) {
    return `${(num / 1_000).toFixed(1)}K`
  }
  return num.toLocaleString()
}

async function ensureChinaMapRegistered(): Promise<void> {
  if (chinaMapRegistered) {
    return
  }
  const response = await fetch(GEO_JSON_URL)
  if (!response.ok) {
    throw new Error(`Failed to load China geoJSON (${response.status})`)
  }
  const geoJson = await response.json()
  echarts.registerMap('china', geoJson)
  chinaMapRegistered = true
}

function redirectOnAuthFailure(
  router: ReturnType<typeof useRouter>,
  status: number
): void {
  if (status === 401) {
    const fullPath = router.currentRoute.value.fullPath
    void router.replace(`/auth?redirect=${encodeURIComponent(fullPath)}`)
    return
  }
  if (status === 403) {
    void router.replace({ name: 'MindMate' })
  }
}

export function usePublicDashboard(mapEl: { value: HTMLElement | null }) {
  const router = useRouter()
  const { t, currentLanguage } = useLanguage()
  const uiStore = useUIStore()
  const notify = useNotifications()

  const isLoading = ref(true)
  const stats = ref<DashboardStats>({
    connected_users: 0,
    registered_users: 0,
    tokens_used_today: 0,
    total_tokens_used: 0,
  })
  const activities = ref<DashboardActivity[]>([])
  const isRefreshing = ref(false)

  const chart = shallowRef<EChartsType | null>(null)
  let eventSource: EventSource | null = null
  let pulseFrame: number | null = null
  let fallbackTimer: ReturnType<typeof setInterval> | null = null
  let sseFailedAt: number | null = null
  let latestActivityTs = 0
  let mapPollTimer: ReturnType<typeof setInterval> | null = null
  let resizeObserver: ResizeObserver | null = null

  function diagramTypeLabel(diagramType: string | undefined): string {
    const raw = (diagramType || 'unknown').trim()
    if (!raw || raw === 'unknown') {
      return t('publicDashboard.unknownDiagram')
    }
    const key = `sidebar.diagramType.${raw}`
    const translated = t(key)
    return translated === key ? raw : translated
  }

  function activityText(diagramType: string | undefined): string {
    const label = diagramTypeLabel(diagramType)
    const lang = currentLanguage.value || uiStore.language
    if (lang === 'zh' || lang === 'zh-tw' || lang.startsWith('zh')) {
      return `${t('publicDashboard.hasGenerated')}${label}`
    }
    return `${t('publicDashboard.hasGenerated')} ${label}`
  }

  function formatActivityTime(timestamp: string): string {
    try {
      return new Date(timestamp).toLocaleTimeString()
    } catch {
      return timestamp
    }
  }

  async function fetchJson<T>(url: string): Promise<T | null> {
    const response = await fetch(url, { credentials: 'include' })
    if (response.status === 401 || response.status === 403) {
      redirectOnAuthFailure(router, response.status)
      return null
    }
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }
    return (await response.json()) as T
  }

  function applyStats(partial: Partial<DashboardStats>): void {
    stats.value = {
      connected_users: partial.connected_users ?? stats.value.connected_users,
      registered_users: partial.registered_users ?? stats.value.registered_users,
      tokens_used_today: partial.tokens_used_today ?? stats.value.tokens_used_today,
      total_tokens_used: partial.total_tokens_used ?? stats.value.total_tokens_used,
    }
  }

  function prependActivity(item: DashboardActivity): void {
    const ts = new Date(item.timestamp).getTime()
    if (!Number.isNaN(ts) && ts > latestActivityTs) {
      latestActivityTs = ts
    }
    activities.value = [item, ...activities.value].slice(0, MAX_ACTIVITIES)
  }

  function buildBaseOption() {
    return {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        backgroundColor: 'rgba(15, 23, 42, 0.92)',
        borderColor: '#334155',
        textStyle: { color: '#e2e8f0' },
      },
      visualMap: {
        show: true,
        min: 0,
        max: 50,
        left: 'left',
        top: 'bottom',
        text: [t('publicDashboard.visualHigh'), t('publicDashboard.visualLow')],
        textStyle: { color: '#e2e8f0' },
        inRange: {
          color: ['#0f172a', '#1e293b', '#1e40af', '#3b82f6', '#60a5fa', '#a78bfa', '#f472b6'],
        },
        calculable: true,
        realtime: true,
        itemWidth: 15,
        itemHeight: 150,
        borderWidth: 2,
        borderColor: '#334155',
        backgroundColor: 'rgba(30, 41, 59, 0.8)',
        textGap: 10,
      },
      geo: {
        map: 'china',
        roam: true,
        zoom: 1.2,
        center: [105, 36],
        itemStyle: {
          areaColor: '#0f172a',
          borderColor: '#334155',
          borderWidth: 1.5,
          shadowColor: 'rgba(0, 0, 0, 0.5)',
          shadowBlur: 10,
        },
        emphasis: {
          itemStyle: {
            areaColor: '#1e40af',
            borderColor: '#60a5fa',
            borderWidth: 3,
            shadowColor: 'rgba(96, 165, 250, 0.8)',
            shadowBlur: 30,
          },
          label: {
            show: true,
            color: '#e2e8f0',
          },
        },
      },
      series: [
        {
          name: SERIES_USERS,
          type: 'map',
          map: 'china',
          geoIndex: 0,
          data: [] as MapDatum[],
          itemStyle: {
            borderColor: '#334155',
            borderWidth: 1.5,
          },
          emphasis: {
            itemStyle: {
              borderColor: '#60a5fa',
              borderWidth: 3,
            },
            label: {
              show: true,
              color: '#e2e8f0',
              fontSize: 14,
              fontWeight: 'bold',
            },
          },
        },
        {
          name: SERIES_SESSIONS,
          type: 'scatter',
          coordinateSystem: 'geo',
          data: [] as Array<{ name: string; value: number[] }>,
          symbol: 'circle',
          symbolSize: 10,
          itemStyle: {
            color: '#60a5fa',
            shadowBlur: 20,
            shadowColor: 'rgba(96, 165, 250, 0.8)',
            borderColor: '#ffffff',
            borderWidth: 2,
            opacity: 0.95,
          },
          label: { show: false },
          emphasis: {
            label: {
              show: true,
              formatter: (params: { name?: string }) => params.name || '',
              position: 'bottom',
              color: '#e2e8f0',
              fontSize: 10,
              fontWeight: 'bold',
              backgroundColor: 'rgba(96, 165, 250, 0.9)',
              padding: [2, 6],
              borderRadius: 4,
            },
          },
          animation: false,
        },
      ],
    }
  }

  function startPulse(): void {
    stopPulse()
    const tick = () => {
      const instance = chart.value
      if (!instance || instance.isDisposed()) {
        pulseFrame = null
        return
      }
      const time = Date.now() / 1000
      const pulse = Math.sin(time * 2) * 3 + 10
      const glow = Math.sin(time * 2) * 8 + 20
      const option = instance.getOption() as { series?: Array<{ name?: string }> }
      const series = option.series
      if (Array.isArray(series)) {
        for (let i = 0; i < series.length; i += 1) {
          if (series[i]?.name === SERIES_SESSIONS) {
            const update: Array<Record<string, unknown> | undefined> = []
            update[i] = {
              symbolSize: pulse,
              itemStyle: { shadowBlur: glow },
            }
            instance.setOption({ series: update }, { notMerge: false, lazyUpdate: true })
            break
          }
        }
      }
      pulseFrame = requestAnimationFrame(tick)
    }
    pulseFrame = requestAnimationFrame(tick)
  }

  function stopPulse(): void {
    if (pulseFrame !== null) {
      cancelAnimationFrame(pulseFrame)
      pulseFrame = null
    }
  }

  async function initMap(): Promise<void> {
    await ensureChinaMapRegistered()
    await nextTick()
    const el = mapEl.value
    if (!el) {
      return
    }
    if (chart.value) {
      chart.value.dispose()
    }
    chart.value = echarts.init(el, 'dark')
    chart.value.setOption(buildBaseOption())
    startPulse()
    resizeObserver?.disconnect()
    resizeObserver = new ResizeObserver(() => {
      chart.value?.resize()
    })
    resizeObserver.observe(el)
  }

  async function loadStats(): Promise<void> {
    const data = await fetchJson<DashboardStats>('/api/public/stats')
    if (!data) {
      return
    }
    applyStats(data)
  }

  async function loadMapData(): Promise<void> {
    const data = await fetchJson<{
      map_data?: MapDatum[]
      flag_data?: FlagDatum[]
    }>('/api/public/map-data')
    if (!data || !chart.value) {
      return
    }
    const mapData = data.map_data || []
    const mapMax = mapData.length > 0 ? Math.max(...mapData.map((item) => item.value), 1) : 1
    const maxValue = Math.max(mapMax, 50)
    chart.value.setOption(
      {
        visualMap: { max: maxValue },
        series: [
          {
            name: SERIES_USERS,
            data: mapData,
          },
          {
            name: SERIES_SESSIONS,
            data: (data.flag_data || []).map((flag) => ({
              name: flag.name,
              value: flag.value,
            })),
          },
        ],
      },
      { notMerge: false }
    )
  }

  async function loadActivityHistory(): Promise<void> {
    const data = await fetchJson<{ activities?: DashboardActivity[] }>(
      '/api/public/activity-history?limit=100'
    )
    if (!data) {
      return
    }
    const list = [...(data.activities || [])].reverse()
    activities.value = []
    latestActivityTs = 0
    for (const item of list) {
      prependActivity(item)
    }
  }

  async function refreshActivityPanel(): Promise<void> {
    if (isRefreshing.value) {
      return
    }
    isRefreshing.value = true
    try {
      await loadActivityHistory()
    } finally {
      isRefreshing.value = false
    }
  }

  function stopFallbackPolling(): void {
    if (fallbackTimer) {
      clearInterval(fallbackTimer)
      fallbackTimer = null
    }
  }

  function startFallbackPolling(): void {
    if (fallbackTimer) {
      return
    }
    fallbackTimer = setInterval(() => {
      void (async () => {
        const data = await fetchJson<{ activities?: DashboardActivity[] }>(
          '/api/public/activity-history?limit=100'
        )
        if (!data) {
          return
        }
        for (const activity of [...(data.activities || [])].reverse()) {
          const ts = new Date(activity.timestamp).getTime()
          if (ts > latestActivityTs) {
            prependActivity(activity)
          }
        }
      })()
    }, 10_000)
  }

  function disconnectSse(): void {
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
  }

  function connectActivityStream(): void {
    disconnectSse()
    eventSource = new EventSource('/api/public/activity-stream')

    eventSource.onopen = () => {
      sseFailedAt = null
      stopFallbackPolling()
    }

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as {
          type?: string
          stats?: Partial<DashboardStats>
          connected_users?: number
          registered_users?: number
          tokens_used_today?: number
          total_tokens_used?: number
          timestamp?: string
          user?: string
          diagram_type?: string
          action?: string
          error?: string
        }
        if (data.type === 'activity') {
          prependActivity({
            type: 'activity',
            timestamp: data.timestamp || new Date().toISOString(),
            user: data.user || 'User *',
            diagram_type: data.diagram_type,
            action: data.action,
          })
          sseFailedAt = null
          stopFallbackPolling()
        } else if (data.type === 'stats_update') {
          applyStats(data)
        } else if (data.type === 'initial' && data.stats) {
          applyStats(data.stats)
        } else if (data.type === 'error' && data.error) {
          notify.error(data.error)
        }
      } catch {
        // Ignore malformed SSE payloads
      }
    }

    eventSource.onerror = () => {
      const readyState = eventSource?.readyState ?? EventSource.CLOSED
      if (readyState !== EventSource.CLOSED) {
        return
      }
      if (!sseFailedAt) {
        sseFailedAt = Date.now()
      }
      if (Date.now() - sseFailedAt > 30_000 && !fallbackTimer) {
        startFallbackPolling()
      }
      void fetch('/api/public/stats', { credentials: 'include', method: 'HEAD' })
        .then((response) => {
          if (response.status === 401 || response.status === 403) {
            stopFallbackPolling()
            redirectOnAuthFailure(router, response.status)
            return
          }
          window.setTimeout(() => {
            if (!eventSource || eventSource.readyState === EventSource.CLOSED) {
              connectActivityStream()
            }
          }, 5000)
        })
        .catch(() => {
          window.setTimeout(() => {
            if (!eventSource || eventSource.readyState === EventSource.CLOSED) {
              connectActivityStream()
            }
          }, 5000)
        })
    }
  }

  async function bootstrap(): Promise<void> {
    isLoading.value = true
    try {
      await initMap()
      await Promise.all([loadStats(), loadMapData(), loadActivityHistory()])
      connectActivityStream()
      mapPollTimer = setInterval(() => {
        void loadMapData()
      }, 20_000)
    } catch {
      notify.error(t('publicDashboard.networkError'))
    } finally {
      isLoading.value = false
    }
  }

  function dispose(): void {
    stopPulse()
    stopFallbackPolling()
    disconnectSse()
    if (mapPollTimer) {
      clearInterval(mapPollTimer)
      mapPollTimer = null
    }
    resizeObserver?.disconnect()
    resizeObserver = null
    if (chart.value) {
      chart.value.dispose()
      chart.value = null
    }
  }

  onMounted(() => {
    void bootstrap()
  })

  onBeforeUnmount(() => {
    dispose()
  })

  return {
    isLoading,
    stats,
    activities,
    isRefreshing,
    formatCompactNumber,
    activityText,
    formatActivityTime,
    refreshActivityPanel,
  }
}
