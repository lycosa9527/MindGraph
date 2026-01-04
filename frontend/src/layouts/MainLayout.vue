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
    <main class="flex-1 flex flex-col overflow-hidden transition-all duration-300 ease-in-out">
      <slot />
    </main>
  </div>
</template>
