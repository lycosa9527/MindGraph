<script setup lang="ts">
import type { DiagramInsertGlyph } from '@/canvas-ribbon/diagramInsertActions'

defineProps<{
  kind: DiagramInsertGlyph
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
    <template v-if="kind === 'step'">
      <rect
        x="0.7"
        y="5.2"
        width="6.3"
        height="5.6"
        rx="2.8"
        class="mm-insert-node-icon__existing"
      />
      <path
        d="M7 8 H9"
        class="mm-insert-node-icon__line"
      />
      <rect
        x="9"
        y="5.2"
        width="6.3"
        height="5.6"
        rx="2.8"
        class="mm-insert-node-icon__added"
      />
    </template>
    <template v-else-if="kind === 'substep'">
      <rect
        x="0.8"
        y="1"
        width="9.2"
        height="5"
        rx="2.5"
        class="mm-insert-node-icon__existing"
      />
      <path
        d="M5.4 6 V7.6 H8"
        class="mm-insert-node-icon__line"
      />
      <rect
        x="8"
        y="6.4"
        width="7.1"
        height="4.6"
        rx="2.3"
        class="mm-insert-node-icon__added"
      />
    </template>
    <template v-else-if="kind === 'branch'">
      <rect
        x="5.1"
        y="0.7"
        width="5.8"
        height="3.8"
        rx="1"
        class="mm-insert-node-icon__existing"
      />
      <path
        d="M8 4.5 V6.2 M3.5 6.2 H12.5 M3.5 6.2 V7.5 M12.5 6.2 V7.5"
        class="mm-insert-node-icon__line"
      />
      <rect
        x="0.7"
        y="7.5"
        width="5.6"
        height="4.5"
        rx="1"
        class="mm-insert-node-icon__existing"
      />
      <rect
        x="9.7"
        y="7.5"
        width="5.6"
        height="4.5"
        rx="1"
        class="mm-insert-node-icon__added"
      />
    </template>
    <template v-else-if="kind === 'leaf'">
      <rect
        x="2.4"
        y="0.8"
        width="11.2"
        height="4.5"
        rx="1"
        class="mm-insert-node-icon__existing"
      />
      <path
        d="M8 5.3 V7.1"
        class="mm-insert-node-icon__line"
      />
      <rect
        x="4.1"
        y="7.1"
        width="7.8"
        height="4.6"
        rx="1"
        class="mm-insert-node-icon__added"
      />
    </template>
    <template v-else-if="kind === 'part'">
      <path
        d="M5 3.5 Q3.85 3.5 3.85 4.55 L3.85 7.15 L2.15 8 L3.85 8.85 L3.85 11.45 Q3.85 12.5 5 12.5"
        class="mm-insert-node-icon__line"
      />
      <rect
        x="6.9"
        y="1.15"
        width="8.2"
        height="4.7"
        rx="1.15"
        class="mm-insert-node-icon__existing"
      />
      <rect
        x="6.9"
        y="10.15"
        width="8.2"
        height="4.7"
        rx="1.15"
        class="mm-insert-node-icon__added"
      />
    </template>
    <template v-else-if="kind === 'subpart'">
      <rect
        x="1.1"
        y="0.75"
        width="13.8"
        height="3.55"
        rx="1.05"
        class="mm-insert-node-icon__existing"
      />
      <path
        d="M5.55 7.55 Q4.6 7.55 4.6 8.3 L4.6 9.55 L3.3 10.2 L4.6 10.85 L4.6 12.1 Q4.6 12.85 5.55 12.85"
        class="mm-insert-node-icon__line"
      />
      <rect
        x="7.15"
        y="5.85"
        width="7.7"
        height="3.4"
        rx="0.95"
        class="mm-insert-node-icon__existing"
      />
      <rect
        x="7.15"
        y="11.15"
        width="7.7"
        height="3.4"
        rx="0.95"
        class="mm-insert-node-icon__added"
      />
    </template>
    <template v-else-if="kind === 'similarity'">
      <rect
        x="1.15"
        y="2.5"
        width="13.7"
        height="11"
        rx="1.15"
        class="mm-insert-node-icon__added"
      />
      <text
        x="8"
        y="8"
        text-anchor="middle"
        dominant-baseline="central"
        class="mm-insert-node-icon__letter"
      >
        S
      </text>
    </template>
    <template v-else-if="kind === 'difference'">
      <rect
        x="1.15"
        y="2.5"
        width="13.7"
        height="11"
        rx="1.15"
        class="mm-insert-node-icon__added"
      />
      <text
        x="8"
        y="8"
        text-anchor="middle"
        dominant-baseline="central"
        class="mm-insert-node-icon__letter"
      >
        D
      </text>
    </template>
    <template v-else-if="kind === 'cause'">
      <rect
        x="1.15"
        y="2.5"
        width="13.7"
        height="11"
        rx="1.15"
        class="mm-insert-node-icon__added"
      />
      <text
        x="8"
        y="8"
        text-anchor="middle"
        dominant-baseline="central"
        class="mm-insert-node-icon__letter"
      >
        C
      </text>
    </template>
    <template v-else-if="kind === 'effect'">
      <rect
        x="1.15"
        y="2.5"
        width="13.7"
        height="11"
        rx="1.15"
        class="mm-insert-node-icon__added"
      />
      <text
        x="8"
        y="8"
        text-anchor="middle"
        dominant-baseline="central"
        class="mm-insert-node-icon__letter"
      >
        E
      </text>
    </template>
    <template v-else-if="kind === 'child'">
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

.mm-insert-node-icon__letter {
  fill: #7c3aed;
  stroke: none;
  font-size: 10.5px;
  font-weight: 700;
  font-family: system-ui, sans-serif;
}

:global(.dark) .mm-insert-node-icon__added {
  stroke: #a78bfa;
}

:global(.dark) .mm-insert-node-icon__letter {
  fill: #a78bfa;
}
</style>
