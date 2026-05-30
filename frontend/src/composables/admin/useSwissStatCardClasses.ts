import { computed, type ComputedRef } from 'vue'

import type { AdminSwissStatTheme } from '@/constants/adminSwissStatTheme'

export function useSwissStatCardClasses(
  theme: ComputedRef<AdminSwissStatTheme>,
  options: ComputedRef<{
    stripe?: 'left' | 'top' | 'none'
    clickable?: boolean
    compact?: boolean
    nearLimit?: boolean
    atLimit?: boolean
    periodActive?: boolean
  }>
): ComputedRef<string[]> {
  return computed(() => {
    const opts = options.value
    const classes = [
      'swiss-stat-card',
      `swiss-stat-card--theme-${theme.value}`,
    ]
    const stripe = opts.stripe ?? 'left'
    if (stripe === 'left') {
      classes.push('swiss-stat-card--stripe-left')
    } else if (stripe === 'top') {
      classes.push('swiss-stat-card--stripe-top')
    }
    if (opts.clickable) {
      classes.push('swiss-stat-card--clickable')
    }
    if (opts.compact) {
      classes.push('swiss-stat-card--compact')
    }
    if (opts.nearLimit) {
      classes.push('swiss-stat-card--near-limit')
    }
    if (opts.atLimit) {
      classes.push('swiss-stat-card--at-limit')
    }
    if (opts.periodActive) {
      classes.push('swiss-stat-card--period-active')
    }
    return classes
  })
}
