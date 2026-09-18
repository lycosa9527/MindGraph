<script setup lang="ts">
/**
 * UI chrome label: primary locale at regular size, optional presenter line below.
 * Message keys only — never pass model output or autocomplete items.
 */
import { computed } from 'vue'

import { resolveBilingual } from '@/i18n/resolveBilingual'

const props = withDefaults(
  defineProps<{
    k: string
    params?: Record<string, unknown>
    /** Skip the presenter line (product names, compact chrome). */
    primaryOnly?: boolean
    /** Tighter stack for pills and dropdown rows. */
    dense?: boolean
  }>(),
  {
    primaryOnly: false,
    dense: false,
  }
)

const copy = computed(() => resolveBilingual(props.k, props.params))
const secondary = computed(() => (props.primaryOnly ? null : copy.value.secondary))
</script>

<template>
  <span
    class="i18n-label"
    :class="{ 'i18n-label--dense': dense }"
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
</style>
