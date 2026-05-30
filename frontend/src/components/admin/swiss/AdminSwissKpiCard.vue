<script setup lang="ts">
/**
 * Single KPI stat card with icon and large value.
 */
import { computed, type Component } from 'vue'

import type { AdminSwissStatTheme } from '@/constants/adminSwissStatTheme'
import { useSwissStatCardClasses } from '@/composables/admin/useSwissStatCardClasses'

const props = withDefaults(
  defineProps<{
    title: string
    value: string | number
    icon?: Component
    theme?: AdminSwissStatTheme
    clickable?: boolean
    compact?: boolean
  }>(),
  {
    icon: undefined,
    theme: 'neutral',
    clickable: false,
    compact: false,
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
    stripe: 'left',
    clickable: props.clickable,
    compact: props.compact,
  }))
)

function onClick(event: MouseEvent): void {
  if (props.clickable) {
    emit('click', event)
  }
}
</script>

<template>
  <article :class="cardClasses" @click="onClick">
    <div class="swiss-stat-card__header">
      <div v-if="icon" class="swiss-stat-card__icon">
        <el-icon :size="compact ? 18 : 22">
          <component :is="icon" />
        </el-icon>
      </div>
      <h3 class="swiss-stat-card__title">
        {{ title }}
      </h3>
    </div>
    <p class="swiss-stat-card__value">
      {{ displayValue }}
    </p>
    <div v-if="$slots.footer" class="swiss-stat-card__hint">
      <slot name="footer" />
    </div>
  </article>
</template>
