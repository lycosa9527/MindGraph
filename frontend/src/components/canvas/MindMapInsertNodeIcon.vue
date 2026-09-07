<script setup lang="ts">
defineProps<{
  kind: 'child' | 'sibling'
}>()
</script>

<template>
  <svg
    class="mm-insert-node-icon"
    viewBox="0 0 16 16"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
  >
    <template v-if="kind === 'child'">
      <rect
        x="3"
        y="1.25"
        width="10"
        height="5.1"
        rx="1.15"
        class="mm-insert-node-icon__existing"
      />
      <path
        d="M8 6.35 V8.55"
        class="mm-insert-node-icon__line"
      />
      <rect
        x="3"
        y="8.55"
        width="10"
        height="5.1"
        rx="1.15"
        class="mm-insert-node-icon__added"
      />
    </template>
    <template v-else>
      <path
        d="M2.4 2.9 H4.15 V13.4"
        class="mm-insert-node-icon__line"
      />
      <path
        d="M4.15 4.15 H6.7"
        class="mm-insert-node-icon__line"
      />
      <rect
        x="6.7"
        y="2.05"
        width="7.35"
        height="4.2"
        rx="1.05"
        class="mm-insert-node-icon__existing"
      />
      <path
        d="M4.15 11.85 H6.7"
        class="mm-insert-node-icon__line"
      />
      <rect
        x="6.7"
        y="9.75"
        width="7.35"
        height="4.2"
        rx="1.05"
        class="mm-insert-node-icon__added"
      />
    </template>
  </svg>
</template>

<style scoped>
.mm-insert-node-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  overflow: visible;
}

.mm-insert-node-icon__existing,
.mm-insert-node-icon__line {
  fill: none;
  stroke: currentColor;
  stroke-width: 1.35;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.mm-insert-node-icon__added {
  fill: none;
  stroke: #7c3aed;
  stroke-width: 1.35;
  stroke-linecap: round;
  stroke-linejoin: round;
}

:global(.dark) .mm-insert-node-icon__added {
  stroke: #a78bfa;
}
</style>
