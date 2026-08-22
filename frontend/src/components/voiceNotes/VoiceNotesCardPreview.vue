<script setup lang="ts">
/**
 * Compact mic + mindmap preview for the mobile diagram-type card.
 */
</script>

<template>
  <svg
    viewBox="0 0 200 150"
    class="voice-notes-card-svg"
    aria-hidden="true"
  >
    <path
      d="M 100 75 Q 65 55, 48 48"
      stroke="#64b5f6"
      stroke-width="3"
      fill="none"
    />
    <path
      d="M 100 75 Q 65 95, 48 102"
      stroke="#64b5f6"
      stroke-width="3"
      fill="none"
    />
    <path
      d="M 100 75 Q 135 55, 152 48"
      stroke="#64b5f6"
      stroke-width="3"
      fill="none"
    />
    <path
      d="M 100 75 Q 135 95, 152 102"
      stroke="#64b5f6"
      stroke-width="3"
      fill="none"
    />
    <circle
      cx="48"
      cy="48"
      r="10"
      fill="#90caf9"
    />
    <circle
      cx="48"
      cy="102"
      r="10"
      fill="#90caf9"
    />
    <circle
      cx="152"
      cy="48"
      r="10"
      fill="#90caf9"
    />
    <circle
      cx="152"
      cy="102"
      r="10"
      fill="#90caf9"
    />
    <rect
      x="88"
      y="52"
      width="24"
      height="32"
      rx="12"
      fill="#1976d2"
    />
    <path
      d="M 92 84 h 16 v 8 a 8 8 0 0 1 -16 0 z"
      fill="#1976d2"
    />
    <line
      x1="100"
      y1="94"
      x2="100"
      y2="104"
      stroke="#1976d2"
      stroke-width="3"
      stroke-linecap="round"
    />
  </svg>
</template>

<style scoped>
.voice-notes-card-svg {
  width: 100%;
  aspect-ratio: 200 / 150;
}
</style>
