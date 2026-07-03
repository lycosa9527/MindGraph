<script setup lang="ts">
import { Users } from '@lucide/vue'

defineProps<{
  title?: string
}>()
</script>

<template>
  <span
    class="collab-live-badge"
    :title="title"
  >
    <Users class="w-2.5 h-2.5" />
  </span>
</template>

<style scoped>
.collab-live-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background-color: #22c55e;
  color: #fff;
  margin-left: 4px;
  vertical-align: middle;
  flex-shrink: 0;
  animation: collab-pulse 2s ease-in-out infinite;
}

@keyframes collab-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.55);
  }
  50% {
    box-shadow: 0 0 0 4px rgba(34, 197, 94, 0);
  }
}
</style>
