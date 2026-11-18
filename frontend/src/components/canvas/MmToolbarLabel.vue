<script setup lang="ts">
/**
 * Toolbar label that can collapse to a short abbreviation.
 * The full translation stays in the DOM for hover reveal.
 */
import { computed } from 'vue'

import I18nText from '@/components/common/I18nText.vue'
import { useLanguage } from '@/composables/core/useLanguage'
import { abbreviateToolbarLabel } from '@/utils/toolbarLabelAbbreviation'

const props = withDefaults(
  defineProps<{
    /** Message key when `text` is not set. */
    k?: string
    /** Pre-resolved label (e.g. school MindMate agent name). */
    text?: string
    /** Show the abbreviation even when the toolbar row still has room. */
    short?: boolean
  }>(),
  { k: '', text: '', short: false }
)

const { t } = useLanguage()
const fullLabel = computed(() => {
  if (props.text) {
    return props.text
  }
  return props.k ? t(props.k) : ''
})
const shortLabel = computed(() => abbreviateToolbarLabel(fullLabel.value))
</script>

<template>
  <span
    class="mm-toolbar-label"
    :class="{ 'is-short': short }"
  >
    <span class="mm-label-full">
      <template v-if="text">{{ text }}</template>
      <I18nText
        v-else-if="k"
        :k="k"
      />
    </span>
    <span
      class="mm-label-short"
      aria-hidden="true"
      >{{ shortLabel }}</span
    >
  </span>
</template>

<style scoped>
.mm-toolbar-label {
  display: inline-flex;
  align-items: center;
  min-width: 0;
}

.mm-label-short {
  display: none;
  font-weight: 600;
  letter-spacing: 0.01em;
  white-space: nowrap;
}
</style>
