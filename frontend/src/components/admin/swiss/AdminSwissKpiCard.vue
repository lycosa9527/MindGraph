<script setup lang="ts">
/**
 * Single KPI stat card with icon and large value.
 */
import { type Component, computed } from 'vue'

import I18nText from '@/components/common/I18nText.vue'
import { useSwissStatCardClasses } from '@/composables/admin/useSwissStatCardClasses'
import type { AdminSwissStatTheme } from '@/constants/adminSwissStatTheme'

const props = withDefaults(
  defineProps<{
    title?: string
    titleKey?: string
    titleParams?: Record<string, unknown>
    value?: string | number
    icon?: Component
    theme?: AdminSwissStatTheme
    clickable?: boolean
    compact?: boolean
  }>(),
  {
    title: '',
    titleKey: '',
    titleParams: undefined,
    value: '',
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
  <article
    :class="cardClasses"
    @click="onClick"
  >
    <div class="swiss-stat-card__header">
      <div
        v-if="icon"
        class="swiss-stat-card__icon"
      >
        <el-icon :size="compact ? 18 : 22">
          <component :is="icon" />
        </el-icon>
      </div>
      <h3 class="swiss-stat-card__title">
        <slot name="title">
          <I18nText
            v-if="titleKey"
            :k="titleKey"
            :params="titleParams"
          />
          <template v-else>{{ title }}</template>
        </slot>
      </h3>
    </div>
    <p class="swiss-stat-card__value">
      <slot name="value">{{ displayValue }}</slot>
    </p>
    <div
      v-if="$slots.footer"
      class="swiss-stat-card__hint"
    >
      <slot name="footer" />
    </div>
  </article>
</template>
