<script setup lang="ts">
/**
 * Title-row collab mark: large + small raised-arm silhouettes (not the 教研 Users glyph).
 */
withDefaults(
  defineProps<{
    size?: number
  }>(),
  { size: 16 }
)
</script>

<template>
  <svg
    xmlns="http://www.w3.org/2000/svg"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="currentColor"
    aria-hidden="true"
  >
    <circle
      cx="6.85"
      cy="4.55"
      r="2.6"
    />
    <path
      d="M11.15 8.15v13.05c0 .55-.45 1-1 1H4.85c-1.05 0-1.55-1.2-1.05-2.05L4.5 18.4V10c0-1.02.83-1.85 1.85-1.85h4.8Z"
    />
    <path
      fill="none"
      stroke="currentColor"
      stroke-width="2.55"
      stroke-linecap="round"
      d="M4.35 13.05 1.7 9.55"
    />
    <circle
      cx="16.95"
      cy="8.05"
      r="2.1"
    />
    <path
      d="M12.85 11.05v10.15c0 .5.4.9.9.9h4.55c.95 0 1.4-1.1.95-1.9l-.5-1.05V12.7c0-.9-.73-1.65-1.65-1.65h-4.25Z"
    />
    <path
      fill="none"
      stroke="currentColor"
      stroke-width="2.15"
      stroke-linecap="round"
      d="M19.15 14.55 21.2 12.15"
    />
  </svg>
</template>
