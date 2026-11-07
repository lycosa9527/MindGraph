/**
 * Lazy-load Chart.js with only line-chart controllers used in admin/school dashboards.
 */
import type { ChartConfiguration, Chart as ChartType, TooltipItem } from 'chart.js'

export type { ChartConfiguration, TooltipItem }

/**
 * Chart.js draws from an animation frame. If the canvas is gone, that frame
 * calls save() on a null context. Dashboard charts draw once.
 */
export const DASHBOARD_CHART_ANIMATION = false

interface ReleasableChart {
  readonly canvas: HTMLCanvasElement | null
  stop: () => void
  destroy: () => void
}

export function releaseChartInstance(chart: ReleasableChart | null | undefined): void {
  if (!chart?.canvas) {
    return
  }
  chart.stop()
  chart.destroy()
}

let chartReady: Promise<typeof ChartType> | null = null

export function loadChartJs(): Promise<typeof ChartType> {
  if (!chartReady) {
    chartReady = import('chart.js').then((mod) => {
      const {
        Chart,
        LineController,
        LineElement,
        BarController,
        BarElement,
        PointElement,
        LinearScale,
        CategoryScale,
        Title,
        Tooltip,
        Legend,
        Filler,
      } = mod
      Chart.register(
        LineController,
        LineElement,
        BarController,
        BarElement,
        PointElement,
        LinearScale,
        CategoryScale,
        Title,
        Tooltip,
        Legend,
        Filler
      )
      return Chart
    })
  }
  return chartReady
}
