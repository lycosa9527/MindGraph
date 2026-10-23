<script setup lang="ts">
/**
 * Chrome and Edge marks for the browser-plugin download page.
 */
import { useId } from 'vue'

defineProps<{
  browser: 'chrome' | 'edge'
}>()

const edgeId = useId()
</script>

<template>
  <svg
    v-if="browser === 'chrome'"
    viewBox="0 0 48 48"
    aria-hidden="true"
  >
    <path
      fill="#EA4335"
      d="M24 24 L24 4 A20 20 0 0 1 41.32 34 Z"
    />
    <path
      fill="#34A853"
      d="M24 24 L41.32 34 A20 20 0 0 1 6.68 34 Z"
    />
    <path
      fill="#FBBC05"
      d="M24 24 L6.68 34 A20 20 0 0 1 24 4 Z"
    />
    <circle
      cx="24"
      cy="24"
      r="9"
      fill="#fff"
    />
    <circle
      cx="24"
      cy="24"
      r="6.5"
      fill="#4285F4"
    />
  </svg>
  <svg
    v-else
    viewBox="0 0 48 48"
    aria-hidden="true"
  >
    <defs>
      <linearGradient
        :id="`${edgeId}-body`"
        x1="8"
        y1="6"
        x2="42"
        y2="42"
        gradientUnits="userSpaceOnUse"
      >
        <stop stop-color="#0C59A4" />
        <stop
          offset="0.55"
          stop-color="#1B9DE2"
        />
        <stop
          offset="1"
          stop-color="#3DDC97"
        />
      </linearGradient>
    </defs>
    <path
      :fill="`url(#${edgeId}-body)`"
      d="M24 5c7.6 0 14.2 4.4 17.4 10.8-2.4-1.5-5.2-2.4-8.2-2.4-7.4 0-13.6 5.2-15 12.2-1.6-5.4-6.6-9.4-12.6-9.4-1.2 0-2.4.2-3.4.5C6.4 10.2 14.4 5 24 5z"
    />
    <path
      fill="#35C5F0"
      d="M42.2 19.6c.5 1.4.8 2.9.8 4.4 0 9.4-7.6 17-17 17-5.8 0-10.8-2.8-13.8-7.2 2.6 3 6.4 4.8 10.6 4.8 7.2 0 13-5.8 13-13 0-2.2-.6-4.2-1.5-6 .2 0 4.8 1.6 7.9 4z"
    />
    <path
      fill="#7FBA00"
      d="M22.4 33.2c1.4.8 3 1.2 4.6 1.2 4.6 0 8.4-3.4 9-7.8-1.8 3.2-5.2 5.4-9.2 5.4-1.6 0-3.2-.4-4.4-1.2z"
    />
  </svg>
</template>
