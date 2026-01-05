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
    <main class="main-content flex-1 flex flex-col overflow-hidden transition-all duration-300 ease-in-out relative">
      <slot />

      <!-- ICP Registration Footer - centered relative to panel -->
      <div class="icp-footer">
        京ICP备2025126228号
      </div>
    </main>
  </div>
</template>

<style scoped>
/* ICP Footer - positioned at bottom of main content area */
.icp-footer {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 8px;
  text-align: center;
  font-size: 12px;
  color: #999;
  user-select: none;
  pointer-events: none;
}
</style>
