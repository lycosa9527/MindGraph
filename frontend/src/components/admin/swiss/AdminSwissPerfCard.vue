<script setup lang="ts">
/**
 * Performance metric card — percentage, progress, optional gauge.
 */
import { computed } from 'vue'

import type { AdminSwissStatTheme } from '@/constants/adminSwissStatTheme'
import { useSwissStatCardClasses } from '@/composables/admin/useSwissStatCardClasses'

const props = withDefaults(
  defineProps<{
    label: string
    pct?: number
    theme?: AdminSwissStatTheme
    progressVariant?: 'linear' | 'gauge' | 'none'
    nearLimit?: boolean
    atLimit?: boolean
  }>(),
  {
    pct: undefined,
    theme: 'storage',
    progressVariant: 'linear',
    nearLimit: false,
    atLimit: false,
  }
)

const clampedPct = computed(() => {
  const raw = props.pct ?? 0
  if (Number.isNaN(raw) || !Number.isFinite(raw)) {
    return 0
  }
  return Math.min(100, Math.max(0, Math.round(raw * 10) / 10))
})

const fillWidth = computed(() => {
  if (clampedPct.value <= 0) {
    return 0
  }
  return Math.min(100, Math.max(clampedPct.value, 2))
})

const cardClasses = useSwissStatCardClasses(
  computed(() => props.theme),
  computed(() => ({
    stripe: 'left',
    nearLimit: props.nearLimit,
    atLimit: props.atLimit,
  }))
)
</script>

<template>
  <article :class="cardClasses">
    <div class="swiss-stat-card__header">
      <h3 class="swiss-stat-card__title">
        {{ label }}
      </h3>
      <span v-if="pct != null" class="swiss-stat-card__pct">{{ clampedPct }}%</span>
    </div>

    <div v-if="progressVariant === 'gauge'" class="swiss-stat-card__gauge">
      <el-progress type="dashboard" :percentage="clampedPct" :width="88" :stroke-width="8" />
    </div>
    <div
      v-else-if="progressVariant === 'linear' && pct != null"
      class="swiss-stat-card__track"
      role="progressbar"
      :aria-valuenow="clampedPct"
      aria-valuemin="0"
      aria-valuemax="100"
    >
      <div class="swiss-stat-card__fill" :style="{ width: `${fillWidth}%` }" />
    </div>

    <p v-if="$slots.kpi" class="swiss-stat-card__sub">
      <slot name="kpi" />
    </p>
    <p v-if="$slots.sub" class="swiss-stat-card__sub">
      <slot name="sub" />
    </p>

    <div v-if="$slots.default" class="swiss-stat-card__body">
      <slot />
    </div>

    <p v-if="$slots.hint" class="swiss-stat-card__hint">
      <slot name="hint" />
    </p>
  </article>
</template>
