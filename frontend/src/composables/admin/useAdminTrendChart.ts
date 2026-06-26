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

export type AdminTrendChartColorScheme = 'light' | 'dark'

interface AdminTrendChartPalette {
  primaryLine: string
  primaryFill: string
  inputLine: string
  inputFill: string
  outputLine: string
  outputFill: string
  tick: string
  grid: string
  legend: string
  tooltipBg: string
  tooltipTitle: string
  tooltipBody: string
  tooltipBorder: string
}

const ADMIN_TREND_CHART_PALETTES: Record<AdminTrendChartColorScheme, AdminTrendChartPalette> = {
  light: {
    primaryLine: '#667eea',
    primaryFill: 'rgba(102, 126, 234, 0.1)',
    inputLine: '#10b981',
    inputFill: 'rgba(16, 185, 129, 0.1)',
    outputLine: '#f59e0b',
    outputFill: 'rgba(245, 158, 11, 0.1)',
    tick: '#78716c',
    grid: 'rgba(168, 162, 158, 0.35)',
    legend: '#44403c',
    tooltipBg: 'rgba(255, 255, 255, 0.96)',
    tooltipTitle: '#1c1917',
    tooltipBody: '#44403c',
    tooltipBorder: '#e7e5e4',
  },
  dark: {
    primaryLine: '#22d3ee',
    primaryFill: 'rgba(34, 211, 238, 0.14)',
    inputLine: '#34d399',
    inputFill: 'rgba(52, 211, 153, 0.12)',
    outputLine: '#fbbf24',
    outputFill: 'rgba(251, 191, 36, 0.12)',
    tick: '#cbd5e1',
    grid: 'rgba(34, 211, 238, 0.14)',
    legend: '#e2e8f0',
    tooltipBg: 'rgba(15, 23, 42, 0.96)',
    tooltipTitle: '#f8fafc',
    tooltipBody: '#e2e8f0',
    tooltipBorder: 'rgba(34, 211, 238, 0.35)',
  },
}

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
  colorScheme?: AdminTrendChartColorScheme
}): Promise<{ instance: ChartInstance<'line'> | null; hasData: boolean }> {
  const {
    canvas,
    title,
    rawData,
    intlLocale,
    inputLabel,
    outputLabel,
    existingInstance,
    colorScheme = 'light',
  } = options
  const palette = ADMIN_TREND_CHART_PALETTES[colorScheme]
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

  const pointBorder = colorScheme === 'dark' ? '#0f172a' : '#ffffff'

  const datasets: ChartConfiguration<'line'>['data']['datasets'] = [
    {
      label: title,
      data: values,
      borderColor: palette.primaryLine,
      backgroundColor: palette.primaryFill,
      borderWidth: 2.5,
      fill: true,
      tension: 0.4,
      pointRadius: 3,
      pointHoverRadius: 6,
      pointBackgroundColor: palette.primaryLine,
      pointBorderColor: pointBorder,
      pointBorderWidth: 1.5,
    },
  ]

  if (hasInputOutput) {
    datasets.push({
      label: inputLabel,
      data: rawData.map((item) => item.input ?? 0),
      borderColor: palette.inputLine,
      backgroundColor: palette.inputFill,
      borderWidth: 2,
      fill: false,
      tension: 0.4,
      pointRadius: 2,
      pointHoverRadius: 5,
      pointBackgroundColor: palette.inputLine,
      pointBorderColor: pointBorder,
      pointBorderWidth: 1.5,
    })
    datasets.push({
      label: outputLabel,
      data: rawData.map((item) => item.output ?? 0),
      borderColor: palette.outputLine,
      backgroundColor: palette.outputFill,
      borderWidth: 2,
      fill: false,
      tension: 0.4,
      pointRadius: 2,
      pointHoverRadius: 5,
      pointBackgroundColor: palette.outputLine,
      pointBorderColor: pointBorder,
      pointBorderWidth: 1.5,
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
          labels: {
            color: palette.legend,
            font: { size: 12, weight: 600 },
            boxWidth: 14,
            boxHeight: 2,
            padding: 14,
          },
        },
        tooltip: {
          backgroundColor: palette.tooltipBg,
          titleColor: palette.tooltipTitle,
          bodyColor: palette.tooltipBody,
          borderColor: palette.tooltipBorder,
          borderWidth: 1,
          padding: 10,
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
            color: palette.tick,
            font: { size: 11 },
            callback: (val: string | number) => formatAdminTrendChartLabel(Number(val)),
          },
          grid: {
            color: palette.grid,
          },
          border: {
            color: palette.grid,
          },
        },
        x: {
          ticks: {
            color: palette.tick,
            font: { size: 11 },
            maxRotation: 45,
            minRotation: 45,
          },
          grid: {
            color: palette.grid,
          },
          border: {
            color: palette.grid,
          },
        },
      },
    },
  }

  const Chart = await loadChartJs()
  return { instance: new Chart(canvas, config), hasData: true }
}

export const ADMIN_TREND_CHART_MOUNT_DELAY_MS = 50
