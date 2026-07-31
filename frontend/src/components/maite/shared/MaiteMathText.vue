<script setup lang="ts">
/**
 * MaiteMathText — render LaTeX-ish math as Unicode.
 */
import { computed } from 'vue'

import { renderMathText } from '@/utils/maite/mathText'

const props = defineProps<{
  text: string
  tag?: keyof HTMLElementTagNameMap
}>()

const rendered = computed(() => renderMathText(props.text))
const tagName = computed(() => props.tag ?? 'span')
</script>

<template>
  <component :is="tagName" class="maite-math-text">{{ rendered }}</component>
</template>

<style scoped>
.maite-math-text {
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
