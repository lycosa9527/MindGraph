<script setup lang="ts">
/**
 * Compact Swiss card: title, primary value, metric chips, remark, optional chart.
 */
import { computed, ref } from 'vue'

import I18nText from '@/components/common/I18nText.vue'
import { useSwissStatCardClasses } from '@/composables/admin/useSwissStatCardClasses'
import { useSchoolActivityChart } from '@/composables/school/useSchoolActivityChart'
import type { AdminSwissStatTheme } from '@/constants/adminSwissStatTheme'

export interface ModuleStatChip {
  label?: string
  labelKey?: string
  value: string
  valueKey?: string
  valueParams?: Record<string, unknown>
}

const props = withDefaults(
  defineProps<{
    title?: string
    titleKey?: string
    value: string | number
    valueLabel?: string
    valueLabelKey?: string
    timestamp: string
    chips?: ModuleStatChip[]
    remark?: string
    remarkKey?: string
    theme?: AdminSwissStatTheme
    empty?: boolean
    emptyText?: string
    emptyTextKey?: string
    showChart?: boolean
    labels?: string[]
    values?: number[]
  }>(),
  {
    title: '',
    titleKey: '',
    valueLabel: '',
    valueLabelKey: '',
    chips: () => [],
    remark: '',
    remarkKey: '',
    theme: 'members',
    empty: false,
    emptyText: '',
    emptyTextKey: '',
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
        <I18nText
          v-if="titleKey"
          :k="titleKey"
        />
        <template v-else>{{ title }}</template>
      </h3>
    </div>
    <p
      v-if="valueLabelKey || valueLabel"
      class="module-stat-card__value-label"
    >
      <I18nText
        v-if="valueLabelKey"
        :k="valueLabelKey"
      />
      <template v-else>{{ valueLabel }}</template>
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
        :key="chip.labelKey || chip.label"
        class="module-stat-card__chip"
      >
        <span class="module-stat-card__chip-label">
          <I18nText
            v-if="chip.labelKey"
            :k="chip.labelKey"
            dense
          />
          <template v-else>{{ chip.label }}</template>
        </span>
        <span class="module-stat-card__chip-value">
          <I18nText
            v-if="chip.valueKey"
            :k="chip.valueKey"
            :params="chip.valueParams"
            dense
          />
          <template v-else>{{ chip.value }}</template>
        </span>
      </li>
    </ul>
    <p
      v-if="remarkKey || remark"
      class="swiss-stat-card__sub"
    >
      <I18nText
        v-if="remarkKey"
        :k="remarkKey"
      />
      <template v-else>{{ remark }}</template>
    </p>
    <div
      v-if="empty"
      class="module-stat-card__empty"
    >
      <I18nText
        v-if="emptyTextKey"
        :k="emptyTextKey"
      />
      <template v-else>{{ emptyText }}</template>
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
