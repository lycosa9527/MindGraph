<script setup lang="ts">
import { useId } from 'vue'

const gradId = `v3-ai-mark-${useId()}`
</script>

<template>
  <svg
    class="v3-ribbon-ai-mark"
    viewBox="0 0 34 22"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    aria-hidden="true"
  >
    <defs>
      <linearGradient
        :id="gradId"
        x1="2"
        y1="2"
        x2="32"
        y2="20"
        gradientUnits="userSpaceOnUse"
      >
        <stop
          offset="0%"
          stop-color="#2563eb"
        />
        <stop
          offset="48%"
          stop-color="#6366f1"
        />
        <stop
          offset="100%"
          stop-color="#a855f7"
        />
      </linearGradient>
    </defs>
    <!-- A -->
    <path
      :fill="`url(#${gradId})`"
      fill-rule="evenodd"
      d="M10.2 2.4c.42-.96 1.78-.96 2.2 0L21.1 20.1c.2.46-.14.95-.64.95h-2.28c-.34 0-.64-.21-.76-.53L16.4 17H6.2l-1.02 3.52c-.12.32-.42.53-.76.53H2.14c-.5 0-.84-.49-.64-.95L10.2 2.4Zm.8 10.86h3.6L12.3 6.7l-1.3 6.56Z"
    />
    <!-- i stem -->
    <rect
      :fill="`url(#${gradId})`"
      x="24.15"
      y="9.15"
      width="4.05"
      height="11.55"
      rx="1.85"
    />
    <!-- sparkle instead of the i-dot -->
    <path
      :fill="`url(#${gradId})`"
      d="M26.18 1.15c.14-.36.7-.36.84 0l.92 2.38c.06.16.18.28.34.34l2.38.92c.36.14.36.7 0 .84l-2.38.92c-.16.06-.28.18-.34.34l-.92 2.38c-.14.36-.7.36-.84 0l-.92-2.38a.6.6 0 0 0-.34-.34l-2.38-.92c-.36-.14-.36-.7 0-.84l2.38-.92c.16-.06.28-.18.34-.34l.92-2.38Z"
    />
  </svg>
</template>

<style scoped>
.v3-ribbon-ai-mark {
  display: block;
  width: 22px;
  height: 15px;
  overflow: visible;
}
</style>
