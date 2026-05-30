<script setup lang="ts">
/**
 * Quota usage card — seats or storage with progress bar.
 */
import { computed, type Component } from 'vue'

import {
  quotaAccentToTheme,
  type AdminSwissQuotaAccent,
  type AdminSwissStatTheme,
} from '@/constants/adminSwissStatTheme'
import { useSwissStatCardClasses } from '@/composables/admin/useSwissStatCardClasses'

const props = withDefaults(
  defineProps<{
    title: string
    used: number
    limit: number
    remainingLabel: string
    icon: Component
    theme?: AdminSwissStatTheme
    accent?: AdminSwissQuotaAccent
    limitSuffix?: string
    usedDecimals?: number
    usedDisplayOverride?: string
    limitDisplayOverride?: string
  }>(),
  {
    theme: undefined,
    accent: 'blue',
    limitSuffix: '',
    usedDecimals: 0,
    usedDisplayOverride: '',
    limitDisplayOverride: '',
  }
)

const resolvedTheme = computed<AdminSwissStatTheme>(() => {
  if (props.theme) {
    return props.theme
  }
  return quotaAccentToTheme(props.accent)
})

const usageRatio = computed(() => {
  if (props.limit <= 0) {
    return 0
  }
  return Math.min(1, Math.max(0, props.used / props.limit))
})

const percentage = computed(() => usageRatio.value * 100)

const percentageBadge = computed(() => {
  const pct = percentage.value
  if (props.used > 0 && pct < 0.1) {
    return '<0.1%'
  }
  if (pct >= 10 || (pct > 0 && Number.isInteger(pct))) {
    return `${Math.round(pct)}%`
  }
  if (pct > 0) {
    return `${pct.toFixed(1)}%`
  }
  return '0%'
})

const fillWidth = computed(() => {
  if (props.used <= 0 || props.limit <= 0) {
    return 0
  }
  return Math.min(100, Math.max(percentage.value, 2))
})

const isNearLimit = computed(() => percentage.value >= 85 && percentage.value < 100)
const isAtLimit = computed(() => props.limit > 0 && props.used >= props.limit)

const cardClasses = useSwissStatCardClasses(resolvedTheme, computed(() => ({
  stripe: 'left',
  nearLimit: isNearLimit.value,
  atLimit: isAtLimit.value,
})))

const usedDisplay = computed(() => {
  if (props.usedDisplayOverride) {
    return props.usedDisplayOverride
  }
  if (props.usedDecimals > 0) {
    return props.used.toFixed(props.usedDecimals)
  }
  return props.used.toLocaleString()
})

const limitDisplay = computed(() => {
  if (props.limitDisplayOverride) {
    return props.limitDisplayOverride
  }
  return `${props.limit.toLocaleString()}${props.limitSuffix}`
})
</script>

<template>
  <article :class="cardClasses">
    <div class="swiss-stat-card__header">
      <div class="swiss-stat-card__icon">
        <el-icon :size="20">
          <component :is="icon" />
        </el-icon>
      </div>
      <h3 class="swiss-stat-card__title">
        {{ title }}
      </h3>
      <span class="swiss-stat-card__badge" :aria-label="percentageBadge">
        {{ percentageBadge }}
      </span>
    </div>

    <div class="swiss-stat-card__value-row">
      <span class="swiss-stat-card__value">{{ usedDisplay }}</span>
      <span class="swiss-stat-card__value-sep">/</span>
      <span class="swiss-stat-card__value-muted">{{ limitDisplay }}</span>
    </div>

    <div
      class="swiss-stat-card__track"
      role="progressbar"
      :aria-valuenow="Math.round(percentage)"
      aria-valuemin="0"
      aria-valuemax="100"
    >
      <div class="swiss-stat-card__fill" :style="{ width: `${fillWidth}%` }" />
    </div>

    <p class="swiss-stat-card__footer">
      <span class="swiss-stat-card__footer-dot" aria-hidden="true" />
      {{ remainingLabel }}
    </p>
  </article>
</template>
