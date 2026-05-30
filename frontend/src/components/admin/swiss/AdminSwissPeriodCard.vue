<script setup lang="ts">
/**
 * Period picker tile for token trend modals.
 */
import { computed } from 'vue'

import type { AdminSwissStatTheme } from '@/constants/adminSwissStatTheme'
import { useSwissStatCardClasses } from '@/composables/admin/useSwissStatCardClasses'

const props = withDefaults(
  defineProps<{
    label: string
    value: string | number
    active?: boolean
    theme?: AdminSwissStatTheme
    clickable?: boolean
  }>(),
  {
    active: false,
    theme: 'storage',
    clickable: true,
  }
)

const emit = defineEmits<{
  click: [event: MouseEvent]
}>()

const displayValue = computed(() => {
  if (typeof props.value === 'number') {
    return props.value.toLocaleString()
  }
  return props.value
})

const cardClasses = useSwissStatCardClasses(
  computed(() => props.theme),
  computed(() => ({
    stripe: 'top' as const,
    clickable: props.clickable,
    periodActive: props.active,
  }))
)

const rootClasses = computed(() => [...cardClasses.value, 'swiss-stat-card--period'])

function onClick(event: MouseEvent): void {
  if (props.clickable) {
    emit('click', event)
  }
}
</script>

<template>
  <article :class="rootClasses" @click="onClick">
    <p class="swiss-stat-card__period-label">{{ label }}</p>
    <p class="swiss-stat-card__period-value">{{ displayValue }}</p>
  </article>
</template>
