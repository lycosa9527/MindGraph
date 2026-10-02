<script setup lang="ts">
/**
 * Bottom rule for an explicit underline node shape.
 * The parent box must be positioned so the rule sits on its bottom edge.
 */
defineProps<{
  color: string
  /** Sit under the text in normal flow. Otherwise pin to the parent box edge. */
  inline?: boolean
}>()
</script>

<template>
  <span
    class="node-shape-underline"
    :class="{ 'node-shape-underline--inline': inline }"
    :style="{ backgroundColor: color }"
  />
</template>

<style scoped>
.node-shape-underline {
  position: absolute;
  right: 0;
  bottom: 0;
  left: 0;
  height: 2px;
  pointer-events: none;
}

.node-shape-underline--inline {
  position: static;
  display: block;
  width: 100%;
}
</style>
