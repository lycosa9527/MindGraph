<script setup lang="ts">
/**
 * UI chrome label: primary locale at regular size, optional presenter line.
 * Message keys only — never pass model output or autocomplete items.
 */
import { computed } from 'vue'

import { resolveBilingual } from '@/i18n/resolveBilingual'
import type { BilingualCopy } from '@/i18n/resolveBilingual'
import { uiMessageExists } from '@/i18n/translateForUiLocale'
import { useUIStore } from '@/stores/ui'

const props = withDefaults(
  defineProps<{
    k: string
    params?: Record<string, unknown>
    /** Message key used when `k` is missing from the catalogs (dynamic error codes). */
    fallbackKey?: string
    /** Raw text used when `k` is missing and there is no translated fallback. */
    fallbackText?: string
    /** Skip the presenter line (product names, compact chrome). */
    primaryOnly?: boolean
    /** Tighter stack for pills and dropdown rows. */
    dense?: boolean
    /** Center both lines. Welcome copy and suggestion headings use this. */
    align?: 'start' | 'center'
    /** `beside` puts the presenter language on the right of the primary language. */
    layout?: 'stack' | 'beside'
  }>(),
  {
    fallbackKey: '',
    fallbackText: '',
    primaryOnly: false,
    dense: false,
    align: 'start',
    layout: 'stack',
  }
)

const copy = computed((): BilingualCopy => {
  const locale = useUIStore().language
  if (!uiMessageExists(props.k, locale)) {
    if (props.fallbackKey) return resolveBilingual(props.fallbackKey, props.params)
    if (props.fallbackText) return { primary: props.fallbackText, secondary: null }
  }
  return resolveBilingual(props.k, props.params)
})
const secondary = computed(() => (props.primaryOnly ? null : copy.value.secondary))
</script>

<template>
  <span
    class="i18n-label"
    :class="{
      'i18n-label--dense': dense,
      'i18n-label--center': align === 'center',
      'i18n-label--beside': layout === 'beside' && secondary,
    }"
  >
    <span class="i18n-label__primary">{{ copy.primary }}</span>
    <span
      v-if="secondary"
      class="i18n-label__secondary"
      >{{ secondary }}</span
    >
  </span>
</template>

<style scoped>
.i18n-label {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-start;
  line-height: 1.15;
  text-align: start;
}

.i18n-label--dense {
  line-height: 1.05;
}

.i18n-label--center {
  align-items: center;
}

.i18n-label--center .i18n-label__primary,
.i18n-label--center .i18n-label__secondary {
  text-align: center;
}

.i18n-label__primary,
.i18n-label__secondary {
  width: 100%;
  text-align: start;
}

.i18n-label__secondary {
  font-size: 0.75em;
  opacity: 0.7;
  line-height: 1.2;
  font-weight: 400;
}

.i18n-label--dense .i18n-label__secondary {
  font-size: 0.65em;
  line-height: 1.1;
  margin-top: 1px;
}

.i18n-label--beside {
  flex-direction: row;
  direction: ltr;
  justify-content: space-between;
  align-items: baseline;
  gap: 0.65em;
  width: 100%;
}

.i18n-label--beside .i18n-label__primary,
.i18n-label--beside .i18n-label__secondary {
  width: auto;
  min-width: 0;
  max-width: calc(50% - 0.35em);
}

.i18n-label--beside .i18n-label__primary {
  text-align: start;
}

.i18n-label--beside .i18n-label__secondary {
  text-align: end;
}
</style>
