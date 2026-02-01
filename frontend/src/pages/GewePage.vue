<script setup lang="ts">
/**
 * GewePage - Gewe WeChat Integration Panel
 * Admin-only page for managing Gewe WeChat login and settings
 */
import GeweLoginComponent from '@/components/admin/GeweLoginComponent.vue'
</script>

<template>
  <div class="gewe-page flex-1 flex flex-col bg-stone-50 overflow-hidden">
    <div class="gewe-header h-14 px-4 flex items-center bg-white border-b border-stone-200">
      <h1 class="text-sm font-semibold text-stone-900">Gewe</h1>
    </div>
    <div class="gewe-content flex-1 overflow-y-auto px-6 pt-6 pb-6">
      <GeweLoginComponent />
    </div>
  </div>
</template>

<style scoped>
.gewe-page {
  min-height: 0;
}

.gewe-content {
  min-height: 0;
}
</style>
