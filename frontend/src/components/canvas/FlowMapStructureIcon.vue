<script setup lang="ts">
import type { FlowMapStructureMode } from '@/utils/flowMapSubstepArrangement'

defineProps<{
  mode: FlowMapStructureMode
}>()
</script>

<template>
  <svg
    class="flow-structure-icon"
    viewBox="0 0 52 32"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
  >
    <!-- row: step on top, substeps side by side below -->
    <template v-if="mode === 'row'">
      <rect
        x="18"
        y="3"
        width="16"
        height="9"
        rx="2"
        class="flow-structure-icon__step"
      />
      <path
        d="M26 12 V15"
        class="flow-structure-icon__line"
        stroke-width="1.2"
        stroke-linecap="round"
      />
      <path
        d="M14 15 H38"
        class="flow-structure-icon__line"
        stroke-width="1.2"
        stroke-linecap="round"
      />
      <path
        d="M14 15 V17 M26 15 V17 M38 15 V17"
        class="flow-structure-icon__line"
        stroke-width="1.2"
        stroke-linecap="round"
      />
      <rect
        x="8"
        y="17"
        width="12"
        height="7"
        rx="1.5"
        class="flow-structure-icon__sub"
      />
      <rect
        x="20"
        y="17"
        width="12"
        height="7"
        rx="1.5"
        class="flow-structure-icon__sub"
      />
      <rect
        x="32"
        y="17"
        width="12"
        height="7"
        rx="1.5"
        class="flow-structure-icon__sub"
      />
    </template>

    <!-- stack: step on top, substeps stacked below -->
    <template v-else-if="mode === 'stack'">
      <rect
        x="18"
        y="2"
        width="16"
        height="8"
        rx="2"
        class="flow-structure-icon__step"
      />
      <path
        d="M26 10 V12"
        class="flow-structure-icon__line"
        stroke-width="1.2"
        stroke-linecap="round"
      />
      <rect
        x="17"
        y="12"
        width="18"
        height="6"
        rx="1.5"
        class="flow-structure-icon__sub"
      />
      <path
        d="M26 18 V20"
        class="flow-structure-icon__line"
        stroke-width="1.2"
        stroke-linecap="round"
      />
      <rect
        x="17"
        y="20"
        width="18"
        height="6"
        rx="1.5"
        class="flow-structure-icon__sub"
      />
    </template>

    <!-- vertical: steps stacked, substeps to the right -->
    <template v-else>
      <rect
        x="4"
        y="4"
        width="14"
        height="8"
        rx="2"
        class="flow-structure-icon__step"
      />
      <path
        d="M11 12 V15"
        class="flow-structure-icon__line"
        stroke-width="1.2"
        stroke-linecap="round"
      />
      <rect
        x="4"
        y="15"
        width="14"
        height="8"
        rx="2"
        class="flow-structure-icon__step"
      />
      <path
        d="M18 19 H22"
        class="flow-structure-icon__line"
        stroke-width="1.2"
        stroke-linecap="round"
      />
      <rect
        x="22"
        y="12"
        width="12"
        height="6"
        rx="1.5"
        class="flow-structure-icon__sub"
      />
      <rect
        x="22"
        y="20"
        width="12"
        height="6"
        rx="1.5"
        class="flow-structure-icon__sub"
      />
    </template>
  </svg>
</template>

<style scoped>
.flow-structure-icon {
  width: 52px;
  height: 32px;
  flex-shrink: 0;
}

.flow-structure-icon__step {
  fill: #7dd3fc;
  stroke: #1e3a5f;
  stroke-width: 1;
}

.flow-structure-icon__sub {
  fill: #fff;
  stroke: #1e3a5f;
  stroke-width: 1;
}

.flow-structure-icon__line {
  stroke: #1e3a5f;
  fill: none;
}
</style>
