<script setup lang="ts">
defineProps<{
  kind: 'blanks' | 'worksheet'
}>()
</script>

<template>
  <svg
    class="w-4 h-4"
    viewBox="0 0 16 16"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
  >
    <template v-if="kind === 'blanks'">
      <rect
        x="1.2"
        y="6.1"
        width="5.4"
        height="3.8"
        rx="1.15"
        fill="currentColor"
        fill-opacity="0.18"
        stroke="currentColor"
        stroke-width="1.15"
      />
      <path
        d="M6.6 8 H8.35 M6.6 8 L10.15 4.15 M6.6 8 L10.15 11.85"
        stroke="currentColor"
        stroke-width="1.15"
        stroke-linecap="round"
      />
      <rect
        x="9.7"
        y="2.35"
        width="5.1"
        height="3.15"
        rx="1"
        fill="currentColor"
        fill-opacity="0.18"
        stroke="currentColor"
        stroke-width="1.15"
      />
      <rect
        x="10.05"
        y="6.35"
        width="5.1"
        height="3.15"
        rx="1"
        fill="none"
        stroke="currentColor"
        stroke-width="1.15"
        stroke-dasharray="1.35 1.05"
      />
      <path
        d="M11.2 7.92 H13.95"
        stroke="currentColor"
        stroke-width="1"
        stroke-linecap="round"
        opacity="0.55"
      />
      <rect
        x="9.7"
        y="10.5"
        width="5.1"
        height="3.15"
        rx="1"
        fill="currentColor"
        fill-opacity="0.18"
        stroke="currentColor"
        stroke-width="1.15"
      />
    </template>
    <template v-else>
      <path
        d="M3.2 1.7 H10.2 L12.8 4.3 V14.3 H3.2 Z"
        fill="currentColor"
        fill-opacity="0.12"
        stroke="currentColor"
        stroke-width="1.15"
        stroke-linejoin="round"
      />
      <path
        d="M10.2 1.7 V4.3 H12.8"
        stroke="currentColor"
        stroke-width="1.15"
        stroke-linejoin="round"
      />
      <path
        d="M5.05 7.05 H10.95"
        stroke="currentColor"
        stroke-width="1.15"
        stroke-linecap="round"
      />
      <path
        d="M5.05 9.35 H9.2"
        stroke="currentColor"
        stroke-width="1.15"
        stroke-linecap="round"
        stroke-dasharray="1.4 1.05"
      />
      <path
        d="M5.05 11.55 H10.2"
        stroke="currentColor"
        stroke-width="1.15"
        stroke-linecap="round"
        stroke-dasharray="1.4 1.05"
      />
    </template>
  </svg>
</template>
