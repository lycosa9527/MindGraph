<script setup lang="ts">
defineProps<{
  mode: 'balanced' | 'right'
}>()
</script>

<template>
  <svg
    class="mm-structure-icon"
    viewBox="0 0 52 32"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
  >
    <!-- balanced: center node + branches on both sides -->
    <template v-if="mode === 'balanced'">
      <rect
        x="20"
        y="11"
        width="12"
        height="10"
        rx="2.5"
        class="mm-structure-icon__root"
      />
      <!-- left branch -->
      <path
        d="M20 16 H14 V12 H8"
        class="mm-structure-icon__line"
        stroke-width="1.2"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
      <path
        d="M20 16 H14 V20 H8"
        class="mm-structure-icon__line"
        stroke-width="1.2"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
      <rect
        x="2"
        y="9"
        width="8"
        height="6"
        rx="1.5"
        class="mm-structure-icon__node"
      />
      <rect
        x="2"
        y="17"
        width="8"
        height="6"
        rx="1.5"
        class="mm-structure-icon__node"
      />
      <!-- right branch -->
      <path
        d="M32 16 H38 V12 H44"
        class="mm-structure-icon__line"
        stroke-width="1.2"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
      <path
        d="M32 16 H38 V20 H44"
        class="mm-structure-icon__line"
        stroke-width="1.2"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
      <rect
        x="42"
        y="9"
        width="8"
        height="6"
        rx="1.5"
        class="mm-structure-icon__node"
      />
      <rect
        x="42"
        y="17"
        width="8"
        height="6"
        rx="1.5"
        class="mm-structure-icon__node"
      />
    </template>

    <!-- right-only: root on left, branches to the right -->
    <template v-else>
      <rect
        x="6"
        y="11"
        width="12"
        height="10"
        rx="2.5"
        class="mm-structure-icon__root"
      />
      <path
        d="M18 16 H24 V12 H30"
        class="mm-structure-icon__line"
        stroke-width="1.2"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
      <path
        d="M18 16 H24 V20 H30"
        class="mm-structure-icon__line"
        stroke-width="1.2"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
      <rect
        x="28"
        y="9"
        width="10"
        height="6"
        rx="1.5"
        class="mm-structure-icon__node"
      />
      <rect
        x="28"
        y="17"
        width="10"
        height="6"
        rx="1.5"
        class="mm-structure-icon__node"
      />
    </template>
  </svg>
</template>

<style scoped>
.mm-structure-icon {
  width: 52px;
  height: 32px;
  flex-shrink: 0;
}

.mm-structure-icon__root {
  fill: #7dd3fc;
  stroke: #1e3a5f;
  stroke-width: 1;
}

.mm-structure-icon__node {
  fill: #fff;
  stroke: #1e3a5f;
  stroke-width: 1;
}

.mm-structure-icon__line {
  stroke: #1e3a5f;
  fill: none;
}
</style>
