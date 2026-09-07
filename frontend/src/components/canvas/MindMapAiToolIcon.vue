<script setup lang="ts">
/**
 * AI generate toolbar icons: base tool shape + sparkle characteristic, fused.
 */
defineProps<{
  kind: 'topic' | 'doc' | 'web' | 'voice' | 'brainstorm' | 'chat' | 'subgraph'
}>()
</script>

<template>
  <svg
    class="mm-ai-tool-icon"
    viewBox="0 0 16 16"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
  >
    <g
      class="mm-ai-tool-icon__base"
      stroke="currentColor"
      stroke-width="1.25"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <template v-if="kind === 'topic'">
        <rect
          x="1.35"
          y="6.35"
          width="6.6"
          height="4.2"
          rx="1.15"
        />
        <path d="M7.95 8.45 H10.05 M7.95 8.45 L10.85 12.35" />
        <rect
          x="10.05"
          y="6.55"
          width="3.85"
          height="2.55"
          rx="0.8"
        />
        <rect
          x="10.15"
          y="10.85"
          width="4.15"
          height="2.7"
          rx="0.85"
        />
      </template>
      <template v-else-if="kind === 'doc'">
        <path d="M2.15 2.95 H8.35 L10.85 5.45 V13.2 H2.15 Z" />
        <path d="M8.35 2.95 V5.45 H10.85" />
        <path d="M4.05 8.15 H8.55 M4.05 10.35 H7.15" />
      </template>
      <template v-else-if="kind === 'web'">
        <circle
          cx="6.35"
          cy="8.15"
          r="4.85"
        />
        <ellipse
          cx="6.35"
          cy="8.15"
          rx="2.05"
          ry="4.85"
        />
        <path d="M1.5 8.15 H11.2 M4.05 4.35 Q6.35 6.1 8.65 4.35 M4.05 11.95 Q6.35 10.2 8.65 11.95" />
      </template>
      <template v-else-if="kind === 'voice'">
        <path d="M11.05 5.35 A 4.45 4.45 0 1 1 9.05 2.72" />
        <path d="M3.25 10.28 A 4.95 3.45 0 0 0 10.65 10.28" />
      </template>
      <template v-else-if="kind === 'brainstorm'">
        <rect
          x="1.45"
          y="3.85"
          width="7.1"
          height="3.05"
          rx="0.9"
        />
        <rect
          x="2.25"
          y="7.7"
          width="7.1"
          height="3.05"
          rx="0.9"
        />
        <rect
          x="3.05"
          y="11.55"
          width="6.35"
          height="2.7"
          rx="0.9"
        />
      </template>
      <template v-else-if="kind === 'chat'">
        <path
          d="M2.2 3.55c0-.9.72-1.62 1.62-1.62h7.05c.9 0 1.62.72 1.62 1.62v4.85c0 .9-.72 1.62-1.62 1.62H6.2L3.15 13.05 V10.02 H3.82c-.9 0-1.62-.72-1.62-1.62V3.55Z"
        />
        <path d="M5.05 5.55 H10.15 M5.05 7.55 H8.55" />
      </template>
      <template v-else>
        <rect
          x="4.55"
          y="1.7"
          width="6.9"
          height="3.35"
          rx="0.95"
        />
        <path d="M8 5.05 V7.15 M8 7.15 H4.15 V8.35 M8 7.15 H11.85 V8.35" />
        <rect
          x="1.45"
          y="8.35"
          width="5.4"
          height="3.2"
          rx="0.9"
        />
        <rect
          x="9.15"
          y="8.35"
          width="5.4"
          height="3.2"
          rx="0.9"
        />
      </template>
    </g>
    <g
      v-if="kind === 'voice'"
      class="mm-ai-tool-icon__spark"
    >
      <path
        d="M10.72 2.42c.09-.24.43-.24.52 0l.46 1.18c.04.11.13.2.24.24l1.18.46c.24.09.24.43 0 .52l-1.18.46a.4.4 0 0 0-.24.24l-.46 1.18c-.09.24-.43.24-.52 0l-.46-1.18a.4.4 0 0 0-.24-.24l-1.18-.46c-.24-.09-.24-.43 0-.52l1.18-.46a.4.4 0 0 0 .24-.24L10.72 2.42Z"
      />
      <path
        class="mm-ai-tool-icon__spark--tiny"
        d="M13.55 1.28c.06-.16.28-.16.34 0l.26.68c.03.07.08.12.15.15l.68.26c.16.06.16.28 0 .34l-.68.26a.22.22 0 0 0-.15.15l-.26.68c-.06.16-.28.16-.34 0l-.26-.68a.22.22 0 0 0-.15-.15l-.68-.26c-.16-.06-.16-.28 0-.34l.68-.26a.22.22 0 0 0 .15-.15l.26-.68Z"
      />
    </g>
    <template v-else>
      <path
        class="mm-ai-tool-icon__spark"
        d="M13.22 0.72c.08-.22.4-.22.48 0l.4 1.05c.04.1.12.18.22.22l1.05.4c.22.08.22.4 0 .48l-1.05.4a.4.4 0 0 0-.22.22l-.4 1.05c-.08.22-.4.22-.48 0l-.4-1.05a.4.4 0 0 0-.22-.22l-1.05-.4c-.22-.08-.22-.4 0-.48l1.05-.4a.4.4 0 0 0 .22-.22L13.22.72Z"
      />
      <path
        class="mm-ai-tool-icon__spark mm-ai-tool-icon__spark--tiny"
        d="M15.12 5.05c.05-.14.24-.14.29 0l.22.58c.02.06.07.1.13.13l.58.22c.14.05.14.24 0 .29l-.58.22a.2.2 0 0 0-.13.13l-.22.58c-.05.14-.24.14-.29 0l-.22-.58a.2.2 0 0 0-.13-.13l-.58-.22c-.14-.05-.14-.24 0-.29l.58-.22a.2.2 0 0 0 .13-.13l.22-.58Z"
      />
    </template>
  </svg>
</template>

<style scoped>
.mm-ai-tool-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  overflow: visible;
}

.mm-ai-tool-icon__base {
  fill: none;
}

.mm-ai-tool-icon__spark {
  fill: currentColor;
}

.mm-ai-tool-icon__spark--tiny {
  opacity: 0.72;
}
</style>
