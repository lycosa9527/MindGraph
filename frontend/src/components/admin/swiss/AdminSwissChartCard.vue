<script setup lang="ts">
/**
 * Swiss diagram card: headline, Chart.js canvas or empty copy, required timestamp.
 */
import { type Component, computed, ref } from 'vue'

import I18nText from '@/components/common/I18nText.vue'
import { useSwissStatCardClasses } from '@/composables/admin/useSwissStatCardClasses'
import {
  type SchoolActivityChartKind,
  useSchoolActivityChart,
} from '@/composables/school/useSchoolActivityChart'
import type { AdminSwissStatTheme } from '@/constants/adminSwissStatTheme'

const props = withDefaults(
  defineProps<{
    title?: string
    titleKey?: string
    value: string | number
    timestamp: string
    theme?: AdminSwissStatTheme
    icon?: Component
    empty?: boolean
    emptyText?: string
    emptyTextKey?: string
    chartKind?: SchoolActivityChartKind
    labels?: string[]
    values?: number[]
  }>(),
  {
    title: '',
    titleKey: '',
    theme: 'members',
    icon: undefined,
    empty: false,
    emptyText: '',
    emptyTextKey: '',
    chartKind: 'bar',
    labels: () => [],
    values: () => [],
  }
)

const canvasRef = ref<HTMLCanvasElement | null>(null)
const displayValue = computed(() => {
  if (typeof props.value === 'number') {
    return props.value.toLocaleString()
  }
  return props.value
})

const cardClasses = useSwissStatCardClasses(
  computed(() => props.theme),
  computed(() => ({ stripe: 'left' as const }))
)

const chartSpec = computed(() => {
  if (props.empty) {
    return null
  }
  return {
    kind: props.chartKind,
    labels: props.labels,
    values: props.values,
  }
})

useSchoolActivityChart(canvasRef, chartSpec)
</script>

<template>
  <article
    :class="cardClasses"
    data-testid="school-activity-chart-card"
  >
    <div class="swiss-stat-card__header">
      <div
        v-if="icon"
        class="swiss-stat-card__icon"
      >
        <el-icon :size="22">
          <component :is="icon" />
        </el-icon>
      </div>
      <h3 class="swiss-stat-card__title">
        <I18nText
          v-if="titleKey"
          :k="titleKey"
        />
        <template v-else>{{ title }}</template>
      </h3>
    </div>
    <p class="swiss-stat-card__value">
      {{ displayValue }}
    </p>
    <div
      v-if="empty"
      class="school-activity-chart-card__empty"
    >
      <I18nText
        v-if="emptyTextKey"
        :k="emptyTextKey"
      />
      <template v-else>{{ emptyText }}</template>
    </div>
    <div
      v-else
      class="school-activity-chart-card__chart"
    >
      <canvas ref="canvasRef" />
    </div>
    <p
      class="swiss-stat-card__hint"
      data-testid="school-activity-card-timestamp"
    >
      {{ timestamp }}
    </p>
  </article>
</template>

<style scoped>
.school-activity-chart-card__chart {
  position: relative;
  width: 100%;
  min-height: 168px;
  height: 168px;
}

.school-activity-chart-card__empty {
  min-height: 168px;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  font-size: 0.8125rem;
  line-height: 1.45;
  color: var(--swiss-muted, #78716c);
  padding: 0.5rem;
}
</style>
