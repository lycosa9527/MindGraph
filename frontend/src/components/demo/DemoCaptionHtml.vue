<script setup lang="ts">
/**
 * Renders a caption that demoCaptionHtml has already sanitized.
 */
import { ref, watch } from 'vue'

const props = defineProps<{ html: string }>()

const root = ref<HTMLElement | null>(null)

function paint(): void {
  const node = root.value
  if (!node) return
  node.innerHTML = props.html
}

watch(() => props.html, paint)
watch(root, paint)
</script>

<template>
  <div
    ref="root"
    class="demo-caption-html"
  />
</template>

<style scoped>
.demo-caption-html {
  line-height: 1.65;
}

.demo-caption-html :deep(ul),
.demo-caption-html :deep(ol) {
  margin: 0.4rem 0 0.4rem 1.25rem;
  padding: 0;
}

.demo-caption-html :deep(p) {
  margin: 0 0 0.6rem;
}

.demo-caption-html :deep(p:last-child) {
  margin-bottom: 0;
}
</style>
