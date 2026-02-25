<script setup lang="ts">
/**
 * DiagramPreviewSvg - SVG preview for each diagram type
 * From archive/templates/editor.html diagram gallery
 */
import type { DiagramType } from '@/types'

defineProps<{
  type: DiagramType
}>()
</script>

<template>
  <div class="diagram-preview">
    <!-- Circle Map -->
    <svg
      v-if="type === 'circle_map'"
      viewBox="0 0 200 150"
      class="diagram-svg"
    >
      <circle class="anim-node" cx="100" cy="75" r="25" fill="#e91e63" />
      <circle
        class="anim-line"
        cx="100"
        cy="75"
        r="71"
        fill="none"
        stroke="#f48fb1"
        stroke-width="2"
      />
      <circle class="anim-node" cx="100" cy="23" r="13" fill="#f48fb1" />
      <circle class="anim-node" cx="150" cy="59" r="13" fill="#f48fb1" />
      <circle class="anim-node" cx="131" cy="117" r="13" fill="#f48fb1" />
      <circle class="anim-node" cx="69" cy="117" r="13" fill="#f48fb1" />
      <circle class="anim-node" cx="50" cy="59" r="13" fill="#f48fb1" />
    </svg>

    <!-- Bubble Map -->
    <svg
      v-else-if="type === 'bubble_map'"
      viewBox="0 0 200 150"
      class="diagram-svg"
    >
      <line
        class="anim-line"
        x1="100"
        y1="80"
        x2="100"
        y2="25"
        stroke="#81c784"
        stroke-width="2"
      />
      <line
        class="anim-line"
        x1="100"
        y1="80"
        x2="152"
        y2="63"
        stroke="#81c784"
        stroke-width="2"
      />
      <line
        class="anim-line"
        x1="100"
        y1="80"
        x2="132"
        y2="125"
        stroke="#81c784"
        stroke-width="2"
      />
      <line
        class="anim-line"
        x1="100"
        y1="80"
        x2="68"
        y2="125"
        stroke="#81c784"
        stroke-width="2"
      />
      <line
        class="anim-line"
        x1="100"
        y1="80"
        x2="48"
        y2="63"
        stroke="#81c784"
        stroke-width="2"
      />
      <circle class="anim-node" cx="100" cy="80" r="25" fill="#4caf50" />
      <circle class="anim-node" cx="100" cy="25" r="14" fill="#81c784" />
      <circle class="anim-node" cx="152" cy="63" r="14" fill="#81c784" />
      <circle class="anim-node" cx="132" cy="125" r="14" fill="#81c784" />
      <circle class="anim-node" cx="68" cy="125" r="14" fill="#81c784" />
      <circle class="anim-node" cx="48" cy="63" r="14" fill="#81c784" />
    </svg>

    <!-- Double Bubble Map -->
    <svg
      v-else-if="type === 'double_bubble_map'"
      viewBox="0 0 200 150"
      class="diagram-svg"
    >
      <line
        class="anim-line"
        x1="60"
        y1="75"
        x2="20"
        y2="50"
        stroke="#64b5f6"
        stroke-width="2"
      />
      <line
        class="anim-line"
        x1="60"
        y1="75"
        x2="20"
        y2="100"
        stroke="#64b5f6"
        stroke-width="2"
      />
      <line
        class="anim-line"
        x1="140"
        y1="75"
        x2="180"
        y2="50"
        stroke="#64b5f6"
        stroke-width="2"
      />
      <line
        class="anim-line"
        x1="140"
        y1="75"
        x2="180"
        y2="100"
        stroke="#64b5f6"
        stroke-width="2"
      />
      <line
        class="anim-line"
        x1="60"
        y1="75"
        x2="100"
        y2="50"
        stroke="#64b5f6"
        stroke-width="2"
      />
      <line
        class="anim-line"
        x1="140"
        y1="75"
        x2="100"
        y2="50"
        stroke="#64b5f6"
        stroke-width="2"
      />
      <line
        class="anim-line"
        x1="60"
        y1="75"
        x2="100"
        y2="100"
        stroke="#64b5f6"
        stroke-width="2"
      />
      <line
        class="anim-line"
        x1="140"
        y1="75"
        x2="100"
        y2="100"
        stroke="#64b5f6"
        stroke-width="2"
      />
      <circle class="anim-node" cx="60" cy="75" r="22" fill="#2196f3" />
      <circle class="anim-node" cx="140" cy="75" r="22" fill="#2196f3" />
      <circle class="anim-node" cx="20" cy="50" r="12" fill="#64b5f6" />
      <circle class="anim-node" cx="20" cy="100" r="12" fill="#64b5f6" />
      <circle class="anim-node" cx="180" cy="50" r="12" fill="#64b5f6" />
      <circle class="anim-node" cx="180" cy="100" r="12" fill="#64b5f6" />
      <circle class="anim-node" cx="100" cy="50" r="12" fill="#90caf9" />
      <circle class="anim-node" cx="100" cy="100" r="12" fill="#90caf9" />
    </svg>

    <!-- Tree Map -->
    <svg
      v-else-if="type === 'tree_map'"
      viewBox="0 0 200 150"
      class="diagram-svg"
    >
      <!-- Single path for T connector: stroke-linejoin ensures clean corners; lines extend into nodes -->
      <path
        class="anim-line"
        d="M 100 49 L 100 74 L 45 74 L 45 112 M 100 74 L 100 112 M 100 74 L 155 74 L 155 112"
        stroke="#ce93d8"
        stroke-width="2"
        stroke-linejoin="round"
        fill="none"
      />
      <rect
        class="anim-node"
        x="75"
        y="24"
        width="50"
        height="25"
        rx="3"
        fill="#9c27b0"
      />
      <rect
        class="anim-node"
        x="22"
        y="104"
        width="46"
        height="22"
        rx="3"
        fill="#ba68c8"
      />
      <rect
        class="anim-node"
        x="77"
        y="104"
        width="46"
        height="22"
        rx="3"
        fill="#ba68c8"
      />
      <rect
        class="anim-node"
        x="132"
        y="104"
        width="46"
        height="22"
        rx="3"
        fill="#ba68c8"
      />
    </svg>

    <!-- Brace Map -->
    <svg
      v-else-if="type === 'brace_map'"
      viewBox="0 0 200 150"
      class="diagram-svg"
    >
      <path
        class="anim-line"
        d="M 115 25 Q 105 25, 105 40 L 105 65 Q 105 75, 95 75 Q 105 75, 105 85 L 105 110 Q 105 125, 115 125"
        stroke="#4dd0e1"
        stroke-width="3"
        fill="none"
      />
      <rect
        class="anim-node"
        x="15"
        y="55"
        width="70"
        height="40"
        rx="4"
        fill="#00bcd4"
      />
      <rect
        class="anim-node"
        x="125"
        y="22"
        width="60"
        height="26"
        rx="3"
        fill="#4dd0e1"
      />
      <rect
        class="anim-node"
        x="125"
        y="62"
        width="60"
        height="26"
        rx="3"
        fill="#4dd0e1"
      />
      <rect
        class="anim-node"
        x="125"
        y="102"
        width="60"
        height="26"
        rx="3"
        fill="#4dd0e1"
      />
    </svg>

    <!-- Flow Map -->
    <svg
      v-else-if="type === 'flow_map'"
      viewBox="0 0 200 150"
      class="diagram-svg"
    >
      <line
        class="anim-line"
        x1="50"
        y1="75"
        x2="65"
        y2="75"
        stroke="#ffb74d"
        stroke-width="4"
      />
      <polygon class="anim-node" points="65,68 80,75 65,82" fill="#ffb74d" />
      <line
        class="anim-line"
        x1="120"
        y1="75"
        x2="135"
        y2="75"
        stroke="#ffb74d"
        stroke-width="4"
      />
      <polygon class="anim-node" points="135,68 150,75 135,82" fill="#ffb74d" />
      <rect
        class="anim-node"
        x="5"
        y="60"
        width="45"
        height="30"
        rx="4"
        fill="#ff9800"
      />
      <rect
        class="anim-node"
        x="80"
        y="60"
        width="40"
        height="30"
        rx="4"
        fill="#ff9800"
      />
      <rect
        class="anim-node"
        x="150"
        y="60"
        width="45"
        height="30"
        rx="4"
        fill="#ff9800"
      />
    </svg>

    <!-- Multi-Flow Map -->
    <svg
      v-else-if="type === 'multi_flow_map'"
      viewBox="0 0 200 150"
      class="diagram-svg"
    >
      <line
        class="anim-line"
        x1="48"
        y1="51"
        x2="75"
        y2="67"
        stroke="#ff8a65"
        stroke-width="3"
      />
      <line
        class="anim-line"
        x1="48"
        y1="99"
        x2="75"
        y2="83"
        stroke="#ff8a65"
        stroke-width="3"
      />
      <line
        class="anim-line"
        x1="125"
        y1="67"
        x2="152"
        y2="51"
        stroke="#ff8a65"
        stroke-width="3"
      />
      <line
        class="anim-line"
        x1="125"
        y1="83"
        x2="152"
        y2="99"
        stroke="#ff8a65"
        stroke-width="3"
      />
      <rect
        class="anim-node"
        x="75"
        y="62"
        width="50"
        height="26"
        rx="4"
        fill="#ff5722"
      />
      <rect
        class="anim-node"
        x="5"
        y="40"
        width="43"
        height="22"
        rx="3"
        fill="#ff8a65"
      />
      <rect
        class="anim-node"
        x="5"
        y="88"
        width="43"
        height="22"
        rx="3"
        fill="#ff8a65"
      />
      <rect
        class="anim-node"
        x="152"
        y="40"
        width="43"
        height="22"
        rx="3"
        fill="#ff8a65"
      />
      <rect
        class="anim-node"
        x="152"
        y="88"
        width="43"
        height="22"
        rx="3"
        fill="#ff8a65"
      />
    </svg>

    <!-- Bridge Map -->
    <svg
      v-else-if="type === 'bridge_map'"
      viewBox="0 0 200 150"
      class="diagram-svg"
    >
      <line
        class="anim-line"
        x1="20"
        y1="75"
        x2="180"
        y2="75"
        stroke="#666"
        stroke-width="3"
      />
      <path class="anim-node" d="M 92 75 L 100 67 L 108 75 Z" fill="#666" />
      <rect
        class="anim-node"
        x="30"
        y="45"
        width="50"
        height="18"
        rx="3"
        fill="#795548"
      />
      <rect
        class="anim-node"
        x="30"
        y="87"
        width="50"
        height="18"
        rx="3"
        fill="#a1887f"
      />
      <rect
        class="anim-node"
        x="120"
        y="45"
        width="50"
        height="18"
        rx="3"
        fill="#795548"
      />
      <rect
        class="anim-node"
        x="120"
        y="87"
        width="50"
        height="18"
        rx="3"
        fill="#a1887f"
      />
    </svg>

    <!-- Mind Map -->
    <svg
      v-else-if="type === 'mindmap'"
      viewBox="0 0 200 150"
      class="diagram-svg"
    >
      <path
        class="anim-line"
        d="M 100 75 Q 65 55, 50 49"
        stroke="#64b5f6"
        stroke-width="3"
        fill="none"
      />
      <path
        class="anim-line"
        d="M 100 75 Q 65 95, 50 101"
        stroke="#64b5f6"
        stroke-width="3"
        fill="none"
      />
      <path
        class="anim-line"
        d="M 100 75 Q 135 55, 155 49"
        stroke="#64b5f6"
        stroke-width="3"
        fill="none"
      />
      <path
        class="anim-line"
        d="M 100 75 Q 135 95, 155 101"
        stroke="#64b5f6"
        stroke-width="3"
        fill="none"
      />
      <circle class="anim-node" cx="100" cy="75" r="18" fill="#1976d2" />
      <rect
        class="anim-node"
        x="10"
        y="40"
        width="45"
        height="18"
        rx="9"
        fill="#42a5f5"
      />
      <rect
        class="anim-node"
        x="10"
        y="92"
        width="45"
        height="18"
        rx="9"
        fill="#42a5f5"
      />
      <rect
        class="anim-node"
        x="145"
        y="40"
        width="45"
        height="18"
        rx="9"
        fill="#42a5f5"
      />
      <rect
        class="anim-node"
        x="145"
        y="92"
        width="45"
        height="18"
        rx="9"
        fill="#42a5f5"
      />
    </svg>

    <!-- Concept Map -->
    <svg
      v-else-if="type === 'concept_map'"
      viewBox="0 0 200 150"
      class="diagram-svg"
    >
      <line
        class="anim-line"
        x1="100"
        y1="40"
        x2="50"
        y2="100"
        stroke="#ef5350"
        stroke-width="2"
      />
      <line
        class="anim-line"
        x1="100"
        y1="40"
        x2="150"
        y2="100"
        stroke="#ef5350"
        stroke-width="2"
      />
      <line
        class="anim-line"
        x1="50"
        y1="100"
        x2="150"
        y2="100"
        stroke="#ef5350"
        stroke-width="2"
        stroke-dasharray="5,5"
      />
      <circle class="anim-node" cx="100" cy="40" r="22" fill="#f44336" />
      <circle class="anim-node" cx="50" cy="100" r="18" fill="#ef5350" />
      <circle class="anim-node" cx="150" cy="100" r="18" fill="#ef5350" />
    </svg>
  </div>
</template>

<style scoped>
.diagram-preview {
  width: 100%;
  aspect-ratio: 200 / 150;
  display: flex;
  align-items: center;
  justify-content: center;
}

.diagram-svg {
  width: 100%;
  height: 100%;
  max-height: 80px;
}

/* Static state when not hovering - diagram fully visible */
.diagram-svg .anim-node {
  opacity: 1;
  transform-origin: center;
}

.diagram-svg .anim-line {
  stroke-dasharray: 100;
  stroke-dashoffset: 0;
  opacity: 1;
}

/* Animation runs only when parent card is hovered - see DiagramTypeGrid */
</style>
