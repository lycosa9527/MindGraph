<script setup lang="ts">
/**
 * UI chrome label: primary locale at regular size, optional presenter line.
 * Message keys only — never pass model output or autocomplete items.
 */
import { computed, nextTick, ref, watch } from 'vue'

import { useResizeObserver } from '@vueuse/core'

import { besideFitScale } from '@/i18n/besideFitScale'
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
    /**
     * `beside` keeps each language on one line: primary on the left, presenter on the right.
     * The line shrinks together when a long language pair would overflow the card.
     */
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

const rootEl = ref<HTMLElement | null>(null)
const primaryEl = ref<HTMLElement | null>(null)
const secondaryEl = ref<HTMLElement | null>(null)
/** 1 = the card font size. Lower only when the one-line pair is wider than the card. */
const besideScale = ref(1)

function updateBesideScale(): void {
  const el = rootEl.value
  const primary = primaryEl.value
  if (!el || !primary || props.layout !== 'beside' || !secondary.value) {
    if (besideScale.value !== 1) besideScale.value = 1
    return
  }
  const available = el.clientWidth
  const gapRaw = Number.parseFloat(getComputedStyle(el).columnGap)
  const gap = Number.isFinite(gapRaw) ? gapRaw : 0
  const used = primary.scrollWidth + (secondaryEl.value?.scrollWidth ?? 0) + gap
  const next = besideFitScale(available, used, besideScale.value)
  if (Math.abs(next - besideScale.value) >= 0.012) besideScale.value = next
}

useResizeObserver(rootEl, () => {
  updateBesideScale()
})

watch(
  () => [copy.value.primary, secondary.value, props.layout] as const,
  () => {
    besideScale.value = 1
    void nextTick().then(updateBesideScale)
  }
)
</script>

<template>
  <span
    ref="rootEl"
    class="i18n-label"
    :class="{
      'i18n-label--dense': dense,
      'i18n-label--center': align === 'center',
      'i18n-label--beside': layout === 'beside' && secondary,
    }"
    :style="besideScale < 1 ? { fontSize: `${besideScale}em` } : undefined"
  >
    <span
      ref="primaryEl"
      class="i18n-label__primary"
      >{{ copy.primary }}</span
    >
    <span
      v-if="secondary"
      ref="secondaryEl"
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
  justify-content: center;
  align-items: baseline;
  gap: 0.65em;
  width: 100%;
  min-width: 0;
  max-width: 100%;
}

.i18n-label--beside .i18n-label__primary,
.i18n-label--beside .i18n-label__secondary {
  width: auto;
  flex: 0 0 auto;
  white-space: nowrap;
}

.i18n-label--beside .i18n-label__primary {
  text-align: start;
}

.i18n-label--beside .i18n-label__secondary {
  text-align: end;
}
</style>
