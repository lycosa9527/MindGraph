<script setup lang="ts">
/**
 * Service / product panel card with top accent stripe.
 */
import { computed } from 'vue'

import type { AdminSwissStatTheme } from '@/constants/adminSwissStatTheme'
import { useSwissStatCardClasses } from '@/composables/admin/useSwissStatCardClasses'

const props = withDefaults(
  defineProps<{
    theme?: AdminSwissStatTheme
    clickable?: boolean
    focusable?: boolean
  }>(),
  {
    theme: 'platform',
    clickable: false,
    focusable: false,
  }
)

const emit = defineEmits<{
  click: [event: MouseEvent]
}>()

const cardClasses = useSwissStatCardClasses(
  computed(() => props.theme),
  computed(() => ({
    stripe: 'top',
    clickable: props.clickable,
  }))
)

function onClick(event: MouseEvent): void {
  if (props.clickable) {
    emit('click', event)
  }
}

function onKeydown(event: KeyboardEvent): void {
  if (!props.focusable || !props.clickable) {
    return
  }
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    emit('click', event as unknown as MouseEvent)
  }
}
</script>

<template>
  <article
    :class="cardClasses"
    :tabindex="focusable && clickable ? 0 : undefined"
    @click="onClick"
    @keydown="onKeydown"
  >
    <header v-if="$slots.header" class="swiss-stat-card__service-header">
      <slot name="header" />
    </header>
    <div class="swiss-stat-card__body">
      <slot />
    </div>
  </article>
</template>
