<script setup lang="ts">
/**
 * MainLayout - Layout with sidebar and main content area
 * Used for MindMate/MindGraph main page
 */
import { AppSidebar } from '@/components/sidebar'
</script>

<template>
  <div class="main-layout h-screen w-screen flex overflow-hidden">
    <!-- Sidebar -->
    <AppSidebar />

    <!-- Main content -->
    <main
      class="main-content flex-1 flex flex-col overflow-hidden transition-all duration-300 ease-in-out"
    >
      <div class="main-slot flex-1 min-h-0 flex flex-col overflow-hidden">
        <slot />
      </div>
      <!-- ICP Registration Footer - reserved space at bottom -->
      <div class="icp-footer">京ICP备2025126228号</div>
    </main>
  </div>
</template>

<style scoped>
.main-slot {
  flex: 1 1 0;
}

/* Slot content (pages) must fill and shrink for internal scroll to work */
.main-slot > * {
  flex: 1 1 0;
  min-height: 0;
  overflow: hidden;
}

/* ICP Footer - reserved space at bottom, in document flow */
.icp-footer {
  flex-shrink: 0;
  padding: 12px 8px;
  text-align: center;
  font-size: 12px;
  color: #999;
  user-select: none;
  pointer-events: none;
}
</style>
