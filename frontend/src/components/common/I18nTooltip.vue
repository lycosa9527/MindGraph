<script setup lang="ts">
/**
 * Element Plus tooltip whose content is bilingual UI chrome (message keys only).
 */
import { ElTooltip } from 'element-plus'

import I18nText from '@/components/common/I18nText.vue'

withDefaults(
  defineProps<{
    k: string
    params?: Record<string, unknown>
    suffix?: string
    primaryOnly?: boolean
    placement?:
      | 'top'
      | 'top-start'
      | 'top-end'
      | 'bottom'
      | 'bottom-start'
      | 'bottom-end'
      | 'left'
      | 'left-start'
      | 'left-end'
      | 'right'
      | 'right-start'
      | 'right-end'
    disabled?: boolean
    popperClass?: string
    /** False so a fast pass across the trigger cannot hold the label open. */
    enterable?: boolean
    showAfter?: number
    hideAfter?: number
  }>(),
  {
    suffix: '',
    primaryOnly: false,
    placement: 'top',
    disabled: false,
    popperClass: '',
    enterable: true,
    showAfter: 0,
    hideAfter: 200,
  }
)
</script>

<template>
  <ElTooltip
    :placement="placement"
    :disabled="disabled"
    :popper-class="popperClass"
    :enterable="enterable"
    :show-after="showAfter"
    :hide-after="hideAfter"
  >
    <template #content>
      <span class="i18n-tooltip-content">
        <I18nText
          :k="k"
          :params="params"
          :primary-only="primaryOnly"
        />
        <span
          v-if="suffix"
          class="i18n-tooltip-suffix"
          >{{ suffix }}</span
        >
      </span>
    </template>
    <slot />
  </ElTooltip>
</template>

<style scoped>
.i18n-tooltip-content {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  text-align: start;
}

.i18n-tooltip-suffix {
  font-size: 0.85em;
  opacity: 0.75;
  white-space: nowrap;
}
</style>
