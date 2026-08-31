/**
 * Chart.js lifecycle for school-activity diagram cards.
 */
import { onBeforeUnmount, ref, watch, type Ref } from 'vue'

import type { Chart as ChartInstance } from 'chart.js'

import { loadChartJs } from '@/utils/lazyChartJs'

export type SchoolActivityChartKind = 'line' | 'bar'

export interface SchoolActivityChartSpec {
  kind: SchoolActivityChartKind
  labels: string[]
  values: number[]
}

export function useSchoolActivityChart(
  canvasRef: Ref<HTMLCanvasElement | null>,
  spec: Ref<SchoolActivityChartSpec | null>
): void {
  const instance = ref<ChartInstance | null>(null)
  let renderToken = 0

  async function render(): Promise<void> {
    renderToken += 1
    const token = renderToken
    instance.value?.destroy()
    instance.value = null
    const canvas = canvasRef.value
    const chartSpec = spec.value
    if (!canvas || !chartSpec) {
      return
    }
    const Chart = await loadChartJs()
    if (token !== renderToken || canvasRef.value !== canvas) {
      return
    }
    instance.value = new Chart(canvas, {
      type: chartSpec.kind,
      data: {
        labels: chartSpec.labels,
        datasets: [
          {
            data: chartSpec.values,
            borderColor: '#667eea',
            backgroundColor:
              chartSpec.kind === 'line' ? 'rgba(102, 126, 234, 0.12)' : 'rgba(102, 126, 234, 0.55)',
            fill: chartSpec.kind === 'line',
            tension: 0.25,
            pointRadius: chartSpec.kind === 'line' && chartSpec.values.length > 40 ? 0 : 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: { enabled: true },
        },
        scales: {
          x: {
            ticks: { color: '#78716c', maxRotation: 0, autoSkip: true },
            grid: { color: 'rgba(168, 162, 158, 0.25)' },
          },
          y: {
            beginAtZero: true,
            ticks: { color: '#78716c', precision: 0 },
            grid: { color: 'rgba(168, 162, 158, 0.25)' },
          },
        },
      },
    })
  }

  watch([canvasRef, spec], () => {
    void render()
  }, { immediate: true, deep: true })

  onBeforeUnmount(() => {
    instance.value?.destroy()
    instance.value = null
  })
}
