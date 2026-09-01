<script setup lang="ts">
/**
 * Compact Swiss card: title, primary value, metric chips, remark, optional chart.
 */
import { computed, ref } from 'vue'

import type { AdminSwissStatTheme } from '@/constants/adminSwissStatTheme'
import { useSwissStatCardClasses } from '@/composables/admin/useSwissStatCardClasses'
import { useSchoolActivityChart } from '@/composables/school/useSchoolActivityChart'

export interface ModuleStatChip {
  label: string
  value: string
}

const props = withDefaults(
  defineProps<{
    title: string
    value: string | number
    valueLabel?: string
    timestamp: string
    chips?: ModuleStatChip[]
    remark?: string
    theme?: AdminSwissStatTheme
    empty?: boolean
    emptyText?: string
    showChart?: boolean
    labels?: string[]
    values?: number[]
  }>(),
  {
    valueLabel: '',
    chips: () => [],
    remark: '',
    theme: 'members',
    empty: false,
    emptyText: '',
    showChart: false,
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
  computed(() => ({ stripe: 'left' as const, compact: true }))
)

const chartSpec = computed(() => {
  if (props.empty || !props.showChart) {
    return null
  }
  return {
    kind: 'bar' as const,
    labels: props.labels,
    values: props.values,
  }
})

useSchoolActivityChart(canvasRef, chartSpec)
</script>

<template>
  <article
    :class="cardClasses"
    data-testid="school-feature-usage-card"
  >
    <div class="swiss-stat-card__header">
      <h3 class="swiss-stat-card__title">
        {{ title }}
      </h3>
    </div>
    <p
      v-if="valueLabel"
      class="module-stat-card__value-label"
    >
      {{ valueLabel }}
    </p>
    <p class="swiss-stat-card__value">
      {{ displayValue }}
    </p>
    <ul
      v-if="chips.length"
      class="module-stat-card__chips"
    >
      <li
        v-for="chip in chips"
        :key="chip.label"
        class="module-stat-card__chip"
      >
        <span class="module-stat-card__chip-label">{{ chip.label }}</span>
        <span class="module-stat-card__chip-value">{{ chip.value }}</span>
      </li>
    </ul>
    <p
      v-if="remark"
      class="swiss-stat-card__sub"
    >
      {{ remark }}
    </p>
    <div
      v-if="empty"
      class="module-stat-card__empty"
    >
      {{ emptyText }}
    </div>
    <div
      v-else-if="showChart"
      class="module-stat-card__chart"
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
.module-stat-card__value-label {
  margin: 0 0 0.2rem;
  font-size: 0.6875rem;
  color: var(--swiss-muted, #78716c);
}

.module-stat-card__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 0.75rem;
  margin: 0;
  padding: 0;
  list-style: none;
}

.module-stat-card__chip {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.module-stat-card__chip-label {
  font-size: 0.6875rem;
  color: var(--swiss-muted, #78716c);
}

.module-stat-card__chip-value {
  font-size: 0.875rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: var(--swiss-ink, #1c1917);
}

.module-stat-card__chart {
  position: relative;
  width: 100%;
  min-height: 112px;
  height: 112px;
}

.module-stat-card__empty {
  min-height: 72px;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  font-size: 0.8125rem;
  line-height: 1.45;
  color: var(--swiss-muted, #78716c);
}
</style>
