<script setup lang="ts">
/**
 * Period picker tile for token trend modals.
 */
import { computed } from 'vue'

import I18nText from '@/components/common/I18nText.vue'
import { useSwissStatCardClasses } from '@/composables/admin/useSwissStatCardClasses'
import type { AdminSwissStatTheme } from '@/constants/adminSwissStatTheme'

const props = withDefaults(
  defineProps<{
    label?: string
    labelKey?: string
    value: string | number
    active?: boolean
    theme?: AdminSwissStatTheme
    clickable?: boolean
  }>(),
  {
    label: '',
    labelKey: '',
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
  <article
    :class="rootClasses"
    @click="onClick"
  >
    <p class="swiss-stat-card__period-label">
      <I18nText
        v-if="labelKey"
        :k="labelKey"
      />
      <template v-else>{{ label }}</template>
    </p>
    <p class="swiss-stat-card__period-value">{{ displayValue }}</p>
  </article>
</template>
