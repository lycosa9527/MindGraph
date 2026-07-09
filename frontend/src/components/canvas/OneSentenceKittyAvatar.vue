<script setup lang="ts">
/**
 * Compact Kitty avatar for one-sentence chat rows (static SVG, no mascot runtime).
 */
withDefaults(
  defineProps<{
    size?: number
  }>(),
  {
    size: 32,
  }
)
</script>

<template>
  <div
    class="one-sentence-kitty-avatar shrink-0"
    :style="{ width: `${size}px`, height: `${size}px` }"
    aria-hidden="true"
  >
    <svg
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      class="h-full w-full"
    >
      <circle
        cx="24"
        cy="24"
        r="24"
        fill="#f5f3ff"
      />
      <path
        d="M14 20 L11 12 L18 17 Z"
        fill="#1f1f24"
      />
      <path
        d="M34 20 L37 12 L30 17 Z"
        fill="#1f1f24"
      />
      <ellipse
        cx="24"
        cy="27"
        rx="13"
        ry="11"
        fill="#1f1f24"
      />
      <ellipse
        cx="18.5"
        cy="26"
        rx="4.2"
        ry="4.8"
        fill="#fcfcfc"
      />
      <ellipse
        cx="29.5"
        cy="26"
        rx="4.2"
        ry="4.8"
        fill="#fcfcfc"
      />
      <circle
        cx="18.5"
        cy="26.5"
        r="2.1"
        fill="#89e289"
      />
      <circle
        cx="29.5"
        cy="26.5"
        r="2.1"
        fill="#eecf68"
      />
      <circle
        cx="18.8"
        cy="26.2"
        r="0.9"
        fill="#111111"
      />
      <circle
        cx="29.8"
        cy="26.2"
        r="0.9"
        fill="#111111"
      />
      <path
        d="M22 31 Q24 32.5 26 31"
        stroke="#454552"
        stroke-width="1.2"
        stroke-linecap="round"
        fill="none"
      />
      <circle
        cx="16"
        cy="30"
        r="1.1"
        fill="#454552"
        opacity="0.55"
      />
      <circle
        cx="32"
        cy="30"
        r="1.1"
        fill="#454552"
        opacity="0.55"
      />
    </svg>
  </div>
</template>

<style scoped>
.one-sentence-kitty-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  overflow: hidden;
  box-shadow: 0 0 0 1px rgb(221 214 254);
}
</style>
