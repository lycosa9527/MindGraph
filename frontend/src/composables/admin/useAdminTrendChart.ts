/**
 * Shared Chart.js helpers for admin token trend modals.
 */
import type { Chart as ChartInstance } from 'chart.js'

import { type ChartConfiguration, type TooltipItem, loadChartJs } from '@/utils/lazyChartJs'

export const ADMIN_TREND_DAYS_MAP = {
  today: 1,
  week: 7,
  month: 30,
  total: 0,
} as const

export type AdminTrendPeriod = keyof typeof ADMIN_TREND_DAYS_MAP

export interface AdminTrendChartPoint {
  date: string
  value: number
  input?: number
  output?: number
}

export function formatAdminTrendNumber(num: number): string {
  if (num >= 1000000) {
    return `${(num / 1000000).toFixed(1)}M`
  }
  if (num >= 1000) {
    return `${(num / 1000).toFixed(1)}K`
  }
  return num.toLocaleString()
}

export function formatAdminTrendChartLabel(value: number): string {
  return formatAdminTrendNumber(value)
}

export function buildAdminTrendChartLabels(
  rawData: AdminTrendChartPoint[],
  intlLocale: string
): string[] {
  return rawData.map((item) => {
    const dateStr = item.date.includes(' ') ? item.date.replace(' ', 'T') : `${item.date}T00:00:00`
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
}

export async function renderAdminTrendLineChart(options: {
  canvas: HTMLCanvasElement
  title: string
  rawData: AdminTrendChartPoint[]
  intlLocale: string
  inputLabel: string
  outputLabel: string
  existingInstance: ChartInstance<'line'> | null
}): Promise<{ instance: ChartInstance<'line'> | null; hasData: boolean }> {
  const { canvas, title, rawData, intlLocale, inputLabel, outputLabel, existingInstance } = options
  if (rawData.length === 0) {
    existingInstance?.destroy()
    return { instance: null, hasData: false }
  }

  existingInstance?.destroy()

  const labels = buildAdminTrendChartLabels(rawData, intlLocale)
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
      label: title,
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
      label: inputLabel,
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
      label: outputLabel,
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
              `${ctx.dataset.label}: ${formatAdminTrendChartLabel(Number(ctx.raw))}`,
          },
        },
      },
      scales: {
        y: {
          beginAtZero: false,
          min: yMin,
          max: yMax,
          ticks: {
            callback: (val: string | number) => formatAdminTrendChartLabel(Number(val)),
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
  return { instance: new Chart(canvas, config), hasData: true }
}

export const ADMIN_TREND_CHART_MOUNT_DELAY_MS = 50
