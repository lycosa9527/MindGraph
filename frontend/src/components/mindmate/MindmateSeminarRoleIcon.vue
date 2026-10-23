<script setup lang="ts">
/**
 * Flat character mark for each seminar role.
 */
import { computed } from 'vue'

import type { SeminarBriefRole } from '@/utils/mindmateSeminarBrief'

const props = withDefaults(
  defineProps<{
    role?: SeminarBriefRole | null
    size?: number
  }>(),
  {
    role: 'observer',
    size: 22,
  }
)

const shown = computed(() => {
  if (props.role == null) {
    return 'plain'
  }
  return props.role === 'none' ? 'observer' : props.role
})

const coat = computed(() => {
  switch (shown.value) {
    case 'leader':
      return '#7c3aed'
    case 'leadPrep':
      return '#4f46e5'
    case 'coPrep':
      return '#0f766e'
    case 'expert':
      return '#c2410c'
    case 'researcher':
      return '#2563eb'
    case 'plain':
      return '#64748b'
    default:
      return '#78716c'
  }
})

const hair = computed(() => {
  switch (shown.value) {
    case 'leader':
      return '#4c1d95'
    case 'leadPrep':
      return '#312e81'
    case 'coPrep':
      return '#115e59'
    case 'expert':
      return '#57534e'
    case 'researcher':
      return '#1e3a8a'
    case 'plain':
      return '#334155'
    default:
      return '#44403c'
  }
})
</script>

<template>
  <svg
    xmlns="http://www.w3.org/2000/svg"
    :width="size"
    :height="size"
    viewBox="0 0 32 32"
    fill="none"
    aria-hidden="true"
  >
    <path
      d="M8.2 29.2c1.1-6.2 3.8-8.8 7.8-8.8s6.7 2.6 7.8 8.8"
      :fill="coat"
    />
    <circle
      cx="16"
      cy="12.2"
      r="6.1"
      fill="#f6c59a"
    />
    <path
      d="M10.2 12.4c.5-4.4 2.8-6.8 5.8-6.8s5.3 2.4 5.8 6.8c-.9-1.7-2.7-2.6-5.8-2.6s-4.9.9-5.8 2.6Z"
      :fill="hair"
    />
    <circle
      cx="13.8"
      cy="12.4"
      r="0.75"
      fill="#1c1917"
    />
    <circle
      cx="17.8"
      cy="12.4"
      r="0.75"
      fill="#1c1917"
    />

    <path
      v-if="shown === 'leader'"
      d="M16 20.6l1.15 2.35 2.55.35-1.85 1.8.45 2.55L16 26.4l-2.3 1.25.45-2.55-1.85-1.8 2.55-.35L16 20.6Z"
      fill="#fbbf24"
    />

    <g v-else-if="shown === 'leadPrep'">
      <rect
        x="18.4"
        y="16.2"
        width="8.2"
        height="10.2"
        rx="1.4"
        fill="#fff"
        stroke="#312e81"
        stroke-width="1.2"
      />
      <path
        d="M20.2 19.2h4.6M20.2 21.6h4.6M20.2 24h3.2"
        stroke="#4f46e5"
        stroke-width="1.1"
        stroke-linecap="round"
      />
    </g>

    <g
      v-else-if="shown === 'coPrep'"
      transform="rotate(-28 23 21)"
    >
      <rect
        x="20.2"
        y="15.2"
        width="3.1"
        height="11.4"
        rx="1.2"
        fill="#fbbf24"
      />
      <path
        d="M20.2 23.4h3.1"
        stroke="#b45309"
        stroke-width="1.1"
      />
      <path
        d="M21.75 14.2l1.55 2.2h-3.1L21.75 14.2Z"
        fill="#f472b6"
      />
    </g>

    <g v-else-if="shown === 'expert'">
      <circle
        cx="13.7"
        cy="12.5"
        r="2.15"
        stroke="#1c1917"
        stroke-width="1.1"
      />
      <circle
        cx="18.1"
        cy="12.5"
        r="2.15"
        stroke="#1c1917"
        stroke-width="1.1"
      />
      <path
        d="M15.8 12.5h.3"
        stroke="#1c1917"
        stroke-width="1.1"
        stroke-linecap="round"
      />
      <circle
        cx="23.4"
        cy="22.4"
        r="3.1"
        fill="#fbbf24"
      />
      <circle
        cx="23.4"
        cy="22.4"
        r="1.35"
        fill="#c2410c"
      />
    </g>

    <g v-else-if="shown === 'researcher'">
      <circle
        cx="22.6"
        cy="20.4"
        r="3.5"
        fill="#eff6ff"
        stroke="#1e3a8a"
        stroke-width="1.4"
      />
      <path
        d="M25.1 22.9l2.6 2.6"
        stroke="#1e3a8a"
        stroke-width="1.6"
        stroke-linecap="round"
      />
    </g>

    <g v-else-if="shown === 'observer'">
      <ellipse
        cx="22.8"
        cy="20.6"
        rx="4.3"
        ry="3.1"
        fill="#fff"
        stroke="#44403c"
        stroke-width="1.2"
      />
      <circle
        cx="22.8"
        cy="20.6"
        r="1.45"
        fill="#7c3aed"
      />
    </g>
  </svg>
</template>
