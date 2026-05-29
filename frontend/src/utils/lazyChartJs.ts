/**
 * Lazy-load Chart.js with only line-chart controllers used in admin/school dashboards.
 */
import type { Chart as ChartType, ChartConfiguration, TooltipItem } from 'chart.js'

export type { ChartConfiguration, TooltipItem }

let chartReady: Promise<typeof ChartType> | null = null

export function loadChartJs(): Promise<typeof ChartType> {
  if (!chartReady) {
    chartReady = import('chart.js').then((mod) => {
      const {
        Chart,
        LineController,
        LineElement,
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
